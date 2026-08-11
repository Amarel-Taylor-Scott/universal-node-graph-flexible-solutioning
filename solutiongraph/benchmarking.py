"""Repeatable benchmark suites and self-contained evidence reports.

Benchmarks compare explicit fixed routes and bounded solver profiles against
the same immutable task cases and oracle.  Bundled suites are mechanism
fixtures: they demonstrate the complete evidence path without making claims
about production datasets or third-party leaderboards.
"""

from __future__ import annotations

import html
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from solutiongraph.artifacts import ArtifactStore, FileArtifactStore, MemoryArtifactStore
from solutiongraph.compiler import Compiler
from solutiongraph.evidence import ExperimentDesign, RouteAggregate
from solutiongraph.executor import (
    CircuitBreaker,
    PythonRuntime,
    ReferenceExecutor,
    RuntimeRegistry,
)
from solutiongraph.experiments import ExperimentCase, ExperimentRunner, ReceiptSink
from solutiongraph.model import DIGEST_RE, ID_RE, FrozenPlan, sha256_digest
from solutiongraph.search import BeliefModel, CandidateWeight
from solutiongraph.solver import UniversalSolver, get_solver_profile
from solutiongraph.subprocess_runtime import SubprocessPythonRuntime
from solutiongraph.tasking import TaskCaseSpec, TaskContract

BENCHMARK_MODEL_VERSION = "0.1"
BENCHMARK_ARM_KINDS = ("fixed-route", "solver-profile")
BENCHMARK_CLAIM_SCOPES = (
    "mechanism-fixture",
    "internal-dataset",
    "public-benchmark",
    "production-shadow",
)


@dataclass(frozen=True)
class BenchmarkArm:
    """One explicitly allocated route-selection strategy."""

    id: str
    title: str
    description: str
    kind: str
    route_id: str = ""
    solver_profile: str = ""
    anchor_route_ids: tuple[str, ...] = ()

    def validate(self, path: str = "benchmark_arm") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a lowercase namespaced identifier")
        if not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.title and description must not be empty")
        if self.kind not in BENCHMARK_ARM_KINDS:
            problems.append(
                f"{path}.kind must be one of {', '.join(BENCHMARK_ARM_KINDS)}"
            )
        if self.kind == "fixed-route":
            if not self.route_id or self.solver_profile or self.anchor_route_ids:
                problems.append(
                    f"{path} fixed-route arms require route_id and no solver settings"
                )
        if self.kind == "solver-profile":
            if not self.solver_profile or self.route_id:
                problems.append(
                    f"{path} solver-profile arms require solver_profile and no route_id"
                )
            else:
                try:
                    get_solver_profile(self.solver_profile)
                except ValueError as exc:
                    problems.append(f"{path}.solver_profile: {exc}")
            if len(self.anchor_route_ids) != len(set(self.anchor_route_ids)):
                problems.append(f"{path}.anchor_route_ids must be unique")
            if any(not ID_RE.fullmatch(item) for item in self.anchor_route_ids):
                problems.append(f"{path}.anchor_route_ids must contain identifiers")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "kind": self.kind,
            "route_id": self.route_id,
            "solver_profile": self.solver_profile,
            "anchor_route_ids": list(self.anchor_route_ids),
        }


@dataclass(frozen=True)
class BenchmarkSuite:
    """Portable design for comparing search strategies on one stable task."""

    id: str
    version: str
    title: str
    description: str
    example_id: str
    task_contract_digest: str
    program_digest: str
    registry_digest: str
    task_case_digests: tuple[str, ...]
    arms: tuple[BenchmarkArm, ...]
    seeds: tuple[int, ...] = (0,)
    repetitions: int = 1
    holdout_case_ids: tuple[str, ...] = ()
    claim_scope: str = "mechanism-fixture"
    dataset_license: str = "CC0-1.0"
    source: str = ""
    notes: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "benchmark_suite") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a lowercase namespaced identifier")
        if not self.version.strip():
            problems.append(f"{path}.version must not be empty")
        for label, value in (
            ("title", self.title),
            ("description", self.description),
            ("example_id", self.example_id),
            ("dataset_license", self.dataset_license),
        ):
            if not value.strip():
                problems.append(f"{path}.{label} must not be empty")
        for label, digest in (
            ("task_contract_digest", self.task_contract_digest),
            ("program_digest", self.program_digest),
            ("registry_digest", self.registry_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be a sha256 digest")
        if not self.task_case_digests:
            problems.append(f"{path}.task_case_digests must not be empty")
        if any(not DIGEST_RE.fullmatch(item) for item in self.task_case_digests):
            problems.append(f"{path}.task_case_digests must contain sha256 digests")
        if len(self.task_case_digests) != len(set(self.task_case_digests)):
            problems.append(f"{path}.task_case_digests must be unique")
        arm_ids = [arm.id for arm in self.arms]
        if not self.arms:
            problems.append(f"{path}.arms must not be empty")
        if len(arm_ids) != len(set(arm_ids)):
            problems.append(f"{path}.arms ids must be unique")
        for index, arm in enumerate(self.arms):
            problems.extend(arm.validate(f"{path}.arms[{index}]"))
        if not self.seeds or len(self.seeds) != len(set(self.seeds)):
            problems.append(f"{path}.seeds must be nonempty and unique")
        if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in self.seeds):
            problems.append(f"{path}.seeds must contain integers")
        if isinstance(self.repetitions, bool) or self.repetitions <= 0:
            problems.append(f"{path}.repetitions must be a positive integer")
        if len(self.holdout_case_ids) != len(set(self.holdout_case_ids)):
            problems.append(f"{path}.holdout_case_ids must be unique")
        if any(not ID_RE.fullmatch(case_id) for case_id in self.holdout_case_ids):
            problems.append(f"{path}.holdout_case_ids must contain identifiers")
        if self.claim_scope not in BENCHMARK_CLAIM_SCOPES:
            problems.append(
                f"{path}.claim_scope must be one of {', '.join(BENCHMARK_CLAIM_SCOPES)}"
            )
        if any(not note.strip() for note in self.notes):
            problems.append(f"{path}.notes must not contain empty strings")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_model_version": BENCHMARK_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "example_id": self.example_id,
            "task_contract_digest": self.task_contract_digest,
            "program_digest": self.program_digest,
            "registry_digest": self.registry_digest,
            "task_case_digests": list(self.task_case_digests),
            "arms": [arm.to_dict() for arm in self.arms],
            "seeds": list(self.seeds),
            "repetitions": self.repetitions,
            "holdout_case_ids": list(self.holdout_case_ids),
            "claim_scope": self.claim_scope,
            "dataset_license": self.dataset_license,
            "source": self.source,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class BenchmarkDefinition:
    """Runtime binding for a portable suite and its local executable fixtures."""

    suite: BenchmarkSuite
    task_contract: TaskContract
    task_cases: tuple[TaskCaseSpec, ...]
    cases: tuple[ExperimentCase, ...]
    example: Any

    def validate(self) -> list[str]:
        problems = self.suite.validate()
        problems.extend(self.task_contract.validate())
        if self.suite.task_contract_digest != self.task_contract.digest:
            problems.append("suite task_contract_digest does not match task contract")
        if self.suite.program_digest != self.example.program.digest:
            problems.append("suite program_digest does not match executable program")
        if self.suite.registry_digest != self.example.registry.digest:
            problems.append("suite registry_digest does not match executable registry")
        if self.suite.example_id != self.example.id:
            problems.append("suite example_id does not match executable example")
        problems.extend(self.task_contract.validate_program(self.example.program))
        spec_ids = [item.id for item in self.task_cases]
        runtime_ids = [item.id for item in self.cases]
        if len(spec_ids) != len(set(spec_ids)) or len(runtime_ids) != len(set(runtime_ids)):
            problems.append("task case ids must be unique")
        if set(spec_ids) != set(runtime_ids):
            problems.append("portable task cases and runtime cases do not exactly match")
        if set(spec_ids) != set(self.task_contract.case_ids):
            problems.append("benchmark task cases do not exactly match task contract case_ids")
        if set(self.suite.holdout_case_ids) - set(spec_ids):
            problems.append("suite holdout cases are not present in task cases")
        if set(self.suite.task_case_digests) != {item.digest for item in self.task_cases}:
            problems.append("suite task_case_digests do not exactly match task cases")
        runtime_by_id = {item.id: item for item in self.cases}
        for index, spec in enumerate(self.task_cases):
            problems.extend(spec.validate(f"task_cases[{index}]"))
            runtime = runtime_by_id.get(spec.id)
            if runtime is not None:
                if spec.input_digest != sha256_digest(dict(runtime.inputs)):
                    problems.append(f"task case {spec.id} input_digest does not match inputs")
                if runtime.verifier.implementation_digest != self.task_contract.oracle.evaluator_digest:
                    problems.append(f"task case {spec.id} verifier does not match task oracle")
        route_ids = {route.id for route in self.example.routes}
        for arm in self.suite.arms:
            if arm.kind == "fixed-route" and arm.route_id not in route_ids:
                problems.append(
                    f"benchmark arm {arm.id} references unknown route {arm.route_id}"
                )
            unknown_anchors = sorted(set(arm.anchor_route_ids) - route_ids)
            if unknown_anchors:
                problems.append(
                    f"benchmark arm {arm.id} references unknown anchor routes: "
                    + ", ".join(unknown_anchors)
                )
        return problems


@dataclass(frozen=True)
class BenchmarkArmResult:
    arm_id: str
    kind: str
    status: str
    route_count_upper_bound: int
    evaluated_plan_count: int
    receipt_count: int
    champion_run_count: int
    accepted_runs: int
    acceptance_rate: float
    champion_plan_digest: str
    champion_selection: tuple[tuple[str, str], ...]
    fallback_plan_digests: tuple[str, ...]
    pareto_plan_digests: tuple[str, ...]
    objective_means: Mapping[str, float]
    objective_variances: Mapping[str, float]
    holdout_confirmed: bool
    optimality_proven: bool
    details: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "kind": self.kind,
            "status": self.status,
            "route_count_upper_bound": self.route_count_upper_bound,
            "evaluated_plan_count": self.evaluated_plan_count,
            "receipt_count": self.receipt_count,
            "champion_run_count": self.champion_run_count,
            "accepted_runs": self.accepted_runs,
            "acceptance_rate": self.acceptance_rate,
            "champion_plan_digest": self.champion_plan_digest,
            "champion_selection": dict(self.champion_selection),
            "fallback_plan_digests": list(self.fallback_plan_digests),
            "pareto_plan_digests": list(self.pareto_plan_digests),
            "objective_means": dict(self.objective_means),
            "objective_variances": dict(self.objective_variances),
            "holdout_confirmed": self.holdout_confirmed,
            "optimality_proven": self.optimality_proven,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class BenchmarkReport:
    suite: BenchmarkSuite
    task_contract: TaskContract
    runtime: str
    generated_at: str
    arm_results: tuple[BenchmarkArmResult, ...]
    problems: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        completed_states = {"completed", "completed-no-accepted-route"}
        return not self.problems and all(
            item.status in completed_states for item in self.arm_results
        )

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict(include_digest=False))

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        payload = {
            "benchmark_model_version": BENCHMARK_MODEL_VERSION,
            "ok": self.ok,
            "suite": self.suite.to_dict(),
            "suite_digest": self.suite.digest,
            "task_contract": self.task_contract.to_dict(),
            "task_contract_digest": self.task_contract.digest,
            "runtime": self.runtime,
            "generated_at": self.generated_at,
            "claim_scope": self.suite.claim_scope,
            "problems": list(self.problems),
            "arms": [item.to_dict() for item in self.arm_results],
        }
        if include_digest:
            payload["report_digest"] = self.digest
        return payload


class BenchmarkRunner:
    """Run every declared arm without changing task or graph semantics."""

    def run(
        self,
        definition: BenchmarkDefinition,
        *,
        runtime: str = "in-process",
        artifact_root: str | Path | None = None,
        receipt_sink: ReceiptSink | None = None,
    ) -> BenchmarkReport:
        problems = definition.validate()
        if problems:
            raise ValueError("invalid benchmark definition: " + "; ".join(problems))
        compiler = Compiler()
        space = compiler.admit(definition.example.program, definition.example.registry)
        cases = {case.id: case for case in definition.cases}
        artifact_factory = _artifact_factory(artifact_root)
        results: list[BenchmarkArmResult] = []
        for arm in definition.suite.arms:
            # Each allocation arm gets a fresh runtime state. Circuit-breaker
            # history is operational state and must not leak between controls.
            executor = _executor(runtime)
            if arm.kind == "fixed-route":
                results.append(
                    self._run_fixed(
                        definition,
                        arm,
                        executor,
                        compiler,
                        space,
                        cases,
                        artifact_factory,
                        receipt_sink,
                    )
                )
            else:
                results.append(
                    self._run_solver(
                        definition,
                        arm,
                        executor,
                        artifact_factory,
                        receipt_sink,
                    )
                )
        return BenchmarkReport(
            suite=definition.suite,
            task_contract=definition.task_contract,
            runtime=runtime,
            generated_at=datetime.now(timezone.utc).isoformat(),
            arm_results=tuple(results),
        )

    @staticmethod
    def _run_fixed(
        definition: BenchmarkDefinition,
        arm: BenchmarkArm,
        executor: ReferenceExecutor,
        compiler: Compiler,
        space: Any,
        cases: Mapping[str, ExperimentCase],
        artifact_factory: Callable[[], ArtifactStore],
        receipt_sink: ReceiptSink | None,
    ) -> BenchmarkArmResult:
        route = next(item for item in definition.example.routes if item.id == arm.route_id)
        plan = compiler.compile(
            definition.example.program,
            definition.example.registry,
            space,
            route.selection,
            fallbacks=route.fallback_map(),
        )
        design = ExperimentDesign(
            id=f"benchmark.{definition.suite.id}.{arm.id}",
            task_case_ids=tuple(case.id for case in definition.cases),
            plan_digests=(plan.digest,),
            seeds=definition.suite.seeds,
            repetitions=definition.suite.repetitions,
            objectives=definition.task_contract.objectives,
            control_plan_digest=plan.digest,
            holdout_case_ids=definition.suite.holdout_case_ids,
        )
        experiment = ExperimentRunner(executor).run(
            design,
            plans={plan.digest: plan},
            cases=cases,
            program=definition.example.program,
            registry=definition.example.registry,
            space=space,
            policy=definition.example.policy,
            artifact_store_factory=artifact_factory,
            receipt_sink=receipt_sink,
            belief_revision="benchmark.fixed-route",
        )
        aggregate = experiment.aggregates[0]
        return _arm_result_from_aggregate(
            arm,
            aggregate,
            plan,
            route_count_upper_bound=space.route_count_upper_bound,
            evaluated_plan_count=1,
            receipt_count=len(experiment.ledger.receipts),
            fallbacks=(),
            pareto=experiment.pareto_plan_digests,
            holdout_confirmed=all(
                receipt.accepted is True
                for receipt in experiment.ledger.receipts
                if receipt.task_case_id in definition.suite.holdout_case_ids
            ) if definition.suite.holdout_case_ids else True,
            optimality_proven=space.route_count_upper_bound == 1,
            details={
                "experiment": experiment.to_dict(),
                "allocation": "one declared fixed route; no search performed",
            },
        )

    @staticmethod
    def _run_solver(
        definition: BenchmarkDefinition,
        arm: BenchmarkArm,
        executor: ReferenceExecutor,
        artifact_factory: Callable[[], ArtifactStore],
        receipt_sink: ReceiptSink | None,
    ) -> BenchmarkArmResult:
        baseline = next(
            (route for route in definition.example.routes if route.id == "baseline"),
            definition.example.routes[0],
        )
        anchor_routes = tuple(
            route
            for route_id in arm.anchor_route_ids
            for route in definition.example.routes
            if route.id == route_id
        )
        suggested_beliefs = BeliefModel(
            revision=(
                "benchmark.suggested-"
                + sha256_digest(
                    [dict(route.selection) for route in anchor_routes]
                ).removeprefix("sha256:")[:16]
                if anchor_routes
                else "benchmark.cold-start"
            ),
            candidate_weights=tuple(
                CandidateWeight(slot_id, candidate_id, 6.0)
                for route in anchor_routes
                for slot_id, candidate_id in route.selection.items()
            ),
        )
        result = UniversalSolver(executor=executor).solve(
            definition.example.program,
            definition.example.registry,
            cases=definition.cases,
            objectives=definition.task_contract.objectives,
            policy=definition.example.policy,
            profile=replace(
                get_solver_profile(arm.solver_profile),
                seeds=definition.suite.seeds,
                repetitions=definition.suite.repetitions,
            ),
            beliefs=suggested_beliefs,
            baseline_selection=baseline.selection,
            anchors=tuple(route.selection for route in anchor_routes),
            holdout_case_ids=definition.suite.holdout_case_ids,
            artifact_store_factory=artifact_factory,
            receipt_sink=receipt_sink,
            allow_exhaustive=arm.solver_profile == "exhaustive",
        )
        champion = result.champion
        if champion is None:
            empty = RouteAggregate("", 0, 0, 0.0, {}, {}, {})
            return _arm_result_from_aggregate(
                arm,
                empty,
                None,
                route_count_upper_bound=result.admitted_space.route_count_upper_bound,
                evaluated_plan_count=len(result.plans),
                receipt_count=len(result.ledger.receipts),
                fallbacks=(),
                pareto=result.pareto_plan_digests,
                holdout_confirmed=False,
                optimality_proven=_solver_optimality_proven(result),
                status="completed-no-accepted-route",
                details={"solver": result.to_dict()},
            )
        aggregate = next(
            item for item in result.ledger.aggregates() if item.plan_digest == champion.digest
        )
        return _arm_result_from_aggregate(
            arm,
            aggregate,
            champion,
            route_count_upper_bound=result.admitted_space.route_count_upper_bound,
            evaluated_plan_count=len(result.plans),
            receipt_count=len(result.ledger.receipts),
            fallbacks=tuple(item.plan_digest for item in result.fallbacks),
            pareto=result.pareto_plan_digests,
            holdout_confirmed=(
                not definition.suite.holdout_case_ids
                or champion.digest in result.holdout_confirmed_plan_digests
            ),
            optimality_proven=_solver_optimality_proven(result),
            details={"solver": result.to_dict()},
        )


def _executor(runtime: str) -> ReferenceExecutor:
    if runtime == "in-process":
        adapter = PythonRuntime()
        policy_runtime = "python"
    elif runtime == "subprocess":
        adapter = SubprocessPythonRuntime(max_memory_mb=None)
        policy_runtime = "python"
    else:
        raise ValueError("benchmark runtime must be in-process or subprocess")
    return ReferenceExecutor(
        runtimes=RuntimeRegistry({policy_runtime: adapter}),
        # Benchmark cases are independent trials. Preserve failures in receipts
        # without allowing earlier trials to censor later candidate evidence.
        circuit_breaker=CircuitBreaker(failure_threshold=1_000_000_000),
    )


def _artifact_factory(root: str | Path | None) -> Callable[[], ArtifactStore]:
    if root is None:
        return MemoryArtifactStore
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return lambda: FileArtifactStore(path)


def _solver_optimality_proven(result: Any) -> bool:
    reports = [round_.search_report for round_ in result.rounds]
    return bool(reports) and all(item.complete and item.optimality_proven for item in reports)


def _selection(plan: FrozenPlan | None) -> tuple[tuple[str, str], ...]:
    if plan is None:
        return ()
    return tuple((item.slot_id, item.candidate_id) for item in plan.bindings)


def _arm_result_from_aggregate(
    arm: BenchmarkArm,
    aggregate: RouteAggregate,
    plan: FrozenPlan | None,
    *,
    route_count_upper_bound: int,
    evaluated_plan_count: int,
    receipt_count: int,
    fallbacks: tuple[str, ...],
    pareto: tuple[str, ...],
    holdout_confirmed: bool,
    optimality_proven: bool,
    details: Mapping[str, Any],
    status: str = "completed",
) -> BenchmarkArmResult:
    return BenchmarkArmResult(
        arm_id=arm.id,
        kind=arm.kind,
        status=status,
        route_count_upper_bound=route_count_upper_bound,
        evaluated_plan_count=evaluated_plan_count,
        receipt_count=receipt_count,
        champion_run_count=aggregate.runs,
        accepted_runs=aggregate.accepted_runs,
        acceptance_rate=aggregate.acceptance_rate,
        champion_plan_digest=plan.digest if plan is not None else "",
        champion_selection=_selection(plan),
        fallback_plan_digests=fallbacks,
        pareto_plan_digests=pareto,
        objective_means=aggregate.metric_means,
        objective_variances=aggregate.metric_variances,
        holdout_confirmed=holdout_confirmed,
        optimality_proven=optimality_proven,
        details=details,
    )


def write_benchmark_report(
    report: BenchmarkReport,
    target: str | Path,
) -> Path:
    """Write a dependency-free report with embedded evidence and route columns."""
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report.to_dict(), sort_keys=True, ensure_ascii=False).replace(
        "<", "\\u003c"
    )
    title = html.escape(report.suite.title)
    document = _REPORT_HTML.replace("{{TITLE}}", title).replace("{{REPORT_JSON}}", payload)
    target_path.write_text(document, encoding="utf-8")
    return target_path


_REPORT_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITLE}} — SolutionGraph evidence</title>
<style>
:root{--bg:#f4f1e8;--paper:#fffdf7;--ink:#19211d;--muted:#667069;--line:#d5d0c3;--green:#176b4b;--lime:#c5f05a;--orange:#ef8e44;--blue:#3068b2;--red:#aa3f38;--shadow:0 18px 55px #2222}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{padding:42px clamp(22px,5vw,76px) 28px;background:var(--ink);color:#fff}header p{color:#c6cec8;max-width:900px;margin:10px 0 0}h1{font-size:clamp(30px,5vw,58px);letter-spacing:-.045em;line-height:1;margin:0}.eyebrow{color:var(--lime);font-size:12px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;margin-bottom:16px}
main{padding:28px clamp(16px,4vw,62px) 70px}.bar{display:flex;gap:10px;flex-wrap:wrap;margin:-48px 0 26px}.pill{background:var(--paper);border:1px solid var(--line);border-radius:999px;padding:10px 15px;box-shadow:0 8px 30px #2221}.pill b{margin-right:6px}
.notice{border-left:5px solid var(--orange);background:#fff6e9;padding:14px 18px;margin:18px 0 28px;border-radius:0 10px 10px 0}.arms{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:15px}.arm{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:var(--shadow)}.arm.good{border-top:6px solid var(--green)}.arm.warn{border-top:6px solid var(--orange)}.arm h2{margin:0 0 3px;font-size:21px}.kind{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.09em;font-weight:750}.metrics{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:18px 0}.metric{background:#eeece3;border-radius:9px;padding:10px}.metric strong{font-size:22px;display:block}.metric span{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
section{margin-top:34px}section>h2{font-size:27px;letter-spacing:-.025em}.route-wrap{overflow:auto;padding:5px 1px 25px}.route{display:flex;align-items:flex-start;min-width:max-content;gap:34px}.step{width:230px;position:relative}.step:not(:last-child):after{content:"";position:absolute;top:79px;left:100%;width:34px;border-top:3px solid var(--green)}.step-label{font-size:12px;text-transform:uppercase;color:var(--muted);font-weight:800;letter-spacing:.08em}.node{margin-top:9px;padding:14px;background:var(--paper);border:2px solid var(--green);border-radius:11px;box-shadow:0 7px 20px #2221;overflow-wrap:anywhere}.node small{display:block;color:var(--muted);margin-top:4px}.empty{color:var(--muted);font-style:italic}
table{width:100%;border-collapse:collapse;background:var(--paper);border-radius:12px;overflow:hidden}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--line)}th{background:#e8e4d9;font-size:12px;text-transform:uppercase;letter-spacing:.07em}code{font:12px ui-monospace,SFMono-Regular,Menlo,monospace}.raw{margin-top:20px}.raw summary{cursor:pointer;font-weight:750}.raw pre{white-space:pre-wrap;word-break:break-word;background:#111713;color:#dce8df;padding:18px;border-radius:12px;max-height:520px;overflow:auto}
@media(max-width:650px){header{padding-top:28px}.bar{margin-top:-18px}.metrics{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<header><div class="eyebrow">SolutionGraph benchmark receipt</div><h1 id="title"></h1><p id="description"></p></header>
<main><div class="bar" id="summary"></div><div class="notice"><strong>Claim boundary:</strong> <span id="claim"></span>. Results apply only to the embedded cases, exact implementations, environment receipts, and declared allocation—not to an external leaderboard or production population.</div>
<section><h2>Allocation arms</h2><div class="arms" id="arms"></div></section>
<section><h2>Champion route, left to right</h2><p>Select an arm to inspect every chosen node in semantic step order.</p><select id="arm-select"></select><div class="route-wrap"><div class="route" id="route"></div></div></section>
<section><h2>Objective comparison</h2><table><thead><tr><th>Arm</th><th>Acceptance</th><th>Plans tried</th><th>Search coverage</th><th>Objectives</th><th>Holdout</th><th>Optimality</th></tr></thead><tbody id="comparison"></tbody></table></section>
<details class="raw"><summary>Complete machine-readable evidence</summary><pre id="raw"></pre></details></main>
<script id="benchmark-data" type="application/json">{{REPORT_JSON}}</script>
<script>
const d=JSON.parse(document.getElementById('benchmark-data').textContent),q=s=>document.querySelector(s),esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
q('#title').textContent=d.suite.title;q('#description').textContent=d.suite.description;q('#claim').textContent=d.claim_scope;
q('#summary').innerHTML=[['status',d.ok?'verified':'problems'],['suite',d.suite.id],['cases',d.suite.task_case_digests.length],['report',d.report_digest.slice(0,23)+'…']].map(x=>`<span class="pill"><b>${esc(x[0])}</b>${esc(x[1])}</span>`).join('');
const pct=n=>(100*n).toFixed(1)+'%',short=s=>s?s.slice(0,19)+'…':'none';
q('#arms').innerHTML=d.arms.map(a=>`<article class="arm ${a.acceptance_rate===1?'good':'warn'}"><div class="kind">${esc(a.kind)}</div><h2>${esc(a.arm_id)}</h2><div class="metrics"><div class="metric"><strong>${a.accepted_runs}/${a.champion_run_count}</strong><span>champion accepted</span></div><div class="metric"><strong>${a.evaluated_plan_count}</strong><span>plans tried</span></div><div class="metric"><strong>${a.receipt_count}</strong><span>total receipts</span></div><div class="metric"><strong>${a.fallback_plan_digests.length}</strong><span>fallbacks</span></div></div><code>${esc(short(a.champion_plan_digest))}</code></article>`).join('');
const sel=q('#arm-select');sel.innerHTML=d.arms.map((a,i)=>`<option value="${i}">${esc(a.arm_id)}</option>`).join('');
function route(){const a=d.arms[+sel.value],entries=Object.entries(a.champion_selection);q('#route').innerHTML=entries.length?entries.map(([step,node],i)=>`<div class="step"><div class="step-label">Step ${i+1} · ${esc(step)}</div><div class="node">${esc(node)}<small>content-bound selection</small></div></div>`).join(''):'<div class="empty">No accepted champion route.</div>'}sel.addEventListener('change',route);route();
q('#comparison').innerHTML=d.arms.map(a=>`<tr><td><b>${esc(a.arm_id)}</b></td><td>${pct(a.acceptance_rate)}</td><td>${a.evaluated_plan_count}/${a.route_count_upper_bound}</td><td>${pct(a.route_count_upper_bound?a.evaluated_plan_count/a.route_count_upper_bound:0)}</td><td>${esc(Object.entries(a.objective_means).map(([k,v])=>k+'='+Number(v).toFixed(4)).join(', ')||'—')}</td><td>${a.holdout_confirmed?'confirmed':'not confirmed'}</td><td>${a.optimality_proven?'proven':'not claimed'}</td></tr>`).join('');
q('#raw').textContent=JSON.stringify(d,null,2);
</script>
</body></html>
"""


__all__ = [
    "BENCHMARK_ARM_KINDS",
    "BENCHMARK_CLAIM_SCOPES",
    "BENCHMARK_MODEL_VERSION",
    "BenchmarkArm",
    "BenchmarkArmResult",
    "BenchmarkDefinition",
    "BenchmarkReport",
    "BenchmarkRunner",
    "BenchmarkSuite",
    "write_benchmark_report",
]
