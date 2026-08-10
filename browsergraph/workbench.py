"""Canonical search-space model and self-contained stage-matrix explorer.

The model deliberately separates four things that are easy to conflate:

``MacroStageDefinition``
    One conceptual task phase containing an ordered submatrix of substeps.
``StageDefinition``
    One atomic ordered substep. Substeps become the selectable left-to-right
    columns inside their macro-stage submatrix.
``NodeManifest``
    One reusable implementation definition and its technical contract.
``NodeCandidate``
    One concrete, atomic parameter binding selectable inside a stage.
``SolutionDefinition``
    One route selecting exactly one candidate from every atomic substep.

``FeedbackDefinition`` and ``OptimizationProfile`` describe the learning and
control plane. They consume receipts and rank alternatives but never become
ordered task stages. ``ExecutionReceipt`` preserves observed evidence, while
``OptimizationDecision`` makes a stage- or route-selection rationale
inspectable. The viewer is a projection of this serialisable model. Execution
remains in :mod:`browsergraph.graph`.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from importlib.resources import files
from itertools import product
from math import isfinite, prod
from pathlib import Path
from typing import Any

from browsergraph.manifest import NODE_ID_RE, NodeManifest

WORKBENCH_SCHEMA_VERSION = "2.0"
WORKBENCH_VIEWS = ("matrix", "network", "compare", "builder", "feedback")


def _slug(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return slug or "value"


def candidate_id(node_id: str, parameters: dict[str, Any] | None = None) -> str:
    """Return a stable readable ID for one concrete node parameter binding."""
    parameters = parameters or {}
    if not parameters:
        return node_id
    payload = json.dumps(parameters, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]
    values = "-".join(_slug(value)[:18] for _, value in sorted(parameters.items()))
    return f"{node_id}--{values}-{digest}"


@dataclass(frozen=True)
class FeedbackDefinition:
    """One typed receipt channel outside the ordered execution stages."""

    id: str
    name: str
    signal: str
    scope: str
    producer: str
    consumer: str
    action: str
    description: str = ""
    required: bool = False

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not NODE_ID_RE.fullmatch(self.id):
            problems.append(f"id {self.id!r} must be a lowercase namespaced identifier")
        for field_name in ("name", "signal", "scope", "producer", "consumer", "action"):
            if not str(getattr(self, field_name)).strip():
                problems.append(f"{field_name} must not be empty")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "signal": self.signal,
            "scope": self.scope,
            "producer": self.producer,
            "consumer": self.consumer,
            "action": self.action,
            "description": self.description,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedbackDefinition:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            signal=str(data["signal"]),
            scope=str(data["scope"]),
            producer=str(data["producer"]),
            consumer=str(data["consumer"]),
            action=str(data["action"]),
            description=str(data.get("description", "")),
            required=bool(data.get("required", False)),
        )


@dataclass(frozen=True)
class OptimizationObjective:
    """One metric direction and weight in a route recommendation profile."""

    metric: str
    direction: str
    weight: float

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.metric.strip():
            problems.append("metric must not be empty")
        if self.direction not in ("maximize", "minimize"):
            problems.append("direction must be 'maximize' or 'minimize'")
        if not isfinite(self.weight) or self.weight < 0:
            problems.append("weight must be a finite non-negative number")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "direction": self.direction,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OptimizationObjective:
        return cls(
            metric=str(data["metric"]),
            direction=str(data["direction"]),
            weight=float(data["weight"]),
        )


@dataclass(frozen=True)
class OptimizationProfile:
    """A data-driven route-ranking policy, never an execution stage."""

    id: str
    name: str
    objectives: tuple[OptimizationObjective, ...]
    strategy: str = "normalized_weighted_score"
    description: str = ""
    minimum_evidence: float = 0.0
    exploration: float = 0.0

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not NODE_ID_RE.fullmatch(self.id):
            problems.append(f"id {self.id!r} must be a lowercase namespaced identifier")
        if not self.name.strip():
            problems.append("name must not be empty")
        if not self.strategy.strip():
            problems.append("strategy must not be empty")
        if not self.objectives:
            problems.append("at least one objective is required")
        for index, objective in enumerate(self.objectives):
            problems.extend(
                f"objective {index}: {problem}"
                for problem in objective.validate())
        objective_metrics = [objective.metric for objective in self.objectives]
        duplicate_metrics = sorted({
            metric for metric in objective_metrics
            if objective_metrics.count(metric) > 1
        })
        if duplicate_metrics:
            problems.append(
                "duplicate objective metric(s): " + ", ".join(duplicate_metrics))
        if self.objectives and sum(objective.weight for objective in self.objectives) <= 0:
            problems.append("objective weights must sum to more than zero")
        if not isfinite(self.minimum_evidence) or self.minimum_evidence < 0:
            problems.append("minimum_evidence must be finite and non-negative")
        if not isfinite(self.exploration) or not 0 <= self.exploration <= 1:
            problems.append("exploration must be between 0 and 1")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "strategy": self.strategy,
            "objectives": [objective.to_dict() for objective in self.objectives],
            "minimum_evidence": self.minimum_evidence,
            "exploration": self.exploration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OptimizationProfile:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            strategy=str(data.get("strategy", "normalized_weighted_score")),
            objectives=tuple(
                OptimizationObjective.from_dict(objective)
                for objective in data.get("objectives") or ()),
            minimum_evidence=float(data.get("minimum_evidence", 0.0)),
            exploration=float(data.get("exploration", 0.0)),
        )


@dataclass(frozen=True)
class ExecutionReceipt:
    """One immutable route execution and verification evidence record."""

    id: str
    solution_id: str
    outcome: str
    accepted: bool | None = None
    verifier: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    stage_outcomes: dict[str, dict[str, Any]] = field(default_factory=dict)
    macro_stage_outcomes: dict[str, dict[str, Any]] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    evidence_source: str = ""
    started_at: str = ""
    completed_at: str = ""
    failure_class: str = ""

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not NODE_ID_RE.fullmatch(self.id):
            problems.append(f"id {self.id!r} must be a lowercase namespaced identifier")
        if not NODE_ID_RE.fullmatch(self.solution_id):
            problems.append(
                f"solution_id {self.solution_id!r} must be a lowercase namespaced identifier")
        if not self.outcome.strip():
            problems.append("outcome must not be empty")
        if self.accepted is not None and not isinstance(self.accepted, bool):
            problems.append("accepted must be boolean or null")
        for field_name in (
            "metrics", "stage_outcomes", "macro_stage_outcomes", "provenance"):
            if not isinstance(getattr(self, field_name), dict):
                problems.append(f"{field_name} must be an object")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "solution_id": self.solution_id,
            "outcome": self.outcome,
            "accepted": self.accepted,
            "verifier": self.verifier,
            "metrics": dict(self.metrics),
            "stage_outcomes": {
                stage_id: dict(outcome)
                for stage_id, outcome in self.stage_outcomes.items()
            },
            "macro_stage_outcomes": {
                stage_id: dict(outcome)
                for stage_id, outcome in self.macro_stage_outcomes.items()
            },
            "provenance": dict(self.provenance),
            "evidence_source": self.evidence_source,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "failure_class": self.failure_class,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionReceipt:
        return cls(
            id=str(data["id"]),
            solution_id=str(data["solution_id"]),
            outcome=str(data["outcome"]),
            accepted=data.get("accepted"),
            verifier=str(data.get("verifier", "")),
            metrics=dict(data.get("metrics") or {}),
            stage_outcomes={
                str(stage_id): dict(outcome)
                for stage_id, outcome in (data.get("stage_outcomes") or {}).items()
            },
            macro_stage_outcomes={
                str(stage_id): dict(outcome)
                for stage_id, outcome in (data.get("macro_stage_outcomes") or {}).items()
            },
            provenance=dict(data.get("provenance") or {}),
            evidence_source=str(data.get("evidence_source", "")),
            started_at=str(data.get("started_at", "")),
            completed_at=str(data.get("completed_at", "")),
            failure_class=str(data.get("failure_class", "")),
        )


@dataclass(frozen=True)
class OptimizationDecision:
    """An inspectable substep-, macro-stage-, or route-level decision trace."""

    id: str
    scope: str
    profile_id: str
    selected: dict[str, str]
    eligible_count: int
    rejected_count: int = 0
    score: float | None = None
    objective_values: dict[str, Any] = field(default_factory=dict)
    contributions: dict[str, float] = field(default_factory=dict)
    alternatives: tuple[str, ...] = ()
    evidence_snapshot: str = ""
    reason: str = ""
    created_at: str = ""

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not NODE_ID_RE.fullmatch(self.id):
            problems.append(f"id {self.id!r} must be a lowercase namespaced identifier")
        if self.scope not in ("stage", "substep", "macro_stage", "route"):
            problems.append(
                "scope must be 'substep', 'macro_stage', or 'route' "
                "('stage' is accepted for legacy data)")
        if self.profile_id and not NODE_ID_RE.fullmatch(self.profile_id):
            problems.append("profile_id must be a lowercase namespaced identifier")
        if not self.selected:
            problems.append("selected must contain at least one stage candidate")
        if not isinstance(self.eligible_count, int) or self.eligible_count < 0:
            problems.append("eligible_count must be a non-negative integer")
        if not isinstance(self.rejected_count, int) or self.rejected_count < 0:
            problems.append("rejected_count must be a non-negative integer")
        if self.score is not None and not isfinite(self.score):
            problems.append("score must be finite or null")
        for field_name in ("selected", "objective_values", "contributions"):
            if not isinstance(getattr(self, field_name), dict):
                problems.append(f"{field_name} must be an object")
        if len(set(self.alternatives)) != len(self.alternatives):
            problems.append("alternatives must not contain duplicates")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scope": self.scope,
            "profile_id": self.profile_id,
            "selected": dict(self.selected),
            "eligible_count": self.eligible_count,
            "rejected_count": self.rejected_count,
            "score": self.score,
            "objective_values": dict(self.objective_values),
            "contributions": dict(self.contributions),
            "alternatives": list(self.alternatives),
            "evidence_snapshot": self.evidence_snapshot,
            "reason": self.reason,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OptimizationDecision:
        return cls(
            id=str(data["id"]),
            scope=str(data["scope"]),
            profile_id=str(data.get("profile_id", "")),
            selected={str(k): str(v) for k, v in (data.get("selected") or {}).items()},
            eligible_count=int(data.get("eligible_count", 0)),
            rejected_count=int(data.get("rejected_count", 0)),
            score=(None if data.get("score") is None else float(data["score"])),
            objective_values=dict(data.get("objective_values") or {}),
            contributions={
                str(metric): float(value)
                for metric, value in (data.get("contributions") or {}).items()
            },
            alternatives=tuple(data.get("alternatives") or ()),
            evidence_snapshot=str(data.get("evidence_snapshot", "")),
            reason=str(data.get("reason", "")),
            created_at=str(data.get("created_at", "")),
        )


@dataclass(frozen=True)
class NodeCandidate:
    """One atomic, selectable binding of a reusable node definition."""

    id: str
    node_id: str
    name: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    def resolved_parameters(self, manifest: NodeManifest) -> dict[str, Any]:
        resolved = {
            parameter.name: parameter.default
            for parameter in manifest.parameters
            if parameter.default is not None
        }
        resolved.update(self.parameters)
        return resolved

    def display_name(self, manifest: NodeManifest) -> str:
        if self.name:
            return self.name
        resolved = self.resolved_parameters(manifest)
        if not resolved:
            return manifest.name
        values = " · ".join(str(resolved[name]) for name in sorted(resolved))
        return f"{manifest.name} · {values}"

    def validate(self, manifest: NodeManifest | None) -> list[str]:
        problems: list[str] = []
        if not NODE_ID_RE.fullmatch(self.id):
            problems.append(f"id {self.id!r} must be a lowercase namespaced identifier")
        if not NODE_ID_RE.fullmatch(self.node_id):
            problems.append(
                f"node_id {self.node_id!r} must be a lowercase namespaced identifier")
        if manifest is None:
            problems.append(f"references unknown node definition {self.node_id}")
            return problems

        specs = {parameter.name: parameter for parameter in manifest.parameters}
        unknown = sorted(set(self.parameters) - set(specs))
        if unknown:
            problems.append("unknown parameter(s): " + ", ".join(unknown))
        resolved = self.resolved_parameters(manifest)
        for parameter in manifest.parameters:
            value = resolved.get(parameter.name)
            if parameter.required and value is None:
                problems.append(f"required parameter {parameter.name} is not bound")
            if parameter.choices and value not in parameter.choices:
                problems.append(
                    f"parameter {parameter.name}={value!r} is not one of "
                    f"{list(parameter.choices)!r}")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_id": self.node_id,
            "name": self.name,
            "parameters": dict(self.parameters),
            "description": self.description,
            "metrics": dict(self.metrics),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeCandidate:
        return cls(
            id=str(data["id"]),
            node_id=str(data["node_id"]),
            name=str(data.get("name", "")),
            parameters=dict(data.get("parameters") or {}),
            description=str(data.get("description", "")),
            metrics=dict(data.get("metrics") or {}),
            tags=tuple(data.get("tags") or ()),
        )


def expand_node_candidates(nodes: tuple[NodeManifest, ...] | list[NodeManifest]) -> tuple[NodeCandidate, ...]:
    """Materialize every declared parameter choice as an atomic candidate.

    There is intentionally no top-k limit. A definition with three browser
    controllers, two binaries and two display modes becomes twelve visible
    candidates. Definitions without enumerated choices become one candidate.
    """
    candidates: list[NodeCandidate] = []
    for manifest in nodes:
        varying = [parameter for parameter in manifest.parameters if parameter.choices]
        fixed = {
            parameter.name: parameter.default
            for parameter in manifest.parameters
            if not parameter.choices and parameter.default is not None
        }
        combinations = product(*(parameter.choices for parameter in varying)) if varying else [()]
        for values in combinations:
            parameters = dict(fixed)
            parameters.update({
                parameter.name: value
                for parameter, value in zip(varying, values, strict=True)
            })
            display_values = [str(parameters[parameter.name]) for parameter in manifest.parameters
                              if parameter.name in parameters]
            name = manifest.name
            if display_values:
                name += " · " + " · ".join(display_values)
            candidates.append(NodeCandidate(
                id=candidate_id(manifest.id, parameters),
                node_id=manifest.id,
                name=name,
                parameters=parameters,
                metrics=dict(manifest.metrics),
                tags=tuple(dict.fromkeys((*manifest.tags, *manifest.roles))),
            ))
    return tuple(candidates)


@dataclass(frozen=True)
class MacroStageDefinition:
    """One conceptual phase grouping a contiguous ordered substep submatrix."""

    id: str
    name: str
    input_type: str
    output_type: str
    success: str
    substeps: tuple[str, ...]
    description: str = ""
    optional: bool = False

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not NODE_ID_RE.fullmatch(self.id):
            problems.append(f"id {self.id!r} must be a lowercase namespaced identifier")
        for field_name in ("name", "input_type", "output_type", "success"):
            if not str(getattr(self, field_name)).strip():
                problems.append(f"{field_name} must not be empty")
        if not self.substeps:
            problems.append("at least one ordered substep is required")
        if any(not isinstance(value, str) or not value.strip() for value in self.substeps):
            problems.append("substeps must contain non-empty identifiers")
        duplicates = sorted({value for value in self.substeps
                             if self.substeps.count(value) > 1})
        if duplicates:
            problems.append("duplicate substep(s): " + ", ".join(duplicates))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "input_type": self.input_type,
            "output_type": self.output_type,
            "success": self.success,
            "optional": self.optional,
            "substeps": list(self.substeps),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MacroStageDefinition:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            input_type=str(data.get("input_type", "any")),
            output_type=str(data.get("output_type", "any")),
            success=str(data.get("success", "")),
            optional=bool(data.get("optional", False)),
            substeps=tuple(data.get("substeps") or ()),
        )


@dataclass(frozen=True)
class StageDefinition:
    """One atomic ordered substep and its complete candidate set.

    ``macro_stage_id`` is optional for backwards compatibility. When a
    workbench declares macro stages, every substep must belong to exactly one
    macro stage and macro-stage membership must be contiguous.
    """

    id: str
    name: str
    input_type: str
    output_type: str
    success: str
    candidates: tuple[str, ...] = ()
    description: str = ""
    optional: bool = False
    variant_axes: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    macro_stage_id: str = ""

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not NODE_ID_RE.fullmatch(self.id):
            problems.append(f"id {self.id!r} must be a lowercase namespaced identifier")
        for field_name in ("name", "input_type", "output_type", "success"):
            if not str(getattr(self, field_name)).strip():
                problems.append(f"{field_name} must not be empty")
        for field_name in ("variant_axes", "required_capabilities"):
            values = getattr(self, field_name)
            if any(not isinstance(value, str) or not value.strip() for value in values):
                problems.append(f"{field_name} values must be non-empty strings")
            duplicates = sorted({value for value in values if values.count(value) > 1})
            if duplicates:
                problems.append(
                    f"duplicate {field_name}: " + ", ".join(duplicates))
        if self.macro_stage_id and not NODE_ID_RE.fullmatch(self.macro_stage_id):
            problems.append(
                "macro_stage_id must be a lowercase namespaced identifier")
        return problems

    def compatibility_problems(self, node: NodeManifest) -> list[str]:
        problems: list[str] = []
        missing_capabilities = sorted(
            set(self.required_capabilities) - set(node.capabilities))
        if missing_capabilities:
            problems.append(
                "missing capability/capabilities " + ", ".join(missing_capabilities))

        pass_through = (
            "pass_through" in node.roles or "pass_through" in node.capabilities)
        if pass_through and not self.optional:
            problems.append("pass-through is allowed only on optional stages")
        if not _has_type(node.inputs, self.input_type):
            problems.append(f"does not accept {self.input_type}")
        if not _has_type(node.outputs, self.output_type):
            verb = "certify" if pass_through else "produce"
            problems.append(f"does not {verb} {self.output_type}")
        return problems

    def accepts(self, node: NodeManifest) -> bool:
        return not self.compatibility_problems(node)

    def discover_candidates(
        self,
        nodes: tuple[NodeManifest, ...] | list[NodeManifest],
        candidates: tuple[NodeCandidate, ...] | list[NodeCandidate] | None = None,
    ) -> tuple[str, ...]:
        node_map = {node.id: node for node in nodes}
        available = (candidates if candidates is not None else tuple(
            NodeCandidate(id=node.id, node_id=node.id) for node in nodes))
        return tuple(
            candidate.id
            for candidate in available
            if candidate.node_id in node_map
            and not candidate.validate(node_map[candidate.node_id])
            and self.accepts(node_map[candidate.node_id])
        )

    def with_discovered_candidates(
        self,
        nodes: tuple[NodeManifest, ...] | list[NodeManifest],
        candidates: tuple[NodeCandidate, ...] | list[NodeCandidate] | None = None,
    ) -> StageDefinition:
        return replace(self, candidates=self.discover_candidates(nodes, candidates))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "input_type": self.input_type,
            "output_type": self.output_type,
            "success": self.success,
            "optional": self.optional,
            "variant_axes": list(self.variant_axes),
            "required_capabilities": list(self.required_capabilities),
            "macro_stage_id": self.macro_stage_id,
            "candidates": list(self.candidates),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageDefinition:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            input_type=str(data.get("input_type", "any")),
            output_type=str(data.get("output_type", "any")),
            success=str(data.get("success", "")),
            optional=bool(data.get("optional", False)),
            variant_axes=tuple(data.get("variant_axes") or ()),
            required_capabilities=tuple(data.get("required_capabilities") or ()),
            macro_stage_id=str(data.get("macro_stage_id", "")),
            candidates=tuple(data.get("candidates") or ()),
        )


# Compatibility for code written against the first workbench prototype. The
# canonical term is now Stage: planes, contracts and optimizers are not steps.
PlaneDefinition = StageDefinition


@dataclass(frozen=True)
class SolutionDefinition:
    """One complete route with one primary candidate per atomic substep."""

    id: str
    name: str
    route: dict[str, str]
    description: str = ""
    fallbacks: dict[str, tuple[str, ...]] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    status: str = "candidate"
    tags: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not NODE_ID_RE.fullmatch(self.id):
            problems.append(f"id {self.id!r} must be a lowercase namespaced identifier")
        if not self.name.strip():
            problems.append("name must not be empty")
        if not self.status.strip():
            problems.append("status must not be empty")
        if any(not isinstance(tag, str) or not tag.strip() for tag in self.tags):
            problems.append("tags must be non-empty strings")
        duplicate_tags = sorted({tag for tag in self.tags if self.tags.count(tag) > 1})
        if duplicate_tags:
            problems.append("duplicate tag(s): " + ", ".join(duplicate_tags))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "route": dict(self.route),
            "fallbacks": {stage: list(nodes) for stage, nodes in self.fallbacks.items()},
            "metrics": dict(self.metrics),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SolutionDefinition:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            status=str(data.get("status", "candidate")),
            route={str(k): str(v) for k, v in (data.get("route") or {}).items()},
            fallbacks={str(k): tuple(v) for k, v in (data.get("fallbacks") or {}).items()},
            metrics=dict(data.get("metrics") or {}),
            tags=tuple(data.get("tags") or ()),
        )


def _has_type(ports: tuple, expected: str) -> bool:
    if expected in ("", "any"):
        return True
    if expected in ("none", "void"):
        return not ports
    return any(port.data_type in ("any", expected) for port in ports)


def _ports_connect(outputs: tuple, inputs: tuple) -> bool:
    if not inputs:
        return True
    if not outputs:
        return False
    return any(
        out.data_type == "any" or inp.data_type == "any" or out.data_type == inp.data_type
        for out in outputs for inp in inputs
    )


def _stage_types_connect(output_type: str, input_type: str) -> bool:
    """Return whether two adjacent declared stage contracts can connect."""
    if output_type in ("", "any") or input_type in ("", "any"):
        return True
    if output_type in ("none", "void") or input_type in ("none", "void"):
        return output_type in ("none", "void") and input_type in ("none", "void")
    return output_type == input_type


@dataclass(frozen=True)
class WorkbenchDefinition:
    """Definitions, macro stages, atomic substeps, candidates, and routes."""

    title: str
    task: str
    success: str
    nodes: tuple[NodeManifest, ...]
    stages: tuple[StageDefinition, ...]
    solutions: tuple[SolutionDefinition, ...]
    macro_stages: tuple[MacroStageDefinition, ...] = ()
    candidates: tuple[NodeCandidate, ...] = ()
    feedback_channels: tuple[FeedbackDefinition, ...] = ()
    optimization_profiles: tuple[OptimizationProfile, ...] = ()
    receipts: tuple[ExecutionReceipt, ...] = ()
    optimization_decisions: tuple[OptimizationDecision, ...] = ()
    schema_version: str = WORKBENCH_SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def planes(self) -> tuple[StageDefinition, ...]:
        """Deprecated compatibility alias; viewer and wire format use ``stages``."""
        return self.stages

    @property
    def route_count(self) -> int:
        """Number of routes selecting one candidate per atomic substep."""
        return prod(len(stage.candidates) for stage in self.stages)

    def effective_candidates(self) -> tuple[NodeCandidate, ...]:
        if self.candidates:
            return self.candidates
        return tuple(NodeCandidate(id=node.id, node_id=node.id) for node in self.nodes)

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.schema_version != WORKBENCH_SCHEMA_VERSION:
            problems.append(
                f"schema_version must be {WORKBENCH_SCHEMA_VERSION!r}, "
                f"got {self.schema_version!r}")
        if not self.title.strip():
            problems.append("title must not be empty")
        if not self.stages:
            problems.append("at least one ordered stage is required")

        def duplicates(values: list[str]) -> list[str]:
            return sorted({value for value in values if values.count(value) > 1})

        atomic_candidates = self.effective_candidates()
        node_ids = [node.id for node in self.nodes]
        candidate_ids = [candidate.id for candidate in atomic_candidates]
        stage_ids = [stage.id for stage in self.stages]
        macro_stage_ids = [stage.id for stage in self.macro_stages]
        solution_ids = [solution.id for solution in self.solutions]
        feedback_ids = [channel.id for channel in self.feedback_channels]
        profile_ids = [profile.id for profile in self.optimization_profiles]
        receipt_ids = [receipt.id for receipt in self.receipts]
        decision_ids = [decision.id for decision in self.optimization_decisions]
        for label, values in (
            ("node", node_ids), ("candidate", candidate_ids),
            ("macro stage", macro_stage_ids), ("stage", stage_ids),
            ("solution", solution_ids),
            ("feedback channel", feedback_ids),
            ("optimization profile", profile_ids),
            ("receipt", receipt_ids), ("optimization decision", decision_ids),
        ):
            duplicate_ids = duplicates(values)
            if duplicate_ids:
                problems.append(f"duplicate {label} id(s): {', '.join(duplicate_ids)}")
        hierarchy_collisions = sorted(set(macro_stage_ids).intersection(stage_ids))
        if hierarchy_collisions:
            problems.append(
                "macro-stage IDs must not reuse substep IDs: "
                + ", ".join(hierarchy_collisions))

        node_map = {node.id: node for node in self.nodes}
        candidate_map = {candidate.id: candidate for candidate in atomic_candidates}
        for node in self.nodes:
            problems.extend(f"node {node.id}: {problem}" for problem in node.validate())
        for candidate in atomic_candidates:
            manifest = node_map.get(candidate.node_id)
            problems.extend(
                f"candidate {candidate.id}: {problem}"
                for problem in candidate.validate(manifest))
        for stage in self.stages:
            problems.extend(
                f"stage {stage.id}: {problem}"
                for problem in stage.validate())
        for macro_stage in self.macro_stages:
            problems.extend(
                f"macro stage {macro_stage.id}: {problem}"
                for problem in macro_stage.validate())
        for solution in self.solutions:
            problems.extend(
                f"solution {solution.id}: {problem}"
                for problem in solution.validate())
        for channel in self.feedback_channels:
            problems.extend(
                f"feedback channel {channel.id}: {problem}"
                for problem in channel.validate())
        for profile in self.optimization_profiles:
            problems.extend(
                f"optimization profile {profile.id}: {problem}"
                for problem in profile.validate())
        for receipt in self.receipts:
            problems.extend(
                f"receipt {receipt.id}: {problem}"
                for problem in receipt.validate())
            if receipt.solution_id not in solution_ids:
                problems.append(
                    f"receipt {receipt.id} references unknown solution "
                    f"{receipt.solution_id}")
            unknown_receipt_stages = (
                sorted(set(receipt.stage_outcomes) - set(stage_ids))
                if isinstance(receipt.stage_outcomes, dict) else [])
            if unknown_receipt_stages:
                problems.append(
                    f"receipt {receipt.id} has outcomes for unknown stage(s): "
                    + ", ".join(unknown_receipt_stages))
            unknown_receipt_macro_stages = (
                sorted(set(receipt.macro_stage_outcomes) - set(macro_stage_ids))
                if isinstance(receipt.macro_stage_outcomes, dict) else [])
            if unknown_receipt_macro_stages:
                problems.append(
                    f"receipt {receipt.id} has outcomes for unknown macro stage(s): "
                    + ", ".join(unknown_receipt_macro_stages))
        for decision in self.optimization_decisions:
            problems.extend(
                f"optimization decision {decision.id}: {problem}"
                for problem in decision.validate())
            if decision.profile_id and decision.profile_id not in profile_ids:
                problems.append(
                    f"optimization decision {decision.id} references unknown profile "
                    f"{decision.profile_id}")
            selected_items = (
                decision.selected.items()
                if isinstance(decision.selected, dict) else ())
            for selected_stage, selected_candidate in selected_items:
                if selected_stage not in stage_ids:
                    problems.append(
                        f"optimization decision {decision.id} selects unknown stage "
                        f"{selected_stage}")
                    continue
                stage = self.stages[stage_ids.index(selected_stage)]
                if selected_candidate not in stage.candidates:
                    problems.append(
                        f"optimization decision {decision.id}: {selected_candidate} "
                        f"is not a candidate for {selected_stage}")
            for alternative in decision.alternatives:
                if alternative not in candidate_ids:
                    problems.append(
                        f"optimization decision {decision.id} references unknown "
                        f"alternative {alternative}")

        category_collisions = sorted(
            set(stage_ids + macro_stage_ids).intersection(feedback_ids + profile_ids))
        if category_collisions:
            problems.append(
                "control-plane IDs must not reuse task-stage IDs: "
                + ", ".join(category_collisions))

        if self.macro_stages:
            stage_map = {stage.id: stage for stage in self.stages}
            declared_substeps: list[str] = []
            for macro_stage in self.macro_stages:
                declared_substeps.extend(macro_stage.substeps)
                if not macro_stage.substeps:
                    continue
                unknown = sorted(set(macro_stage.substeps) - set(stage_ids))
                if unknown:
                    problems.append(
                        f"macro stage {macro_stage.id} references unknown substep(s): "
                        + ", ".join(unknown))
                    continue
                for substep_id in macro_stage.substeps:
                    substep = stage_map[substep_id]
                    if substep.macro_stage_id != macro_stage.id:
                        problems.append(
                            f"substep {substep.id} declares macro stage "
                            f"{substep.macro_stage_id!r}, expected {macro_stage.id!r}")
                first = stage_map[macro_stage.substeps[0]]
                last = stage_map[macro_stage.substeps[-1]]
                if not _stage_types_connect(macro_stage.input_type, first.input_type):
                    problems.append(
                        f"macro stage {macro_stage.id} input {macro_stage.input_type} "
                        f"does not connect to first substep input {first.input_type}")
                if not _stage_types_connect(last.output_type, macro_stage.output_type):
                    problems.append(
                        f"macro stage {macro_stage.id} output {macro_stage.output_type} "
                        f"does not match last substep output {last.output_type}")
            duplicate_substeps = duplicates(declared_substeps)
            if duplicate_substeps:
                problems.append(
                    "substep(s) assigned to multiple macro stages: "
                    + ", ".join(duplicate_substeps))
            missing_substeps = sorted(set(stage_ids) - set(declared_substeps))
            if missing_substeps:
                problems.append(
                    "substep(s) not assigned to a macro stage: "
                    + ", ".join(missing_substeps))
            if declared_substeps != stage_ids:
                problems.append(
                    "macro-stage substeps must preserve the global contiguous stage order")
        else:
            unexpected_parents = sorted(
                stage.id for stage in self.stages if stage.macro_stage_id)
            if unexpected_parents:
                problems.append(
                    "stages declare macro_stage_id but macro_stages is empty: "
                    + ", ".join(unexpected_parents))

        for left, right in zip(self.stages, self.stages[1:], strict=False):
            if not _stage_types_connect(left.output_type, right.input_type):
                problems.append(
                    f"stage boundary {left.id} → {right.id}: "
                    f"{left.output_type} does not connect to {right.input_type}")

        for stage in self.stages:
            if not stage.candidates:
                problems.append(f"stage {stage.id} has no candidates")
            duplicate_candidates = duplicates(list(stage.candidates))
            if duplicate_candidates:
                problems.append(
                    f"stage {stage.id} repeats candidate(s): "
                    + ", ".join(duplicate_candidates))
            for candidate_id_value in stage.candidates:
                candidate = candidate_map.get(candidate_id_value)
                if candidate is None:
                    problems.append(
                        f"stage {stage.id} references unknown candidate {candidate_id_value}")
                    continue
                manifest = node_map.get(candidate.node_id)
                if manifest is None:
                    continue
                for problem in stage.compatibility_problems(manifest):
                    problems.append(
                        f"stage {stage.id}: {candidate_id_value} {problem}")

            eligible = set(stage.discover_candidates(
                list(self.nodes), list(atomic_candidates)))
            omitted = sorted(eligible - set(stage.candidates))
            if omitted:
                problems.append(
                    f"stage {stage.id} omits compatible candidate(s): "
                    + ", ".join(omitted))

        expected_route = set(stage_ids)
        for solution in self.solutions:
            route_keys = set(solution.route)
            if route_keys != expected_route:
                missing = sorted(expected_route - route_keys)
                extra = sorted(route_keys - expected_route)
                if missing:
                    problems.append(
                        f"solution {solution.id} omits stage(s): {', '.join(missing)}")
                if extra:
                    problems.append(
                        f"solution {solution.id} has unknown stage(s): {', '.join(extra)}")
            unknown_fallback_stages = sorted(
                set(solution.fallbacks) - expected_route)
            if unknown_fallback_stages:
                problems.append(
                    f"solution {solution.id} has fallbacks for unknown stage(s): "
                    + ", ".join(unknown_fallback_stages))

            selected_nodes: list[NodeManifest] = []
            for stage in self.stages:
                selected_id = solution.route.get(stage.id)
                if selected_id is None:
                    continue
                if selected_id not in stage.candidates:
                    problems.append(
                        f"solution {solution.id}: {selected_id} is not a candidate "
                        f"for {stage.id}")
                    continue
                candidate = candidate_map.get(selected_id)
                if candidate is None:
                    problems.append(
                        f"solution {solution.id}: {selected_id} is not in the "
                        "candidate registry")
                    continue
                manifest = node_map.get(candidate.node_id)
                if manifest is None:
                    continue
                selected_nodes.append(manifest)
                fallbacks = solution.fallbacks.get(stage.id, ())
                if selected_id in fallbacks:
                    problems.append(
                        f"solution {solution.id}: primary {selected_id} is also a fallback")
                if len(set(fallbacks)) != len(fallbacks):
                    problems.append(
                        f"solution {solution.id}: duplicate fallback in {stage.id}")
                for fallback in fallbacks:
                    if fallback not in stage.candidates:
                        problems.append(
                            f"solution {solution.id}: fallback {fallback} is not a "
                            f"candidate for {stage.id}")

            for index in range(len(selected_nodes) - 1):
                left, right = selected_nodes[index], selected_nodes[index + 1]
                if not _ports_connect(left.outputs, right.inputs):
                    problems.append(
                        f"solution {solution.id}: {left.id} outputs do not connect "
                        f"to {right.id} inputs")

        return problems

    def assert_valid(self) -> WorkbenchDefinition:
        problems = self.validate()
        if problems:
            raise ValueError("invalid workbench:\n  - " + "\n  - ".join(problems))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "title": self.title,
            "task": self.task,
            "success": self.success,
            "nodes": [node.to_dict() for node in self.nodes],
            "candidates": [candidate.to_dict()
                           for candidate in self.effective_candidates()],
            "macro_stages": [stage.to_dict() for stage in self.macro_stages],
            "stages": [stage.to_dict() for stage in self.stages],
            "solutions": [solution.to_dict() for solution in self.solutions],
            "feedback_channels": [
                channel.to_dict() for channel in self.feedback_channels],
            "optimization_profiles": [
                profile.to_dict() for profile in self.optimization_profiles],
            "receipts": [receipt.to_dict() for receipt in self.receipts],
            "optimization_decisions": [
                decision.to_dict() for decision in self.optimization_decisions],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkbenchDefinition:
        legacy = "stages" not in data and "planes" in data
        workbench = cls(
            schema_version=(WORKBENCH_SCHEMA_VERSION if legacy else str(
                data.get("schema_version", WORKBENCH_SCHEMA_VERSION))),
            title=str(data.get("title", "Graph workbench")),
            task=str(data.get("task", "")),
            success=str(data.get("success", "")),
            nodes=tuple(NodeManifest.from_dict(node) for node in data.get("nodes") or ()),
            candidates=tuple(
                NodeCandidate.from_dict(candidate)
                for candidate in data.get("candidates") or ()),
            macro_stages=tuple(
                MacroStageDefinition.from_dict(stage)
                for stage in data.get("macro_stages") or ()),
            stages=tuple(
                StageDefinition.from_dict(stage)
                for stage in (data.get("stages") or data.get("planes") or ())),
            solutions=tuple(
                SolutionDefinition.from_dict(solution)
                for solution in data.get("solutions") or ()),
            feedback_channels=tuple(
                FeedbackDefinition.from_dict(channel)
                for channel in data.get("feedback_channels") or ()),
            optimization_profiles=tuple(
                OptimizationProfile.from_dict(profile)
                for profile in data.get("optimization_profiles") or ()),
            receipts=tuple(
                ExecutionReceipt.from_dict(receipt)
                for receipt in data.get("receipts") or ()),
            optimization_decisions=tuple(
                OptimizationDecision.from_dict(decision)
                for decision in data.get("optimization_decisions") or ()),
            metadata=dict(data.get("metadata") or {}),
        )
        return workbench.assert_valid()

    @classmethod
    def load(cls, path: str | Path) -> WorkbenchDefinition:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def render_html(self, view: str = "matrix") -> str:
        """Render one self-contained studio, initially focused on ``view``."""
        self.assert_valid()
        if view not in WORKBENCH_VIEWS:
            raise ValueError(
                f"unknown workbench view {view!r}; choose from {WORKBENCH_VIEWS}")
        template = files("browsergraph").joinpath(
            "assets/workbench-studio-template.html")
        html = template.read_text(encoding="utf-8")
        data_marker = "__WORKBENCH_DATA__"
        view_marker = "__WORKBENCH_INITIAL_VIEW__"
        if html.count(data_marker) != 1 or html.count(view_marker) != 1:
            raise RuntimeError(
                "workbench template must contain exactly one data and view marker")
        payload = json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))
        payload = payload.replace("</", "<\\/")
        return html.replace(data_marker, payload).replace(
            view_marker, json.dumps(view))

    def write_html(self, path: str | Path, view: str = "matrix") -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.render_html(view=view), encoding="utf-8")
        return destination

    def write_suite(self, directory: str | Path) -> dict[str, Path]:
        """Write five linked mental projections of the same canonical data."""
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        names = {
            "matrix": "index.html",
            "network": "path-network.html",
            "compare": "compare-routes.html",
            "builder": "build-route.html",
            "feedback": "feedback-loop.html",
        }
        outputs = {
            view: self.write_html(destination / filename, view=view)
            for view, filename in names.items()
        }
        data_path = destination / "workbench.json"
        data_path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        outputs["data"] = data_path
        return outputs


def workbench_schema() -> dict[str, Any]:
    resource = files("browsergraph").joinpath("schemas/workbench.schema.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def demo_workbench() -> WorkbenchDefinition:
    from browsergraph.demo import build_demo_workbench
    return build_demo_workbench()
