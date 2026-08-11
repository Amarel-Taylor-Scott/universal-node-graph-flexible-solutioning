"""Safe authoring helpers for strict Python node contracts.

These helpers remove repetitive manifest code without weakening the NodeSpec
ABI.  They inspect the callable that will actually execute, reject signatures
the runtime cannot invoke, hash its source, and create stable parameter-bound
candidate identities.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import product
from math import prod
from typing import Any

from solutiongraph.executor import callable_implementation_digest
from solutiongraph.model import (
    Candidate,
    Determinism,
    FailureMode,
    Idempotency,
    NodeSpec,
    ParameterSpec,
    Port,
    Registry,
    ResourceClaim,
    canonical_json,
    sha256_digest,
)

AUTHORING_MODEL_VERSION = "0.1"


def _entrypoint(function: Callable[..., Any]) -> str:
    module = getattr(function, "__module__", "")
    name = getattr(function, "__name__", "")
    qualname = getattr(function, "__qualname__", "")
    if not module or not name or qualname != name or "<locals>" in qualname:
        raise ValueError(
            "Python nodes must use an importable top-level function; closures, "
            "lambdas, bound methods, and nested functions are not portable entrypoints"
        )
    return f"{module}:{name}"


def validate_python_signature(
    function: Callable[..., Any],
    inputs: tuple[Port, ...],
    parameters: tuple[ParameterSpec, ...],
) -> list[str]:
    """Return ABI/signature mismatches for the keyword-only runtime invocation."""
    problems: list[str] = []
    input_names = [port.name for port in inputs]
    parameter_names = [parameter.name for parameter in parameters]
    overlap = sorted(set(input_names) & set(parameter_names))
    if overlap:
        problems.append(
            "input ports and parameters overlap: " + ", ".join(overlap)
        )
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError) as exc:
        return [f"callable signature cannot be inspected: {exc}"]
    declared = set(input_names) | set(parameter_names)
    accepts_kwargs = any(
        item.kind == inspect.Parameter.VAR_KEYWORD
        for item in signature.parameters.values()
    )
    keyword_parameters = {
        name
        for name, item in signature.parameters.items()
        if item.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    positional_only = {
        name
        for name, item in signature.parameters.items()
        if item.kind == inspect.Parameter.POSITIONAL_ONLY
    }
    unsupported = sorted(declared & positional_only)
    if unsupported:
        problems.append(
            "runtime cannot bind positional-only inputs or parameters: "
            + ", ".join(unsupported)
        )
    missing = sorted(declared - keyword_parameters) if not accepts_kwargs else []
    if missing:
        problems.append(
            "callable does not accept declared inputs or parameters: "
            + ", ".join(missing)
        )
    unexpected_required = sorted(
        name
        for name, item in signature.parameters.items()
        if item.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY)
        and item.default is inspect.Parameter.empty
        and name not in declared
    )
    if unexpected_required:
        problems.append(
            "callable requires undeclared arguments: "
            + ", ".join(unexpected_required)
        )
    return problems


@dataclass(frozen=True)
class PythonNodeDefinition:
    """An executable Python function paired with its strict portable NodeSpec."""

    function: Callable[..., Any]
    spec: NodeSpec

    def validate(self) -> list[str]:
        problems = self.spec.validate()
        problems.extend(
            validate_python_signature(self.function, self.spec.inputs, self.spec.parameters)
        )
        try:
            expected_entrypoint = _entrypoint(self.function)
        except ValueError as exc:
            problems.append(str(exc))
        else:
            if self.spec.entrypoint != expected_entrypoint:
                problems.append("NodeSpec entrypoint does not identify the supplied callable")
        try:
            digest = callable_implementation_digest(self.function)
        except (OSError, TypeError) as exc:
            problems.append(f"callable source cannot be hashed: {exc}")
        else:
            if self.spec.implementation_digest != digest:
                problems.append("NodeSpec implementation_digest does not match callable source")
        return problems

    def candidate(
        self,
        parameters: Mapping[str, Any] | None = None,
        *,
        candidate_id: str | None = None,
        deployment: str = "",
    ) -> Candidate:
        return bind_candidate(
            self.spec,
            parameters or {},
            candidate_id=candidate_id,
            deployment=deployment,
        )

    def candidates(
        self,
        *,
        fixed_parameters: Mapping[str, Any] | None = None,
        max_candidates: int | None = None,
        deployment: str = "",
    ) -> tuple[Candidate, ...]:
        return enumerate_candidates(
            self.spec,
            fixed_parameters=fixed_parameters,
            max_candidates=max_candidates,
            deployment=deployment,
        )


def define_python_node(
    *,
    node_id: str,
    function: Callable[..., Any],
    inputs: tuple[Port, ...],
    outputs: tuple[Port, ...],
    capabilities: tuple[str, ...],
    description: str,
    version: str = "1.0.0",
    parameters: tuple[ParameterSpec, ...] = (),
    effects: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
    determinism: Determinism = Determinism.DETERMINISTIC,
    idempotency: Idempotency = Idempotency.IDEMPOTENT,
    preconditions: tuple[str, ...] = (),
    postconditions: tuple[str, ...] = (),
    invariants: tuple[str, ...] = (),
    failure_modes: tuple[FailureMode, ...] = (),
    resources: tuple[ResourceClaim, ...] = (),
    verifier: str = "",
    source: str = "",
) -> PythonNodeDefinition:
    """Create and immediately validate a portable Python node definition."""
    signature_problems = validate_python_signature(function, inputs, parameters)
    if signature_problems:
        raise ValueError("invalid Python node signature: " + "; ".join(signature_problems))
    entrypoint = _entrypoint(function)
    spec = NodeSpec(
        id=node_id,
        version=version,
        implementation_digest=callable_implementation_digest(function),
        inputs=inputs,
        outputs=outputs,
        runtime="python",
        entrypoint=entrypoint,
        description=description,
        parameters=parameters,
        capabilities=capabilities,
        effects=effects,
        permissions=permissions,
        determinism=determinism,
        idempotency=idempotency,
        preconditions=preconditions,
        postconditions=postconditions,
        invariants=invariants,
        failure_modes=failure_modes,
        resources=resources,
        verifier=verifier,
        source=source or function.__module__.replace(".", "/") + ".py",
    )
    definition = PythonNodeDefinition(function, spec)
    problems = definition.validate()
    if problems:
        raise ValueError("invalid Python node definition: " + "; ".join(problems))
    return definition


def _candidate_suffix(parameters: Mapping[str, Any]) -> str:
    if not parameters:
        return "default"
    digest = sha256_digest(dict(parameters)).removeprefix("sha256:")[:12]
    labels = []
    for key, value in sorted(parameters.items()):
        token = re.sub(r"[^a-z0-9-]+", "-", str(value).lower()).strip("-")
        if token:
            labels.append(f"{key}-{token[:20]}")
    readable = "-".join(labels)[:64].strip("-") or "binding"
    return f"{readable}-{digest}"


def bind_candidate(
    node: NodeSpec,
    parameters: Mapping[str, Any],
    *,
    candidate_id: str | None = None,
    deployment: str = "",
) -> Candidate:
    """Freeze one exact node parameter binding with a stable identity."""
    # Ensure values have one content-addressable representation before creating
    # an identity that could otherwise vary between processes.
    canonical_json(dict(parameters))
    candidate = Candidate(
        id=candidate_id or f"candidate.{node.id}.{_candidate_suffix(parameters)}",
        node_id=node.id,
        node_version=node.version,
        implementation_digest=node.implementation_digest,
        parameters=dict(parameters),
        deployment=deployment,
    )
    problems = candidate.validate(node)
    if problems:
        raise ValueError("invalid candidate binding: " + "; ".join(problems))
    return candidate


def enumerate_candidates(
    node: NodeSpec,
    *,
    fixed_parameters: Mapping[str, Any] | None = None,
    max_candidates: int | None = None,
    deployment: str = "",
) -> tuple[Candidate, ...]:
    """Enumerate the declared finite parameter grid without a hidden cap.

    ``max_candidates`` is an explicit caller guard.  If the exact grid exceeds
    it, enumeration fails with the exact size rather than silently truncating.
    """
    fixed = dict(fixed_parameters or {})
    known = {parameter.name for parameter in node.parameters}
    unknown = sorted(set(fixed) - known)
    if unknown:
        raise ValueError("fixed parameters are not declared: " + ", ".join(unknown))
    names: list[str] = []
    choices: list[tuple[Any, ...]] = []
    omitted: set[str] = set()
    for parameter in node.parameters:
        names.append(parameter.name)
        if parameter.name in fixed:
            choices.append((fixed[parameter.name],))
        elif parameter.choices:
            choices.append(tuple(parameter.choices))
        elif parameter.default is not None:
            choices.append((parameter.default,))
        elif parameter.required:
            raise ValueError(
                f"required parameter {parameter.name} has no finite choices or fixed binding"
            )
        else:
            choices.append((None,))
            omitted.add(parameter.name)
    exact_count = prod(len(items) for items in choices) if choices else 1
    if max_candidates is not None:
        if max_candidates <= 0:
            raise ValueError("max_candidates must be positive")
        if exact_count > max_candidates:
            raise ValueError(
                f"declared parameter grid has {exact_count} candidates, exceeding "
                f"explicit max_candidates={max_candidates}"
            )
    bindings = product(*choices) if choices else ((),)
    return tuple(
        bind_candidate(
            node,
            {
                name: value
                for name, value in zip(names, values, strict=True)
                if name not in omitted
            },
            deployment=deployment,
        )
        for values in bindings
    )


def build_python_registry(
    registry_id: str,
    version: str,
    definitions: Iterable[PythonNodeDefinition],
    *,
    candidates: Iterable[Candidate] | None = None,
) -> Registry:
    """Build a validated registry, generating one default candidate per node."""
    items = tuple(definitions)
    nodes = tuple(item.spec for item in items)
    supplied_candidates = (
        tuple(candidates)
        if candidates is not None
        else tuple(item.candidate() for item in items)
    )
    registry = Registry(registry_id, version, nodes, supplied_candidates)
    node_keys = [(node.id, node.version) for node in nodes]
    if len(node_keys) != len(set(node_keys)):
        raise ValueError("registry node id/version pairs must be unique")
    candidate_ids = [candidate.id for candidate in supplied_candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("registry candidate ids must be unique")
    node_map = registry.node_map()
    problems = [
        problem
        for index, candidate in enumerate(supplied_candidates)
        for problem in candidate.validate(
            node_map.get((candidate.node_id, candidate.node_version)),
            f"candidates[{index}]",
        )
    ]
    if problems:
        raise ValueError("invalid registry: " + "; ".join(problems))
    return registry


__all__ = [
    "AUTHORING_MODEL_VERSION",
    "PythonNodeDefinition",
    "bind_candidate",
    "build_python_registry",
    "define_python_node",
    "enumerate_candidates",
    "validate_python_signature",
]
