"""Evidence-only learning for What-Is-Next allocation.

Beliefs may reorder or allocate proposal strategies.  They cannot change task
meaning, make an invalid graph valid, grant authority, or replace independent
execution and evaluation evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Any, Sequence

from solutiongraph.model import ID_RE, sha256_digest

LEARNING_MODEL_VERSION = "0.1"


@dataclass(frozen=True)
class FactorWeight:
    factor_kind: str
    factor_id: str
    mean_reward: float
    evidence_count: int
    uncertainty: float

    def validate(self) -> list[str]:
        problems: list[str] = []
        for label, value in (("factor_kind", self.factor_kind), ("factor_id", self.factor_id)):
            if not ID_RE.fullmatch(value):
                problems.append(f"{label} must be namespaced")
        if not isfinite(self.mean_reward):
            problems.append("mean_reward must be finite")
        if self.evidence_count < 0:
            problems.append("evidence_count must be non-negative")
        if not isfinite(self.uncertainty) or self.uncertainty < 0:
            problems.append("uncertainty must be finite and non-negative")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class StrategyEvidence:
    strategy_id: str
    action_kind: str
    reward: float
    accepted: bool
    context_policy_id: str = ""
    model_id: str = ""
    tags: tuple[str, ...] = ()
    receipt_id: str = ""

    def validate(self) -> list[str]:
        problems: list[str] = []
        for label, value in (("strategy_id", self.strategy_id), ("action_kind", self.action_kind)):
            if not ID_RE.fullmatch(value):
                problems.append(f"{label} must be namespaced")
        for label, value in (("context_policy_id", self.context_policy_id),
                             ("model_id", self.model_id), ("receipt_id", self.receipt_id)):
            if value and not ID_RE.fullmatch(value):
                problems.append(f"{label} must be empty or namespaced")
        if not isfinite(self.reward):
            problems.append("reward must be finite")
        if len(self.tags) != len(set(self.tags)) or any(not ID_RE.fullmatch(item) for item in self.tags):
            problems.append("tags must contain unique namespaced identifiers")
        return problems


# Earlier prototype name retained.
LearningObservation = StrategyEvidence


@dataclass(frozen=True)
class NextBeliefModel:
    revision: str = "untrained"
    factors: tuple[FactorWeight, ...] = ()
    exploration_scale: float = 0.25

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.revision.strip():
            problems.append("belief revision must not be empty")
        if not isfinite(self.exploration_scale) or self.exploration_scale < 0:
            problems.append("exploration_scale must be finite and non-negative")
        keys = [(item.factor_kind, item.factor_id) for item in self.factors]
        if len(keys) != len(set(keys)):
            problems.append("belief factors must have unique kind/id pairs")
        for item in self.factors:
            problems.extend(item.validate())
        return problems

    def factor_map(self) -> dict[tuple[str, str], FactorWeight]:
        return {(item.factor_kind, item.factor_id): item for item in self.factors}

    def factor_score(self, factor_kind: str, factor_id: str) -> float:
        item = self.factor_map().get((factor_kind, factor_id))
        if item is None:
            return 0.0
        bonus = self.exploration_scale * item.uncertainty
        return item.mean_reward + bonus

    def score_strategy(self, strategy_id: str) -> float:
        return self.factor_score("factor.strategy", strategy_id)

    def score_observation(self, observation: StrategyEvidence) -> float:
        score = self.factor_score("factor.strategy", observation.strategy_id)
        score += self.factor_score("factor.action-kind", observation.action_kind)
        if observation.context_policy_id:
            score += self.factor_score("factor.context-policy", observation.context_policy_id)
        if observation.model_id:
            score += self.factor_score("factor.model", observation.model_id)
        score += sum(self.factor_score("factor.tag", tag) for tag in observation.tags)
        return score

    def to_dict(self) -> dict[str, Any]:
        return {
            "learning_model_version": LEARNING_MODEL_VERSION,
            "revision": self.revision,
            "exploration_scale": self.exploration_scale,
            "factors": [item.to_dict() for item in self.factors],
        }


class BeliefUpdater:
    """Incrementally update factor means while retaining explicit uncertainty."""

    def __init__(self, *, rejection_reward: float = -0.25) -> None:
        self.rejection_reward = rejection_reward

    @staticmethod
    def _factor_keys(observation: StrategyEvidence) -> tuple[tuple[str, str], ...]:
        keys = [
            ("factor.strategy", observation.strategy_id),
            ("factor.action-kind", observation.action_kind),
        ]
        if observation.context_policy_id:
            keys.append(("factor.context-policy", observation.context_policy_id))
        if observation.model_id:
            keys.append(("factor.model", observation.model_id))
        keys.extend(("factor.tag", tag) for tag in observation.tags)
        return tuple(keys)

    def update(
        self,
        model: NextBeliefModel,
        observations: Sequence[StrategyEvidence],
        *,
        revision: str,
    ) -> NextBeliefModel:
        problems = model.validate()
        for observation in observations:
            problems.extend(observation.validate())
        if not revision.strip():
            problems.append("updated belief revision must not be empty")
        if problems:
            raise ValueError("invalid next-belief update: " + "; ".join(problems))

        by_key = model.factor_map()
        totals: dict[tuple[str, str], tuple[float, int]] = {
            key: (item.mean_reward * item.evidence_count, item.evidence_count)
            for key, item in by_key.items()
        }
        for observation in observations:
            reward = observation.reward if observation.accepted else self.rejection_reward
            for key in self._factor_keys(observation):
                total, count = totals.get(key, (0.0, 0))
                totals[key] = (total + reward, count + 1)

        factors = []
        for (kind, factor_id), (total, count) in sorted(totals.items()):
            mean = total / count if count else 0.0
            uncertainty = 1.0 / sqrt(max(1, count))
            factors.append(FactorWeight(kind, factor_id, mean, count, uncertainty))
        return NextBeliefModel(
            revision=revision,
            factors=tuple(factors),
            exploration_scale=model.exploration_scale,
        )


__all__ = [
    "LEARNING_MODEL_VERSION", "BeliefUpdater", "FactorWeight",
    "LearningObservation", "NextBeliefModel", "StrategyEvidence",
]
