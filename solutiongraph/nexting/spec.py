"""Portable definitions for Solver Cells, missions, authority, and workspaces.

A runtime ``SolverCell`` is a composition of Python objects.  A
``SolverCellSpec`` is the immutable, serialisable contract describing what that
cell is allowed to pursue and which replaceable seams it resolves.  Keeping
these separate prevents domain roles from turning into a hierarchy of mutable
Agent/Worker/Employee subclasses.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE, canonical_json, sha256_digest
from solutiongraph.nexting.contracts import DecisionPolicy, NextBudget

CELL_SPEC_MODEL_VERSION = "0.1"
CELL_LIFECYCLES = ("finite", "continuous", "interactive")
CELL_RUN_MODES = ("execute", "plan-only", "shadow", "replay")


def _identifier(value: str, path: str, *, optional: bool = False) -> list[str]:
    if optional and not value:
        return []
    if ID_RE.fullmatch(value):
        return []
    return [f"{path} must be a namespaced identifier"]


def _digest(value: str, path: str, *, optional: bool = False) -> list[str]:
    if optional and not value:
        return []
    if DIGEST_RE.fullmatch(value):
        return []
    return [f"{path} must be a sha256 digest"]


def _identifiers(values: tuple[str, ...], path: str) -> list[str]:
    problems: list[str] = []
    if len(values) != len(set(values)):
        problems.append(f"{path} must be unique")
    if any(not ID_RE.fullmatch(value) for value in values):
        problems.append(f"{path} must contain namespaced identifiers")
    return problems


def _json_value(value: Any, path: str) -> list[str]:
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        return [f"{path} must be JSON serialisable"]
    return []


def _policy_problems(policy: DecisionPolicy, path: str) -> list[str]:
    problems = _identifier(policy.id, f"{path}.id")
    for name in (
        "utility_weight",
        "information_gain_weight",
        "confidence_weight",
        "uncertainty_penalty",
        "cost_penalty",
        "priority_weight",
        "diversity_bonus",
    ):
        value = getattr(policy, name)
        if not isfinite(value) or value < 0:
            problems.append(f"{path}.{name} must be finite and non-negative")
    if not isfinite(policy.minimum_confidence) or not 0.0 <= policy.minimum_confidence <= 1.0:
        problems.append(f"{path}.minimum_confidence must be between zero and one")
    return problems


@dataclass(frozen=True)
class MissionContract:
    """The delegated outcome for one Solver Cell, not a prompt persona."""

    id: str
    version: str
    goal: str
    success_predicate_refs: tuple[str, ...]
    objective_refs: tuple[str, ...] = ()
    hard_constraint_refs: tuple[str, ...] = ()
    required_output_kinds: tuple[str, ...] = ()
    lifecycle: str = "finite"
    parent_mission_ref: str = ""
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "mission") -> list[str]:
        problems = _identifier(self.id, f"{path}.id")
        if not self.version.strip() or not self.goal.strip():
            problems.append(f"{path}.version and goal must not be empty")
        if not self.success_predicate_refs:
            problems.append(f"{path}.success_predicate_refs must not be empty")
        for label, values in (
            ("success_predicate_refs", self.success_predicate_refs),
            ("objective_refs", self.objective_refs),
            ("hard_constraint_refs", self.hard_constraint_refs),
            ("required_output_kinds", self.required_output_kinds),
        ):
            problems.extend(_identifiers(values, f"{path}.{label}"))
        if self.lifecycle not in CELL_LIFECYCLES:
            problems.append(f"{path}.lifecycle must be one of {', '.join(CELL_LIFECYCLES)}")
        problems.extend(
            _identifier(
                self.parent_mission_ref,
                f"{path}.parent_mission_ref",
                optional=True,
            )
        )
        problems.extend(_json_value(dict(self.extensions), f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_spec_model_version": CELL_SPEC_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "goal": self.goal,
            "success_predicate_refs": list(self.success_predicate_refs),
            "objective_refs": list(self.objective_refs),
            "hard_constraint_refs": list(self.hard_constraint_refs),
            "required_output_kinds": list(self.required_output_kinds),
            "lifecycle": self.lifecycle,
            "parent_mission_ref": self.parent_mission_ref,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class CellAuthority:
    """Maximum authority the cell may request through downstream adapters."""

    id: str
    allowed_action_kinds: tuple[str, ...]
    allowed_effects: tuple[str, ...] = ()
    granted_permissions: tuple[str, ...] = ()
    allowed_runtime_ids: tuple[str, ...] = ()
    allowed_model_ids: tuple[str, ...] = ()
    allowed_research_source_kinds: tuple[str, ...] = ()
    may_spawn_subloops: bool = True
    may_request_human_review: bool = True
    may_propose_graph_changes: bool = True
    may_execute_effects: bool = False
    maximum_child_depth: int = 4
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "authority") -> list[str]:
        problems = _identifier(self.id, f"{path}.id")
        if not self.allowed_action_kinds:
            problems.append(f"{path}.allowed_action_kinds must not be empty")
        for label, values in (
            ("allowed_action_kinds", self.allowed_action_kinds),
            ("allowed_effects", self.allowed_effects),
            ("granted_permissions", self.granted_permissions),
            ("allowed_runtime_ids", self.allowed_runtime_ids),
            ("allowed_model_ids", self.allowed_model_ids),
            ("allowed_research_source_kinds", self.allowed_research_source_kinds),
        ):
            problems.extend(_identifiers(values, f"{path}.{label}"))
        if self.maximum_child_depth < 0:
            problems.append(f"{path}.maximum_child_depth must be non-negative")
        if self.may_execute_effects and not self.allowed_effects:
            problems.append(
                f"{path} cannot allow effect execution without declared allowed_effects"
            )
        problems.extend(_json_value(dict(self.extensions), f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "allowed_action_kinds": list(self.allowed_action_kinds),
            "allowed_effects": list(self.allowed_effects),
            "granted_permissions": list(self.granted_permissions),
            "allowed_runtime_ids": list(self.allowed_runtime_ids),
            "allowed_model_ids": list(self.allowed_model_ids),
            "allowed_research_source_kinds": list(
                self.allowed_research_source_kinds
            ),
            "may_spawn_subloops": self.may_spawn_subloops,
            "may_request_human_review": self.may_request_human_review,
            "may_propose_graph_changes": self.may_propose_graph_changes,
            "may_execute_effects": self.may_execute_effects,
            "maximum_child_depth": self.maximum_child_depth,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class CellWorkspace:
    """References to stores and memory scopes; it contains no mutable data."""

    id: str
    knowledge_store_ref: str
    artifact_store_ref: str
    event_journal_ref: str
    history_refs: tuple[str, ...] = ()
    blueprint_catalog_refs: tuple[str, ...] = ()
    node_registry_refs: tuple[str, ...] = ()
    package_registry_refs: tuple[str, ...] = ()
    research_archive_refs: tuple[str, ...] = ()
    secret_scope_refs: tuple[str, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "workspace") -> list[str]:
        problems = _identifier(self.id, f"{path}.id")
        for label, value in (
            ("knowledge_store_ref", self.knowledge_store_ref),
            ("artifact_store_ref", self.artifact_store_ref),
            ("event_journal_ref", self.event_journal_ref),
        ):
            problems.extend(_identifier(value, f"{path}.{label}"))
        for label, values in (
            ("history_refs", self.history_refs),
            ("blueprint_catalog_refs", self.blueprint_catalog_refs),
            ("node_registry_refs", self.node_registry_refs),
            ("package_registry_refs", self.package_registry_refs),
            ("research_archive_refs", self.research_archive_refs),
            ("secret_scope_refs", self.secret_scope_refs),
        ):
            problems.extend(_identifiers(values, f"{path}.{label}"))
        problems.extend(_json_value(dict(self.extensions), f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "knowledge_store_ref": self.knowledge_store_ref,
            "artifact_store_ref": self.artifact_store_ref,
            "event_journal_ref": self.event_journal_ref,
            "history_refs": list(self.history_refs),
            "blueprint_catalog_refs": list(self.blueprint_catalog_refs),
            "node_registry_refs": list(self.node_registry_refs),
            "package_registry_refs": list(self.package_registry_refs),
            "research_archive_refs": list(self.research_archive_refs),
            "secret_scope_refs": list(self.secret_scope_refs),
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class SolverCellSpec:
    """Portable shell for one role-neutral Solver Cell definition."""

    id: str
    version: str
    title: str
    mission: MissionContract
    authority: CellAuthority
    workspace: CellWorkspace
    strategy_ids: tuple[str, ...]
    question_factory_ref: str
    strategy_selection_policy_ref: str
    context_policy_ref: str
    action_router_ref: str
    state_reducer_ref: str
    budget: NextBudget = field(default_factory=NextBudget)
    decision_policy: DecisionPolicy = field(default_factory=DecisionPolicy)
    role_profile_refs: tuple[str, ...] = ()
    parent_cell_spec_ref: str = ""
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "cell_spec") -> list[str]:
        problems = _identifier(self.id, f"{path}.id")
        if not self.version.strip() or not self.title.strip():
            problems.append(f"{path}.version and title must not be empty")
        problems.extend(self.mission.validate(f"{path}.mission"))
        problems.extend(self.authority.validate(f"{path}.authority"))
        problems.extend(self.workspace.validate(f"{path}.workspace"))
        if not self.strategy_ids:
            problems.append(f"{path}.strategy_ids must not be empty")
        problems.extend(_identifiers(self.strategy_ids, f"{path}.strategy_ids"))
        for label, value in (
            ("question_factory_ref", self.question_factory_ref),
            ("strategy_selection_policy_ref", self.strategy_selection_policy_ref),
            ("context_policy_ref", self.context_policy_ref),
            ("action_router_ref", self.action_router_ref),
            ("state_reducer_ref", self.state_reducer_ref),
        ):
            problems.extend(_identifier(value, f"{path}.{label}"))
        problems.extend(_identifiers(self.role_profile_refs, f"{path}.role_profile_refs"))
        problems.extend(
            _identifier(
                self.parent_cell_spec_ref,
                f"{path}.parent_cell_spec_ref",
                optional=True,
            )
        )
        problems.extend(self.budget.validate())
        problems.extend(_policy_problems(self.decision_policy, f"{path}.decision_policy"))
        if set(self.authority.allowed_action_kinds).isdisjoint(
            self.mission.required_output_kinds
        ) is False:
            problems.append(
                f"{path}.required_output_kinds describe outputs, not action kinds"
            )
        if self.budget.max_depth > self.authority.maximum_child_depth:
            problems.append(
                f"{path}.budget.max_depth exceeds authority.maximum_child_depth"
            )
        problems.extend(_json_value(dict(self.extensions), f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_spec_model_version": CELL_SPEC_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "mission": self.mission.to_dict(),
            "authority": self.authority.to_dict(),
            "workspace": self.workspace.to_dict(),
            "strategy_ids": list(self.strategy_ids),
            "question_factory_ref": self.question_factory_ref,
            "strategy_selection_policy_ref": self.strategy_selection_policy_ref,
            "context_policy_ref": self.context_policy_ref,
            "action_router_ref": self.action_router_ref,
            "state_reducer_ref": self.state_reducer_ref,
            "budget": self.budget.to_dict(),
            "decision_policy": self.decision_policy.to_dict(),
            "role_profile_refs": list(self.role_profile_refs),
            "parent_cell_spec_ref": self.parent_cell_spec_ref,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class CellRunRequest:
    """One exact invocation of a portable cell specification."""

    id: str
    cell_spec_digest: str
    initial_state_digest: str
    mode: str = "execute"
    parent_run_ref: str = ""
    delegated_scope_ref: str = ""
    random_seed: int = 0
    budget_override: Mapping[str, Any] = field(default_factory=dict)
    context_override_ref: str = ""
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "cell_run") -> list[str]:
        problems = _identifier(self.id, f"{path}.id")
        problems.extend(_digest(self.cell_spec_digest, f"{path}.cell_spec_digest"))
        problems.extend(_digest(self.initial_state_digest, f"{path}.initial_state_digest"))
        if self.mode not in CELL_RUN_MODES:
            problems.append(f"{path}.mode must be one of {', '.join(CELL_RUN_MODES)}")
        for label, value in (
            ("parent_run_ref", self.parent_run_ref),
            ("delegated_scope_ref", self.delegated_scope_ref),
            ("context_override_ref", self.context_override_ref),
        ):
            problems.extend(_identifier(value, f"{path}.{label}", optional=True))
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
            problems.append(f"{path}.random_seed must be an integer")
        problems.extend(_json_value(dict(self.budget_override), f"{path}.budget_override"))
        problems.extend(_json_value(dict(self.extensions), f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_spec_model_version": CELL_SPEC_MODEL_VERSION,
            "id": self.id,
            "cell_spec_digest": self.cell_spec_digest,
            "initial_state_digest": self.initial_state_digest,
            "mode": self.mode,
            "parent_run_ref": self.parent_run_ref,
            "delegated_scope_ref": self.delegated_scope_ref,
            "random_seed": self.random_seed,
            "budget_override": dict(self.budget_override),
            "context_override_ref": self.context_override_ref,
            "extensions": dict(self.extensions),
        }


__all__ = [
    "CELL_LIFECYCLES",
    "CELL_RUN_MODES",
    "CELL_SPEC_MODEL_VERSION",
    "CellAuthority",
    "CellRunRequest",
    "CellWorkspace",
    "MissionContract",
    "SolverCellSpec",
]
