"""Machine-learning dataset, split, label, leakage, and evaluation questions."""

from __future__ import annotations

from solutiongraph.question_packs.base import deterministic, human, llm, pack, q

ML = ("concept.dataset.recordset", "concept.ml.target", "concept.ml.split")

ML_DATASET_QUESTIONS = (
    q(
        "ml-dataset", "target", "Target validity",
        "Is the target well-defined, measured consistently, and available for the intended prediction horizon?",
        ("concept.ml.target",), "ml.target-invalid", "critical",
        (deterministic("quality.ml-target-check"),
         human("quality.review-ml-target")), scope="pipeline",
        preconditions=("precondition.records-available", "precondition.target-available"),
    ),
    q(
        "ml-dataset", "target-balance", "Target distribution and balance",
        "Is the target balanced or long-tailed, and does the evaluation metric reflect the consequential regions?",
        ("concept.ml.target",), "ml.target-distribution-risk", "high",
        (deterministic("quality.target-balance-check", cost_tier=2),
         llm("quality.interpret-target-distribution")), scope="dataset",
    ),
    q(
        "ml-dataset", "split-integrity", "Split integrity",
        "Are train, validation, and holdout splits disjoint at row, entity, group, and time levels?",
        ML, "ml.split-contamination", "critical",
        (deterministic("quality.ml-split-integrity-check", cost_tier=3),), scope="dataset",
        preconditions=("precondition.records-available", "precondition.split-available"),
    ),
    q(
        "ml-dataset", "feature-leakage", "Feature and target leakage",
        "Do features duplicate, encode, postdate, or otherwise reveal the target?",
        ML, "ml.feature-leakage", "critical",
        (deterministic("quality.ml-leakage-check", cost_tier=3),
         llm("quality.audit-ml-leakage", cost_tier=7)), scope="pipeline",
    ),
    q(
        "ml-dataset", "duplicate-leakage", "Duplicate examples across splits",
        "Do exact or near-duplicate examples cross split boundaries and inflate evaluation?",
        ML, "ml.duplicate-split-leakage", "critical",
        (deterministic("quality.ml-duplicate-split-check", cost_tier=3),), scope="dataset",
    ),
    q(
        "ml-dataset", "missingness", "Missingness and imputation boundary",
        "Are imputation statistics learned only from training data and applied consistently to later splits?",
        ML, "ml.imputation-leakage", "critical",
        (deterministic("quality.ml-imputation-boundary-check", cost_tier=3),), scope="pipeline",
    ),
    q(
        "ml-dataset", "drift", "Train-to-serving drift",
        "Which feature, target, missingness, and category distributions differ across time, splits, or serving data?",
        ML, "ml.distribution-drift", "high",
        (deterministic("quality.ml-drift-check", cost_tier=4),
         llm("quality.interpret-ml-drift", cost_tier=7)), scope="dataset",
    ),
    q(
        "ml-dataset", "prediction-contamination", "Prediction-column contamination",
        "Are prior model scores, predictions, or post-outcome features unintentionally included as training inputs?",
        ("concept.ml.target", "concept.ml.prediction"),
        "ml.prediction-contamination", "critical",
        (deterministic("quality.ml-prediction-contamination-check", cost_tier=2),),
        scope="cross-field",
    ),
    q(
        "ml-dataset", "evaluation-slices", "Evaluation slice coverage",
        "Does evaluation cover rare classes, tails, geographies, periods, source systems, and high-harm groups?",
        ML, "ml.evaluation-slice-gap", "high",
        (deterministic("quality.ml-slice-coverage-check", cost_tier=4),
         human("quality.review-ml-slices")), scope="pipeline",
    ),
)

ML_DATASET_PACK = pack(
    "ml-dataset", "Machine-learning dataset interrogation",
    "Target, split, leakage, imputation, drift, contamination, and evaluation-slice questions.",
    ML_DATASET_QUESTIONS,
)

__all__ = ["ML_DATASET_PACK", "ML_DATASET_QUESTIONS"]
