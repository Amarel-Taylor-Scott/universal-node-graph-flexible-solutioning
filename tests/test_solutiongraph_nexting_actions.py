from __future__ import annotations

from solutiongraph.nexting import (
    ExperimentRequest,
    GraphChangeRequest,
    OptimizationRequest,
    StopRequest,
    validate_action_payload,
)


def test_graph_change_payload_can_identify_each_supported_graph_action() -> None:
    for action_kind in (
        "next.mutate-graph",
        "next.propose-graph",
        "next.propose-subgraph",
        "next.propose-node",
        "next.replace-node",
    ):
        payload = GraphChangeRequest(
            action_kind=action_kind,
            change_kind="change.insert-obligation",
            target_ref="graph.test",
            operations=({"operation": "insert"},),
            hypothesis="The added obligation improves the declared objective.",
        )
        assert not validate_action_payload(action_kind, payload)


def test_optimization_and_experiment_aliases_remain_typed() -> None:
    configure = OptimizationRequest(
        action_kind="next.configure",
        target_ref="node.model",
        objective_ids=("metric.quality",),
        search_space_ref="space.model-parameters",
    )
    compare = ExperimentRequest(
        action_kind="next.compare",
        candidate_refs=("candidate.a", "candidate.b"),
        case_refs=("case.validation",),
        objective_ids=("metric.quality",),
    )
    assert not validate_action_payload("next.configure", configure)
    assert not validate_action_payload("next.compare", compare)


def test_pause_uses_terminal_payload_without_becoming_stop() -> None:
    pause = StopRequest(
        action_kind="next.pause",
        terminal_disposition="pause",
        reason="External evidence is not yet available.",
    )
    assert not validate_action_payload("next.pause", pause)
    assert validate_action_payload("next.stop", pause)
