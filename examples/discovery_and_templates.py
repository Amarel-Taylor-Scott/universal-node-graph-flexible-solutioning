"""Negotiate a node registry and select a reusable semantic template."""
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from solutiongraph import (
    DiscoveryQuery,
    DiscoveryReceipt,
    HarnessCapabilities,
    RegistrySnapshot,
    SchemaSupport,
    negotiate_registry,
    sha256_digest,
)
from solutiongraph.catalog import reference_registry_capabilities
from solutiongraph.reference_nodes import REFERENCE_REGISTRY
from solutiongraph.template_library import REFERENCE_TEMPLATES


template = REFERENCE_TEMPLATES.matching(domains=("machine-learning.tabular",))[0]
print(template.id, len(template.stages), len(template.program.slots), template.digest)

harness = HarnessCapabilities(
    harness_id="example.local-harness",
    harness_version="1.0.0",
    protocol_versions=("0.1",),
    schemas=(
        SchemaSupport("node-spec", ("0.1",)),
        SchemaSupport("node-descriptor", ("0.1",)),
        SchemaSupport("node-pack", ("0.1",)),
    ),
    query_modes=("vector", "lexical", "enumeration"),
    descriptor_fields=("summary", "purposes", "actions", "ports"),
)
session = negotiate_registry(harness, reference_registry_capabilities())
print("negotiated", session.query_modes, session.warnings)

query = DiscoveryQuery(
    id="example.reference-nodes",
    session_digest=session.digest,
    text="small JSON and external connector primitives",
    requested_modes=("lexical", "enumeration"),
)
receipt = DiscoveryReceipt(
    id="example.reference-snapshot",
    query_digest=query.digest,
    session_digest=session.digest,
    source_registry_digest=reference_registry_capabilities().registry_digest,
    snapshot_registry_digest=REFERENCE_REGISTRY.digest,
    modes_used=("lexical", "enumeration"),
    pages_fetched=1,
    records_examined=len(REFERENCE_REGISTRY.nodes),
    matches_returned=len(REFERENCE_REGISTRY.nodes),
    result_node_spec_digests=tuple(node.digest for node in REFERENCE_REGISTRY.nodes),
    complete=True,
    total_matches=len(REFERENCE_REGISTRY.nodes),
    explanations_available=True,
    coverage_notes=("Local checked-in reference pack only.",),
    extensions=(("example.query-text-digest", sha256_digest(query.text)),),
)
snapshot = RegistrySnapshot(REFERENCE_REGISTRY, receipt)
assert query.validate(session) == []
assert snapshot.validate() == []
print(snapshot.digest, receipt.complete, receipt.matches_returned)
