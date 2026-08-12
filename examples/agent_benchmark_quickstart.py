#!/usr/bin/env python3
"""Run the dependency-free 10-task, 20-trial agent-benchmark smoke."""

from __future__ import annotations

import argparse
from pathlib import Path

from solutiongraph.agent_bench import (
    reference_agent_benchmark_suite,
    run_agent_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/agent-benchmark-smoke"),
        help="New directory for workspaces, receipts, diagrams, JSON, and HTML",
    )
    args = parser.parse_args()
    suite = reference_agent_benchmark_suite()
    result = run_agent_benchmark(suite, args.output_dir)
    print(
        f"{result.report.status}: {result.report.accepted_trials}/"
        f"{result.report.executed_trials} fixture trials accepted"
    )
    print(f"Report: {result.report_html}")
    print(f"Evidence: {result.report_json}")
    print(f"Journal: {result.receipt_journal}")
    print(
        "Claim boundary: this deterministic fixture validates transport and scoring; "
        "it does not measure an LLM or establish SolutionGraph efficacy."
    )
    return 0 if result.report.status == "benchmark.completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
