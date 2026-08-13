#!/usr/bin/env python3
"""Run the semantic question-bank and reversible shadow-repair example."""

from __future__ import annotations

from pathlib import Path

from solutiongraph.interrogation.engine import InterrogationEngine
from solutiongraph.interrogation.io import load_records
from solutiongraph.interrogation.reporting import write_report_bundle

ROOT = Path(__file__).parents[1]


def main() -> None:
    records = load_records(ROOT / "examples" / "data" / "dirty_organizations.json")
    report = InterrogationEngine().run(
        records,
        effort="E3",
        mapping_strategy="conservative",
        planning_strategy="risk-first",
        repair_strategy="safe-only",
        random_seed=17,
    )
    output = ROOT / ".artifacts" / "semantic-interrogation"
    paths = write_report_bundle(report, output)
    summary = report.summary()
    print(
        f"{report.id}: decision={report.verification.decision} "
        f"visible_questions={summary['question_count']} "
        f"findings={summary['finding_count_before']}->{summary['finding_count_after']} "
        f"repairs={summary['applied_operation_count']}"
    )
    for path in paths:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
