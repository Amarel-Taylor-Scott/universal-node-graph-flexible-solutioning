"""Extensible node discovery, registry negotiation, snapshots, and node packs.

Executable truth remains in :class:`NodeSpec`. Human descriptions, search
documents, embeddings, and index-specific features are independently versioned
sidecars keyed by the node-spec digest. A registry handshake negotiates only
the discovery mechanisms both sides actually support.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from solutiongraph.errors import Diagnostic, ValidationError
from solutiongraph.model import (
    DIGEST_RE,
    ID_RE,
    PORT_RE,
    NodeSpec,
    Registry,
    canonical_json,
    sha256_digest,
)

DISCOVERY_PROTOCOL_VERSION = "0.1"


def _duplicates(values: list[str]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


def _validate_unique_ids(values: tuple[str, ...], path: str) -> list[str]:
    problems: list[str] = []
    if len(values) != len(set(values)):
        problems.append(f"{path} must be unique")
    if any(not ID_RE.fullmatch(value) for value in values):
        problems.append(f"{path} must contain lowercase namespaced identifiers")
    return problems


def _validate_extensions(extensions: tuple[tuple[str, Any], ...], path: str) -> list[str]:
    problems: list[str] = []
    keys = [key for key, _ in extensions]
    if len(keys) != len(set(keys)):
        problems.append(f"{path} keys must be unique")
    for key, value in extensions:
        if not ID_RE.fullmatch(key) or "." not in key:
            problems.append(f"{path}.{key} must use a namespaced key")
        try:
            canonical_json(value)
        except (TypeError, ValueError):
            problems.append(f"{path}.{key} must be JSON serialisable")
    return problems


@dataclass(frozen=True)
class SearchDocument:
    """One optional textual view of a node or one of its interface elements."""

    id: str
    text: str
    language: str = "und"
    targets: tuple[str, ...] = ("node",)
    source_digest: str = ""
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "document") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.text.strip():
            problems.append(f"{path}.text must not be empty")
        if not self.language.strip():
            problems.append(f"{path}.language must not be empty")
        if not self.targets or any(not target.strip() for target in self.targets):
            problems.append(f"{path}.targets must contain non-empty targets")
        if len(self.targets) != len(set(self.targets)):
            problems.append(f"{path}.targets must be unique")
        if self.source_digest and not DIGEST_RE.fullmatch(self.source_digest):
            problems.append(f"{path}.source_digest must be sha256:<64 lowercase hex chars>")
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "language": self.language,
            "targets": list(self.targets),
            "source_digest": self.source_digest,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class PortMeaning:
    """Optional human/search meaning attached to a strict ABI port."""

    direction: str
    port_name: str
    description: str = ""
    concepts: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()

    def validate(self, path: str = "port_meaning") -> list[str]:
        problems: list[str] = []
        if self.direction not in ("input", "output"):
            problems.append(f"{path}.direction must be input or output")
        if not PORT_RE.fullmatch(self.port_name):
            problems.append(f"{path}.port_name must be snake_case")
        problems.extend(_validate_unique_ids(self.concepts, f"{path}.concepts"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "port_name": self.port_name,
            "description": self.description,
            "concepts": list(self.concepts),
            "examples": list(self.examples),
        }


@dataclass(frozen=True)
class NodeDescriptor:
    """Sparse, extensible discovery metadata that never changes node validity."""

    node_id: str
    node_version: str
    node_spec_digest: str
    title: str = ""
    summary: str = ""
    purposes: tuple[str, ...] = ()
    solutions: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    ports: tuple[PortMeaning, ...] = ()
    documents: tuple[SearchDocument, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, node: NodeSpec | None = None, path: str = "descriptor") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.node_id):
            problems.append(f"{path}.node_id must be a namespaced identifier")
        if not self.node_version.strip():
            problems.append(f"{path}.node_version must not be empty")
        if not DIGEST_RE.fullmatch(self.node_spec_digest):
            problems.append(f"{path}.node_spec_digest must be sha256:<64 lowercase hex chars>")
        for label, values in (
            ("domains", self.domains),
            ("tags", self.tags),
        ):
            problems.extend(_validate_unique_ids(values, f"{path}.{label}"))
        for label, values in (
            ("purposes", self.purposes),
            ("solutions", self.solutions),
            ("actions", self.actions),
            ("aliases", self.aliases),
        ):
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not value.strip() for value in values):
                problems.append(f"{path}.{label} must not contain empty values")
        port_keys = [(port.direction, port.port_name) for port in self.ports]
        if len(port_keys) != len(set(port_keys)):
            problems.append(f"{path}.ports must identify each ABI port at most once")
        for index, port in enumerate(self.ports):
            problems.extend(port.validate(f"{path}.ports[{index}]"))
        document_ids = [document.id for document in self.documents]
        if len(document_ids) != len(set(document_ids)):
            problems.append(f"{path}.documents must have unique ids")
        for index, document in enumerate(self.documents):
            problems.extend(document.validate(f"{path}.documents[{index}]"))
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        if node is not None:
            if (self.node_id, self.node_version) != (node.id, node.version):
                problems.append(f"{path} identifies a different node")
            if self.node_spec_digest != node.digest:
                problems.append(f"{path}.node_spec_digest does not match the node contract")
            for port in self.ports:
                if node.port(port.direction, port.port_name) is None:
                    problems.append(
                        f"{path}.ports references unknown {port.direction} {port.port_name}"
                    )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery_version": DISCOVERY_PROTOCOL_VERSION,
            "node_id": self.node_id,
            "node_version": self.node_version,
            "node_spec_digest": self.node_spec_digest,
            "title": self.title,
            "summary": self.summary,
            "purposes": list(self.purposes),
            "solutions": list(self.solutions),
            "actions": list(self.actions),
            "domains": list(self.domains),
            "tags": list(self.tags),
            "aliases": list(self.aliases),
            "ports": [port.to_dict() for port in self.ports],
            "documents": [document.to_dict() for document in self.documents],
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class EmbeddingSpace:
    """Exact identity of one optional vector representation space."""

    id: str
    model_id: str
    model_revision: str
    vector_kind: str
    dimensions: int | None
    distance: str
    normalization: str = "none"
    scalar_type: str = "float32"
    model_digest: str = ""
    targets: tuple[str, ...] = ("node.summary",)
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "embedding_space") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not ID_RE.fullmatch(self.model_id):
            problems.append(f"{path}.model_id must be a namespaced identifier")
        if not self.model_revision.strip():
            problems.append(f"{path}.model_revision must not be empty")
        if self.vector_kind not in ("dense", "sparse", "multivector"):
            problems.append(f"{path}.vector_kind must be dense, sparse, or multivector")
        if self.vector_kind in ("dense", "multivector"):
            if self.dimensions is None or self.dimensions <= 0:
                problems.append(f"{path}.dimensions must be positive for dense vectors")
        elif self.dimensions is not None and self.dimensions <= 0:
            problems.append(f"{path}.dimensions must be positive or null")
        if not ID_RE.fullmatch(self.distance):
            problems.append(f"{path}.distance must be a namespaced identifier")
        if not ID_RE.fullmatch(self.normalization):
            problems.append(f"{path}.normalization must be a namespaced identifier")
        if not ID_RE.fullmatch(self.scalar_type):
            problems.append(f"{path}.scalar_type must be a namespaced identifier")
        if self.model_digest and not DIGEST_RE.fullmatch(self.model_digest):
            problems.append(f"{path}.model_digest must be sha256:<64 lowercase hex chars>")
        if not self.targets or len(self.targets) != len(set(self.targets)):
            problems.append(f"{path}.targets must be non-empty and unique")
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        return problems

    def is_compatible_with(self, other: EmbeddingSpace) -> bool:
        """Require exact vector semantics; dimensions alone are not compatibility."""
        return (
            self.id == other.id
            and self.model_id == other.model_id
            and self.model_revision == other.model_revision
            and self.vector_kind == other.vector_kind
            and self.dimensions == other.dimensions
            and self.distance == other.distance
            and self.normalization == other.normalization
            and self.scalar_type == other.scalar_type
            and self.model_digest == other.model_digest
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "model_digest": self.model_digest,
            "vector_kind": self.vector_kind,
            "dimensions": self.dimensions,
            "distance": self.distance,
            "normalization": self.normalization,
            "scalar_type": self.scalar_type,
            "targets": list(self.targets),
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class EmbeddingRecord:
    """An inline or content-addressed vector sidecar for one descriptor target."""

    id: str
    node_spec_digest: str
    descriptor_digest: str
    space_id: str
    target: str
    values: tuple[float, ...] = ()
    sparse_values: tuple[tuple[int, float], ...] = ()
    multivector: tuple[tuple[float, ...], ...] = ()
    artifact_digest: str = ""
    artifact_uri: str = ""
    source_text_digest: str = ""
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, space: EmbeddingSpace | None = None, path: str = "embedding") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        for label, digest in (
            ("node_spec_digest", self.node_spec_digest),
            ("descriptor_digest", self.descriptor_digest),
            ("artifact_digest", self.artifact_digest),
            ("source_text_digest", self.source_text_digest),
        ):
            if digest and not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be sha256:<64 lowercase hex chars>")
        if not self.node_spec_digest or not self.descriptor_digest:
            problems.append(f"{path} requires node_spec_digest and descriptor_digest")
        if not ID_RE.fullmatch(self.space_id):
            problems.append(f"{path}.space_id must be a namespaced identifier")
        if not self.target.strip():
            problems.append(f"{path}.target must not be empty")
        forms = sum(
            bool(value)
            for value in (
                self.values,
                self.sparse_values,
                self.multivector,
                self.artifact_digest,
            )
        )
        if forms != 1:
            problems.append(f"{path} must contain exactly one inline or external vector form")
        if self.artifact_digest and not self.artifact_uri:
            problems.append(f"{path}.artifact_uri is required with artifact_digest")
        if self.artifact_uri and not self.artifact_digest:
            problems.append(f"{path}.artifact_digest is required with artifact_uri")
        numbers = [*self.values, *(value for _, value in self.sparse_values)]
        numbers.extend(value for vector in self.multivector for value in vector)
        if any(not isfinite(value) for value in numbers):
            problems.append(f"{path} vector values must be finite")
        indices = [index for index, _ in self.sparse_values]
        if any(index < 0 for index in indices) or len(indices) != len(set(indices)):
            problems.append(f"{path}.sparse_values indices must be non-negative and unique")
        if space is not None:
            if self.space_id != space.id:
                problems.append(f"{path}.space_id does not match the embedding space")
            expected = space.dimensions
            if self.values and (space.vector_kind != "dense" or len(self.values) != expected):
                problems.append(f"{path}.values do not match dense space dimensions")
            if self.sparse_values and space.vector_kind != "sparse":
                problems.append(f"{path}.sparse_values require a sparse space")
            if (
                self.sparse_values
                and expected is not None
                and any(index >= expected for index in indices)
            ):
                problems.append(f"{path}.sparse_values index exceeds space dimensions")
            if self.multivector:
                if space.vector_kind != "multivector":
                    problems.append(f"{path}.multivector requires a multivector space")
                elif any(len(vector) != expected for vector in self.multivector):
                    problems.append(f"{path}.multivector rows do not match space dimensions")
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery_version": DISCOVERY_PROTOCOL_VERSION,
            "id": self.id,
            "node_spec_digest": self.node_spec_digest,
            "descriptor_digest": self.descriptor_digest,
            "space_id": self.space_id,
            "target": self.target,
            "values": list(self.values),
            "sparse_values": [
                {"index": index, "value": value} for index, value in self.sparse_values
            ],
            "multivector": [list(vector) for vector in self.multivector],
            "artifact_digest": self.artifact_digest,
            "artifact_uri": self.artifact_uri,
            "source_text_digest": self.source_text_digest,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class QueryMode:
    """One registry query mechanism and its inspectability guarantees."""

    id: str
    fields: tuple[str, ...] = ()
    supports_filters: bool = False
    supports_scores: bool = False
    supports_explanations: bool = False
    supports_cursor: bool = False
    requires_embedding_space: bool = False
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "query_mode") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if len(self.fields) != len(set(self.fields)) or any(
            not field.strip() for field in self.fields
        ):
            problems.append(f"{path}.fields must be non-empty and unique")
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fields": list(self.fields),
            "supports_filters": self.supports_filters,
            "supports_scores": self.supports_scores,
            "supports_explanations": self.supports_explanations,
            "supports_cursor": self.supports_cursor,
            "requires_embedding_space": self.requires_embedding_space,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class SchemaSupport:
    name: str
    versions: tuple[str, ...]

    def validate(self, path: str = "schema") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.name):
            problems.append(f"{path}.name must be a namespaced identifier")
        if not self.versions or len(self.versions) != len(set(self.versions)):
            problems.append(f"{path}.versions must be non-empty and unique")
        if any(not version.strip() for version in self.versions):
            problems.append(f"{path}.versions must not contain empty values")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "versions": list(self.versions)}


@dataclass(frozen=True)
class RegistryCapabilities:
    """Server half of the harness–node-registry discovery handshake."""

    registry_id: str
    registry_version: str
    registry_digest: str
    protocol_versions: tuple[str, ...]
    schemas: tuple[SchemaSupport, ...]
    query_modes: tuple[QueryMode, ...]
    embedding_spaces: tuple[EmbeddingSpace, ...] = ()
    descriptor_fields: tuple[str, ...] = ()
    supports_enumeration: bool = True
    supports_snapshots: bool = True
    supports_continuation: bool = False
    supports_explanations: bool = True
    max_page_size: int | None = None
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "registry_capabilities") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.registry_id):
            problems.append(f"{path}.registry_id must be a namespaced identifier")
        if not self.registry_version.strip():
            problems.append(f"{path}.registry_version must not be empty")
        if not DIGEST_RE.fullmatch(self.registry_digest):
            problems.append(f"{path}.registry_digest must be sha256:<64 lowercase hex chars>")
        if not self.protocol_versions or len(self.protocol_versions) != len(
            set(self.protocol_versions)
        ):
            problems.append(f"{path}.protocol_versions must be non-empty and unique")
        schema_names = [schema.name for schema in self.schemas]
        for duplicate in _duplicates(schema_names):
            problems.append(f"{path}.schemas contains duplicate {duplicate}")
        for index, schema in enumerate(self.schemas):
            problems.extend(schema.validate(f"{path}.schemas[{index}]"))
        mode_ids = [mode.id for mode in self.query_modes]
        if not mode_ids:
            problems.append(f"{path}.query_modes must not be empty")
        for duplicate in _duplicates(mode_ids):
            problems.append(f"{path}.query_modes contains duplicate {duplicate}")
        for index, mode in enumerate(self.query_modes):
            problems.extend(mode.validate(f"{path}.query_modes[{index}]"))
        space_ids = [space.id for space in self.embedding_spaces]
        for duplicate in _duplicates(space_ids):
            problems.append(f"{path}.embedding_spaces contains duplicate {duplicate}")
        for index, space in enumerate(self.embedding_spaces):
            problems.extend(space.validate(f"{path}.embedding_spaces[{index}]"))
        if len(self.descriptor_fields) != len(set(self.descriptor_fields)):
            problems.append(f"{path}.descriptor_fields must be unique")
        if self.max_page_size is not None and self.max_page_size <= 0:
            problems.append(f"{path}.max_page_size must be positive or null")
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery_version": DISCOVERY_PROTOCOL_VERSION,
            "registry_id": self.registry_id,
            "registry_version": self.registry_version,
            "registry_digest": self.registry_digest,
            "protocol_versions": list(self.protocol_versions),
            "schemas": [schema.to_dict() for schema in self.schemas],
            "query_modes": [mode.to_dict() for mode in self.query_modes],
            "embedding_spaces": [space.to_dict() for space in self.embedding_spaces],
            "descriptor_fields": list(self.descriptor_fields),
            "supports_enumeration": self.supports_enumeration,
            "supports_snapshots": self.supports_snapshots,
            "supports_continuation": self.supports_continuation,
            "supports_explanations": self.supports_explanations,
            "max_page_size": self.max_page_size,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class HarnessCapabilities:
    """Client preferences; order expresses fallback preference, never validity."""

    harness_id: str
    harness_version: str
    protocol_versions: tuple[str, ...]
    schemas: tuple[SchemaSupport, ...]
    query_modes: tuple[str, ...]
    embedding_spaces: tuple[EmbeddingSpace, ...] = ()
    descriptor_fields: tuple[str, ...] = ()
    require_explanations: bool = False
    require_snapshots: bool = True
    require_enumeration: bool = False
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "harness_capabilities") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.harness_id):
            problems.append(f"{path}.harness_id must be a namespaced identifier")
        if not self.harness_version.strip():
            problems.append(f"{path}.harness_version must not be empty")
        if not self.protocol_versions or len(self.protocol_versions) != len(
            set(self.protocol_versions)
        ):
            problems.append(f"{path}.protocol_versions must be non-empty and unique")
        if not self.query_modes:
            problems.append(f"{path}.query_modes must not be empty")
        problems.extend(_validate_unique_ids(self.query_modes, f"{path}.query_modes"))
        schema_names = [schema.name for schema in self.schemas]
        for duplicate in _duplicates(schema_names):
            problems.append(f"{path}.schemas contains duplicate {duplicate}")
        for index, schema in enumerate(self.schemas):
            problems.extend(schema.validate(f"{path}.schemas[{index}]"))
        space_ids = [space.id for space in self.embedding_spaces]
        for duplicate in _duplicates(space_ids):
            problems.append(f"{path}.embedding_spaces contains duplicate {duplicate}")
        for index, space in enumerate(self.embedding_spaces):
            problems.extend(space.validate(f"{path}.embedding_spaces[{index}]"))
        if len(self.descriptor_fields) != len(set(self.descriptor_fields)):
            problems.append(f"{path}.descriptor_fields must be unique")
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery_version": DISCOVERY_PROTOCOL_VERSION,
            "harness_id": self.harness_id,
            "harness_version": self.harness_version,
            "protocol_versions": list(self.protocol_versions),
            "schemas": [schema.to_dict() for schema in self.schemas],
            "query_modes": list(self.query_modes),
            "embedding_spaces": [space.to_dict() for space in self.embedding_spaces],
            "descriptor_fields": list(self.descriptor_fields),
            "require_explanations": self.require_explanations,
            "require_snapshots": self.require_snapshots,
            "require_enumeration": self.require_enumeration,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class RegistrySession:
    """Immutable result of capability negotiation for one registry snapshot flow."""

    protocol_version: str
    registry_id: str
    registry_version: str
    registry_digest: str
    harness_id: str
    harness_version: str
    query_modes: tuple[str, ...]
    embedding_spaces: tuple[EmbeddingSpace, ...]
    descriptor_fields: tuple[str, ...]
    schema_versions: tuple[tuple[str, str], ...]
    supports_enumeration: bool
    supports_snapshots: bool
    supports_continuation: bool
    supports_explanations: bool
    max_page_size: int | None
    warnings: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery_version": DISCOVERY_PROTOCOL_VERSION,
            "protocol_version": self.protocol_version,
            "registry_id": self.registry_id,
            "registry_version": self.registry_version,
            "registry_digest": self.registry_digest,
            "harness_id": self.harness_id,
            "harness_version": self.harness_version,
            "query_modes": list(self.query_modes),
            "embedding_spaces": [space.to_dict() for space in self.embedding_spaces],
            "descriptor_fields": list(self.descriptor_fields),
            "schema_versions": dict(self.schema_versions),
            "supports_enumeration": self.supports_enumeration,
            "supports_snapshots": self.supports_snapshots,
            "supports_continuation": self.supports_continuation,
            "supports_explanations": self.supports_explanations,
            "max_page_size": self.max_page_size,
            "warnings": list(self.warnings),
        }


def negotiate_registry(
    harness: HarnessCapabilities, registry: RegistryCapabilities
) -> RegistrySession:
    """Negotiate an exact, inspectable discovery session with graceful fallback."""
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(
        Diagnostic("UNG-HANDSHAKE-001", problem, "harness") for problem in harness.validate()
    )
    diagnostics.extend(
        Diagnostic("UNG-HANDSHAKE-002", problem, "registry") for problem in registry.validate()
    )
    if diagnostics:
        raise ValidationError("invalid registry handshake", diagnostics)

    protocol = next(
        (version for version in harness.protocol_versions if version in registry.protocol_versions),
        "",
    )
    if not protocol:
        diagnostics.append(
            Diagnostic(
                "UNG-HANDSHAKE-003",
                "harness and registry have no common protocol version",
                "protocol_versions",
            )
        )

    server_spaces = {space.id: space for space in registry.embedding_spaces}
    compatible_spaces = tuple(
        space
        for space in harness.embedding_spaces
        if space.id in server_spaces and space.is_compatible_with(server_spaces[space.id])
    )
    server_modes = {mode.id: mode for mode in registry.query_modes}
    warnings: list[str] = []
    modes: list[str] = []
    for mode_id in harness.query_modes:
        mode = server_modes.get(mode_id)
        if mode is None:
            warnings.append(f"unavailable query mode: {mode_id}")
            continue
        if mode.requires_embedding_space and not compatible_spaces:
            warnings.append(f"disabled {mode_id}: no exactly compatible embedding space")
            continue
        modes.append(mode_id)
    if not modes:
        diagnostics.append(
            Diagnostic(
                "UNG-HANDSHAKE-004",
                "harness and registry have no usable query mode",
                "query_modes",
                "Advertise enumeration, exact, lexical, or an exactly matching vector space.",
            )
        )
    if harness.require_explanations and not registry.supports_explanations:
        diagnostics.append(
            Diagnostic(
                "UNG-HANDSHAKE-005",
                "harness requires search explanations but the registry cannot provide them",
                "supports_explanations",
            )
        )
    if harness.require_snapshots and not registry.supports_snapshots:
        diagnostics.append(
            Diagnostic(
                "UNG-HANDSHAKE-007",
                "harness requires stable registry snapshots but the registry cannot provide them",
                "supports_snapshots",
            )
        )
    if harness.require_enumeration and not registry.supports_enumeration:
        diagnostics.append(
            Diagnostic(
                "UNG-HANDSHAKE-008",
                "harness requires deterministic enumeration but the registry cannot provide it",
                "supports_enumeration",
            )
        )

    server_schemas = {schema.name: schema.versions for schema in registry.schemas}
    schema_versions: list[tuple[str, str]] = []
    for schema in harness.schemas:
        chosen = next(
            (
                version
                for version in schema.versions
                if version in server_schemas.get(schema.name, ())
            ),
            "",
        )
        if chosen:
            schema_versions.append((schema.name, chosen))
        else:
            diagnostics.append(
                Diagnostic(
                    "UNG-HANDSHAKE-006",
                    f"no common schema version for {schema.name}",
                    f"schemas.{schema.name}",
                )
            )
    if diagnostics:
        raise ValidationError("registry capability negotiation failed", diagnostics)

    descriptor_fields = tuple(
        field for field in harness.descriptor_fields if field in registry.descriptor_fields
    )
    missing_fields = sorted(set(harness.descriptor_fields) - set(descriptor_fields))
    if missing_fields:
        warnings.append("unavailable descriptor fields: " + ", ".join(missing_fields))
    return RegistrySession(
        protocol_version=protocol,
        registry_id=registry.registry_id,
        registry_version=registry.registry_version,
        registry_digest=registry.registry_digest,
        harness_id=harness.harness_id,
        harness_version=harness.harness_version,
        query_modes=tuple(modes),
        embedding_spaces=compatible_spaces,
        descriptor_fields=descriptor_fields,
        schema_versions=tuple(schema_versions),
        supports_enumeration=registry.supports_enumeration,
        supports_snapshots=registry.supports_snapshots,
        supports_continuation=registry.supports_continuation,
        supports_explanations=registry.supports_explanations,
        max_page_size=registry.max_page_size,
        warnings=tuple(warnings),
    )


@dataclass(frozen=True)
class DiscoveryQuery:
    """A content-addressed, replayable request for a working registry universe."""

    id: str
    session_digest: str
    text: str = ""
    required_capabilities: tuple[str, ...] = ()
    required_input_types: tuple[str, ...] = ()
    required_output_types: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    requested_modes: tuple[str, ...] = ()
    embedding_targets: tuple[tuple[str, str], ...] = ()
    page_size: int | None = None
    cursor: str = ""
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(
        self, session: RegistrySession | None = None, path: str = "discovery_query"
    ) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not DIGEST_RE.fullmatch(self.session_digest):
            problems.append(f"{path}.session_digest must be sha256:<64 lowercase hex chars>")
        for label, values in (
            ("required_capabilities", self.required_capabilities),
            ("required_input_types", self.required_input_types),
            ("required_output_types", self.required_output_types),
            ("domains", self.domains),
            ("tags", self.tags),
            ("requested_modes", self.requested_modes),
        ):
            problems.extend(_validate_unique_ids(values, f"{path}.{label}"))
        if self.page_size is not None and self.page_size <= 0:
            problems.append(f"{path}.page_size must be positive or null")
        spaces = [space for space, _ in self.embedding_targets]
        if len(self.embedding_targets) != len(set(self.embedding_targets)):
            problems.append(f"{path}.embedding_targets must be unique")
        if any(
            not ID_RE.fullmatch(space) or not target.strip()
            for space, target in self.embedding_targets
        ):
            problems.append(f"{path}.embedding_targets contains an invalid space or target")
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        if session is not None:
            if self.session_digest != session.digest:
                problems.append(f"{path}.session_digest does not match the negotiated session")
            unavailable_modes = sorted(set(self.requested_modes) - set(session.query_modes))
            if unavailable_modes:
                problems.append(
                    f"{path}.requested_modes were not negotiated: " + ", ".join(unavailable_modes)
                )
            available_spaces = {space.id for space in session.embedding_spaces}
            unavailable_spaces = sorted(set(spaces) - available_spaces)
            if unavailable_spaces:
                problems.append(
                    f"{path}.embedding_targets use unavailable spaces: "
                    + ", ".join(unavailable_spaces)
                )
            if (
                self.page_size is not None
                and session.max_page_size is not None
                and self.page_size > session.max_page_size
            ):
                problems.append(
                    f"{path}.page_size exceeds the registry's advertised operational maximum"
                )
            if self.cursor and not session.supports_continuation:
                problems.append(f"{path}.cursor requires continuation support")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery_version": DISCOVERY_PROTOCOL_VERSION,
            "id": self.id,
            "session_digest": self.session_digest,
            "text": self.text,
            "required_capabilities": list(self.required_capabilities),
            "required_input_types": list(self.required_input_types),
            "required_output_types": list(self.required_output_types),
            "domains": list(self.domains),
            "tags": list(self.tags),
            "requested_modes": list(self.requested_modes),
            "embedding_targets": [
                {"space_id": space, "target": target} for space, target in self.embedding_targets
            ],
            "page_size": self.page_size,
            "cursor": self.cursor,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class DiscoveryReceipt:
    """Evidence defining exactly how a compiler registry snapshot was discovered."""

    id: str
    query_digest: str
    session_digest: str
    source_registry_digest: str
    snapshot_registry_digest: str
    modes_used: tuple[str, ...]
    pages_fetched: int
    records_examined: int
    matches_returned: int
    result_node_spec_digests: tuple[str, ...]
    complete: bool
    continuation_token: str = ""
    total_matches: int | None = None
    explanations_available: bool = False
    coverage_notes: tuple[str, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "discovery_receipt") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        for label, digest in (
            ("query_digest", self.query_digest),
            ("session_digest", self.session_digest),
            ("source_registry_digest", self.source_registry_digest),
            ("snapshot_registry_digest", self.snapshot_registry_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be sha256:<64 lowercase hex chars>")
        if not self.modes_used:
            problems.append(f"{path}.modes_used must not be empty")
        problems.extend(_validate_unique_ids(self.modes_used, f"{path}.modes_used"))
        if self.pages_fetched < 0 or self.records_examined < 0 or self.matches_returned < 0:
            problems.append(f"{path} counts must be non-negative")
        if self.matches_returned != len(self.result_node_spec_digests):
            problems.append(f"{path}.matches_returned must equal result digest count")
        if len(self.result_node_spec_digests) != len(set(self.result_node_spec_digests)):
            problems.append(f"{path}.result_node_spec_digests must be unique")
        if any(not DIGEST_RE.fullmatch(digest) for digest in self.result_node_spec_digests):
            problems.append(f"{path}.result_node_spec_digests contains an invalid digest")
        if self.total_matches is not None and self.total_matches < self.matches_returned:
            problems.append(f"{path}.total_matches cannot be smaller than returned matches")
        if self.complete and self.continuation_token:
            problems.append(f"{path}.complete receipts cannot have a continuation token")
        if not self.complete and not self.continuation_token and not self.coverage_notes:
            problems.append(
                f"{path} incomplete discovery needs a continuation token or coverage note"
            )
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery_version": DISCOVERY_PROTOCOL_VERSION,
            "id": self.id,
            "query_digest": self.query_digest,
            "session_digest": self.session_digest,
            "source_registry_digest": self.source_registry_digest,
            "snapshot_registry_digest": self.snapshot_registry_digest,
            "modes_used": list(self.modes_used),
            "pages_fetched": self.pages_fetched,
            "records_examined": self.records_examined,
            "matches_returned": self.matches_returned,
            "result_node_spec_digests": list(self.result_node_spec_digests),
            "complete": self.complete,
            "continuation_token": self.continuation_token,
            "total_matches": self.total_matches,
            "explanations_available": self.explanations_available,
            "coverage_notes": list(self.coverage_notes),
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class RegistrySnapshot:
    """Closed-world compiler registry plus the evidence defining its boundary."""

    registry: Registry
    receipt: DiscoveryReceipt

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "registry_snapshot") -> list[str]:
        problems = self.receipt.validate(f"{path}.receipt")
        if self.receipt.snapshot_registry_digest != self.registry.digest:
            problems.append(f"{path}.receipt does not identify this registry")
        node_digests = {node.digest for node in self.registry.nodes}
        if node_digests != set(self.receipt.result_node_spec_digests):
            problems.append(f"{path}.receipt result digests do not match registry nodes")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry": self.registry.to_dict(),
            "discovery_receipt": self.receipt.to_dict(),
        }


@dataclass(frozen=True)
class ArtifactReference:
    name: str
    media_type: str
    digest: str
    uri: str = ""
    annotations: tuple[tuple[str, str], ...] = ()

    def validate(self, path: str = "artifact") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.name):
            problems.append(f"{path}.name must be a namespaced identifier")
        if not self.media_type.strip():
            problems.append(f"{path}.media_type must not be empty")
        if not DIGEST_RE.fullmatch(self.digest):
            problems.append(f"{path}.digest must be sha256:<64 lowercase hex chars>")
        keys = [key for key, _ in self.annotations]
        if len(keys) != len(set(keys)) or any(
            not ID_RE.fullmatch(key) or "." not in key for key in keys
        ):
            problems.append(f"{path}.annotations must have unique namespaced keys")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "media_type": self.media_type,
            "digest": self.digest,
            "uri": self.uri,
            "annotations": dict(self.annotations),
        }


@dataclass(frozen=True)
class NodePackManifest:
    """Portable, content-addressed collection of node contracts and sidecars."""

    id: str
    version: str
    description: str
    node_spec_digests: tuple[str, ...]
    descriptor_digests: tuple[str, ...] = ()
    embedding_record_digests: tuple[str, ...] = ()
    artifacts: tuple[ArtifactReference, ...] = ()
    dependencies: tuple[ArtifactReference, ...] = ()
    source: str = ""
    license: str = ""
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "node_pack") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.version.strip() or not self.description.strip():
            problems.append(f"{path}.version and description must not be empty")
        for label, values in (
            ("node_spec_digests", self.node_spec_digests),
            ("descriptor_digests", self.descriptor_digests),
            ("embedding_record_digests", self.embedding_record_digests),
        ):
            if label == "node_spec_digests" and not values:
                problems.append(f"{path}.{label} must not be empty")
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not DIGEST_RE.fullmatch(value) for value in values):
                problems.append(f"{path}.{label} contains an invalid digest")
        artifact_names = [artifact.name for artifact in (*self.artifacts, *self.dependencies)]
        if len(artifact_names) != len(set(artifact_names)):
            problems.append(f"{path} artifact and dependency names must be unique")
        for label, values in (
            ("artifacts", self.artifacts),
            ("dependencies", self.dependencies),
        ):
            for index, artifact in enumerate(values):
                problems.extend(artifact.validate(f"{path}.{label}[{index}]"))
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery_version": DISCOVERY_PROTOCOL_VERSION,
            "id": self.id,
            "version": self.version,
            "description": self.description,
            "node_spec_digests": list(self.node_spec_digests),
            "descriptor_digests": list(self.descriptor_digests),
            "embedding_record_digests": list(self.embedding_record_digests),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "dependencies": [artifact.to_dict() for artifact in self.dependencies],
            "source": self.source,
            "license": self.license,
            "extensions": dict(self.extensions),
        }


def descriptors_by_node(
    descriptors: tuple[NodeDescriptor, ...],
) -> Mapping[tuple[str, str], NodeDescriptor]:
    """Create a deterministic lookup and reject ambiguous descriptor versions."""
    result: dict[tuple[str, str], NodeDescriptor] = {}
    for descriptor in descriptors:
        key = descriptor.node_id, descriptor.node_version
        if key in result:
            raise ValueError(f"duplicate descriptor for {key[0]}@{key[1]}")
        result[key] = descriptor
    return result
