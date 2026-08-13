"""Deterministic reference catalogue projection for repositories and registries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from solutiongraph.agent_bench.config import (
    command_matrix_example_suite,
    reference_agent_benchmark_suite,
)
from solutiongraph.agent_bench.tasks import REFERENCE_AGENT_TASKS
from solutiongraph.arena import UNIVERSAL_DAG_ARENA
from solutiongraph.benchmark_library import REFERENCE_BENCHMARKS
from solutiongraph.discovery import (
    QueryMode,
    RegistryCapabilities,
    SchemaSupport,
)
from solutiongraph.examples.data_science_tasks import (
    DATA_SCIENCE_NODES,
    DATA_SCIENCE_REGISTRY,
)
from solutiongraph.examples.extended_tasks import (
    EXTENDED_NODES,
    EXTENDED_REGISTRY,
)
from solutiongraph.examples.showcase_tasks import (
    DUECARE_HARNESS_BUNDLE,
    DUECARE_HARNESS_EVIDENCE,
    SHOWCASE_NODES,
    SHOWCASE_REGISTRY,
)
from solutiongraph.examples.tasks import EXAMPLE_REGISTRY
from solutiongraph.examples.tasks import NODES as EXAMPLE_NODES
from solutiongraph.interrogation.node_pack import (
    INTERROGATION_DESCRIPTORS,
    INTERROGATION_NODE_PACK,
    INTERROGATION_NODE_SPECS,
    INTERROGATION_REGISTRY,
)
from solutiongraph.pack_library import (
    DATA_SCIENCE_LIFECYCLE_NODE_PACK,
    ENGINEERING_SHOWCASE_NODE_PACK,
    EXTENDED_ARENA_NODE_PACK,
    REAL_WORLD_EXAMPLE_NODE_PACK,
    REFERENCE_CORE_NODE_PACK,
)
from solutiongraph.question_packs import (
    REFERENCE_CONCEPTS,
    REFERENCE_QUESTION_PACKS,
    REFERENCE_QUESTIONS,
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
        extensions=(("stdlib.maturity", "reference"),),
    )


def showcase_registry_capabilities() -> RegistryCapabilities:
    """Advertise exact lookup and enumeration for showcase mechanism fixtures."""
    return RegistryCapabilities(
        registry_id=SHOWCASE_REGISTRY.id,
        registry_version=SHOWCASE_REGISTRY.version,
        registry_digest=SHOWCASE_REGISTRY.digest,
        protocol_versions=("0.1",),
        schemas=(
            SchemaSupport("node-spec", ("0.2",)),
            SchemaSupport("node-pack", ("0.1",)),
            SchemaSupport("harness-bundle", ("0.1",)),
        ),
        query_modes=(
            QueryMode("exact", fields=("node_id", "node_spec_digest")),
            QueryMode("enumeration", supports_cursor=True),
        ),
        supports_enumeration=True,
        supports_snapshots=True,
        supports_continuation=True,
        max_page_size=1000,
        extensions=(("example.maturity", "mechanism-fixture"),),
    )


def data_science_registry_capabilities() -> RegistryCapabilities:
    """Advertise exact lookup and enumeration for lifecycle mechanism fixtures."""
    return RegistryCapabilities(
        registry_id=DATA_SCIENCE_REGISTRY.id,
        registry_version=DATA_SCIENCE_REGISTRY.version,
        registry_digest=DATA_SCIENCE_REGISTRY.digest,
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
        extensions=(("example.maturity", "deterministic-mechanism-fixture"),),
    )


def interrogation_registry_capabilities() -> RegistryCapabilities:
    """Advertise strict and lexical discovery for interrogation stages."""
    return RegistryCapabilities(
        registry_id=INTERROGATION_REGISTRY.id,
        registry_version=INTERROGATION_REGISTRY.version,
        registry_digest=INTERROGATION_REGISTRY.digest,
        protocol_versions=("0.1",),
        schemas=(
            SchemaSupport("node-spec", ("0.2",)),
            SchemaSupport("node-descriptor", ("0.1",)),
            SchemaSupport("node-pack", ("0.1",)),
            SchemaSupport("question-pack", ("0.1",)),
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
            "title", "summary", "purposes", "solutions", "actions", "domains",
            "tags", "ports", "documents",
        ),
        supports_enumeration=True,
        supports_snapshots=True,
        supports_continuation=True,
        supports_explanations=True,
        max_page_size=1000,
        extensions=(("interrogation.maturity", "reference"),),
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
    showcase_capabilities = showcase_registry_capabilities()
    data_science_capabilities = data_science_registry_capabilities()
    interrogation_capabilities = interrogation_registry_capabilities()
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
        "nodepacks/extended-arena/registry-capabilities.json": (extended_capabilities.to_dict()),
        "nodepacks/stdlib-data-foundation/manifest.json": (STANDARD_LIBRARY_NODE_PACK.to_dict()),
        "nodepacks/stdlib-data-foundation/registry.json": (STANDARD_LIBRARY_REGISTRY.to_dict()),
        "nodepacks/stdlib-data-foundation/registry-capabilities.json": (
            stdlib_capabilities.to_dict()
        ),
        "nodepacks/engineering-showcases/manifest.json": (ENGINEERING_SHOWCASE_NODE_PACK.to_dict()),
        "nodepacks/engineering-showcases/registry.json": SHOWCASE_REGISTRY.to_dict(),
        "nodepacks/engineering-showcases/registry-capabilities.json": (
            showcase_capabilities.to_dict()
        ),
        "nodepacks/data-science-lifecycle/manifest.json": (
            DATA_SCIENCE_LIFECYCLE_NODE_PACK.to_dict()
        ),
        "nodepacks/data-science-lifecycle/registry.json": DATA_SCIENCE_REGISTRY.to_dict(),
        "nodepacks/data-science-lifecycle/registry-capabilities.json": (
            data_science_capabilities.to_dict()
        ),
        "nodepacks/semantic-interrogation/manifest.json": INTERROGATION_NODE_PACK.to_dict(),
        "nodepacks/semantic-interrogation/registry.json": INTERROGATION_REGISTRY.to_dict(),
        "nodepacks/semantic-interrogation/registry-capabilities.json": (
            interrogation_capabilities.to_dict()
        ),
        "harnesses/duecare-example.json": DUECARE_HARNESS_BUNDLE.to_dict(),
        "harnesses/duecare-evidence-example.json": DUECARE_HARNESS_EVIDENCE.to_dict(),
    }
    reference_agent_suite = reference_agent_benchmark_suite()
    command_agent_suite = command_matrix_example_suite()
    for bundle in REFERENCE_AGENT_TASKS:
        documents[f"agent-bench/tasks/{bundle.spec.id}.json"] = bundle.spec.to_dict()
    documents["agent-bench/suites/reference-smoke.json"] = reference_agent_suite.to_dict()
    documents["agent-bench/suites/command-matrix-example.json"] = command_agent_suite.to_dict()
    documents["agent-bench/index.json"] = {
        "agent_bench_model_version": "0.1",
        "task_count": len(REFERENCE_AGENT_TASKS),
        "tasks": [
            {
                "id": bundle.spec.id,
                "version": bundle.spec.version,
                "digest": bundle.spec.digest,
                "template_id": bundle.spec.template_id,
                "category_ids": list(bundle.spec.categories),
                "case_count": len(bundle.spec.cases),
                "sealed_case_count": len(bundle.spec.sealed_case_ids),
                "path": f"agent-bench/tasks/{bundle.spec.id}.json",
            }
            for bundle in REFERENCE_AGENT_TASKS
        ],
        "suites": [
            {
                "id": suite.id,
                "version": suite.version,
                "digest": suite.digest,
                "claim_scope": suite.claim_scope,
                "enabled_trial_count": suite.total_trials,
                "path": path,
            }
            for suite, path in (
                (reference_agent_suite, "agent-bench/suites/reference-smoke.json"),
                (command_agent_suite, "agent-bench/suites/command-matrix-example.json"),
            )
        ],
        "sealed_payloads_published": False,
    }
    for node in REFERENCE_NODE_SPECS:
        documents[f"nodepacks/reference-core/nodes/{node.id}.json"] = node.to_dict()
    for descriptor in REFERENCE_DESCRIPTORS:
        documents[f"nodepacks/reference-core/descriptors/{descriptor.node_id}.json"] = (
            descriptor.to_dict()
        )
    for node in EXAMPLE_NODES:
        documents[f"nodepacks/real-world-examples/nodes/{node.id}.json"] = node.to_dict()
    for node in EXTENDED_NODES:
        documents[f"nodepacks/extended-arena/nodes/{node.id}.json"] = node.to_dict()
    for node in STANDARD_LIBRARY_NODE_SPECS:
        documents[f"nodepacks/stdlib-data-foundation/nodes/{node.id}.json"] = node.to_dict()
    for node in SHOWCASE_NODES:
        documents[f"nodepacks/engineering-showcases/nodes/{node.id}.json"] = node.to_dict()
    for node in DATA_SCIENCE_NODES:
        documents[f"nodepacks/data-science-lifecycle/nodes/{node.id}.json"] = node.to_dict()
    for node in INTERROGATION_NODE_SPECS:
        documents[f"nodepacks/semantic-interrogation/nodes/{node.id}.json"] = node.to_dict()
    for descriptor in INTERROGATION_DESCRIPTORS:
        documents[
            f"nodepacks/semantic-interrogation/descriptors/{descriptor.node_id}.json"
        ] = descriptor.to_dict()
    for descriptor in STANDARD_LIBRARY_DESCRIPTORS:
        documents[f"nodepacks/stdlib-data-foundation/descriptors/{descriptor.node_id}.json"] = (
            descriptor.to_dict()
        )
    for concept in REFERENCE_CONCEPTS:
        documents[f"question-packs/concepts/{concept.id}.json"] = concept.to_dict()
    for pack in REFERENCE_QUESTION_PACKS:
        documents[f"question-packs/packs/{pack.id}.json"] = pack.to_dict()
    for question in REFERENCE_QUESTIONS:
        documents[f"question-packs/questions/{question.id}.json"] = question.to_dict()
    documents["question-packs/index.json"] = {
        "interrogation_model_version": "0.1",
        "concept_count": len(REFERENCE_CONCEPTS),
        "pack_count": len(REFERENCE_QUESTION_PACKS),
        "question_count": len(REFERENCE_QUESTIONS),
        "concepts": [
            {"id": item.id, "digest": item.digest, "path": f"question-packs/concepts/{item.id}.json"}
            for item in REFERENCE_CONCEPTS
        ],
        "packs": [
            {
                "id": item.id,
                "digest": item.digest,
                "question_count": len(item.questions),
                "path": f"question-packs/packs/{item.id}.json",
            }
            for item in REFERENCE_QUESTION_PACKS
        ],
    }
    for template in REFERENCE_TEMPLATES.templates:
        documents[f"templates/{template.id}.json"] = template.to_dict()
    for task in UNIVERSAL_DAG_ARENA.tasks:
        documents[f"arena/{task.id}.json"] = task.to_dict()

    documents["arena/index.json"] = UNIVERSAL_DAG_ARENA.to_dict()

    for bundle in REFERENCE_BENCHMARKS:
        root = f"benchmarks/{bundle.id}"
        documents[f"{root}/suite.json"] = bundle.definition.suite.to_dict()
        documents[f"{root}/task-contract.json"] = bundle.definition.task_contract.to_dict()
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
            {
                "id": ENGINEERING_SHOWCASE_NODE_PACK.id,
                "version": ENGINEERING_SHOWCASE_NODE_PACK.version,
                "digest": ENGINEERING_SHOWCASE_NODE_PACK.digest,
                "path": "nodepacks/engineering-showcases/manifest.json",
                "node_count": len(SHOWCASE_NODES),
                "descriptor_count": 0,
                "embedding_record_count": 0,
            },
            {
                "id": DATA_SCIENCE_LIFECYCLE_NODE_PACK.id,
                "version": DATA_SCIENCE_LIFECYCLE_NODE_PACK.version,
                "digest": DATA_SCIENCE_LIFECYCLE_NODE_PACK.digest,
                "path": "nodepacks/data-science-lifecycle/manifest.json",
                "node_count": len(DATA_SCIENCE_NODES),
                "descriptor_count": 0,
                "embedding_record_count": 0,
            },
            {
                "id": INTERROGATION_NODE_PACK.id,
                "version": INTERROGATION_NODE_PACK.version,
                "digest": INTERROGATION_NODE_PACK.digest,
                "path": "nodepacks/semantic-interrogation/manifest.json",
                "node_count": len(INTERROGATION_NODE_SPECS),
                "descriptor_count": len(INTERROGATION_DESCRIPTORS),
                "embedding_record_count": 0,
            },
        ],
        "harnesses": [
            {
                "id": DUECARE_HARNESS_BUNDLE.id,
                "version": DUECARE_HARNESS_BUNDLE.version,
                "digest": DUECARE_HARNESS_BUNDLE.digest,
                "path": "harnesses/duecare-example.json",
                "graph_count": len(DUECARE_HARNESS_BUNDLE.graphs),
                "evidence_path": "harnesses/duecare-evidence-example.json",
                "evidence_digest": DUECARE_HARNESS_EVIDENCE.digest,
                "atomic_judgment_count": len(DUECARE_HARNESS_EVIDENCE.atomic_judgments),
                "panel_count": len(DUECARE_HARNESS_EVIDENCE.panels),
            }
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
        "agent_bench": {
            "path": "agent-bench/index.json",
            "task_count": len(REFERENCE_AGENT_TASKS),
            "suite_count": 2,
            "reference_smoke_trials": reference_agent_suite.total_trials,
            "sealed_payloads_published": False,
        },
        "question_packs": {
            "path": "question-packs/index.json",
            "concept_count": len(REFERENCE_CONCEPTS),
            "pack_count": len(REFERENCE_QUESTION_PACKS),
            "question_count": len(REFERENCE_QUESTIONS),
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
    "data_science_registry_capabilities",
    "example_registry_capabilities",
    "extended_registry_capabilities",
    "reference_registry_capabilities",
    "interrogation_registry_capabilities",
    "showcase_registry_capabilities",
    "standard_library_registry_capabilities",
    "write_catalog",
]
