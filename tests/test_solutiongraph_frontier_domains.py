from __future__ import annotations

import pytest

from solutiongraph.arena import UNIVERSAL_DAG_ARENA
from solutiongraph.catalog import catalog_documents
from solutiongraph.examples.frontier_tasks import (
    DOMAIN_OPERATIONS,
    FRONTIER_CANDIDATES,
    FRONTIER_EXAMPLE_TASKS,
    FRONTIER_NODES,
    FRONTIER_REGISTRY,
)
from solutiongraph.examples.tasks import run_example
from solutiongraph.pack_library import FRONTIER_DOMAIN_NODE_PACK


def test_frontier_pack_closes_seven_domains_with_two_candidates_per_operation():
    assert len(FRONTIER_EXAMPLE_TASKS) == len(DOMAIN_OPERATIONS) == 7
    assert len(FRONTIER_NODES) == len(FRONTIER_CANDIDATES) == 70
    assert len(FRONTIER_REGISTRY.nodes) == len(FRONTIER_REGISTRY.candidates) == 70
    assert all(node.validate() == [] for node in FRONTIER_NODES)
    node_map = FRONTIER_REGISTRY.node_map()
    assert all(
        candidate.validate(node_map[(candidate.node_id, candidate.node_version)]) == []
        for candidate in FRONTIER_CANDIDATES
    )
    assert FRONTIER_DOMAIN_NODE_PACK.validate() == []
    assert FRONTIER_DOMAIN_NODE_PACK.node_spec_digests == tuple(
        node.digest for node in FRONTIER_NODES
    )


@pytest.mark.parametrize("example", FRONTIER_EXAMPLE_TASKS, ids=lambda item: item.id)
def test_each_frontier_domain_runs_a_rejected_control_and_accepted_reference(example):
    space, plans = example.compile()
    assert len(example.program.slots) == 5
    assert space.route_count_upper_bound == 32
    assert len(plans) == 2
    assert all(len(space.choices_for(slot.id)) == 2 for slot in example.program.slots)

    report = run_example(example.id, route="all")
    receipts = report["experiment"]["receipts"]
    assert [receipt["accepted"] for receipt in receipts] == [False, True]
    assert [route.expected_accepted for route in example.routes] == [False, True]
    assert all(receipt["verification_details"]["claim_boundary"] for receipt in receipts)


@pytest.mark.parametrize(
    "example_id",
    (
        "defensive-cyber-investigation",
        "video-media-assurance",
        "robotics-safety-simulation",
    ),
)
def test_frontier_reference_routes_execute_in_isolated_subprocesses(example_id):
    report = run_example(example_id, route="reference", runtime="subprocess")
    receipt = report["execution"]["receipt"]
    assert receipt["accepted"]
    assert {node["isolation"] for node in receipt["node_receipts"]} == {"subprocess"}


def test_frontier_pack_and_arena_bindings_are_catalogued():
    documents = catalog_documents()
    assert documents["nodepacks/frontier-domains/manifest.json"] == (
        FRONTIER_DOMAIN_NODE_PACK.to_dict()
    )
    assert documents["nodepacks/frontier-domains/registry.json"] == (FRONTIER_REGISTRY.to_dict())
    index_entry = next(
        item
        for item in documents["index.json"]["node_packs"]
        if item["id"] == FRONTIER_DOMAIN_NODE_PACK.id
    )
    assert index_entry["node_count"] == 70

    mapping = {
        "arena.defensive-cyber-investigation": "defensive-cyber-investigation",
        "arena.video-media-assurance": "video-media-assurance",
        "arena.three-d-asset-assurance": "three-d-asset-assurance",
        "arena.game-build-playtest": "gameplay-replay-and-balance",
        "arena.robotics-control-assurance": "robotics-safety-simulation",
        "arena.iot-fleet-assurance": "iot-telemetry-assurance",
        "arena.digital-twin-validation": "digital-twin-validation",
    }
    for task_id, example_id in mapping.items():
        task = UNIVERSAL_DAG_ARENA.get(task_id)
        assert task.readiness == "executable_fixture"
        assert task.executable_example_ids == (example_id,)
