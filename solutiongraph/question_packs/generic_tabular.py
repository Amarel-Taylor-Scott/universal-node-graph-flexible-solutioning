"""Questions applicable to nearly every record-oriented dataset."""

from __future__ import annotations

from solutiongraph.question_packs.base import deterministic, human, llm, pack, q
from solutiongraph.question_packs.concepts import DQV, SHACL

DATASET = ("concept.dataset.recordset",)

GENERIC_TABULAR_QUESTIONS = (
    q(
        "generic-tabular", "placeholders", "Missing and placeholder values",
        "Which fields contain blanks, sentinels, test values, or placeholder tokens?",
        DATASET, "data.placeholder-values", "medium",
        (deterministic("quality.placeholder-check"),), scope="dataset",
        repairs=("repair.normalize-missing", "repair.quarantine-record"), references=(DQV,),
    ),
    q(
        "generic-tabular", "unicode-controls", "Unicode and control characters",
        "Do values contain non-normalized Unicode, control characters, or invisible separators?",
        DATASET, "data.unicode-or-control", "medium",
        (deterministic("quality.unicode-control-check"),), scope="dataset",
        repairs=("repair.normalize-unicode", "repair.strip-controls"),
    ),
    q(
        "generic-tabular", "whitespace", "Whitespace anomalies",
        "Do text values contain leading, trailing, or repeated whitespace that changes matching?",
        DATASET, "data.whitespace-anomaly", "low",
        (deterministic("quality.whitespace-check"),), scope="dataset",
        repairs=("repair.trim-whitespace",),
    ),
    q(
        "generic-tabular", "type-conformance", "Observed type conformance",
        "Do values conform to the inferred or declared field type without silent coercion?",
        DATASET, "data.type-nonconformance", "high",
        (deterministic("quality.type-conformance-check"),), scope="dataset",
        references=(SHACL,),
    ),
    q(
        "generic-tabular", "duplicate-rows", "Duplicate records",
        "Are exact duplicate records present, and are they expected repetitions or ingestion errors?",
        DATASET, "data.duplicate-record", "medium",
        (deterministic("quality.duplicate-record-check"),), scope="dataset",
        repairs=("repair.quarantine-duplicate",),
    ),
    q(
        "generic-tabular", "identifier-uniqueness", "Identifier uniqueness",
        "Do identifier-like fields remain unique where the data contract requires uniqueness?",
        ("concept.dataset.record-id",), "data.identifier-duplicate", "high",
        (deterministic("quality.identifier-uniqueness-check"),), scope="dataset",
        preconditions=("precondition.records-available", "precondition.identifier-available"),
    ),
    q(
        "generic-tabular", "conditional-missingness", "Conditional missingness",
        "Does missingness change materially by source, time, geography, or entity type?",
        DATASET, "data.conditional-missingness", "medium",
        (deterministic("quality.conditional-missingness-check", cost_tier=3),
         llm("quality.interpret-missingness", cost_tier=7)), scope="dataset",
        evidence=("evidence.missingness-matrix", "evidence.group-counts"),
    ),
    q(
        "generic-tabular", "modal-dominance", "Cardinality and modal dominance",
        "Do low entropy, impossible cardinality, or dominant values indicate defaults or broken ingestion?",
        DATASET, "data.suspicious-cardinality", "medium",
        (deterministic("quality.cardinality-check", cost_tier=2),), scope="dataset",
        evidence=("evidence.cardinality", "evidence.top-value-hashes"),
    ),
    q(
        "generic-tabular", "numeric-outliers", "Numeric outliers",
        "Which numeric values are extreme under robust distribution checks, and are they plausible?",
        DATASET, "data.numeric-outlier", "medium",
        (deterministic("quality.numeric-outlier-check", cost_tier=2),
         llm("quality.interpret-outlier-clusters", cost_tier=7)), scope="dataset",
        repairs=("repair.quarantine-record",),
    ),
    q(
        "generic-tabular", "cross-field-conflicts", "Cross-field contradictions",
        "Which combinations of fields contradict declared or learned invariants?",
        DATASET, "data.cross-field-conflict", "high",
        (deterministic("quality.cross-field-check", cost_tier=3),
         llm("quality.adjudicate-cross-field-conflict", cost_tier=7),
         human("quality.review-cross-field-conflict")), scope="cross-field",
        evidence=("evidence.invariant", "evidence.affected-count"),
    ),
    q(
        "generic-tabular", "source-conflicts", "Source and survivorship conflicts",
        "When sources disagree, is the selected value supported by an explicit survivorship rule?",
        ("concept.dataset.recordset", "concept.dataset.source"),
        "data.source-conflict", "high",
        (deterministic("quality.source-conflict-check", cost_tier=3),
         human("quality.review-source-conflict")), scope="entity",
        preconditions=("precondition.records-available", "precondition.source-available"),
    ),
    q(
        "generic-tabular", "privacy-exposure", "Sensitive-value exposure",
        "Are values, samples, logs, or model contexts exposing data beyond the declared privacy boundary?",
        DATASET, "data.privacy-exposure", "critical",
        (deterministic("quality.privacy-pattern-check", cost_tier=3),
         human("quality.review-privacy-boundary")), scope="pipeline",
        privacy_class="privacy.restricted",
    ),
)

GENERIC_TABULAR_PACK = pack(
    "generic-tabular",
    "Generic tabular interrogation",
    "Aggregate, field, row, cross-field, and source-quality questions for record datasets.",
    GENERIC_TABULAR_QUESTIONS,
)

__all__ = ["GENERIC_TABULAR_PACK", "GENERIC_TABULAR_QUESTIONS"]
