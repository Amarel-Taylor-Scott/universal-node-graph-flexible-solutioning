from __future__ import annotations

from dataclasses import replace

import pytest

from solutiongraph import (
    ArtifactReference,
    Candidate,
    DiscoveryQuery,
    DiscoveryReceipt,
    EmbeddingRecord,
    EmbeddingSpace,
    HarnessCapabilities,
    NodeDescriptor,
    NodePackManifest,
    NodeSpec,
    Port,
    PortMeaning,
    QueryMode,
    Registry,
    RegistryCapabilities,
    RegistrySnapshot,
    SchemaSupport,
    SearchDocument,
    ValidationError,
    ValueType,
    negotiate_registry,
    sha256_digest,
)
from solutiongraph.schemas import load_all_schemas


def node_fixture() -> NodeSpec:
    return NodeSpec(
        id="example.parse.json",
        version="1.0.0",
        implementation_digest=sha256_digest("example.parse.json:implementation"),
        inputs=(Port("raw", ValueType("example.raw")),),
        outputs=(Port("value", ValueType("example.value")),),
        runtime="python",
        entrypoint="example_nodes:parse_json",
        capabilities=("example.parse",),
    )


def descriptor_fixture(node: NodeSpec | None = None) -> NodeDescriptor:
    node = node or node_fixture()
    return NodeDescriptor(
        node_id=node.id,
        node_version=node.version,
        node_spec_digest=node.digest,
        title="Parse JSON",
        summary="Parse a raw JSON document into a typed value.",
        purposes=("Turn serialized data into a structured value.",),
        actions=("parse",),
        domains=("data.processing",),
        ports=(
            PortMeaning("input", "raw", "A serialized JSON document."),
            PortMeaning("output", "value", "The parsed value."),
        ),
        documents=(
            SearchDocument(
                "example.node-overview",
                "A strict JSON parser for data processing pipelines.",
            ),
        ),
        extensions=(("example.maintainer", "team-data"),),
    )


def dense_space(*, revision: str = "2026-01", dimensions: int = 3) -> EmbeddingSpace:
    return EmbeddingSpace(
        id="example.semantic-v1",
        model_id="example.embedding-model",
        model_revision=revision,
        model_digest=sha256_digest(f"model:{revision}"),
        vector_kind="dense",
        dimensions=dimensions,
        distance="cosine",
        normalization="l2",
    )


def registry_capabilities(
    node: NodeSpec | None = None,
    *,
    spaces: tuple[EmbeddingSpace, ...] = (),
) -> RegistryCapabilities:
    node = node or node_fixture()
    return RegistryCapabilities(
        registry_id="example.registry",
        registry_version="1.0.0",
        registry_digest=sha256_digest("registry-source"),
        protocol_versions=("0.1",),
        schemas=(SchemaSupport("node-spec", ("0.1",)),),
        query_modes=(
            QueryMode("vector", requires_embedding_space=True, supports_scores=True),
            QueryMode("lexical", fields=("summary",), supports_scores=True),
            QueryMode("enumeration", supports_cursor=True),
        ),
        embedding_spaces=spaces,
        descriptor_fields=("summary", "actions", "ports"),
        supports_continuation=True,
        max_page_size=500,
    )


def harness_capabilities(*, spaces: tuple[EmbeddingSpace, ...] = ()) -> HarnessCapabilities:
    return HarnessCapabilities(
        harness_id="example.harness",
        harness_version="1.0.0",
        protocol_versions=("0.1",),
        schemas=(SchemaSupport("node-spec", ("0.1",)),),
        query_modes=("vector", "lexical", "enumeration"),
        embedding_spaces=spaces,
        descriptor_fields=("summary", "actions", "unknown-field"),
    )


def test_descriptor_is_sparse_search_metadata_bound_to_the_exact_node_contract():
    node = node_fixture()
    descriptor = descriptor_fixture(node)

    assert descriptor.validate(node) == []
    assert descriptor.digest.startswith("sha256:")
    assert NodeDescriptor(node.id, node.version, node.digest).validate(node) == []

    changed_node = replace(node, description="A contract change.")
    assert any("does not match" in item for item in descriptor.validate(changed_node))
    bad_port = replace(
        descriptor,
        ports=(PortMeaning("input", "missing", "Unknown ABI port."),),
    )
    assert any("unknown input missing" in item for item in bad_port.validate(node))


def test_embedding_records_require_an_exact_declared_space_and_one_storage_form():
    node = node_fixture()
    descriptor = descriptor_fixture(node)
    space = dense_space()
    record = EmbeddingRecord(
        id="example.node-summary-vector",
        node_spec_digest=node.digest,
        descriptor_digest=descriptor.digest,
        space_id=space.id,
        target="node.summary",
        values=(0.1, 0.2, 0.3),
        source_text_digest=sha256_digest(descriptor.summary),
    )

    assert record.validate(space) == []
    assert not space.is_compatible_with(dense_space(revision="2026-02"))
    assert not space.is_compatible_with(dense_space(dimensions=4))
    assert (
        EmbeddingRecord(
            id="example.external-vector",
            node_spec_digest=node.digest,
            descriptor_digest=descriptor.digest,
            space_id=space.id,
            target="node.summary",
            artifact_digest=sha256_digest("vector-artifact"),
            artifact_uri="oci://example/vectors@sha256:abc",
        ).validate(space)
        == []
    )
    invalid = replace(record, artifact_digest=sha256_digest("second-form"))
    assert any("exactly one" in item for item in invalid.validate(space))
    orphan_uri = replace(record, values=(), artifact_uri="oci://example/vector")
    assert any("artifact_digest is required" in item for item in orphan_uri.validate(space))

    sparse = EmbeddingSpace(
        id="example.sparse-v1",
        model_id="example.sparse-model",
        model_revision="1",
        vector_kind="sparse",
        dimensions=10,
        distance="dot",
    )
    out_of_range = replace(
        record,
        space_id=sparse.id,
        values=(),
        sparse_values=((10, 1.0),),
    )
    assert any("exceeds space dimensions" in item for item in out_of_range.validate(sparse))


def test_handshake_negotiates_exact_vector_identity_and_falls_back_without_guessing():
    incompatible = dense_space(revision="2026-02")
    session = negotiate_registry(
        harness_capabilities(spaces=(incompatible,)),
        registry_capabilities(spaces=(dense_space(),)),
    )

    assert session.query_modes == ("lexical", "enumeration")
    assert session.embedding_spaces == ()
    assert any("disabled vector" in warning for warning in session.warnings)
    assert any("unknown-field" in warning for warning in session.warnings)

    exact = dense_space()
    vector_session = negotiate_registry(
        harness_capabilities(spaces=(exact,)),
        registry_capabilities(spaces=(exact,)),
    )
    assert vector_session.query_modes[0] == "vector"
    assert vector_session.embedding_spaces == (exact,)


def test_handshake_rejects_protocol_schema_and_query_mismatches_with_diagnostics():
    registry = registry_capabilities()
    no_protocol = replace(harness_capabilities(), protocol_versions=("9.9",))
    with pytest.raises(ValidationError) as protocol_error:
        negotiate_registry(no_protocol, registry)
    assert "UNG-HANDSHAKE-003" in str(protocol_error.value)

    no_schema = replace(
        harness_capabilities(),
        schemas=(SchemaSupport("node-spec", ("9.9",)),),
    )
    with pytest.raises(ValidationError) as schema_error:
        negotiate_registry(no_schema, registry)
    assert "UNG-HANDSHAKE-006" in str(schema_error.value)

    no_mode = replace(harness_capabilities(), query_modes=("exact",))
    with pytest.raises(ValidationError) as mode_error:
        negotiate_registry(no_mode, registry)
    assert "UNG-HANDSHAKE-004" in str(mode_error.value)

    no_snapshots = replace(registry, supports_snapshots=False)
    with pytest.raises(ValidationError) as snapshot_error:
        negotiate_registry(harness_capabilities(), no_snapshots)
    assert "UNG-HANDSHAKE-007" in str(snapshot_error.value)


def test_discovery_query_is_replayable_and_respects_negotiated_limits():
    session = negotiate_registry(harness_capabilities(), registry_capabilities())
    query = DiscoveryQuery(
        id="example.parsers",
        session_digest=session.digest,
        text="parse structured JSON",
        required_capabilities=("example.parse",),
        requested_modes=("lexical", "enumeration"),
        page_size=250,
    )
    assert query.validate(session) == []
    assert query.digest.startswith("sha256:")
    duplicated = replace(
        query,
        embedding_targets=(
            ("example.semantic-v1", "node.summary"),
            ("example.semantic-v1", "node.summary"),
        ),
    )
    assert any("must be unique" in item for item in duplicated.validate())
    too_large = replace(query, page_size=501)
    assert any("operational maximum" in item for item in too_large.validate(session))


def test_receipt_closes_an_open_registry_query_into_an_exact_compiler_snapshot():
    node = node_fixture()
    candidate = Candidate(
        id="example.parse.json.default",
        node_id=node.id,
        node_version=node.version,
        implementation_digest=node.implementation_digest,
    )
    registry = Registry("example.snapshot", "1.0.0", (node,), (candidate,))
    receipt = DiscoveryReceipt(
        id="example.discovery-receipt",
        query_digest=sha256_digest("query"),
        session_digest=sha256_digest("session"),
        source_registry_digest=sha256_digest("source-registry"),
        snapshot_registry_digest=registry.digest,
        modes_used=("lexical",),
        pages_fetched=1,
        records_examined=20,
        matches_returned=1,
        result_node_spec_digests=(node.digest,),
        complete=True,
        total_matches=1,
    )
    snapshot = RegistrySnapshot(registry, receipt)
    assert snapshot.validate() == []

    incomplete = replace(receipt, complete=False)
    assert any("continuation token or coverage note" in item for item in incomplete.validate())
    wrong = replace(receipt, result_node_spec_digests=(sha256_digest("other"),))
    assert any("do not match" in item for item in RegistrySnapshot(registry, wrong).validate())


def test_node_pack_is_content_addressed_and_allows_only_namespaced_extensions():
    node = node_fixture()
    descriptor = descriptor_fixture(node)
    artifact = ArtifactReference(
        name="example.python-source",
        media_type="text/x-python",
        digest=node.implementation_digest,
        annotations=(("org.opencontainers.image.title", "example_nodes.py"),),
    )
    pack = NodePackManifest(
        id="example.core-node-pack",
        version="1.0.0",
        description="Reference portable nodes.",
        node_spec_digests=(node.digest,),
        descriptor_digests=(descriptor.digest,),
        artifacts=(artifact,),
        source="https://example.invalid/nodes",
        license="MIT",
        extensions=(("example.search-policy", {"lexical": True}),),
    )
    assert pack.validate() == []
    assert pack.digest.startswith("sha256:")
    assert any(
        "namespaced" in item
        for item in replace(pack, extensions=(("unnamespaced", True),)).validate()
    )


def test_discovery_and_template_wire_schemas_are_strict_but_extensions_are_open():
    schemas = load_all_schemas()
    expected = {
        "node-descriptor.schema.json",
        "embedding-record.schema.json",
        "registry-capabilities.schema.json",
        "harness-capabilities.schema.json",
        "registry-session.schema.json",
        "discovery-query.schema.json",
        "discovery-receipt.schema.json",
        "registry-snapshot.schema.json",
        "node-pack.schema.json",
        "solution-template.schema.json",
        "search-report.schema.json",
    }
    assert expected.issubset(schemas)
    assert all(schemas[name]["additionalProperties"] is False for name in expected)
    assert schemas["common.schema.json"]["$defs"]["extensions"]["additionalProperties"] is True
