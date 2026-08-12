"""Task fingerprints and history-informed initialization for SolutionGraph.

This module supplies optimizer priors, never compiler authority.  It preserves
the full admitted candidate space, records uncertainty and provenance, keeps
history-blind/random lanes, and produces an initialization object that the
ordinary :class:`UniversalSolver` can independently validate and execute.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from math import ceil, exp, isfinite, log, log2, sqrt
from random import Random
from statistics import fmean, median
from typing import Any, Protocol

from solutiongraph.evidence import Objective, RunReceipt
from solutiongraph.model import (
    DIGEST_RE,
    ID_RE,
    AdmittedSpace,
    canonical_json,
    sha256_digest,
)
from solutiongraph.search import (
    BeliefModel,
    CandidateWeight,
    InteractionWeight,
    SearchBudget,
    SearchEngine,
    SearchMode,
)
from solutiongraph.task_categories import (
    DEFAULT_TASK_CATEGORY_REGISTRY,
    TaskCategoryMatch,
    TaskCategoryRegistry,
)
from solutiongraph.tasking import TaskContract

TASK_INTELLIGENCE_MODEL_VERSION = "0.1"


def _json_value(value: Any) -> Any:
    return json.loads(canonical_json(value))


def _json_problems(value: Any, path: str) -> list[str]:
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        return [f"{path} must be JSON serialisable"]
    return []


def _finite_numbers(value: Any, path: str) -> list[str]:
    problems: list[str] = []
    if isinstance(value, bool) or value is None:
        return problems
    if isinstance(value, (int, float)):
        if not isfinite(float(value)):
            problems.append(f"{path} numeric values must be finite")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            problems.extend(_finite_numbers(child, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            problems.extend(_finite_numbers(child, f"{path}[{index}]"))
    return problems


def _extension_problems(extensions: tuple[tuple[str, Any], ...], path: str) -> list[str]:
    problems: list[str] = []
    keys = [key for key, _ in extensions]
    if len(keys) != len(set(keys)):
        problems.append(f"{path} keys must be unique")
    for key, value in extensions:
        if not ID_RE.fullmatch(key) or "." not in key:
            problems.append(f"{path}.{key} must use a namespaced key")
        problems.extend(_json_problems(value, f"{path}.{key}"))
        problems.extend(_finite_numbers(value, f"{path}.{key}"))
    return problems


def _quantile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _rollup(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {key: 0.0 for key in ("mean", "std", "min", "q10", "q50", "q90", "max")}
    numeric = [float(value) for value in values]
    mean = fmean(numeric)
    variance = fmean((value - mean) ** 2 for value in numeric)
    return {
        "mean": mean,
        "std": sqrt(variance),
        "min": min(numeric),
        "q10": _quantile(numeric, 0.10),
        "q50": _quantile(numeric, 0.50),
        "q90": _quantile(numeric, 0.90),
        "max": max(numeric),
    }


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:
        return True
    return isinstance(value, str) and not value.strip()


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or _is_missing(value):
        return None
    if isinstance(value, (int, float)) and isfinite(float(value)):
        return float(value)
    return None


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) < 3 or len(left) != len(right):
        return 0.0
    left_mean = fmean(left)
    right_mean = fmean(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_scale = sum((value - left_mean) ** 2 for value in left)
    right_scale = sum((value - right_mean) ** 2 for value in right)
    denominator = sqrt(left_scale * right_scale)
    return numerator / denominator if denominator else 0.0


@dataclass(frozen=True)
class FingerprintAttribute:
    """One missing-aware, provenance-bearing task attribute."""

    key: str
    value: Any
    availability: str = "availability.available"
    evidence_kind: str = "evidence.observed"
    compute_tier: str = "tier.a"
    confidence: float = 1.0
    uncertainty: float = 0.0
    sample_size: int | None = None
    random_seed: int | None = None
    source: str = ""

    def validate(self, path: str = "attribute") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.key) or "." not in self.key:
            problems.append(f"{path}.key must be an extensible namespaced identifier")
        for label, value in (
            ("availability", self.availability),
            ("evidence_kind", self.evidence_kind),
            ("compute_tier", self.compute_tier),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        if not isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            problems.append(f"{path}.confidence must be finite and between zero and one")
        if not isfinite(self.uncertainty) or self.uncertainty < 0:
            problems.append(f"{path}.uncertainty must be finite and non-negative")
        if self.sample_size is not None and self.sample_size < 0:
            problems.append(f"{path}.sample_size must be non-negative or null")
        if self.random_seed is not None and isinstance(self.random_seed, bool):
            problems.append(f"{path}.random_seed must be an integer or null")
        problems.extend(_json_problems(self.value, f"{path}.value"))
        problems.extend(_finite_numbers(self.value, f"{path}.value"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": _json_value(self.value),
            "availability": self.availability,
            "evidence_kind": self.evidence_kind,
            "compute_tier": self.compute_tier,
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "sample_size": self.sample_size,
            "random_seed": self.random_seed,
            "source": self.source,
        }


@dataclass(frozen=True)
class TaskEmbedding:
    """An optional exact embedding record; never a compatibility claim."""

    kind: str
    encoder_id: str
    encoder_version: str
    vector: tuple[float, ...]
    encoder_digest: str = ""
    input_manifest_digest: str = ""
    privacy_class: str = "privacy.derived"
    confidence: float = 1.0

    def validate(self, path: str = "embedding") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.kind) or not ID_RE.fullmatch(self.encoder_id):
            problems.append(f"{path}.kind and encoder_id must be namespaced identifiers")
        if not self.encoder_version.strip():
            problems.append(f"{path}.encoder_version must not be empty")
        if not self.vector or any(not isfinite(value) for value in self.vector):
            problems.append(f"{path}.vector must contain finite values")
        for label, digest in (
            ("encoder_digest", self.encoder_digest),
            ("input_manifest_digest", self.input_manifest_digest),
        ):
            if digest and not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be empty or a sha256 digest")
        if not ID_RE.fullmatch(self.privacy_class):
            problems.append(f"{path}.privacy_class must be a namespaced identifier")
        if not isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            problems.append(f"{path}.confidence must be finite and between zero and one")
        return problems

    @property
    def space_key(self) -> tuple[str, str, str, str]:
        return (self.kind, self.encoder_id, self.encoder_version, self.encoder_digest)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "encoder_id": self.encoder_id,
            "encoder_version": self.encoder_version,
            "encoder_digest": self.encoder_digest,
            "input_manifest_digest": self.input_manifest_digest,
            "privacy_class": self.privacy_class,
            "confidence": self.confidence,
            "vector": list(self.vector),
        }


@dataclass(frozen=True)
class TaskFingerprint:
    """Content-addressed progressive task profile with an availability mask."""

    task_contract_digest: str
    task_id: str
    knowledge_layer: str
    legal_information_boundary: str
    profile_policy_id: str
    attributes: tuple[FingerprintAttribute, ...]
    dataset_family_id: str = ""
    category_matches: tuple[TaskCategoryMatch, ...] = ()
    embeddings: tuple[TaskEmbedding, ...] = ()
    warnings: tuple[str, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def id(self) -> str:
        return "fingerprint." + self.digest.removeprefix("sha256:")

    @property
    def attribute_map(self) -> dict[str, FingerprintAttribute]:
        return {attribute.key: attribute for attribute in self.attributes}

    def validate(self, path: str = "fingerprint") -> list[str]:
        problems: list[str] = []
        if not DIGEST_RE.fullmatch(self.task_contract_digest):
            problems.append(f"{path}.task_contract_digest must be a sha256 digest")
        if not ID_RE.fullmatch(self.task_id):
            problems.append(f"{path}.task_id must be a namespaced identifier")
        if not self.knowledge_layer.startswith("K") or not self.knowledge_layer[1:].isdigit():
            problems.append(f"{path}.knowledge_layer must be K followed by a non-negative integer")
        for label, value in (
            ("legal_information_boundary", self.legal_information_boundary),
            ("profile_policy_id", self.profile_policy_id),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        if self.dataset_family_id and not ID_RE.fullmatch(self.dataset_family_id):
            problems.append(f"{path}.dataset_family_id must be empty or namespaced")
        keys = [attribute.key for attribute in self.attributes]
        if len(keys) != len(set(keys)):
            problems.append(f"{path}.attributes keys must be unique")
        for index, attribute in enumerate(self.attributes):
            problems.extend(attribute.validate(f"{path}.attributes[{index}]"))
        categories = [match.category_id for match in self.category_matches]
        if len(categories) != len(set(categories)):
            problems.append(f"{path}.category_matches category ids must be unique")
        for index, match in enumerate(self.category_matches):
            problems.extend(match.validate(f"{path}.category_matches[{index}]"))
        spaces = [embedding.space_key for embedding in self.embeddings]
        if len(spaces) != len(set(spaces)):
            problems.append(f"{path}.embeddings spaces must be unique")
        for index, embedding in enumerate(self.embeddings):
            problems.extend(embedding.validate(f"{path}.embeddings[{index}]"))
        if any(not warning.strip() for warning in self.warnings):
            problems.append(f"{path}.warnings must not contain empty strings")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def with_attributes(
        self,
        *attributes: FingerprintAttribute,
        knowledge_layer: str | None = None,
        warnings: tuple[str, ...] = (),
    ) -> TaskFingerprint:
        merged = self.attribute_map
        merged.update({attribute.key: attribute for attribute in attributes})
        return replace(
            self,
            knowledge_layer=knowledge_layer or self.knowledge_layer,
            attributes=tuple(merged[key] for key in sorted(merged)),
            warnings=tuple(dict.fromkeys((*self.warnings, *warnings))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_intelligence_model_version": TASK_INTELLIGENCE_MODEL_VERSION,
            "task_contract_digest": self.task_contract_digest,
            "task_id": self.task_id,
            "dataset_family_id": self.dataset_family_id,
            "knowledge_layer": self.knowledge_layer,
            "legal_information_boundary": self.legal_information_boundary,
            "profile_policy_id": self.profile_policy_id,
            "attributes": [attribute.to_dict() for attribute in self.attributes],
            "category_matches": [match.to_dict() for match in self.category_matches],
            "embeddings": [embedding.to_dict() for embedding in self.embeddings],
            "warnings": list(self.warnings),
            "extensions": dict(self.extensions),
        }


def fingerprint_from_contract(
    contract: TaskContract,
    *,
    dataset_family_id: str = "",
    legal_information_boundary: str = "boundary.train-only",
    profile_policy_id: str = "profile.contract-only",
    category_registry: TaskCategoryRegistry = DEFAULT_TASK_CATEGORY_REGISTRY,
    extra_attributes: Sequence[FingerprintAttribute] = (),
) -> TaskFingerprint:
    """Build a cheap K0 profile without inspecting task-case values."""
    problems = (*contract.validate(), *category_registry.validate())
    if problems:
        raise ValueError("invalid task intelligence input: " + "; ".join(problems))
    categories = category_registry.classify(contract)
    extension_map = dict(contract.extensions)
    family = extension_map.get("task.family")
    if not isinstance(family, str) or not family:
        family = categories[0].category_id if categories else "task.unknown"
    domain = extension_map.get("semantic.domain_labels", ())
    if isinstance(domain, str):
        domain = (domain,)
    if not isinstance(domain, (list, tuple)):
        domain = ()
    attributes = [
        FingerprintAttribute("task.family", family, evidence_kind="evidence.declared"),
        FingerprintAttribute(
            "task.category_ids",
            tuple(match.category_id for match in categories),
            evidence_kind="evidence.inferred",
            confidence=max((match.score for match in categories), default=0.0),
        ),
        FingerprintAttribute("task.input_count", len(contract.inputs)),
        FingerprintAttribute("task.output_count", len(contract.outputs)),
        FingerprintAttribute(
            "task.output_type_ids", tuple(port.value_type.id for port in contract.outputs)
        ),
        FingerprintAttribute("task.metric.ids", tuple(item.metric for item in contract.objectives)),
        FingerprintAttribute(
            "task.metric.directions", tuple(item.direction for item in contract.objectives)
        ),
        FingerprintAttribute("task.constraint_count", len(contract.constraints)),
        FingerprintAttribute("task.allowed_effect_count", len(contract.allowed_effects)),
        FingerprintAttribute("task.permission_count", len(contract.granted_permissions)),
        FingerprintAttribute("task.tags", contract.tags, evidence_kind="evidence.declared"),
        FingerprintAttribute(
            "semantic.domain_labels",
            tuple(str(item) for item in domain),
            evidence_kind="evidence.declared",
        ),
        *extra_attributes,
    ]
    fingerprint = TaskFingerprint(
        task_contract_digest=contract.digest,
        task_id=contract.id,
        dataset_family_id=dataset_family_id,
        knowledge_layer="K0",
        legal_information_boundary=legal_information_boundary,
        profile_policy_id=profile_policy_id,
        attributes=tuple(sorted(attributes, key=lambda item: item.key)),
        category_matches=categories,
    )
    fingerprint_problems = fingerprint.validate()
    if fingerprint_problems:
        raise ValueError("invalid task fingerprint: " + "; ".join(fingerprint_problems))
    return fingerprint


def _sample_records(
    records: Sequence[Mapping[str, Any]], sample_limit: int | None, seed: int
) -> tuple[Mapping[str, Any], ...]:
    if sample_limit is None or len(records) <= sample_limit:
        return tuple(records)
    if sample_limit <= 0:
        raise ValueError("sample_limit must be positive or null")
    random = Random(seed)
    reservoir = list(records[:sample_limit])
    for index, record in enumerate(records[sample_limit:], start=sample_limit):
        replacement = random.randrange(index + 1)
        if replacement < sample_limit:
            reservoir[replacement] = record
    return tuple(reservoir)


def profile_tabular_records(
    base: TaskFingerprint,
    records: Sequence[Mapping[str, Any]],
    *,
    target_field: str | None = None,
    sample_limit: int | None = 10_000,
    random_seed: int = 0,
) -> TaskFingerprint:
    """Add deterministic K1-K4 attributes from a caller-authorized record sample.

    This dependency-free profiler deliberately returns aggregates only.  It is
    a useful baseline and extension seam, not a replacement for specialized
    statistical, privacy, media, graph, or distributed profilers.
    """
    if base.validate():
        raise ValueError("base fingerprint is invalid")
    if any(not isinstance(record, Mapping) for record in records):
        raise ValueError("records must be mappings")
    if any(not isinstance(key, str) for record in records for key in record):
        raise ValueError("record keys must be strings")
    sample = _sample_records(records, sample_limit, random_seed)
    columns = tuple(sorted({str(key) for record in sample for key in record}))
    n_rows = len(records)
    n_columns = len(columns)
    per_column_values = {column: [record.get(column) for record in sample] for column in columns}
    missing_rates: list[float] = []
    unique_ratios: list[float] = []
    type_counts: Counter[str] = Counter()
    numeric_rollups: dict[str, list[float]] = defaultdict(list)

    for _column, values in per_column_values.items():
        present = [value for value in values if not _is_missing(value)]
        missing_rates.append(1.0 - len(present) / max(1, len(values)))
        try:
            unique = {canonical_json(value) for value in present}
        except (TypeError, ValueError) as exc:
            raise ValueError("sampled record values must be JSON serialisable") from exc
        unique_ratios.append(len(unique) / max(1, len(present)))
        numeric = [number for value in present if (number := _numeric(value)) is not None]
        if not present:
            kind = "missing"
        elif len(numeric) / len(present) >= 0.9:
            kind = "numeric"
            if numeric:
                mean = fmean(numeric)
                variance = fmean((value - mean) ** 2 for value in numeric)
                scale = sqrt(variance)
                skew = fmean(((value - mean) / scale) ** 3 for value in numeric) if scale else 0.0
                numeric_rollups["mean"].append(mean)
                numeric_rollups["std"].append(scale)
                numeric_rollups["skewness"].append(skew)
        elif present and all(isinstance(value, bool) for value in present):
            kind = "boolean"
        elif present and all(isinstance(value, str) for value in present):
            parsed_dates = 0
            for value in present[:100]:
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                    parsed_dates += 1
                except ValueError:
                    pass
            if parsed_dates / min(100, len(present)) >= 0.8:
                kind = "datetime"
            else:
                average_length = fmean(len(value) for value in present)
                kind = (
                    "text"
                    if average_length >= 40 or len(unique) / len(present) >= 0.5
                    else "categorical"
                )
        else:
            kind = "mixed"
        type_counts[kind] += 1

    missing = _rollup(missing_rates)
    cardinality = _rollup(unique_ratios)
    attributes = [
        FingerprintAttribute("data.n_rows", n_rows, sample_size=n_rows),
        FingerprintAttribute("data.n_columns", n_columns, sample_size=len(sample)),
        FingerprintAttribute("data.rows_per_feature", n_rows / max(1, n_columns)),
        FingerprintAttribute("data.profile_sample_size", len(sample), random_seed=random_seed),
        FingerprintAttribute(
            "data.profile_sample_fraction", len(sample) / max(1, n_rows), random_seed=random_seed
        ),
        FingerprintAttribute("types.counts", dict(sorted(type_counts.items()))),
        FingerprintAttribute(
            "types.fractions",
            {key: value / max(1, n_columns) for key, value in sorted(type_counts.items())},
        ),
        FingerprintAttribute("missing.fraction.mean", missing["mean"]),
        FingerprintAttribute("missing.fraction.q90", missing["q90"]),
        FingerprintAttribute("missing.fraction.max", missing["max"]),
        FingerprintAttribute("cardinality.unique_ratio.mean", cardinality["mean"]),
        FingerprintAttribute("cardinality.unique_ratio.q90", cardinality["q90"]),
        FingerprintAttribute("cardinality.unique_ratio.max", cardinality["max"]),
    ]
    for statistic, values in numeric_rollups.items():
        rollup = _rollup(values)
        for aggregate in ("mean", "std", "q10", "q50", "q90", "max"):
            attributes.append(
                FingerprintAttribute(
                    f"feature_stats.numeric_{statistic}.{aggregate}",
                    rollup[aggregate],
                    compute_tier="tier.b",
                    sample_size=len(sample),
                    random_seed=random_seed,
                )
            )

    row_digests = [
        sha256_digest({column: record.get(column) for column in columns}) for record in sample
    ]
    attributes.append(
        FingerprintAttribute(
            "duplicates.exact_row_fraction",
            1.0 - len(set(row_digests)) / max(1, len(row_digests)),
            sample_size=len(sample),
            random_seed=random_seed,
        )
    )

    target_profiled = False
    profile_warnings: list[str] = []
    if target_field and target_field in per_column_values:
        target_values = [
            value for value in per_column_values[target_field] if not _is_missing(value)
        ]
        numeric_target = [
            number for value in target_values if (number := _numeric(value)) is not None
        ]
        category_ids = {match.category_id for match in base.category_matches}
        regression_declared = "dag.learn.regression" in category_ids
        classification_declared = "dag.learn.classification" in category_ids
        looks_regression = (
            bool(target_values)
            and len(numeric_target) == len(target_values)
            and (
                regression_declared
                or (
                    not classification_declared
                    and len(set(numeric_target)) > max(20, sqrt(len(numeric_target)))
                )
            )
        )
        if looks_regression and numeric_target:
            target_profiled = True
            target_mean = fmean(numeric_target)
            variance = fmean((value - target_mean) ** 2 for value in numeric_target)
            target_std = sqrt(variance)
            ordered = sorted(numeric_target)
            target_median = median(ordered)
            mad = median([abs(value - target_median) for value in ordered])
            skew = (
                fmean(((value - target_mean) / target_std) ** 3 for value in ordered)
                if target_std
                else 0.0
            )
            attributes.extend(
                (
                    FingerprintAttribute("target.kind", "target.regression", compute_tier="tier.b"),
                    FingerprintAttribute("target.mean", target_mean, compute_tier="tier.b"),
                    FingerprintAttribute("target.median", target_median, compute_tier="tier.b"),
                    FingerprintAttribute("target.std", target_std, compute_tier="tier.b"),
                    FingerprintAttribute("target.mad", mad, compute_tier="tier.b"),
                    FingerprintAttribute("target.skewness", skew, compute_tier="tier.b"),
                    FingerprintAttribute(
                        "target.zero_fraction",
                        sum(value == 0 for value in ordered) / len(ordered),
                        compute_tier="tier.b",
                    ),
                    FingerprintAttribute(
                        "target.unique_ratio",
                        len(set(ordered)) / len(ordered),
                        compute_tier="tier.b",
                    ),
                )
            )
            correlations: list[float] = []
            for column in columns:
                if column == target_field:
                    continue
                pairs = [
                    (feature, target)
                    for record in sample
                    if (feature := _numeric(record.get(column))) is not None
                    and (target := _numeric(record.get(target_field))) is not None
                ]
                if len(pairs) >= 3:
                    left, right = zip(*pairs, strict=True)
                    correlations.append(abs(_pearson(left, right)))
            correlation_rollup = _rollup(correlations)
            attributes.extend(
                (
                    FingerprintAttribute(
                        "signal.linear_abs.mean", correlation_rollup["mean"], compute_tier="tier.b"
                    ),
                    FingerprintAttribute(
                        "signal.linear_abs.q90", correlation_rollup["q90"], compute_tier="tier.b"
                    ),
                    FingerprintAttribute(
                        "signal.linear_abs.max", correlation_rollup["max"], compute_tier="tier.b"
                    ),
                )
            )
        elif target_values:
            target_profiled = True
            counts = Counter(canonical_json(value) for value in target_values)
            total = sum(counts.values())
            probabilities = [count / total for count in counts.values()]
            entropy = -sum(probability * log(probability) for probability in probabilities)
            attributes.extend(
                (
                    FingerprintAttribute(
                        "target.kind", "target.classification", compute_tier="tier.b"
                    ),
                    FingerprintAttribute("target.n_classes", len(counts), compute_tier="tier.b"),
                    FingerprintAttribute("target.class_entropy", entropy, compute_tier="tier.b"),
                    FingerprintAttribute(
                        "target.minority_support", min(counts.values()), compute_tier="tier.b"
                    ),
                    FingerprintAttribute(
                        "target.imbalance_ratio",
                        max(counts.values()) / min(counts.values()),
                        compute_tier="tier.b",
                    ),
                )
            )

    elif target_field:
        profile_warnings.append(
            "Requested target field was not present in the authorized sample; "
            "target attributes remain unavailable."
        )

    profiled = base.with_attributes(
        *attributes,
        knowledge_layer="K4" if target_profiled else "K2",
        warnings=(
            "Tabular profile contains aggregate mechanism evidence from a caller-authorized sample; specialized profilers may extend it.",
            *profile_warnings,
        ),
    )
    problems = profiled.validate()
    if problems:
        raise ValueError("invalid profiled fingerprint: " + "; ".join(problems))
    return profiled


@dataclass(frozen=True)
class HistoricalOutcome:
    metric: str
    direction: str
    raw_value: float
    oriented_value: float
    normalized_lift: float | None = None
    uncertainty: float = 0.0
    evidence_count: int = 1
    objective_weight: float = 1.0

    def validate(self, path: str = "outcome") -> list[str]:
        problems: list[str] = []
        if not self.metric.strip():
            problems.append(f"{path}.metric must not be empty")
        if self.direction not in ("maximize", "minimize"):
            problems.append(f"{path}.direction must be maximize or minimize")
        for label, value in (
            ("raw_value", self.raw_value),
            ("oriented_value", self.oriented_value),
        ):
            if not isfinite(value):
                problems.append(f"{path}.{label} must be finite")
        if self.normalized_lift is not None and not isfinite(self.normalized_lift):
            problems.append(f"{path}.normalized_lift must be finite or null")
        if not isfinite(self.uncertainty) or self.uncertainty < 0:
            problems.append(f"{path}.uncertainty must be finite and non-negative")
        if self.evidence_count <= 0:
            problems.append(f"{path}.evidence_count must be positive")
        if not isfinite(self.objective_weight) or self.objective_weight < 0:
            problems.append(f"{path}.objective_weight must be finite and non-negative")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "direction": self.direction,
            "raw_value": self.raw_value,
            "oriented_value": self.oriented_value,
            "normalized_lift": self.normalized_lift,
            "uncertainty": self.uncertainty,
            "evidence_count": self.evidence_count,
            "objective_weight": self.objective_weight,
        }


@dataclass(frozen=True)
class HistoricalEpisode:
    """One immutable route observation; success is not required."""

    id: str
    task_contract_digest: str
    fingerprint_digest: str
    route_id: str
    selection: tuple[tuple[str, str], ...]
    outcomes: tuple[HistoricalOutcome, ...]
    accepted: bool
    status: str
    source_lane: str
    optimizer_id: str
    effort_policy_id: str
    dataset_family_id: str = ""
    plan_digest: str = ""
    program_digest: str = ""
    registry_digest: str = ""
    admitted_space_digest: str = ""
    verifier_digest: str = ""
    environment_digest: str = ""
    budget: tuple[tuple[str, float], ...] = ()
    costs: tuple[tuple[str, float], ...] = ()
    failures: tuple[str, ...] = ()
    evidence_scope: str = "evidence.mechanism-fixture"
    created_at: str = ""
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def normalized_utility(self) -> float:
        normalized = [
            (item.normalized_lift, item.objective_weight)
            for item in self.outcomes
            if item.normalized_lift is not None
        ]
        if normalized:
            weight = sum(item[1] for item in normalized)
            return (
                sum(value * objective_weight for value, objective_weight in normalized) / weight
                if weight
                else fmean(value for value, _ in normalized)
            )
        # Raw metrics may have incompatible units and scales.  Until a caller
        # supplies cohort-normalized lifts, acceptance is the only comparable
        # cross-task utility signal.
        return 1.0 if self.accepted else -1.0

    def validate(self, path: str = "episode") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("route_id", self.route_id),
            ("status", self.status),
            ("source_lane", self.source_lane),
            ("optimizer_id", self.optimizer_id),
            ("effort_policy_id", self.effort_policy_id),
            ("evidence_scope", self.evidence_scope),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        for label, digest in (
            ("task_contract_digest", self.task_contract_digest),
            ("fingerprint_digest", self.fingerprint_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be a sha256 digest")
        for label, digest in (
            ("plan_digest", self.plan_digest),
            ("program_digest", self.program_digest),
            ("registry_digest", self.registry_digest),
            ("admitted_space_digest", self.admitted_space_digest),
            ("verifier_digest", self.verifier_digest),
            ("environment_digest", self.environment_digest),
        ):
            if digest and not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be empty or a sha256 digest")
        if self.dataset_family_id and not ID_RE.fullmatch(self.dataset_family_id):
            problems.append(f"{path}.dataset_family_id must be empty or namespaced")
        slots = [slot for slot, _ in self.selection]
        if len(slots) != len(set(slots)) or not self.selection:
            problems.append(f"{path}.selection must be nonempty with unique slots")
        if any(not ID_RE.fullmatch(value) for pair in self.selection for value in pair):
            problems.append(f"{path}.selection must contain namespaced identifiers")
        if not self.outcomes and not self.failures:
            problems.append(f"{path} must preserve at least one outcome or failure")
        for index, outcome in enumerate(self.outcomes):
            problems.extend(outcome.validate(f"{path}.outcomes[{index}]"))
        for label, pairs in (("budget", self.budget), ("costs", self.costs)):
            keys = [key for key, _ in pairs]
            if len(keys) != len(set(keys)):
                problems.append(f"{path}.{label} keys must be unique")
            if any(not ID_RE.fullmatch(key) for key in keys):
                problems.append(f"{path}.{label} keys must be namespaced")
            if any(not isfinite(value) or value < 0 for _, value in pairs):
                problems.append(f"{path}.{label} values must be finite and non-negative")
        if len(self.failures) != len(set(self.failures)) or any(
            not ID_RE.fullmatch(failure) for failure in self.failures
        ):
            problems.append(f"{path}.failures must contain unique namespaced identifiers")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_intelligence_model_version": TASK_INTELLIGENCE_MODEL_VERSION,
            "id": self.id,
            "task_contract_digest": self.task_contract_digest,
            "fingerprint_digest": self.fingerprint_digest,
            "dataset_family_id": self.dataset_family_id,
            "route_id": self.route_id,
            "plan_digest": self.plan_digest,
            "program_digest": self.program_digest,
            "registry_digest": self.registry_digest,
            "admitted_space_digest": self.admitted_space_digest,
            "verifier_digest": self.verifier_digest,
            "selection": dict(self.selection),
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "accepted": self.accepted,
            "status": self.status,
            "source_lane": self.source_lane,
            "optimizer_id": self.optimizer_id,
            "effort_policy_id": self.effort_policy_id,
            "environment_digest": self.environment_digest,
            "budget": dict(self.budget),
            "costs": dict(self.costs),
            "failures": list(self.failures),
            "evidence_scope": self.evidence_scope,
            "created_at": self.created_at,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class HistoricalMemory:
    """A content-addressed task/fingerprint/episode evidence snapshot."""

    id: str
    version: str
    fingerprints: tuple[TaskFingerprint, ...] = ()
    episodes: tuple[HistoricalEpisode, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or "." not in self.id:
            problems.append("historical memory id must be namespaced")
        if not self.version.strip():
            problems.append("historical memory version must not be empty")
        fingerprint_digests = [fingerprint.digest for fingerprint in self.fingerprints]
        if len(fingerprint_digests) != len(set(fingerprint_digests)):
            problems.append("historical memory fingerprint digests must be unique")
        for index, fingerprint in enumerate(self.fingerprints):
            problems.extend(fingerprint.validate(f"fingerprints[{index}]"))
        episode_ids = [episode.id for episode in self.episodes]
        if len(episode_ids) != len(set(episode_ids)):
            problems.append("historical memory episode ids must be unique")
        known = set(fingerprint_digests)
        for index, episode in enumerate(self.episodes):
            problems.extend(episode.validate(f"episodes[{index}]"))
            if episode.fingerprint_digest not in known:
                problems.append(f"episodes[{index}] references an unknown fingerprint")
        problems.extend(_extension_problems(self.extensions, "memory.extensions"))
        return problems

    def append_fingerprint(self, fingerprint: TaskFingerprint) -> HistoricalMemory:
        if fingerprint.digest in {item.digest for item in self.fingerprints}:
            return self
        return replace(self, fingerprints=(*self.fingerprints, fingerprint))

    def append_episode(self, episode: HistoricalEpisode) -> HistoricalMemory:
        return replace(self, episodes=(*self.episodes, episode))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_intelligence_model_version": TASK_INTELLIGENCE_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "fingerprints": [fingerprint.to_dict() for fingerprint in self.fingerprints],
            "fingerprint_digests": [fingerprint.digest for fingerprint in self.fingerprints],
            "episodes": [episode.to_dict() for episode in self.episodes],
            "extensions": dict(self.extensions),
        }


def historical_episode_from_receipts(
    fingerprint: TaskFingerprint,
    route_id: str,
    receipts: Sequence[RunReceipt],
    objectives: Sequence[Objective],
    *,
    source_lane: str,
    optimizer_id: str,
    effort_policy_id: str,
    minimum_acceptance_rate: float = 1.0,
    normalized_lifts: Mapping[str, float] | None = None,
    budget: Mapping[str, float] | None = None,
    costs: Mapping[str, float] | None = None,
    evidence_scope: str = "evidence.mechanism-fixture",
    dataset_family_id: str | None = None,
    registry_digest: str = "",
) -> HistoricalEpisode:
    """Seal comparable run receipts into one failure-preserving history episode.

    Normalized lifts are intentionally caller supplied because normalization
    requires an explicit, task-appropriate baseline cohort.  Raw and oriented
    objective means are always retained.
    """
    receipts = tuple(receipts)
    objectives = tuple(objectives)
    normalized_lifts = normalized_lifts or {}
    budget = budget or {}
    costs = costs or {}
    problems = list(fingerprint.validate())
    problems.extend(problem for receipt in receipts for problem in receipt.validate())
    problems.extend(problem for objective in objectives for problem in objective.validate())
    if not receipts:
        problems.append("episode ingestion requires at least one receipt")
    if not objectives:
        problems.append("episode ingestion requires at least one objective")
    if len({objective.metric for objective in objectives}) != len(objectives):
        problems.append("episode ingestion objective metrics must be unique")
    if not 0.0 <= minimum_acceptance_rate <= 1.0:
        problems.append("minimum_acceptance_rate must be between zero and one")
    if problems:
        raise ValueError("invalid episode ingestion input: " + "; ".join(problems))

    plan_digests = {receipt.plan_digest for receipt in receipts}
    program_digests = {receipt.program_digest for receipt in receipts}
    admitted_space_digests = {
        receipt.admitted_space_digest for receipt in receipts if receipt.admitted_space_digest
    }
    verifier_digests = {receipt.verifier_digest for receipt in receipts if receipt.verifier_digest}
    selections = {receipt.assignments for receipt in receipts}
    if (
        len(plan_digests) != 1
        or len(program_digests) != 1
        or len(admitted_space_digests) > 1
        or len(verifier_digests) > 1
        or len(selections) != 1
    ):
        raise ValueError(
            "episode ingestion receipts must describe one exact plan, program, "
            "admitted space, verifier, and selection"
        )
    unknown_lifts = sorted(set(normalized_lifts) - {item.metric for item in objectives})
    if unknown_lifts:
        raise ValueError(
            "normalized_lifts contains undeclared objectives: " + ", ".join(unknown_lifts)
        )

    outcomes: list[HistoricalOutcome] = []
    for objective in objectives:
        values = [
            float(receipt.metrics[objective.metric])
            for receipt in receipts
            if objective.metric in receipt.metrics
        ]
        if not values:
            continue
        mean = fmean(values)
        variance = fmean((value - mean) ** 2 for value in values)
        outcomes.append(
            HistoricalOutcome(
                objective.metric,
                objective.direction,
                mean,
                mean if objective.direction == "maximize" else -mean,
                normalized_lifts.get(objective.metric),
                sqrt(variance / len(values)),
                len(values),
                objective.weight,
            )
        )

    acceptance_rate = sum(receipt.accepted is True for receipt in receipts) / len(receipts)
    accepted = bool(outcomes) and acceptance_rate >= minimum_acceptance_rate
    failures = tuple(
        sorted({receipt.failure_class for receipt in receipts if receipt.failure_class})
    )
    if not outcomes and not failures:
        failures = ("failure.missing-objective-evidence",)
    status = (
        "status.accepted"
        if accepted
        else (
            "status.failed"
            if all(receipt.outcome == "failed" for receipt in receipts)
            else "status.rejected"
        )
    )
    environment_digests = tuple(
        sorted({receipt.environment_digest for receipt in receipts if receipt.environment_digest})
    )
    environment_digest = (
        environment_digests[0]
        if len(environment_digests) == 1
        else sha256_digest({"environment_digests": environment_digests})
        if environment_digests
        else ""
    )
    receipt_ids = tuple(sorted(receipt.id for receipt in receipts))
    episode_suffix = sha256_digest(
        {
            "fingerprint": fingerprint.digest,
            "route_id": route_id,
            "plan_digest": next(iter(plan_digests)),
            "receipt_ids": receipt_ids,
        }
    ).removeprefix("sha256:")[:24]
    episode = HistoricalEpisode(
        id=f"episode.{episode_suffix}",
        task_contract_digest=fingerprint.task_contract_digest,
        fingerprint_digest=fingerprint.digest,
        dataset_family_id=dataset_family_id or fingerprint.dataset_family_id,
        route_id=route_id,
        plan_digest=next(iter(plan_digests)),
        program_digest=next(iter(program_digests)),
        registry_digest=registry_digest,
        admitted_space_digest=next(iter(admitted_space_digests), ""),
        verifier_digest=next(iter(verifier_digests), ""),
        selection=next(iter(selections)),
        outcomes=tuple(outcomes),
        accepted=accepted,
        status=status,
        source_lane=source_lane,
        optimizer_id=optimizer_id,
        effort_policy_id=effort_policy_id,
        environment_digest=environment_digest,
        budget=tuple(sorted((key, float(value)) for key, value in budget.items())),
        costs=tuple(sorted((key, float(value)) for key, value in costs.items())),
        failures=failures,
        evidence_scope=evidence_scope,
        created_at=max((receipt.completed_at for receipt in receipts), default=""),
        extensions=(("evidence.receipt_ids", receipt_ids),),
    )
    episode_problems = episode.validate()
    if episode_problems:
        raise ValueError("invalid ingested historical episode: " + "; ".join(episode_problems))
    return episode


@dataclass(frozen=True)
class ChannelScore:
    channel_id: str
    similarity: float
    coverage: float
    confidence: float
    explanations: tuple[str, ...] = ()

    @property
    def effective(self) -> float:
        return self.similarity * self.coverage * self.confidence

    def validate(self, path: str = "channel_score") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.channel_id):
            problems.append(f"{path}.channel_id must be namespaced")
        for label, value in (
            ("similarity", self.similarity),
            ("coverage", self.coverage),
            ("confidence", self.confidence),
        ):
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                problems.append(f"{path}.{label} must be finite and between zero and one")
        if any(not explanation.strip() for explanation in self.explanations):
            problems.append(f"{path}.explanations must not contain empty strings")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "similarity": self.similarity,
            "coverage": self.coverage,
            "confidence": self.confidence,
            "effective": self.effective,
            "explanations": list(self.explanations),
        }


class SimilarityChannel(Protocol):
    id: str

    def score(self, query: TaskFingerprint, candidate: TaskFingerprint) -> ChannelScore: ...


def _value_similarity(left: Any, right: Any) -> float | None:
    if isinstance(left, bool) or isinstance(right, bool):
        return 1.0 if left == right else 0.0
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        scale = max(abs(float(left)), abs(float(right)), 1.0)
        return max(0.0, 1.0 - abs(float(left) - float(right)) / scale)
    if isinstance(left, str) and isinstance(right, str):
        return 1.0 if left.casefold() == right.casefold() else 0.0
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        shared = set(left) & set(right)
        values = [_value_similarity(left[key], right[key]) for key in shared]
        usable = [value for value in values if value is not None]
        return fmean(usable) if usable else None
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        left_set = {canonical_json(value) for value in left}
        right_set = {canonical_json(value) for value in right}
        union = left_set | right_set
        return len(left_set & right_set) / len(union) if union else 1.0
    return 1.0 if left == right else 0.0


@dataclass(frozen=True)
class ExactSimilarityChannel:
    id: str = "channel.exact"

    def score(self, query: TaskFingerprint, candidate: TaskFingerprint) -> ChannelScore:
        if query.digest == candidate.digest:
            return ChannelScore(self.id, 1.0, 1.0, 1.0, ("same fingerprint digest",))
        if query.dataset_family_id and query.dataset_family_id == candidate.dataset_family_id:
            return ChannelScore(self.id, 0.95, 1.0, 0.95, ("same dataset family",))
        coverage = 1.0 if query.dataset_family_id and candidate.dataset_family_id else 0.0
        return ChannelScore(self.id, 0.0, coverage, 1.0, ())


@dataclass(frozen=True)
class CategorySimilarityChannel:
    id: str = "channel.taxonomic"

    def score(self, query: TaskFingerprint, candidate: TaskFingerprint) -> ChannelScore:
        left = {match.category_id for match in query.category_matches}
        right = {match.category_id for match in candidate.category_matches}
        if not left or not right:
            return ChannelScore(self.id, 0.0, 0.0, 0.0, ())
        intersection = left & right
        similarity = len(intersection) / len(left | right)
        confidence = min(
            max(match.score for match in query.category_matches),
            max(match.score for match in candidate.category_matches),
        )
        return ChannelScore(
            self.id,
            similarity,
            1.0,
            confidence,
            tuple(f"shared:{category_id}" for category_id in sorted(intersection)),
        )


@dataclass(frozen=True)
class AttributeSimilarityChannel:
    id: str
    prefixes: tuple[str, ...]

    def score(self, query: TaskFingerprint, candidate: TaskFingerprint) -> ChannelScore:
        left = {
            key: value
            for key, value in query.attribute_map.items()
            if any(key.startswith(prefix) for prefix in self.prefixes)
            and value.availability == "availability.available"
        }
        right = {
            key: value
            for key, value in candidate.attribute_map.items()
            if any(key.startswith(prefix) for prefix in self.prefixes)
            and value.availability == "availability.available"
        }
        if not left:
            return ChannelScore(self.id, 0.0, 0.0, 0.0, ())
        similarities: list[tuple[str, float, float]] = []
        for key in sorted(set(left) & set(right)):
            similarity = _value_similarity(left[key].value, right[key].value)
            if similarity is None:
                continue
            confidence = min(left[key].confidence, right[key].confidence)
            uncertainty = 1.0 + left[key].uncertainty + right[key].uncertainty
            similarities.append((key, similarity, confidence / uncertainty))
        if not similarities:
            return ChannelScore(self.id, 0.0, 0.0, 0.0, ())
        weight = sum(item[2] for item in similarities)
        similarity = sum(item[1] * item[2] for item in similarities) / max(weight, 1e-12)
        coverage = len(similarities) / len(left)
        confidence = min(1.0, weight / len(similarities))
        strongest = sorted(similarities, key=lambda item: (-item[1] * item[2], item[0]))[:5]
        return ChannelScore(
            self.id,
            similarity,
            coverage,
            confidence,
            tuple(f"{key}={value:.3f}" for key, value, _ in strongest),
        )


@dataclass(frozen=True)
class EmbeddingSimilarityChannel:
    id: str = "channel.embedding"

    def score(self, query: TaskFingerprint, candidate: TaskFingerprint) -> ChannelScore:
        left = {embedding.space_key: embedding for embedding in query.embeddings}
        right = {embedding.space_key: embedding for embedding in candidate.embeddings}
        shared = sorted(set(left) & set(right))
        if not shared:
            return ChannelScore(self.id, 0.0, 0.0, 0.0, ())
        scores: list[float] = []
        confidences: list[float] = []
        explanations: list[str] = []
        for key in shared:
            first = left[key]
            second = right[key]
            if len(first.vector) != len(second.vector):
                continue
            numerator = sum(a * b for a, b in zip(first.vector, second.vector, strict=True))
            denominator = sqrt(sum(a * a for a in first.vector) * sum(b * b for b in second.vector))
            cosine = numerator / denominator if denominator else 0.0
            scores.append(max(0.0, min(1.0, (cosine + 1.0) / 2.0)))
            confidences.append(min(first.confidence, second.confidence))
            explanations.append(f"shared-space:{key[0]}")
        if not scores:
            return ChannelScore(self.id, 0.0, 0.0, 0.0, ())
        return ChannelScore(
            self.id,
            fmean(scores),
            len(scores) / max(1, len(left)),
            fmean(confidences),
            tuple(explanations),
        )


DEFAULT_SIMILARITY_CHANNELS: tuple[SimilarityChannel, ...] = (
    ExactSimilarityChannel(),
    CategorySimilarityChannel(),
    AttributeSimilarityChannel(
        "channel.structural",
        (
            "data.",
            "types.",
            "target.",
            "missing.",
            "cardinality.",
            "duplicates.",
            "dependence.",
            "time.",
            "geo.",
            "relational.",
            "quality.",
        ),
    ),
    AttributeSimilarityChannel(
        "channel.statistical",
        (
            "feature_stats.",
            "signal.",
            "interaction.",
            "geometry.",
            "outliers.",
            "noise.",
            "drift.",
            "landmarker.",
        ),
    ),
    AttributeSimilarityChannel("channel.semantic", ("semantic.", "task.")),
    EmbeddingSimilarityChannel(),
)


@dataclass(frozen=True)
class RetrievalPolicy:
    id: str = "retrieval.history-late-fusion"
    top_k: int = 12
    channel_weights: tuple[tuple[str, float], ...] = (
        ("channel.exact", 1.5),
        ("channel.taxonomic", 1.0),
        ("channel.structural", 1.25),
        ("channel.statistical", 1.0),
        ("channel.semantic", 0.75),
        ("channel.embedding", 1.0),
    )
    minimum_channel_coverage: float = 0.05
    empirical_bayes_prior_strength: float = 3.0
    deduplicate_dataset_families: bool = True
    preserve_conflicts: bool = True

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("retrieval policy id must be namespaced")
        if self.top_k <= 0:
            problems.append("retrieval top_k must be positive")
        ids = [channel_id for channel_id, _ in self.channel_weights]
        if len(ids) != len(set(ids)) or any(not ID_RE.fullmatch(item) for item in ids):
            problems.append("retrieval channel ids must be unique and namespaced")
        if any(not isfinite(weight) or weight < 0 for _, weight in self.channel_weights):
            problems.append("retrieval channel weights must be finite and non-negative")
        if not 0.0 <= self.minimum_channel_coverage <= 1.0:
            problems.append("minimum_channel_coverage must be between zero and one")
        if (
            not isfinite(self.empirical_bayes_prior_strength)
            or self.empirical_bayes_prior_strength < 0
        ):
            problems.append("empirical_bayes_prior_strength must be finite and non-negative")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "top_k": self.top_k,
            "channel_weights": dict(self.channel_weights),
            "minimum_channel_coverage": self.minimum_channel_coverage,
            "empirical_bayes_prior_strength": self.empirical_bayes_prior_strength,
            "deduplicate_dataset_families": self.deduplicate_dataset_families,
            "preserve_conflicts": self.preserve_conflicts,
        }


@dataclass(frozen=True)
class HistoricalRecommendation:
    route_id: str
    selection: tuple[tuple[str, str], ...]
    episode_ids: tuple[str, ...]
    dataset_family_ids: tuple[str, ...]
    channel_scores: tuple[ChannelScore, ...]
    fused_similarity: float
    expected_normalized_lift: float
    uncertainty: float
    negative_transfer_risk: float
    accepted_rate: float
    ranking_score: float
    recommended_use: str
    conflicting_episode_ids: tuple[str, ...] = ()

    def validate(self, path: str = "recommendation") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.route_id):
            problems.append(f"{path}.route_id must be namespaced")
        slots = [slot for slot, _ in self.selection]
        if not self.selection or len(slots) != len(set(slots)):
            problems.append(f"{path}.selection must be nonempty with unique slots")
        if any(not ID_RE.fullmatch(value) for pair in self.selection for value in pair):
            problems.append(f"{path}.selection must contain namespaced identifiers")
        for label, values in (
            ("episode_ids", self.episode_ids),
            ("dataset_family_ids", self.dataset_family_ids),
            ("conflicting_episode_ids", self.conflicting_episode_ids),
        ):
            if len(values) != len(set(values)) or any(
                not ID_RE.fullmatch(value) for value in values
            ):
                problems.append(f"{path}.{label} must contain unique namespaced ids")
        if set(self.conflicting_episode_ids) - set(self.episode_ids):
            problems.append(f"{path}.conflicting_episode_ids must be episode_ids")
        channel_ids = [score.channel_id for score in self.channel_scores]
        if len(channel_ids) != len(set(channel_ids)):
            problems.append(f"{path}.channel_scores must have unique channel ids")
        for index, score in enumerate(self.channel_scores):
            problems.extend(score.validate(f"{path}.channel_scores[{index}]"))
        for label, value in (
            ("fused_similarity", self.fused_similarity),
            ("negative_transfer_risk", self.negative_transfer_risk),
            ("accepted_rate", self.accepted_rate),
        ):
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                problems.append(f"{path}.{label} must be finite and in [0,1]")
        for label, value in (
            ("expected_normalized_lift", self.expected_normalized_lift),
            ("ranking_score", self.ranking_score),
        ):
            if not isfinite(value):
                problems.append(f"{path}.{label} must be finite")
        if not isfinite(self.uncertainty) or self.uncertainty < 0:
            problems.append(f"{path}.uncertainty must be finite and non-negative")
        if not ID_RE.fullmatch(self.recommended_use):
            problems.append(f"{path}.recommended_use must be namespaced")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "selection": dict(self.selection),
            "episode_ids": list(self.episode_ids),
            "dataset_family_ids": list(self.dataset_family_ids),
            "channel_scores": [score.to_dict() for score in self.channel_scores],
            "fused_similarity": self.fused_similarity,
            "expected_normalized_lift": self.expected_normalized_lift,
            "uncertainty": self.uncertainty,
            "negative_transfer_risk": self.negative_transfer_risk,
            "accepted_rate": self.accepted_rate,
            "ranking_score": self.ranking_score,
            "recommended_use": self.recommended_use,
            "conflicting_episode_ids": list(self.conflicting_episode_ids),
        }


class HistoricalRetriever:
    """Auditable late fusion over replaceable similarity channels."""

    def __init__(self, channels: Sequence[SimilarityChannel] = DEFAULT_SIMILARITY_CHANNELS) -> None:
        self.channels = tuple(channels)
        ids = [channel.id for channel in self.channels]
        if not self.channels or len(ids) != len(set(ids)):
            raise ValueError("historical retrieval channels must be nonempty and unique")

    def retrieve(
        self,
        query: TaskFingerprint,
        memory: HistoricalMemory,
        policy: RetrievalPolicy | None = None,
    ) -> tuple[HistoricalRecommendation, ...]:
        policy = policy or RetrievalPolicy()
        problems = (*query.validate(), *memory.validate(), *policy.validate())
        if problems:
            raise ValueError("invalid historical retrieval input: " + "; ".join(problems))
        weight_map = dict(policy.channel_weights)
        fingerprint_map = {fingerprint.digest: fingerprint for fingerprint in memory.fingerprints}
        if policy.deduplicate_dataset_families:
            global_by_family: dict[str, list[float]] = defaultdict(list)
            for episode in memory.episodes:
                global_by_family[episode.dataset_family_id or episode.id].append(
                    episode.normalized_utility
                )
            global_utilities = [fmean(utilities) for utilities in global_by_family.values()]
        else:
            global_utilities = [episode.normalized_utility for episode in memory.episodes]
        global_prior = fmean(global_utilities) if global_utilities else 0.0
        scored: dict[str, list[tuple[HistoricalEpisode, float, tuple[ChannelScore, ...]]]] = (
            defaultdict(list)
        )

        for episode in memory.episodes:
            candidate = fingerprint_map[episode.fingerprint_digest]
            scores = tuple(channel.score(query, candidate) for channel in self.channels)
            usable = [
                score
                for score in scores
                if score.coverage >= policy.minimum_channel_coverage
                and weight_map.get(score.channel_id, 0.0) > 0
            ]
            denominator = sum(weight_map[score.channel_id] for score in usable)
            fused = (
                sum(weight_map[score.channel_id] * score.effective for score in usable)
                / denominator
                if denominator
                else 0.0
            )
            if fused > 0:
                scored[episode.route_id].append((episode, fused, scores))

        recommendations: list[HistoricalRecommendation] = []
        for route_id, observations in scored.items():
            if policy.deduplicate_dataset_families:
                by_family: dict[
                    str,
                    list[tuple[HistoricalEpisode, float, tuple[ChannelScore, ...]]],
                ] = defaultdict(list)
                for item in observations:
                    family = item[0].dataset_family_id or item[0].id
                    by_family[family].append(item)
                observation_groups = list(by_family.values())
            else:
                observation_groups = [[item] for item in observations]
            all_observations = [item for group in observation_groups for item in group]
            family_summaries = [
                (
                    group,
                    fmean(item[1] for item in group),
                    fmean(item[0].normalized_utility for item in group),
                    fmean(float(item[0].accepted) for item in group),
                    fmean(float(bool(item[0].failures) or not item[0].accepted) for item in group),
                )
                for group in observation_groups
            ]
            weights = [max(1e-9, item[1]) for item in family_summaries]
            weight_sum = sum(weights)
            mean_similarity = (
                sum(
                    weight * item[1] for weight, item in zip(weights, family_summaries, strict=True)
                )
                / weight_sum
            )
            mean_utility = (
                sum(
                    weight * item[2] for weight, item in zip(weights, family_summaries, strict=True)
                )
                / weight_sum
            )
            evidence_count = len(family_summaries)
            prior = policy.empirical_bayes_prior_strength
            posterior = (evidence_count * mean_utility + prior * global_prior) / (
                evidence_count + prior
            )
            accepted_rate = (
                sum(
                    weight * item[3] for weight, item in zip(weights, family_summaries, strict=True)
                )
                / weight_sum
            )
            failure_rate = (
                sum(
                    weight * item[4] for weight, item in zip(weights, family_summaries, strict=True)
                )
                / weight_sum
            )
            uncertainty = min(1.0, 1.0 / sqrt(evidence_count) + (1.0 - mean_similarity) / 2.0)
            negative_risk = min(
                1.0,
                0.65 * failure_rate + 0.20 * max(0.0, -posterior) + 0.15 * (1.0 - mean_similarity),
            )
            utility_factor = 1.0 / (1.0 + exp(-max(-30.0, min(30.0, posterior))))
            ranking = mean_similarity * utility_factor * (1.0 - negative_risk)
            representative = max(
                all_observations,
                key=lambda item: (item[1], item[0].accepted, item[0].id),
            )
            aggregated_scores: list[ChannelScore] = []
            for channel in self.channels:
                family_channel_scores = [
                    [
                        next(score for score in item[2] if score.channel_id == channel.id)
                        for item in group
                    ]
                    for group in observation_groups
                ]
                aggregated_scores.append(
                    ChannelScore(
                        channel.id,
                        fmean(
                            fmean(score.similarity for score in group)
                            for group in family_channel_scores
                        ),
                        fmean(
                            fmean(score.coverage for score in group)
                            for group in family_channel_scores
                        ),
                        fmean(
                            fmean(score.confidence for score in group)
                            for group in family_channel_scores
                        ),
                        tuple(
                            dict.fromkeys(
                                explanation
                                for group in family_channel_scores
                                for score in group
                                for explanation in score.explanations
                            )
                        )[:8],
                    )
                )
            signs = {
                1 if item[0].normalized_utility > 0 else -1 if item[0].normalized_utility < 0 else 0
                for item in all_observations
            }
            conflicts = (
                tuple(item[0].id for item in all_observations)
                if policy.preserve_conflicts and 1 in signs and -1 in signs
                else ()
            )
            use = (
                "start.historical-replay"
                if accepted_rate >= 0.5 and negative_risk < 0.5
                else "start.failure-repair"
            )
            recommendations.append(
                HistoricalRecommendation(
                    route_id=route_id,
                    selection=representative[0].selection,
                    episode_ids=tuple(item[0].id for item in all_observations),
                    dataset_family_ids=tuple(
                        sorted(
                            {
                                item[0].dataset_family_id
                                for item in all_observations
                                if item[0].dataset_family_id
                            }
                        )
                    ),
                    channel_scores=tuple(aggregated_scores),
                    fused_similarity=mean_similarity,
                    expected_normalized_lift=posterior,
                    uncertainty=uncertainty,
                    negative_transfer_risk=negative_risk,
                    accepted_rate=accepted_rate,
                    ranking_score=ranking,
                    recommended_use=use,
                    conflicting_episode_ids=conflicts,
                )
            )
        recommendations.sort(key=lambda item: (-item.ranking_score, item.route_id))
        selected = tuple(recommendations[: policy.top_k])
        recommendation_problems = [
            problem
            for index, recommendation in enumerate(selected)
            for problem in recommendation.validate(f"recommendations[{index}]")
        ]
        if recommendation_problems:
            raise RuntimeError(
                "historical retriever produced invalid recommendations: "
                + "; ".join(recommendation_problems)
            )
        return selected


@dataclass(frozen=True)
class EffortPolicy:
    """Explicit multidimensional defaults for any positive effort level."""

    id: str
    level: int
    fingerprint_layer: str
    historical_start_limit: int
    random_start_count: int
    contrast_start_count: int
    portfolio_limit: int
    sampling_attempt_limit: int
    minimum_history_coverage: float
    search_rounds: tuple[SearchBudget, ...]
    seeds: tuple[int, ...] = (0,)
    repetitions: int = 1
    minimum_acceptance_rate: float = 1.0
    fallback_count: int = 2
    protected_history_blind_lane: bool = True
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.id.startswith("effort."):
            problems.append("effort policy id must use the effort namespace")
        if self.level <= 0:
            problems.append("effort level must be positive")
        if not self.fingerprint_layer.startswith("K") or not self.fingerprint_layer[1:].isdigit():
            problems.append("fingerprint_layer must be K followed by an integer")
        for label, value in (
            ("historical_start_limit", self.historical_start_limit),
            ("random_start_count", self.random_start_count),
            ("contrast_start_count", self.contrast_start_count),
            ("portfolio_limit", self.portfolio_limit),
            ("sampling_attempt_limit", self.sampling_attempt_limit),
            ("repetitions", self.repetitions),
        ):
            if value <= 0:
                problems.append(f"{label} must be positive")
        if not 0.0 <= self.minimum_history_coverage <= 1.0:
            problems.append("minimum_history_coverage must be between zero and one")
        if not self.search_rounds:
            problems.append("effort policy search_rounds must not be empty")
        for index, budget in enumerate(self.search_rounds):
            problems.extend(f"search_rounds[{index}]: {problem}" for problem in budget.validate())
        if not self.seeds or len(self.seeds) != len(set(self.seeds)):
            problems.append("effort seeds must be nonempty and unique")
        if not 0.0 <= self.minimum_acceptance_rate <= 1.0:
            problems.append("minimum_acceptance_rate must be between zero and one")
        if self.fallback_count < 0:
            problems.append("fallback_count must be non-negative")
        problems.extend(_extension_problems(self.extensions, "effort.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "level": self.level,
            "fingerprint_layer": self.fingerprint_layer,
            "historical_start_limit": self.historical_start_limit,
            "random_start_count": self.random_start_count,
            "contrast_start_count": self.contrast_start_count,
            "portfolio_limit": self.portfolio_limit,
            "sampling_attempt_limit": self.sampling_attempt_limit,
            "minimum_history_coverage": self.minimum_history_coverage,
            "search_rounds": [_search_budget_dict(item) for item in self.search_rounds],
            "seeds": list(self.seeds),
            "repetitions": self.repetitions,
            "minimum_acceptance_rate": self.minimum_acceptance_rate,
            "fallback_count": self.fallback_count,
            "protected_history_blind_lane": self.protected_history_blind_lane,
            "extensions": dict(self.extensions),
        }


def effort_policy(level: int | str | EffortPolicy) -> EffortPolicy:
    """Return inspectable defaults without restricting caller-defined policies."""
    if isinstance(level, EffortPolicy):
        problems = level.validate()
        if problems:
            raise ValueError("invalid effort policy: " + "; ".join(problems))
        return level
    if isinstance(level, str):
        normalized = level.casefold().removeprefix("effort.")
        level = 1000 if normalized in ("maximum", "max", "self-learning") else int(normalized)
    if isinstance(level, bool) or level <= 0:
        raise ValueError("effort level must be a positive integer")
    scale = max(1, ceil(log2(level + 1)))
    if level <= 1:
        layer = "K2"
    elif level < 10:
        layer = "K5"
    elif level < 100:
        layer = "K7"
    else:
        layer = "K8"
    rounds: list[SearchBudget] = [SearchBudget(SearchMode.PRIOR, result_limit=max(1, scale))]
    if scale >= 2:
        rounds.append(
            SearchBudget(
                SearchMode.BEAM,
                evaluation_limit=4 * scale * scale,
                result_limit=4 * scale,
                beam_width=4 * scale * scale,
            )
        )
    if scale >= 3:
        rounds.append(
            SearchBudget(
                SearchMode.SPROUT,
                evaluation_limit=6 * scale * scale,
                result_limit=4 * scale,
                random_seed=1729 + level,
                sampling_attempt_limit=24 * scale * scale,
                mutation_probability=min(0.75, 0.25 + 0.03 * scale),
            )
        )
    policy = EffortPolicy(
        id=f"effort.{level}",
        level=level,
        fingerprint_layer=layer,
        historical_start_limit=2 * scale,
        random_start_count=max(1, scale // 2),
        contrast_start_count=max(1, scale // 3),
        portfolio_limit=3 + 4 * scale,
        sampling_attempt_limit=32 * scale * scale,
        minimum_history_coverage=max(0.25, 0.75 - 0.04 * scale),
        search_rounds=tuple(rounds),
        seeds=tuple(range(1 + scale // 3)),
        repetitions=max(1, scale // 4),
        fallback_count=max(1, scale // 2),
    )
    problems = policy.validate()
    if problems:
        raise ValueError("generated invalid effort policy: " + "; ".join(problems))
    return policy


@dataclass(frozen=True)
class StartCandidate:
    id: str
    source_lane: str
    selection: tuple[tuple[str, str], ...]
    history_blind: bool
    predicted_utility: float
    uncertainty: float
    novelty: float
    parent_episode_ids: tuple[str, ...] = ()
    rationale: tuple[str, ...] = ()
    random_seed: int | None = None

    def validate(self, space: AdmittedSpace, path: str = "start") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.source_lane):
            problems.append(f"{path}.id and source_lane must be namespaced")
        selection = dict(self.selection)
        choice_map = dict(space.choices)
        if set(selection) != set(choice_map):
            problems.append(f"{path}.selection must bind every admitted slot exactly once")
        invalid = [
            f"{slot}={candidate}"
            for slot, candidate in selection.items()
            if candidate not in choice_map.get(slot, ())
        ]
        if invalid:
            problems.append(
                f"{path}.selection contains non-admitted bindings: {', '.join(invalid)}"
            )
        if any(constraint.matches(selection) for constraint in space.constraints):
            problems.append(f"{path}.selection violates an admitted-space constraint")
        for label, value in (
            ("predicted_utility", self.predicted_utility),
            ("uncertainty", self.uncertainty),
            ("novelty", self.novelty),
        ):
            if not isfinite(value):
                problems.append(f"{path}.{label} must be finite")
        if self.uncertainty < 0 or not 0.0 <= self.novelty <= 1.0:
            problems.append(f"{path}.uncertainty must be non-negative and novelty in [0,1]")
        if any(not ID_RE.fullmatch(item) for item in self.parent_episode_ids):
            problems.append(f"{path}.parent_episode_ids must be namespaced")
        if len(self.parent_episode_ids) != len(set(self.parent_episode_ids)):
            problems.append(f"{path}.parent_episode_ids must be unique")
        if any(not item.strip() for item in self.rationale):
            problems.append(f"{path}.rationale must not contain empty strings")
        if self.random_seed is not None and (
            isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int)
        ):
            problems.append(f"{path}.random_seed must be an integer or null")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_lane": self.source_lane,
            "selection": dict(self.selection),
            "history_blind": self.history_blind,
            "predicted_utility": self.predicted_utility,
            "uncertainty": self.uncertainty,
            "novelty": self.novelty,
            "parent_episode_ids": list(self.parent_episode_ids),
            "rationale": list(self.rationale),
            "random_seed": self.random_seed,
        }


@dataclass(frozen=True)
class OptimizerAllocation:
    optimizer_id: str
    budget_fraction: float
    protected: bool
    rationale: tuple[str, ...]

    def validate(self, path: str = "optimizer") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.optimizer_id):
            problems.append(f"{path}.optimizer_id must be namespaced")
        if not isfinite(self.budget_fraction) or not 0.0 <= self.budget_fraction <= 1.0:
            problems.append(f"{path}.budget_fraction must be finite and in [0,1]")
        if any(not item.strip() for item in self.rationale):
            problems.append(f"{path}.rationale must not contain empty strings")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "optimizer_id": self.optimizer_id,
            "budget_fraction": self.budget_fraction,
            "protected": self.protected,
            "rationale": list(self.rationale),
        }


def _belief_to_dict(beliefs: BeliefModel) -> dict[str, Any]:
    return {
        "revision": beliefs.revision,
        "default_log_weight": beliefs.default_log_weight,
        "candidate_weights": [
            {
                "slot_id": item.slot_id,
                "candidate_id": item.candidate_id,
                "log_weight": item.log_weight,
                "evidence_count": item.evidence_count,
                "uncertainty": item.uncertainty,
            }
            for item in beliefs.candidate_weights
        ],
        "interaction_weights": [
            {
                "left_slot": item.left_slot,
                "left_candidate": item.left_candidate,
                "right_slot": item.right_slot,
                "right_candidate": item.right_candidate,
                "log_weight": item.log_weight,
                "evidence_count": item.evidence_count,
            }
            for item in beliefs.interaction_weights
        ],
    }


def _search_budget_dict(budget: SearchBudget) -> dict[str, Any]:
    return {
        "mode": budget.mode.value,
        "evaluation_limit": budget.evaluation_limit,
        "result_limit": budget.result_limit,
        "beam_width": budget.beam_width,
        "random_seed": budget.random_seed,
        "sampling_attempt_limit": budget.sampling_attempt_limit,
        "mutation_probability": budget.mutation_probability,
    }


@dataclass(frozen=True)
class SearchInitialization:
    """History-informed optimizer state, kept outside frozen plan semantics."""

    query_fingerprint_digest: str
    memory_digest: str
    retrieval_policy: RetrievalPolicy
    effort_policy: EffortPolicy
    recommendations: tuple[HistoricalRecommendation, ...]
    starts: tuple[StartCandidate, ...]
    optimizer_allocations: tuple[OptimizerAllocation, ...]
    beliefs: BeliefModel
    warnings: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def anchors(self) -> tuple[dict[str, str], ...]:
        return tuple(dict(start.selection) for start in self.starts)

    def validate(self, space: AdmittedSpace) -> list[str]:
        problems: list[str] = []
        for label, digest in (
            ("query_fingerprint_digest", self.query_fingerprint_digest),
            ("memory_digest", self.memory_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{label} must be a sha256 digest")
        problems.extend(self.retrieval_policy.validate())
        problems.extend(self.effort_policy.validate())
        route_ids = [item.route_id for item in self.recommendations]
        if len(route_ids) != len(set(route_ids)):
            problems.append("search initialization recommendations must have unique routes")
        for index, recommendation in enumerate(self.recommendations):
            problems.extend(recommendation.validate(f"recommendations[{index}]"))
        if not self.starts:
            problems.append("search initialization starts must not be empty")
        if self.effort_policy.protected_history_blind_lane and not any(
            start.history_blind for start in self.starts
        ):
            problems.append("protected history-blind lane is missing")
        start_ids = [start.id for start in self.starts]
        if len(start_ids) != len(set(start_ids)):
            problems.append("search initialization start ids must be unique")
        selections = [start.selection for start in self.starts]
        if len(selections) != len(set(selections)):
            problems.append("search initialization selections must be unique")
        for index, start in enumerate(self.starts):
            problems.extend(start.validate(space, f"starts[{index}]"))
        optimizer_ids = [allocation.optimizer_id for allocation in self.optimizer_allocations]
        if len(optimizer_ids) != len(set(optimizer_ids)):
            problems.append("search initialization optimizer ids must be unique")
        for index, allocation in enumerate(self.optimizer_allocations):
            problems.extend(allocation.validate(f"optimizer_allocations[{index}]"))
        if not self.optimizer_allocations:
            problems.append("search initialization optimizer_allocations must not be empty")
        total = sum(item.budget_fraction for item in self.optimizer_allocations)
        if self.optimizer_allocations and abs(total - 1.0) > 1e-9:
            problems.append("optimizer allocation fractions must sum to one")
        problems.extend(self.beliefs.validate())
        if not self.beliefs.revision.strip():
            problems.append("history beliefs revision must not be empty")
        choice_map = dict(space.choices)
        candidate_weight_keys = [
            (weight.slot_id, weight.candidate_id) for weight in self.beliefs.candidate_weights
        ]
        if len(candidate_weight_keys) != len(set(candidate_weight_keys)):
            problems.append("history candidate weights must be unique")
        for weight in self.beliefs.candidate_weights:
            if weight.candidate_id not in choice_map.get(weight.slot_id, ()):
                problems.append("history beliefs must reference only admitted candidates")
        interaction_weight_keys = [
            (
                weight.left_slot,
                weight.left_candidate,
                weight.right_slot,
                weight.right_candidate,
            )
            for weight in self.beliefs.interaction_weights
        ]
        if len(interaction_weight_keys) != len(set(interaction_weight_keys)):
            problems.append("history interaction weights must be unique")
        for weight in self.beliefs.interaction_weights:
            if weight.left_candidate not in choice_map.get(
                weight.left_slot, ()
            ) or weight.right_candidate not in choice_map.get(weight.right_slot, ()):
                problems.append(
                    "history interaction beliefs must reference only admitted candidates"
                )
        if any(not warning.strip() for warning in self.warnings):
            problems.append("search initialization warnings must not contain empty strings")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_intelligence_model_version": TASK_INTELLIGENCE_MODEL_VERSION,
            "query_fingerprint_digest": self.query_fingerprint_digest,
            "memory_digest": self.memory_digest,
            "retrieval_policy": self.retrieval_policy.to_dict(),
            "effort_policy": self.effort_policy.to_dict(),
            "recommendations": [item.to_dict() for item in self.recommendations],
            "starts": [start.to_dict() for start in self.starts],
            "optimizer_allocations": [item.to_dict() for item in self.optimizer_allocations],
            "beliefs": _belief_to_dict(self.beliefs),
            "warnings": list(self.warnings),
        }


def _selection_distance(left: Mapping[str, str], right: Mapping[str, str]) -> float:
    keys = set(left) | set(right)
    return sum(left.get(key) != right.get(key) for key in keys) / max(1, len(keys))


def _start_id(lane: str, selection: Mapping[str, str]) -> str:
    suffix = sha256_digest({"lane": lane, "selection": dict(selection)}).removeprefix("sha256:")[
        :20
    ]
    return f"start.{suffix}"


def _valid_selection(space: AdmittedSpace, selection: Mapping[str, str]) -> bool:
    choice_map = dict(space.choices)
    return (
        set(selection) == set(choice_map)
        and all(candidate in choice_map[slot] for slot, candidate in selection.items())
        and not any(constraint.matches(selection) for constraint in space.constraints)
    )


class HistoryInformedPlanner:
    """Compose compatible starts, beliefs, optimizers, and effort defaults."""

    def __init__(self, retriever: HistoricalRetriever | None = None) -> None:
        self.retriever = retriever or HistoricalRetriever()

    def plan(
        self,
        space: AdmittedSpace,
        query: TaskFingerprint,
        memory: HistoricalMemory,
        *,
        effort: int | str | EffortPolicy = 5,
        retrieval_policy: RetrievalPolicy | None = None,
        canonical_selection: Mapping[str, str] | None = None,
        random_seed: int = 0,
    ) -> SearchInitialization:
        selected_effort = effort_policy(effort)
        selected_retrieval = retrieval_policy or RetrievalPolicy(
            top_k=max(1, selected_effort.historical_start_limit)
        )
        recommendations = self.retriever.retrieve(query, memory, selected_retrieval)
        warnings: list[str] = []
        requested_layer = int(selected_effort.fingerprint_layer.removeprefix("K"))
        available_layer = int(query.knowledge_layer.removeprefix("K"))
        if available_layer < requested_layer:
            warnings.append(
                f"Effort policy requested {selected_effort.fingerprint_layer} profiling, "
                f"but the supplied fingerprint is {query.knowledge_layer}; retrieval "
                "continued with missing-aware channels."
            )
        if canonical_selection is None:
            report = SearchEngine().search(
                space,
                BeliefModel(revision="history-blind.canonical"),
                SearchBudget(SearchMode.PRIOR, result_limit=1),
            )
            if not report.proposals:
                raise ValueError("admitted space has no feasible canonical route")
            canonical_selection = report.proposals[0].selection
        canonical = dict(canonical_selection)
        if not _valid_selection(space, canonical):
            raise ValueError("canonical_selection must be a complete feasible admitted route")
        starts: list[StartCandidate] = [
            StartCandidate(
                _start_id("start.canonical-history-blind", canonical),
                "start.canonical-history-blind",
                tuple(canonical.items()),
                True,
                0.0,
                1.0,
                1.0,
                rationale=("Deterministic compiler-admitted control without historical outcomes.",),
            )
        ]
        seen = {tuple(canonical.items())}
        choice_map = dict(space.choices)

        for recommendation in recommendations[: selected_effort.historical_start_limit]:
            historical = dict(recommendation.selection)
            compatible = {
                slot: candidate
                for slot, candidate in historical.items()
                if candidate in choice_map.get(slot, ())
            }
            coverage = len(compatible) / max(1, len(choice_map))
            if coverage < selected_effort.minimum_history_coverage:
                warnings.append(
                    f"Historical route {recommendation.route_id} retained as evidence but not a start; compatible coverage={coverage:.3f}."
                )
                continue
            repaired = {**canonical, **compatible}
            key = tuple(repaired.items())
            if key in seen or not _valid_selection(space, repaired):
                continue
            seen.add(key)
            starts.append(
                StartCandidate(
                    _start_id(recommendation.recommended_use, repaired),
                    recommendation.recommended_use,
                    key,
                    False,
                    recommendation.expected_normalized_lift,
                    recommendation.uncertainty,
                    _selection_distance(repaired, canonical),
                    recommendation.episode_ids,
                    (
                        f"History similarity={recommendation.fused_similarity:.3f}.",
                        f"Negative-transfer risk={recommendation.negative_transfer_risk:.3f}.",
                        f"Compatible historical coverage={coverage:.3f}.",
                    ),
                )
            )

        sample_count = selected_effort.random_start_count + selected_effort.contrast_start_count
        if sample_count:
            random_report = SearchEngine().search(
                space,
                BeliefModel(revision="history-blind.random"),
                SearchBudget(
                    SearchMode.SPROUT,
                    evaluation_limit=sample_count,
                    result_limit=sample_count,
                    random_seed=random_seed,
                    sampling_attempt_limit=selected_effort.sampling_attempt_limit,
                    mutation_probability=1.0,
                ),
            )
            random_routes = [proposal.selection for proposal in random_report.proposals]
            random_routes.sort(
                key=lambda selection: (
                    -_selection_distance(selection, canonical),
                    tuple(selection.items()),
                )
            )
            for index, selection in enumerate(random_routes):
                key = tuple(selection.items())
                if key in seen:
                    continue
                seen.add(key)
                contrast = index < selected_effort.contrast_start_count
                lane = "start.contrast-history-blind" if contrast else "start.random-history-blind"
                starts.append(
                    StartCandidate(
                        _start_id(lane, selection),
                        lane,
                        key,
                        True,
                        0.0,
                        1.0,
                        _selection_distance(selection, canonical),
                        rationale=("Compiler-valid outcome-history-blind exploration lane.",),
                        random_seed=random_seed,
                    )
                )
        if len(starts) == 1 and space.route_count_upper_bound > 1:
            warnings.append("Random/contrast sampling did not produce a distinct feasible route.")

        selected_starts = self._select_diverse(starts, selected_effort.portfolio_limit)
        beliefs = self._beliefs(space, query, memory, recommendations)
        average_confidence = (
            fmean(
                recommendation.fused_similarity * (1.0 - recommendation.negative_transfer_risk)
                for recommendation in recommendations
            )
            if recommendations
            else 0.0
        )
        allocations = self._optimizer_allocations(average_confidence)
        initialization = SearchInitialization(
            query.digest,
            memory.digest,
            selected_retrieval,
            selected_effort,
            recommendations,
            selected_starts,
            allocations,
            beliefs,
            tuple(warnings),
        )
        problems = initialization.validate(space)
        if problems:
            raise ValueError("invalid search initialization: " + "; ".join(problems))
        return initialization

    @staticmethod
    def _select_diverse(starts: Sequence[StartCandidate], limit: int) -> tuple[StartCandidate, ...]:
        selected: list[StartCandidate] = []
        remaining = list(starts)
        canonical = next(
            (item for item in remaining if item.source_lane == "start.canonical-history-blind"),
            remaining[0],
        )
        selected.append(canonical)
        remaining.remove(canonical)
        while remaining and len(selected) < limit:

            def key(item: StartCandidate) -> tuple[float, float, str]:
                diversity = min(
                    _selection_distance(dict(item.selection), dict(chosen.selection))
                    for chosen in selected
                )
                evidence = item.predicted_utility - item.uncertainty
                protected = 0.25 if item.history_blind else 0.0
                return diversity + 0.15 * evidence + protected, item.novelty, item.id

            winner = max(remaining, key=key)
            selected.append(winner)
            remaining.remove(winner)
        return tuple(selected)

    @staticmethod
    def _beliefs(
        space: AdmittedSpace,
        query: TaskFingerprint,
        memory: HistoricalMemory,
        recommendations: Sequence[HistoricalRecommendation],
    ) -> BeliefModel:
        choice_map = dict(space.choices)
        accumulators: dict[tuple[str, str], list[tuple[float, int, float]]] = defaultdict(list)
        for recommendation in recommendations:
            strength = recommendation.ranking_score * max(
                -2.0, min(2.0, recommendation.expected_normalized_lift + 1.0)
            )
            evidence = max(1, len(recommendation.episode_ids))
            for slot, candidate in recommendation.selection:
                if candidate in choice_map.get(slot, ()):
                    accumulators[(slot, candidate)].append(
                        (strength, evidence, recommendation.uncertainty)
                    )
        weights = tuple(
            CandidateWeight(
                slot,
                candidate,
                fmean(item[0] for item in values),
                sum(item[1] for item in values),
                fmean(item[2] for item in values),
            )
            for (slot, candidate), values in sorted(accumulators.items())
        )
        revision = (
            "history."
            + memory.digest.removeprefix("sha256:")[:12]
            + "."
            + query.digest.removeprefix("sha256:")[:12]
        )
        return BeliefModel(revision=revision, candidate_weights=weights)

    @staticmethod
    def _optimizer_allocations(history_confidence: float) -> tuple[OptimizerAllocation, ...]:
        history_fraction = 0.15 + 0.30 * max(0.0, min(1.0, history_confidence))
        beam_fraction = 0.30
        sprout_fraction = 1.0 - history_fraction - beam_fraction
        return (
            OptimizerAllocation(
                "optimizer.history-prior",
                history_fraction,
                False,
                ("Exploit calibrated historical route/component evidence.",),
            ),
            OptimizerAllocation(
                "optimizer.typed-beam",
                beam_fraction,
                False,
                ("Explore high-belief compiler-valid combinations.",),
            ),
            OptimizerAllocation(
                "optimizer.seeded-sprout",
                sprout_fraction,
                True,
                ("Protected contrast, random, repair, and escape exploration.",),
            ),
        )


def merge_belief_models(primary: BeliefModel, secondary: BeliefModel) -> BeliefModel:
    """Combine advisory priors without changing admission or plan identity."""
    problems = (*primary.validate(), *secondary.validate())
    if problems:
        raise ValueError("cannot merge invalid beliefs: " + "; ".join(problems))
    candidates: dict[tuple[str, str], list[CandidateWeight]] = defaultdict(list)
    for item in (*primary.candidate_weights, *secondary.candidate_weights):
        candidates[(item.slot_id, item.candidate_id)].append(item)
    interactions: dict[tuple[str, str, str, str], list[InteractionWeight]] = defaultdict(list)
    for item in (*primary.interaction_weights, *secondary.interaction_weights):
        interactions[
            (item.left_slot, item.left_candidate, item.right_slot, item.right_candidate)
        ].append(item)
    return BeliefModel(
        revision=f"merge.{sha256_digest((primary.revision, secondary.revision))[-20:]}",
        candidate_weights=tuple(
            CandidateWeight(
                key[0],
                key[1],
                sum(item.log_weight for item in values),
                sum(item.evidence_count for item in values),
                fmean(item.uncertainty for item in values),
            )
            for key, values in sorted(candidates.items())
        ),
        interaction_weights=tuple(
            InteractionWeight(
                *key,
                sum(item.log_weight for item in values),
                sum(item.evidence_count for item in values),
            )
            for key, values in sorted(interactions.items())
        ),
        default_log_weight=primary.default_log_weight + secondary.default_log_weight,
    )


@dataclass(frozen=True)
class LaneOutcome:
    start_id: str
    source_lane: str
    budget_digest: str
    normalized_lift: float
    accepted: bool

    def validate(self, path: str = "lane_outcome") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.start_id) or not ID_RE.fullmatch(self.source_lane):
            problems.append(f"{path}.start_id and source_lane must be namespaced")
        if not DIGEST_RE.fullmatch(self.budget_digest):
            problems.append(f"{path}.budget_digest must be a sha256 digest")
        if not isfinite(self.normalized_lift):
            problems.append(f"{path}.normalized_lift must be finite")
        return problems


@dataclass(frozen=True)
class NegativeTransferAssessment:
    status: str
    prior_miss: bool
    matched_budget_count: int
    history_best_lift: float | None
    history_blind_best_lift: float | None
    regret: float | None
    recommended_lanes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "prior_miss": self.prior_miss,
            "matched_budget_count": self.matched_budget_count,
            "history_best_lift": self.history_best_lift,
            "history_blind_best_lift": self.history_blind_best_lift,
            "regret": self.regret,
            "recommended_lanes": list(self.recommended_lanes),
        }


def assess_negative_transfer(
    outcomes: Sequence[LaneOutcome], *, tolerance: float = 0.0
) -> NegativeTransferAssessment:
    """Compare historical and history-blind lanes only at matched budgets."""
    problems = [
        problem
        for index, item in enumerate(outcomes)
        for problem in item.validate(f"outcomes[{index}]")
    ]
    if problems:
        raise ValueError("invalid transfer assessment: " + "; ".join(problems))
    by_budget: dict[str, list[LaneOutcome]] = defaultdict(list)
    for outcome in outcomes:
        by_budget[outcome.budget_digest].append(outcome)
    matched = []
    for items in by_budget.values():
        historical = [
            item.normalized_lift for item in items if "history-blind" not in item.source_lane
        ]
        blind = [item.normalized_lift for item in items if "history-blind" in item.source_lane]
        if historical and blind:
            matched.append((max(historical), max(blind)))
    if not matched:
        return NegativeTransferAssessment(
            "assessment.insufficient-matched-evidence", False, 0, None, None, None, ()
        )
    history_best = max(item[0] for item in matched)
    blind_best = max(item[1] for item in matched)
    regret = blind_best - history_best
    prior_miss = regret > tolerance
    lanes = (
        (
            "start.contrast-history-blind",
            "start.random-history-blind",
            "start.failure-repair",
        )
        if prior_miss
        else ()
    )
    return NegativeTransferAssessment(
        "assessment.prior-miss" if prior_miss else "assessment.no-prior-miss",
        prior_miss,
        len(matched),
        history_best,
        blind_best,
        regret,
        lanes,
    )


__all__ = [
    "DEFAULT_SIMILARITY_CHANNELS",
    "TASK_INTELLIGENCE_MODEL_VERSION",
    "AttributeSimilarityChannel",
    "CategorySimilarityChannel",
    "ChannelScore",
    "EffortPolicy",
    "EmbeddingSimilarityChannel",
    "ExactSimilarityChannel",
    "FingerprintAttribute",
    "HistoricalEpisode",
    "HistoricalMemory",
    "HistoricalOutcome",
    "HistoricalRecommendation",
    "HistoricalRetriever",
    "HistoryInformedPlanner",
    "LaneOutcome",
    "NegativeTransferAssessment",
    "OptimizerAllocation",
    "RetrievalPolicy",
    "SearchInitialization",
    "SimilarityChannel",
    "StartCandidate",
    "TaskEmbedding",
    "TaskFingerprint",
    "assess_negative_transfer",
    "effort_policy",
    "fingerprint_from_contract",
    "historical_episode_from_receipts",
    "merge_belief_models",
    "profile_tabular_records",
]
