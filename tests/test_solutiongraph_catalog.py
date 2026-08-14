from __future__ import annotations

import json
from pathlib import Path

import pytest

from solutiongraph.agent_bench import REFERENCE_AGENT_TASKS
from solutiongraph.arena import UNIVERSAL_DAG_ARENA
from solutiongraph.benchmark_library import REFERENCE_BENCHMARKS
from solutiongraph.catalog import catalog_documents, write_catalog
from solutiongraph.design_atlas import (
    REFERENCE_DESIGN_PACKS,
    REFERENCE_DESIGN_QUESTIONS,
    REFERENCE_SOURCES,
    REFERENCE_TASK_ARCHETYPES,
    REFERENCE_TECHNIQUES,
    TECHNIQUES_BY_PHASE,
)
from solutiongraph.design_atlas.node_pack import (
    DESIGN_ATLAS_DESCRIPTORS,
    DESIGN_ATLAS_NODE_SPECS,
)
from solutiongraph.examples.data_science_tasks import DATA_SCIENCE_NODES
from solutiongraph.examples.extended_tasks import EXTENDED_NODES
from solutiongraph.examples.frontier_tasks import FRONTIER_NODES
from solutiongraph.examples.showcase_tasks import SHOWCASE_NODES
from solutiongraph.examples.tasks import NODES as EXAMPLE_NODES
from solutiongraph.integrations import REFERENCE_INTEGRATION_ADAPTERS
from solutiongraph.interrogation.node_pack import (
    INTERROGATION_DESCRIPTORS,
    INTERROGATION_NODE_SPECS,
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
    fetch_http_json,
    identity_json,
    parse_json,
    require_keys,
)
from solutiongraph.specialized import (
    REFERENCE_SPECIALIZED_PACK_REGISTRY,
    REFERENCE_SPECIALIZED_PACKS,
)
from solutiongraph.stdlib_pack import (
    STANDARD_LIBRARY_DESCRIPTORS,
    STANDARD_LIBRARY_NODE_SPECS,
)
from solutiongraph.template_library import REFERENCE_TEMPLATES
from solutiongraph.universal import (
    REFERENCE_DOMAIN_PACKS,
    REFERENCE_ENGINEERING_QUESTIONS,
    REFERENCE_OBLIGATIONS,
)


def test_reference_nodes_execute_and_all_contracts_and_descriptors_validate():
    value = {"id": 7, "name": "example"}
    assert identity_json(value) is value
    assert parse_json('{"id": 7}') == {"id": 7}
    assert require_keys(value, ("id",)) == value
    with pytest.raises(TypeError, match="JSON object"):
        require_keys(7, ("id",))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="GET or HEAD"):
        fetch_http_json({"url": "https://example.invalid", "method": "POST"})
    assert all(node.validate() == [] for node in REFERENCE_NODE_SPECS)
    assert all(
        descriptor.validate(node) == []
        for node, descriptor in zip(REFERENCE_NODE_SPECS, REFERENCE_DESCRIPTORS, strict=True)
    )
    assert len(REFERENCE_REGISTRY.nodes) == 5


def test_reference_templates_cover_unrelated_domains_and_atomic_obligations():
    assert REFERENCE_TEMPLATES.validate() == []
    assert len(REFERENCE_TEMPLATES.templates) == 42
    assert sum(len(template.program.slots) for template in REFERENCE_TEMPLATES.templates) == 733
    assert {
        "template.kaggle-tabular",
        "template.data-quality",
        "template.qa-engineering",
        "template.login-system",
        "template.deployment-release",
        "template.shipping-notifications",
        "template.knowledge-retrieval",
        "template.database-migration",
        "template.observability-sre",
    }.issubset({template.id for template in REFERENCE_TEMPLATES.templates})


def test_catalogue_projection_is_deterministic_indexed_and_has_no_fake_embeddings():
    first = catalog_documents()
    second = catalog_documents()
    assert first == second
    expected = (
        (3 + 5 + 5)
        + (3 + len(EXAMPLE_NODES))
        + (3 + len(EXTENDED_NODES))
        + (3 + len(STANDARD_LIBRARY_NODE_SPECS) + len(STANDARD_LIBRARY_DESCRIPTORS))
        + (3 + len(SHOWCASE_NODES))
        + (3 + len(DATA_SCIENCE_NODES))
        + (3 + len(FRONTIER_NODES))
        + (3 + len(INTERROGATION_NODE_SPECS) + len(INTERROGATION_DESCRIPTORS))
        + (3 + len(DESIGN_ATLAS_NODE_SPECS) + len(DESIGN_ATLAS_DESCRIPTORS))
        + 1
        + len(REFERENCE_CONCEPTS)
        + len(REFERENCE_QUESTION_PACKS)
        + len(REFERENCE_QUESTIONS)
        + 1
        + len(REFERENCE_SOURCES)
        + len(REFERENCE_TECHNIQUES)
        + len(REFERENCE_DESIGN_PACKS)
        + len(REFERENCE_DESIGN_QUESTIONS)
        + len(REFERENCE_TASK_ARCHETYPES)
        + len(TECHNIQUES_BY_PHASE)
        + 1
        + 1
        + len(REFERENCE_AGENT_TASKS)
        + 3
        + len(REFERENCE_TEMPLATES.templates)
        + len(UNIVERSAL_DAG_ARENA.tasks)
        + 1
        + sum(
            3 + len(bundle.definition.task_cases) + len(bundle.baseline_plans)
            for bundle in REFERENCE_BENCHMARKS
        )
        + 1
        + 1
        + len(REFERENCE_OBLIGATIONS)
        + len(REFERENCE_DOMAIN_PACKS)
        + len(REFERENCE_ENGINEERING_QUESTIONS)
        + len(REFERENCE_INTEGRATION_ADAPTERS)
        + 3
        + 3
        + len(REFERENCE_SPECIALIZED_PACKS)
    )
    assert len(first) == expected
    index = first["index.json"]
    assert len(index["templates"]) == 42
    assert index["arena"] == {
        "path": "arena/index.json",
        "task_count": 63,
        "executable_fixture_count": 45,
    }
    assert [item["node_count"] for item in index["node_packs"]] == [
        5,
        len(STANDARD_LIBRARY_NODE_SPECS),
        len(EXAMPLE_NODES),
        len(EXTENDED_NODES),
        len(SHOWCASE_NODES),
        len(DATA_SCIENCE_NODES),
        len(FRONTIER_NODES),
        len(INTERROGATION_NODE_SPECS),
        len(DESIGN_ATLAS_NODE_SPECS),
    ]
    assert index["question_packs"] == {
        "path": "question-packs/index.json",
        "concept_count": len(REFERENCE_CONCEPTS),
        "pack_count": len(REFERENCE_QUESTION_PACKS),
        "question_count": len(REFERENCE_QUESTIONS),
    }
    assert index["design_atlas"] == {
        "path": "design-atlas/index.json",
        "technique_count": 618,
        "pack_count": 28,
        "question_count": 112,
        "task_archetype_count": 31,
        "machine_maturity_floor": "C1",
    }
    assert index["benchmarks"] == {
        "path": "benchmarks/index.json",
        "benchmark_count": 6,
        "task_case_count": 24,
        "solution_pack_count": 6,
    }
    assert index["agent_bench"] == {
        "path": "agent-bench/index.json",
        "task_count": 10,
        "suite_count": 2,
        "reference_smoke_trials": 20,
        "sealed_payloads_published": False,
    }
    assert index["specialized_packages"] == {
        "path": "specialized-packs/index.json",
        "registry_digest": REFERENCE_SPECIALIZED_PACK_REGISTRY.digest,
        "pack_count": 26,
        "recipe_count": 89,
        "profiler_feature_count": 127,
        "metric_count": 118,
        "gate_count": 55,
    }
    assert first["agent-bench/index.json"]["sealed_payloads_published"] is False
    assert all(
        f"agent-bench/tasks/{bundle.spec.id}.json" in first
        for bundle in REFERENCE_AGENT_TASKS
    )
    assert index["node_packs"][0]["embedding_record_count"] == 0
    capabilities = first["nodepacks/reference-core/registry-capabilities.json"]
    assert [mode["id"] for mode in capabilities["query_modes"]] == [
        "exact",
        "lexical",
        "enumeration",
    ]
    assert capabilities["embedding_spaces"] == []
    example_capabilities = first["nodepacks/real-world-examples/registry-capabilities.json"]
    assert [mode["id"] for mode in example_capabilities["query_modes"]] == [
        "exact",
        "enumeration",
    ]
    assert example_capabilities["embedding_spaces"] == []


def test_catalogue_export_round_trips_every_generated_document(tmp_path):
    written = write_catalog(tmp_path)
    expected = catalog_documents()
    assert len(written) == len(expected)
    assert {str(path.relative_to(tmp_path)) for path in written} == set(expected)
    for relative, document in expected.items():
        assert json.loads((tmp_path / relative).read_text(encoding="utf-8")) == document


def test_catalogue_explorer_is_self_contained_and_exposes_every_reference_template():
    html = (Path(__file__).parents[1] / "examples" / "catalog-template-explorer.html").read_text(
        encoding="utf-8"
    )
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "ung-catalog-explorer" in html
    assert "ung-domain-select" in html
    assert all(template.id in html for template in REFERENCE_TEMPLATES.templates)
    assert all(node.id in html for node in REFERENCE_NODE_SPECS)
    assert all(node.id in html for node in EXAMPLE_NODES)
    assert all(node.id in html for node in EXTENDED_NODES)
    assert all(node.id in html for node in SHOWCASE_NODES)
    assert all(node.id in html for node in FRONTIER_NODES)
    assert all(node.id in html for node in STANDARD_LIBRARY_NODE_SPECS)
    assert all(node.description in html for node in REFERENCE_NODE_SPECS)
    assert all(
        slot.id in html and slot.purpose in html
        for template in REFERENCE_TEMPLATES.templates
        for slot in template.program.slots
    )


def test_universal_dag_explorer_is_linear_complete_and_self_contained():
    html = (Path(__file__).parents[1] / "examples" / "universal-dag-explorer.html").read_text(
        encoding="utf-8"
    )
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert '<script id="codex-visualization-floating-ui-core"' not in html
    assert html.count('class="udx-stage"') == 3
    assert html.count('class="udx-step"') == 9
    assert html.count('class="udx-node"') == 27
    assert "Every step. Every compatible node. Every tested route." in html
    assert "Execution is monotonic left to right" in html
    assert all(f'data-route="{route}"' in html for route in ("champion", "fallback", "control"))
