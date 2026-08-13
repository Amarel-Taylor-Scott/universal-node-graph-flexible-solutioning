"""Append-only observational utility memory for question selection."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from solutiongraph.model import DIGEST_RE, ID_RE, sha256_digest


@dataclass(frozen=True)
class QuestionUtilityObservation:
    id: str
    question_id: str
    task_fingerprint_digest: str
    context_tags: tuple[str, ...]
    finding_produced: bool
    repair_proposed: bool
    repair_promoted: bool
    false_correction: bool
    human_minutes: float = 0.0
    latency_ms: float = 0.0
    monetary_cost: float = 0.0
    source_receipt_digest: str = ""

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "observation") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.question_id):
            problems.append(f"{path}.id and question_id must be namespaced identifiers")
        if not DIGEST_RE.fullmatch(self.task_fingerprint_digest):
            problems.append(f"{path}.task_fingerprint_digest must be a sha256 digest")
        if self.source_receipt_digest and not DIGEST_RE.fullmatch(self.source_receipt_digest):
            problems.append(f"{path}.source_receipt_digest must be empty or sha256")
        if len(self.context_tags) != len(set(self.context_tags)) or any(
            not ID_RE.fullmatch(tag) for tag in self.context_tags
        ):
            problems.append(f"{path}.context_tags must be unique namespaced identifiers")
        for label, value in (
            ("human_minutes", self.human_minutes),
            ("latency_ms", self.latency_ms),
            ("monetary_cost", self.monetary_cost),
        ):
            if not isfinite(value) or value < 0:
                problems.append(f"{path}.{label} must be finite and non-negative")
        return problems

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "question_id": self.question_id,
            "task_fingerprint_digest": self.task_fingerprint_digest,
            "context_tags": list(self.context_tags),
            "finding_produced": self.finding_produced,
            "repair_proposed": self.repair_proposed,
            "repair_promoted": self.repair_promoted,
            "false_correction": self.false_correction,
            "human_minutes": self.human_minutes,
            "latency_ms": self.latency_ms,
            "monetary_cost": self.monetary_cost,
            "source_receipt_digest": self.source_receipt_digest,
        }


@dataclass(frozen=True)
class QuestionUtilityEstimate:
    question_id: str
    observation_count: int
    helpful_count: int
    false_correction_count: int
    posterior_mean: float
    uncertainty: float
    contextual_count: int


class QuestionUtilityProvider(Protocol):
    @property
    def digest(self) -> str: ...

    def estimate(
        self,
        question_id: str,
        context_tags: tuple[str, ...] = (),
    ) -> QuestionUtilityEstimate: ...


@dataclass(frozen=True)
class QuestionUtilityMemory:
    id: str
    version: str
    observations: tuple[QuestionUtilityObservation, ...] = ()
    parent_digest: str = ""

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "question_utility_memory") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.version.strip():
            problems.append(f"{path}.id and version must be valid")
        if self.parent_digest and not DIGEST_RE.fullmatch(self.parent_digest):
            problems.append(f"{path}.parent_digest must be empty or sha256")
        ids = [observation.id for observation in self.observations]
        if len(ids) != len(set(ids)):
            problems.append(f"{path}.observations ids must be unique")
        for index, observation in enumerate(self.observations):
            problems.extend(observation.validate(f"{path}.observations[{index}]"))
        return problems

    def append(
        self,
        *observations: QuestionUtilityObservation,
        version: str | None = None,
    ) -> QuestionUtilityMemory:
        result = QuestionUtilityMemory(
            id=self.id,
            version=version or self.version,
            observations=(*self.observations, *observations),
            parent_digest=self.digest,
        )
        problems = result.validate()
        if problems:
            raise ValueError("invalid question utility update: " + "; ".join(problems))
        return result

    def estimate(
        self,
        question_id: str,
        context_tags: tuple[str, ...] = (),
    ) -> QuestionUtilityEstimate:
        requested = set(context_tags)
        all_matches = [item for item in self.observations if item.question_id == question_id]
        contextual = [
            item for item in all_matches if not requested or requested <= set(item.context_tags)
        ]
        matches = contextual if contextual else all_matches
        helpful = sum(
            item.finding_produced and (item.repair_promoted or not item.repair_proposed)
            for item in matches
        )
        false_corrections = sum(item.false_correction for item in matches)
        alpha = 1.0 + helpful
        beta = 1.0 + len(matches) - helpful + 2.0 * false_corrections
        posterior = alpha / (alpha + beta)
        uncertainty = 1.0 / (alpha + beta) ** 0.5
        return QuestionUtilityEstimate(
            question_id=question_id,
            observation_count=len(matches),
            helpful_count=helpful,
            false_correction_count=false_corrections,
            posterior_mean=posterior,
            uncertainty=uncertainty,
            contextual_count=len(contextual),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "version": self.version,
            "parent_digest": self.parent_digest,
            "observations": [item.to_dict() for item in self.observations],
            "limitations": (
                "Question effects are observational unless a controlled assignment "
                "supports a causal interpretation."
            ),
        }


EMPTY_QUESTION_UTILITY_MEMORY = QuestionUtilityMemory(
    "memory.interrogation-questions", "1.0.0"
)


__all__ = [
    "EMPTY_QUESTION_UTILITY_MEMORY",
    "QuestionUtilityEstimate",
    "QuestionUtilityMemory",
    "QuestionUtilityObservation",
    "QuestionUtilityProvider",
]
