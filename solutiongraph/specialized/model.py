"""Typed definitions for extraction-ready specialized capability packs.

A specialized capability pack is an authoring and discovery bundle.  It points
to semantic templates, executable node packs, question banks, examples,
benchmarks, and integration adapters, but it is deliberately *not* an
executable closure.  ``NodePackManifest`` remains the reusable executable
distribution unit and ``SolutionPackManifest`` remains the exact task/run
closure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from solutiongraph.model import ID_RE, canonical_json, sha256_digest

SPECIALIZED_PACK_MODEL_VERSION = "0.1"
SPECIALIZED_PACK_ENTRY_POINT_GROUP = "solutiongraph.specialized_packs"
PACK_READINESS = (
    "catalog",
    "executable-fixture",
    "credentialed-connector",
    "production-adapter",
)
PROFILE_MODES = ("declared", "deterministic", "external", "model")
PROFILE_VALUE_KINDS = (
    "boolean",
    "integer",
    "number",
    "string",
    "category",
    "distribution",
    "vector",
    "mapping",
)
METRIC_DIRECTIONS = ("maximize", "minimize", "target", "none")
GATE_DECISIONS = ("reject", "escalate", "warn")
ORACLE_KINDS = (
    "exact",
    "property",
    "cross-implementation",
    "statistical",
    "human",
    "external-authority",
)

_DISTRIBUTION_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_MODULE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*$")


def _unique(
    values: tuple[str, ...],
    path: str,
    *,
    ids: bool = False,
    required: bool = False,
) -> list[str]:
    problems: list[str] = []
    if required and not values:
        problems.append(f"{path} must not be empty")
    if len(values) != len(set(values)):
        problems.append(f"{path} must be unique")
    if any(not item.strip() for item in values):
        problems.append(f"{path} must not contain empty values")
    if ids and any(not ID_RE.fullmatch(item) for item in values):
        problems.append(f"{path} must contain namespaced identifiers")
    return problems


def _extensions_problems(extensions: tuple[tuple[str, Any], ...], path: str) -> list[str]:
    problems: list[str] = []
    keys = [key for key, _ in extensions]
    if len(keys) != len(set(keys)):
        problems.append(f"{path} keys must be unique")
    for key, value in extensions:
        if not ID_RE.fullmatch(key) or "." not in key:
            problems.append(f"{path}.{key} must use a namespaced key")
        try:
            canonical_json(value)
        except (TypeError, ValueError):
            problems.append(f"{path}.{key} must be JSON serialisable")
    return problems


@dataclass(frozen=True)
class ProfilerFeature:
    """One task/data characteristic a pack can use for nomination or history.

    Features never grant graph compatibility.  Model-produced vectors remain
    discovery evidence and need an exact embedding-space identity in the
    ordinary discovery protocol before vectors can be compared.
    """

    id: str
    title: str
    description: str
    value_kind: str
    mode: str
    evidence_kind: str
    cost_tier: int = 1
    effects: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    requirements: tuple[str, ...] = ()

    @property
    def easy_to_compute(self) -> bool:
        return self.mode == "deterministic" and not self.effects and not self.permissions

    def validate(self, path: str = "profiler_feature") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.id.startswith("feature."):
            problems.append(f"{path}.id must begin with feature.")
        if not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.title and description must not be empty")
        if self.value_kind not in PROFILE_VALUE_KINDS:
            problems.append(f"{path}.value_kind is unsupported")
        if self.mode not in PROFILE_MODES:
            problems.append(f"{path}.mode is unsupported")
        if not ID_RE.fullmatch(self.evidence_kind):
            problems.append(f"{path}.evidence_kind must be namespaced")
        if not 1 <= self.cost_tier <= 10:
            problems.append(f"{path}.cost_tier must be between one and ten")
        for label in ("effects", "permissions", "requirements"):
            problems.extend(_unique(getattr(self, label), f"{path}.{label}", ids=True))
        if self.mode == "deterministic" and (self.effects or self.permissions):
            problems.append(f"{path} deterministic features must not hide effects or permissions")
        if self.mode == "model" and "model.invoke" not in self.permissions:
            problems.append(f"{path} model features require model.invoke permission")
        if self.mode == "external" and not self.effects:
            problems.append(f"{path} external features must declare an effect")
        if self.value_kind == "vector" and self.mode != "model":
            problems.append(f"{path} vector features must use model mode")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "value_kind": self.value_kind,
            "mode": self.mode,
            "evidence_kind": self.evidence_kind,
            "cost_tier": self.cost_tier,
            "effects": list(self.effects),
            "permissions": list(self.permissions),
            "requirements": list(self.requirements),
            "easy_to_compute": self.easy_to_compute,
        }


@dataclass(frozen=True)
class EvaluationMetric:
    """One objective or diagnostic recommended by a capability pack."""

    id: str
    title: str
    description: str
    direction: str
    unit: str
    scope: str
    required_evidence: tuple[str, ...]

    def validate(self, path: str = "metric") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.id.startswith("metric."):
            problems.append(f"{path}.id must begin with metric.")
        if not self.title.strip() or not self.description.strip() or not self.unit.strip():
            problems.append(f"{path}.title, description, and unit must not be empty")
        if self.direction not in METRIC_DIRECTIONS:
            problems.append(f"{path}.direction is unsupported")
        if not ID_RE.fullmatch(self.scope):
            problems.append(f"{path}.scope must be namespaced")
        problems.extend(
            _unique(
                self.required_evidence,
                f"{path}.required_evidence",
                ids=True,
                required=True,
            )
        )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "direction": self.direction,
            "unit": self.unit,
            "scope": self.scope,
            "required_evidence": list(self.required_evidence),
        }


@dataclass(frozen=True)
class QualityGate:
    """A pack-level evaluation recommendation, not a self-authorizing oracle."""

    id: str
    title: str
    description: str
    metric_ids: tuple[str, ...]
    oracle_kind: str
    decision: str
    independent: bool = True

    def validate(self, path: str = "gate") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.id.startswith("gate."):
            problems.append(f"{path}.id must begin with gate.")
        if not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.title and description must not be empty")
        problems.extend(_unique(self.metric_ids, f"{path}.metric_ids", ids=True, required=True))
        if self.oracle_kind not in ORACLE_KINDS:
            problems.append(f"{path}.oracle_kind is unsupported")
        if self.decision not in GATE_DECISIONS:
            problems.append(f"{path}.decision is unsupported")
        if self.decision == "reject" and not self.independent:
            problems.append(f"{path} rejecting gates must be independently identified")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "metric_ids": list(self.metric_ids),
            "oracle_kind": self.oracle_kind,
            "decision": self.decision,
            "independent": self.independent,
        }


@dataclass(frozen=True)
class PackRecipe:
    """A typed authoring starting point assembled from existing asset families."""

    id: str
    title: str
    description: str
    input_kind_ids: tuple[str, ...]
    output_kind_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    category_ids: tuple[str, ...]
    template_ids: tuple[str, ...]
    node_pack_ids: tuple[str, ...] = ()
    question_pack_ids: tuple[str, ...] = ()
    design_pack_ids: tuple[str, ...] = ()
    example_ids: tuple[str, ...] = ()
    benchmark_ids: tuple[str, ...] = ()
    agent_benchmark_ids: tuple[str, ...] = ()
    arena_task_ids: tuple[str, ...] = ()
    adapter_ids: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def validate(self, path: str = "recipe") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.id.startswith("recipe."):
            problems.append(f"{path}.id must begin with recipe.")
        if not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.title and description must not be empty")
        for label in (
            "input_kind_ids",
            "output_kind_ids",
            "capability_ids",
            "category_ids",
            "template_ids",
        ):
            problems.extend(
                _unique(getattr(self, label), f"{path}.{label}", ids=True, required=True)
            )
        for label in (
            "node_pack_ids",
            "question_pack_ids",
            "design_pack_ids",
            "example_ids",
            "benchmark_ids",
            "agent_benchmark_ids",
            "arena_task_ids",
            "adapter_ids",
            "effects",
            "permissions",
        ):
            problems.extend(_unique(getattr(self, label), f"{path}.{label}", ids=True))
        problems.extend(_unique(self.limitations, f"{path}.limitations"))
        if set(self.effects) - set(self.permissions):
            # Effects and permissions use the same vocabulary in the reference
            # recipes.  Production adapters may refine them in executable ABIs.
            problems.append(f"{path}.effects must have corresponding permissions")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "input_kind_ids": list(self.input_kind_ids),
            "output_kind_ids": list(self.output_kind_ids),
            "capability_ids": list(self.capability_ids),
            "category_ids": list(self.category_ids),
            "template_ids": list(self.template_ids),
            "node_pack_ids": list(self.node_pack_ids),
            "question_pack_ids": list(self.question_pack_ids),
            "design_pack_ids": list(self.design_pack_ids),
            "example_ids": list(self.example_ids),
            "benchmark_ids": list(self.benchmark_ids),
            "agent_benchmark_ids": list(self.agent_benchmark_ids),
            "arena_task_ids": list(self.arena_task_ids),
            "adapter_ids": list(self.adapter_ids),
            "effects": list(self.effects),
            "permissions": list(self.permissions),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class SpecializedPackDefinition:
    """One extraction-ready vertical view over reusable SolutionGraph assets."""

    id: str
    version: str
    title: str
    description: str
    readiness: str
    current_distribution: str
    python_module: str
    entry_point_name: str
    extraction_target: str
    domain_pack_ids: tuple[str, ...]
    task_category_ids: tuple[str, ...]
    signal_terms: tuple[str, ...]
    recipes: tuple[PackRecipe, ...]
    profiler_features: tuple[ProfilerFeature, ...]
    metrics: tuple[EvaluationMetric, ...]
    gates: tuple[QualityGate, ...]
    source: str
    license: str
    limitations: tuple[str, ...]
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                capability for recipe in self.recipes for capability in recipe.capability_ids
            )
        )

    @property
    def input_kind_ids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(kind for recipe in self.recipes for kind in recipe.input_kind_ids)
        )

    @property
    def output_kind_ids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(kind for recipe in self.recipes for kind in recipe.output_kind_ids)
        )

    def validate(self, path: str = "specialized_pack") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.id.startswith("specialized-pack."):
            problems.append(f"{path}.id must begin with specialized-pack.")
        if not self.version.strip() or not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.version, title, and description must not be empty")
        if self.readiness not in PACK_READINESS:
            problems.append(f"{path}.readiness is unsupported")
        for label, value in (
            ("current_distribution", self.current_distribution),
            ("entry_point_name", self.entry_point_name),
            ("extraction_target", self.extraction_target),
        ):
            if not _DISTRIBUTION_RE.fullmatch(value):
                problems.append(f"{path}.{label} is not a valid distribution/entry name")
        if not _MODULE_RE.fullmatch(self.python_module):
            problems.append(f"{path}.python_module is not a valid import path")
        for label in ("domain_pack_ids", "task_category_ids"):
            problems.extend(
                _unique(getattr(self, label), f"{path}.{label}", ids=True, required=True)
            )
        problems.extend(_unique(self.signal_terms, f"{path}.signal_terms", required=True))
        if any(term != term.casefold() for term in self.signal_terms):
            problems.append(f"{path}.signal_terms must be case-folded")
        if not self.source.strip() or not self.license.strip():
            problems.append(f"{path}.source and license must not be empty")
        problems.extend(_unique(self.limitations, f"{path}.limitations", required=True))
        problems.extend(_extensions_problems(self.extensions, f"{path}.extensions"))

        for label, values in (
            ("recipes", self.recipes),
            ("profiler_features", self.profiler_features),
            ("metrics", self.metrics),
            ("gates", self.gates),
        ):
            if not values:
                problems.append(f"{path}.{label} must not be empty")
            ids = [item.id for item in values]
            if len(ids) != len(set(ids)):
                problems.append(f"{path}.{label} ids must be unique")
            for index, item in enumerate(values):
                problems.extend(item.validate(f"{path}.{label}[{index}]"))

        known_metrics = {metric.id for metric in self.metrics}
        for index, gate in enumerate(self.gates):
            unknown = sorted(set(gate.metric_ids) - known_metrics)
            if unknown:
                problems.append(
                    f"{path}.gates[{index}] references unknown metrics: " + ", ".join(unknown)
                )
        declared_categories = set(self.task_category_ids)
        for index, recipe in enumerate(self.recipes):
            unknown = sorted(set(recipe.category_ids) - declared_categories)
            if unknown:
                problems.append(
                    f"{path}.recipes[{index}] uses undeclared categories: " + ", ".join(unknown)
                )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "specialized_pack_model_version": SPECIALIZED_PACK_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "readiness": self.readiness,
            "delivery": {
                "current_distribution": self.current_distribution,
                "python_module": self.python_module,
                "entry_point_group": SPECIALIZED_PACK_ENTRY_POINT_GROUP,
                "entry_point_name": self.entry_point_name,
                "extraction_target": self.extraction_target,
            },
            "domain_pack_ids": list(self.domain_pack_ids),
            "task_category_ids": list(self.task_category_ids),
            "signal_terms": list(self.signal_terms),
            "recipes": [item.to_dict() for item in self.recipes],
            "profiler_features": [item.to_dict() for item in self.profiler_features],
            "metrics": [item.to_dict() for item in self.metrics],
            "gates": [item.to_dict() for item in self.gates],
            "source": self.source,
            "license": self.license,
            "limitations": list(self.limitations),
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class SpecializedPackRegistry:
    """A closed-world set of specialized pack definitions for one release."""

    id: str
    version: str
    packs: tuple[SpecializedPackDefinition, ...]
    description: str

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "specialized_pack_registry") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.id.startswith("registry."):
            problems.append(f"{path}.id must begin with registry.")
        if not self.version.strip() or not self.description.strip():
            problems.append(f"{path}.version and description must not be empty")
        if not self.packs:
            problems.append(f"{path}.packs must not be empty")
        pack_ids = [pack.id for pack in self.packs]
        if len(pack_ids) != len(set(pack_ids)):
            problems.append(f"{path}.packs ids must be unique because requests address packs by id")
        entry_names = [pack.entry_point_name for pack in self.packs]
        if len(entry_names) != len(set(entry_names)):
            problems.append(f"{path}.packs entry point names must be unique")
        extraction_targets = [pack.extraction_target for pack in self.packs]
        if len(extraction_targets) != len(set(extraction_targets)):
            problems.append(f"{path}.packs extraction targets must be unique")
        for label in ("recipes", "profiler_features", "metrics", "gates"):
            item_ids = [item.id for pack in self.packs for item in getattr(pack, label)]
            if len(item_ids) != len(set(item_ids)):
                problems.append(f"{path}.packs {label} ids must be globally unique")
        for index, pack in enumerate(self.packs):
            problems.extend(pack.validate(f"{path}.packs[{index}]"))
        return problems

    def get(self, pack_id: str) -> SpecializedPackDefinition:
        for pack in self.packs:
            if pack.id == pack_id:
                return pack
        raise KeyError(pack_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "specialized_pack_model_version": SPECIALIZED_PACK_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "description": self.description,
            "packs": [pack.to_dict() for pack in self.packs],
        }


__all__ = [
    "GATE_DECISIONS",
    "METRIC_DIRECTIONS",
    "ORACLE_KINDS",
    "PACK_READINESS",
    "PROFILE_MODES",
    "PROFILE_VALUE_KINDS",
    "SPECIALIZED_PACK_ENTRY_POINT_GROUP",
    "SPECIALIZED_PACK_MODEL_VERSION",
    "EvaluationMetric",
    "PackRecipe",
    "ProfilerFeature",
    "QualityGate",
    "SpecializedPackDefinition",
    "SpecializedPackRegistry",
]
