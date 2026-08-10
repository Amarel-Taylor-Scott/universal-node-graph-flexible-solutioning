"""Small executable reference node pack and its discovery descriptors.

These primitives demonstrate the portable ABI. They are not a privileged
standard library and production registries may provide different candidates.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from solutiongraph.discovery import NodeDescriptor, PortMeaning, SearchDocument
from solutiongraph.model import (
    Candidate,
    Determinism,
    FailureMode,
    Idempotency,
    NodeSpec,
    ParameterSpec,
    Port,
    Registry,
    ValueType,
    sha256_digest,
)

JSON_VALUE = ValueType("reference.json-value", media_type="application/json")
JSON_OBJECT = ValueType("reference.json-object", media_type="application/json")
JSON_TEXT = ValueType("reference.json-text", media_type="application/json")
FILE_PATH = ValueType("reference.file-path", media_type="text/plain")
HTTP_REQUEST = ValueType("reference.http-request", media_type="application/json")


def identity_json(value: Any) -> Any:
    """Return a JSON-compatible value unchanged."""
    json.dumps(value, allow_nan=False)
    return value


def parse_json(text: str) -> Any:
    """Parse strict JSON text."""
    return json.loads(text)


def require_keys(value: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    """Return a shallow copy after checking all required keys."""
    if not isinstance(value, Mapping):
        raise TypeError("value must be a JSON object")
    missing = sorted(set(keys) - set(value))
    if missing:
        raise ValueError("missing required keys: " + ", ".join(missing))
    return dict(value)


def read_local_json(path: str) -> Any:
    """Read one explicit local JSON path; the node contract declares this effect."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fetch_http_json(request: Mapping[str, Any]) -> Any:
    """Fetch JSON through one explicit read-only HTTP request mapping."""
    method = str(request.get("method", "GET")).upper()
    if method not in {"GET", "HEAD"}:
        raise ValueError("reference.fetch-http-json permits only GET or HEAD")
    url = str(request["url"])
    headers = {str(key): str(value) for key, value in request.get("headers", {}).items()}
    timeout = float(request.get("timeout_seconds", 30.0))
    with urlopen(Request(url, None, headers, method=method), timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _implementation_digest(entrypoint: str) -> str:
    """Hash the declared Python entrypoint source, not a mutable package label."""
    return sha256_digest(inspect.getsource(globals()[entrypoint]))


REFERENCE_NODE_SPECS = (
    NodeSpec(
        id="reference.identity-json",
        version="1.0.0",
        implementation_digest=_implementation_digest("identity_json"),
        inputs=(Port("value", JSON_VALUE),),
        outputs=(Port("value", JSON_VALUE),),
        runtime="python",
        entrypoint="solutiongraph.reference_nodes:identity_json",
        description="Validate JSON compatibility and return the exact value unchanged.",
        capabilities=("control.identity",),
        determinism=Determinism.DETERMINISTIC,
        idempotency=Idempotency.IDEMPOTENT,
        postconditions=("Output is structurally equal to input.",),
        verifier="reference.verify.structural-equality",
        source="solutiongraph/reference_nodes.py",
    ),
    NodeSpec(
        id="reference.parse-json",
        version="1.0.0",
        implementation_digest=_implementation_digest("parse_json"),
        inputs=(Port("text", JSON_TEXT),),
        outputs=(Port("value", JSON_VALUE),),
        runtime="python",
        entrypoint="solutiongraph.reference_nodes:parse_json",
        description="Parse JSON text without repairing malformed input.",
        capabilities=("data.parse-json",),
        determinism=Determinism.DETERMINISTIC,
        idempotency=Idempotency.IDEMPOTENT,
        failure_modes=(FailureMode("data.invalid-json", False, "Input is not strict JSON."),),
        verifier="reference.verify.json-roundtrip",
        source="solutiongraph/reference_nodes.py",
    ),
    NodeSpec(
        id="reference.require-keys",
        version="1.0.0",
        implementation_digest=_implementation_digest("require_keys"),
        inputs=(Port("value", JSON_OBJECT),),
        outputs=(Port("value", JSON_OBJECT),),
        runtime="python",
        entrypoint="solutiongraph.reference_nodes:require_keys",
        description="Require a finite configured set of object keys.",
        parameters=(
            ParameterSpec(
                "keys",
                "array[string]",
                required=True,
                description="Required object keys.",
            ),
        ),
        capabilities=("data.require-keys",),
        determinism=Determinism.DETERMINISTIC,
        idempotency=Idempotency.IDEMPOTENT,
        preconditions=("Input is a JSON object.",),
        failure_modes=(
            FailureMode("data.invalid-shape", False, "Input is not a JSON object."),
            FailureMode("data.missing-key", False, "A required key is absent."),
        ),
        verifier="reference.verify.required-keys",
        source="solutiongraph/reference_nodes.py",
    ),
    NodeSpec(
        id="reference.read-local-json",
        version="1.0.0",
        implementation_digest=_implementation_digest("read_local_json"),
        inputs=(Port("path", FILE_PATH),),
        outputs=(Port("value", JSON_VALUE),),
        runtime="python",
        entrypoint="solutiongraph.reference_nodes:read_local_json",
        description="Read strict JSON from one explicitly provided local path.",
        capabilities=("connector.file-json",),
        effects=("filesystem.read",),
        permissions=("filesystem.read",),
        determinism=Determinism.RECORDED,
        idempotency=Idempotency.CONDITIONAL,
        failure_modes=(
            FailureMode("filesystem.not-found", False, "The requested path does not exist."),
            FailureMode("data.invalid-json", False, "File content is not strict JSON."),
        ),
        verifier="reference.verify.content-digest",
        source="solutiongraph/reference_nodes.py",
    ),
    NodeSpec(
        id="reference.fetch-http-json",
        version="1.0.0",
        implementation_digest=_implementation_digest("fetch_http_json"),
        inputs=(Port("request", HTTP_REQUEST),),
        outputs=(Port("value", JSON_VALUE),),
        runtime="python",
        entrypoint="solutiongraph.reference_nodes:fetch_http_json",
        description="Execute an explicit read-only HTTP request and parse JSON.",
        capabilities=("connector.http-json",),
        effects=("network.read",),
        permissions=("network.read",),
        determinism=Determinism.RECORDED,
        idempotency=Idempotency.CONDITIONAL,
        preconditions=(
            "The request policy authorizes the URL.",
            "The request method is GET or HEAD and has no body.",
        ),
        failure_modes=(
            FailureMode(
                "policy.disallowed-method",
                False,
                "The request method is not GET or HEAD.",
            ),
            FailureMode("network.timeout", True, "The request exceeded its timeout."),
            FailureMode("network.http-error", True, "The remote service returned an error."),
            FailureMode("data.invalid-json", False, "The response is not strict JSON."),
        ),
        verifier="reference.verify.http-receipt",
        source="solutiongraph/reference_nodes.py",
    ),
)


REFERENCE_CANDIDATES = tuple(
    Candidate(
        id=f"candidate.{node.id}.default",
        node_id=node.id,
        node_version=node.version,
        implementation_digest=node.implementation_digest,
    )
    for node in REFERENCE_NODE_SPECS
    if not node.parameters
) + (
    Candidate(
        id="candidate.reference.require-keys.identifier",
        node_id="reference.require-keys",
        node_version="1.0.0",
        implementation_digest=next(
            node.implementation_digest
            for node in REFERENCE_NODE_SPECS
            if node.id == "reference.require-keys"
        ),
        parameters={"keys": ["id"]},
    ),
)


REFERENCE_REGISTRY = Registry(
    "reference.core-registry",
    "1.0.0",
    REFERENCE_NODE_SPECS,
    REFERENCE_CANDIDATES,
)


def _descriptor(
    node: NodeSpec, *, purposes: tuple[str, ...], domains: tuple[str, ...]
) -> NodeDescriptor:
    return NodeDescriptor(
        node_id=node.id,
        node_version=node.version,
        node_spec_digest=node.digest,
        title=node.id.rsplit(".", 1)[-1].replace("-", " ").title(),
        summary=node.description,
        purposes=purposes,
        actions=(node.capabilities[0],),
        domains=domains,
        tags=("reference",),
        ports=tuple(PortMeaning("input", port.name, port.description) for port in node.inputs)
        + tuple(PortMeaning("output", port.name, port.description) for port in node.outputs),
        documents=(
            SearchDocument(
                f"document.{node.id}",
                f"{node.description} Effects: {', '.join(node.effects) or 'none'}. "
                f"Capabilities: {', '.join(node.capabilities)}.",
                targets=("node", "node.inputs", "node.outputs"),
            ),
        ),
        extensions=(("reference.maturity", "demonstration"),),
    )


REFERENCE_DESCRIPTORS = tuple(
    _descriptor(
        node,
        purposes=(
            (
                "Connect a graph to an explicitly authorized external resource."
                if node.effects
                else "Perform a small deterministic data or control operation."
            ),
        ),
        domains=(("integration.external",) if node.effects else ("software.general",)),
    )
    for node in REFERENCE_NODE_SPECS
)


__all__ = [
    "REFERENCE_CANDIDATES",
    "REFERENCE_DESCRIPTORS",
    "REFERENCE_NODE_SPECS",
    "REFERENCE_REGISTRY",
    "fetch_http_json",
    "identity_json",
    "parse_json",
    "read_local_json",
    "require_keys",
]
