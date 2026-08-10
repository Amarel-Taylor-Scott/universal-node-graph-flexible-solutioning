from __future__ import annotations

import json
from pathlib import Path

import pytest

from solutiongraph.catalog import catalog_documents, write_catalog
from solutiongraph.examples.tasks import NODES as EXAMPLE_NODES
from solutiongraph.reference_nodes import (
    REFERENCE_DESCRIPTORS,
    REFERENCE_NODE_SPECS,
    REFERENCE_REGISTRY,
    fetch_http_json,
    identity_json,
    parse_json,
    require_keys,
)
from solutiongraph.template_library import REFERENCE_TEMPLATES


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
        for node, descriptor in zip(
            REFERENCE_NODE_SPECS, REFERENCE_DESCRIPTORS, strict=True
        )
    )
    assert len(REFERENCE_REGISTRY.nodes) == 5


def test_reference_templates_cover_unrelated_domains_and_atomic_obligations():
    assert REFERENCE_TEMPLATES.validate() == []
    assert len(REFERENCE_TEMPLATES.templates) == 19
    assert sum(len(template.program.slots) for template in REFERENCE_TEMPLATES.templates) == 339
    assert {
        "template.kaggle-tabular",
        "template.data-quality",
        "template.qa-engineering",
        "template.login-system",
        "template.deployment-release",
        "template.shipping-notifications",
    }.issubset({template.id for template in REFERENCE_TEMPLATES.templates})


def test_catalogue_projection_is_deterministic_indexed_and_has_no_fake_embeddings():
    first = catalog_documents()
    second = catalog_documents()
    assert first == second
    assert len(first) == 3 + 5 + 5 + 3 + len(EXAMPLE_NODES) + 19 + 1
    index = first["index.json"]
    assert len(index["templates"]) == 19
    assert [item["node_count"] for item in index["node_packs"]] == [5, len(EXAMPLE_NODES)]
    assert index["node_packs"][0]["embedding_record_count"] == 0
    capabilities = first["nodepacks/reference-core/registry-capabilities.json"]
    assert [mode["id"] for mode in capabilities["query_modes"]] == [
        "exact",
        "lexical",
        "enumeration",
    ]
    assert capabilities["embedding_spaces"] == []
    example_capabilities = first[
        "nodepacks/real-world-examples/registry-capabilities.json"
    ]
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
    assert all(node.description in html for node in REFERENCE_NODE_SPECS)
    assert all(
        slot.id in html and slot.purpose in html
        for template in REFERENCE_TEMPLATES.templates
        for slot in template.program.slots
    )
