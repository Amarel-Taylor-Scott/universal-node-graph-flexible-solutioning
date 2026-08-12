#!/usr/bin/env python3
"""Normalize an explicit Kaggle-style manifest without fetching or submitting data."""

from __future__ import annotations

import json

from solutiongraph.benchmark_adapters import (
    ExternalBenchmarkRequest,
    get_benchmark_adapter,
)
from solutiongraph.evidence import Objective
from solutiongraph.model import Port, ValueType, sha256_digest
from solutiongraph.tasking import TaskCaseSpec, TaskOracle


def main() -> None:
    table = ValueType("example.kaggle.table")
    submission = ValueType("example.kaggle.submission")
    request = ExternalBenchmarkRequest(
        task_id="task.kaggle.example-regression",
        task_version="2026-08-12",
        title="Versioned tabular regression competition",
        intent="Train on the declared competition snapshot and emit a valid prediction table.",
        success_contract="Pass local submission validation and minimize the frozen RMSE evaluator.",
        inputs=(Port("training_table", table),),
        outputs=(Port("submission", submission),),
        oracle=TaskOracle(
            "oracle.kaggle.example-regression",
            "1.0.0",
            "statistical",
            sha256_digest("frozen-local-rmse-evaluator-v1"),
            "artifact://evaluators/example-rmse-v1",
            candidate_readable=False,
        ),
        objectives=(Objective("rmse", "minimize"),),
        cases=(
            TaskCaseSpec(
                "case.kaggle.example-regression.local-holdout",
                "holdout",
                sha256_digest("authorized-local-holdout-input-v1"),
                "artifact://cases/example-regression-local-holdout-v1",
            ),
        ),
        source_id="source.kaggle.example-regression",
        source_version="competition-rules-2026-08-12",
        source_uri="https://www.kaggle.com/competitions/example-regression",
        metadata=(
            ("benchmark.dataset-license", "competition-specific"),
            ("benchmark.data-version", "snapshot-2026-08-12"),
            ("benchmark.metric-implementation", "artifact://metrics/rmse-v1"),
            ("benchmark.leakage-rules", "local holdout is candidate-inaccessible"),
            ("benchmark.submission-format", "row_id,prediction"),
        ),
        external_requirements=(
            "Authorized competition data access is required outside this manifest.",
        ),
    )
    bundle = get_benchmark_adapter("adapter.kaggle").adapt(request)
    print(json.dumps(bundle.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
