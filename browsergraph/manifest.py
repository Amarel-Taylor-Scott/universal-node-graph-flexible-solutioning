"""Canonical, domain-neutral node descriptions.

The runtime ``Contract`` intentionally stays small: it contains the declarations
the browser scheduler and linter already enforce.  A ``NodeManifest`` is the
richer, portable envelope used by registries, graph compilers and viewers.  It
describes technical ports, human documentation, configuration, effects,
permissions, dependencies and learned performance priors without changing how
the wrapped node executes.

Existing nodes need no rewrite. ``manifest_of(node)`` infers a useful manifest
from their current contract, while ``NodeDefinition`` is the thin wrapper for
authors who want to supply the full description explicitly.
"""
from __future__ import annotations

import inspect
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from importlib.resources import files
from typing import Any

from browsergraph.contracts import KIND_RE, contract_of

MANIFEST_SCHEMA_VERSION = "1.0"
NODE_ID_RE = re.compile(r"^[a-z][a-z0-9_.:/-]*$")


@dataclass(frozen=True)
class PortSpec:
    """One typed input or output port in a node manifest."""

    name: str
    data_type: str = "any"
    description: str = ""
    required: bool = True
    semantic_type: str = ""
    units: str = ""
    schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "data_type": self.data_type,
            "description": self.description,
            "required": self.required,
            "semantic_type": self.semantic_type,
            "units": self.units,
            "schema": dict(self.schema),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PortSpec:
        return cls(
            name=str(data["name"]),
            data_type=str(data.get("data_type", "any")),
            description=str(data.get("description", "")),
            required=bool(data.get("required", True)),
            semantic_type=str(data.get("semantic_type", "")),
            units=str(data.get("units", "")),
            schema=dict(data.get("schema") or {}),
        )


@dataclass(frozen=True)
class ParameterSpec:
    """A configurable value accepted by a node factory."""

    name: str
    data_type: str = "any"
    description: str = ""
    required: bool = False
    default: Any = None
    choices: tuple[Any, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "data_type": self.data_type,
            "description": self.description,
            "required": self.required,
            "default": self.default,
            "choices": list(self.choices),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParameterSpec:
        return cls(
            name=str(data["name"]),
            data_type=str(data.get("data_type", "any")),
            description=str(data.get("description", "")),
            required=bool(data.get("required", False)),
            default=data.get("default"),
            choices=tuple(data.get("choices") or ()),
        )


@dataclass(frozen=True)
class NodeManifest:
    """Portable definition of a node, independent of its Python implementation."""

    id: str
    kind: str
    name: str
    version: str = "0.1.0"
    schema_version: str = MANIFEST_SCHEMA_VERSION
    description: str = ""
    roles: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    inputs: tuple[PortSpec, ...] = ()
    outputs: tuple[PortSpec, ...] = ()
    parameters: tuple[ParameterSpec, ...] = ()
    effects: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    resources: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    intelligence: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    docs: str = ""
    tags: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.schema_version != MANIFEST_SCHEMA_VERSION:
            problems.append(
                f"schema_version must be {MANIFEST_SCHEMA_VERSION!r}, "
                f"got {self.schema_version!r}")
        if not NODE_ID_RE.fullmatch(self.id):
            problems.append(f"id {self.id!r} must be a lowercase namespaced identifier")
        if not KIND_RE.fullmatch(self.kind):
            problems.append(f"kind {self.kind!r} must be snake_case")
        if not self.name.strip():
            problems.append("name must not be empty")
        if not self.version.strip():
            problems.append("version must not be empty")

        for label, items in (
            ("input", self.inputs),
            ("output", self.outputs),
            ("parameter", self.parameters),
        ):
            names = [item.name for item in items]
            duplicates = sorted({name for name in names if names.count(name) > 1})
            if duplicates:
                problems.append(f"duplicate {label} name(s): {', '.join(duplicates)}")
            if any(not name.strip() for name in names):
                problems.append(f"{label} names must not be empty")

        for label, items in (
            ("role", self.roles),
            ("capability", self.capabilities),
            ("effect", self.effects),
            ("permission", self.permissions),
            ("dependency", self.dependencies),
            ("tag", self.tags),
        ):
            if any(not isinstance(item, str) or not item.strip() for item in items):
                problems.append(f"{label} values must be non-empty strings")
            duplicates = sorted({
                item for item in items
                if isinstance(item, str) and items.count(item) > 1
            })
            if duplicates:
                problems.append(f"duplicate {label}(s): {', '.join(duplicates)}")

        for label, ports in (("input", self.inputs), ("output", self.outputs)):
            if any(not port.data_type.strip() for port in ports):
                problems.append(f"{label} data types must not be empty")
            if any(not isinstance(port.required, bool) for port in ports):
                problems.append(f"{label} required flags must be boolean")
        for parameter in self.parameters:
            if not parameter.data_type.strip():
                problems.append("parameter data types must not be empty")
            if not isinstance(parameter.required, bool):
                problems.append("parameter required flags must be boolean")
            if (parameter.choices and parameter.default is not None
                    and parameter.default not in parameter.choices):
                problems.append(
                    f"parameter {parameter.name}: default must be one of its choices")
        for field_name in ("resources", "runtime", "context", "intelligence", "metrics"):
            if not isinstance(getattr(self, field_name), dict):
                problems.append(f"{field_name} must be an object")
        return problems

    def assert_valid(self) -> NodeManifest:
        problems = self.validate()
        if problems:
            raise ValueError("invalid node manifest:\n  - " + "\n  - ".join(problems))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "roles": list(self.roles),
            "capabilities": list(self.capabilities),
            "inputs": [port.to_dict() for port in self.inputs],
            "outputs": [port.to_dict() for port in self.outputs],
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "effects": list(self.effects),
            "permissions": list(self.permissions),
            "dependencies": list(self.dependencies),
            "resources": dict(self.resources),
            "runtime": dict(self.runtime),
            "context": dict(self.context),
            "intelligence": dict(self.intelligence),
            "metrics": dict(self.metrics),
            "source": self.source,
            "docs": self.docs,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeManifest:
        manifest = cls(
            schema_version=str(data.get("schema_version", MANIFEST_SCHEMA_VERSION)),
            id=str(data["id"]),
            kind=str(data["kind"]),
            name=str(data["name"]),
            version=str(data.get("version", "0.1.0")),
            description=str(data.get("description", "")),
            roles=tuple(data.get("roles") or ()),
            capabilities=tuple(data.get("capabilities") or ()),
            inputs=tuple(PortSpec.from_dict(port) for port in data.get("inputs") or ()),
            outputs=tuple(PortSpec.from_dict(port) for port in data.get("outputs") or ()),
            parameters=tuple(
                ParameterSpec.from_dict(parameter)
                for parameter in data.get("parameters") or ()),
            effects=tuple(data.get("effects") or ()),
            permissions=tuple(data.get("permissions") or ()),
            dependencies=tuple(data.get("dependencies") or ()),
            resources=dict(data.get("resources") or {}),
            runtime=dict(data.get("runtime") or {}),
            context=dict(data.get("context") or {}),
            intelligence=dict(data.get("intelligence") or {}),
            metrics=dict(data.get("metrics") or {}),
            source=str(data.get("source", "")),
            docs=str(data.get("docs", "")),
            tags=tuple(data.get("tags") or ()),
        )
        return manifest.assert_valid()

    @classmethod
    def from_node(cls, obj: Any, **overrides: Any) -> NodeManifest:
        """Infer a rich manifest from an existing Node class or instance."""
        contract = contract_of(obj)
        node_type = obj if inspect.isclass(obj) else type(obj)
        raw_doc = inspect.getdoc(node_type) or ""
        description = raw_doc.split("\n\n", 1)[0].replace("\n", " ")

        roles: list[str] = []
        if contract.writes and not contract.reads:
            roles.append("source")
        if contract.reads or contract.writes:
            roles.append("transform")
        if contract.mutates:
            roles.append("action")
        if contract.verifies:
            roles.append("verifier")
        if contract.uses_llm:
            roles.append("model")
        if not roles:
            roles.append("control")

        permissions = []
        if contract.needs_browser:
            permissions.append("browser")
        if contract.uses_llm:
            permissions.append("llm")

        effects = ["remote_state"] if contract.mutates else []
        source = f"{node_type.__module__}.{node_type.__qualname__}"
        inferred = cls(
            id=f"browsergraph.{contract.kind}",
            kind=contract.kind,
            name=node_type.__name__,
            description=description,
            roles=tuple(dict.fromkeys(roles)),
            capabilities=(contract.kind,),
            inputs=tuple(PortSpec(name=key, data_type="context:any")
                         for key in contract.reads),
            outputs=tuple(PortSpec(name=key, data_type="context:any")
                          for key in contract.writes),
            effects=tuple(effects),
            permissions=tuple(permissions),
            runtime={
                "needs_browser": contract.needs_browser,
                "mutates": contract.mutates,
                "verifies": contract.verifies,
                "interacts": contract.interacts,
                "uses_llm": contract.uses_llm,
                "selector": contract.selector,
            },
            context={
                "reads": list(contract.reads),
                "writes": list(contract.writes),
                "default_scopes": ["attempt"],
            },
            intelligence={
                "mode": "llm_assisted" if contract.uses_llm else "deterministic",
                "may_propose_route_change": False,
            },
            source=source,
        )
        if overrides:
            inferred = replace(inferred, **overrides)
        return inferred.assert_valid()


@dataclass(frozen=True)
class NodeDefinition:
    """Thin wrapper coupling a portable manifest to an optional node factory."""

    manifest: NodeManifest
    factory: Callable[..., Any] | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        self.manifest.assert_valid()

    @classmethod
    def from_node(cls, node_type: type, **manifest_overrides: Any) -> NodeDefinition:
        manifest = manifest_of(node_type)
        if manifest_overrides:
            manifest = replace(manifest, **manifest_overrides).assert_valid()
        return cls(manifest, node_type)

    def build(self, **kwargs: Any) -> Any:
        if self.factory is None:
            raise TypeError(f"{self.manifest.id} is metadata-only and has no factory")
        return self.factory(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return self.manifest.to_dict()


def described_node(**manifest_overrides: Any):
    """Attach a full manifest to a Node class without changing its execution."""
    def decorate(node_type: type) -> type:
        manifest = NodeManifest.from_node(node_type, **manifest_overrides)
        node_type.__node_manifest__ = manifest
        return node_type
    return decorate


def manifest_of(obj: Any) -> NodeManifest:
    """Return an attached manifest or infer one from the existing contract."""
    node_type = obj if inspect.isclass(obj) else type(obj)
    attached = node_type.__dict__.get("__node_manifest__")
    if attached is not None:
        if not isinstance(attached, NodeManifest):
            raise TypeError("__node_manifest__ must be a NodeManifest")
        return attached.assert_valid()
    return NodeManifest.from_node(obj)


def manifest_schema() -> dict[str, Any]:
    """Load the bundled JSON Schema used by non-Python registries and viewers."""
    resource = files("browsergraph").joinpath("schemas/node-manifest.schema.json")
    return json.loads(resource.read_text(encoding="utf-8"))
