#!/usr/bin/env python3
"""Run a cold start, learn immutable history, reuse it, then study a graph mutation."""

from __future__ import annotations

import json
from dataclasses import replace

from solutiongraph.examples.control_mutation_experiment import (
    CONTROL_MUTATION_CASE,
    control_mutation_experiment_spec,
)
from solutiongraph.examples.intelligent_solutioning import example_solution_request
from solutiongraph.graph_experiments import GraphExperimentRunner
from solutiongraph.solutioning import TaskSolutionEngine
from solutiongraph.studies import ExperimentStudyRunner, StudyDesign


def main() -> None:
    engine = TaskSolutionEngine()
    cold_request = example_solution_request("data-cleanup", effort=1)
    cold = engine.solve(cold_request)
    memory_update = engine.learn(cold_request, cold)

    warm_request = replace(
        cold_request,
        id="solution.example.data-cleanup-warm",
        historical_memory=memory_update.memory,
    )
    warm_binding = engine.bind(warm_request)
    warm = engine.execute(warm_request, warm_binding)

    graph_report = GraphExperimentRunner().run(control_mutation_experiment_spec())
    candidate_digests = tuple(
        item.plan_digest
        for item in graph_report.comparisons
        if item.plan_digest != graph_report.control_plan_digest
    )
    study = ExperimentStudyRunner().analyze(
        StudyDesign(
            id="study.control-mutation-paired",
            control_plan_digest=graph_report.control_plan_digest,
            candidate_plan_digests=candidate_digests,
            objectives=graph_report.spec.objectives,
            task_case_ids=(CONTROL_MUTATION_CASE.id,),
            minimum_pairs=1,
            bootstrap_resamples=500,
            practical_effect_thresholds=(("quality", 0.01),),
        ),
        graph_report.ledger,
    )

    print(
        json.dumps(
            {
                "cold": {
                    "status": cold.status,
                    "evaluated_plans": len(cold.solver.plans),
                    "historical_recommendations": len(
                        cold.binding.initialization.recommendations
                    ),
                },
                "memory_update": {
                    "episodes": len(memory_update.memory.episodes),
                    "digest": memory_update.memory.digest,
                },
                "warm": {
                    "status": warm.status,
                    "historical_recommendations": len(
                        warm.binding.initialization.recommendations
                    ),
                    "starting_lanes": [
                        item.source_lane for item in warm.binding.initialization.starts
                    ],
                    "negative_transfer": warm.negative_transfer.to_dict(),
                },
                "mutation_study": {
                    "status": study.status,
                    "recommended_plan_digests": list(study.recommended_plan_digests),
                    "arm_verdicts": {
                        arm.candidate_plan_digest: arm.verdict for arm in study.arms
                    },
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
