"""Private child-process endpoint for :mod:`solutiongraph.subprocess_runtime`."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
from collections.abc import Mapping
from typing import Any

from solutiongraph.executor import NodeExecutionFailure
from solutiongraph.subprocess_runtime import (
    SUBPROCESS_PROTOCOL_VERSION,
    _decode_portable,
    _encode_portable,
    _protocol_json,
)


def _apply_limits(limits: Mapping[str, Any]) -> None:
    try:
        import resource
    except ImportError:  # pragma: no cover - Windows has no resource module
        return
    memory_bytes = limits.get("memory_bytes")
    cpu_seconds = limits.get("cpu_seconds")
    if isinstance(memory_bytes, int) and memory_bytes > 0:
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    if isinstance(cpu_seconds, int) and cpu_seconds > 0:
        # The hard limit is one second above the soft limit so Python has a
        # chance to terminate cleanly before the kernel sends SIGKILL.
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))


def _resolve(entrypoint: str):
    module_name, separator, attribute = entrypoint.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("python entrypoint must use module:callable syntax")
    function = getattr(importlib.import_module(module_name), attribute, None)
    if not callable(function):
        raise ValueError("python entrypoint is not callable")
    return function


def _response(payload: Mapping[str, Any]) -> None:
    sys.stdout.buffer.write(_protocol_json(payload))
    sys.stdout.buffer.flush()


def main() -> int:
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if not isinstance(request, Mapping):
            raise ValueError("request must be an object")
        if request.get("protocol") != SUBPROCESS_PROTOCOL_VERSION:
            raise ValueError("incompatible subprocess protocol")
        entrypoint = request.get("entrypoint")
        arguments = request.get("arguments")
        limits = request.get("limits", {})
        if not isinstance(entrypoint, str) or not isinstance(arguments, Mapping):
            raise ValueError("request entrypoint or arguments are malformed")
        if not isinstance(limits, Mapping):
            raise ValueError("request limits are malformed")
        _apply_limits(limits)
        decoded = {
            name: _decode_portable(value)
            for name, value in arguments.items()
            if isinstance(name, str)
        }
        if len(decoded) != len(arguments):
            raise ValueError("argument names must be strings")
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = _resolve(entrypoint)(**decoded)
        except NodeExecutionFailure as exc:
            _response({
                "protocol": SUBPROCESS_PROTOCOL_VERSION,
                "status": "node_failure",
                "failure_class": exc.failure_class,
                "message": str(exc),
                "retryable": exc.retryable,
                "stdout": stdout.getvalue()[-4000:],
                "stderr": stderr.getvalue()[-4000:],
            })
            return 0
        except BaseException as exc:  # the protocol must preserve child failure
            _response({
                "protocol": SUBPROCESS_PROTOCOL_VERSION,
                "status": "exception",
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "stdout": stdout.getvalue()[-4000:],
                "stderr": stderr.getvalue()[-4000:],
            })
            return 0
        encoded = _encode_portable(result)
        response = {
            "protocol": SUBPROCESS_PROTOCOL_VERSION,
            "status": "succeeded",
            "result": encoded,
            "stdout": stdout.getvalue()[-4000:],
            "stderr": stderr.getvalue()[-4000:],
        }
        max_output_bytes = limits.get("max_output_bytes")
        if isinstance(max_output_bytes, int) and len(_protocol_json(response)) > max_output_bytes:
            _response({
                "protocol": SUBPROCESS_PROTOCOL_VERSION,
                "status": "exception",
                "exception_type": "OutputLimitExceeded",
                "message": "encoded result exceeds the configured protocol output limit",
            })
            return 0
        _response(response)
        return 0
    except BaseException as exc:
        _response({
            "protocol": SUBPROCESS_PROTOCOL_VERSION,
            "status": "exception",
            "exception_type": type(exc).__name__,
            "message": str(exc),
        })
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
