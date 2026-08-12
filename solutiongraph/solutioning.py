"""End-to-end façade for history-informed, typed task solutioning.

The façade is deliberately a composition layer.  It does not merge task
meaning, compiler admission, optimizer priors, frozen plans, execution policy,
or evidence.  Each public operation exposes one stage so callers can inspect or
replace it, while :func:`solve_task` provides the five-minute path.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from solutiongraph.artifacts import ArtifactStore, MemoryArtifactStore, digest_value
from solutiongraph.compiler import Compiler
from solutiongraph.errors import ValidationError
from solutiongraph.evidence import EvidenceLedger
from solutiongraph.executor import ExecutionPolicy
from solutiongraph.experiments import ExperimentCase, ReceiptSink
from solutiongraph.intelligence import (
    EffortPolicy,
    HistoricalMemory,
    HistoricalMemoryUpdate,
    HistoricalRecommendation,
    HistoryInformedPlanner,
    LaneOutcome,
    NegativeTransferAssessment,
    RetrievalPolicy,
    SearchInitialization,
    TaskFingerprint,
    assess_negative_transfer,
    close_solver_history,
    effort_policy,
    fingerprint_from_contract,
)
from solutiongraph.model import (
    ID_RE,
    AdmittedSpace,
    FrozenPlan,
    ProgramGraph,
    Registry,
    sha256_digest,
)
from solutiongraph.solver import SolverResult, UniversalSolver
from solutiongraph.tasking import TaskContract

TASK_SOLUTION_MODEL_VERSION = "0.1"


def _empty_memory() -> HistoricalMemory:
    return HistoricalMemory("memory.taedri-empty", "1.0.0")


@dataclass(frozen=True)
class TaskSolutionRequest:
    """Typed quality-of-life boundary for one complete solve request."""

    id: str
    task: TaskContract
    program: ProgramGraph
    registry: Registry
    cases: tuple[ExperimentCase, ...]
    policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    historical_memory: HistoricalMemory = field(default_factory=_empty_memory)
    fingerprint: TaskFingerprint | None = None
    effort: int | str | EffortPolicy = 5
    retrieval_policy: RetrievalPolicy | None = None
    baseline_selection: tuple[tuple[str, str], ...] = ()
    holdout_case_ids: tuple[str, ...] = ()
    random_seed: int = 0

    @property
    def selected_effort(self) -> EffortPolicy:
        return effort_policy(self.effort)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_solution_model_version": TASK_SOLUTION_MODEL_VERSION,
            "id": self.id,
            "task_contract_digest": self.task.digest,
            "program_digest": self.program.digest,
            "registry_digest": self.registry.digest,
            "cases": [
                {
                    "id": case.id,
                    "input_digest": digest_value(case.inputs),
                    "verifier": case.verifier.identifier,
                    "verifier_digest": case.verifier.implementation_digest,
                }
                for case in self.cases
            ],
            "execution_policy": self.policy.to_dict(),
            "historical_memory_digest": self.historical_memory.digest,
            "fingerprint_digest": self.fingerprint.digest if self.fingerprint else "",
            "effort_policy": self.selected_effort.to_dict(),
            "retrieval_policy": (
                self.retrieval_policy.to_dict() if self.retrieval_policy is not None else None
            ),
            "baseline_selection": dict(self.baseline_selection),
            "holdout_case_ids": list(self.holdout_case_ids),
            "random_seed": self.random_seed,
        }


@dataclass(frozen=True)
class TaskSolutionBinding:
    """Validated task recognition and search state bound to one admitted space."""

    request_digest: str
    fingerprint: TaskFingerprint
    admitted_space: AdmittedSpace
    initialization: SearchInitialization

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_digest": self.request_digest,
            "fingerprint": self.fingerprint.to_dict(),
            "admitted_space_digest": self.admitted_space.digest,
            "route_count_upper_bound": self.admitted_space.route_count_upper_bound,
            "initialization": self.initialization.to_dict(),
        }


@dataclass(frozen=True)
class TaskSolutionResult:
    """Complete staged result without erasing the underlying solver evidence."""

    request_id: str
    binding: TaskSolutionBinding
    solver: SolverResult
    negative_transfer: NegativeTransferAssessment

    @property
    def status(self) -> str:
        return self.solver.status

    @property
    def champion(self) -> FrozenPlan | None:
        return self.solver.champion

    def to_dict(self, *, include_receipts: bool = True) -> dict[str, Any]:
        return {
            "task_solution_model_version": TASK_SOLUTION_MODEL_VERSION,
            "status": self.status,
            "request_id": self.request_id,
            "request_digest": self.binding.request_digest,
            "binding_digest": self.binding.digest,
            "fingerprint": self.binding.fingerprint.to_dict(),
            "initialization": self.binding.initialization.to_dict(),
            "negative_transfer": self.negative_transfer.to_dict(),
            "solver": self.solver.to_dict(include_receipts=include_receipts),
        }


class TaskSolutionEngine:
    """Recognize, retrieve, route, bind, execute, and learn through public seams."""

    def __init__(
        self,
        *,
        compiler: Compiler | None = None,
        planner: HistoryInformedPlanner | None = None,
        solver: UniversalSolver | None = None,
    ) -> None:
        self.compiler = compiler or Compiler()
        self.planner = planner or HistoryInformedPlanner()
        self.solver = solver or UniversalSolver(compiler=self.compiler)

    def validate(self, request: TaskSolutionRequest) -> tuple[str, ...]:
        problems: list[str] = []
        if not ID_RE.fullmatch(request.id) or "." not in request.id:
            problems.append("task solution request id must be namespaced")
        problems.extend(request.task.validate())
        problems.extend(request.task.validate_program(request.program))
        problems.extend(request.policy.validate())
        problems.extend(request.historical_memory.validate())
        problems.extend(request.selected_effort.validate())
        if request.retrieval_policy is not None:
            problems.extend(request.retrieval_policy.validate())
        program_inputs = {item.name for item in request.program.inputs}
        case_ids = [case.id for case in request.cases]
        if not request.cases or len(case_ids) != len(set(case_ids)):
            problems.append("task solution cases must be nonempty with unique ids")
        if set(request.task.case_ids) != set(case_ids):
            problems.append("task solution cases must exactly match the task contract")
        for case in request.cases:
            if set(case.inputs) != program_inputs:
                problems.append(f"case {case.id} inputs differ from the program interface")
            if case.verifier.identifier != request.task.oracle.id:
                problems.append(f"case {case.id} verifier id differs from the task oracle")
            if case.verifier.implementation_digest != request.task.oracle.evaluator_digest:
                problems.append(f"case {case.id} verifier digest differs from the task oracle")
        if set(request.holdout_case_ids) - set(case_ids):
            problems.append("task solution holdout cases must be present in cases")
        if len(request.holdout_case_ids) != len(set(request.holdout_case_ids)):
            problems.append("task solution holdout case ids must be unique")
        if isinstance(request.random_seed, bool) or not isinstance(request.random_seed, int):
            problems.append("task solution random_seed must be an integer")
        baseline_slots = [slot_id for slot_id, _ in request.baseline_selection]
        if len(baseline_slots) != len(set(baseline_slots)):
            problems.append("task solution baseline must bind each slot at most once")
        if request.fingerprint is not None:
            problems.extend(request.fingerprint.validate())
            if request.fingerprint.task_contract_digest != request.task.digest:
                problems.append("supplied fingerprint does not match the task contract")
            if request.fingerprint.task_id != request.task.id:
                problems.append("supplied fingerprint task id does not match the task")
        diagnostics = (
            *self.compiler.validate_program(request.program),
            *self.compiler.validate_registry(request.registry),
        )
        problems.extend(
            f"{item.code}: {item.message} ({item.path})" for item in diagnostics
        )
        if not diagnostics:
            try:
                space = self.compiler.admit(request.program, request.registry)
                if request.baseline_selection:
                    self.compiler.compile(
                        request.program,
                        request.registry,
                        space,
                        dict(request.baseline_selection),
                    )
            except ValidationError as exc:
                problems.extend(
                    f"{item.code}: {item.message} ({item.path})" for item in exc.diagnostics
                )
            except ValueError as exc:
                problems.append(str(exc))
        return tuple(dict.fromkeys(problems))

    def recognize(self, request: TaskSolutionRequest) -> TaskFingerprint:
        """Classify and fingerprint the task; no route becomes valid here."""

        if request.fingerprint is not None:
            return request.fingerprint
        extensions = dict(request.task.extensions)
        dataset_family = extensions.get("dataset.family-id", "")
        if not isinstance(dataset_family, str):
            dataset_family = ""
        return fingerprint_from_contract(
            request.task,
            dataset_family_id=dataset_family,
        )

    def search(
        self,
        request: TaskSolutionRequest,
        *,
        admitted_space: AdmittedSpace | None = None,
        fingerprint: TaskFingerprint | None = None,
    ) -> SearchInitialization:
        """Build the uncertainty-aware portfolio with protected blind lanes."""

        space = admitted_space or self.compiler.admit(request.program, request.registry)
        recognized = fingerprint or self.recognize(request)
        return self.planner.plan(
            space,
            recognized,
            request.historical_memory,
            effort=request.selected_effort,
            retrieval_policy=request.retrieval_policy,
            canonical_selection=(
                dict(request.baseline_selection) if request.baseline_selection else None
            ),
            random_seed=request.random_seed,
        )

    def retrieve(
        self,
        request: TaskSolutionRequest,
        *,
        admitted_space: AdmittedSpace | None = None,
        fingerprint: TaskFingerprint | None = None,
    ) -> tuple[HistoricalRecommendation, ...]:
        return self.search(
            request,
            admitted_space=admitted_space,
            fingerprint=fingerprint,
        ).recommendations

    def bind(self, request: TaskSolutionRequest) -> TaskSolutionBinding:
        """Validate and bind recognition/search state to exact compiler admission."""

        problems = self.validate(request)
        if problems:
            raise ValueError("invalid task solution request: " + "; ".join(problems))
        space = self.compiler.admit(request.program, request.registry)
        fingerprint = self.recognize(request)
        initialization = self.search(
            request,
            admitted_space=space,
            fingerprint=fingerprint,
        )
        return TaskSolutionBinding(request.digest, fingerprint, space, initialization)

    def route(
        self,
        request: TaskSolutionRequest,
        binding: TaskSolutionBinding,
    ) -> Mapping[str, FrozenPlan]:
        """Compile every proposed starting point without executing any of them."""

        self._require_binding(request, binding)
        return {
            start.id: self.compiler.compile(
                request.program,
                request.registry,
                binding.admitted_space,
                dict(start.selection),
            )
            for start in binding.initialization.starts
        }

    def execute(
        self,
        request: TaskSolutionRequest,
        binding: TaskSolutionBinding,
        *,
        artifact_store_factory: Callable[[], ArtifactStore] | None = None,
        receipt_sink: ReceiptSink | None = None,
        allow_exhaustive: bool = False,
    ) -> TaskSolutionResult:
        """Run the ordinary solver against the inspected, exact binding."""

        self._require_binding(request, binding)
        result = self.solver.solve(
            request.program,
            request.registry,
            cases=request.cases,
            objectives=request.task.objectives,
            policy=request.policy,
            initialization=binding.initialization,
            baseline_selection=(
                dict(request.baseline_selection) if request.baseline_selection else None
            ),
            holdout_case_ids=request.holdout_case_ids,
            artifact_store_factory=artifact_store_factory,
            receipt_sink=receipt_sink,
            allow_exhaustive=allow_exhaustive,
        )
        transfer = self._negative_transfer(result)
        return TaskSolutionResult(request.id, binding, result, transfer)

    def solve(
        self,
        request: TaskSolutionRequest,
        *,
        artifact_store_factory: Callable[[], ArtifactStore] | None = None,
        receipt_sink: ReceiptSink | None = None,
        allow_exhaustive: bool = False,
    ) -> TaskSolutionResult:
        binding = self.bind(request)
        return self.execute(
            request,
            binding,
            artifact_store_factory=artifact_store_factory,
            receipt_sink=receipt_sink,
            allow_exhaustive=allow_exhaustive,
        )

    @staticmethod
    def get_evidence(result: TaskSolutionResult) -> EvidenceLedger:
        return result.solver.ledger

    @staticmethod
    def learn(
        request: TaskSolutionRequest,
        result: TaskSolutionResult,
        *,
        artifact_store: ArtifactStore | None = None,
        normalized_lifts_by_plan: Mapping[str, Mapping[str, float]] | None = None,
        costs_by_plan: Mapping[str, Mapping[str, float]] | None = None,
        evidence_scope: str = "evidence.mechanism-fixture",
    ) -> HistoricalMemoryUpdate:
        """Close development evidence into a new memory snapshot; never mutate history."""

        if result.binding.request_digest != request.digest:
            raise ValueError("task solution result belongs to a different request")
        return close_solver_history(
            request.historical_memory,
            result.binding.fingerprint,
            result.solver,
            request.task.objectives,
            artifact_store=artifact_store or MemoryArtifactStore(),
            normalized_lifts_by_plan=normalized_lifts_by_plan,
            costs_by_plan=costs_by_plan,
            evidence_scope=evidence_scope,
        )

    def _require_binding(
        self,
        request: TaskSolutionRequest,
        binding: TaskSolutionBinding,
    ) -> None:
        if binding.request_digest != request.digest:
            raise ValueError("task solution binding belongs to a different request")
        current = self.compiler.admit(request.program, request.registry)
        if current.digest != binding.admitted_space.digest:
            raise ValueError("task solution admitted space changed after binding")
        problems = binding.initialization.validate(current)
        if problems:
            raise ValueError("invalid bound search initialization: " + "; ".join(problems))

    @staticmethod
    def _negative_transfer(result: SolverResult) -> NegativeTransferAssessment:
        rankings = {item.plan_digest: item for item in result.rankings}
        outcomes = tuple(
            LaneOutcome(
                attribution.start_id,
                attribution.source_lane,
                attribution.budget_digest,
                rankings[attribution.plan_digest].weighted_score,
                rankings[attribution.plan_digest].meets_acceptance_gate,
                attribution.history_blind,
            )
            for attribution in result.lane_attributions
            if attribution.primary and attribution.plan_digest in rankings
        )
        return assess_negative_transfer(outcomes)


def solve_task(
    request: TaskSolutionRequest,
    *,
    engine: TaskSolutionEngine | None = None,
    artifact_store_factory: Callable[[], ArtifactStore] | None = None,
    receipt_sink: ReceiptSink | None = None,
    allow_exhaustive: bool = False,
) -> TaskSolutionResult:
    """Five-minute public path from one typed request to evidence-backed result."""

    return (engine or TaskSolutionEngine()).solve(
        request,
        artifact_store_factory=artifact_store_factory,
        receipt_sink=receipt_sink,
        allow_exhaustive=allow_exhaustive,
    )


__all__ = [
    "TASK_SOLUTION_MODEL_VERSION",
    "TaskSolutionBinding",
    "TaskSolutionEngine",
    "TaskSolutionRequest",
    "TaskSolutionResult",
    "solve_task",
]
