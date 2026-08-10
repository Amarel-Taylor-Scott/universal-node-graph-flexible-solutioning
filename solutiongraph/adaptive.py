"""Inspectable multi-fidelity promotion and early-stopping primitives.

These policies allocate experiment resources after the compiler has produced
valid plans. They cannot admit a candidate, alter a frozen plan, or turn an
unaccepted outcome into a successful one.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite

from solutiongraph.model import DIGEST_RE, ID_RE


@dataclass(frozen=True)
class TrialObservation:
    plan_digest: str
    resource: float
    metric: float
    accepted: bool = True
    complete: bool = True
    failure_class: str = ""

    def validate(self, path: str = "observation") -> list[str]:
        problems: list[str] = []
        if not DIGEST_RE.fullmatch(self.plan_digest):
            problems.append(f"{path}.plan_digest must be a sha256 digest")
        if not isfinite(self.resource) or self.resource <= 0:
            problems.append(f"{path}.resource must be finite and positive")
        if not isfinite(self.metric):
            problems.append(f"{path}.metric must be finite")
        if self.failure_class and not ID_RE.fullmatch(self.failure_class):
            problems.append(f"{path}.failure_class must be a namespaced identifier")
        return problems


@dataclass(frozen=True)
class SuccessiveHalvingPolicy:
    id: str
    metric: str
    direction: str
    min_resource: float
    max_resource: float
    reduction_factor: int = 3
    min_survivors: int = 1
    require_accepted: bool = True

    def validate(self, path: str = "policy") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.metric):
            problems.append(f"{path}.id and metric must be namespaced identifiers")
        if self.direction not in ("maximize", "minimize"):
            problems.append(f"{path}.direction must be maximize or minimize")
        if (
            not isfinite(self.min_resource)
            or not isfinite(self.max_resource)
            or self.min_resource <= 0
            or self.max_resource < self.min_resource
        ):
            problems.append(f"{path} resource bounds are invalid")
        if self.reduction_factor < 2:
            problems.append(f"{path}.reduction_factor must be at least two")
        if self.min_survivors <= 0:
            problems.append(f"{path}.min_survivors must be positive")
        return problems


@dataclass(frozen=True)
class PromotionDecision:
    plan_digest: str
    metric: float
    from_resource: float
    to_resource: float
    promoted: bool
    rank: int | None
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_digest": self.plan_digest,
            "metric": self.metric,
            "from_resource": self.from_resource,
            "to_resource": self.to_resource,
            "promoted": self.promoted,
            "rank": self.rank,
            "reason": self.reason,
        }


def plan_successive_halving(
    observations: tuple[TrialObservation, ...],
    policy: SuccessiveHalvingPolicy,
) -> tuple[PromotionDecision, ...]:
    """Rank one completed resource rung and disclose every promotion decision."""
    problems = policy.validate()
    for index, observation in enumerate(observations):
        problems.extend(observation.validate(f"observations[{index}]"))
    if not observations:
        problems.append("observations must not be empty")
    digests = [observation.plan_digest for observation in observations]
    if len(digests) != len(set(digests)):
        problems.append("observations must contain one result per plan")
    resources = {observation.resource for observation in observations}
    if len(resources) > 1:
        problems.append("successive halving compares one resource rung at a time")
    if problems:
        raise ValueError("invalid promotion rung: " + "; ".join(problems))

    current_resource = observations[0].resource
    if current_resource < policy.min_resource or current_resource > policy.max_resource:
        raise ValueError("observation resource is outside the policy bounds")
    next_resource = min(
        policy.max_resource,
        current_resource * policy.reduction_factor,
    )
    eligible = tuple(
        observation
        for observation in observations
        if observation.complete and (observation.accepted or not policy.require_accepted)
    )
    reverse = policy.direction == "maximize"
    ranked = tuple(
        sorted(
            eligible,
            key=lambda observation: (
                -observation.metric if reverse else observation.metric,
                observation.plan_digest,
            ),
        )
    )
    rank_by_digest = {
        observation.plan_digest: index + 1 for index, observation in enumerate(ranked)
    }
    survivor_count = min(
        len(ranked),
        max(policy.min_survivors, ceil(len(ranked) / policy.reduction_factor)),
    )
    survivors = {observation.plan_digest for observation in ranked[:survivor_count]}

    decisions: list[PromotionDecision] = []
    for observation in sorted(observations, key=lambda item: item.plan_digest):
        rank = rank_by_digest.get(observation.plan_digest)
        if not observation.complete:
            reason = "not promoted: trial is incomplete"
            promoted = False
        elif policy.require_accepted and not observation.accepted:
            suffix = f" ({observation.failure_class})" if observation.failure_class else ""
            reason = "not promoted: acceptance contract failed" + suffix
            promoted = False
        elif current_resource >= policy.max_resource:
            reason = "not promoted: maximum resource already reached"
            promoted = False
        elif observation.plan_digest in survivors:
            reason = f"promoted: rank {rank} is within top {survivor_count}"
            promoted = True
        else:
            reason = f"not promoted: rank {rank} is outside top {survivor_count}"
            promoted = False
        decisions.append(
            PromotionDecision(
                plan_digest=observation.plan_digest,
                metric=observation.metric,
                from_resource=current_resource,
                to_resource=next_resource,
                promoted=promoted,
                rank=rank,
                reason=reason,
            )
        )
    return tuple(decisions)


@dataclass(frozen=True)
class MetricObservation:
    resource: float
    value: float
    accepted: bool = True


@dataclass(frozen=True)
class EarlyStoppingPolicy:
    metric: str
    direction: str
    patience: int
    min_delta: float = 0.0
    min_resource: float = 0.0

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.metric):
            problems.append("metric must be a namespaced identifier")
        if self.direction not in ("maximize", "minimize"):
            problems.append("direction must be maximize or minimize")
        if self.patience <= 0:
            problems.append("patience must be positive")
        if not isfinite(self.min_delta) or self.min_delta < 0:
            problems.append("min_delta must be finite and non-negative")
        if not isfinite(self.min_resource) or self.min_resource < 0:
            problems.append("min_resource must be finite and non-negative")
        return problems


@dataclass(frozen=True)
class EarlyStopDecision:
    stop: bool
    reason: str
    best_value: float | None
    stale_observations: int


def should_stop_early(
    history: tuple[MetricObservation, ...],
    policy: EarlyStoppingPolicy,
) -> EarlyStopDecision:
    """Apply a deterministic patience rule to ordered accepted observations."""
    problems = policy.validate()
    for index, observation in enumerate(history):
        if not isfinite(observation.resource) or observation.resource < 0:
            problems.append(f"history[{index}].resource must be finite and non-negative")
        if not isfinite(observation.value):
            problems.append(f"history[{index}].value must be finite")
    if any(
        history[index].resource < history[index - 1].resource for index in range(1, len(history))
    ):
        problems.append("history resources must be non-decreasing")
    if problems:
        raise ValueError("invalid early-stop history: " + "; ".join(problems))

    accepted = tuple(observation for observation in history if observation.accepted)
    if not accepted:
        return EarlyStopDecision(False, "no accepted metric observations", None, 0)
    best = accepted[0].value
    stale = 0
    for observation in accepted[1:]:
        improvement = (
            observation.value - best if policy.direction == "maximize" else best - observation.value
        )
        if improvement > policy.min_delta:
            best = observation.value
            stale = 0
        else:
            stale += 1
    if accepted[-1].resource < policy.min_resource:
        return EarlyStopDecision(
            False,
            "minimum resource has not been reached",
            best,
            stale,
        )
    stop = stale >= policy.patience
    return EarlyStopDecision(
        stop,
        (
            f"stop: no improvement greater than {policy.min_delta} for "
            f"{stale} accepted observations"
            if stop
            else f"continue: stale observations {stale}/{policy.patience}"
        ),
        best,
        stale,
    )
