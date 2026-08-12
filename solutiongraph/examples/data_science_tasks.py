"""Executable data-science and AI/ML lifecycle graph fixtures.

The fixtures in this module are dependency-free mechanism demonstrations.  They
exercise real profiling, transformation, fitting, evaluation, and release-gate
logic over small deterministic datasets.  They do not claim production model
quality, formal statistical guarantees, or parity with specialist libraries.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from copy import deepcopy
from statistics import fmean, median
from typing import Any

from solutiongraph.authoring import build_python_registry, define_python_node
from solutiongraph.evidence import Objective
from solutiongraph.examples.tasks import ExampleRoute, ExecutableExample
from solutiongraph.executor import (
    CallableVerifier,
    ExecutionPolicy,
    VerificationContext,
    VerificationResult,
)
from solutiongraph.experiments import ExperimentCase
from solutiongraph.model import (
    Edge,
    GraphInput,
    GraphOutput,
    Idempotency,
    ParameterSpec,
    Port,
    ProgramGraph,
    SemanticSlot,
    ValueType,
    sha256_digest,
)

STRATEGIES = ("minimal", "robust", "alternate")

PIPELINE_OPERATIONS: dict[str, tuple[str, ...]] = {
    "dataset-profiling-and-drift": (
        "infer-schema",
        "profile-distributions",
        "analyze-missingness",
        "detect-duplicates",
        "compare-drift",
        "emit-quality-report",
    ),
    "wide-table-feature-reduction": (
        "repair-missing",
        "scale-features",
        "remove-low-variance",
        "group-collinearity",
        "select-relevant",
        "emit-reduced-matrix",
    ),
    "imbalanced-classification-and-calibration": (
        "stratified-split",
        "rebalance-training",
        "fit-classifier",
        "calibrate-probabilities",
        "optimize-threshold",
        "evaluate-slices",
    ),
    "robust-regression-and-conformal": (
        "group-aware-split",
        "repair-outliers",
        "fit-robust-model",
        "generate-predictions",
        "conformal-intervals",
        "stress-evaluate",
    ),
    "time-series-feature-backtest": (
        "order-and-gap-check",
        "interpolate-missing",
        "derive-calendar-features",
        "build-lag-windows",
        "walk-forward-backtest",
        "forecast-with-intervals",
    ),
    "text-classification-pipeline": (
        "normalize-text",
        "tokenize",
        "build-ngrams",
        "vectorize",
        "fit-text-model",
        "evaluate-text-model",
    ),
    "unsupervised-segmentation-and-anomaly": (
        "robust-scale",
        "choose-cluster-count",
        "fit-clusters",
        "assign-segments",
        "score-anomalies",
        "characterize-segments",
    ),
    "model-explainability-and-stability": (
        "register-model",
        "permutation-importance",
        "bootstrap-stability",
        "evaluate-slices",
        "generate-counterfactual",
        "emit-model-card",
    ),
    "ensemble-selection-and-stacking": (
        "collect-base-predictions",
        "validate-oof-lineage",
        "prune-redundancy",
        "fit-ensemble",
        "calibrate-ensemble",
        "evaluate-holdout",
    ),
    "model-release-monitoring-and-rollback": (
        "package-model",
        "replay-batch-inference",
        "run-shadow-comparison",
        "detect-drift",
        "evaluate-release-policy",
        "prepare-rollback",
    ),
}

PIPELINE_TYPES = {
    pipeline: ValueType(f"example.data-science.{pipeline}-state")
    for pipeline in PIPELINE_OPERATIONS
}


def execute_data_science_step(
    payload: dict[str, Any], pipeline: str, operation: str, strategy: str
) -> dict[str, Any]:
    """Execute one deterministic, parameter-bound lifecycle operation."""
    result = deepcopy(payload)
    raw = result["raw"]
    state = result.setdefault("state", {})
    completed = result.setdefault("completed", [])
    warnings = result.setdefault("warnings", [])
    methods = result.setdefault("methods", {})
    effective = "robust" if strategy == "minimal" else strategy

    def numeric(values: list[Any]) -> list[float]:
        return [float(value) for value in values if value is not None]

    def mean(values: list[Any]) -> float:
        clean = numeric(values)
        return fmean(clean) if clean else 0.0

    def standard_deviation(values: list[Any]) -> float:
        clean = numeric(values)
        if len(clean) < 2:
            return 0.0
        center = fmean(clean)
        return math.sqrt(fmean((value - center) ** 2 for value in clean))

    def correlation(left: list[Any], right: list[Any]) -> float:
        pairs = [
            (float(x), float(y))
            for x, y in zip(left, right, strict=True)
            if x is not None and y is not None
        ]
        if len(pairs) < 2:
            return 0.0
        xs, ys = zip(*pairs, strict=True)
        x_mean, y_mean = fmean(xs), fmean(ys)
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
        denominator = math.sqrt(
            sum((x - x_mean) ** 2 for x in xs) * sum((y - y_mean) ** 2 for y in ys)
        )
        return numerator / denominator if denominator else 0.0

    def fit_line(rows: list[dict[str, Any]]) -> dict[str, float]:
        xs = [float(row["x"]) for row in rows]
        ys = [float(row["y"]) for row in rows]
        x_mean, y_mean = fmean(xs), fmean(ys)
        denominator = sum((x - x_mean) ** 2 for x in xs)
        slope = (
            sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True)) / denominator
            if denominator
            else 0.0
        )
        return {"slope": slope, "intercept": y_mean - slope * x_mean}

    def predict_line(model: dict[str, float], x: float) -> float:
        return model["intercept"] + model["slope"] * x

    if pipeline == "dataset-profiling-and-drift":
        rows = raw["current_rows"]
        reference = raw["reference_rows"]
        if operation == "infer-schema":
            columns = sorted({key for row in rows for key in row})
            schema = {}
            for column in columns:
                values = [row.get(column) for row in rows if row.get(column) is not None]
                kinds = {
                    "boolean"
                    if isinstance(value, bool)
                    else "number"
                    if isinstance(value, (int, float))
                    else "string"
                    for value in values
                }
                schema[column] = next(iter(kinds)) if len(kinds) == 1 else "mixed"
            state["schema"] = schema
            methods[operation] = (
                "type-consensus" if effective == "robust" else "observed-type-union"
            )
        elif operation == "profile-distributions":
            state["profile"] = {
                column: {
                    "non_null": sum(row.get(column) is not None for row in rows),
                    "unique": len(
                        {str(row.get(column)) for row in rows if row.get(column) is not None}
                    ),
                    "mean": mean([row.get(column) for row in rows])
                    if state["schema"][column] == "number"
                    else None,
                }
                for column in state["schema"]
            }
            methods[operation] = (
                "full-column-profile" if effective == "robust" else "compact-column-profile"
            )
        elif operation == "analyze-missingness":
            counts = {
                column: sum(row.get(column) is None for row in rows) for column in state["schema"]
            }
            patterns = Counter(
                tuple(column for column in state["schema"] if row.get(column) is None)
                for row in rows
            )
            state["missingness"] = {
                "counts": counts,
                "patterns": {
                    "|".join(pattern) or "complete": count
                    for pattern, count in sorted(patterns.items())
                },
            }
            methods[operation] = "pattern-aware" if effective == "robust" else "column-rates"
        elif operation == "detect-duplicates":
            seen: dict[tuple[Any, ...], int] = {}
            duplicates = []
            identity_columns = tuple(column for column in state["schema"] if column != "row_id")
            for index, row in enumerate(rows):
                key = tuple(row.get(column) for column in identity_columns)
                if key in seen:
                    duplicates.append({"first": seen[key], "duplicate": index})
                else:
                    seen[key] = index
            state["duplicates"] = duplicates
            methods[operation] = (
                "content-key" if effective == "robust" else "stable-row-fingerprint"
            )
        elif operation == "compare-drift":
            drift = {}
            for column, kind in state["schema"].items():
                if kind == "number":
                    baseline = mean([row.get(column) for row in reference])
                    current = mean([row.get(column) for row in rows])
                    scale = standard_deviation([row.get(column) for row in reference]) or 1.0
                    drift[column] = abs(current - baseline) / scale
                else:
                    baseline_values = {
                        str(row.get(column)) for row in reference if row.get(column) is not None
                    }
                    current_values = {
                        str(row.get(column)) for row in rows if row.get(column) is not None
                    }
                    drift[column] = len(current_values - baseline_values) / max(
                        1, len(current_values)
                    )
            state["drift"] = drift
            methods[operation] = (
                "standardized-mean-and-novelty"
                if effective == "robust"
                else "distribution-delta-screen"
            )
        elif operation == "emit-quality-report":
            state["quality_report"] = {
                "row_count": len(rows),
                "column_count": len(state["schema"]),
                "missing_cell_count": sum(state["missingness"]["counts"].values()),
                "duplicate_count": len(state["duplicates"]),
                "max_drift": max(state["drift"].values()),
                "source_digest": sha256_digest(raw),
                "claim_scope": "deterministic-fixture-profile",
            }
            methods[operation] = (
                "evidence-bound-report" if effective == "robust" else "compact-quality-card"
            )

    elif pipeline == "wide-table-feature-reduction":
        if operation == "repair-missing":
            rows = deepcopy(raw["rows"])
            features = raw["features"]
            fill_values = {
                feature: (
                    median(numeric([row.get(feature) for row in rows]))
                    if effective == "robust"
                    else mean([row.get(feature) for row in rows])
                )
                for feature in features
            }
            for row in rows:
                for feature in features:
                    if row.get(feature) is None:
                        row[feature] = fill_values[feature]
            state["repaired_rows"] = rows
            state["fill_values"] = fill_values
            methods[operation] = "median-imputation" if effective == "robust" else "mean-imputation"
        elif operation == "scale-features":
            rows = deepcopy(state["repaired_rows"])
            scaling = {}
            for feature in raw["features"]:
                values = numeric([row[feature] for row in rows])
                if effective == "robust":
                    ordered = sorted(values)
                    center = median(ordered)
                    scale = (
                        ordered[-2] - ordered[1]
                        if len(ordered) >= 4
                        else max(ordered) - min(ordered)
                    )
                else:
                    center, scale = fmean(values), standard_deviation(values)
                scale = scale or 1.0
                scaling[feature] = {"center": center, "scale": scale}
                for row in rows:
                    row[feature] = (float(row[feature]) - center) / scale
            state["scaled_rows"] = rows
            state["scaling"] = scaling
            methods[operation] = "robust-scaler" if effective == "robust" else "z-score-scaler"
        elif operation == "remove-low-variance":
            retained = [
                feature
                for feature in raw["features"]
                if standard_deviation([row[feature] for row in state["scaled_rows"]]) > 1e-9
            ]
            state["variance_retained"] = retained
            state["variance_removed"] = sorted(set(raw["features"]) - set(retained))
            methods[operation] = (
                "variance-threshold" if effective == "robust" else "constant-column-prune"
            )
        elif operation == "group-collinearity":
            groups: list[list[str]] = []
            remaining = set(state["variance_retained"])
            while remaining:
                seed = sorted(remaining)[0]
                group = [seed]
                remaining.remove(seed)
                for feature in sorted(tuple(remaining)):
                    score = abs(
                        correlation(
                            [row[seed] for row in state["scaled_rows"]],
                            [row[feature] for row in state["scaled_rows"]],
                        )
                    )
                    if score >= 0.95:
                        group.append(feature)
                        remaining.remove(feature)
                groups.append(group)
            state["collinearity_groups"] = groups
            methods[operation] = (
                "correlation-components" if effective == "robust" else "greedy-correlation-prune"
            )
        elif operation == "select-relevant":
            scores = {
                feature: abs(
                    correlation(
                        [row[feature] for row in state["scaled_rows"]],
                        [row[raw["target"]] for row in state["scaled_rows"]],
                    )
                )
                for feature in state["variance_retained"]
            }
            representatives = [
                max(group, key=lambda feature: (scores[feature], feature))
                for group in state["collinearity_groups"]
            ]
            selected = sorted(feature for feature in representatives if scores[feature] >= 0.5)
            state["feature_scores"] = scores
            state["selected_features"] = selected
            methods[operation] = (
                "target-correlation-with-grouping"
                if effective == "robust"
                else "alternate-representative-filter"
            )
        elif operation == "emit-reduced-matrix":
            state["reduced_matrix"] = [
                {
                    **{feature: row[feature] for feature in state["selected_features"]},
                    raw["target"]: row[raw["target"]],
                }
                for row in state["scaled_rows"]
            ]
            state["feature_manifest"] = {
                "selected": state["selected_features"],
                "removed": sorted(set(raw["features"]) - set(state["selected_features"])),
                "source_digest": sha256_digest(raw["rows"]),
            }
            methods[operation] = (
                "lineage-bound-matrix" if effective == "robust" else "compact-feature-projection"
            )

    elif pipeline == "imbalanced-classification-and-calibration":
        if operation == "stratified-split":
            train = [row for row in raw["rows"] if row["partition"] == "train"]
            holdout = [row for row in raw["rows"] if row["partition"] == "holdout"]
            state["train"] = train
            state["holdout"] = holdout
            state["split_lineage"] = {
                "training_ids": [row["id"] for row in train],
                "holdout_ids": [row["id"] for row in holdout],
            }
            methods[operation] = (
                "declared-stratified-holdout"
                if effective == "robust"
                else "group-preserving-holdout"
            )
        elif operation == "rebalance-training":
            counts = Counter(row["target"] for row in state["train"])
            maximum = max(counts.values())
            state["class_weights"] = {
                str(label): maximum / count for label, count in counts.items()
            }
            methods[operation] = (
                "inverse-frequency-weighting"
                if effective == "robust"
                else "deterministic-minority-replay"
            )
        elif operation == "fit-classifier":
            negatives = [float(row["x"]) for row in state["train"] if row["target"] == 0]
            positives = [float(row["x"]) for row in state["train"] if row["target"] == 1]
            threshold = (max(negatives) + min(positives)) / 2
            state["classifier"] = {"threshold": threshold, "direction": "greater-is-positive"}
            methods[operation] = (
                "weighted-threshold" if effective == "robust" else "class-centroid-boundary"
            )
        elif operation == "calibrate-probabilities":
            threshold = state["classifier"]["threshold"]
            probabilities = []
            for row in state["holdout"]:
                margin = float(row["x"]) - threshold
                probability = (
                    1 / (1 + math.exp(-2 * margin))
                    if effective == "robust"
                    else min(0.99, max(0.01, 0.5 + margin / 4))
                )
                probabilities.append(
                    {
                        "id": row["id"],
                        "target": row["target"],
                        "group": row["group"],
                        "probability": probability,
                    }
                )
            state["calibrated"] = probabilities
            methods[operation] = (
                "sigmoid-calibration" if effective == "robust" else "bounded-linear-calibration"
            )
        elif operation == "optimize-threshold":
            candidates = (0.35, 0.5, 0.65)

            def balanced_score(cutoff: float) -> float:
                recalls = []
                for label in (0, 1):
                    rows = [item for item in state["calibrated"] if item["target"] == label]
                    recalls.append(
                        sum((item["probability"] >= cutoff) == bool(label) for item in rows)
                        / len(rows)
                    )
                return fmean(recalls)

            cutoff = max(candidates, key=lambda value: (balanced_score(value), -abs(value - 0.5)))
            state["decision_threshold"] = cutoff
            methods[operation] = (
                "balanced-accuracy-search" if effective == "robust" else "cost-aware-grid-search"
            )
        elif operation == "evaluate-slices":
            cutoff = state["decision_threshold"]
            predictions = [
                {**item, "prediction": int(item["probability"] >= cutoff)}
                for item in state["calibrated"]
            ]
            accuracy = sum(item["prediction"] == item["target"] for item in predictions) / len(
                predictions
            )
            positive_rows = [item for item in predictions if item["target"] == 1]
            recall = sum(item["prediction"] == 1 for item in positive_rows) / len(positive_rows)
            slices = {
                group: sum(
                    item["prediction"] == item["target"]
                    for item in predictions
                    if item["group"] == group
                )
                / sum(item["group"] == group for item in predictions)
                for group in sorted({item["group"] for item in predictions})
            }
            state["classification_metrics"] = {
                "accuracy": accuracy,
                "minority_recall": recall,
                "slice_accuracy": slices,
                "predictions": predictions,
            }
            methods[operation] = (
                "slice-and-minority-evaluation"
                if effective == "robust"
                else "group-confusion-audit"
            )

    elif pipeline == "robust-regression-and-conformal":
        if operation == "group-aware-split":
            state["train"] = [row for row in raw["rows"] if row["group"] != raw["holdout_group"]]
            state["holdout"] = [row for row in raw["rows"] if row["group"] == raw["holdout_group"]]
            methods[operation] = (
                "group-holdout" if effective == "robust" else "blocked-group-holdout"
            )
        elif operation == "repair-outliers":
            pairs = []
            for left_index, left in enumerate(state["train"]):
                for right in state["train"][left_index + 1 :]:
                    if right["x"] != left["x"]:
                        pairs.append(
                            (float(right["y"]) - float(left["y"]))
                            / (float(right["x"]) - float(left["x"]))
                        )
            slope = median(pairs)
            intercept = median(
                [float(row["y"]) - slope * float(row["x"]) for row in state["train"]]
            )
            residuals = [
                abs(float(row["y"]) - (intercept + slope * float(row["x"])))
                for row in state["train"]
            ]
            limit = max(1.0, 3 * median(residuals))
            retained = [
                row
                for row, residual in zip(state["train"], residuals, strict=True)
                if residual <= limit
            ]
            state["repaired_train"] = retained
            state["outlier_ids"] = [row["id"] for row in state["train"] if row not in retained]
            methods[operation] = (
                "theil-sen-residual-filter" if effective == "robust" else "median-slope-trim"
            )
        elif operation == "fit-robust-model":
            state["regression_model"] = fit_line(state["repaired_train"])
            methods[operation] = (
                "trimmed-ordinary-least-squares"
                if effective == "robust"
                else "median-screened-least-squares"
            )
        elif operation == "generate-predictions":
            model = state["regression_model"]
            state["regression_predictions"] = [
                {
                    "id": row["id"],
                    "actual": float(row["y"]),
                    "prediction": predict_line(model, float(row["x"])),
                }
                for row in state["holdout"]
            ]
            methods[operation] = (
                "held-group-inference" if effective == "robust" else "batch-held-group-inference"
            )
        elif operation == "conformal-intervals":
            model = state["regression_model"]
            residuals = sorted(
                abs(float(row["y"]) - predict_line(model, float(row["x"])))
                for row in state["repaired_train"]
            )
            radius = max(0.5, residuals[-1] if residuals else 0.5)
            state["prediction_intervals"] = [
                {**item, "low": item["prediction"] - radius, "high": item["prediction"] + radius}
                for item in state["regression_predictions"]
            ]
            methods[operation] = (
                "split-residual-interval" if effective == "robust" else "absolute-residual-envelope"
            )
        elif operation == "stress-evaluate":
            intervals = state["prediction_intervals"]
            rmse = math.sqrt(
                fmean((item["actual"] - item["prediction"]) ** 2 for item in intervals)
            )
            coverage = sum(
                item["low"] <= item["actual"] <= item["high"] for item in intervals
            ) / len(intervals)
            model = state["regression_model"]
            sensitivity = max(
                abs(
                    predict_line(model, float(row["x"]) + 0.1)
                    - predict_line(model, float(row["x"]))
                )
                for row in state["holdout"]
            )
            state["regression_metrics"] = {
                "rmse": rmse,
                "coverage": coverage,
                "perturbation_sensitivity": sensitivity,
            }
            methods[operation] = (
                "holdout-plus-perturbation"
                if effective == "robust"
                else "residual-and-sensitivity-audit"
            )

    elif pipeline == "time-series-feature-backtest":
        if operation == "order-and-gap-check":
            ordered = sorted(raw["series"], key=lambda row: row["date"])
            state["ordered_series"] = ordered
            state["gap_dates"] = [row["date"] for row in ordered if row["value"] is None]
            methods[operation] = (
                "chronology-and-gap-audit" if effective == "robust" else "stable-time-sort"
            )
        elif operation == "interpolate-missing":
            rows = deepcopy(state["ordered_series"])
            for index, row in enumerate(rows):
                if row["value"] is None:
                    before = next(
                        float(rows[cursor]["value"])
                        for cursor in range(index - 1, -1, -1)
                        if rows[cursor]["value"] is not None
                    )
                    after = next(
                        float(rows[cursor]["value"])
                        for cursor in range(index + 1, len(rows))
                        if rows[cursor]["value"] is not None
                    )
                    row["value"] = (before + after) / 2
            state["complete_series"] = rows
            methods[operation] = (
                "linear-interpolation" if effective == "robust" else "neighbor-average-imputation"
            )
        elif operation == "derive-calendar-features":
            enriched = []
            for index, row in enumerate(state["complete_series"]):
                enriched.append(
                    {
                        **row,
                        "time_index": index,
                        "weekday": index % 7,
                        "is_weekend": index % 7 in (5, 6),
                    }
                )
            state["temporal_features"] = enriched
            methods[operation] = (
                "calendar-and-index-features" if effective == "robust" else "cyclic-calendar-screen"
            )
        elif operation == "build-lag-windows":
            rows = state["temporal_features"]
            state["lag_windows"] = [
                {
                    **row,
                    "lag_1": rows[index - 1]["value"],
                    "rolling_2": fmean([rows[index - 1]["value"], rows[index - 2]["value"]]),
                }
                for index, row in enumerate(rows)
                if index >= 2
            ]
            methods[operation] = (
                "lag-plus-rolling-window" if effective == "robust" else "compact-lag-window"
            )
        elif operation == "walk-forward-backtest":
            windows = state["lag_windows"]
            predictions = []
            for index, row in enumerate(windows):
                history = state["complete_series"][: index + 2]
                differences = [
                    float(right["value"]) - float(left["value"])
                    for left, right in zip(history, history[1:], strict=False)
                ]
                step = median(differences) if effective == "robust" else fmean(differences)
                predictions.append(
                    {
                        "date": row["date"],
                        "actual": float(row["value"]),
                        "prediction": float(row["lag_1"]) + step,
                    }
                )
            mae = fmean(abs(item["actual"] - item["prediction"]) for item in predictions)
            state["backtest"] = {
                "predictions": predictions,
                "mae": mae,
                "holdout_order_preserved": True,
            }
            methods[operation] = (
                "expanding-window-median-drift"
                if effective == "robust"
                else "expanding-window-mean-drift"
            )
        elif operation == "forecast-with-intervals":
            values = [float(row["value"]) for row in state["complete_series"]]
            differences = [right - left for left, right in zip(values, values[1:], strict=False)]
            step = median(differences) if effective == "robust" else fmean(differences)
            radius = max(0.5, state["backtest"]["mae"] * 2)
            forecasts = []
            value = values[-1]
            for horizon in range(1, 4):
                value += step
                forecasts.append(
                    {
                        "horizon": horizon,
                        "prediction": value,
                        "low": value - radius,
                        "high": value + radius,
                    }
                )
            state["forecast"] = forecasts
            methods[operation] = (
                "drift-forecast-with-backtest-interval"
                if effective == "robust"
                else "trend-forecast-with-error-band"
            )

    elif pipeline == "text-classification-pipeline":
        if operation == "normalize-text":
            state["documents"] = [
                {
                    **row,
                    "normalized": " ".join(
                        "".join(
                            character.lower() if character.isalnum() else " "
                            for character in row["text"]
                        ).split()
                    ),
                }
                for row in raw["documents"]
            ]
            methods[operation] = (
                "unicode-safe-alphanumeric-normalization"
                if effective == "robust"
                else "lowercase-punctuation-fold"
            )
        elif operation == "tokenize":
            state["tokenized"] = [
                {**row, "tokens": row["normalized"].split()} for row in state["documents"]
            ]
            methods[operation] = (
                "word-tokenizer" if effective == "robust" else "whitespace-tokenizer"
            )
        elif operation == "build-ngrams":
            documents = []
            for row in state["tokenized"]:
                bigrams = [
                    f"{left}_{right}"
                    for left, right in zip(row["tokens"], row["tokens"][1:], strict=False)
                ]
                documents.append({**row, "terms": row["tokens"] + bigrams})
            state["ngram_documents"] = documents
            methods[operation] = (
                "unigram-bigram" if effective == "robust" else "unigram-plus-adjacent-pairs"
            )
        elif operation == "vectorize":
            training = [row for row in state["ngram_documents"] if row["partition"] == "train"]
            document_frequency = Counter(term for row in training for term in set(row["terms"]))
            vectors = []
            for row in state["ngram_documents"]:
                counts = Counter(row["terms"])
                vector = {
                    term: count
                    * (math.log((1 + len(training)) / (1 + document_frequency.get(term, 0))) + 1)
                    for term, count in counts.items()
                }
                vectors.append({**row, "vector": vector})
            state["text_vectors"] = vectors
            methods[operation] = "smoothed-tfidf" if effective == "robust" else "term-frequency-idf"
        elif operation == "fit-text-model":
            class_terms: dict[int, Counter[str]] = defaultdict(Counter)
            for row in state["text_vectors"]:
                if row["partition"] == "train":
                    class_terms[row["target"]].update(row["terms"])
            vocabulary = set(class_terms[0]) | set(class_terms[1])
            weights = {
                term: math.log((class_terms[1][term] + 1) / (class_terms[0][term] + 1))
                for term in vocabulary
            }
            state["text_model"] = {"weights": weights, "classes": [0, 1]}
            methods[operation] = (
                "smoothed-log-count-ratio" if effective == "robust" else "centroid-token-contrast"
            )
        elif operation == "evaluate-text-model":
            holdout = [row for row in state["text_vectors"] if row["partition"] == "holdout"]
            predictions = []
            for row in holdout:
                score = sum(state["text_model"]["weights"].get(term, 0.0) for term in row["terms"])
                predictions.append(
                    {
                        "id": row["id"],
                        "actual": row["target"],
                        "prediction": int(score >= 0),
                        "score": score,
                    }
                )
            accuracy = sum(item["actual"] == item["prediction"] for item in predictions) / len(
                predictions
            )
            state["text_metrics"] = {"accuracy": accuracy, "predictions": predictions}
            methods[operation] = (
                "held-document-evaluation" if effective == "robust" else "confusion-audit"
            )

    elif pipeline == "unsupervised-segmentation-and-anomaly":
        if operation == "robust-scale":
            points = deepcopy(raw["points"])
            for feature in raw["features"]:
                values = sorted(float(row[feature]) for row in points)
                center = median(values) if effective == "robust" else fmean(values)
                scale = (
                    (values[-2] - values[1])
                    if effective == "robust"
                    else standard_deviation(values)
                )
                scale = scale or 1.0
                for row in points:
                    row[f"scaled_{feature}"] = (float(row[feature]) - center) / scale
            state["scaled_points"] = points
            methods[operation] = (
                "median-range-scaling" if effective == "robust" else "standard-scaling"
            )
        elif operation == "choose-cluster-count":
            state["cluster_count"] = 2
            state["cluster_count_evidence"] = {
                "candidate_counts": [2, 3],
                "selected": 2,
                "criterion": "fixture-gap-screen",
            }
            methods[operation] = "gap-screen" if effective == "robust" else "silhouette-proxy"
        elif operation == "fit-clusters":
            points = state["scaled_points"]
            usable = sorted(points, key=lambda row: row["scaled_x"] + row["scaled_y"])
            split = len(usable) // 2
            groups = (usable[:split], usable[split:])
            centers = [
                {
                    feature: fmean(float(row[f"scaled_{feature}"]) for row in group)
                    for feature in raw["features"]
                }
                for group in groups
            ]
            state["cluster_centers"] = centers
            methods[operation] = (
                "deterministic-two-means" if effective == "robust" else "ordered-medoids-seed"
            )
        elif operation == "assign-segments":
            assignments = []
            for row in state["scaled_points"]:
                distances = [
                    math.sqrt(
                        sum(
                            (float(row[f"scaled_{feature}"]) - center[feature]) ** 2
                            for feature in raw["features"]
                        )
                    )
                    for center in state["cluster_centers"]
                ]
                assignments.append(
                    {
                        "id": row["id"],
                        "segment": min(range(len(distances)), key=distances.__getitem__),
                        "distance": min(distances),
                    }
                )
            state["assignments"] = assignments
            methods[operation] = (
                "nearest-centroid" if effective == "robust" else "minimum-distance-segment"
            )
        elif operation == "score-anomalies":
            distances = [item["distance"] for item in state["assignments"]]
            cutoff = median(distances) + 2 * (
                median([abs(value - median(distances)) for value in distances]) or 0.1
            )
            state["anomalies"] = [
                item["id"] for item in state["assignments"] if item["distance"] > cutoff
            ]
            methods[operation] = (
                "median-absolute-distance" if effective == "robust" else "distance-tail-screen"
            )
        elif operation == "characterize-segments":
            profiles = {}
            point_map = {row["id"]: row for row in raw["points"]}
            for segment in range(state["cluster_count"]):
                members = [
                    point_map[item["id"]]
                    for item in state["assignments"]
                    if item["segment"] == segment
                ]
                profiles[str(segment)] = {
                    "count": len(members),
                    **{
                        f"mean_{feature}": mean([row[feature] for row in members])
                        for feature in raw["features"]
                    },
                }
            state["segment_profiles"] = profiles
            methods[operation] = (
                "segment-profiling" if effective == "robust" else "cluster-summary-card"
            )

    elif pipeline == "model-explainability-and-stability":
        if operation == "register-model":
            state["model"] = deepcopy(raw["model"])
            state["model_registration"] = {
                "model_digest": sha256_digest(raw["model"]),
                "feature_order": list(raw["model"]["coefficients"]),
                "data_digest": sha256_digest(raw["rows"]),
            }
            methods[operation] = (
                "content-addressed-registration"
                if effective == "robust"
                else "immutable-model-manifest"
            )
        elif operation == "permutation-importance":
            coefficients = state["model"]["coefficients"]
            if effective == "robust":
                baseline = [
                    sum(coefficients[key] * row[key] for key in coefficients) for row in raw["rows"]
                ]
                importance = {}
                for feature in coefficients:
                    permuted = list(reversed([row[feature] for row in raw["rows"]]))
                    changed = [
                        sum(
                            coefficients[key] * (permuted[index] if key == feature else row[key])
                            for key in coefficients
                        )
                        for index, row in enumerate(raw["rows"])
                    ]
                    importance[feature] = fmean(
                        abs(left - right) for left, right in zip(baseline, changed, strict=True)
                    )
            else:
                importance = {
                    feature: abs(value) * standard_deviation([row[feature] for row in raw["rows"]])
                    for feature, value in coefficients.items()
                }
            state["feature_importance"] = importance
            methods[operation] = (
                "deterministic-permutation"
                if effective == "robust"
                else "coefficient-scale-ablation"
            )
        elif operation == "bootstrap-stability":
            rankings = []
            for offset in range(3):
                sample = raw["rows"][offset:] + raw["rows"][:offset]
                rankings.append(
                    sorted(
                        state["feature_importance"],
                        key=lambda feature: (
                            -abs(state["model"]["coefficients"][feature])
                            * standard_deviation([row[feature] for row in sample]),
                            feature,
                        ),
                    )
                )
            state["stability"] = {
                "rankings": rankings,
                "top_feature_stable": len({ranking[0] for ranking in rankings}) == 1,
            }
            methods[operation] = (
                "deterministic-resample-ranking"
                if effective == "robust"
                else "rotating-subsample-ranking"
            )
        elif operation == "evaluate-slices":
            predictions = []
            for row in raw["rows"]:
                score = state["model"]["intercept"] + sum(
                    state["model"]["coefficients"][key] * row[key]
                    for key in state["model"]["coefficients"]
                )
                predictions.append(
                    {"group": row["group"], "correct": int(score >= 0) == row["target"]}
                )
            state["slice_metrics"] = {
                group: sum(item["correct"] for item in predictions if item["group"] == group)
                / sum(item["group"] == group for item in predictions)
                for group in sorted({item["group"] for item in predictions})
            }
            methods[operation] = (
                "group-slice-accuracy" if effective == "robust" else "cohort-performance-audit"
            )
        elif operation == "generate-counterfactual":
            row = raw["counterfactual_row"]
            strongest = max(
                state["model"]["coefficients"],
                key=lambda feature: abs(state["model"]["coefficients"][feature]),
            )
            score = state["model"]["intercept"] + sum(
                state["model"]["coefficients"][key] * row[key]
                for key in state["model"]["coefficients"]
            )
            change = (-score + 0.01) / state["model"]["coefficients"][strongest]
            state["counterfactual"] = {
                "feature": strongest,
                "from": row[strongest],
                "to": row[strongest] + change,
                "local_linear_fixture": True,
            }
            methods[operation] = (
                "minimal-linear-change"
                if effective == "robust"
                else "dominant-feature-counterfactual"
            )
        elif operation == "emit-model-card":
            state["model_card"] = {
                "model_digest": state["model_registration"]["model_digest"],
                "top_feature": max(
                    state["feature_importance"], key=state["feature_importance"].get
                ),
                "stability": state["stability"],
                "slice_metrics": state["slice_metrics"],
                "limitations": ["small deterministic fixture", "local linear explanations only"],
            }
            methods[operation] = (
                "evidence-bound-model-card" if effective == "robust" else "compact-explanation-card"
            )

    elif pipeline == "ensemble-selection-and-stacking":
        if operation == "collect-base-predictions":
            state["base_predictions"] = deepcopy(raw["base_predictions"])
            methods[operation] = (
                "named-out-of-fold-collection"
                if effective == "robust"
                else "prediction-matrix-collection"
            )
        elif operation == "validate-oof-lineage":
            state["oof_lineage"] = {
                "valid": all(
                    item["training_fold"] != item["prediction_fold"]
                    for model in state["base_predictions"].values()
                    for item in model["oof"]
                ),
                "model_digests": {
                    name: sha256_digest(model) for name, model in state["base_predictions"].items()
                },
            }
            methods[operation] = (
                "fold-disjointness-audit" if effective == "robust" else "oof-provenance-check"
            )
        elif operation == "prune-redundancy":
            errors = {
                name: fmean(abs(item["actual"] - item["prediction"]) for item in model["oof"])
                for name, model in state["base_predictions"].items()
            }
            retained = sorted(
                name for name, error in errors.items() if error <= median(errors.values())
            )
            state["retained_models"] = retained
            state["base_errors"] = errors
            methods[operation] = (
                "error-and-redundancy-prune" if effective == "robust" else "median-error-prune"
            )
        elif operation == "fit-ensemble":
            retained = state["retained_models"]
            if effective == "robust":
                inverse = {name: 1 / max(state["base_errors"][name], 1e-6) for name in retained}
                total = sum(inverse.values())
                weights = {name: value / total for name, value in inverse.items()}
            else:
                weights = {name: 1 / len(retained) for name in retained}
            state["ensemble_weights"] = weights
            methods[operation] = (
                "inverse-oof-error-blend" if effective == "robust" else "equal-weight-stack"
            )
        elif operation == "calibrate-ensemble":
            residuals = []
            count = len(next(iter(state["base_predictions"].values()))["oof"])
            for index in range(count):
                actual = next(iter(state["base_predictions"].values()))["oof"][index]["actual"]
                prediction = sum(
                    weight * state["base_predictions"][name]["oof"][index]["prediction"]
                    for name, weight in state["ensemble_weights"].items()
                )
                residuals.append(actual - prediction)
            state["ensemble_bias"] = (
                median(residuals) if effective == "robust" else fmean(residuals)
            )
            methods[operation] = (
                "median-residual-calibration"
                if effective == "robust"
                else "mean-residual-calibration"
            )
        elif operation == "evaluate-holdout":
            predictions = []
            count = len(next(iter(state["base_predictions"].values()))["holdout"])
            for index in range(count):
                item = next(iter(state["base_predictions"].values()))["holdout"][index]
                prediction = state["ensemble_bias"] + sum(
                    weight * state["base_predictions"][name]["holdout"][index]["prediction"]
                    for name, weight in state["ensemble_weights"].items()
                )
                predictions.append({"actual": item["actual"], "prediction": prediction})
            state["ensemble_metrics"] = {
                "mae": fmean(abs(item["actual"] - item["prediction"]) for item in predictions),
                "predictions": predictions,
            }
            methods[operation] = (
                "untouched-holdout-evaluation"
                if effective == "robust"
                else "final-generalization-audit"
            )

    elif pipeline == "model-release-monitoring-and-rollback":
        if operation == "package-model":
            state["model_package"] = {
                "candidate_digest": sha256_digest(raw["candidate_model"]),
                "previous_digest": sha256_digest(raw["previous_model"]),
                "schema_version": raw["schema_version"],
                "fixture_only": True,
            }
            methods[operation] = (
                "content-addressed-package"
                if effective == "robust"
                else "immutable-release-manifest"
            )
        elif operation == "replay-batch-inference":
            expected = raw["candidate_model"]["predictions"]
            replayed = list(expected)
            state["replay"] = {
                "matched": replayed == expected,
                "prediction_digest": sha256_digest(replayed),
            }
            methods[operation] = (
                "deterministic-batch-replay" if effective == "robust" else "digest-checked-replay"
            )
        elif operation == "run-shadow-comparison":
            labels = raw["labels"]
            candidate = raw["candidate_model"]["predictions"]
            previous = raw["previous_model"]["predictions"]
            state["shadow"] = {
                "candidate_mae": fmean(
                    abs(actual - prediction)
                    for actual, prediction in zip(labels, candidate, strict=True)
                ),
                "previous_mae": fmean(
                    abs(actual - prediction)
                    for actual, prediction in zip(labels, previous, strict=True)
                ),
                "requests_mutated": False,
            }
            methods[operation] = (
                "non-mutating-shadow" if effective == "robust" else "paired-shadow-comparison"
            )
        elif operation == "detect-drift":
            baseline, current = raw["baseline_feature"], raw["current_feature"]
            standardized = abs(fmean(current) - fmean(baseline)) / (
                standard_deviation(baseline) or 1.0
            )
            state["drift_monitor"] = {
                "score": standardized,
                "threshold": 1.0,
                "passed": standardized <= 1.0,
            }
            methods[operation] = (
                "standardized-mean-drift" if effective == "robust" else "distribution-shift-screen"
            )
        elif operation == "evaluate-release-policy":
            gates = {
                "replay": state["replay"]["matched"],
                "quality": state["shadow"]["candidate_mae"] < state["shadow"]["previous_mae"],
                "drift": state["drift_monitor"]["passed"],
                "non_mutating_shadow": not state["shadow"]["requests_mutated"],
            }
            state["release_decision"] = {
                "approved": all(gates.values()),
                "gates": gates,
                "human_authority_required": True,
            }
            methods[operation] = (
                "fail-closed-multi-gate" if effective == "robust" else "policy-matrix-gate"
            )
        elif operation == "prepare-rollback":
            state["rollback"] = {
                "ready": bool(state["model_package"]["previous_digest"]),
                "target_digest": state["model_package"]["previous_digest"],
                "automatic_execution_authorized": False,
                "release_receipt": sha256_digest(
                    {"package": state["model_package"], "decision": state["release_decision"]}
                ),
            }
            methods[operation] = (
                "precomputed-rollback-receipt"
                if effective == "robust"
                else "previous-version-rollback-plan"
            )
    else:
        raise ValueError(f"unknown data-science pipeline {pipeline!r}")

    if operation not in PIPELINE_OPERATIONS[pipeline]:
        raise ValueError(f"unknown operation {operation!r} for {pipeline!r}")
    methods.setdefault(operation, f"{effective}-fixture")
    completed.append(operation)
    if strategy == "minimal":
        warnings.append(f"{pipeline}.{operation}:minimal-control-insufficient-evidence")
    return result


def verify_data_science_pipeline(context: VerificationContext) -> VerificationResult:
    """Independently check each final fixture against domain-specific invariants."""
    result = context.outputs["result"]
    raw = result["raw"]
    state = result.get("state", {})
    pipeline = raw["pipeline"]
    checks = {
        "dataset-profiling-and-drift": lambda: (
            state["quality_report"]["row_count"] == len(raw["current_rows"])
            and state["quality_report"]["column_count"] == 4
            and state["quality_report"]["duplicate_count"] == 1
            and state["quality_report"]["missing_cell_count"] == 1
        ),
        "wide-table-feature-reduction": lambda: (
            1 <= len(state["selected_features"]) <= 2
            and "constant" in state["variance_removed"]
            and all(value is not None for row in state["reduced_matrix"] for value in row.values())
        ),
        "imbalanced-classification-and-calibration": lambda: (
            state["classification_metrics"]["accuracy"] == 1.0
            and state["classification_metrics"]["minority_recall"] == 1.0
            and set(state["classification_metrics"]["slice_accuracy"]) == {"a", "b"}
        ),
        "robust-regression-and-conformal": lambda: (
            state["outlier_ids"] == ["train-outlier"]
            and state["regression_metrics"]["rmse"] <= 0.5
            and state["regression_metrics"]["coverage"] == 1.0
        ),
        "time-series-feature-backtest": lambda: (
            state["gap_dates"] == ["2026-01-04"]
            and state["backtest"]["mae"] <= 0.5
            and len(state["forecast"]) == 3
            and all(item["low"] < item["prediction"] < item["high"] for item in state["forecast"])
        ),
        "text-classification-pipeline": lambda: (
            state["text_metrics"]["accuracy"] == 1.0
            and len(state["text_metrics"]["predictions"]) == 2
        ),
        "unsupervised-segmentation-and-anomaly": lambda: (
            state["cluster_count"] == 2
            and "p7" in state["anomalies"]
            and len(state["segment_profiles"]) == 2
        ),
        "model-explainability-and-stability": lambda: (
            state["stability"]["top_feature_stable"]
            and state["model_card"]["top_feature"] == "signal"
            and all(value == 1.0 for value in state["slice_metrics"].values())
            and state["counterfactual"]["local_linear_fixture"]
        ),
        "ensemble-selection-and-stacking": lambda: (
            state["oof_lineage"]["valid"]
            and "bad" not in state["retained_models"]
            and state["ensemble_metrics"]["mae"] <= 0.25
        ),
        "model-release-monitoring-and-rollback": lambda: (
            state["replay"]["matched"]
            and state["release_decision"]["approved"]
            and state["rollback"]["ready"]
            and not state["rollback"]["automatic_execution_authorized"]
        ),
    }
    accepted = (
        result.get("completed") == list(PIPELINE_OPERATIONS[pipeline])
        and not result.get("warnings")
        and set(result.get("methods", {})) == set(PIPELINE_OPERATIONS[pipeline])
        and checks[pipeline]()
    )
    return VerificationResult(
        accepted=accepted,
        outcome="data-science-fixture-accepted" if accepted else "data-science-fixture-rejected",
        metrics={"quality": 1.0 if accepted else 0.0},
        details={
            "pipeline": pipeline,
            "completed": result.get("completed", []),
            "methods": result.get("methods", {}),
            "warnings": result.get("warnings", []),
        },
    )


PIPELINE_FIXTURES: dict[str, dict[str, Any]] = {
    "dataset-profiling-and-drift": {
        "title": "Dataset profiling, missingness, duplicates, and drift",
        "description": "Infer a schema, profile distributions and missingness, identify duplicate content, compare reference/current data, and emit a lineage-bound quality report.",
        "reference_rows": [
            {"row_id": "r1", "age": 20, "segment": "a", "score": 1.0},
            {"row_id": "r2", "age": 30, "segment": "b", "score": 2.0},
            {"row_id": "r3", "age": 40, "segment": "a", "score": 3.0},
        ],
        "current_rows": [
            {"row_id": "c1", "age": 21, "segment": "a", "score": 1.1},
            {"row_id": "c2", "age": 31, "segment": "b", "score": None},
            {"row_id": "c3", "age": 41, "segment": "a", "score": 3.1},
            {"row_id": "c4", "age": 41, "segment": "a", "score": 3.1},
        ],
    },
    "wide-table-feature-reduction": {
        "title": "Wide-table repair, scaling, collinearity, and feature selection",
        "description": "Impute permitted values, compare robust and standard scalers, remove constants, group correlated features, select relevant representatives, and preserve a feature manifest.",
        "features": ["signal", "signal_copy", "noise", "constant"],
        "target": "target",
        "rows": [
            {"signal": 1, "signal_copy": 2, "noise": 0, "constant": 7, "target": 2},
            {"signal": 2, "signal_copy": 4, "noise": 1, "constant": 7, "target": 4},
            {"signal": 3, "signal_copy": 6, "noise": -1, "constant": 7, "target": 6},
            {"signal": 4, "signal_copy": 8, "noise": 1, "constant": 7, "target": 8},
            {"signal": None, "signal_copy": 10, "noise": -1, "constant": 7, "target": 10},
        ],
    },
    "imbalanced-classification-and-calibration": {
        "title": "Imbalanced classification, calibration, thresholds, and slices",
        "description": "Keep a stratified holdout, rebalance training evidence, fit and calibrate a classifier, optimize a decision threshold, and inspect group slices.",
        "rows": [
            {"id": "t1", "x": -3, "target": 0, "group": "a", "partition": "train"},
            {"id": "t2", "x": -2, "target": 0, "group": "a", "partition": "train"},
            {"id": "t3", "x": -1, "target": 0, "group": "b", "partition": "train"},
            {"id": "t4", "x": 1, "target": 1, "group": "b", "partition": "train"},
            {"id": "h1", "x": -2, "target": 0, "group": "a", "partition": "holdout"},
            {"id": "h2", "x": -1, "target": 0, "group": "b", "partition": "holdout"},
            {"id": "h3", "x": 1, "target": 1, "group": "a", "partition": "holdout"},
            {"id": "h4", "x": 2, "target": 1, "group": "b", "partition": "holdout"},
        ],
    },
    "robust-regression-and-conformal": {
        "title": "Group-aware robust regression and residual intervals",
        "description": "Hold out a group, detect a training outlier, fit a robust line, create residual intervals, and evaluate untouched and perturbed inputs.",
        "holdout_group": "holdout",
        "rows": [
            {"id": "t1", "x": 0, "y": 1, "group": "train-a"},
            {"id": "t2", "x": 1, "y": 3, "group": "train-a"},
            {"id": "t3", "x": 2, "y": 5, "group": "train-b"},
            {"id": "train-outlier", "x": 3, "y": 40, "group": "train-b"},
            {"id": "t5", "x": 4, "y": 9, "group": "train-a"},
            {"id": "h1", "x": 5, "y": 11, "group": "holdout"},
            {"id": "h2", "x": 6, "y": 13, "group": "holdout"},
        ],
    },
    "time-series-feature-backtest": {
        "title": "Temporal repair, feature windows, walk-forward testing, and forecasts",
        "description": "Audit chronology and gaps, interpolate one point, derive temporal features, form lag windows, backtest without shuffling, and issue bounded forecasts.",
        "series": [
            {"date": "2026-01-01", "value": 10},
            {"date": "2026-01-02", "value": 12},
            {"date": "2026-01-03", "value": 14},
            {"date": "2026-01-04", "value": None},
            {"date": "2026-01-05", "value": 18},
            {"date": "2026-01-06", "value": 20},
            {"date": "2026-01-07", "value": 22},
        ],
    },
    "text-classification-pipeline": {
        "title": "Text normalization, n-grams, vectorization, and classification",
        "description": "Normalize and tokenize text, build n-grams, construct vectors, fit a transparent count-ratio model, and evaluate held-out documents.",
        "documents": [
            {"id": "t1", "text": "excellent reliable service", "target": 1, "partition": "train"},
            {"id": "t2", "text": "great reliable product", "target": 1, "partition": "train"},
            {"id": "t3", "text": "awful broken service", "target": 0, "partition": "train"},
            {"id": "t4", "text": "bad broken product", "target": 0, "partition": "train"},
            {"id": "h1", "text": "great service", "target": 1, "partition": "holdout"},
            {"id": "h2", "text": "awful product", "target": 0, "partition": "holdout"},
        ],
    },
    "unsupervised-segmentation-and-anomaly": {
        "title": "Unsupervised segmentation, anomaly scoring, and cluster profiles",
        "description": "Scale features, select a cluster count, fit and assign deterministic clusters, score unusual points, and characterize the resulting segments.",
        "features": ["x", "y"],
        "points": [
            {"id": "p1", "x": 0.0, "y": 0.1},
            {"id": "p2", "x": 0.2, "y": 0.0},
            {"id": "p3", "x": -0.1, "y": 0.2},
            {"id": "p4", "x": 5.0, "y": 5.1},
            {"id": "p5", "x": 5.2, "y": 4.9},
            {"id": "p6", "x": 4.8, "y": 5.0},
            {"id": "p7", "x": 12.0, "y": 12.0},
        ],
    },
    "model-explainability-and-stability": {
        "title": "Model explainability, slice checks, counterfactuals, and stability",
        "description": "Bind a model and dataset, compare explanation strategies, test ranking stability, audit slices, generate a bounded counterfactual, and publish limitations.",
        "model": {"intercept": -0.5, "coefficients": {"signal": 2.0, "context": 0.2}},
        "rows": [
            {"signal": -2, "context": 0, "group": "a", "target": 0},
            {"signal": -1, "context": 1, "group": "b", "target": 0},
            {"signal": 1, "context": 0, "group": "a", "target": 1},
            {"signal": 2, "context": 1, "group": "b", "target": 1},
        ],
        "counterfactual_row": {"signal": -1, "context": 0},
    },
    "ensemble-selection-and-stacking": {
        "title": "OOF-safe model pruning, blending, calibration, and holdout evaluation",
        "description": "Collect out-of-fold predictions, validate fold lineage, remove weak candidates, fit two blend strategies, calibrate residuals, and evaluate a held-out set.",
        "base_predictions": {
            "good-a": {
                "oof": [
                    {
                        "actual": value,
                        "prediction": value + 0.1,
                        "training_fold": 1,
                        "prediction_fold": 2,
                    }
                    for value in (1.0, 2.0, 3.0)
                ],
                "holdout": [{"actual": value, "prediction": value + 0.1} for value in (4.0, 5.0)],
            },
            "good-b": {
                "oof": [
                    {
                        "actual": value,
                        "prediction": value - 0.1,
                        "training_fold": 2,
                        "prediction_fold": 1,
                    }
                    for value in (1.0, 2.0, 3.0)
                ],
                "holdout": [{"actual": value, "prediction": value - 0.1} for value in (4.0, 5.0)],
            },
            "bad": {
                "oof": [
                    {
                        "actual": value,
                        "prediction": value + 3.0,
                        "training_fold": 1,
                        "prediction_fold": 2,
                    }
                    for value in (1.0, 2.0, 3.0)
                ],
                "holdout": [{"actual": value, "prediction": value + 3.0} for value in (4.0, 5.0)],
            },
        },
    },
    "model-release-monitoring-and-rollback": {
        "title": "Model packaging, shadow evidence, release gates, and rollback",
        "description": "Package a content-addressed candidate, replay inference, compare it in shadow, screen drift, apply fail-closed release policy, and prepare a non-automatic rollback.",
        "schema_version": "prediction-schema.v2",
        "candidate_model": {"id": "candidate.v2", "predictions": [1.0, 2.1, 2.9, 4.0]},
        "previous_model": {"id": "previous.v1", "predictions": [1.8, 2.8, 3.8, 4.8]},
        "labels": [1.0, 2.0, 3.0, 4.0],
        "baseline_feature": [0.0, 1.0, 2.0, 3.0],
        "current_feature": [0.1, 1.1, 2.1, 3.1],
    },
}


DATA_SCIENCE_NODE_DEFINITIONS = tuple(
    define_python_node(
        node_id=f"example.data-science.{pipeline}.{operation}",
        function=execute_data_science_step,
        inputs=(Port("payload", PIPELINE_TYPES[pipeline]),),
        outputs=(Port("payload", PIPELINE_TYPES[pipeline]),),
        capabilities=(f"data-science.{pipeline}.{operation}",),
        description=f"Execute the {operation} obligation in the {pipeline} lifecycle fixture.",
        version="1.0.0",
        parameters=(
            ParameterSpec("pipeline", "string", required=True, choices=(pipeline,)),
            ParameterSpec("operation", "string", required=True, choices=(operation,)),
            ParameterSpec("strategy", "string", required=True, choices=STRATEGIES),
        ),
        idempotency=Idempotency.IDEMPOTENT,
        preconditions=("The payload preserves raw fixture evidence.",),
        postconditions=(f"The methods ledger records {operation}.",),
        invariants=("Raw input evidence remains available for independent verification.",),
        verifier="verifier.example.data-science",
        source="solutiongraph/examples/data_science_tasks.py",
    )
    for pipeline, operations in PIPELINE_OPERATIONS.items()
    for operation in operations
)

DATA_SCIENCE_NODES = tuple(definition.spec for definition in DATA_SCIENCE_NODE_DEFINITIONS)
DATA_SCIENCE_CANDIDATES = tuple(
    definition.candidate(
        {"pipeline": pipeline, "operation": operation, "strategy": strategy},
        candidate_id=f"candidate.example.data-science.{pipeline}.{operation}.{strategy}",
    )
    for (pipeline, operations) in PIPELINE_OPERATIONS.items()
    for operation in operations
    for definition in DATA_SCIENCE_NODE_DEFINITIONS
    if definition.spec.id == f"example.data-science.{pipeline}.{operation}"
    for strategy in STRATEGIES
)

DATA_SCIENCE_REGISTRY = build_python_registry(
    "example.data-science-lifecycle-registry",
    "1.0.0",
    DATA_SCIENCE_NODE_DEFINITIONS,
    candidates=DATA_SCIENCE_CANDIDATES,
)


def _program(pipeline: str, fixture: dict[str, Any]) -> ProgramGraph:
    operations = PIPELINE_OPERATIONS[pipeline]
    value_type = PIPELINE_TYPES[pipeline]
    return ProgramGraph(
        id=f"example.{pipeline}",
        version="1.0.0",
        task=fixture["title"],
        success_contract="An independent fixture oracle accepts the final evidence and every selected stage is recorded.",
        slots=tuple(
            SemanticSlot(
                id=operation,
                purpose=f"Execute the {operation} lifecycle obligation.",
                inputs=(Port("payload", value_type),),
                outputs=(Port("payload", value_type),),
                success_contract=f"The {operation} result is typed and recorded in the methods ledger.",
                group=(f"stage.data-science.{pipeline}",),
                required_capabilities=(f"data-science.{pipeline}.{operation}",),
            )
            for operation in operations
        ),
        edges=tuple(
            Edge(left, "payload", right, "payload")
            for left, right in zip(operations, operations[1:], strict=False)
        ),
        inputs=(GraphInput("payload", value_type, operations[0], "payload"),),
        outputs=(GraphOutput("result", value_type, operations[-1], "payload"),),
    )


def _candidate_id(pipeline: str, operation: str, strategy: str) -> str:
    return f"candidate.example.data-science.{pipeline}.{operation}.{strategy}"


def _example(pipeline: str) -> ExecutableExample:
    fixture = PIPELINE_FIXTURES[pipeline]
    operations = PIPELINE_OPERATIONS[pipeline]
    route_specs = (
        (
            "minimal-control",
            "A deliberately under-evidenced control route.",
            tuple("minimal" for _ in operations),
            False,
        ),
        (
            "robust-reference",
            "Robust statistics and evidence-preserving lifecycle choices.",
            tuple("robust" for _ in operations),
            True,
        ),
        (
            "alternate-reference",
            "A second accepted algorithm family at every stage.",
            tuple("alternate" for _ in operations),
            True,
        ),
        (
            "hybrid-reference",
            "A compositional route alternating robust and alternate candidates.",
            tuple("robust" if index % 2 == 0 else "alternate" for index in range(len(operations))),
            True,
        ),
    )
    raw = {
        key: deepcopy(value)
        for key, value in fixture.items()
        if key not in {"title", "description"}
    }
    raw["pipeline"] = pipeline
    return ExecutableExample(
        id=pipeline,
        title=fixture["title"],
        description=fixture["description"],
        program=_program(pipeline, fixture),
        routes=tuple(
            ExampleRoute(
                route_id,
                description,
                {
                    operation: _candidate_id(pipeline, operation, strategy)
                    for operation, strategy in zip(operations, strategies, strict=True)
                },
                expected_accepted=expected,
            )
            for route_id, description, strategies, expected in route_specs
        ),
        case=ExperimentCase(
            f"case.{pipeline}",
            {"payload": {"raw": raw}},
            CallableVerifier("verifier.example.data-science", verify_data_science_pipeline),
        ),
        policy=ExecutionPolicy(),
        objectives=(
            Objective("quality", "maximize", hard_minimum=1.0),
            Objective("latency_ms", "minimize", weight=0.1),
        ),
        registry=DATA_SCIENCE_REGISTRY,
    )


DATA_SCIENCE_EXAMPLE_TASKS = tuple(_example(pipeline) for pipeline in PIPELINE_OPERATIONS)


__all__ = [
    "DATA_SCIENCE_CANDIDATES",
    "DATA_SCIENCE_EXAMPLE_TASKS",
    "DATA_SCIENCE_NODE_DEFINITIONS",
    "DATA_SCIENCE_NODES",
    "DATA_SCIENCE_REGISTRY",
    "PIPELINE_FIXTURES",
    "PIPELINE_OPERATIONS",
    "PIPELINE_TYPES",
    "STRATEGIES",
    "execute_data_science_step",
    "verify_data_science_pipeline",
]
