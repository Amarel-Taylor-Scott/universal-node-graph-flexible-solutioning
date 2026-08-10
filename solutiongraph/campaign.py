"""Immutable lineage and trust-boundary contracts for generated graph campaigns.

The campaign layer records why a graph was proposed and which evidence changed
its disposition.  It does not compile graphs, execute nodes, or judge its own
proposals.  Those responsibilities remain with the compiler, executor, and an
independent evaluator respectively.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE


CAMPAIGN_MODEL_VERSION = "0.1"
ISOLATION_LEVELS = ("in_process", "subprocess", "container", "microvm", "remote")
DECISIONS = ("retain", "promote", "reject", "quarantine", "invalidate")


@dataclass(frozen=True)
class CampaignBudget:
    """Hard limits owned by the harness, never by candidate code."""

    max_candidates: int
    max_trials: int
    max_parallel_trials: int = 1
    max_failures: int = 0
    max_wall_seconds: float | None = None
    max_cost_units: float | None = None
    fidelity_rungs: tuple[float, ...] = (1.0,)
    random_seed: int = 0

    def validate(self, path: str = "budget") -> list[str]:
        problems: list[str] = []
        if self.max_candidates <= 0 or self.max_trials <= 0:
            problems.append(f"{path}.max_candidates and max_trials must be positive")
        if self.max_parallel_trials <= 0:
            problems.append(f"{path}.max_parallel_trials must be positive")
        if self.max_failures < 0:
            problems.append(f"{path}.max_failures must be non-negative")
        for label, value in (
            ("max_wall_seconds", self.max_wall_seconds),
            ("max_cost_units", self.max_cost_units),
        ):
            if value is not None and (not isfinite(value) or value <= 0):
                problems.append(f"{path}.{label} must be finite and positive or null")
        if not self.fidelity_rungs:
            problems.append(f"{path}.fidelity_rungs must not be empty")
        elif any(not isfinite(value) or value <= 0 for value in self.fidelity_rungs):
            problems.append(f"{path}.fidelity_rungs must contain finite positive values")
        elif any(
            current <= previous
            for previous, current in zip(self.fidelity_rungs, self.fidelity_rungs[1:])
        ):
            problems.append(f"{path}.fidelity_rungs must be strictly increasing")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_candidates": self.max_candidates,
            "max_trials": self.max_trials,
            "max_parallel_trials": self.max_parallel_trials,
            "max_failures": self.max_failures,
            "max_wall_seconds": self.max_wall_seconds,
            "max_cost_units": self.max_cost_units,
            "fidelity_rungs": list(self.fidelity_rungs),
            "random_seed": self.random_seed,
        }


@dataclass(frozen=True)
class EvaluationBoundary:
    """Identity and isolation requirements for one fixed evaluation oracle."""

    id: str
    evaluator_digest: str
    dataset_digest: str
    environment_digest: str
    trust_level: str = "untrusted"
    candidate_isolation: str = "microvm"
    evaluator_isolation: str = "remote"
    candidate_can_read_evaluator: bool = False
    candidate_can_write_evaluator: bool = False
    candidate_network_access: bool = False
    hidden_case_ids: tuple[str, ...] = ()

    def validate(self, path: str = "evaluation_boundary") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        for label, digest in (
            ("evaluator_digest", self.evaluator_digest),
            ("dataset_digest", self.dataset_digest),
            ("environment_digest", self.environment_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be a sha256 digest")
        if self.trust_level not in ("trusted", "untrusted"):
            problems.append(f"{path}.trust_level must be trusted or untrusted")
        for label, value in (
            ("candidate_isolation", self.candidate_isolation),
            ("evaluator_isolation", self.evaluator_isolation),
        ):
            if value not in ISOLATION_LEVELS:
                problems.append(f"{path}.{label} is not a supported isolation level")
        if len(self.hidden_case_ids) != len(set(self.hidden_case_ids)):
            problems.append(f"{path}.hidden_case_ids must be unique")
        if any(not ID_RE.fullmatch(case_id) for case_id in self.hidden_case_ids):
            problems.append(f"{path}.hidden_case_ids contains an invalid identifier")
        if self.candidate_can_write_evaluator:
            problems.append(f"{path}: candidate code must never write the evaluator")
        if self.hidden_case_ids and self.candidate_can_read_evaluator:
            problems.append(f"{path}: hidden cases require a candidate-unreadable evaluator")
        if self.trust_level == "untrusted" and self.candidate_isolation not in (
            "microvm",
            "remote",
        ):
            problems.append(
                f"{path}: untrusted candidates require microvm or remote isolation; "
                "a plain container is not an adversarial boundary"
            )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "evaluator_digest": self.evaluator_digest,
            "dataset_digest": self.dataset_digest,
            "environment_digest": self.environment_digest,
            "trust_level": self.trust_level,
            "candidate_isolation": self.candidate_isolation,
            "evaluator_isolation": self.evaluator_isolation,
            "candidate_can_read_evaluator": self.candidate_can_read_evaluator,
            "candidate_can_write_evaluator": self.candidate_can_write_evaluator,
            "candidate_network_access": self.candidate_network_access,
            "hidden_case_ids": list(self.hidden_case_ids),
        }


@dataclass(frozen=True)
class CandidateRecord:
    """One proposed frozen plan and its immutable ancestry."""

    id: str
    plan_digest: str
    parent_ids: tuple[str, ...]
    generation: int
    operator: str
    hypothesis: str
    proposer: str = ""
    proposal_digest: str = ""
    belief_revision: str = ""
    created_at: str = ""

    def validate(self, path: str = "candidate") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not DIGEST_RE.fullmatch(self.plan_digest):
            problems.append(f"{path}.plan_digest must be a sha256 digest")
        if not ID_RE.fullmatch(self.operator):
            problems.append(f"{path}.operator must be a namespaced identifier")
        if self.proposer and not ID_RE.fullmatch(self.proposer):
            problems.append(f"{path}.proposer must be empty or a namespaced identifier")
        if self.proposal_digest and not DIGEST_RE.fullmatch(self.proposal_digest):
            problems.append(f"{path}.proposal_digest must be empty or a sha256 digest")
        if not self.hypothesis.strip():
            problems.append(f"{path}.hypothesis must not be empty")
        if len(self.parent_ids) != len(set(self.parent_ids)):
            problems.append(f"{path}.parent_ids must be unique")
        if self.id in self.parent_ids:
            problems.append(f"{path} cannot be its own parent")
        if any(not ID_RE.fullmatch(parent_id) for parent_id in self.parent_ids):
            problems.append(f"{path}.parent_ids contains an invalid identifier")
        if self.generation < 0:
            problems.append(f"{path}.generation must be non-negative")
        if self.parent_ids and self.generation == 0:
            problems.append(f"{path}: a derived candidate must have generation greater than zero")
        if not self.parent_ids and self.generation != 0:
            problems.append(f"{path}: a seed candidate must have generation zero")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "plan_digest": self.plan_digest,
            "parent_ids": list(self.parent_ids),
            "generation": self.generation,
            "operator": self.operator,
            "hypothesis": self.hypothesis,
            "proposer": self.proposer,
            "proposal_digest": self.proposal_digest,
            "belief_revision": self.belief_revision,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class CampaignDecision:
    """An append-only disposition backed by zero or more immutable receipts."""

    id: str
    candidate_id: str
    decision: str
    reason: str
    receipt_ids: tuple[str, ...] = ()
    decided_at: str = ""

    def validate(self, path: str = "decision") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.candidate_id):
            problems.append(f"{path}.id and candidate_id must be namespaced identifiers")
        if self.decision not in DECISIONS:
            problems.append(f"{path}.decision must be one of {', '.join(DECISIONS)}")
        if not self.reason.strip():
            problems.append(f"{path}.reason must not be empty")
        if len(self.receipt_ids) != len(set(self.receipt_ids)):
            problems.append(f"{path}.receipt_ids must be unique")
        if any(not ID_RE.fullmatch(receipt_id) for receipt_id in self.receipt_ids):
            problems.append(f"{path}.receipt_ids contains an invalid identifier")
        if self.decision in ("retain", "promote", "reject") and not self.receipt_ids:
            problems.append(f"{path}.{self.decision} requires execution evidence")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "decision": self.decision,
            "reason": self.reason,
            "receipt_ids": list(self.receipt_ids),
            "decided_at": self.decided_at,
        }


@dataclass(frozen=True)
class CampaignLedger:
    """A population DAG plus append-only disposition events."""

    candidates: tuple[CandidateRecord, ...] = ()
    decisions: tuple[CampaignDecision, ...] = ()

    def append_candidate(self, candidate: CandidateRecord) -> CampaignLedger:
        problems = candidate.validate()
        by_id = {item.id: item for item in self.candidates}
        if candidate.id in by_id:
            problems.append("candidate ids must be globally unique within a campaign")
        missing = sorted(set(candidate.parent_ids) - set(by_id))
        if missing:
            problems.append("candidate parents must already exist: " + ", ".join(missing))
        if not missing and candidate.parent_ids:
            parent_generation = max(by_id[parent].generation for parent in candidate.parent_ids)
            if candidate.generation <= parent_generation:
                problems.append("candidate generation must exceed every parent generation")
        if problems:
            raise ValueError("invalid campaign candidate: " + "; ".join(problems))
        return CampaignLedger(self.candidates + (candidate,), self.decisions)

    def append_decision(self, decision: CampaignDecision) -> CampaignLedger:
        problems = decision.validate()
        if decision.candidate_id not in {candidate.id for candidate in self.candidates}:
            problems.append("decision references an unknown candidate")
        if decision.id in {item.id for item in self.decisions}:
            problems.append("decision ids must be globally unique within a campaign")
        if problems:
            raise ValueError("invalid campaign decision: " + "; ".join(problems))
        return CampaignLedger(self.candidates, self.decisions + (decision,))

    def latest_decisions(self) -> dict[str, CampaignDecision]:
        latest: dict[str, CampaignDecision] = {}
        for decision in self.decisions:
            latest[decision.candidate_id] = decision
        return latest

    def frontier(self) -> tuple[CandidateRecord, ...]:
        """Return proposed, retained, and promoted candidates in stable order."""
        latest = self.latest_decisions()
        return tuple(
            candidate
            for candidate in self.candidates
            if latest.get(candidate.id) is None
            or latest[candidate.id].decision in ("retain", "promote")
        )

    def ancestors(self, candidate_id: str) -> tuple[CandidateRecord, ...]:
        by_id = {candidate.id: candidate for candidate in self.candidates}
        if candidate_id not in by_id:
            raise KeyError(candidate_id)
        found: set[str] = set()

        def visit(item_id: str) -> None:
            for parent_id in by_id[item_id].parent_ids:
                if parent_id not in found:
                    found.add(parent_id)
                    visit(parent_id)

        visit(candidate_id)
        return tuple(candidate for candidate in self.candidates if candidate.id in found)

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_model_version": CAMPAIGN_MODEL_VERSION,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "decisions": [decision.to_dict() for decision in self.decisions],
        }


__all__ = [
    "CAMPAIGN_MODEL_VERSION",
    "CampaignBudget",
    "CampaignDecision",
    "CampaignLedger",
    "CandidateRecord",
    "EvaluationBoundary",
]
