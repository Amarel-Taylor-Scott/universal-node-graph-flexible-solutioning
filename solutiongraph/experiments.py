"""Receipt-producing experiment orchestration over already compiled routes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from solutiongraph.artifacts import ArtifactStore, MemoryArtifactStore
from solutiongraph.evidence import (
    EvidenceLedger,
    ExperimentDesign,
    RouteAggregate,
    RunReceipt,
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


class ReceiptSink(Protocol):
    """Durable destination invoked immediately after every completed run."""

    def append(self, *receipts: RunReceipt) -> Any: ...


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


@dataclass(frozen=True)
class ExperimentBundle:
    """Typed closure passed through experiment orchestration as one value.

    This is a quality-of-life API over the existing explicit objects.  It does
    not merge their identities or let experiment settings alter program,
    registry, admitted-space, or plan semantics.
    """

    design: ExperimentDesign
    plans: Mapping[str, FrozenPlan]
    cases: Mapping[str, ExperimentCase]
    program: ProgramGraph
    registry: Registry
    space: AdmittedSpace
    policy: ExecutionPolicy
    belief_revision: str = ""

    def validate(self) -> list[str]:
        problems = list(self.design.validate())
        missing_plans = sorted(set(self.design.plan_digests) - set(self.plans))
        missing_cases = sorted(set(self.design.task_case_ids) - set(self.cases))
        if missing_plans:
            problems.append("missing experiment plans: " + ", ".join(missing_plans))
        if missing_cases:
            problems.append("missing experiment cases: " + ", ".join(missing_cases))
        mismatched_plans = sorted(
            digest
            for digest in self.design.plan_digests
            if digest in self.plans and self.plans[digest].digest != digest
        )
        mismatched_cases = sorted(
            case_id
            for case_id in self.design.task_case_ids
            if case_id in self.cases and self.cases[case_id].id != case_id
        )
        if mismatched_plans:
            problems.append(
                "experiment plan keys do not match plan digests: "
                + ", ".join(mismatched_plans)
            )
        if mismatched_cases:
            problems.append(
                "experiment case keys do not match case ids: "
                + ", ".join(mismatched_cases)
            )
        if self.space.program_digest != self.program.digest:
            problems.append("admitted space does not match experiment program")
        if self.space.registry_digest != self.registry.digest:
            problems.append("admitted space does not match experiment registry")
        for digest in self.design.plan_digests:
            plan = self.plans.get(digest)
            if plan is None:
                continue
            if plan.program_digest != self.program.digest:
                problems.append(f"plan {digest} does not match experiment program")
            if plan.registry_digest != self.registry.digest:
                problems.append(f"plan {digest} does not match experiment registry")
            if plan.admitted_space_digest != self.space.digest:
                problems.append(f"plan {digest} does not match admitted space")
        problems.extend(self.policy.validate())
        return problems


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
        receipt_sink: ReceiptSink | None = None,
        belief_revision: str = "",
    ) -> ExperimentResult:
        return self.run_bundle(
            ExperimentBundle(
                design=design,
                plans=plans,
                cases=cases,
                program=program,
                registry=registry,
                space=space,
                policy=policy,
                belief_revision=belief_revision,
            ),
            artifact_store_factory=artifact_store_factory,
            receipt_sink=receipt_sink,
        )

    def run_bundle(
        self,
        bundle: ExperimentBundle,
        *,
        artifact_store_factory: Callable[[], ArtifactStore] | None = None,
        receipt_sink: ReceiptSink | None = None,
    ) -> ExperimentResult:
        """Execute a typed experiment bundle without a long pass-through list."""

        problems = bundle.validate()
        if problems:
            raise ValueError("invalid experiment bundle: " + "; ".join(problems))
        design = bundle.design
        artifact_store_factory = artifact_store_factory or MemoryArtifactStore

        ledger = EvidenceLedger()
        holdout_receipts: list[str] = []
        for case_id in design.task_case_ids:
            case = bundle.cases[case_id]
            for plan_digest in design.plan_digests:
                plan = bundle.plans[plan_digest]
                for seed in design.seeds:
                    for repetition in range(1, design.repetitions + 1):
                        short_plan = plan.digest.removeprefix("sha256:")[:12]
                        run_id = (
                            f"run.{design.id}.{case_id}.{short_plan}."
                            f"seed-{seed}.rep-{repetition}"
                        )
                        result = self.executor.execute(
                            plan,
                            bundle.program,
                            bundle.registry,
                            bundle.space,
                            case.inputs,
                            task_case_id=case.id,
                            verifier=case.verifier,
                            policy=bundle.policy,
                            artifact_store=artifact_store_factory(),
                            seed=seed,
                            belief_revision=bundle.belief_revision,
                            run_id=run_id,
                        )
                        if receipt_sink is not None:
                            receipt_sink.append(result.receipt)
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


__all__ = [
    "ExperimentBundle",
    "ExperimentCase",
    "ExperimentResult",
    "ExperimentRunner",
    "ReceiptSink",
]
