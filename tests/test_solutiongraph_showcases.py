from __future__ import annotations

from dataclasses import replace

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry as SchemaRegistry
from referencing import Resource

from solutiongraph.catalog import catalog_documents
from solutiongraph.examples.showcase_tasks import (
    DUECARE_HARNESS_BUNDLE,
    SHOWCASE_EXAMPLE_TASKS,
    SHOWCASE_NODES,
    SHOWCASE_REGISTRY,
)
from solutiongraph.examples.tasks import run_example
from solutiongraph.harnessing import HarnessFlow
from solutiongraph.schemas import SCHEMA_NAMES, load_all_schemas
from solutiongraph.task_categories import (
    COMMON_DAG_TASK_CATEGORIES,
    DEFAULT_TASK_CATEGORY_REGISTRY,
)

_SCHEMAS = load_all_schemas()
_SCHEMA_REGISTRY = SchemaRegistry().with_resources(
    (schema["$id"], Resource.from_contents(schema))
    for schema in _SCHEMAS.values()
)


def _validate_wire(schema_name: str, payload: object) -> None:
    errors = sorted(
        Draft202012Validator(
            _SCHEMAS[schema_name], registry=_SCHEMA_REGISTRY
        ).iter_errors(payload),
        key=lambda error: tuple(error.path),
    )
    assert not errors, "; ".join(error.message for error in errors)


def test_engineering_showcase_pack_has_seven_executable_candidate_comparisons():
    assert len(SHOWCASE_EXAMPLE_TASKS) == 7
    assert len(SHOWCASE_NODES) == len(SHOWCASE_REGISTRY.candidates) == 82
    for example in SHOWCASE_EXAMPLE_TASKS:
        space, plans = example.compile()
        assert len(plans) == 2
        assert len(space.decisions) == (
            len(example.program.slots) * len(SHOWCASE_REGISTRY.candidates)
        )
        result = run_example(example.id, route="all")
        assert [receipt["accepted"] for receipt in result["experiment"]["receipts"]] == [
            False,
            True,
        ]


def test_duecare_harness_bundle_separates_authority_and_seals_outer_feedback():
    assert DUECARE_HARNESS_BUNDLE.validate() == []
    assert len(DUECARE_HARNESS_BUNDLE.graphs) == 6
    assert set(DUECARE_HARNESS_BUNDLE.development_case_ids).isdisjoint(
        DUECARE_HARNESS_BUNDLE.holdout_case_ids
    )
    firewall = next(
        flow
        for flow in DUECARE_HARNESS_BUNDLE.flows
        if flow.artifact_class == "artifact.hidden-outer-feedback"
    )
    assert firewall.exposure == "deny"


def test_duecare_harness_rejects_outer_feedback_leakage_and_hidden_case_exposure():
    flows = tuple(
        replace(flow, exposure="aggregate")
        if flow.artifact_class == "artifact.hidden-outer-feedback"
        else flow
        for flow in DUECARE_HARNESS_BUNDLE.flows
    )
    assert any(
        "deny-only feedback firewall" in problem
        for problem in replace(DUECARE_HARNESS_BUNDLE, flows=flows).validate()
    )

    leaking = HarnessFlow(
        "graph.duecare-outer",
        "graph.duecare-solution",
        "artifact.hidden-holdout-cases",
        "full",
        "This illegal flow leaks hidden cases to a candidate-visible graph.",
    )
    problems = replace(
        DUECARE_HARNESS_BUNDLE,
        flows=(*DUECARE_HARNESS_BUNDLE.flows, leaking),
    ).validate()
    assert any("hidden artifacts cannot be fully exposed" in problem for problem in problems)

    no_promotion = replace(
        DUECARE_HARNESS_BUNDLE,
        graphs=tuple(
            graph
            for graph in DUECARE_HARNESS_BUNDLE.graphs
            if "harness.approve-promotion" not in graph.authorities
        ),
    )
    assert any(
        "harness.approve-promotion" in problem for problem in no_promotion.validate()
    )


def test_showcase_harness_wire_contract_and_catalog_projection_are_strict():
    assert "harness-bundle.schema.json" in SCHEMA_NAMES
    schema = load_all_schemas()["harness-bundle.schema.json"]
    assert schema["additionalProperties"] is False
    _validate_wire("harness-bundle.schema.json", DUECARE_HARNESS_BUNDLE.to_dict())
    documents = catalog_documents()
    assert documents["harnesses/duecare-example.json"] == (DUECARE_HARNESS_BUNDLE.to_dict())
    assert documents["nodepacks/engineering-showcases/registry.json"] == (
        SHOWCASE_REGISTRY.to_dict()
    )
    assert documents["index.json"]["harnesses"][0]["graph_count"] == 6


def test_common_dag_registry_is_open_but_seeds_ninety_five_composable_categories():
    assert len(COMMON_DAG_TASK_CATEGORIES) == 95
    assert DEFAULT_TASK_CATEGORY_REGISTRY.validate() == []
    geotemporal = DEFAULT_TASK_CATEGORY_REGISTRY.get("dag.integrate.enrich.geotemporal")
    assert set(geotemporal.parent_ids) == {
        "dag.integrate.enrich.geospatial",
        "dag.integrate.enrich.temporal",
    }
    assert {
        "dag.generate.synthetic.tabular",
        "dag.generate.synthetic.text",
        "dag.generate.synthetic.adversarial",
        "dag.learn.reinforcement",
        "dag.evaluate.judge",
        "dag.serve.frontend",
        "dag.serve.backend",
        "dag.serve.plugin",
    }.issubset({category.id for category in COMMON_DAG_TASK_CATEGORIES})


@pytest.mark.parametrize(
    "example_id",
    ("geotemporal-enrichment", "duecare-llm-evaluation-harness"),
)
def test_boundary_showcases_execute_in_the_subprocess_lifecycle_adapter(example_id):
    result = run_example(example_id, route="all", runtime="subprocess")
    assert [receipt["accepted"] for receipt in result["experiment"]["receipts"]] == [
        False,
        True,
    ]
