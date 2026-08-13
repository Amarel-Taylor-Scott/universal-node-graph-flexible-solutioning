"""Immutable contracts for semantic data interrogation and reversible repair.

Questions are declarative obligations.  They are not executable nodes and they
do not acquire authority from prose.  ``CheckRequirement`` objects nominate
ordinary node capabilities or adapters, while plans and receipts preserve the
exact selection and observations made for one dataset.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE, canonical_json, sha256_digest

INTERROGATION_MODEL_VERSION = "0.1"

QUESTION_SCOPES = ("field", "row", "entity", "dataset", "cross-field", "pipeline")
QUESTION_MODES = ("deterministic", "external", "llm", "human")
QUESTION_SEVERITIES = ("info", "low", "medium", "high", "critical")
PLAN_STATUSES = ("selected", "deferred", "blocked", "not-applicable")
QUESTION_OUTCOMES = ("pass", "fail", "abstain", "error", "not-run")
PATCH_ACTIONS = ("add", "replace", "remove", "quarantine")
REPAIR_DECISIONS = ("promote", "quarantine", "reject", "abstain", "no-change")


def _json_value(value: Any) -> Any:
    return json.loads(canonical_json(value))


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


def _unique(values: tuple[str, ...], path: str, *, identifiers: bool = False) -> list[str]:
    problems: list[str] = []
    if len(values) != len(set(values)):
        problems.append(f"{path} must be unique")
    if any(not value.strip() for value in values):
        problems.append(f"{path} must not contain empty values")
    if identifiers and any(not ID_RE.fullmatch(value) for value in values):
        problems.append(f"{path} must contain namespaced identifiers")
    return problems


@dataclass(frozen=True)
class StandardsReference:
    """One exact semantic, validation, or authority reference."""

    id: str
    url: str
    role: str
    revision: str = ""
    jurisdiction: str = ""
    license: str = ""
    notes: str = ""

    def validate(self, path: str = "reference") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.url.startswith(("https://", "urn:")):
            problems.append(f"{path}.url must be an https URL or URN")
        if not ID_RE.fullmatch(self.role):
            problems.append(f"{path}.role must be a namespaced identifier")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "role": self.role,
            "revision": self.revision,
            "jurisdiction": self.jurisdiction,
            "license": self.license,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> StandardsReference:
        return cls(**value)


@dataclass(frozen=True)
class ConceptDefinition:
    """A semantic field concept, independent of any checking implementation."""

    id: str
    version: str
    canonical_uri: str
    label: str
    value_type: str
    aliases: tuple[str, ...]
    description: str = ""
    parent_ids: tuple[str, ...] = ()
    jurisdictions: tuple[str, ...] = ()
    references: tuple[StandardsReference, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "concept") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.version.strip() or not self.label.strip():
            problems.append(f"{path}.version and label must not be empty")
        if not self.canonical_uri.startswith(("https://", "urn:")):
            problems.append(f"{path}.canonical_uri must be an https URL or URN")
        if not ID_RE.fullmatch(self.value_type):
            problems.append(f"{path}.value_type must be a namespaced identifier")
        problems.extend(_unique(self.aliases, f"{path}.aliases"))
        problems.extend(_unique(self.parent_ids, f"{path}.parent_ids", identifiers=True))
        problems.extend(_unique(self.jurisdictions, f"{path}.jurisdictions"))
        reference_ids = tuple(reference.id for reference in self.references)
        problems.extend(_unique(reference_ids, f"{path}.references ids", identifiers=True))
        for index, reference in enumerate(self.references):
            problems.extend(reference.validate(f"{path}.references[{index}]"))
        problems.extend(_extensions_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "interrogation_model_version": INTERROGATION_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "canonical_uri": self.canonical_uri,
            "label": self.label,
            "description": self.description,
            "value_type": self.value_type,
            "aliases": list(self.aliases),
            "parent_ids": list(self.parent_ids),
            "jurisdictions": list(self.jurisdictions),
            "references": [item.to_dict() for item in self.references],
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ConceptDefinition:
        data = dict(value)
        data.pop("interrogation_model_version", None)
        for key in ("aliases", "parent_ids", "jurisdictions"):
            data[key] = tuple(data.get(key, ()))
        data["references"] = tuple(
            StandardsReference.from_dict(item) for item in data.get("references", ())
        )
        data["extensions"] = tuple(data.get("extensions", {}).items())
        return cls(**data)


@dataclass(frozen=True)
class FieldProfile:
    """Aggregate-only profile for one source field."""

    field_name: str
    inferred_type: str
    row_count: int
    non_missing_count: int
    distinct_count: int
    missing_fraction: float
    placeholder_count: int = 0
    control_character_count: int = 0
    non_nfc_count: int = 0
    leading_or_trailing_space_count: int = 0
    min_length: int | None = None
    max_length: int | None = None
    numeric_fraction: float = 0.0
    top_value_hashes: tuple[tuple[str, int], ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "field_profile") -> list[str]:
        problems: list[str] = []
        if not self.field_name.strip():
            problems.append(f"{path}.field_name must not be empty")
        if not ID_RE.fullmatch(self.inferred_type):
            problems.append(f"{path}.inferred_type must be a namespaced identifier")
        counts = (
            self.row_count,
            self.non_missing_count,
            self.distinct_count,
            self.placeholder_count,
            self.control_character_count,
            self.non_nfc_count,
            self.leading_or_trailing_space_count,
        )
        if any(value < 0 for value in counts):
            problems.append(f"{path} counts must be non-negative")
        if self.non_missing_count > self.row_count:
            problems.append(f"{path}.non_missing_count cannot exceed row_count")
        for label, value in (
            ("missing_fraction", self.missing_fraction),
            ("numeric_fraction", self.numeric_fraction),
        ):
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                problems.append(f"{path}.{label} must be finite and between zero and one")
        if self.min_length is not None and self.min_length < 0:
            problems.append(f"{path}.min_length must be non-negative or null")
        if self.max_length is not None and self.max_length < 0:
            problems.append(f"{path}.max_length must be non-negative or null")
        if self.min_length is not None and self.max_length is not None:
            if self.min_length > self.max_length:
                problems.append(f"{path}.min_length cannot exceed max_length")
        hashes = tuple(item[0] for item in self.top_value_hashes)
        if len(hashes) != len(set(hashes)) or any(not DIGEST_RE.fullmatch(item) for item in hashes):
            problems.append(f"{path}.top_value_hashes must use unique sha256 digests")
        if any(count <= 0 for _, count in self.top_value_hashes):
            problems.append(f"{path}.top_value_hashes counts must be positive")
        problems.extend(_extensions_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "inferred_type": self.inferred_type,
            "row_count": self.row_count,
            "non_missing_count": self.non_missing_count,
            "distinct_count": self.distinct_count,
            "missing_fraction": self.missing_fraction,
            "placeholder_count": self.placeholder_count,
            "control_character_count": self.control_character_count,
            "non_nfc_count": self.non_nfc_count,
            "leading_or_trailing_space_count": self.leading_or_trailing_space_count,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "numeric_fraction": self.numeric_fraction,
            "top_value_hashes": [
                {"digest": digest, "count": count}
                for digest, count in self.top_value_hashes
            ],
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> FieldProfile:
        data = dict(value)
        data["top_value_hashes"] = tuple(
            (item["digest"], item["count"]) for item in data.get("top_value_hashes", ())
        )
        data["extensions"] = tuple(data.get("extensions", {}).items())
        return cls(**data)


@dataclass(frozen=True)
class DatasetProfile:
    """Content-addressed dataset profile used for planning, never raw evidence."""

    dataset_digest: str
    source_id: str
    row_count: int
    column_names: tuple[str, ...]
    fields: tuple[FieldProfile, ...]
    duplicate_row_count: int = 0
    profile_policy_id: str = "profile.aggregate-only"
    sampled_row_count: int = 0
    warnings: tuple[str, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def field_map(self) -> dict[str, FieldProfile]:
        return {field.field_name: field for field in self.fields}

    def validate(self, path: str = "dataset_profile") -> list[str]:
        problems: list[str] = []
        if not DIGEST_RE.fullmatch(self.dataset_digest):
            problems.append(f"{path}.dataset_digest must be a sha256 digest")
        if not ID_RE.fullmatch(self.source_id):
            problems.append(f"{path}.source_id must be a namespaced identifier")
        if not ID_RE.fullmatch(self.profile_policy_id):
            problems.append(f"{path}.profile_policy_id must be a namespaced identifier")
        if self.row_count < 0 or self.sampled_row_count < 0 or self.duplicate_row_count < 0:
            problems.append(f"{path} counts must be non-negative")
        if self.sampled_row_count > self.row_count:
            problems.append(f"{path}.sampled_row_count cannot exceed row_count")
        problems.extend(_unique(self.column_names, f"{path}.column_names"))
        field_names = tuple(field.field_name for field in self.fields)
        if field_names != self.column_names:
            problems.append(f"{path}.fields must exactly follow column_names")
        for index, field in enumerate(self.fields):
            problems.extend(field.validate(f"{path}.fields[{index}]"))
        problems.extend(_unique(self.warnings, f"{path}.warnings"))
        problems.extend(_extensions_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "interrogation_model_version": INTERROGATION_MODEL_VERSION,
            "dataset_digest": self.dataset_digest,
            "source_id": self.source_id,
            "row_count": self.row_count,
            "column_names": list(self.column_names),
            "fields": [field.to_dict() for field in self.fields],
            "duplicate_row_count": self.duplicate_row_count,
            "profile_policy_id": self.profile_policy_id,
            "sampled_row_count": self.sampled_row_count,
            "warnings": list(self.warnings),
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DatasetProfile:
        data = dict(value)
        data.pop("interrogation_model_version", None)
        data["column_names"] = tuple(data["column_names"])
        data["fields"] = tuple(FieldProfile.from_dict(item) for item in data["fields"])
        data["warnings"] = tuple(data.get("warnings", ()))
        data["extensions"] = tuple(data.get("extensions", {}).items())
        return cls(**data)


@dataclass(frozen=True)
class FieldConceptMatch:
    field_name: str
    concept_id: str
    confidence: float
    method: str
    alternatives: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def validate(self, path: str = "field_match") -> list[str]:
        problems: list[str] = []
        if not self.field_name.strip() or not ID_RE.fullmatch(self.concept_id):
            problems.append(f"{path}.field_name and concept_id must be valid")
        if not isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            problems.append(f"{path}.confidence must be finite and between zero and one")
        if not ID_RE.fullmatch(self.method):
            problems.append(f"{path}.method must be a namespaced identifier")
        problems.extend(_unique(self.alternatives, f"{path}.alternatives", identifiers=True))
        problems.extend(_unique(self.evidence, f"{path}.evidence"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "concept_id": self.concept_id,
            "confidence": self.confidence,
            "method": self.method,
            "alternatives": list(self.alternatives),
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> FieldConceptMatch:
        data = dict(value)
        data["alternatives"] = tuple(data.get("alternatives", ()))
        data["evidence"] = tuple(data.get("evidence", ()))
        return cls(**data)


@dataclass(frozen=True)
class SemanticFieldMap:
    dataset_digest: str
    mapping_policy_id: str
    matches: tuple[FieldConceptMatch, ...]
    unmapped_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def concepts(self) -> frozenset[str]:
        return frozenset(match.concept_id for match in self.matches)

    def fields_for(self, concept_ids: tuple[str, ...]) -> tuple[str, ...]:
        requested = set(concept_ids)
        return tuple(
            match.field_name for match in self.matches if match.concept_id in requested
        )

    def validate(self, path: str = "semantic_field_map") -> list[str]:
        problems: list[str] = []
        if not DIGEST_RE.fullmatch(self.dataset_digest):
            problems.append(f"{path}.dataset_digest must be a sha256 digest")
        if not ID_RE.fullmatch(self.mapping_policy_id):
            problems.append(f"{path}.mapping_policy_id must be a namespaced identifier")
        field_names = tuple(match.field_name for match in self.matches)
        if len(field_names) != len(set(field_names)):
            problems.append(f"{path}.matches must map each field at most once")
        for index, match in enumerate(self.matches):
            problems.extend(match.validate(f"{path}.matches[{index}]"))
        problems.extend(_unique(self.unmapped_fields, f"{path}.unmapped_fields"))
        if set(field_names) & set(self.unmapped_fields):
            problems.append(f"{path} mapped and unmapped field sets must be disjoint")
        problems.extend(_unique(self.warnings, f"{path}.warnings"))
        problems.extend(_extensions_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "interrogation_model_version": INTERROGATION_MODEL_VERSION,
            "dataset_digest": self.dataset_digest,
            "mapping_policy_id": self.mapping_policy_id,
            "matches": [item.to_dict() for item in self.matches],
            "unmapped_fields": list(self.unmapped_fields),
            "warnings": list(self.warnings),
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SemanticFieldMap:
        data = dict(value)
        data.pop("interrogation_model_version", None)
        data["matches"] = tuple(FieldConceptMatch.from_dict(item) for item in data["matches"])
        data["unmapped_fields"] = tuple(data.get("unmapped_fields", ()))
        data["warnings"] = tuple(data.get("warnings", ()))
        data["extensions"] = tuple(data.get("extensions", {}).items())
        return cls(**data)


@dataclass(frozen=True)
class CheckRequirement:
    capability: str
    mode: str
    optional: bool = False
    effect: str = ""
    permission: str = ""
    cost_tier: int = 1
    evidence_kinds: tuple[str, ...] = ()

    def validate(self, path: str = "check") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.capability):
            problems.append(f"{path}.capability must be a namespaced identifier")
        if self.mode not in QUESTION_MODES:
            problems.append(f"{path}.mode must be one of {QUESTION_MODES}")
        if self.effect and not ID_RE.fullmatch(self.effect):
            problems.append(f"{path}.effect must be empty or namespaced")
        if self.permission and not ID_RE.fullmatch(self.permission):
            problems.append(f"{path}.permission must be empty or namespaced")
        if self.cost_tier < 1 or self.cost_tier > 10:
            problems.append(f"{path}.cost_tier must be between one and ten")
        problems.extend(_unique(self.evidence_kinds, f"{path}.evidence_kinds", identifiers=True))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "mode": self.mode,
            "optional": self.optional,
            "effect": self.effect,
            "permission": self.permission,
            "cost_tier": self.cost_tier,
            "evidence_kinds": list(self.evidence_kinds),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CheckRequirement:
        data = dict(value)
        data["evidence_kinds"] = tuple(data.get("evidence_kinds", ()))
        return cls(**data)


@dataclass(frozen=True)
class QuestionDefinition:
    id: str
    version: str
    title: str
    question: str
    concept_ids: tuple[str, ...]
    scope: str
    finding_code: str
    severity: str
    checks: tuple[CheckRequirement, ...]
    preconditions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    evidence_required: tuple[str, ...] = ()
    repair_families: tuple[str, ...] = ()
    abstain_when: tuple[str, ...] = ()
    jurisdictions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    references: tuple[StandardsReference, ...] = ()
    privacy_class: str = "privacy.aggregate"
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "question") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.finding_code):
            problems.append(f"{path}.id and finding_code must be namespaced identifiers")
        if not self.version.strip() or not self.title.strip() or not self.question.strip():
            problems.append(f"{path}.version, title, and question must not be empty")
        problems.extend(_unique(self.concept_ids, f"{path}.concept_ids", identifiers=True))
        if not self.concept_ids:
            problems.append(f"{path}.concept_ids must not be empty")
        if self.scope not in QUESTION_SCOPES:
            problems.append(f"{path}.scope must be one of {QUESTION_SCOPES}")
        if self.severity not in QUESTION_SEVERITIES:
            problems.append(f"{path}.severity must be one of {QUESTION_SEVERITIES}")
        if not self.checks:
            problems.append(f"{path}.checks must not be empty")
        capabilities = tuple(check.capability for check in self.checks)
        problems.extend(_unique(capabilities, f"{path}.checks capabilities", identifiers=True))
        for index, check in enumerate(self.checks):
            problems.extend(check.validate(f"{path}.checks[{index}]"))
        for label, values, identifiers in (
            ("preconditions", self.preconditions, True),
            ("dependencies", self.dependencies, True),
            ("evidence_required", self.evidence_required, True),
            ("repair_families", self.repair_families, True),
            ("tags", self.tags, True),
            ("abstain_when", self.abstain_when, False),
            ("jurisdictions", self.jurisdictions, False),
        ):
            problems.extend(_unique(values, f"{path}.{label}", identifiers=identifiers))
        if not ID_RE.fullmatch(self.privacy_class):
            problems.append(f"{path}.privacy_class must be a namespaced identifier")
        for index, reference in enumerate(self.references):
            problems.extend(reference.validate(f"{path}.references[{index}]"))
        problems.extend(_extensions_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "interrogation_model_version": INTERROGATION_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "question": self.question,
            "concept_ids": list(self.concept_ids),
            "scope": self.scope,
            "finding_code": self.finding_code,
            "severity": self.severity,
            "checks": [check.to_dict() for check in self.checks],
            "preconditions": list(self.preconditions),
            "dependencies": list(self.dependencies),
            "evidence_required": list(self.evidence_required),
            "repair_families": list(self.repair_families),
            "abstain_when": list(self.abstain_when),
            "jurisdictions": list(self.jurisdictions),
            "tags": list(self.tags),
            "references": [item.to_dict() for item in self.references],
            "privacy_class": self.privacy_class,
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> QuestionDefinition:
        data = dict(value)
        data.pop("interrogation_model_version", None)
        for key in (
            "concept_ids",
            "preconditions",
            "dependencies",
            "evidence_required",
            "repair_families",
            "abstain_when",
            "jurisdictions",
            "tags",
        ):
            data[key] = tuple(data.get(key, ()))
        data["checks"] = tuple(CheckRequirement.from_dict(item) for item in data["checks"])
        data["references"] = tuple(
            StandardsReference.from_dict(item) for item in data.get("references", ())
        )
        data["extensions"] = tuple(data.get("extensions", {}).items())
        return cls(**data)


@dataclass(frozen=True)
class QuestionPack:
    id: str
    version: str
    title: str
    description: str
    concept_ids: tuple[str, ...]
    questions: tuple[QuestionDefinition, ...]
    source: str
    license: str
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(
        self,
        concepts: tuple[ConceptDefinition, ...] = (),
        path: str = "question_pack",
    ) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.version.strip() or not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.version, title, and description must not be empty")
        if not self.source.strip() or not self.license.strip():
            problems.append(f"{path}.source and license must not be empty")
        problems.extend(_unique(self.concept_ids, f"{path}.concept_ids", identifiers=True))
        question_ids = tuple(question.id for question in self.questions)
        problems.extend(_unique(question_ids, f"{path}.questions ids", identifiers=True))
        if not self.questions:
            problems.append(f"{path}.questions must not be empty")
        declared = set(self.concept_ids)
        for index, question in enumerate(self.questions):
            problems.extend(question.validate(f"{path}.questions[{index}]"))
            missing = sorted(set(question.concept_ids) - declared)
            if missing:
                problems.append(
                    f"{path}.questions[{index}] uses undeclared concepts: " + ", ".join(missing)
                )
        if concepts:
            available = {concept.id for concept in concepts}
            missing = sorted(declared - available)
            if missing:
                problems.append(f"{path} references unknown concepts: " + ", ".join(missing))
        problems.extend(_extensions_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "interrogation_model_version": INTERROGATION_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "concept_ids": list(self.concept_ids),
            "questions": [question.to_dict() for question in self.questions],
            "source": self.source,
            "license": self.license,
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> QuestionPack:
        data = dict(value)
        data.pop("interrogation_model_version", None)
        data["concept_ids"] = tuple(data.get("concept_ids", ()))
        data["questions"] = tuple(
            QuestionDefinition.from_dict(item) for item in data.get("questions", ())
        )
        data["extensions"] = tuple(data.get("extensions", {}).items())
        return cls(**data)


@dataclass(frozen=True)
class InterrogationBudget:
    id: str
    effort_level: int
    allowed_modes: tuple[str, ...]
    granted_permissions: tuple[str, ...] = ()
    max_cost_tier: int = 1
    max_questions: int | None = None
    exhaustive: bool = False
    exploration_fraction: float = 0.10
    random_seed: int = 0

    def validate(self, path: str = "budget") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if self.effort_level not in (1, 3, 5, 7, 10):
            problems.append(f"{path}.effort_level must be one of 1, 3, 5, 7, 10")
        if not self.allowed_modes or any(mode not in QUESTION_MODES for mode in self.allowed_modes):
            problems.append(f"{path}.allowed_modes must use known question modes")
        problems.extend(_unique(self.allowed_modes, f"{path}.allowed_modes"))
        problems.extend(
            _unique(self.granted_permissions, f"{path}.granted_permissions", identifiers=True)
        )
        if self.max_cost_tier < 1 or self.max_cost_tier > 10:
            problems.append(f"{path}.max_cost_tier must be between one and ten")
        if self.max_questions is not None and self.max_questions <= 0:
            problems.append(f"{path}.max_questions must be positive or null")
        if self.exhaustive and self.max_questions is not None:
            problems.append(f"{path}.exhaustive budgets cannot cap max_questions")
        if not isfinite(self.exploration_fraction) or not 0 <= self.exploration_fraction <= 1:
            problems.append(f"{path}.exploration_fraction must be between zero and one")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "effort_level": self.effort_level,
            "allowed_modes": list(self.allowed_modes),
            "granted_permissions": list(self.granted_permissions),
            "max_cost_tier": self.max_cost_tier,
            "max_questions": self.max_questions,
            "exhaustive": self.exhaustive,
            "exploration_fraction": self.exploration_fraction,
            "random_seed": self.random_seed,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> InterrogationBudget:
        data = dict(value)
        data["allowed_modes"] = tuple(data["allowed_modes"])
        data["granted_permissions"] = tuple(data.get("granted_permissions", ()))
        return cls(**data)


@dataclass(frozen=True)
class QuestionPlanItem:
    question_id: str
    question_digest: str
    pack_id: str
    status: str
    fields: tuple[str, ...]
    priority: float
    selected_capability: str = ""
    selected_mode: str = ""
    reasons: tuple[str, ...] = ()
    historical_observations: int = 0
    historical_utility: float = 0.0

    def validate(self, path: str = "plan_item") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.question_id) or not ID_RE.fullmatch(self.pack_id):
            problems.append(f"{path}.question_id and pack_id must be namespaced identifiers")
        if not DIGEST_RE.fullmatch(self.question_digest):
            problems.append(f"{path}.question_digest must be a sha256 digest")
        if self.status not in PLAN_STATUSES:
            problems.append(f"{path}.status must be one of {PLAN_STATUSES}")
        if not isfinite(self.priority):
            problems.append(f"{path}.priority must be finite")
        if self.status == "selected":
            if not ID_RE.fullmatch(self.selected_capability):
                problems.append(f"{path}.selected_capability is required for selected items")
            if self.selected_mode not in QUESTION_MODES:
                problems.append(f"{path}.selected_mode is required for selected items")
        if self.historical_observations < 0 or not isfinite(self.historical_utility):
            problems.append(f"{path} historical values must be finite and non-negative in count")
        problems.extend(_unique(self.fields, f"{path}.fields"))
        problems.extend(_unique(self.reasons, f"{path}.reasons"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question_digest": self.question_digest,
            "pack_id": self.pack_id,
            "status": self.status,
            "fields": list(self.fields),
            "priority": self.priority,
            "selected_capability": self.selected_capability,
            "selected_mode": self.selected_mode,
            "reasons": list(self.reasons),
            "historical_observations": self.historical_observations,
            "historical_utility": self.historical_utility,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> QuestionPlanItem:
        data = dict(value)
        data["fields"] = tuple(data.get("fields", ()))
        data["reasons"] = tuple(data.get("reasons", ()))
        return cls(**data)


@dataclass(frozen=True)
class QuestionPlan:
    dataset_profile_digest: str
    semantic_field_map_digest: str
    question_pack_digests: tuple[str, ...]
    budget: InterrogationBudget
    items: tuple[QuestionPlanItem, ...]
    planner_id: str
    planner_version: str
    historical_revision: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self._content_dict())

    @property
    def id(self) -> str:
        return "question-plan." + self.digest.removeprefix("sha256:")

    def validate(self, path: str = "question_plan") -> list[str]:
        problems: list[str] = []
        for label, digest in (
            ("dataset_profile_digest", self.dataset_profile_digest),
            ("semantic_field_map_digest", self.semantic_field_map_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be a sha256 digest")
        if any(not DIGEST_RE.fullmatch(item) for item in self.question_pack_digests):
            problems.append(f"{path}.question_pack_digests must contain sha256 digests")
        if len(self.question_pack_digests) != len(set(self.question_pack_digests)):
            problems.append(f"{path}.question_pack_digests must be unique")
        problems.extend(self.budget.validate(f"{path}.budget"))
        keys = tuple(item.question_id for item in self.items)
        problems.extend(_unique(keys, f"{path}.items question ids", identifiers=True))
        for index, item in enumerate(self.items):
            problems.extend(item.validate(f"{path}.items[{index}]"))
        if not ID_RE.fullmatch(self.planner_id) or not self.planner_version.strip():
            problems.append(f"{path}.planner identity must be valid")
        if self.historical_revision and not DIGEST_RE.fullmatch(self.historical_revision):
            problems.append(f"{path}.historical_revision must be empty or a sha256 digest")
        problems.extend(_unique(self.warnings, f"{path}.warnings"))
        return problems

    def _content_dict(self) -> dict[str, Any]:
        return {
            "interrogation_model_version": INTERROGATION_MODEL_VERSION,
            "dataset_profile_digest": self.dataset_profile_digest,
            "semantic_field_map_digest": self.semantic_field_map_digest,
            "question_pack_digests": list(self.question_pack_digests),
            "budget": self.budget.to_dict(),
            "items": [item.to_dict() for item in self.items],
            "planner_id": self.planner_id,
            "planner_version": self.planner_version,
            "historical_revision": self.historical_revision,
            "warnings": list(self.warnings),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, **self._content_dict()}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> QuestionPlan:
        data = dict(value)
        data.pop("interrogation_model_version", None)
        data.pop("id", None)
        data["question_pack_digests"] = tuple(data["question_pack_digests"])
        data["budget"] = InterrogationBudget.from_dict(data["budget"])
        data["items"] = tuple(QuestionPlanItem.from_dict(item) for item in data["items"])
        data["warnings"] = tuple(data.get("warnings", ()))
        return cls(**data)


@dataclass(frozen=True)
class Finding:
    question_id: str
    question_digest: str
    code: str
    severity: str
    confidence: float
    fields: tuple[str, ...]
    row_ids: tuple[str, ...]
    affected_count: int
    evidence: tuple[tuple[str, Any], ...]
    sample_value_digests: tuple[str, ...] = ()
    remediation_families: tuple[str, ...] = ()
    summary: str = ""

    @property
    def digest(self) -> str:
        return sha256_digest(self._content_dict())

    @property
    def id(self) -> str:
        return "finding." + self.digest.removeprefix("sha256:")

    def validate(self, path: str = "finding") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.question_id) or not ID_RE.fullmatch(self.code):
            problems.append(f"{path}.question_id and code must be namespaced identifiers")
        if not DIGEST_RE.fullmatch(self.question_digest):
            problems.append(f"{path}.question_digest must be a sha256 digest")
        if self.severity not in QUESTION_SEVERITIES:
            problems.append(f"{path}.severity must be known")
        if not isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            problems.append(f"{path}.confidence must be between zero and one")
        if self.affected_count < 0 or self.affected_count < len(self.row_ids):
            problems.append(f"{path}.affected_count must cover disclosed row ids")
        problems.extend(_unique(self.fields, f"{path}.fields"))
        problems.extend(_unique(self.row_ids, f"{path}.row_ids"))
        problems.extend(
            _unique(self.remediation_families, f"{path}.remediation_families", identifiers=True)
        )
        if any(not DIGEST_RE.fullmatch(item) for item in self.sample_value_digests):
            problems.append(f"{path}.sample_value_digests must be sha256 digests")
        problems.extend(_extensions_problems(self.evidence, f"{path}.evidence"))
        return problems

    def _content_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question_digest": self.question_digest,
            "code": self.code,
            "severity": self.severity,
            "confidence": self.confidence,
            "fields": list(self.fields),
            "row_ids": list(self.row_ids),
            "affected_count": self.affected_count,
            "evidence": {key: _json_value(value) for key, value in self.evidence},
            "sample_value_digests": list(self.sample_value_digests),
            "remediation_families": list(self.remediation_families),
            "summary": self.summary,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, **self._content_dict()}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Finding:
        data = dict(value)
        data.pop("id", None)
        for key in ("fields", "row_ids", "sample_value_digests", "remediation_families"):
            data[key] = tuple(data.get(key, ()))
        data["evidence"] = tuple(data.get("evidence", {}).items())
        return cls(**data)


@dataclass(frozen=True)
class QuestionReceipt:
    id: str
    plan_digest: str
    dataset_digest: str
    question_id: str
    question_digest: str
    check_capability: str
    check_implementation_id: str
    check_implementation_version: str
    check_implementation_digest: str
    mode: str
    outcome: str
    fields: tuple[str, ...]
    rows_examined: int
    coverage: float
    finding_ids: tuple[str, ...] = ()
    evidence: tuple[tuple[str, Any], ...] = ()
    error_code: str = ""
    latency_ms: float = 0.0

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "question_receipt") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("question_id", self.question_id),
            ("check_capability", self.check_capability),
            ("check_implementation_id", self.check_implementation_id),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        for label, digest in (
            ("plan_digest", self.plan_digest),
            ("dataset_digest", self.dataset_digest),
            ("question_digest", self.question_digest),
            ("check_implementation_digest", self.check_implementation_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be a sha256 digest")
        if self.mode not in QUESTION_MODES or self.outcome not in QUESTION_OUTCOMES:
            problems.append(f"{path}.mode or outcome is invalid")
        if self.rows_examined < 0 or not isfinite(self.coverage) or not 0 <= self.coverage <= 1:
            problems.append(f"{path}.rows_examined and coverage must be valid")
        if not isfinite(self.latency_ms) or self.latency_ms < 0:
            problems.append(f"{path}.latency_ms must be finite and non-negative")
        problems.extend(_unique(self.fields, f"{path}.fields"))
        problems.extend(_unique(self.finding_ids, f"{path}.finding_ids", identifiers=True))
        if self.error_code and not ID_RE.fullmatch(self.error_code):
            problems.append(f"{path}.error_code must be empty or namespaced")
        problems.extend(_extensions_problems(self.evidence, f"{path}.evidence"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "interrogation_model_version": INTERROGATION_MODEL_VERSION,
            "id": self.id,
            "plan_digest": self.plan_digest,
            "dataset_digest": self.dataset_digest,
            "question_id": self.question_id,
            "question_digest": self.question_digest,
            "check_capability": self.check_capability,
            "check_implementation_id": self.check_implementation_id,
            "check_implementation_version": self.check_implementation_version,
            "check_implementation_digest": self.check_implementation_digest,
            "mode": self.mode,
            "outcome": self.outcome,
            "fields": list(self.fields),
            "rows_examined": self.rows_examined,
            "coverage": self.coverage,
            "finding_ids": list(self.finding_ids),
            "evidence": {key: _json_value(value) for key, value in self.evidence},
            "error_code": self.error_code,
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True)
class FindingSet:
    dataset_digest: str
    plan_digest: str
    receipts: tuple[QuestionReceipt, ...]
    findings: tuple[Finding, ...]
    executor_id: str
    executor_version: str

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "finding_set") -> list[str]:
        problems: list[str] = []
        if not DIGEST_RE.fullmatch(self.dataset_digest) or not DIGEST_RE.fullmatch(self.plan_digest):
            problems.append(f"{path} dataset and plan digests must be sha256 digests")
        if not ID_RE.fullmatch(self.executor_id) or not self.executor_version.strip():
            problems.append(f"{path}.executor identity must be valid")
        receipt_ids = tuple(receipt.id for receipt in self.receipts)
        problems.extend(_unique(receipt_ids, f"{path}.receipts ids", identifiers=True))
        finding_ids = tuple(finding.id for finding in self.findings)
        problems.extend(_unique(finding_ids, f"{path}.findings ids", identifiers=True))
        for index, receipt in enumerate(self.receipts):
            problems.extend(receipt.validate(f"{path}.receipts[{index}]"))
            unknown = sorted(set(receipt.finding_ids) - set(finding_ids))
            if unknown:
                problems.append(f"{path}.receipts[{index}] references unknown findings")
        for index, finding in enumerate(self.findings):
            problems.extend(finding.validate(f"{path}.findings[{index}]"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "interrogation_model_version": INTERROGATION_MODEL_VERSION,
            "dataset_digest": self.dataset_digest,
            "plan_digest": self.plan_digest,
            "receipts": [receipt.to_dict() for receipt in self.receipts],
            "findings": [finding.to_dict() for finding in self.findings],
            "executor_id": self.executor_id,
            "executor_version": self.executor_version,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> FindingSet:
        data = dict(value)
        data.pop("interrogation_model_version", None)
        receipt_values = []
        for item in data["receipts"]:
            receipt = dict(item)
            receipt.pop("interrogation_model_version", None)
            receipt["fields"] = tuple(receipt.get("fields", ()))
            receipt["finding_ids"] = tuple(receipt.get("finding_ids", ()))
            receipt["evidence"] = tuple(receipt.get("evidence", {}).items())
            receipt_values.append(QuestionReceipt(**receipt))
        data["receipts"] = tuple(receipt_values)
        data["findings"] = tuple(Finding.from_dict(item) for item in data["findings"])
        return cls(**data)


@dataclass(frozen=True)
class PatchOperation:
    id: str
    finding_id: str
    row_id: str
    row_index: int
    field_name: str
    action: str
    before_digest: str
    after_value: Any = None
    before_value: Any = None
    reversible: bool = True
    safe_to_auto_apply: bool = False
    reason: str = ""

    def validate(self, path: str = "patch") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.finding_id):
            problems.append(f"{path}.id and finding_id must be namespaced identifiers")
        if self.row_index < 0 or not self.row_id.strip() or not self.field_name.strip():
            problems.append(f"{path} row and field identities must be valid")
        if self.action not in PATCH_ACTIONS:
            problems.append(f"{path}.action must be one of {PATCH_ACTIONS}")
        if not DIGEST_RE.fullmatch(self.before_digest):
            problems.append(f"{path}.before_digest must be a sha256 digest")
        try:
            canonical_json(self.before_value)
            canonical_json(self.after_value)
        except (TypeError, ValueError):
            problems.append(f"{path} values must be JSON serialisable")
        if self.safe_to_auto_apply and not self.reversible:
            problems.append(f"{path} an automatically applied patch must be reversible")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "finding_id": self.finding_id,
            "row_id": self.row_id,
            "row_index": self.row_index,
            "field_name": self.field_name,
            "action": self.action,
            "before_digest": self.before_digest,
            "before_value": _json_value(self.before_value),
            "after_value": _json_value(self.after_value),
            "reversible": self.reversible,
            "safe_to_auto_apply": self.safe_to_auto_apply,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PatchOperation:
        return cls(**value)


@dataclass(frozen=True)
class RepairProposal:
    dataset_digest: str
    finding_set_digest: str
    repair_family: str
    strategy: str
    operations: tuple[PatchOperation, ...]
    proposer_id: str
    proposer_version: str
    requires_approval: bool = True
    notes: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self._content_dict())

    @property
    def id(self) -> str:
        return "repair-proposal." + self.digest.removeprefix("sha256:")

    def validate(self, path: str = "repair_proposal") -> list[str]:
        problems: list[str] = []
        if not DIGEST_RE.fullmatch(self.dataset_digest) or not DIGEST_RE.fullmatch(
            self.finding_set_digest
        ):
            problems.append(f"{path} dataset and finding-set digests must be sha256 digests")
        for label, value in (
            ("repair_family", self.repair_family),
            ("strategy", self.strategy),
            ("proposer_id", self.proposer_id),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        if not self.proposer_version.strip():
            problems.append(f"{path}.proposer_version must not be empty")
        operation_ids = tuple(operation.id for operation in self.operations)
        problems.extend(_unique(operation_ids, f"{path}.operations ids", identifiers=True))
        for index, operation in enumerate(self.operations):
            problems.extend(operation.validate(f"{path}.operations[{index}]"))
        if not self.requires_approval and any(
            not operation.safe_to_auto_apply for operation in self.operations
        ):
            problems.append(f"{path} cannot bypass approval for review-only operations")
        problems.extend(_unique(self.notes, f"{path}.notes"))
        return problems

    def _content_dict(self) -> dict[str, Any]:
        return {
            "interrogation_model_version": INTERROGATION_MODEL_VERSION,
            "dataset_digest": self.dataset_digest,
            "finding_set_digest": self.finding_set_digest,
            "repair_family": self.repair_family,
            "strategy": self.strategy,
            "operations": [operation.to_dict() for operation in self.operations],
            "proposer_id": self.proposer_id,
            "proposer_version": self.proposer_version,
            "requires_approval": self.requires_approval,
            "notes": list(self.notes),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, **self._content_dict()}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RepairProposal:
        data = dict(value)
        data.pop("interrogation_model_version", None)
        data.pop("id", None)
        data["operations"] = tuple(PatchOperation.from_dict(item) for item in data["operations"])
        data["notes"] = tuple(data.get("notes", ()))
        return cls(**data)


@dataclass(frozen=True)
class RepairApplicationReceipt:
    id: str
    proposal_digest: str
    input_dataset_digest: str
    output_dataset_digest: str
    applied_operation_ids: tuple[str, ...]
    skipped_operation_ids: tuple[str, ...]
    status: str
    errors: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "repair_application") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        for label, digest in (
            ("proposal_digest", self.proposal_digest),
            ("input_dataset_digest", self.input_dataset_digest),
            ("output_dataset_digest", self.output_dataset_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be a sha256 digest")
        if self.status not in ("applied", "partial", "no-change", "failed"):
            problems.append(f"{path}.status is invalid")
        problems.extend(
            _unique(self.applied_operation_ids, f"{path}.applied_operation_ids", identifiers=True)
        )
        problems.extend(
            _unique(self.skipped_operation_ids, f"{path}.skipped_operation_ids", identifiers=True)
        )
        if set(self.applied_operation_ids) & set(self.skipped_operation_ids):
            problems.append(f"{path} applied and skipped operations must be disjoint")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_digest": self.proposal_digest,
            "input_dataset_digest": self.input_dataset_digest,
            "output_dataset_digest": self.output_dataset_digest,
            "applied_operation_ids": list(self.applied_operation_ids),
            "skipped_operation_ids": list(self.skipped_operation_ids),
            "status": self.status,
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RepairApplicationReceipt:
        data = dict(value)
        data["applied_operation_ids"] = tuple(data.get("applied_operation_ids", ()))
        data["skipped_operation_ids"] = tuple(data.get("skipped_operation_ids", ()))
        data["errors"] = tuple(data.get("errors", ()))
        return cls(**data)


@dataclass(frozen=True)
class VerificationReceipt:
    id: str
    proposal_digest: str
    application_receipt_digest: str
    before_finding_set_digest: str
    after_finding_set_digest: str
    verifier_id: str
    verifier_version: str
    verifier_digest: str
    independence: str
    resolved_finding_ids: tuple[str, ...]
    remaining_finding_ids: tuple[str, ...]
    introduced_finding_ids: tuple[str, ...]
    unchanged_field_count: int
    decision: str
    reasons: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "verification") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.verifier_id):
            problems.append(f"{path}.id and verifier_id must be namespaced identifiers")
        for label, digest in (
            ("proposal_digest", self.proposal_digest),
            ("application_receipt_digest", self.application_receipt_digest),
            ("before_finding_set_digest", self.before_finding_set_digest),
            ("after_finding_set_digest", self.after_finding_set_digest),
            ("verifier_digest", self.verifier_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be a sha256 digest")
        if not self.verifier_version.strip() or not ID_RE.fullmatch(self.independence):
            problems.append(f"{path} verifier version and independence must be valid")
        if self.decision not in REPAIR_DECISIONS:
            problems.append(f"{path}.decision must be one of {REPAIR_DECISIONS}")
        if self.unchanged_field_count < 0:
            problems.append(f"{path}.unchanged_field_count must be non-negative")
        groups = (
            self.resolved_finding_ids,
            self.remaining_finding_ids,
            self.introduced_finding_ids,
        )
        for index, group in enumerate(groups):
            problems.extend(_unique(group, f"{path}.finding_group[{index}]", identifiers=True))
        if any(set(left) & set(right) for i, left in enumerate(groups) for right in groups[i + 1 :]):
            problems.append(f"{path} finding outcome groups must be disjoint")
        problems.extend(_unique(self.reasons, f"{path}.reasons"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "interrogation_model_version": INTERROGATION_MODEL_VERSION,
            "id": self.id,
            "proposal_digest": self.proposal_digest,
            "application_receipt_digest": self.application_receipt_digest,
            "before_finding_set_digest": self.before_finding_set_digest,
            "after_finding_set_digest": self.after_finding_set_digest,
            "verifier_id": self.verifier_id,
            "verifier_version": self.verifier_version,
            "verifier_digest": self.verifier_digest,
            "independence": self.independence,
            "resolved_finding_ids": list(self.resolved_finding_ids),
            "remaining_finding_ids": list(self.remaining_finding_ids),
            "introduced_finding_ids": list(self.introduced_finding_ids),
            "unchanged_field_count": self.unchanged_field_count,
            "decision": self.decision,
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> VerificationReceipt:
        data = dict(value)
        data.pop("interrogation_model_version", None)
        for key in (
            "resolved_finding_ids",
            "remaining_finding_ids",
            "introduced_finding_ids",
            "reasons",
        ):
            data[key] = tuple(data.get(key, ()))
        return cls(**data)


__all__ = [
    "INTERROGATION_MODEL_VERSION",
    "PATCH_ACTIONS",
    "PLAN_STATUSES",
    "QUESTION_MODES",
    "QUESTION_OUTCOMES",
    "QUESTION_SCOPES",
    "QUESTION_SEVERITIES",
    "REPAIR_DECISIONS",
    "CheckRequirement",
    "ConceptDefinition",
    "DatasetProfile",
    "FieldConceptMatch",
    "FieldProfile",
    "Finding",
    "FindingSet",
    "InterrogationBudget",
    "PatchOperation",
    "QuestionDefinition",
    "QuestionPack",
    "QuestionPlan",
    "QuestionPlanItem",
    "QuestionReceipt",
    "RepairApplicationReceipt",
    "RepairProposal",
    "SemanticFieldMap",
    "StandardsReference",
    "VerificationReceipt",
]
