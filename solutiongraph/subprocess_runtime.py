"""Strict JSON/bytes subprocess adapter for trusted Python node entrypoints.

This adapter provides process lifecycle isolation, wall-clock termination, and
optional POSIX CPU/address-space limits.  It deliberately does *not* claim to
be a hostile-code sandbox: the child still has the operating-system authority
of the current user unless an outer container, microVM, Wasm, or remote runner
removes it.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from solutiongraph.executor import (
    ExecutionError,
    NodeExecutionFailure,
    PythonRuntime,
    _RuntimeExecutionFailure,
)
from solutiongraph.model import NodeSpec, sha256_digest

SUBPROCESS_PROTOCOL_VERSION = "1.0"


def _encode_portable(value: Any) -> dict[str, Any]:
    """Encode JSON-compatible values and bytes without reserved-key collisions."""
    if value is None:
        return {"kind": "null"}
    if isinstance(value, bool):
        return {"kind": "boolean", "value": value}
    if isinstance(value, int):
        return {"kind": "integer", "value": value}
    if isinstance(value, float):
        if not isfinite(value):
            raise ExecutionError("subprocess values must not contain non-finite numbers")
        return {"kind": "number", "value": value}
    if isinstance(value, str):
        return {"kind": "string", "value": value}
    if isinstance(value, bytes):
        return {
            "kind": "bytes",
            "base64": base64.b64encode(value).decode("ascii"),
        }
    if isinstance(value, tuple):
        return {"kind": "tuple", "items": [_encode_portable(item) for item in value]}
    if isinstance(value, list):
        return {"kind": "list", "items": [_encode_portable(item) for item in value]}
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ExecutionError("subprocess mappings require string keys")
        return {
            "kind": "mapping",
            "items": [
                [key, _encode_portable(value[key])] for key in sorted(value)
            ],
        }
    raise ExecutionError(
        "subprocess values must be null, booleans, finite numbers, strings, "
        f"bytes, lists, tuples, or string-keyed mappings; got {type(value).__name__}"
    )


def _decode_portable(payload: Any) -> Any:
    if not isinstance(payload, Mapping):
        raise ExecutionError("subprocess value envelope must be an object")
    kind = payload.get("kind")
    if kind == "null" and set(payload) == {"kind"}:
        return None
    if kind == "boolean" and set(payload) == {"kind", "value"}:
        value = payload["value"]
        if isinstance(value, bool):
            return value
    if kind == "integer" and set(payload) == {"kind", "value"}:
        value = payload["value"]
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    if kind == "number" and set(payload) == {"kind", "value"}:
        value = payload["value"]
        if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value):
            return float(value)
    if kind == "string" and set(payload) == {"kind", "value"}:
        value = payload["value"]
        if isinstance(value, str):
            return value
    if kind == "bytes" and set(payload) == {"kind", "base64"}:
        encoded = payload["base64"]
        if isinstance(encoded, str):
            try:
                return base64.b64decode(encoded, validate=True)
            except ValueError as exc:
                raise ExecutionError("subprocess byte value is not valid base64") from exc
    if kind in {"list", "tuple"} and set(payload) == {"kind", "items"}:
        items = payload["items"]
        if isinstance(items, list):
            decoded = [_decode_portable(item) for item in items]
            return tuple(decoded) if kind == "tuple" else decoded
    if kind == "mapping" and set(payload) == {"kind", "items"}:
        items = payload["items"]
        if isinstance(items, list):
            result: dict[str, Any] = {}
            for pair in items:
                if (
                    not isinstance(pair, list)
                    or len(pair) != 2
                    or not isinstance(pair[0], str)
                    or pair[0] in result
                ):
                    raise ExecutionError("subprocess mapping envelope is malformed")
                result[pair[0]] = _decode_portable(pair[1])
            return result
    raise ExecutionError(f"invalid subprocess value envelope for kind {kind!r}")


def _protocol_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class SubprocessPythonRuntime:
    """Invoke Python nodes in a fresh child process through a strict wire ABI."""

    runtime_id: str = "python"
    isolation: str = "subprocess"
    adapter_id: str = "solutiongraph.python-subprocess-v1"
    timeout_seconds: float = 30.0
    max_output_bytes: int = 8 * 1024 * 1024
    max_memory_mb: int | None = 512
    max_cpu_seconds: int | None = 30
    python_executable: str = sys.executable
    environment_allowlist: tuple[str, ...] = (
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONHASHSEED",
        "PYTHONPATH",
        "SYSTEMROOT",
        "TMP",
        "TEMP",
    )

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        if self.max_memory_mb is not None and self.max_memory_mb <= 0:
            raise ValueError("max_memory_mb must be positive or null")
        if self.max_cpu_seconds is not None and self.max_cpu_seconds <= 0:
            raise ValueError("max_cpu_seconds must be positive or null")

    @property
    def environment_identity(self) -> str:
        return sha256_digest(
            {
                "adapter": self.adapter_id,
                "protocol": SUBPROCESS_PROTOCOL_VERSION,
                "python": self.python_executable,
                "timeout_seconds": self.timeout_seconds,
                "max_output_bytes": self.max_output_bytes,
                "max_memory_mb": self.max_memory_mb,
                "max_cpu_seconds": self.max_cpu_seconds,
                "environment_allowlist": self.environment_allowlist,
            }
        )

    def implementation_digest(self, node: NodeSpec) -> str:
        # Inspect in the parent before starting the child.  The frozen digest is
        # still checked again by ReferenceExecutor before invocation.
        return PythonRuntime().implementation_digest(node)

    def _environment(self) -> dict[str, str]:
        environment = {
            key: os.environ[key]
            for key in self.environment_allowlist
            if key in os.environ
        }
        # Editable installs and test modules may live only on the current
        # interpreter path.  Preserve that import identity explicitly.
        import_paths = [item for item in sys.path if item]
        existing = environment.get("PYTHONPATH", "")
        if existing:
            import_paths.extend(existing.split(os.pathsep))
        environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(import_paths))
        environment.setdefault("PYTHONHASHSEED", "0")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return environment

    def invoke(
        self,
        node: NodeSpec,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
    ) -> Any:
        arguments = dict(inputs)
        overlap = set(arguments).intersection(parameters)
        if overlap:
            raise ExecutionError(
                "node port and parameter names overlap at runtime: "
                + ", ".join(sorted(overlap))
            )
        arguments.update(parameters)
        request = {
            "protocol": SUBPROCESS_PROTOCOL_VERSION,
            "entrypoint": node.entrypoint,
            "arguments": {
                name: _encode_portable(value)
                for name, value in sorted(arguments.items())
            },
            "limits": {
                "memory_bytes": (
                    self.max_memory_mb * 1024 * 1024
                    if self.max_memory_mb is not None
                    else None
                ),
                "cpu_seconds": self.max_cpu_seconds,
                "max_output_bytes": self.max_output_bytes,
            },
        }
        try:
            completed = subprocess.run(
                [self.python_executable, "-m", "solutiongraph._subprocess_worker"],
                input=_protocol_json(request),
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
                env=self._environment(),
            )
        except subprocess.TimeoutExpired as exc:
            raise _RuntimeExecutionFailure(
                "runtime.timeout",
                f"{node.id} exceeded {self.timeout_seconds:g} seconds",
            ) from exc
        except OSError as exc:
            raise _RuntimeExecutionFailure(
                "runtime.subprocess-start",
                f"could not start subprocess for {node.id}: {exc}",
            ) from exc

        if len(completed.stdout) > self.max_output_bytes:
            raise _RuntimeExecutionFailure(
                "runtime.output-limit",
                f"{node.id} runtime protocol output exceeded {self.max_output_bytes} bytes",
            )
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace")[-2000:]
            raise _RuntimeExecutionFailure(
                "runtime.subprocess-crash",
                f"{node.id} subprocess exited {completed.returncode}: {stderr}",
            )
        try:
            response = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _RuntimeExecutionFailure(
                "runtime.protocol",
                f"{node.id} returned an invalid subprocess response",
            ) from exc
        if not isinstance(response, Mapping) or response.get("protocol") != SUBPROCESS_PROTOCOL_VERSION:
            raise _RuntimeExecutionFailure(
                "runtime.protocol",
                f"{node.id} returned an incompatible subprocess protocol",
            )
        status = response.get("status")
        if status == "succeeded" and set(response) >= {"protocol", "status", "result"}:
            try:
                return _decode_portable(response["result"])
            except ExecutionError as exc:
                raise _RuntimeExecutionFailure("runtime.protocol", str(exc)) from exc
        if status == "node_failure":
            failure_class = response.get("failure_class")
            message = response.get("message")
            retryable = response.get("retryable")
            if (
                not isinstance(failure_class, str)
                or not isinstance(message, str)
                or not isinstance(retryable, bool)
            ):
                raise _RuntimeExecutionFailure(
                    "runtime.protocol", f"{node.id} returned a malformed node failure"
                )
            raise NodeExecutionFailure(
                failure_class,
                message,
                retryable=retryable,
            )
        if status == "exception":
            exception_type = response.get("exception_type", "Exception")
            message = response.get("message", "child node raised")
            raise _RuntimeExecutionFailure(
                "runtime.exception",
                f"{exception_type}: {message}",
            )
        raise _RuntimeExecutionFailure(
            "runtime.protocol", f"{node.id} returned unknown subprocess status {status!r}"
        )


__all__ = [
    "SUBPROCESS_PROTOCOL_VERSION",
    "SubprocessPythonRuntime",
]
