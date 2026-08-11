"""Deterministic reference catalogue projection for repositories and registries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from solutiongraph.arena import UNIVERSAL_DAG_ARENA
from solutiongraph.benchmark_library import REFERENCE_BENCHMARKS
from solutiongraph.discovery import (
    QueryMode,
    RegistryCapabilities,
    SchemaSupport,
)
from solutiongraph.examples.extended_tasks import (
    EXTENDED_NODES,
    EXTENDED_REGISTRY,
)
from solutiongraph.examples.tasks import EXAMPLE_REGISTRY
from solutiongraph.examples.tasks import NODES as EXAMPLE_NODES
from solutiongraph.pack_library import (
    EXTENDED_ARENA_NODE_PACK,
    REAL_WORLD_EXAMPLE_NODE_PACK,
    REFERENCE_CORE_NODE_PACK,
)
from solutiongraph.reference_nodes import (
    REFERENCE_DESCRIPTORS,
    REFERENCE_NODE_SPECS,
    REFERENCE_REGISTRY,
)
from solutiongraph.stdlib_pack import (
    STANDARD_LIBRARY_DESCRIPTORS,
    STANDARD_LIBRARY_NODE_PACK,
    STANDARD_LIBRARY_NODE_SPECS,
    STANDARD_LIBRARY_REGISTRY,
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
            SchemaSupport("node-spec", ("0.2",)),
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
            SchemaSupport("node-spec", ("0.2",)),
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


def extended_registry_capabilities() -> RegistryCapabilities:
    """Advertise exact lookup and enumeration for the extended Arena pack."""
    return RegistryCapabilities(
        registry_id=EXTENDED_REGISTRY.id,
        registry_version=EXTENDED_REGISTRY.version,
        registry_digest=EXTENDED_REGISTRY.digest,
        protocol_versions=("0.1",),
        schemas=(
            SchemaSupport("node-spec", ("0.2",)),
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
        extensions=(("example.maturity", "cross-domain-conformance-fixture"),),
    )


def standard_library_registry_capabilities() -> RegistryCapabilities:
    """Advertise strict and lexical discovery for reusable standard nodes."""
    return RegistryCapabilities(
        registry_id=STANDARD_LIBRARY_REGISTRY.id,
        registry_version=STANDARD_LIBRARY_REGISTRY.version,
        registry_digest=STANDARD_LIBRARY_REGISTRY.digest,
        protocol_versions=("0.1",),
        schemas=(
            SchemaSupport("node-spec", ("0.2",)),
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
            "title", "summary", "purposes", "solutions", "actions",
            "domains", "tags", "ports", "documents",
        ),
        supports_enumeration=True,
        supports_snapshots=True,
        supports_continuation=True,
        supports_explanations=True,
        max_page_size=1000,
        extensions=(("stdlib.maturity", "reference"),),
    )


def catalog_documents() -> dict[str, dict[str, Any]]:
    """Return every generated catalogue document keyed by portable relative path."""
    node_pack = REFERENCE_CORE_NODE_PACK
    capabilities = reference_registry_capabilities()
    example_pack = REAL_WORLD_EXAMPLE_NODE_PACK
    example_capabilities = example_registry_capabilities()
    extended_pack = EXTENDED_ARENA_NODE_PACK
    extended_capabilities = extended_registry_capabilities()
    stdlib_capabilities = standard_library_registry_capabilities()
    documents: dict[str, dict[str, Any]] = {
        "nodepacks/reference-core/manifest.json": node_pack.to_dict(),
        "nodepacks/reference-core/registry.json": REFERENCE_REGISTRY.to_dict(),
        "nodepacks/reference-core/registry-capabilities.json": capabilities.to_dict(),
        "nodepacks/real-world-examples/manifest.json": example_pack.to_dict(),
        "nodepacks/real-world-examples/registry.json": EXAMPLE_REGISTRY.to_dict(),
        "nodepacks/real-world-examples/registry-capabilities.json": (
            example_capabilities.to_dict()
        ),
        "nodepacks/extended-arena/manifest.json": extended_pack.to_dict(),
        "nodepacks/extended-arena/registry.json": EXTENDED_REGISTRY.to_dict(),
        "nodepacks/extended-arena/registry-capabilities.json": (
            extended_capabilities.to_dict()
        ),
        "nodepacks/stdlib-data-foundation/manifest.json": (
            STANDARD_LIBRARY_NODE_PACK.to_dict()
        ),
        "nodepacks/stdlib-data-foundation/registry.json": (
            STANDARD_LIBRARY_REGISTRY.to_dict()
        ),
        "nodepacks/stdlib-data-foundation/registry-capabilities.json": (
            stdlib_capabilities.to_dict()
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
    for node in EXTENDED_NODES:
        documents[f"nodepacks/extended-arena/nodes/{node.id}.json"] = node.to_dict()
    for node in STANDARD_LIBRARY_NODE_SPECS:
        documents[f"nodepacks/stdlib-data-foundation/nodes/{node.id}.json"] = (
            node.to_dict()
        )
    for descriptor in STANDARD_LIBRARY_DESCRIPTORS:
        documents[
            f"nodepacks/stdlib-data-foundation/descriptors/{descriptor.node_id}.json"
        ] = descriptor.to_dict()
    for template in REFERENCE_TEMPLATES.templates:
        documents[f"templates/{template.id}.json"] = template.to_dict()
    for task in UNIVERSAL_DAG_ARENA.tasks:
        documents[f"arena/{task.id}.json"] = task.to_dict()

    documents["arena/index.json"] = UNIVERSAL_DAG_ARENA.to_dict()

    for bundle in REFERENCE_BENCHMARKS:
        root = f"benchmarks/{bundle.id}"
        documents[f"{root}/suite.json"] = bundle.definition.suite.to_dict()
        documents[f"{root}/task-contract.json"] = (
            bundle.definition.task_contract.to_dict()
        )
        documents[f"{root}/solution-pack.json"] = bundle.solution_pack.to_dict()
        for case in bundle.definition.task_cases:
            documents[f"{root}/cases/{case.id}.json"] = case.to_dict()
        for plan in bundle.baseline_plans:
            documents[f"{root}/baselines/{plan.digest.removeprefix('sha256:')}.json"] = (
                plan.to_dict()
            )

    documents["benchmarks/index.json"] = {
        "benchmark_model_version": "0.1",
        "benchmark_count": len(REFERENCE_BENCHMARKS),
        "benchmarks": [
            {
                "id": bundle.id,
                "version": bundle.definition.suite.version,
                "digest": bundle.definition.suite.digest,
                "solution_pack_digest": bundle.solution_pack.digest,
                "claim_scope": bundle.definition.suite.claim_scope,
                "case_count": len(bundle.definition.task_cases),
                "arm_count": len(bundle.definition.suite.arms),
                "path": f"benchmarks/{bundle.id}/suite.json",
            }
            for bundle in REFERENCE_BENCHMARKS
        ],
    }

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
                "id": STANDARD_LIBRARY_NODE_PACK.id,
                "version": STANDARD_LIBRARY_NODE_PACK.version,
                "digest": STANDARD_LIBRARY_NODE_PACK.digest,
                "path": "nodepacks/stdlib-data-foundation/manifest.json",
                "node_count": len(STANDARD_LIBRARY_NODE_SPECS),
                "descriptor_count": len(STANDARD_LIBRARY_DESCRIPTORS),
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
            {
                "id": extended_pack.id,
                "version": extended_pack.version,
                "digest": extended_pack.digest,
                "path": "nodepacks/extended-arena/manifest.json",
                "node_count": len(EXTENDED_NODES),
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
        "benchmarks": {
            "path": "benchmarks/index.json",
            "benchmark_count": len(REFERENCE_BENCHMARKS),
            "task_case_count": sum(
                len(bundle.definition.task_cases) for bundle in REFERENCE_BENCHMARKS
            ),
            "solution_pack_count": len(REFERENCE_BENCHMARKS),
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
    "extended_registry_capabilities",
    "reference_registry_capabilities",
    "standard_library_registry_capabilities",
    "write_catalog",
]
