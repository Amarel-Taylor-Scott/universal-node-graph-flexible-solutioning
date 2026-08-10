"""Receipt-producing experiment orchestration over already compiled routes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from solutiongraph.artifacts import ArtifactStore, MemoryArtifactStore
from solutiongraph.evidence import (
    EvidenceLedger,
    ExperimentDesign,
    RouteAggregate,
    pareto_front,
)
from solutiongraph.executor import (
    ExecutionPolicy,
    ReferenceExecutor,
    Verifier,
)
from solutiongraph.model import AdmittedSpace, FrozenPlan, ProgramGraph, Registry


@dataclass(frozen=True)
class ExperimentCase:
    """One immutable task case with its independent acceptance oracle."""

    id: str
    inputs: Mapping[str, Any]
    verifier: Verifier


@dataclass(frozen=True)
class ExperimentResult:
    design: ExperimentDesign
    ledger: EvidenceLedger
    aggregates: tuple[RouteAggregate, ...]
    pareto_plan_digests: tuple[str, ...]
    holdout_receipt_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.design.id,
            "scheduled_runs": self.design.scheduled_runs,
            "completed_runs": len(self.ledger.receipts),
            "holdout_receipt_ids": list(self.holdout_receipt_ids),
            "pareto_plan_digests": list(self.pareto_plan_digests),
            "aggregates": [
                {
                    "plan_digest": item.plan_digest,
                    "runs": item.runs,
                    "accepted_runs": item.accepted_runs,
                    "acceptance_rate": item.acceptance_rate,
                    "metric_means": dict(item.metric_means),
                    "metric_variances": dict(item.metric_variances),
                    "failure_classes": dict(item.failure_classes),
                }
                for item in self.aggregates
            ],
            "receipts": [receipt.to_dict() for receipt in self.ledger.receipts],
        }


class ExperimentRunner:
    """Run a declared plan/case/seed matrix without changing route validity."""

    def __init__(self, executor: ReferenceExecutor | None = None) -> None:
        self.executor = executor or ReferenceExecutor()

    def run(
        self,
        design: ExperimentDesign,
        *,
        plans: Mapping[str, FrozenPlan],
        cases: Mapping[str, ExperimentCase],
        program: ProgramGraph,
        registry: Registry,
        space: AdmittedSpace,
        policy: ExecutionPolicy,
        artifact_store_factory: Callable[[], ArtifactStore] | None = None,
        belief_revision: str = "",
    ) -> ExperimentResult:
        problems = design.validate()
        if problems:
            raise ValueError("invalid experiment design: " + "; ".join(problems))
        missing_plans = sorted(set(design.plan_digests) - set(plans))
        missing_cases = sorted(set(design.task_case_ids) - set(cases))
        if missing_plans:
            raise ValueError("missing experiment plans: " + ", ".join(missing_plans))
        if missing_cases:
            raise ValueError("missing experiment cases: " + ", ".join(missing_cases))
        artifact_store_factory = artifact_store_factory or MemoryArtifactStore

        ledger = EvidenceLedger()
        holdout_receipts: list[str] = []
        for case_id in design.task_case_ids:
            case = cases[case_id]
            for plan_digest in design.plan_digests:
                plan = plans[plan_digest]
                for seed in design.seeds:
                    for repetition in range(1, design.repetitions + 1):
                        short_plan = plan.digest.removeprefix("sha256:")[:12]
                        run_id = (
                            f"run.{design.id}.{case_id}.{short_plan}."
                            f"seed-{seed}.rep-{repetition}"
                        )
                        result = self.executor.execute(
                            plan,
                            program,
                            registry,
                            space,
                            case.inputs,
                            task_case_id=case.id,
                            verifier=case.verifier,
                            policy=policy,
                            artifact_store=artifact_store_factory(),
                            seed=seed,
                            belief_revision=belief_revision,
                            run_id=run_id,
                        )
                        ledger = ledger.append(result.receipt)
                        if case_id in design.holdout_case_ids:
                            holdout_receipts.append(result.receipt.id)

        aggregates = ledger.aggregates()
        front = pareto_front(aggregates, design.objectives)
        return ExperimentResult(
            design=design,
            ledger=ledger,
            aggregates=aggregates,
            pareto_plan_digests=tuple(item.plan_digest for item in front),
            holdout_receipt_ids=tuple(holdout_receipts),
        )


__all__ = ["ExperimentCase", "ExperimentResult", "ExperimentRunner"]
