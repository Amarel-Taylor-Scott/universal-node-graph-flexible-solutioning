"""Canonical node-pack manifests shared by catalogs and solution packs."""

from __future__ import annotations

from solutiongraph.discovery import ArtifactReference, NodePackManifest
from solutiongraph.examples.data_science_tasks import DATA_SCIENCE_NODES
from solutiongraph.examples.extended_tasks import EXTENDED_NODES
from solutiongraph.examples.showcase_tasks import SHOWCASE_NODES
from solutiongraph.examples.tasks import NODES as EXAMPLE_NODES
from solutiongraph.interrogation.node_pack import INTERROGATION_NODE_PACK
from solutiongraph.reference_nodes import REFERENCE_DESCRIPTORS, REFERENCE_NODE_SPECS

REPOSITORY_SOURCE = (
    "https://github.com/Amarel-Taylor-Scott/universal-node-graph-flexible-solutioning"
)


def _artifacts(nodes):
    return tuple(
        ArtifactReference(
            name=f"artifact.{node.id}",
            media_type="text/x-python",
            digest=node.implementation_digest,
            uri=f"python://{node.entrypoint}",
            annotations=(("org.opencontainers.image.title", node.entrypoint),),
        )
        for node in nodes
    )


REFERENCE_CORE_NODE_PACK = NodePackManifest(
    id="reference.core-node-pack",
    version="1.0.0",
    description=(
        "Executable demonstration primitives, identity behavior, and explicit "
        "filesystem/network connectors."
    ),
    node_spec_digests=tuple(node.digest for node in REFERENCE_NODE_SPECS),
    descriptor_digests=tuple(descriptor.digest for descriptor in REFERENCE_DESCRIPTORS),
    artifacts=_artifacts(REFERENCE_NODE_SPECS),
    source=REPOSITORY_SOURCE,
    license="MIT",
    extensions=(("reference.maturity", "demonstration"),),
)

REAL_WORLD_EXAMPLE_NODE_PACK = NodePackManifest(
    id="example.real-world-node-pack",
    version="1.0.0",
    description=(
        "Dependency-free executable teaching nodes for web, document, image, "
        "data quality, address verification, entity linking, forecasting, "
        "code repair, feed validation, regression, and classification examples."
    ),
    node_spec_digests=tuple(node.digest for node in EXAMPLE_NODES),
    artifacts=_artifacts(EXAMPLE_NODES),
    source=REPOSITORY_SOURCE,
    license="MIT",
    extensions=(("example.maturity", "executable-teaching-fixture"),),
)

EXTENDED_ARENA_NODE_PACK = NodePackManifest(
    id="example.extended-arena-node-pack",
    version="1.0.0",
    description=(
        "Strict and heuristic reference nodes for contact verification, web "
        "change monitoring, reconciliation, PII redaction, schema migration, "
        "incident triage, dependency assurance, recommendation ranking, "
        "scientific comparison, and numerical solving."
    ),
    node_spec_digests=tuple(node.digest for node in EXTENDED_NODES),
    artifacts=_artifacts(EXTENDED_NODES),
    source=REPOSITORY_SOURCE,
    license="MIT",
    extensions=(("example.maturity", "cross-domain-conformance-fixture"),),
)

ENGINEERING_SHOWCASE_NODE_PACK = NodePackManifest(
    id="example.engineering-showcase-node-pack",
    version="1.1.0",
    description=(
        "Dependency-free reference candidates for contract-aware cleaning, event-time "
        "windowing, GIS boundaries, backend APIs, frontend release journeys, document "
        "rendering, geotemporal enrichment, user journeys, synthetic tabular and LLM "
        "data, grounded documents, bounded reinforcement learning, and DueCare-style "
        "evaluation harnesses."
    ),
    node_spec_digests=tuple(node.digest for node in SHOWCASE_NODES),
    artifacts=_artifacts(SHOWCASE_NODES),
    source=REPOSITORY_SOURCE,
    license="MIT",
    extensions=(("example.maturity", "mechanism-fixture"),),
)

DATA_SCIENCE_LIFECYCLE_NODE_PACK = NodePackManifest(
    id="example.data-science-lifecycle-node-pack",
    version="1.0.0",
    description=(
        "Three-strategy executable nodes for dataset profiling, feature reduction, "
        "classification, regression, time series, text, clustering, explainability, "
        "ensembles, model release monitoring, and rollback."
    ),
    node_spec_digests=tuple(node.digest for node in DATA_SCIENCE_NODES),
    artifacts=_artifacts(DATA_SCIENCE_NODES),
    source=REPOSITORY_SOURCE,
    license="MIT",
    extensions=(("example.maturity", "deterministic-mechanism-fixture"),),
)

REFERENCE_NODE_PACKS = (
    REFERENCE_CORE_NODE_PACK,
    REAL_WORLD_EXAMPLE_NODE_PACK,
    EXTENDED_ARENA_NODE_PACK,
    ENGINEERING_SHOWCASE_NODE_PACK,
    DATA_SCIENCE_LIFECYCLE_NODE_PACK,
    INTERROGATION_NODE_PACK,
)


__all__ = [
    "EXTENDED_ARENA_NODE_PACK",
    "ENGINEERING_SHOWCASE_NODE_PACK",
    "INTERROGATION_NODE_PACK",
    "DATA_SCIENCE_LIFECYCLE_NODE_PACK",
    "REAL_WORLD_EXAMPLE_NODE_PACK",
    "REFERENCE_CORE_NODE_PACK",
    "REFERENCE_NODE_PACKS",
    "REPOSITORY_SOURCE",
]
