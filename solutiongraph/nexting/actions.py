"""Typed payload shells for universal What-Is-Next answer families.

The control plane stores payloads as portable JSON mappings. These frozen
classes provide optional typed authoring helpers without turning the action
vocabulary into a closed enum. Unknown namespaced action kinds may still be
introduced by plugins and validated by their own schemas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping, Union

from solutiongraph.model import ID_RE, canonical_json, sha256_digest

ACTION_PAYLOAD_MODEL_VERSION = "0.1"
GRAPH_CHANGE_ACTIONS = (
    "next.mutate-graph",
    "next.propose-graph",
    "next.propose-subgraph",
    "next.propose-node",
    "next.replace-node",
)
OPTIMIZATION_ACTIONS = ("next.configure", "next.optimize")
EXPERIMENT_ACTIONS = ("next.evaluate", "next.compare")
TERMINAL_ACTIONS = ("next.stop", "next.pause")


def _ids(values: tuple[str, ...], label: str) -> list[str]:
    problems: list[str] = []
    if len(values) != len(set(values)):
        problems.append(f"{label} must be unique")
    if any(not ID_RE.fullmatch(value) for value in values):
        problems.append(f"{label} must contain namespaced identifiers")
    return problems


def _json(value: Any, label: str) -> list[str]:
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        return [f"{label} must be JSON serialisable"]
    return []


@dataclass(frozen=True)
class ContextRequest:
    selector_ids: tuple[str, ...]
    reason: str
    maximum_bytes: int | None = None
    summarize: bool = True

    action_kind: str = field(default="next.gather-context", init=False)

    def validate(self) -> list[str]:
        problems = _ids(self.selector_ids, "selector_ids")
        if not self.selector_ids:
            problems.append("selector_ids must not be empty")
        if not self.reason.strip():
            problems.append("reason must not be empty")
        if self.maximum_bytes is not None and self.maximum_bytes <= 0:
            problems.append("maximum_bytes must be positive or null")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_model_version": ACTION_PAYLOAD_MODEL_VERSION,
            "selector_ids": list(self.selector_ids),
            "reason": self.reason,
            "maximum_bytes": self.maximum_bytes,
            "summarize": self.summarize,
        }


@dataclass(frozen=True)
class ProbeRequest:
    probe_kind: str
    hypothesis: str
    input_refs: tuple[str, ...] = ()
    metric_ids: tuple[str, ...] = ()
    alternatives: tuple[Mapping[str, Any], ...] = ()

    action_kind: str = field(default="next.run-probe", init=False)

    def validate(self) -> list[str]:
        problems = (
            []
            if ID_RE.fullmatch(self.probe_kind)
            else ["probe_kind must be namespaced"]
        )
        if not self.hypothesis.strip():
            problems.append("hypothesis must not be empty")
        problems.extend(_ids(self.input_refs, "input_refs"))
        problems.extend(_ids(self.metric_ids, "metric_ids"))
        problems.extend(_json(list(self.alternatives), "alternatives"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_model_version": ACTION_PAYLOAD_MODEL_VERSION,
            "probe_kind": self.probe_kind,
            "hypothesis": self.hypothesis,
            "input_refs": list(self.input_refs),
            "metric_ids": list(self.metric_ids),
            "alternatives": [dict(item) for item in self.alternatives],
        }


@dataclass(frozen=True)
class ResearchRequest:
    query: str
    source_kinds: tuple[str, ...] = ()
    output_contract: str = "knowledge.research-report"
    freshness_days: int | None = None
    blind_to_prior_work: bool = False

    action_kind: str = field(default="next.research", init=False)

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.query.strip():
            problems.append("query must not be empty")
        problems.extend(_ids(self.source_kinds, "source_kinds"))
        if not ID_RE.fullmatch(self.output_contract):
            problems.append("output_contract must be namespaced")
        if self.freshness_days is not None and self.freshness_days < 0:
            problems.append("freshness_days must be non-negative or null")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_model_version": ACTION_PAYLOAD_MODEL_VERSION,
            "query": self.query,
            "source_kinds": list(self.source_kinds),
            "output_contract": self.output_contract,
            "freshness_days": self.freshness_days,
            "blind_to_prior_work": self.blind_to_prior_work,
        }


@dataclass(frozen=True)
class GraphChangeRequest:
    change_kind: str
    target_ref: str
    operations: tuple[Mapping[str, Any], ...]
    hypothesis: str
    preserve_external_interface: bool = True
    action_kind: str = "next.mutate-graph"

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.action_kind not in GRAPH_CHANGE_ACTIONS:
            problems.append("action_kind is not a graph-change action")
        for label, value in (
            ("change_kind", self.change_kind),
            ("target_ref", self.target_ref),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{label} must be namespaced")
        if not self.operations:
            problems.append("operations must not be empty")
        if not self.hypothesis.strip():
            problems.append("hypothesis must not be empty")
        problems.extend(_json(list(self.operations), "operations"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_model_version": ACTION_PAYLOAD_MODEL_VERSION,
            "action_kind": self.action_kind,
            "change_kind": self.change_kind,
            "target_ref": self.target_ref,
            "operations": [dict(item) for item in self.operations],
            "hypothesis": self.hypothesis,
            "preserve_external_interface": self.preserve_external_interface,
        }


@dataclass(frozen=True)
class OptimizationRequest:
    target_ref: str
    objective_ids: tuple[str, ...]
    search_space_ref: str
    budget_ref: str = ""
    optimizer_family: str = "optimizer.adaptive"
    action_kind: str = "next.optimize"

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.action_kind not in OPTIMIZATION_ACTIONS:
            problems.append("action_kind is not an optimization action")
        for label, value in (
            ("target_ref", self.target_ref),
            ("search_space_ref", self.search_space_ref),
            ("optimizer_family", self.optimizer_family),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{label} must be namespaced")
        if self.budget_ref and not ID_RE.fullmatch(self.budget_ref):
            problems.append("budget_ref must be empty or namespaced")
        problems.extend(_ids(self.objective_ids, "objective_ids"))
        if not self.objective_ids:
            problems.append("objective_ids must not be empty")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_model_version": ACTION_PAYLOAD_MODEL_VERSION,
            "action_kind": self.action_kind,
            "target_ref": self.target_ref,
            "objective_ids": list(self.objective_ids),
            "search_space_ref": self.search_space_ref,
            "budget_ref": self.budget_ref,
            "optimizer_family": self.optimizer_family,
        }


@dataclass(frozen=True)
class ExperimentRequest:
    candidate_refs: tuple[str, ...]
    case_refs: tuple[str, ...]
    objective_ids: tuple[str, ...]
    fidelity: float = 1.0
    repetitions: int = 1
    action_kind: str = "next.evaluate"

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.action_kind not in EXPERIMENT_ACTIONS:
            problems.append("action_kind is not an experiment action")
        for label, values in (
            ("candidate_refs", self.candidate_refs),
            ("case_refs", self.case_refs),
            ("objective_ids", self.objective_ids),
        ):
            problems.extend(_ids(values, label))
            if not values:
                problems.append(f"{label} must not be empty")
        if not isfinite(self.fidelity) or self.fidelity <= 0:
            problems.append("fidelity must be finite and positive")
        if self.repetitions <= 0:
            problems.append("repetitions must be positive")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_model_version": ACTION_PAYLOAD_MODEL_VERSION,
            "action_kind": self.action_kind,
            "candidate_refs": list(self.candidate_refs),
            "case_refs": list(self.case_refs),
            "objective_ids": list(self.objective_ids),
            "fidelity": self.fidelity,
            "repetitions": self.repetitions,
        }


@dataclass(frozen=True)
class CouncilRequest:
    member_strategy_ids: tuple[str, ...]
    aggregation: str
    question_ref: str
    blind_members: bool = True
    maximum_rounds: int = 1

    action_kind: str = field(default="next.ask-council", init=False)

    def validate(self) -> list[str]:
        problems = _ids(self.member_strategy_ids, "member_strategy_ids")
        if not self.member_strategy_ids:
            problems.append("member_strategy_ids must not be empty")
        for label, value in (
            ("aggregation", self.aggregation),
            ("question_ref", self.question_ref),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{label} must be namespaced")
        if self.maximum_rounds <= 0:
            problems.append("maximum_rounds must be positive")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_model_version": ACTION_PAYLOAD_MODEL_VERSION,
            "member_strategy_ids": list(self.member_strategy_ids),
            "aggregation": self.aggregation,
            "question_ref": self.question_ref,
            "blind_members": self.blind_members,
            "maximum_rounds": self.maximum_rounds,
        }


@dataclass(frozen=True)
class SubloopRequest:
    goal: str
    scope: str
    allowed_action_kinds: tuple[str, ...]
    context_policy_id: str
    budget_overrides: Mapping[str, Any] = field(default_factory=dict)
    return_contract: str = "knowledge.subloop-result"

    action_kind: str = field(default="next.spawn-subloop", init=False)

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.goal.strip():
            problems.append("goal must not be empty")
        for label, value in (
            ("scope", self.scope),
            ("context_policy_id", self.context_policy_id),
            ("return_contract", self.return_contract),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{label} must be namespaced")
        problems.extend(_ids(self.allowed_action_kinds, "allowed_action_kinds"))
        if not self.allowed_action_kinds:
            problems.append("allowed_action_kinds must not be empty")
        problems.extend(_json(dict(self.budget_overrides), "budget_overrides"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_model_version": ACTION_PAYLOAD_MODEL_VERSION,
            "goal": self.goal,
            "scope": self.scope,
            "allowed_action_kinds": list(self.allowed_action_kinds),
            "context_policy_id": self.context_policy_id,
            "budget_overrides": dict(self.budget_overrides),
            "return_contract": self.return_contract,
        }


@dataclass(frozen=True)
class StopRequest:
    reason: str
    terminal_disposition: str = "stop"
    unresolved_refs: tuple[str, ...] = ()
    action_kind: str = "next.stop"

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.action_kind not in TERMINAL_ACTIONS:
            problems.append("action_kind is not a terminal action")
        if not self.reason.strip():
            problems.append("reason must not be empty")
        if self.terminal_disposition not in (
            "stop",
            "pause",
            "blocked",
            "exhausted",
        ):
            problems.append("terminal_disposition is invalid")
        problems.extend(_ids(self.unresolved_refs, "unresolved_refs"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_model_version": ACTION_PAYLOAD_MODEL_VERSION,
            "action_kind": self.action_kind,
            "reason": self.reason,
            "terminal_disposition": self.terminal_disposition,
            "unresolved_refs": list(self.unresolved_refs),
        }


ActionPayload = Union[
    ContextRequest,
    ProbeRequest,
    ResearchRequest,
    GraphChangeRequest,
    OptimizationRequest,
    ExperimentRequest,
    CouncilRequest,
    SubloopRequest,
    StopRequest,
]

REFERENCE_PAYLOAD_TYPES = {
    "next.gather-context": ContextRequest,
    "next.run-probe": ProbeRequest,
    "next.research": ResearchRequest,
    **{kind: GraphChangeRequest for kind in GRAPH_CHANGE_ACTIONS},
    **{kind: OptimizationRequest for kind in OPTIMIZATION_ACTIONS},
    **{kind: ExperimentRequest for kind in EXPERIMENT_ACTIONS},
    "next.ask-council": CouncilRequest,
    "next.spawn-subloop": SubloopRequest,
    **{kind: StopRequest for kind in TERMINAL_ACTIONS},
}


def action_payload_digest(payload: ActionPayload) -> str:
    return sha256_digest(
        {"action_kind": payload.action_kind, "payload": payload.to_dict()}
    )


def validate_action_payload(
    action_kind: str,
    payload: ActionPayload,
) -> list[str]:
    problems: list[str] = []
    if not ID_RE.fullmatch(action_kind):
        problems.append("action_kind must be namespaced")
    if payload.action_kind != action_kind:
        problems.append("payload action_kind differs from requested action kind")
    expected = REFERENCE_PAYLOAD_TYPES.get(action_kind)
    if expected is not None and not isinstance(payload, expected):
        problems.append(f"{action_kind} expects {expected.__name__}")
    problems.extend(payload.validate())
    return problems


__all__ = [
    "ACTION_PAYLOAD_MODEL_VERSION",
    "EXPERIMENT_ACTIONS",
    "GRAPH_CHANGE_ACTIONS",
    "OPTIMIZATION_ACTIONS",
    "REFERENCE_PAYLOAD_TYPES",
    "TERMINAL_ACTIONS",
    "ActionPayload",
    "ContextRequest",
    "CouncilRequest",
    "ExperimentRequest",
    "GraphChangeRequest",
    "OptimizationRequest",
    "ProbeRequest",
    "ResearchRequest",
    "StopRequest",
    "SubloopRequest",
    "action_payload_digest",
    "validate_action_payload",
]
