"""Reusable multi-objective ranking for receipt-derived route aggregates.

This module deliberately operates on evidence after execution.  It does not
participate in compiler admission, route search, or plan freezing.  Keeping the
normalization and gate logic here lets solvers, topology experiments, and
external harnesses compare the same immutable observations without copying a
private scoring implementation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from solutiongraph.evidence import Objective, RouteAggregate, pareto_front


@dataclass(frozen=True)
class RankedAggregate:
    """One evidence aggregate ranked under an explicit objective projection."""

    rank: int
    plan_digest: str
    runs: int
    accepted_runs: int
    acceptance_rate: float
    metric_means: Mapping[str, float]
    metric_variances: Mapping[str, float]
    failure_classes: Mapping[str, int]
    weighted_score: float
    meets_acceptance_gate: bool
    meets_objective_constraints: bool
    pareto: bool

    @property
    def eligible(self) -> bool:
        return self.meets_acceptance_gate and self.meets_objective_constraints

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "plan_digest": self.plan_digest,
            "runs": self.runs,
            "accepted_runs": self.accepted_runs,
            "acceptance_rate": self.acceptance_rate,
            "metric_means": dict(self.metric_means),
            "metric_variances": dict(self.metric_variances),
            "failure_classes": dict(self.failure_classes),
            "weighted_score": self.weighted_score,
            "meets_acceptance_gate": self.meets_acceptance_gate,
            "meets_objective_constraints": self.meets_objective_constraints,
            "pareto": self.pareto,
        }


def rank_route_aggregates(
    aggregates: Iterable[RouteAggregate],
    objectives: tuple[Objective, ...],
    *,
    minimum_acceptance_rate: float = 1.0,
) -> tuple[RankedAggregate, ...]:
    """Rank routes without hiding hard gates or multi-objective tradeoffs.

    The weighted score is a user-selected projection over min/max-normalized
    eligible observations.  The Pareto flag remains available so callers do
    not have to treat that scalar projection as objective truth.
    """

    aggregates = tuple(aggregates)
    problems: list[str] = []
    if not 0.0 <= minimum_acceptance_rate <= 1.0:
        problems.append("minimum_acceptance_rate must be between zero and one")
    if not objectives:
        problems.append("objectives must not be empty")
    metrics = [objective.metric for objective in objectives]
    if len(metrics) != len(set(metrics)):
        problems.append("objective metrics must be unique")
    for objective in objectives:
        problems.extend(objective.validate())
    if problems:
        raise ValueError("invalid route ranking configuration: " + "; ".join(problems))

    constraint_ok = {
        aggregate.plan_digest: all(
            objective.metric in aggregate.metric_means
            and (
                objective.hard_minimum is None
                or aggregate.metric_means[objective.metric] >= objective.hard_minimum
            )
            and (
                objective.hard_maximum is None
                or aggregate.metric_means[objective.metric] <= objective.hard_maximum
            )
            for objective in objectives
        )
        for aggregate in aggregates
    }
    eligible = tuple(
        aggregate
        for aggregate in aggregates
        if aggregate.acceptance_rate >= minimum_acceptance_rate
        and constraint_ok[aggregate.plan_digest]
    )
    bounds: dict[str, tuple[float, float]] = {}
    for objective in objectives:
        values = [
            aggregate.metric_means[objective.metric]
            for aggregate in eligible
            if objective.metric in aggregate.metric_means
        ]
        if values:
            bounds[objective.metric] = (min(values), max(values))

    weight_total = sum(objective.weight for objective in objectives)
    pareto_digests = {aggregate.plan_digest for aggregate in pareto_front(aggregates, objectives)}
    unranked: list[RankedAggregate] = []
    for aggregate in aggregates:
        gate = aggregate.acceptance_rate >= minimum_acceptance_rate
        score_parts: list[tuple[float, float]] = []
        for objective in objectives:
            value = aggregate.metric_means.get(objective.metric)
            bound = bounds.get(objective.metric)
            if value is None or bound is None:
                normalized = 0.0
            elif bound[0] == bound[1]:
                normalized = 1.0
            elif objective.direction == "maximize":
                normalized = (value - bound[0]) / (bound[1] - bound[0])
            else:
                normalized = (bound[1] - value) / (bound[1] - bound[0])
            score_parts.append((objective.weight, normalized))
        score = (
            sum(weight * value for weight, value in score_parts) / weight_total
            if weight_total > 0
            else 0.0
        )
        if not gate or not constraint_ok[aggregate.plan_digest]:
            score = 0.0
        unranked.append(
            RankedAggregate(
                rank=0,
                plan_digest=aggregate.plan_digest,
                runs=aggregate.runs,
                accepted_runs=aggregate.accepted_runs,
                acceptance_rate=aggregate.acceptance_rate,
                metric_means=dict(aggregate.metric_means),
                metric_variances=dict(aggregate.metric_variances),
                failure_classes=dict(aggregate.failure_classes),
                weighted_score=score,
                meets_acceptance_gate=gate,
                meets_objective_constraints=constraint_ok[aggregate.plan_digest],
                pareto=aggregate.plan_digest in pareto_digests,
            )
        )
    ordered = sorted(
        unranked,
        key=lambda item: (
            not item.eligible,
            -item.weighted_score,
            -item.acceptance_rate,
            item.plan_digest,
        ),
    )
    return tuple(replace(item, rank=index) for index, item in enumerate(ordered, 1))


__all__ = ["RankedAggregate", "rank_route_aggregates"]
