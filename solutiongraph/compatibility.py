"""Optional node compatibility profiles beyond the minimal executable ABI.

Profiles describe operational semantics that are important for safe composition
but should not be confused with learned quality.  Missing optional metadata is
reported as unknown; it is never silently treated as compatible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE, PORT_RE, NodeSpec, Registry, sha256_digest

COMPATIBILITY_MODEL_VERSION = "0.1"
STATE_MODES = ("stateless", "checkpointable", "external", "unknown")
CACHE_MODES = ("never", "content", "run", "unknown")
ORDERING_MODES = ("unordered", "stable", "sorted", "event-time", "unknown")
TIME_MODES = ("none", "processing-time", "event-time", "dual", "unknown")


@dataclass(frozen=True)
class PortSemantics:
    direction: str
    port_name: str
    nullable: bool | None = None
    ordering: str = "unknown"
    time_domain: str = "unknown"
    event_time_field: str = ""
    data_classifications: tuple[str, ...] = ()
    schema_compatibility: str = "exact"
    description: str = ""

    def validate(self, node: NodeSpec | None, path: str) -> list[str]:
        problems: list[str] = []
        if self.direction not in ("input", "output"):
            problems.append(f"{path}.direction must be input or output")
        if not PORT_RE.fullmatch(self.port_name):
            problems.append(f"{path}.port_name must be snake_case")
        if self.nullable is not None and not isinstance(self.nullable, bool):
            problems.append(f"{path}.nullable must be boolean or null")
        if self.ordering not in ORDERING_MODES:
            problems.append(f"{path}.ordering is not recognized")
        if self.time_domain not in TIME_MODES:
            problems.append(f"{path}.time_domain is not recognized")
        if self.event_time_field and self.time_domain not in ("event-time", "dual"):
            problems.append(
                f"{path}.event_time_field requires event-time or dual time semantics"
            )
        if not self.schema_compatibility.strip():
            problems.append(f"{path}.schema_compatibility must not be empty")
        if len(self.data_classifications) != len(set(self.data_classifications)):
            problems.append(f"{path}.data_classifications must be unique")
        if any(not ID_RE.fullmatch(item) for item in self.data_classifications):
            problems.append(f"{path}.data_classifications must contain identifiers")
        if node is not None and self.direction in ("input", "output"):
            if node.port(self.direction, self.port_name) is None:
                problems.append(f"{path} references an unknown node port")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "port_name": self.port_name,
            "nullable": self.nullable,
            "ordering": self.ordering,
            "time_domain": self.time_domain,
            "event_time_field": self.event_time_field,
            "data_classifications": list(self.data_classifications),
            "schema_compatibility": self.schema_compatibility,
            "description": self.description,
        }


@dataclass(frozen=True)
class NodeCompatibilityProfile:
    node_id: str
    node_version: str
    implementation_digest: str
    ports: tuple[PortSemantics, ...] = ()
    state_mode: str = "unknown"
    state_schema_digest: str = ""
    state_version: str = ""
    cache_mode: str = "unknown"
    secret_scopes: tuple[str, ...] = ()
    hardware_requirements: tuple[str, ...] = ()
    data_residencies: tuple[str, ...] = ()
    compensation_node_id: str = ""
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, node: NodeSpec | None, path: str = "profile") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.node_id) or not self.node_version.strip():
            problems.append(f"{path} node identity is invalid")
        if not DIGEST_RE.fullmatch(self.implementation_digest):
            problems.append(f"{path}.implementation_digest must be a sha256 digest")
        if node is None:
            problems.append(f"{path} references an unknown node")
        elif (
            self.node_id != node.id
            or self.node_version != node.version
            or self.implementation_digest != node.implementation_digest
        ):
            problems.append(f"{path} identity does not match the registry node")
        if self.state_mode not in STATE_MODES:
            problems.append(f"{path}.state_mode is not recognized")
        if self.cache_mode not in CACHE_MODES:
            problems.append(f"{path}.cache_mode is not recognized")
        if self.state_schema_digest and not DIGEST_RE.fullmatch(self.state_schema_digest):
            problems.append(f"{path}.state_schema_digest must be empty or sha256")
        if self.state_mode == "checkpointable" and (
            not self.state_schema_digest or not self.state_version
        ):
            problems.append(
                f"{path} checkpointable state requires schema digest and version"
            )
        if self.compensation_node_id and not ID_RE.fullmatch(self.compensation_node_id):
            problems.append(f"{path}.compensation_node_id must be empty or an identifier")
        port_keys = [(item.direction, item.port_name) for item in self.ports]
        if len(port_keys) != len(set(port_keys)):
            problems.append(f"{path}.ports must contain unique direction/name pairs")
        for index, item in enumerate(self.ports):
            problems.extend(item.validate(node, f"{path}.ports[{index}]"))
        for label, values in (
            ("secret_scopes", self.secret_scopes),
            ("hardware_requirements", self.hardware_requirements),
            ("data_residencies", self.data_residencies),
        ):
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not ID_RE.fullmatch(item) for item in values):
                problems.append(f"{path}.{label} must contain identifiers")
        extension_names = [name for name, _ in self.extensions]
        if len(extension_names) != len(set(extension_names)):
            problems.append(f"{path}.extensions must have unique names")
        if any("." not in name or not ID_RE.fullmatch(name) for name in extension_names):
            problems.append(f"{path}.extensions must use namespaced keys")
        return problems

    def port(self, direction: str, name: str) -> PortSemantics | None:
        return next(
            (
                item
                for item in self.ports
                if item.direction == direction and item.port_name == name
            ),
            None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "compatibility_model_version": COMPATIBILITY_MODEL_VERSION,
            "node_id": self.node_id,
            "node_version": self.node_version,
            "implementation_digest": self.implementation_digest,
            "ports": [item.to_dict() for item in self.ports],
            "state_mode": self.state_mode,
            "state_schema_digest": self.state_schema_digest,
            "state_version": self.state_version,
            "cache_mode": self.cache_mode,
            "secret_scopes": list(self.secret_scopes),
            "hardware_requirements": list(self.hardware_requirements),
            "data_residencies": list(self.data_residencies),
            "compensation_node_id": self.compensation_node_id,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class CompatibilityCatalog:
    id: str
    version: str
    profiles: tuple[NodeCompatibilityProfile, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, registry: Registry) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.version.strip():
            problems.append("compatibility catalog identity is invalid")
        keys = [(item.node_id, item.node_version) for item in self.profiles]
        if len(keys) != len(set(keys)):
            problems.append("compatibility profiles must contain unique node versions")
        nodes = registry.node_map()
        for index, profile in enumerate(self.profiles):
            problems.extend(
                profile.validate(
                    nodes.get((profile.node_id, profile.node_version)),
                    f"profiles[{index}]",
                )
            )
            if profile.compensation_node_id and not any(
                node.id == profile.compensation_node_id for node in registry.nodes
            ):
                problems.append(
                    f"profiles[{index}].compensation_node_id references an unknown node"
                )
        return problems

    def get(self, node_id: str, node_version: str) -> NodeCompatibilityProfile | None:
        return next(
            (
                profile
                for profile in self.profiles
                if profile.node_id == node_id and profile.node_version == node_version
            ),
            None,
        )

    def edge_problems(
        self,
        source: NodeSpec,
        source_port: str,
        target: NodeSpec,
        target_port: str,
        *,
        require_complete: bool = False,
    ) -> tuple[str, ...]:
        """Compare ordering/time/privacy semantics without altering ABI admission."""
        source_profile = self.get(source.id, source.version)
        target_profile = self.get(target.id, target.version)
        source_semantics = (
            source_profile.port("output", source_port) if source_profile else None
        )
        target_semantics = (
            target_profile.port("input", target_port) if target_profile else None
        )
        if source_semantics is None or target_semantics is None:
            return (
                "compatibility metadata is incomplete",
            ) if require_complete else ()
        problems: list[str] = []
        if (
            target_semantics.ordering not in ("unknown", "unordered")
            and source_semantics.ordering != target_semantics.ordering
        ):
            problems.append(
                f"ordering {source_semantics.ordering} does not satisfy "
                f"{target_semantics.ordering}"
            )
        if (
            target_semantics.time_domain not in ("unknown", "none")
            and source_semantics.time_domain != target_semantics.time_domain
        ):
            problems.append(
                f"time domain {source_semantics.time_domain} does not satisfy "
                f"{target_semantics.time_domain}"
            )
        missing_classifications = sorted(
            set(source_semantics.data_classifications)
            - set(target_semantics.data_classifications)
        )
        if missing_classifications:
            problems.append(
                "target does not declare handling for: "
                + ", ".join(missing_classifications)
            )
        if target_semantics.nullable is False and source_semantics.nullable is not False:
            problems.append("possibly-null source does not satisfy non-null target")
        return tuple(problems)

    def node_problems(
        self,
        node: NodeSpec,
        *,
        available_secret_scopes: tuple[str, ...] = (),
        available_hardware: tuple[str, ...] = (),
        data_residency: str = "",
        require_checkpointable: bool = False,
        require_compensation: bool = False,
        require_complete: bool = False,
    ) -> tuple[str, ...]:
        """Check operational requirements for one already ABI-compatible node."""
        profile = self.get(node.id, node.version)
        if profile is None:
            return ("compatibility metadata is incomplete",) if require_complete else ()
        problems: list[str] = []
        missing_secrets = sorted(
            set(profile.secret_scopes) - set(available_secret_scopes)
        )
        if missing_secrets:
            problems.append("missing secret scopes: " + ", ".join(missing_secrets))
        missing_hardware = sorted(
            set(profile.hardware_requirements) - set(available_hardware)
        )
        if missing_hardware:
            problems.append("missing hardware: " + ", ".join(missing_hardware))
        if data_residency:
            if profile.data_residencies and data_residency not in profile.data_residencies:
                problems.append(
                    f"data residency {data_residency} is not declared by the node"
                )
            elif require_complete and not profile.data_residencies:
                problems.append("data residency compatibility is unknown")
        if require_checkpointable and profile.state_mode != "checkpointable":
            problems.append("node is not declared checkpointable")
        if require_compensation and not profile.compensation_node_id:
            problems.append("node has no declared compensation node")
        return tuple(problems)

    def to_dict(self) -> dict[str, Any]:
        return {
            "compatibility_model_version": COMPATIBILITY_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "profiles": [profile.to_dict() for profile in self.profiles],
        }


__all__ = [
    "CACHE_MODES",
    "COMPATIBILITY_MODEL_VERSION",
    "CompatibilityCatalog",
    "NodeCompatibilityProfile",
    "ORDERING_MODES",
    "PortSemantics",
    "STATE_MODES",
    "TIME_MODES",
]
