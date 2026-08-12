from __future__ import annotations

import pytest

from solutiongraph.catalog import catalog_documents
from solutiongraph.examples.data_science_tasks import (
    DATA_SCIENCE_CANDIDATES,
    DATA_SCIENCE_EXAMPLE_TASKS,
    DATA_SCIENCE_NODE_DEFINITIONS,
    DATA_SCIENCE_NODES,
    DATA_SCIENCE_REGISTRY,
    PIPELINE_OPERATIONS,
)
from solutiongraph.examples.tasks import run_example
from solutiongraph.pack_library import DATA_SCIENCE_LIFECYCLE_NODE_PACK


def test_data_science_pack_exposes_sixty_valid_nodes_and_three_candidates_per_slot():
    assert len(DATA_SCIENCE_EXAMPLE_TASKS) == 10
    assert len(DATA_SCIENCE_NODE_DEFINITIONS) == len(DATA_SCIENCE_NODES) == 60
    assert len(DATA_SCIENCE_CANDIDATES) == len(DATA_SCIENCE_REGISTRY.candidates) == 180
    assert all(definition.validate() == [] for definition in DATA_SCIENCE_NODE_DEFINITIONS)
    node_map = DATA_SCIENCE_REGISTRY.node_map()
    assert all(
        candidate.validate(node_map[(candidate.node_id, candidate.node_version)]) == []
        for candidate in DATA_SCIENCE_CANDIDATES
    )
    assert DATA_SCIENCE_LIFECYCLE_NODE_PACK.validate() == []


@pytest.mark.parametrize("example", DATA_SCIENCE_EXAMPLE_TASKS, ids=lambda item: item.id)
def test_each_data_science_pipeline_admits_729_routes_and_executes_four_evidence_routes(example):
    space, plans = example.compile()
    assert space.route_count_upper_bound == 729
    assert len(plans) == 4
    assert all(len(space.choices_for(slot.id)) == 3 for slot in example.program.slots)

    report = run_example(example.id, route="all")
    receipts = report["experiment"]["receipts"]
    assert [receipt["accepted"] for receipt in receipts] == [False, True, True, True]
    assert [route.expected_accepted for route in example.routes] == [False, True, True, True]


def test_accepted_routes_use_distinct_and_composable_stage_strategies():
    robust = run_example("robust-regression-and-conformal", route="robust-reference")
    alternate = run_example("robust-regression-and-conformal", route="alternate-reference")
    hybrid = run_example("robust-regression-and-conformal", route="hybrid-reference")

    robust_methods = robust["execution"]["outputs"]["result"]["methods"]
    alternate_methods = alternate["execution"]["outputs"]["result"]["methods"]
    hybrid_methods = hybrid["execution"]["outputs"]["result"]["methods"]
    assert robust_methods != alternate_methods
    assert set(hybrid_methods.values()).intersection(robust_methods.values())
    assert set(hybrid_methods.values()).intersection(alternate_methods.values())
    assert robust["execution"]["receipt"]["accepted"]
    assert alternate["execution"]["receipt"]["accepted"]
    assert hybrid["execution"]["receipt"]["accepted"]


@pytest.mark.parametrize(
    "example_id",
    ("dataset-profiling-and-drift", "model-release-monitoring-and-rollback"),
)
def test_data_science_boundary_examples_run_in_isolated_subprocesses(example_id):
    report = run_example(example_id, route="hybrid-reference", runtime="subprocess")
    receipt = report["execution"]["receipt"]
    assert receipt["accepted"]
    assert {node["isolation"] for node in receipt["node_receipts"]} == {"subprocess"}


def test_data_science_pack_is_projected_into_the_portable_catalog():
    documents = catalog_documents()
    assert documents["nodepacks/data-science-lifecycle/manifest.json"] == (
        DATA_SCIENCE_LIFECYCLE_NODE_PACK.to_dict()
    )
    assert documents["nodepacks/data-science-lifecycle/registry.json"] == (
        DATA_SCIENCE_REGISTRY.to_dict()
    )
    index_entry = next(
        item
        for item in documents["index.json"]["node_packs"]
        if item["id"] == DATA_SCIENCE_LIFECYCLE_NODE_PACK.id
    )
    assert index_entry["node_count"] == 60
    assert set(PIPELINE_OPERATIONS) == {
        document.removeprefix("arena/arena.").removesuffix(".json")
        for document in documents
        if document.startswith("arena/arena.")
        and document.removeprefix("arena/arena.").removesuffix(".json") in PIPELINE_OPERATIONS
    }
