"""Strict contracts for the data-science design atlas.

The atlas keeps three truths separate:

* a technique inventory says that an approach is known;
* a design question says which decision and evidence a task requires;
* capability evidence says how much of an implementation has actually been proven.

None of those objects is an executable :class:`~solutiongraph.model.NodeSpec`.
Executable techniques still enter SolutionGraph through the ordinary node ABI,
compiler admission, frozen-plan execution, and receipt protocols.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE, sha256_digest

DESIGN_ATLAS_MODEL_VERSION = "0.1"
DESIGN_MODES = ("deterministic", "llm", "human", "external")
PLAN_STATUSES = ("selected", "deferred", "blocked", "not-applicable")
DECISION_STATUSES = ("accepted", "provisional", "abstained", "unanswered")
MATURITY_LEVELS = tuple(f"C{index}" for index in range(8))


def _nonempty_unique(values: tuple[str, ...], path: str) -> list[str]:
    problems: list[str] = []
    if len(values) != len(set(values)):
        problems.append(f"{path} must be unique")
    if any(not value.strip() for value in values):
        problems.append(f"{path} must not contain empty values")
    return problems


def _ids(values: tuple[str, ...], path: str) -> list[str]:
    problems = _nonempty_unique(values, path)
    if any(not ID_RE.fullmatch(value) for value in values):
        problems.append(f"{path} must contain namespaced identifiers")
    return problems


@dataclass(frozen=True)
class ResearchReference:
    """A primary or official source used to justify a design concern."""

    id: str
    title: str
    url: str
    kind: str
    claim: str
    revision: str = ""

    def validate(self, path: str = "reference") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.title.strip() or not self.claim.strip():
            problems.append(f"{path}.title and claim must not be empty")
        if not self.url.startswith("https://"):
            problems.append(f"{path}.url must use https")
        if not ID_RE.fullmatch(self.kind):
            problems.append(f"{path}.kind must be a namespaced identifier")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "kind": self.kind,
            "claim": self.claim,
            "revision": self.revision,
        }


@dataclass(frozen=True)
class Technique:
    """One catalog entry, deliberately weaker than an implementation claim."""

    id: str
    ordinal: str
    phase_id: str
    phase_title: str
    family: str
    title: str
    examples: str
    source_claim: str
    source_note: str
    source_id: str = "source.owner-technique-inventory.2026-08-13"
    owner: str = "owner.solutiongraph-project"
    references: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "technique") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("phase_id", self.phase_id),
            ("source_id", self.source_id),
            ("owner", self.owner),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        if not self.ordinal or not self.title.strip() or not self.phase_title.strip():
            problems.append(f"{path}.ordinal, title, and phase_title must not be empty")
        if self.source_claim not in {
            "reported-implemented",
            "reported-partial",
            "reported-designed",
            "reported-absent",
        }:
            problems.append(f"{path}.source_claim is unsupported")
        problems.extend(_ids(self.references, f"{path}.references"))
        problems.extend(_ids(self.tags, f"{path}.tags"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_atlas_model_version": DESIGN_ATLAS_MODEL_VERSION,
            "id": self.id,
            "ordinal": self.ordinal,
            "phase_id": self.phase_id,
            "phase_title": self.phase_title,
            "family": self.family,
            "title": self.title,
            "examples": self.examples,
            "source_claim": self.source_claim,
            "source_note": self.source_note,
            "source_id": self.source_id,
            "owner": self.owner,
            "references": list(self.references),
            "tags": list(self.tags),
            "maturity_floor": "C1",
            "claim_boundary": (
                "The source claim describes an unverified supplied inventory. "
                "This entry proves catalog coverage only; executable maturity is separate."
            ),
        }


@dataclass(frozen=True)
class DecisionChoice:
    """One explicit branch available when answering a design question."""

    id: str
    label: str
    consequence: str
    action_ids: tuple[str, ...] = ()
    technique_tags: tuple[str, ...] = ()

    def validate(self, path: str = "choice") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.label.strip() or not self.consequence.strip():
            problems.append(f"{path}.label and consequence must not be empty")
        problems.extend(_ids(self.action_ids, f"{path}.action_ids"))
        problems.extend(_ids(self.technique_tags, f"{path}.technique_tags"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "consequence": self.consequence,
            "action_ids": list(self.action_ids),
            "technique_tags": list(self.technique_tags),
        }


@dataclass(frozen=True)
class DesignQuestion:
    """A declarative, evidence-seeking design decision—not an executable node."""

    id: str
    version: str
    pack_id: str
    title: str
    prompt: str
    rationale: str
    response_modes: tuple[str, ...]
    cost_tier: int
    risk_weight: float
    required_evidence: tuple[str, ...]
    choices: tuple[DecisionChoice, ...]
    trigger_any: tuple[str, ...] = ()
    trigger_all: tuple[str, ...] = ()
    exclude_when: tuple[str, ...] = ()
    experiment_template: str = ""
    stop_conditions: tuple[str, ...] = ()
    reference_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "question") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.pack_id):
            problems.append(f"{path}.id and pack_id must be namespaced identifiers")
        if not self.version.strip() or not self.title.strip() or not self.prompt.strip():
            problems.append(f"{path}.version, title, and prompt must not be empty")
        if not self.rationale.strip():
            problems.append(f"{path}.rationale must not be empty")
        problems.extend(_nonempty_unique(self.response_modes, f"{path}.response_modes"))
        if not self.response_modes or any(mode not in DESIGN_MODES for mode in self.response_modes):
            problems.append(f"{path}.response_modes must use supported modes")
        if not 1 <= self.cost_tier <= 10:
            problems.append(f"{path}.cost_tier must be between one and ten")
        if not isfinite(self.risk_weight) or not 0.0 <= self.risk_weight <= 1.0:
            problems.append(f"{path}.risk_weight must be finite and between zero and one")
        for label, values in (
            ("required_evidence", self.required_evidence),
            ("trigger_any", self.trigger_any),
            ("trigger_all", self.trigger_all),
            ("exclude_when", self.exclude_when),
            ("reference_ids", self.reference_ids),
            ("tags", self.tags),
        ):
            problems.extend(_ids(values, f"{path}.{label}"))
        if len(self.choices) < 2:
            problems.append(f"{path}.choices must contain at least two explicit branches")
        choice_ids = tuple(choice.id for choice in self.choices)
        problems.extend(_ids(choice_ids, f"{path}.choices ids"))
        for index, choice in enumerate(self.choices):
            problems.extend(choice.validate(f"{path}.choices[{index}]"))
        problems.extend(_nonempty_unique(self.stop_conditions, f"{path}.stop_conditions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_atlas_model_version": DESIGN_ATLAS_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "pack_id": self.pack_id,
            "title": self.title,
            "prompt": self.prompt,
            "rationale": self.rationale,
            "response_modes": list(self.response_modes),
            "cost_tier": self.cost_tier,
            "risk_weight": self.risk_weight,
            "required_evidence": list(self.required_evidence),
            "choices": [choice.to_dict() for choice in self.choices],
            "trigger_any": list(self.trigger_any),
            "trigger_all": list(self.trigger_all),
            "exclude_when": list(self.exclude_when),
            "experiment_template": self.experiment_template,
            "stop_conditions": list(self.stop_conditions),
            "reference_ids": list(self.reference_ids),
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class DesignPack:
    id: str
    version: str
    title: str
    description: str
    stage: str
    questions: tuple[DesignQuestion, ...]
    reference_ids: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "pack") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.stage):
            problems.append(f"{path}.id and stage must be namespaced identifiers")
        if not self.version.strip() or not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.version, title, and description must not be empty")
        if not self.questions:
            problems.append(f"{path}.questions must not be empty")
        ids = tuple(question.id for question in self.questions)
        problems.extend(_ids(ids, f"{path}.question ids"))
        if any(question.pack_id != self.id for question in self.questions):
            problems.append(f"{path}.questions must reference this pack")
        for index, question in enumerate(self.questions):
            problems.extend(question.validate(f"{path}.questions[{index}]"))
        problems.extend(_ids(self.reference_ids, f"{path}.reference_ids"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_atlas_model_version": DESIGN_ATLAS_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "stage": self.stage,
            "questions": [question.to_dict() for question in self.questions],
            "reference_ids": list(self.reference_ids),
        }


@dataclass(frozen=True)
class TaskArchetype:
    id: str
    title: str
    description: str
    outcome_artifact: str
    required_pack_ids: tuple[str, ...]
    optional_pack_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "archetype") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.outcome_artifact):
            problems.append(f"{path}.id and outcome_artifact must be namespaced identifiers")
        if not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.title and description must not be empty")
        problems.extend(_ids(self.required_pack_ids, f"{path}.required_pack_ids"))
        problems.extend(_ids(self.optional_pack_ids, f"{path}.optional_pack_ids"))
        problems.extend(_ids(self.tags, f"{path}.tags"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_atlas_model_version": DESIGN_ATLAS_MODEL_VERSION,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "outcome_artifact": self.outcome_artifact,
            "required_pack_ids": list(self.required_pack_ids),
            "optional_pack_ids": list(self.optional_pack_ids),
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class DesignContext:
    """Task facts used for applicability; unknowns stay explicit."""

    id: str
    task_type: str
    objective: str
    modalities: tuple[str, ...]
    lifecycle_stage: str = "lifecycle.prototype"
    risk_tier: str = "risk.medium"
    signals: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    row_count: int | None = None
    column_count: int | None = None
    target_name: str = ""
    time_field: str = ""
    group_field: str = ""
    entity_field: str = ""
    protected_test: bool = True
    dataset_profile_digest: str = ""
    semantic_map_digest: str = ""

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def tags(self) -> frozenset[str]:
        derived = {
            self.task_type,
            self.lifecycle_stage,
            self.risk_tier,
            *self.modalities,
            *self.signals,
            *self.constraints,
        }
        if self.time_field:
            derived.add("signal.time-aware")
        if self.group_field:
            derived.add("signal.grouped")
        if self.entity_field:
            derived.add("signal.entity-aware")
        if self.target_name:
            derived.add("signal.supervised")
        if self.protected_test:
            derived.add("policy.protected-test")
        return frozenset(derived)

    def validate(self, path: str = "context") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("task_type", self.task_type),
            ("lifecycle_stage", self.lifecycle_stage),
            ("risk_tier", self.risk_tier),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        if not self.objective.strip():
            problems.append(f"{path}.objective must not be empty")
        for label, values in (
            ("modalities", self.modalities),
            ("signals", self.signals),
            ("constraints", self.constraints),
        ):
            problems.extend(_ids(values, f"{path}.{label}"))
        if not self.modalities:
            problems.append(f"{path}.modalities must not be empty")
        if self.row_count is not None and self.row_count < 0:
            problems.append(f"{path}.row_count must be non-negative or null")
        if self.column_count is not None and self.column_count < 0:
            problems.append(f"{path}.column_count must be non-negative or null")
        for label, value in (
            ("dataset_profile_digest", self.dataset_profile_digest),
            ("semantic_map_digest", self.semantic_map_digest),
        ):
            if value and not DIGEST_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be empty or a sha256 digest")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_atlas_model_version": DESIGN_ATLAS_MODEL_VERSION,
            "id": self.id,
            "task_type": self.task_type,
            "objective": self.objective,
            "modalities": list(self.modalities),
            "lifecycle_stage": self.lifecycle_stage,
            "risk_tier": self.risk_tier,
            "signals": list(self.signals),
            "constraints": list(self.constraints),
            "row_count": self.row_count,
            "column_count": self.column_count,
            "target_name": self.target_name,
            "time_field": self.time_field,
            "group_field": self.group_field,
            "entity_field": self.entity_field,
            "protected_test": self.protected_test,
            "dataset_profile_digest": self.dataset_profile_digest,
            "semantic_map_digest": self.semantic_map_digest,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DesignContext:
        data = dict(value)
        data.pop("design_atlas_model_version", None)
        for key in ("modalities", "signals", "constraints"):
            data[key] = tuple(data.get(key, ()))
        return cls(**data)


@dataclass(frozen=True)
class DesignEffort:
    id: str
    max_questions: int | None
    max_cost_tier: int
    exploration_fraction: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "max_questions": self.max_questions,
            "max_cost_tier": self.max_cost_tier,
            "exploration_fraction": self.exploration_fraction,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DesignEffort:
        return cls(**value)


@dataclass(frozen=True)
class DesignPlanItem:
    question_id: str
    pack_id: str
    status: str
    priority: float
    response_mode: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "pack_id": self.pack_id,
            "status": self.status,
            "priority": self.priority,
            "response_mode": self.response_mode,
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DesignPlanItem:
        data = dict(value)
        data["reasons"] = tuple(data.get("reasons", ()))
        return cls(**data)


@dataclass(frozen=True)
class DesignPlan:
    id: str
    context_digest: str
    archetype_id: str
    effort: DesignEffort
    items: tuple[DesignPlanItem, ...]
    random_seed: int
    planner_revision: str = "planner.design-atlas.0.1"

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_atlas_model_version": DESIGN_ATLAS_MODEL_VERSION,
            "id": self.id,
            "context_digest": self.context_digest,
            "archetype_id": self.archetype_id,
            "effort": self.effort.to_dict(),
            "items": [item.to_dict() for item in self.items],
            "random_seed": self.random_seed,
            "planner_revision": self.planner_revision,
            "summary": {
                status: sum(item.status == status for item in self.items)
                for status in PLAN_STATUSES
            },
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DesignPlan:
        data = dict(value)
        data.pop("design_atlas_model_version", None)
        data.pop("summary", None)
        data["effort"] = DesignEffort.from_dict(data["effort"])
        data["items"] = tuple(DesignPlanItem.from_dict(item) for item in data["items"])
        return cls(**data)


@dataclass(frozen=True)
class DecisionAnswer:
    question_id: str
    choice_id: str
    rationale: str
    evidence_refs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    confidence: float = 0.0
    responder: str = "responder.unspecified"
    abstained: bool = False

    def validate(self, path: str = "answer") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.question_id) or not ID_RE.fullmatch(self.responder):
            problems.append(f"{path}.question_id and responder must be identifiers")
        if not self.abstained and not ID_RE.fullmatch(self.choice_id):
            problems.append(f"{path}.choice_id must be an identifier unless abstained")
        if not isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            problems.append(f"{path}.confidence must be finite and between zero and one")
        problems.extend(_nonempty_unique(self.evidence_refs, f"{path}.evidence_refs"))
        problems.extend(_nonempty_unique(self.assumptions, f"{path}.assumptions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_atlas_model_version": DESIGN_ATLAS_MODEL_VERSION,
            "question_id": self.question_id,
            "choice_id": self.choice_id,
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
            "assumptions": list(self.assumptions),
            "confidence": self.confidence,
            "responder": self.responder,
            "abstained": self.abstained,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DecisionAnswer:
        data = dict(value)
        data.pop("design_atlas_model_version", None)
        for key in ("evidence_refs", "assumptions"):
            data[key] = tuple(data.get(key, ()))
        return cls(**data)


@dataclass(frozen=True)
class DecisionRecord:
    question_id: str
    choice_id: str
    status: str
    evidence_refs: tuple[str, ...]
    rationale: str
    assumptions: tuple[str, ...]
    action_ids: tuple[str, ...]
    experiment: str
    stop_conditions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "choice_id": self.choice_id,
            "status": self.status,
            "evidence_refs": list(self.evidence_refs),
            "rationale": self.rationale,
            "assumptions": list(self.assumptions),
            "action_ids": list(self.action_ids),
            "experiment": self.experiment,
            "stop_conditions": list(self.stop_conditions),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DecisionRecord:
        data = dict(value)
        for key in ("evidence_refs", "assumptions", "action_ids", "stop_conditions"):
            data[key] = tuple(data.get(key, ()))
        return cls(**data)


@dataclass(frozen=True)
class DesignDossier:
    id: str
    plan_digest: str
    decisions: tuple[DecisionRecord, ...]
    unanswered_question_ids: tuple[str, ...]
    blocked_question_ids: tuple[str, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_atlas_model_version": DESIGN_ATLAS_MODEL_VERSION,
            "id": self.id,
            "plan_digest": self.plan_digest,
            "decisions": [decision.to_dict() for decision in self.decisions],
            "unanswered_question_ids": list(self.unanswered_question_ids),
            "blocked_question_ids": list(self.blocked_question_ids),
            "claim_boundary": (
                "Accepted means evidence was cited for this design record; it does not "
                "prove that a proposed graph is compiler-valid or empirically superior."
            ),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DesignDossier:
        data = dict(value)
        data.pop("design_atlas_model_version", None)
        data.pop("claim_boundary", None)
        data["decisions"] = tuple(
            DecisionRecord.from_dict(item) for item in data.get("decisions", ())
        )
        for key in ("unanswered_question_ids", "blocked_question_ids"):
            data[key] = tuple(data.get(key, ()))
        return cls(**data)


@dataclass(frozen=True)
class CapabilityEvidence:
    """Evidence inputs from which maturity is derived, never self-awarded."""

    capability_id: str
    cataloged: bool = False
    declaration_digest: str = ""
    valid_smoke_tests: int = 0
    invalid_smoke_tests: int = 0
    compatibility_tests: int = 0
    leakage_tests: int = 0
    search_registered: bool = False
    search_tests: int = 0
    benchmark_receipts: int = 0
    benchmark_seeds: int = 0
    monitoring_evidence: tuple[str, ...] = ()
    security_evidence: tuple[str, ...] = ()
    privacy_evidence: tuple[str, ...] = ()
    rollback_evidence: tuple[str, ...] = ()
    slo_evidence: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()

    def validate(self, path: str = "capability_evidence") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.capability_id):
            problems.append(f"{path}.capability_id must be a namespaced identifier")
        if self.declaration_digest and not DIGEST_RE.fullmatch(self.declaration_digest):
            problems.append(f"{path}.declaration_digest must be empty or a sha256 digest")
        counts = (
            self.valid_smoke_tests,
            self.invalid_smoke_tests,
            self.compatibility_tests,
            self.leakage_tests,
            self.search_tests,
            self.benchmark_receipts,
            self.benchmark_seeds,
        )
        if any(value < 0 for value in counts):
            problems.append(f"{path} counts must be non-negative")
        for label in (
            "monitoring_evidence",
            "security_evidence",
            "privacy_evidence",
            "rollback_evidence",
            "slo_evidence",
            "artifact_refs",
        ):
            problems.extend(_nonempty_unique(getattr(self, label), f"{path}.{label}"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_atlas_model_version": DESIGN_ATLAS_MODEL_VERSION,
            "capability_id": self.capability_id,
            "cataloged": self.cataloged,
            "declaration_digest": self.declaration_digest,
            "valid_smoke_tests": self.valid_smoke_tests,
            "invalid_smoke_tests": self.invalid_smoke_tests,
            "compatibility_tests": self.compatibility_tests,
            "leakage_tests": self.leakage_tests,
            "search_registered": self.search_registered,
            "search_tests": self.search_tests,
            "benchmark_receipts": self.benchmark_receipts,
            "benchmark_seeds": self.benchmark_seeds,
            "monitoring_evidence": list(self.monitoring_evidence),
            "security_evidence": list(self.security_evidence),
            "privacy_evidence": list(self.privacy_evidence),
            "rollback_evidence": list(self.rollback_evidence),
            "slo_evidence": list(self.slo_evidence),
            "artifact_refs": list(self.artifact_refs),
        }


@dataclass(frozen=True)
class MaturityAssessment:
    capability_id: str
    overall_level: str
    level_name: str
    component_levels: tuple[tuple[str, str], ...]
    satisfied_gates: tuple[str, ...]
    next_gate: str
    evidence_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "overall_level": self.overall_level,
            "level_name": self.level_name,
            "component_levels": dict(self.component_levels),
            "satisfied_gates": list(self.satisfied_gates),
            "next_gate": self.next_gate,
            "evidence_digest": self.evidence_digest,
        }


__all__ = [
    "CapabilityEvidence",
    "DECISION_STATUSES",
    "DESIGN_ATLAS_MODEL_VERSION",
    "DESIGN_MODES",
    "DecisionAnswer",
    "DecisionChoice",
    "DecisionRecord",
    "DesignContext",
    "DesignDossier",
    "DesignEffort",
    "DesignPack",
    "DesignPlan",
    "DesignPlanItem",
    "DesignQuestion",
    "MATURITY_LEVELS",
    "MaturityAssessment",
    "PLAN_STATUSES",
    "ResearchReference",
    "TaskArchetype",
    "Technique",
]
