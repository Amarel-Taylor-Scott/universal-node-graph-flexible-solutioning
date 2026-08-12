"""Mini competition-style regression, classification, and forecasting tasks."""

from __future__ import annotations

from math import exp, sqrt
from statistics import median
from typing import Any

from solutiongraph.agent_bench.tasks.common import (
    CaseEvaluation,
    TaskCaseData,
    make_bundle,
)


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        if abs(augmented[column][column]) < 1e-12:
            augmented[column][column] += 1e-8
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                value - factor * basis
                for value, basis in zip(augmented[row], augmented[column], strict=True)
            ]
    return [augmented[index][-1] for index in range(size)]


def solve_tabular_regression(payload: dict[str, Any]) -> dict[str, Any]:
    features = tuple(payload["features"])
    rows = payload["train"]
    design = [[1.0, *(float(row[name]) for name in features)] for row in rows]
    target = [float(row[payload["target"]]) for row in rows]
    width = len(features) + 1
    gram = [
        [sum(row[left] * row[right] for row in design) for right in range(width)]
        for left in range(width)
    ]
    rhs = [sum(row[index] * value for row, value in zip(design, target, strict=True)) for index in range(width)]
    coefficients = _solve_linear_system(gram, rhs)
    predictions = []
    for row in payload["test"]:
        values = [1.0, *(float(row[name]) for name in features)]
        predictions.append(round(sum(a * b for a, b in zip(coefficients, values, strict=True)), 6))
    return {"predictions": predictions}


def regression_oracle(
    _payload: dict[str, Any],
    candidate: dict[str, Any],
    expected: dict[str, Any],
) -> CaseEvaluation:
    predictions = candidate.get("predictions") if isinstance(candidate, dict) else None
    targets = expected["targets"]
    if not isinstance(predictions, list) or len(predictions) != len(targets):
        return CaseEvaluation(False, 0.0, (("rmse", 1_000_000.0),), ("prediction shape mismatch",))
    try:
        values = [float(value) for value in predictions]
    except (TypeError, ValueError):
        return CaseEvaluation(False, 0.0, (("rmse", 1_000_000.0),), ("predictions must be numeric",))
    rmse = sqrt(sum((value - target) ** 2 for value, target in zip(values, targets, strict=True)) / len(targets))
    accepted = rmse <= float(expected["maximum_rmse"])
    return CaseEvaluation(
        accepted,
        1.0 / (1.0 + rmse),
        (("rmse", rmse),),
        () if accepted else ("RMSE exceeds the case threshold",),
    )


_REGRESSION_CASES = (
    TaskCaseData(
        "agent-case.regression.public",
        "development",
        {
            "features": ["x", "z"],
            "target": "y",
            "train": [
                {"x": 0, "z": 1, "y": 1.5},
                {"x": 1, "z": 0, "y": 3.0},
                {"x": 2, "z": 1, "y": 5.5},
                {"x": 3, "z": 0, "y": 7.0},
                {"x": 4, "z": 1, "y": 9.5},
            ],
            "test": [{"x": 5, "z": 0}, {"x": 6, "z": 1}],
        },
        {"targets": [11.0, 13.5], "maximum_rmse": 0.05},
        True,
        ("mini-kaggle",),
    ),
    TaskCaseData(
        "agent-case.regression.holdout-a",
        "holdout",
        {
            "features": ["a", "b"],
            "target": "target",
            "train": [
                {"a": -2, "b": 0, "target": -5},
                {"a": -1, "b": 2, "target": -1},
                {"a": 0, "b": 1, "target": 0},
                {"a": 1, "b": 3, "target": 4},
                {"a": 2, "b": -1, "target": 2},
                {"a": 3, "b": 2, "target": 7},
            ],
            "test": [{"a": 4, "b": 0}, {"a": -3, "b": 1}],
        },
        {"targets": [7.0, -6.0], "maximum_rmse": 0.1},
        False,
    ),
    TaskCaseData(
        "agent-case.regression.holdout-b",
        "stress",
        {
            "features": ["u"],
            "target": "v",
            "train": [{"u": value, "v": 2.5 - 0.75 * value} for value in range(-3, 5)],
            "test": [{"u": 10}, {"u": -8}],
        },
        {"targets": [-5.0, 8.5], "maximum_rmse": 0.1},
        False,
    ),
)

TABULAR_REGRESSION = make_bundle(
    task_id="agent-task.tabular-regression",
    title="Mini Kaggle-style tabular regression",
    summary="Fit a general numeric regression pipeline and emit submission-shaped predictions.",
    instructions=(
        "Use only training labels, fit a deterministic linear model with an intercept over the named "
        "numeric features, and return one finite prediction per test row in original order. Do not "
        "hard-code the public coefficients or inspect evaluator files."
    ),
    input_contract="Named numeric features, a target name, labeled train rows, and unlabeled test rows.",
    output_contract="An object containing exactly one ordered numeric predictions array.",
    success_contract="The sealed-case RMSE is at or below each predeclared threshold and the shape is exact.",
    categories=("ml.regression", "ml.tabular", "benchmark.kaggle-style"),
    template_id="template.kaggle-tabular",
    stages=("Validate schema", "Split roles", "Fit", "Predict", "Validate submission", "Score"),
    cases=_REGRESSION_CASES,
    reference_solver=solve_tabular_regression,
    oracle=regression_oracle,
    score_metric="rmse",
    score_direction="minimize",
    acceptance_threshold=0.1,
    allowed_imports=("math", "statistics", "typing"),
    extra_context_sources=("DATA_SCIENCE_AI_ML_PIPELINE_EXAMPLES.md",),
)


def solve_imbalanced_classification(payload: dict[str, Any]) -> dict[str, Any]:
    feature = payload["feature"]
    target = payload["target"]
    positives = [float(row[feature]) for row in payload["train"] if int(row[target]) == 1]
    negatives = [float(row[feature]) for row in payload["train"] if int(row[target]) == 0]
    positive_mean = sum(positives) / len(positives)
    negative_mean = sum(negatives) / len(negatives)
    threshold = (positive_mean + negative_mean) / 2.0
    orientation = 1.0 if positive_mean >= negative_mean else -1.0
    scale = max(0.25, abs(positive_mean - negative_mean) / 2.0)
    probabilities: list[float] = []
    labels: list[int] = []
    for row in payload["test"]:
        margin = orientation * (float(row[feature]) - threshold) / scale
        probability = 1.0 / (1.0 + exp(-margin))
        probabilities.append(round(probability, 6))
        labels.append(int(probability >= 0.5))
    return {"labels": labels, "probabilities": probabilities}


def classification_oracle(
    _payload: dict[str, Any],
    candidate: dict[str, Any],
    expected: dict[str, Any],
) -> CaseEvaluation:
    labels = candidate.get("labels") if isinstance(candidate, dict) else None
    probabilities = candidate.get("probabilities") if isinstance(candidate, dict) else None
    truth = expected["labels"]
    if (
        not isinstance(labels, list)
        or not isinstance(probabilities, list)
        or len(labels) != len(truth)
        or len(probabilities) != len(truth)
    ):
        return CaseEvaluation(False, 0.0, (("minority_f1", 0.0),), ("classification output shape mismatch",))
    try:
        predicted = [int(value) for value in labels]
        probs = [float(value) for value in probabilities]
    except (TypeError, ValueError):
        return CaseEvaluation(False, 0.0, (("minority_f1", 0.0),), ("labels/probabilities have invalid types",))
    if any(value not in (0, 1) for value in predicted) or any(not 0 <= value <= 1 for value in probs):
        return CaseEvaluation(False, 0.0, (("minority_f1", 0.0),), ("labels or probabilities are outside their domains",))
    tp = sum(left == right == 1 for left, right in zip(predicted, truth, strict=True))
    fp = sum(left == 1 and right == 0 for left, right in zip(predicted, truth, strict=True))
    fn = sum(left == 0 and right == 1 for left, right in zip(predicted, truth, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accepted = f1 >= expected["minimum_f1"] and recall >= expected["minimum_recall"]
    return CaseEvaluation(
        accepted,
        f1,
        (("minority_f1", f1), ("minority_recall", recall)),
        () if accepted else ("minority-class gates were not met",),
    )


_CLASSIFICATION_CASES = (
    TaskCaseData(
        "agent-case.classification.public",
        "development",
        {
            "feature": "risk",
            "target": "label",
            "train": [
                *[{"risk": value, "label": 0} for value in (0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5)],
                {"risk": 0.8, "label": 1},
                {"risk": 0.9, "label": 1},
            ],
            "test": [{"risk": 0.15}, {"risk": 0.75}, {"risk": 0.95}, {"risk": 0.4}],
        },
        {"labels": [0, 1, 1, 0], "minimum_f1": 0.95, "minimum_recall": 1.0},
        True,
    ),
    TaskCaseData(
        "agent-case.classification.holdout-a",
        "holdout",
        {
            "feature": "signal",
            "target": "outcome",
            "train": [
                *[{"signal": value, "outcome": 0} for value in (10, 11, 12, 13, 14, 15, 16)],
                {"signal": 3, "outcome": 1},
                {"signal": 4, "outcome": 1},
            ],
            "test": [{"signal": 2}, {"signal": 12}, {"signal": 5}, {"signal": 18}],
        },
        {"labels": [1, 0, 1, 0], "minimum_f1": 0.95, "minimum_recall": 1.0},
        False,
    ),
    TaskCaseData(
        "agent-case.classification.holdout-b",
        "stress",
        {
            "feature": "score",
            "target": "flag",
            "train": [
                *[{"score": value, "flag": 0} for value in (-5, -4, -3, -2, -1, 0, 1, 2)],
                {"score": 6, "flag": 1},
                {"score": 7, "flag": 1},
            ],
            "test": [{"score": -2}, {"score": 5.5}, {"score": 9}],
        },
        {"labels": [0, 1, 1], "minimum_f1": 0.95, "minimum_recall": 1.0},
        False,
    ),
)

IMBALANCED_CLASSIFICATION = make_bundle(
    task_id="agent-task.imbalanced-classification",
    title="Imbalanced binary classification",
    summary="Produce probability-bearing predictions that protect the minority class.",
    instructions=(
        "Learn the direction and threshold from the labeled training rows; emit one binary label and "
        "probability per test row. The evaluator gates minority F1 and recall, so a majority-only model "
        "cannot pass. Preserve input order and use no third-party dependencies."
    ),
    input_contract="One named numeric feature, a binary target, labeled train rows, and test rows.",
    output_contract="Parallel labels and probabilities arrays in original test-row order.",
    success_contract="Probability domains, output shape, minority F1, and minority recall all pass.",
    categories=("ml.classification", "ml.imbalanced", "ml.calibration"),
    template_id="template.kaggle-tabular",
    stages=("Profile balance", "Fit direction", "Calibrate score", "Choose threshold", "Predict", "Slice-evaluate"),
    cases=_CLASSIFICATION_CASES,
    reference_solver=solve_imbalanced_classification,
    oracle=classification_oracle,
    score_metric="minority_f1",
    acceptance_threshold=0.95,
    allowed_imports=("math", "statistics", "typing"),
    extra_context_sources=("DATA_SCIENCE_AI_ML_PIPELINE_EXAMPLES.md",),
)


def solve_time_series_forecast(payload: dict[str, Any]) -> dict[str, Any]:
    values = [float(row["value"]) for row in payload["observations"]]
    differences = [right - left for left, right in zip(values, values[1:], strict=False)]
    recent = differences[-min(5, len(differences)) :] if differences else [0.0]
    slope = median(recent)
    last = values[-1]
    forecasts = [round(last + slope * step, 6) for step in range(1, int(payload["horizon"]) + 1)]
    return {"forecasts": forecasts, "method": "median_recent_difference"}


def forecast_oracle(
    _payload: dict[str, Any],
    candidate: dict[str, Any],
    expected: dict[str, Any],
) -> CaseEvaluation:
    forecasts = candidate.get("forecasts") if isinstance(candidate, dict) else None
    targets = expected["targets"]
    if not isinstance(forecasts, list) or len(forecasts) != len(targets):
        return CaseEvaluation(False, 0.0, (("mae", 1_000_000.0),), ("forecast shape mismatch",))
    try:
        values = [float(value) for value in forecasts]
    except (TypeError, ValueError):
        return CaseEvaluation(False, 0.0, (("mae", 1_000_000.0),), ("forecasts must be numeric",))
    mae = sum(abs(value - target) for value, target in zip(values, targets, strict=True)) / len(targets)
    accepted = mae <= expected["maximum_mae"]
    return CaseEvaluation(accepted, 1.0 / (1.0 + mae), (("mae", mae),), () if accepted else ("MAE exceeds threshold",))


def _series(start: str, values: list[float]) -> list[dict[str, Any]]:
    return [{"time": f"{start}-{index + 1:02d}", "value": value} for index, value in enumerate(values)]


_FORECAST_CASES = (
    TaskCaseData(
        "agent-case.forecast.public",
        "development",
        {"observations": _series("2026-01", [10, 12, 14, 16, 18, 20]), "horizon": 3},
        {"targets": [22, 24, 26], "maximum_mae": 0.01},
        True,
    ),
    TaskCaseData(
        "agent-case.forecast.holdout-a",
        "holdout",
        {"observations": _series("2026-02", [30, 28.5, 27, 25.5, 24, 22.5]), "horizon": 2},
        {"targets": [21, 19.5], "maximum_mae": 0.01},
        False,
    ),
    TaskCaseData(
        "agent-case.forecast.holdout-b",
        "stress",
        {"observations": _series("2026-03", [4, 5, 6, 7, 8, 9, 10]), "horizon": 4},
        {"targets": [11, 12, 13, 14], "maximum_mae": 0.01},
        False,
    ),
)

TIME_SERIES_FORECAST = make_bundle(
    task_id="agent-task.time-series-forecast",
    title="Leakage-safe time-series forecast",
    summary="Forecast an ordered horizon without shuffle or future-label access.",
    instructions=(
        "Treat observations as chronological, estimate a robust recent trend using past values only, "
        "and forecast the requested horizon in order. Return the method label and exact forecast length."
    ),
    input_contract="Chronologically ordered time/value observations and a positive forecast horizon.",
    output_contract="An ordered numeric forecasts array and a method label.",
    success_contract="No future labels are exposed; shape is exact and sealed-case MAE meets the gate.",
    categories=("ml.forecasting", "time.validation", "ml.backtesting"),
    template_id="template.time-series-forecasting",
    stages=("Validate chronology", "Measure trend", "Select window", "Forecast", "Check horizon", "Score MAE"),
    cases=_FORECAST_CASES,
    reference_solver=solve_time_series_forecast,
    oracle=forecast_oracle,
    score_metric="mae",
    score_direction="minimize",
    acceptance_threshold=0.01,
    allowed_imports=("statistics", "math", "typing"),
    extra_context_sources=("DATA_SCIENCE_AI_ML_PIPELINE_EXAMPLES.md",),
)


ML_TASKS = (TABULAR_REGRESSION, IMBALANCED_CLASSIFICATION, TIME_SERIES_FORECAST)

__all__ = [
    "IMBALANCED_CLASSIFICATION",
    "ML_TASKS",
    "TABULAR_REGRESSION",
    "TIME_SERIES_FORECAST",
    "classification_oracle",
    "forecast_oracle",
    "regression_oracle",
    "solve_imbalanced_classification",
    "solve_tabular_regression",
    "solve_time_series_forecast",
]
