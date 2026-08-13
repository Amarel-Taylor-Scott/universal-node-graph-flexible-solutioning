"""Explicit local parallel allocation over immutable experiment bundles.

This module does not make the reference executor a distributed scheduler.  It
fans out independent run cells only when the caller supplies a fresh-executor
factory, preserves deterministic schedule order in the evidence ledger, and
serializes receipt-sink appends as soon as each run completes.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock

from solutiongraph.artifacts import ArtifactStore, MemoryArtifactStore
from solutiongraph.evidence import EvidenceLedger, RunReceipt, pareto_front
from solutiongraph.executor import ReferenceExecutor
from solutiongraph.experiments import (
    ExperimentBundle,
    ExperimentResult,
    ReceiptSink,
)


@dataclass(frozen=True)
class ParallelExperimentPolicy:
    max_parallel_runs: int = 4

    def validate(self) -> list[str]:
        return (
            ["max_parallel_runs must be a positive integer"]
            if isinstance(self.max_parallel_runs, bool) or self.max_parallel_runs <= 0
            else []
        )


@dataclass(frozen=True)
class ScheduledExperimentRun:
    index: int
    case_id: str
    plan_digest: str
    seed: int
    repetition: int
    run_id: str


def schedule_experiment(bundle: ExperimentBundle) -> tuple[ScheduledExperimentRun, ...]:
    problems = bundle.validate()
    if problems:
        raise ValueError("invalid experiment bundle: " + "; ".join(problems))
    scheduled: list[ScheduledExperimentRun] = []
    for case_id in bundle.design.task_case_ids:
        for plan_digest in bundle.design.plan_digests:
            for seed in bundle.design.seeds:
                for repetition in range(1, bundle.design.repetitions + 1):
                    short_plan = plan_digest.removeprefix("sha256:")[:12]
                    run_id = (
                        f"run.{bundle.design.id}.{case_id}.{short_plan}."
                        f"seed-{seed}.rep-{repetition}"
                    )
                    scheduled.append(
                        ScheduledExperimentRun(
                            index=len(scheduled),
                            case_id=case_id,
                            plan_digest=plan_digest,
                            seed=seed,
                            repetition=repetition,
                            run_id=run_id,
                        )
                    )
    if len(scheduled) != bundle.design.scheduled_runs:
        raise ValueError("experiment schedule does not match declared scheduled_runs")
    return tuple(scheduled)


class ParallelExperimentRunner:
    """Run independent local experiment cells with isolated executor instances."""

    def __init__(
        self,
        executor_factory: Callable[[], ReferenceExecutor],
        *,
        policy: ParallelExperimentPolicy | None = None,
    ) -> None:
        self.executor_factory = executor_factory
        self.policy = policy or ParallelExperimentPolicy()
        problems = self.policy.validate()
        if problems:
            raise ValueError("invalid parallel experiment policy: " + "; ".join(problems))

    def run_bundle(
        self,
        bundle: ExperimentBundle,
        *,
        artifact_store_factory: Callable[[], ArtifactStore] | None = None,
        receipt_sink: ReceiptSink | None = None,
    ) -> ExperimentResult:
        schedule = schedule_experiment(bundle)
        artifact_store_factory = artifact_store_factory or MemoryArtifactStore
        sink_lock = Lock()
        allocation_lock = Lock()
        executor_ids: set[int] = set()
        artifact_store_ids: set[int] = set()
        allocated_executors: list[ReferenceExecutor] = []
        allocated_artifact_stores: list[ArtifactStore] = []

        def execute(item: ScheduledExperimentRun) -> RunReceipt:
            with allocation_lock:
                executor = self.executor_factory()
                artifact_store = artifact_store_factory()
                if not isinstance(executor, ReferenceExecutor):
                    raise TypeError("executor_factory must return a ReferenceExecutor")
                if id(executor) in executor_ids:
                    raise ValueError(
                        "executor_factory must return a fresh executor for every run"
                    )
                if id(artifact_store) in artifact_store_ids:
                    raise ValueError(
                        "artifact_store_factory must return a fresh store for every run"
                    )
                executor_ids.add(id(executor))
                artifact_store_ids.add(id(artifact_store))
                # Retain allocations until the bundle completes so Python
                # cannot recycle object ids and create a false reuse signal.
                allocated_executors.append(executor)
                allocated_artifact_stores.append(artifact_store)
            case = bundle.cases[item.case_id]
            result = executor.execute(
                bundle.plans[item.plan_digest],
                bundle.program,
                bundle.registry,
                bundle.space,
                case.inputs,
                task_case_id=case.id,
                verifier=case.verifier,
                policy=bundle.policy,
                artifact_store=artifact_store,
                seed=item.seed,
                belief_revision=bundle.belief_revision,
                run_id=item.run_id,
            )
            if receipt_sink is not None:
                with sink_lock:
                    receipt_sink.append(result.receipt)
            return result.receipt

        futures: dict[int, Future[RunReceipt]] = {}
        with ThreadPoolExecutor(
            max_workers=self.policy.max_parallel_runs,
            thread_name_prefix="solutiongraph-experiment",
        ) as pool:
            for item in schedule:
                futures[item.index] = pool.submit(execute, item)
            receipts = tuple(futures[index].result() for index in range(len(schedule)))

        ledger = EvidenceLedger(receipts)
        aggregates = ledger.aggregates()
        front = pareto_front(aggregates, bundle.design.objectives)
        holdout_ids = set(bundle.design.holdout_case_ids)
        return ExperimentResult(
            design=bundle.design,
            ledger=ledger,
            aggregates=aggregates,
            pareto_plan_digests=tuple(item.plan_digest for item in front),
            holdout_receipt_ids=tuple(
                receipt.id
                for receipt in receipts
                if receipt.task_case_id in holdout_ids
            ),
        )


__all__ = [
    "ParallelExperimentPolicy",
    "ParallelExperimentRunner",
    "ScheduledExperimentRun",
    "schedule_experiment",
]
