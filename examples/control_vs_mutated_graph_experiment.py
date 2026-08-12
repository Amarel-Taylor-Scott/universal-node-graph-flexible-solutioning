"""Run a fixed control graph beside one explicit topology mutation."""

from __future__ import annotations

import json

from solutiongraph.examples.control_mutation_experiment import (
    control_mutation_experiment_spec,
)
from solutiongraph.graph_experiments import GraphExperimentRunner


def main() -> None:
    report = GraphExperimentRunner().run(control_mutation_experiment_spec())
    summary = {
        "status": report.status,
        "total_cartesian_routes": report.search_report.total_cartesian_routes,
        "executed_plan_count": len(report.plans),
        "complete_grid_evaluated": report.complete_grid_evaluated,
        "control_plan_digest": report.control_plan_digest,
        "champion_plan_digest": report.champion_plan_digest,
        "champion_variant": next(
            item.variant_id
            for item in report.comparisons
            if item.plan_digest == report.champion_plan_digest
        ),
        "routes": [
            {
                "rank": item.rank,
                "role": item.role,
                "variant": item.variant_id,
                "accepted": item.acceptance_rate == 1.0,
                "quality": item.objective_means.get("quality"),
                "selection": dict(item.selection),
            }
            for item in report.comparisons
        ],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
