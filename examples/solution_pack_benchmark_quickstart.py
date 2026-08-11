"""Run one complete portable task/solution-pack benchmark locally.

This example deliberately uses a bundled transparent mechanism fixture. Replace
its cases and oracle with representative, licensed, independently evaluated data
before making domain-performance claims.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from solutiongraph.benchmark_library import get_benchmark
from solutiongraph.benchmarking import BenchmarkRunner, write_benchmark_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/solution-pack-quickstart"),
    )
    parser.add_argument(
        "--runtime",
        choices=("in-process", "subprocess"),
        default="in-process",
    )
    args = parser.parse_args()

    bundle = get_benchmark("benchmark.stdlib-data-quality")
    problems = bundle.validate()
    if problems:
        raise SystemExit("invalid bundled closure: " + "; ".join(problems))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = BenchmarkRunner().run(
        bundle.definition,
        runtime=args.runtime,
        artifact_root=args.output_dir / "artifacts",
    )
    json_path = args.output_dir / "benchmark-report.json"
    html_path = args.output_dir / "benchmark-report.html"
    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_benchmark_report(report, html_path)

    print(f"solution pack: {bundle.solution_pack.id}")
    print(f"closure digest: {bundle.solution_pack.digest}")
    print(f"suite: {report.suite.id}")
    print(f"claim scope: {report.suite.claim_scope}")
    for arm in report.arm_results:
        print(
            f"{arm.arm_id}: {arm.status}; "
            f"plans={arm.evaluated_plan_count}/{arm.route_count_upper_bound}; "
            f"accepted={arm.accepted_runs}/{arm.champion_run_count}; "
            f"holdout={arm.holdout_confirmed}; "
            f"optimality={arm.optimality_proven}"
        )
    print(f"JSON evidence: {json_path}")
    print(f"HTML projection: {html_path}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
