"""Immutable contracts for the What-Is-Next control plane.

A Solver Cell repeatedly asks: given what is presently known, what should
happen next?  The answer may be a test, research task, graph proposal, subloop,
comparison, optimization, human review, pause, or stop.  These objects carry no
compiler, runtime, evaluator, or promotion authority.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE, canonical_json, sha256_digest

NEXTING_MODEL_VERSION = "0.1"
CORE_ACTION_KINDS = (
    "next.gather-context", "next.run-probe", "next.research",
    "next.retrieve-blueprint", "next.instantiate-graph", "next.propose-graph",
    "next.propose-subgraph", "next.propose-node", "next.propose-package",
    "next.mutate-graph", "next.replace-node", "next.configure", "next.optimize",
    "next.evaluate", "next.compare", "next.ensemble", "next.spawn-subloop",
    "next.ask-council", "next.request-human", "next.continue-recipe",
    "next.pause", "next.stop",
)
DECISION_DISPOSITIONS = (
    "one", "ordered", "parallel", "ensemble", "branch", "defer", "stop",
)
ACTION_OUTCOMES = ("succeeded", "failed", "blocked", "skipped", "cancelled")


def _json(value: Any) -> Any:
    return json.loads(canonical_json(value))


def _id(value: str, path: str, *, optional: bool = False) -> list[str]:
    if optional and not value:
        return []
    return [] if ID_RE.fullmatch(value) else [f"{path} must be a namespaced identifier"]


def _digest(value: str, path: str, *, optional: bool = False) -> list[str]:
    if optional and not value:
        return []
    return [] if DIGEST_RE.fullmatch(value) else [f"{path} must be a sha256 digest"]


def _unit(value: float, path: str) -> list[str]:
    return [] if isfinite(value) and 0.0 <= value <= 1.0 else [f"{path} must be between zero and one"]


def _unique(values: tuple[str, ...], path: str, *, identifiers: bool = False) -> list[str]:
    problems: list[str] = []
    if len(values) != len(set(values)):
        problems.append(f"{path} must be unique")
    if any(not item.strip() for item in values):
        problems.append(f"{path} must contain nonempty strings")
    if identifiers and any(not ID_RE.fullmatch(item) for item in values):
        problems.append(f"{path} must contain namespaced identifiers")
    return problems


@dataclass(frozen=True)
class KnowledgeReference:
    """A content-addressed pointer; its bytes need not enter model context."""

    id: str
    kind: str
    digest: str
    uri: str = ""
    summary: str = ""
    tags: tuple[str, ...] = ()
    visibility: str = "knowledge.internal"
    confidence: float = 1.0
    observed_at: str = ""
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def validate(self, path: str = "knowledge_ref") -> list[str]:
        problems = [*_id(self.id, f"{path}.id"), *_id(self.kind, f"{path}.kind"),
                    *_digest(self.digest, f"{path}.digest"),
                    *_id(self.visibility, f"{path}.visibility"),
                    *_unit(self.confidence, f"{path}.confidence")]
        problems += _unique(self.tags, f"{path}.tags", identifiers=True)
        if self.uri and not self.uri.startswith(("artifact://", "file://", "db://", "https://", "urn:")):
            problems.append(f"{path}.uri uses an unsupported scheme")
        try:
            canonical_json(dict(self.extensions))
        except (TypeError, ValueError):
            problems.append(f"{path}.extensions must be JSON serialisable")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "kind": self.kind, "digest": self.digest, "uri": self.uri,
            "summary": self.summary, "tags": list(self.tags), "visibility": self.visibility,
            "confidence": self.confidence, "observed_at": self.observed_at,
            "extensions": _json(dict(self.extensions)),
        }


@dataclass(frozen=True)
class KnowledgeFact:
    id: str
    subject: str
    predicate: str
    value: Any
    confidence: float = 1.0
    evidence_refs: tuple[str, ...] = ()
    status: str = "knowledge.supported"
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def validate(self, path: str = "fact") -> list[str]:
        problems = [*_id(self.id, f"{path}.id"), *_id(self.predicate, f"{path}.predicate"),
                    *_id(self.status, f"{path}.status"),
                    *_unit(self.confidence, f"{path}.confidence")]
        if not self.subject.strip():
            problems.append(f"{path}.subject must not be empty")
        problems += _unique(self.evidence_refs, f"{path}.evidence_refs", identifiers=True)
        try:
            canonical_json(self.value)
            canonical_json(dict(self.extensions))
        except (TypeError, ValueError):
            problems.append(f"{path}.value and extensions must be JSON serialisable")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "subject": self.subject, "predicate": self.predicate,
            "value": _json(self.value), "confidence": self.confidence,
            "evidence_refs": list(self.evidence_refs), "status": self.status,
            "extensions": _json(dict(self.extensions)),
        }


@dataclass(frozen=True)
class Unknown:
    id: str
    question: str
    importance: float = 0.5
    blockers: tuple[str, ...] = ()
    suggested_probe_kinds: tuple[str, ...] = ()

    def validate(self, path: str = "unknown") -> list[str]:
        problems = [*_id(self.id, f"{path}.id"), *_unit(self.importance, f"{path}.importance")]
        if not self.question.strip():
            problems.append(f"{path}.question must not be empty")
        problems += _unique(self.blockers, f"{path}.blockers", identifiers=True)
        problems += _unique(self.suggested_probe_kinds, f"{path}.suggested_probe_kinds", identifiers=True)
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "question": self.question, "importance": self.importance,
            "blockers": list(self.blockers),
            "suggested_probe_kinds": list(self.suggested_probe_kinds),
        }


@dataclass(frozen=True)
class ProgressSignal:
    id: str
    value: float
    direction: str = "maximize"
    previous_value: float | None = None
    threshold: float | None = None

    @property
    def changed(self) -> bool:
        return self.previous_value is None or self.previous_value != self.value

    def validate(self, path: str = "progress") -> list[str]:
        problems = _id(self.id, f"{path}.id")
        if self.direction not in ("maximize", "minimize", "target"):
            problems.append(f"{path}.direction is invalid")
        for label, value in (("value", self.value), ("previous_value", self.previous_value),
                             ("threshold", self.threshold)):
            if value is not None and not isfinite(value):
                problems.append(f"{path}.{label} must be finite or null")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class KnowledgeState:
    """The smallest durable answer to: what do I presently know?"""

    id: str
    revision: str
    goal: str
    references: tuple[KnowledgeReference, ...] = ()
    facts: tuple[KnowledgeFact, ...] = ()
    unknowns: tuple[Unknown, ...] = ()
    progress: tuple[ProgressSignal, ...] = ()
    frontier_refs: tuple[str, ...] = ()
    graph_ref: str = ""
    plan_ref: str = ""
    run_ref: str = ""
    recipe_ref: str = ""
    parent_state_digest: str = ""
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def reference_map(self) -> dict[str, KnowledgeReference]:
        return {item.id: item for item in self.references}

    @property
    def fact_map(self) -> dict[str, KnowledgeFact]:
        return {item.id: item for item in self.facts}

    def validate(self, path: str = "state") -> list[str]:
        problems = _id(self.id, f"{path}.id")
        if not self.revision.strip() or not self.goal.strip():
            problems.append(f"{path}.revision and goal are required")
        for label, values in (("references", self.references), ("facts", self.facts),
                              ("unknowns", self.unknowns), ("progress", self.progress)):
            problems += _unique(tuple(item.id for item in values), f"{path}.{label}.ids", identifiers=True)
            for index, item in enumerate(values):
                problems += item.validate(f"{path}.{label}[{index}]")
        problems += _unique(self.frontier_refs, f"{path}.frontier_refs", identifiers=True)
        for label, value in (("graph_ref", self.graph_ref), ("plan_ref", self.plan_ref),
                             ("run_ref", self.run_ref), ("recipe_ref", self.recipe_ref)):
            problems += _id(value, f"{path}.{label}", optional=True)
        problems += _digest(self.parent_state_digest, f"{path}.parent_state_digest", optional=True)
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "nexting_model_version": NEXTING_MODEL_VERSION, "id": self.id,
            "revision": self.revision, "goal": self.goal,
            "references": [item.to_dict() for item in self.references],
            "facts": [item.to_dict() for item in self.facts],
            "unknowns": [item.to_dict() for item in self.unknowns],
            "progress": [item.to_dict() for item in self.progress],
            "frontier_refs": list(self.frontier_refs), "graph_ref": self.graph_ref,
            "plan_ref": self.plan_ref, "run_ref": self.run_ref, "recipe_ref": self.recipe_ref,
            "parent_state_digest": self.parent_state_digest,
            "extensions": _json(dict(self.extensions)),
        }


@dataclass(frozen=True)
class NextQuestion:
    id: str
    state_digest: str
    prompt: str = "Given what is presently known, what should happen next?"
    scope: str = "scope.problem"
    target_ref: str = ""
    allowed_action_kinds: tuple[str, ...] = CORE_ACTION_KINDS
    context_policy_id: str = "context.selective"
    recipe_ref: str = ""
    parent_question_id: str = ""
    depth: int = 0
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems = [*_id(self.id, "question.id"), *_digest(self.state_digest, "question.state_digest"),
                    *_id(self.scope, "question.scope"), *_id(self.context_policy_id, "question.context_policy_id")]
        if not self.prompt.strip() or self.depth < 0:
            problems.append("question prompt must be nonempty and depth non-negative")
        problems += _id(self.target_ref, "question.target_ref", optional=True)
        problems += _id(self.recipe_ref, "question.recipe_ref", optional=True)
        problems += _id(self.parent_question_id, "question.parent_question_id", optional=True)
        problems += _unique(self.allowed_action_kinds, "question.allowed_action_kinds", identifiers=True)
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "state_digest": self.state_digest, "prompt": self.prompt,
            "scope": self.scope, "target_ref": self.target_ref,
            "allowed_action_kinds": list(self.allowed_action_kinds),
            "context_policy_id": self.context_policy_id, "recipe_ref": self.recipe_ref,
            "parent_question_id": self.parent_question_id, "depth": self.depth,
            "extensions": _json(dict(self.extensions)),
        }


@dataclass(frozen=True)
class NextBudget:
    max_strategy_calls: int = 16
    max_proposals: int = 64
    max_parallel: int = 4
    max_actions: int = 3
    max_depth: int = 4
    max_iterations: int = 50
    max_no_progress: int = 5
    max_cost_units: float | None = None
    max_wall_seconds: float | None = None
    protected_blind_fraction: float = 0.10
    protected_random_fraction: float = 0.10
    random_seed: int = 0

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        for name in ("max_strategy_calls", "max_proposals", "max_parallel", "max_actions",
                     "max_depth", "max_iterations", "max_no_progress"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                problems.append(f"budget.{name} must be positive")
        for name in ("max_cost_units", "max_wall_seconds"):
            value = getattr(self, name)
            if value is not None and (not isfinite(value) or value <= 0):
                problems.append(f"budget.{name} must be positive or null")
        problems += _unit(self.protected_blind_fraction, "budget.protected_blind_fraction")
        problems += _unit(self.protected_random_fraction, "budget.protected_random_fraction")
        if self.protected_blind_fraction + self.protected_random_fraction > 1.0:
            problems.append("protected budget fractions exceed one")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class NextActionProposal:
    """A typed answer, not an authorized graph or runtime action."""

    id: str
    question_id: str
    action_kind: str
    title: str
    rationale: str
    strategy_id: str
    target_ref: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    prerequisite_refs: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    expected_information_gain: float = 0.0
    expected_utility: float = 0.0
    expected_cost: float = 0.0
    confidence: float = 0.5
    uncertainty: float = 0.5
    priority: float = 0.0
    model_id: str = ""
    prompt_digest: str = ""
    context_manifest_digest: str = ""
    correlation_group: str = ""
    parallel_safe: bool = False
    conflict_keys: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def semantic_identity(self) -> str:
        return sha256_digest({
            "action_kind": self.action_kind, "target_ref": self.target_ref,
            "payload": _json(dict(self.payload)),
            "prerequisite_refs": sorted(self.prerequisite_refs),
            "expected_outputs": sorted(self.expected_outputs),
        })

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems = [*_id(self.id, "proposal.id"), *_id(self.question_id, "proposal.question_id"),
                    *_id(self.action_kind, "proposal.action_kind"), *_id(self.strategy_id, "proposal.strategy_id")]
        if not self.title.strip() or not self.rationale.strip():
            problems.append("proposal title and rationale are required")
        for name in ("expected_information_gain", "expected_utility", "confidence", "uncertainty"):
            problems += _unit(getattr(self, name), f"proposal.{name}")
        if not isfinite(self.expected_cost) or self.expected_cost < 0 or not isfinite(self.priority):
            problems.append("proposal cost and priority must be finite")
        problems += _id(self.target_ref, "proposal.target_ref", optional=True)
        problems += _id(self.model_id, "proposal.model_id", optional=True)
        problems += _digest(self.prompt_digest, "proposal.prompt_digest", optional=True)
        problems += _digest(self.context_manifest_digest, "proposal.context_manifest_digest", optional=True)
        problems += _id(self.correlation_group, "proposal.correlation_group", optional=True)
        problems += _unique(self.prerequisite_refs, "proposal.prerequisite_refs", identifiers=True)
        problems += _unique(self.expected_outputs, "proposal.expected_outputs", identifiers=True)
        problems += _unique(self.tags, "proposal.tags", identifiers=True)
        try:
            canonical_json(dict(self.payload))
        except (TypeError, ValueError):
            problems.append("proposal payload must be JSON serialisable")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "question_id": self.question_id, "action_kind": self.action_kind,
            "title": self.title, "rationale": self.rationale, "strategy_id": self.strategy_id,
            "target_ref": self.target_ref, "payload": _json(dict(self.payload)),
            "prerequisite_refs": list(self.prerequisite_refs),
            "expected_outputs": list(self.expected_outputs),
            "expected_information_gain": self.expected_information_gain,
            "expected_utility": self.expected_utility, "expected_cost": self.expected_cost,
            "confidence": self.confidence, "uncertainty": self.uncertainty,
            "priority": self.priority, "model_id": self.model_id,
            "prompt_digest": self.prompt_digest,
            "context_manifest_digest": self.context_manifest_digest,
            "correlation_group": self.correlation_group,
            "parallel_safe": self.parallel_safe, "conflict_keys": list(self.conflict_keys),
            "tags": list(self.tags), "extensions": _json(dict(self.extensions)),
        }


@dataclass(frozen=True)
class StrategyOutcome:
    strategy_id: str
    question_id: str
    proposals: tuple[NextActionProposal, ...] = ()
    requested_context: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    abstained: bool = False
    cost_units: float = 0.0
    latency_seconds: float = 0.0

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id, "question_id": self.question_id,
            "proposals": [item.to_dict() for item in self.proposals],
            "requested_context": list(self.requested_context),
            "diagnostics": list(self.diagnostics), "abstained": self.abstained,
            "cost_units": self.cost_units, "latency_seconds": self.latency_seconds,
        }


@dataclass(frozen=True)
class ProposalCluster:
    semantic_identity: str
    representative: NextActionProposal
    member_ids: tuple[str, ...]
    strategy_ids: tuple[str, ...]
    aggregate_confidence: float
    aggregate_uncertainty: float

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_identity": self.semantic_identity,
            "representative": self.representative.to_dict(),
            "member_ids": list(self.member_ids), "strategy_ids": list(self.strategy_ids),
            "aggregate_confidence": self.aggregate_confidence,
            "aggregate_uncertainty": self.aggregate_uncertainty,
        }


@dataclass(frozen=True)
class DecisionPolicy:
    id: str = "next.policy.pareto-balanced"
    utility_weight: float = 1.0
    information_gain_weight: float = 0.75
    confidence_weight: float = 0.75
    uncertainty_penalty: float = 0.35
    cost_penalty: float = 0.25
    priority_weight: float = 0.25
    diversity_bonus: float = 0.15
    minimum_confidence: float = 0.0
    allow_parallel: bool = True
    allow_ensemble: bool = True

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class NextDecision:
    id: str
    question_id: str
    disposition: str
    selected_proposal_ids: tuple[str, ...]
    rationale: str
    confidence: float
    ranked_cluster_digests: tuple[str, ...]
    unresolved_question_ids: tuple[str, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "question_id": self.question_id, "disposition": self.disposition,
            "selected_proposal_ids": list(self.selected_proposal_ids),
            "rationale": self.rationale, "confidence": self.confidence,
            "ranked_cluster_digests": list(self.ranked_cluster_digests),
            "unresolved_question_ids": list(self.unresolved_question_ids),
            "extensions": _json(dict(self.extensions)),
        }


@dataclass(frozen=True)
class NextDecisionReceipt:
    id: str
    state_digest: str
    question_digest: str
    budget_digest: str
    policy_digest: str
    selected_strategy_ids: tuple[str, ...]
    outcomes: tuple[StrategyOutcome, ...]
    clusters: tuple[ProposalCluster, ...]
    decision: NextDecision
    skipped_strategy_ids: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "nexting_model_version": NEXTING_MODEL_VERSION, "id": self.id,
            "state_digest": self.state_digest, "question_digest": self.question_digest,
            "budget_digest": self.budget_digest, "policy_digest": self.policy_digest,
            "selected_strategy_ids": list(self.selected_strategy_ids),
            "skipped_strategy_ids": list(self.skipped_strategy_ids),
            "outcomes": [item.to_dict() for item in self.outcomes],
            "clusters": [item.to_dict() for item in self.clusters],
            "decision": self.decision.to_dict(), "diagnostics": list(self.diagnostics),
        }


@dataclass(frozen=True)
class ActionResult:
    proposal_id: str
    outcome: str
    produced_references: tuple[KnowledgeReference, ...] = ()
    produced_facts: tuple[KnowledgeFact, ...] = ()
    resolved_unknown_ids: tuple[str, ...] = ()
    metrics: Mapping[str, float] = field(default_factory=dict)
    failure_class: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id, "outcome": self.outcome,
            "produced_references": [item.to_dict() for item in self.produced_references],
            "produced_facts": [item.to_dict() for item in self.produced_facts],
            "resolved_unknown_ids": list(self.resolved_unknown_ids),
            "metrics": dict(self.metrics), "failure_class": self.failure_class,
            "details": _json(dict(self.details)),
        }


@dataclass(frozen=True)
class LoopIterationReceipt:
    id: str
    iteration: int
    prior_state_digest: str
    decision_receipt_digest: str
    action_results: tuple[ActionResult, ...]
    next_state_digest: str
    progress_observed: bool

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "iteration": self.iteration,
            "prior_state_digest": self.prior_state_digest,
            "decision_receipt_digest": self.decision_receipt_digest,
            "action_results": [item.to_dict() for item in self.action_results],
            "next_state_digest": self.next_state_digest,
            "progress_observed": self.progress_observed,
        }


@dataclass(frozen=True)
class SolverCellReceipt:
    id: str
    initial_state_digest: str
    final_state_digest: str
    iteration_receipts: tuple[LoopIterationReceipt, ...]
    terminal_disposition: str
    reason: str

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "nexting_model_version": NEXTING_MODEL_VERSION, "id": self.id,
            "initial_state_digest": self.initial_state_digest,
            "final_state_digest": self.final_state_digest,
            "iteration_receipts": [item.to_dict() for item in self.iteration_receipts],
            "terminal_disposition": self.terminal_disposition, "reason": self.reason,
        }


__all__ = [
    "ACTION_OUTCOMES", "CORE_ACTION_KINDS", "DECISION_DISPOSITIONS",
    "NEXTING_MODEL_VERSION", "ActionResult", "DecisionPolicy", "KnowledgeFact",
    "KnowledgeReference", "KnowledgeState", "LoopIterationReceipt",
    "NextActionProposal", "NextBudget", "NextDecision", "NextDecisionReceipt",
    "NextQuestion", "ProgressSignal", "ProposalCluster", "SolverCellReceipt",
    "StrategyOutcome", "Unknown",
]
