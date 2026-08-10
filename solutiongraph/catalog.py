"""Deterministic reference catalogue projection for repositories and registries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from solutiongraph.arena import UNIVERSAL_DAG_ARENA
from solutiongraph.discovery import (
    ArtifactReference,
    NodePackManifest,
    QueryMode,
    RegistryCapabilities,
    SchemaSupport,
)
from solutiongraph.examples.tasks import EXAMPLE_REGISTRY
from solutiongraph.examples.tasks import NODES as EXAMPLE_NODES
from solutiongraph.reference_nodes import (
    REFERENCE_DESCRIPTORS,
    REFERENCE_NODE_SPECS,
    REFERENCE_REGISTRY,
)
from solutiongraph.template_library import REFERENCE_TEMPLATES


def reference_registry_capabilities() -> RegistryCapabilities:
    """Advertise the search features actually present in the reference pack."""
    return RegistryCapabilities(
        registry_id=REFERENCE_REGISTRY.id,
        registry_version=REFERENCE_REGISTRY.version,
        registry_digest=REFERENCE_REGISTRY.digest,
        protocol_versions=("0.1",),
        schemas=(
            SchemaSupport("node-spec", ("0.1",)),
            SchemaSupport("node-descriptor", ("0.1",)),
            SchemaSupport("node-pack", ("0.1",)),
        ),
        query_modes=(
            QueryMode("exact", fields=("node_id", "node_spec_digest")),
            QueryMode(
                "lexical",
                fields=("title", "summary", "purposes", "actions", "documents"),
                supports_filters=True,
                supports_scores=True,
                supports_explanations=True,
            ),
            QueryMode("enumeration", supports_cursor=True),
        ),
        descriptor_fields=(
            "title",
            "summary",
            "purposes",
            "solutions",
            "actions",
            "domains",
            "tags",
            "ports",
            "documents",
        ),
        supports_enumeration=True,
        supports_snapshots=True,
        supports_continuation=True,
        supports_explanations=True,
        max_page_size=1000,
        extensions=(("reference.maturity", "demonstration"),),
    )


def example_registry_capabilities() -> RegistryCapabilities:
    """Advertise only exact lookup and enumeration for the sparse example pack."""
    return RegistryCapabilities(
        registry_id=EXAMPLE_REGISTRY.id,
        registry_version=EXAMPLE_REGISTRY.version,
        registry_digest=EXAMPLE_REGISTRY.digest,
        protocol_versions=("0.1",),
        schemas=(
            SchemaSupport("node-spec", ("0.1",)),
            SchemaSupport("node-pack", ("0.1",)),
        ),
        query_modes=(
            QueryMode("exact", fields=("node_id", "node_spec_digest")),
            QueryMode("enumeration", supports_cursor=True),
        ),
        supports_enumeration=True,
        supports_snapshots=True,
        supports_continuation=True,
        max_page_size=1000,
        extensions=(("example.maturity", "executable-teaching-fixture"),),
    )


def catalog_documents() -> dict[str, dict[str, Any]]:
    """Return every generated catalogue document keyed by portable relative path."""
    artifacts = tuple(
        ArtifactReference(
            name=f"artifact.{node.id}",
            media_type="text/x-python",
            digest=node.implementation_digest,
            uri=f"python://{node.entrypoint}",
            annotations=(("org.opencontainers.image.title", node.entrypoint),),
        )
        for node in REFERENCE_NODE_SPECS
    )
    node_pack = NodePackManifest(
        id="reference.core-node-pack",
        version="1.0.0",
        description=(
            "Executable demonstration primitives, identity behavior, and explicit "
            "filesystem/network connectors."
        ),
        node_spec_digests=tuple(node.digest for node in REFERENCE_NODE_SPECS),
        descriptor_digests=tuple(descriptor.digest for descriptor in REFERENCE_DESCRIPTORS),
        artifacts=artifacts,
        source=("https://github.com/Amarel-Taylor-Scott/universal-node-graph-flexible-solutioning"),
        license="MIT",
        extensions=(("reference.maturity", "demonstration"),),
    )
    capabilities = reference_registry_capabilities()
    example_artifacts = tuple(
        ArtifactReference(
            name=f"artifact.{node.id}",
            media_type="text/x-python",
            digest=node.implementation_digest,
            uri=f"python://{node.entrypoint}",
            annotations=(("org.opencontainers.image.title", node.entrypoint),),
        )
        for node in EXAMPLE_NODES
    )
    example_pack = NodePackManifest(
        id="example.real-world-node-pack",
        version="1.0.0",
        description=(
            "Dependency-free executable teaching nodes for web, document, image, "
            "data quality, address verification, entity linking, forecasting, "
            "code repair, feed validation, regression, and classification examples."
        ),
        node_spec_digests=tuple(node.digest for node in EXAMPLE_NODES),
        artifacts=example_artifacts,
        source=(
            "https://github.com/Amarel-Taylor-Scott/"
            "universal-node-graph-flexible-solutioning"
        ),
        license="MIT",
        extensions=(("example.maturity", "executable-teaching-fixture"),),
    )
    example_capabilities = example_registry_capabilities()
    documents: dict[str, dict[str, Any]] = {
        "nodepacks/reference-core/manifest.json": node_pack.to_dict(),
        "nodepacks/reference-core/registry.json": REFERENCE_REGISTRY.to_dict(),
        "nodepacks/reference-core/registry-capabilities.json": capabilities.to_dict(),
        "nodepacks/real-world-examples/manifest.json": example_pack.to_dict(),
        "nodepacks/real-world-examples/registry.json": EXAMPLE_REGISTRY.to_dict(),
        "nodepacks/real-world-examples/registry-capabilities.json": (
            example_capabilities.to_dict()
        ),
    }
    for node in REFERENCE_NODE_SPECS:
        documents[f"nodepacks/reference-core/nodes/{node.id}.json"] = node.to_dict()
    for descriptor in REFERENCE_DESCRIPTORS:
        documents[f"nodepacks/reference-core/descriptors/{descriptor.node_id}.json"] = (
            descriptor.to_dict()
        )
    for node in EXAMPLE_NODES:
        documents[f"nodepacks/real-world-examples/nodes/{node.id}.json"] = (
            node.to_dict()
        )
    for template in REFERENCE_TEMPLATES.templates:
        documents[f"templates/{template.id}.json"] = template.to_dict()
    for task in UNIVERSAL_DAG_ARENA.tasks:
        documents[f"arena/{task.id}.json"] = task.to_dict()

    documents["arena/index.json"] = UNIVERSAL_DAG_ARENA.to_dict()

    documents["index.json"] = {
        "catalog_model_version": "0.1",
        "templates": [
            {
                "id": template.id,
                "version": template.version,
                "digest": template.digest,
                "path": f"templates/{template.id}.json",
                "domains": list(template.domains),
                "tags": list(template.tags),
                "atomic_slot_count": len(template.program.slots),
            }
            for template in REFERENCE_TEMPLATES.templates
        ],
        "node_packs": [
            {
                "id": node_pack.id,
                "version": node_pack.version,
                "digest": node_pack.digest,
                "path": "nodepacks/reference-core/manifest.json",
                "node_count": len(REFERENCE_NODE_SPECS),
                "descriptor_count": len(REFERENCE_DESCRIPTORS),
                "embedding_record_count": 0,
            },
            {
                "id": example_pack.id,
                "version": example_pack.version,
                "digest": example_pack.digest,
                "path": "nodepacks/real-world-examples/manifest.json",
                "node_count": len(EXAMPLE_NODES),
                "descriptor_count": 0,
                "embedding_record_count": 0,
            },
        ],
        "arena": {
            "path": "arena/index.json",
            "task_count": len(UNIVERSAL_DAG_ARENA.tasks),
            "executable_fixture_count": len(
                UNIVERSAL_DAG_ARENA.matching(readiness="executable_fixture")
            ),
        },
    }
    return dict(sorted(documents.items()))


def write_catalog(root: str | Path) -> tuple[Path, ...]:
    """Write the deterministic documents and return their paths."""
    root_path = Path(root)
    written: list[Path] = []
    for relative, document in catalog_documents().items():
        target = root_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written.append(target)
    return tuple(written)


__all__ = [
    "catalog_documents",
    "example_registry_capabilities",
    "reference_registry_capabilities",
    "write_catalog",
]
