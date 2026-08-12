"""Controlled experiments across compatible graph topologies and node routes.

The topology family defines explicit graph shapes.  Ordinary compiler admission
defines the valid route grid inside each shape.  This module adds the missing
experiment layer: always execute one exact control plan, execute the selected
control-topology alternatives and mutations under identical cases/seeds, and
compare receipt-derived evidence without allowing search to change semantics.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from solutiongraph.artifacts import ArtifactStore, MemoryArtifactStore, digest_value
from solutiongraph.compiler import Compiler
from solutiongraph.evidence import EvidenceLedger, ExperimentDesign, Objective
from solutiongraph.executor import ExecutionPolicy, ReferenceExecutor
from solutiongraph.experiments import (
    ExperimentBundle,
    ExperimentCase,
    ExperimentResult,
    ExperimentRunner,
    ReceiptSink,
)
from solutiongraph.model import ID_RE, AdmittedSpace, FrozenPlan, Registry, sha256_digest
from solutiongraph.ranking import RankedAggregate, rank_route_aggregates
from solutiongraph.search import BeliefModel, SearchEngine, SearchMode
from solutiongraph.topology import (
    TopologyFamily,
    TopologySearchBudget,
    TopologySearchEngine,
    TopologySearchReport,
)

GRAPH_EXPERIMENT_MODEL_VERSION = "0.1"
GRAPH_EXPERIMENT_STATUSES = ("completed", "completed-no-accepted-route")
GRAPH_ROUTE_ROLES = ("control", "control-topology-alternative", "mutation")


def _belief_to_dict(belief: BeliefModel) -> dict[str, Any]:
    return {
        "revision": belief.revision,
        "default_log_weight": belief.default_log_weight,
        "candidate_weights": [
            {
                "slot_id": item.slot_id,
                "candidate_id": item.candidate_id,
                "log_weight": item.log_weight,
                "evidence_count": item.evidence_count,
                "uncertainty": item.uncertainty,
            }
            for item in belief.candidate_weights
        ],
        "interaction_weights": [
            {
                "left_slot": item.left_slot,
                "left_candidate": item.left_candidate,
                "right_slot": item.right_slot,
                "right_candidate": item.right_candidate,
                "log_weight": item.log_weight,
                "evidence_count": item.evidence_count,
            }
            for item in belief.interaction_weights
        ],
    }


def _search_budget_to_dict(budget: TopologySearchBudget) -> dict[str, Any]:
    route = budget.route_budget
    return {
        "route_budget": {
            "mode": route.mode.value,
            "evaluation_limit": route.evaluation_limit,
            "result_limit": route.result_limit,
            "beam_width": route.beam_width,
            "random_seed": route.random_seed,
            "sampling_attempt_limit": route.sampling_attempt_limit,
            "mutation_probability": route.mutation_probability,
        },
        "topology_limit": budget.topology_limit,
        "global_evaluation_limit": budget.global_evaluation_limit,
        "result_limit": budget.result_limit,
    }


@dataclass(frozen=True)
class GraphControl:
    """One exact compiler-valid plan that remains fixed during the experiment."""

    variant_id: str
    selection: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "selection": dict(sorted(self.selection.items())),
        }

    def validate(
        self,
        family: TopologyFamily,
        spaces: Mapping[str, AdmittedSpace] | None = None,
    ) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.variant_id):
            problems.append("control variant_id must be a namespaced identifier")
        variant_ids = {variant.id for variant in family.variants}
        if self.variant_id not in variant_ids:
            problems.append("control variant_id is not in the topology family")
            return problems
        if any(
            not ID_RE.fullmatch(slot_id) or not ID_RE.fullmatch(candidate_id)
            for slot_id, candidate_id in self.selection.items()
        ):
            problems.append("control selection must map identifiers to identifiers")
        if spaces is not None and self.variant_id in spaces:
            choices = dict(spaces[self.variant_id].choices)
            missing = sorted(set(choices) - set(self.selection))
            unknown = sorted(set(self.selection) - set(choices))
            invalid = sorted(
                f"{slot_id}={candidate_id}"
                for slot_id, candidate_id in self.selection.items()
                if slot_id in choices and candidate_id not in choices[slot_id]
            )
            if missing:
                problems.append("control selection is missing slots: " + ", ".join(missing))
            if unknown:
                problems.append("control selection has unknown slots: " + ", ".join(unknown))
            if invalid:
                problems.append(
                    "control selection has non-admitted candidates: " + ", ".join(invalid)
                )
        return problems


@dataclass(frozen=True)
class GraphExperimentSpec:
    """Complete typed configuration for one control-versus-mutations experiment."""

    id: str
    family: TopologyFamily
    registry: Registry
    cases: tuple[ExperimentCase, ...]
    objectives: tuple[Objective, ...]
    control: GraphControl
    search_budget: TopologySearchBudget
    policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    beliefs: Mapping[str, BeliefModel] = field(default_factory=dict)
    seeds: tuple[int, ...] = (0,)
    repetitions: int = 1
    holdout_case_ids: tuple[str, ...] = ()
    minimum_acceptance_rate: float = 1.0
    require_complete_grid: bool = False

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("graph experiment id must be a namespaced identifier")
        problems.extend(f"family: {problem}" for problem in self.family.validate())
        problems.extend(
            f"registry: {diagnostic.code}: {diagnostic.message} ({diagnostic.path})"
            for diagnostic in Compiler().validate_registry(self.registry)
        )
        if not self.cases:
            problems.append("graph experiment cases must not be empty")
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            problems.append("graph experiment case ids must be unique")
        if any(not ID_RE.fullmatch(case_id) for case_id in case_ids):
            problems.append("graph experiment case ids must be namespaced identifiers")
        if set(self.holdout_case_ids) - set(case_ids):
            problems.append("holdout cases must be present in graph experiment cases")
        if len(self.holdout_case_ids) != len(set(self.holdout_case_ids)):
            problems.append("holdout case ids must be unique")
        reference_inputs = (
            {item.name for item in self.family.variants[0].program.inputs}
            if self.family.variants
            else set()
        )
        for case in self.cases:
            if set(case.inputs) != reference_inputs:
                problems.append(f"case {case.id} inputs differ from the topology family interface")
            if not ID_RE.fullmatch(case.verifier.identifier):
                problems.append(f"case {case.id} verifier identifier is invalid")
            if not getattr(case.verifier, "implementation_digest", ""):
                problems.append(f"case {case.id} verifier digest is required")
        if not self.objectives:
            problems.append("graph experiment objectives must not be empty")
        metrics = [objective.metric for objective in self.objectives]
        if len(metrics) != len(set(metrics)):
            problems.append("graph experiment objective metrics must be unique")
        for objective in self.objectives:
            problems.extend(objective.validate())
        if not self.seeds or len(self.seeds) != len(set(self.seeds)):
            problems.append("graph experiment seeds must be nonempty and unique")
        if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in self.seeds):
            problems.append("graph experiment seeds must be integers")
        if (
            isinstance(self.repetitions, bool)
            or not isinstance(self.repetitions, int)
            or self.repetitions <= 0
        ):
            problems.append("graph experiment repetitions must be positive")
        if not 0.0 <= self.minimum_acceptance_rate <= 1.0:
            problems.append("minimum_acceptance_rate must be between zero and one")
        problems.extend(self.policy.validate())
        problems.extend(self.search_budget.validate())
        variant_ids = {variant.id for variant in self.family.variants}
        unknown_beliefs = sorted(set(self.beliefs) - variant_ids)
        if unknown_beliefs:
            problems.append(
                "beliefs reference unknown topology variants: " + ", ".join(unknown_beliefs)
            )
        for variant_id, belief in self.beliefs.items():
            problems.extend(f"beliefs[{variant_id}]: {problem}" for problem in belief.validate())
        problems.extend(self.control.validate(self.family))
        if self.require_complete_grid:
            route = self.search_budget.route_budget
            if route.mode != SearchMode.EXHAUSTIVE:
                problems.append("complete-grid experiments require exhaustive route search")
            if route.evaluation_limit is not None:
                problems.append("complete-grid experiments cannot cap route evaluation")
            if self.search_budget.topology_limit is not None:
                problems.append("complete-grid experiments cannot cap topology count")
            if self.search_budget.global_evaluation_limit is not None:
                problems.append("complete-grid experiments cannot set a global route cap")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_experiment_model_version": GRAPH_EXPERIMENT_MODEL_VERSION,
            "id": self.id,
            "family_digest": self.family.digest,
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
            "objectives": [
                {
                    "metric": objective.metric,
                    "direction": objective.direction,
                    "weight": objective.weight,
                    "hard_minimum": objective.hard_minimum,
                    "hard_maximum": objective.hard_maximum,
                }
                for objective in self.objectives
            ],
            "control": self.control.to_dict(),
            "search_budget": _search_budget_to_dict(self.search_budget),
            "execution_policy": self.policy.to_dict(),
            "beliefs": {
                variant_id: _belief_to_dict(belief)
                for variant_id, belief in sorted(self.beliefs.items())
            },
            "seeds": list(self.seeds),
            "repetitions": self.repetitions,
            "holdout_case_ids": list(self.holdout_case_ids),
            "minimum_acceptance_rate": self.minimum_acceptance_rate,
            "require_complete_grid": self.require_complete_grid,
        }


@dataclass(frozen=True)
class GraphRouteComparison:
    """Cross-topology evidence for one exact plan."""

    rank: int
    plan_digest: str
    variant_id: str
    role: str
    selection: tuple[tuple[str, str], ...]
    runs: int
    accepted_runs: int
    acceptance_rate: float
    objective_means: Mapping[str, float]
    objective_variances: Mapping[str, float]
    objective_deltas_from_control: Mapping[str, float]
    weighted_score: float
    meets_acceptance_gate: bool
    meets_objective_constraints: bool
    pareto: bool

    @property
    def eligible(self) -> bool:
        return self.meets_acceptance_gate and self.meets_objective_constraints

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "plan_digest": self.plan_digest,
            "variant_id": self.variant_id,
            "role": self.role,
            "selection": dict(self.selection),
            "runs": self.runs,
            "accepted_runs": self.accepted_runs,
            "acceptance_rate": self.acceptance_rate,
            "objective_means": dict(self.objective_means),
            "objective_variances": dict(self.objective_variances),
            "objective_deltas_from_control": dict(self.objective_deltas_from_control),
            "weighted_score": self.weighted_score,
            "meets_acceptance_gate": self.meets_acceptance_gate,
            "meets_objective_constraints": self.meets_objective_constraints,
            "pareto": self.pareto,
        }


@dataclass(frozen=True)
class GraphVariantExperimentResult:
    variant_id: str
    program_digest: str
    admitted_space_digest: str
    route_count_upper_bound: int
    plan_digests: tuple[str, ...]
    experiment: ExperimentResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "program_digest": self.program_digest,
            "admitted_space_digest": self.admitted_space_digest,
            "route_count_upper_bound": self.route_count_upper_bound,
            "plan_digests": list(self.plan_digests),
            "experiment": self.experiment.to_dict(),
        }


@dataclass(frozen=True)
class GraphExperimentReport:
    """Complete control/mutation search, execution, and comparison evidence."""

    spec: GraphExperimentSpec
    search_report: TopologySearchReport
    variant_results: tuple[GraphVariantExperimentResult, ...]
    plans: Mapping[str, FrozenPlan]
    ledger: EvidenceLedger
    comparisons: tuple[GraphRouteComparison, ...]
    control_plan_digest: str
    champion_plan_digest: str | None
    pareto_plan_digests: tuple[str, ...]
    complete_grid_evaluated: bool
    declared_grid_optimality_proven: bool

    @property
    def status(self) -> str:
        return "completed" if self.champion_plan_digest else "completed-no-accepted-route"

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_experiment_model_version": GRAPH_EXPERIMENT_MODEL_VERSION,
            "status": self.status,
            "experiment_id": self.spec.id,
            "spec_digest": self.spec.digest,
            "family_digest": self.spec.family.digest,
            "registry_digest": self.spec.registry.digest,
            "control_variant_id": self.spec.control.variant_id,
            "control_plan_digest": self.control_plan_digest,
            "total_cartesian_routes": self.search_report.total_cartesian_routes,
            "selected_plan_count": len(self.plans),
            "executed_plan_count": len(self.ledger.aggregates()),
            "complete_grid_evaluated": self.complete_grid_evaluated,
            "declared_grid_optimality_proven": self.declared_grid_optimality_proven,
            "champion_plan_digest": self.champion_plan_digest or "",
            "pareto_plan_digests": list(self.pareto_plan_digests),
            "configuration": self.spec.to_dict(),
            "search": self.search_report.to_dict(),
            "comparisons": [item.to_dict() for item in self.comparisons],
            "variants": [item.to_dict() for item in self.variant_results],
        }


class GraphExperimentRunner:
    """Compile and execute a fixed control beside explicit graph mutations."""

    def __init__(
        self,
        *,
        compiler: Compiler | None = None,
        search_engine: SearchEngine | None = None,
        executor_factory: Callable[[], ReferenceExecutor] | None = None,
    ) -> None:
        self.compiler = compiler or Compiler()
        self.topology_engine = TopologySearchEngine(
            compiler=self.compiler,
            search_engine=search_engine or SearchEngine(),
        )
        self.executor_factory = executor_factory or ReferenceExecutor

    def run(
        self,
        spec: GraphExperimentSpec,
        *,
        artifact_store_factory: Callable[[], ArtifactStore] | None = None,
        receipt_sink: ReceiptSink | None = None,
    ) -> GraphExperimentReport:
        problems = spec.validate()
        if problems:
            raise ValueError("invalid graph experiment: " + "; ".join(problems))
        spaces = dict(self.topology_engine.admit_all(spec.family, spec.registry))
        control_problems = spec.control.validate(spec.family, spaces)
        if control_problems:
            raise ValueError("invalid graph experiment control: " + "; ".join(control_problems))

        control_variant = spec.family.get(spec.control.variant_id)
        control_plan = self.compiler.compile(
            control_variant.program,
            spec.registry,
            spaces[control_variant.id],
            spec.control.selection,
        )
        search_report = self.topology_engine.search(
            spec.family,
            spec.registry,
            budget=spec.search_budget,
            beliefs=spec.beliefs,
        )
        if spec.require_complete_grid:
            if not search_report.complete:
                raise ValueError("complete-grid experiment search did not cover every route")
            if len(search_report.proposals) != search_report.evaluated_routes:
                raise ValueError(
                    "complete-grid experiment result_limit hides executable routes; "
                    "increase both topology and route result_limit values"
                )

        plans_by_variant: dict[str, dict[str, FrozenPlan]] = {
            control_variant.id: {control_plan.digest: control_plan}
        }
        all_plans: dict[str, FrozenPlan] = {control_plan.digest: control_plan}
        for proposal in search_report.proposals:
            plan = self.topology_engine.compile(spec.family, spec.registry, proposal)
            all_plans[plan.digest] = plan
            plans_by_variant.setdefault(proposal.variant_id, {})[plan.digest] = plan

        cases = {case.id: case for case in spec.cases}
        artifact_store_factory = artifact_store_factory or MemoryArtifactStore
        ledger = EvidenceLedger()
        variant_results: list[GraphVariantExperimentResult] = []
        plan_variants: dict[str, str] = {}
        for variant in spec.family.variants:
            variant_plans = plans_by_variant.get(variant.id, {})
            if not variant_plans:
                continue
            plan_variants.update({digest: variant.id for digest in variant_plans})
            design = ExperimentDesign(
                id=f"{spec.id}.{variant.id}",
                task_case_ids=tuple(cases),
                plan_digests=tuple(sorted(variant_plans)),
                seeds=spec.seeds,
                repetitions=spec.repetitions,
                objectives=spec.objectives,
                control_plan_digest=(
                    control_plan.digest if variant.id == control_variant.id else ""
                ),
                holdout_case_ids=spec.holdout_case_ids,
            )
            experiment = ExperimentRunner(self.executor_factory()).run_bundle(
                ExperimentBundle(
                    design=design,
                    plans=variant_plans,
                    cases=cases,
                    program=variant.program,
                    registry=spec.registry,
                    space=spaces[variant.id],
                    policy=spec.policy,
                    belief_revision=(spec.beliefs.get(variant.id, BeliefModel()).revision),
                ),
                artifact_store_factory=artifact_store_factory,
                receipt_sink=receipt_sink,
            )
            ledger = ledger.append(*experiment.ledger.receipts)
            variant_results.append(
                GraphVariantExperimentResult(
                    variant_id=variant.id,
                    program_digest=variant.program.digest,
                    admitted_space_digest=spaces[variant.id].digest,
                    route_count_upper_bound=spaces[variant.id].route_count_upper_bound,
                    plan_digests=tuple(sorted(variant_plans)),
                    experiment=experiment,
                )
            )

        rankings = rank_route_aggregates(
            ledger.aggregates(),
            spec.objectives,
            minimum_acceptance_rate=spec.minimum_acceptance_rate,
        )
        control_score = next(item for item in rankings if item.plan_digest == control_plan.digest)
        comparisons = tuple(
            self._comparison(
                score,
                all_plans[score.plan_digest],
                plan_variants[score.plan_digest],
                spec,
                control_plan.digest,
                control_score,
            )
            for score in rankings
        )
        champion = next((item.plan_digest for item in comparisons if item.eligible), None)
        pareto = tuple(item.plan_digest for item in comparisons if item.pareto)
        completed_runs = sum(len(result.experiment.ledger.receipts) for result in variant_results)
        scheduled_runs = sum(result.experiment.design.scheduled_runs for result in variant_results)
        complete_grid = (
            search_report.complete
            and len(all_plans) == search_report.evaluated_routes
            and completed_runs == scheduled_runs
        )
        return GraphExperimentReport(
            spec=spec,
            search_report=search_report,
            variant_results=tuple(variant_results),
            plans=all_plans,
            ledger=ledger,
            comparisons=comparisons,
            control_plan_digest=control_plan.digest,
            champion_plan_digest=champion,
            pareto_plan_digests=pareto,
            complete_grid_evaluated=complete_grid,
            declared_grid_optimality_proven=complete_grid and champion is not None,
        )

    @staticmethod
    def _comparison(
        score: RankedAggregate,
        plan: FrozenPlan,
        variant_id: str,
        spec: GraphExperimentSpec,
        control_plan_digest: str,
        control_score: RankedAggregate,
    ) -> GraphRouteComparison:
        if score.plan_digest == control_plan_digest:
            role = "control"
        elif variant_id == spec.control.variant_id:
            role = "control-topology-alternative"
        else:
            role = "mutation"
        deltas = {
            objective.metric: (
                score.metric_means[objective.metric] - control_score.metric_means[objective.metric]
            )
            for objective in spec.objectives
            if objective.metric in score.metric_means
            and objective.metric in control_score.metric_means
        }
        by_slot = {binding.slot_id: binding.candidate_id for binding in plan.bindings}
        selection = tuple((slot_id, by_slot[slot_id]) for slot_id in plan.topological_order)
        return GraphRouteComparison(
            rank=score.rank,
            plan_digest=score.plan_digest,
            variant_id=variant_id,
            role=role,
            selection=selection,
            runs=score.runs,
            accepted_runs=score.accepted_runs,
            acceptance_rate=score.acceptance_rate,
            objective_means={
                objective.metric: score.metric_means[objective.metric]
                for objective in spec.objectives
                if objective.metric in score.metric_means
            },
            objective_variances={
                objective.metric: score.metric_variances[objective.metric]
                for objective in spec.objectives
                if objective.metric in score.metric_variances
            },
            objective_deltas_from_control=deltas,
            weighted_score=score.weighted_score,
            meets_acceptance_gate=score.meets_acceptance_gate,
            meets_objective_constraints=score.meets_objective_constraints,
            pareto=score.pareto,
        )


__all__ = [
    "GRAPH_EXPERIMENT_MODEL_VERSION",
    "GRAPH_EXPERIMENT_STATUSES",
    "GRAPH_ROUTE_ROLES",
    "GraphControl",
    "GraphExperimentReport",
    "GraphExperimentRunner",
    "GraphExperimentSpec",
    "GraphRouteComparison",
    "GraphVariantExperimentResult",
]
