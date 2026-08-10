from __future__ import annotations

import pytest

from solutiongraph import (
    EarlyStoppingPolicy,
    MetricObservation,
    SuccessiveHalvingPolicy,
    TrialObservation,
    plan_successive_halving,
    sha256_digest,
    should_stop_early,
)


def policy(direction: str = "maximize") -> SuccessiveHalvingPolicy:
    return SuccessiveHalvingPolicy(
        id="experiment.successive-halving",
        metric="metric.validation-quality",
        direction=direction,
        min_resource=1,
        max_resource=27,
        reduction_factor=3,
    )


def observation(
    name: str,
    metric: float,
    *,
    accepted: bool = True,
    complete: bool = True,
    resource: float = 3,
) -> TrialObservation:
    return TrialObservation(
        sha256_digest(name),
        resource,
        metric,
        accepted,
        complete,
        "failure.contract" if not accepted else "",
    )


def test_successive_halving_promotes_the_top_rung_and_explains_every_plan():
    observations = tuple(
        observation(f"plan-{index}", metric)
        for index, metric in enumerate((0.40, 0.91, 0.73, 0.82, 0.65, 0.10))
    )
    decisions = plan_successive_halving(observations, policy())

    assert len(decisions) == len(observations)
    promoted = [decision for decision in decisions if decision.promoted]
    assert len(promoted) == 2
    assert {decision.metric for decision in promoted} == {0.91, 0.82}
    assert {decision.to_resource for decision in decisions} == {9}
    assert all(decision.reason for decision in decisions)


def test_failed_incomplete_and_max_resource_trials_are_never_promoted():
    observations = (
        observation("accepted", 0.5),
        observation("failed", 1.0, accepted=False),
        observation("incomplete", 2.0, complete=False),
    )
    decisions = plan_successive_halving(observations, policy())
    by_digest = {decision.plan_digest: decision for decision in decisions}
    assert by_digest[sha256_digest("accepted")].promoted
    assert "acceptance contract failed" in by_digest[sha256_digest("failed")].reason
    assert "incomplete" in by_digest[sha256_digest("incomplete")].reason

    at_max = tuple(observation(f"max-{index}", index, resource=27) for index in range(3))
    assert not any(decision.promoted for decision in plan_successive_halving(at_max, policy()))


def test_successive_halving_is_deterministic_for_minimization_and_ties():
    observations = (
        observation("b", 2.0),
        observation("a", 1.0),
        observation("c", 1.0),
    )
    decisions = plan_successive_halving(observations, policy("minimize"))
    ranked = sorted(
        (decision for decision in decisions if decision.rank is not None),
        key=lambda decision: decision.rank,
    )
    assert [decision.metric for decision in ranked] == [1.0, 1.0, 2.0]
    assert ranked[0].plan_digest < ranked[1].plan_digest


def test_promotion_requires_one_resource_rung_and_unique_plan_results():
    with pytest.raises(ValueError, match="one resource rung"):
        plan_successive_halving(
            (observation("a", 1.0, resource=1), observation("b", 2.0, resource=3)),
            policy(),
        )
    duplicate = observation("same", 1.0)
    with pytest.raises(ValueError, match="one result per plan"):
        plan_successive_halving((duplicate, duplicate), policy())


def test_early_stopping_waits_for_minimum_resource_and_declared_patience():
    stopping = EarlyStoppingPolicy(
        metric="metric.validation-quality",
        direction="maximize",
        patience=3,
        min_delta=0.01,
        min_resource=4,
    )
    before_minimum = (
        MetricObservation(1, 0.8),
        MetricObservation(2, 0.805),
        MetricObservation(3, 0.804),
    )
    decision = should_stop_early(before_minimum, stopping)
    assert not decision.stop
    assert "minimum resource" in decision.reason

    after_patience = before_minimum + (MetricObservation(4, 0.803),)
    decision = should_stop_early(after_patience, stopping)
    assert decision.stop
    assert decision.stale_observations == 3

    improved = after_patience + (MetricObservation(5, 0.83),)
    assert not should_stop_early(improved, stopping).stop


def test_early_stopping_rejects_reordered_resource_history():
    stopping = EarlyStoppingPolicy("metric.loss", "minimize", patience=2)
    with pytest.raises(ValueError, match="non-decreasing"):
        should_stop_early(
            (MetricObservation(2, 1.0), MetricObservation(1, 0.9)),
            stopping,
        )
