"""Evidence-backed universal route solver over typed SolutionGraph programs.

The solver is an orchestration layer, not a second compiler or executor.  It
only searches compiler-admitted candidates, freezes every proposal before it
runs, and ranks immutable receipts produced by independent task verifiers.
Optimizer beliefs never enter a frozen plan or change execution semantics.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from solutiongraph.artifacts import ArtifactStore, MemoryArtifactStore
from solutiongraph.compiler import Compiler
from solutiongraph.evidence import (
    EvidenceLedger,
    ExperimentDesign,
    Objective,
    RouteAggregate,
    learn_observational_beliefs,
    pareto_front,
)
from solutiongraph.executor import ExecutionPolicy, ReferenceExecutor
from solutiongraph.experiments import ExperimentCase, ExperimentRunner, ReceiptSink
from solutiongraph.intelligence import SearchInitialization, merge_belief_models
from solutiongraph.model import AdmittedSpace, FrozenPlan, ProgramGraph, Registry, sha256_digest
from solutiongraph.search import (
    BeliefModel,
    RouteProposal,
    SearchBudget,
    SearchEngine,
    SearchMode,
    SearchReport,
)

SOLVER_MODEL_VERSION = "0.1"


@dataclass(frozen=True)
class SolverProfile:
    """A named, inspectable allocation policy for route discovery and trials."""

    id: str
    search_rounds: tuple[SearchBudget, ...]
    seeds: tuple[int, ...] = (0,)
    repetitions: int = 1
    minimum_acceptance_rate: float = 1.0
    fallback_count: int = 2

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.id:
            problems.append("profile id must not be empty")
        if not self.search_rounds:
            problems.append("profile search_rounds must not be empty")
        for index, budget in enumerate(self.search_rounds):
            problems.extend(
                f"search_rounds[{index}]: {problem}" for problem in budget.validate()
            )
        if not self.seeds or len(self.seeds) != len(set(self.seeds)):
            problems.append("profile seeds must be nonempty and unique")
        if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in self.seeds):
            problems.append("profile seeds must be integers")
        if self.repetitions <= 0:
            problems.append("profile repetitions must be positive")
        if not 0.0 <= self.minimum_acceptance_rate <= 1.0:
            problems.append("minimum_acceptance_rate must be between zero and one")
        if self.fallback_count < 0:
            problems.append("fallback_count must be non-negative")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "search_rounds": [
                {
                    "mode": budget.mode.value,
                    "evaluation_limit": budget.evaluation_limit,
                    "result_limit": budget.result_limit,
                    "beam_width": budget.beam_width,
                    "random_seed": budget.random_seed,
                    "sampling_attempt_limit": budget.sampling_attempt_limit,
                    "mutation_probability": budget.mutation_probability,
                }
                for budget in self.search_rounds
            ],
            "seeds": list(self.seeds),
            "repetitions": self.repetitions,
            "minimum_acceptance_rate": self.minimum_acceptance_rate,
            "fallback_count": self.fallback_count,
        }


QUICK_PROFILE = SolverProfile(
    id="quick",
    search_rounds=(SearchBudget(SearchMode.PRIOR, result_limit=1),),
    fallback_count=0,
)

BALANCED_PROFILE = SolverProfile(
    id="balanced",
    search_rounds=(
        SearchBudget(SearchMode.PRIOR, result_limit=1),
        SearchBudget(
            SearchMode.BEAM,
            evaluation_limit=8,
            result_limit=8,
            beam_width=8,
        ),
    ),
    fallback_count=2,
)

BROAD_PROFILE = SolverProfile(
    id="broad",
    search_rounds=(
        SearchBudget(SearchMode.PRIOR, result_limit=1),
        SearchBudget(
            SearchMode.BEAM,
            evaluation_limit=32,
            result_limit=16,
            beam_width=32,
        ),
        SearchBudget(
            SearchMode.SPROUT,
            evaluation_limit=16,
            result_limit=16,
            random_seed=1729,
            sampling_attempt_limit=256,
            mutation_probability=0.4,
        ),
    ),
    seeds=(0, 1),
    fallback_count=3,
)

EXHAUSTIVE_PROFILE = SolverProfile(
    id="exhaustive",
    # result_limit is replaced with the admitted Cartesian upper bound.  There
    # is intentionally no implicit route cap in this profile.
    search_rounds=(SearchBudget(SearchMode.EXHAUSTIVE, result_limit=1),),
    fallback_count=3,
)

SOLVER_PROFILES: Mapping[str, SolverProfile] = {
    profile.id: profile
    for profile in (QUICK_PROFILE, BALANCED_PROFILE, BROAD_PROFILE, EXHAUSTIVE_PROFILE)
}


@dataclass(frozen=True)
class SolverRound:
    """One search allocation and the new frozen plans it evaluated."""

    index: int
    search_report: SearchReport
    plan_digests: tuple[str, ...]
    receipt_ids: tuple[str, ...]
    belief_revision_before: str
    belief_revision_after: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "belief_revision_before": self.belief_revision_before,
            "belief_revision_after": self.belief_revision_after,
            "plan_digests": list(self.plan_digests),
            "receipt_ids": list(self.receipt_ids),
            "search": self.search_report.to_dict(),
        }


@dataclass(frozen=True)
class RankedRoute:
    """Evidence ranking for one exact, content-addressed plan."""

    rank: int
    plan_digest: str
    selection: tuple[tuple[str, str], ...]
    acceptance_rate: float
    accepted_runs: int
    runs: int
    objective_means: Mapping[str, float]
    objective_variances: Mapping[str, float]
    weighted_score: float
    meets_acceptance_gate: bool
    meets_objective_constraints: bool
    pareto: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "plan_digest": self.plan_digest,
            "selection": dict(self.selection),
            "acceptance_rate": self.acceptance_rate,
            "accepted_runs": self.accepted_runs,
            "runs": self.runs,
            "objective_means": dict(self.objective_means),
            "objective_variances": dict(self.objective_variances),
            "weighted_score": self.weighted_score,
            "meets_acceptance_gate": self.meets_acceptance_gate,
            "meets_objective_constraints": self.meets_objective_constraints,
            "pareto": self.pareto,
        }


@dataclass(frozen=True)
class FallbackRoute:
    """A separately benchmarked route selected for quality and dissimilarity."""

    priority: int
    plan_digest: str
    evidence_score: float
    diversity_score: float
    selection_score: float
    candidate_diversity: float
    implementation_diversity: float
    failure_mode_diversity: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority": self.priority,
            "plan_digest": self.plan_digest,
            "evidence_score": self.evidence_score,
            "diversity_score": self.diversity_score,
            "selection_score": self.selection_score,
            "candidate_diversity": self.candidate_diversity,
            "implementation_diversity": self.implementation_diversity,
            "failure_mode_diversity": self.failure_mode_diversity,
        }


@dataclass(frozen=True)
class SolverResult:
    """Complete provenance for one universal solve operation."""

    status: str
    profile: SolverProfile
    program_digest: str
    registry_digest: str
    admitted_space: AdmittedSpace
    rounds: tuple[SolverRound, ...]
    plans: Mapping[str, FrozenPlan]
    ledger: EvidenceLedger
    rankings: tuple[RankedRoute, ...]
    champion_plan_digest: str | None
    fallbacks: tuple[FallbackRoute, ...]
    pareto_plan_digests: tuple[str, ...]
    development_receipt_ids: tuple[str, ...]
    holdout_receipt_ids: tuple[str, ...]
    holdout_confirmed_plan_digests: tuple[str, ...]
    initial_beliefs: BeliefModel
    learned_beliefs: BeliefModel
    search_initialization_digest: str = ""

    @property
    def champion(self) -> FrozenPlan | None:
        if self.champion_plan_digest is None:
            return None
        return self.plans[self.champion_plan_digest]

    def to_dict(self, *, include_receipts: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "solver_model_version": SOLVER_MODEL_VERSION,
            "status": self.status,
            "profile": self.profile.to_dict(),
            "program_digest": self.program_digest,
            "registry_digest": self.registry_digest,
            "admitted_space_digest": self.admitted_space.digest,
            "route_count_upper_bound": self.admitted_space.route_count_upper_bound,
            "admitted_candidates": {
                slot_id: list(candidates)
                for slot_id, candidates in self.admitted_space.choices
            },
            "rounds": [round_.to_dict() for round_ in self.rounds],
            "evaluated_plan_count": len(self.plans),
            "champion_plan_digest": self.champion_plan_digest,
            "fallbacks": [fallback.to_dict() for fallback in self.fallbacks],
            "pareto_plan_digests": list(self.pareto_plan_digests),
            "development_receipt_ids": list(self.development_receipt_ids),
            "holdout_receipt_ids": list(self.holdout_receipt_ids),
            "holdout_confirmed_plan_digests": list(
                self.holdout_confirmed_plan_digests
            ),
            "rankings": [ranking.to_dict() for ranking in self.rankings],
            "initial_belief_revision": self.initial_beliefs.revision,
            "learned_belief_revision": self.learned_beliefs.revision,
            "search_initialization_digest": self.search_initialization_digest,
        }
        if include_receipts:
            payload["receipts"] = [
                receipt.to_dict() for receipt in self.ledger.receipts
            ]
        return payload


def get_solver_profile(profile: str | SolverProfile) -> SolverProfile:
    if isinstance(profile, SolverProfile):
        selected = profile
    else:
        try:
            selected = SOLVER_PROFILES[profile]
        except KeyError as exc:
            known = ", ".join(SOLVER_PROFILES)
            raise ValueError(f"unknown solver profile {profile!r}; known profiles: {known}") from exc
    problems = selected.validate()
    if problems:
        raise ValueError("invalid solver profile: " + "; ".join(problems))
    return selected


class UniversalSolver:
    """Compile, search, execute, learn, rank, and select route-level backups."""

    def __init__(
        self,
        *,
        compiler: Compiler | None = None,
        search_engine: SearchEngine | None = None,
        executor: ReferenceExecutor | None = None,
    ) -> None:
        self.compiler = compiler or Compiler()
        self.search_engine = search_engine or SearchEngine()
        self.executor = executor or ReferenceExecutor()

    def solve(
        self,
        program: ProgramGraph,
        registry: Registry,
        *,
        cases: Sequence[ExperimentCase],
        objectives: tuple[Objective, ...],
        policy: ExecutionPolicy | None = None,
        profile: str | SolverProfile | None = None,
        beliefs: BeliefModel | None = None,
        initialization: SearchInitialization | None = None,
        baseline_selection: Mapping[str, str] | None = None,
        anchors: Sequence[Mapping[str, str]] = (),
        holdout_case_ids: tuple[str, ...] = (),
        artifact_store_factory: Callable[[], ArtifactStore] | None = None,
        receipt_sink: ReceiptSink | None = None,
        allow_exhaustive: bool = False,
    ) -> SolverResult:
        """Solve one typed task without weakening compiler or verifier gates."""
        if profile is None and initialization is not None:
            effort = initialization.effort_policy
            selected_profile = get_solver_profile(
                SolverProfile(
                    id=effort.id,
                    search_rounds=effort.search_rounds,
                    seeds=effort.seeds,
                    repetitions=effort.repetitions,
                    minimum_acceptance_rate=effort.minimum_acceptance_rate,
                    fallback_count=effort.fallback_count,
                )
            )
        else:
            selected_profile = get_solver_profile(profile or "balanced")
        if not cases:
            raise ValueError("solver cases must not be empty")
        if not objectives:
            raise ValueError("solver objectives must not be empty")
        if len({case.id for case in cases}) != len(cases):
            raise ValueError("solver case ids must be unique")
        if set(holdout_case_ids) - {case.id for case in cases}:
            raise ValueError("holdout cases must be present in cases")
        development_cases = tuple(
            case for case in cases if case.id not in holdout_case_ids
        )
        if holdout_case_ids and not development_cases:
            raise ValueError("at least one development case is required with holdouts")
        if any(
            budget.mode == SearchMode.EXHAUSTIVE
            for budget in selected_profile.search_rounds
        ) and not allow_exhaustive:
            raise ValueError(
                "exhaustive search requires allow_exhaustive=True; it has no implicit route cap"
            )

        policy = policy or ExecutionPolicy()
        policy_problems = policy.validate()
        if policy_problems:
            raise ValueError("invalid execution policy: " + "; ".join(policy_problems))
        artifact_store_factory = artifact_store_factory or MemoryArtifactStore
        space = self.compiler.admit(program, registry)
        if initialization is not None:
            initialization_problems = initialization.validate(space)
            if initialization_problems:
                raise ValueError(
                    "invalid search initialization: "
                    + "; ".join(initialization_problems)
                )
        if beliefs is not None and initialization is not None:
            initial_beliefs = merge_belief_models(initialization.beliefs, beliefs)
        elif initialization is not None:
            initial_beliefs = initialization.beliefs
        else:
            initial_beliefs = beliefs or BeliefModel(revision="solver.cold-start")
        belief_problems = initial_beliefs.validate()
        if belief_problems:
            raise ValueError("invalid initial beliefs: " + "; ".join(belief_problems))

        case_map = {case.id: case for case in cases}
        development_case_map = {case.id: case for case in development_cases or cases}
        all_plans: dict[str, FrozenPlan] = {}
        evaluated_selections: set[tuple[tuple[str, str], ...]] = set()
        ledger = EvidenceLedger()
        rounds: list[SolverRound] = []
        current_beliefs = initial_beliefs
        baseline_key: tuple[tuple[str, str], ...] | None = None
        full_anchors = [dict(anchor) for anchor in anchors]
        initialization_starts = (
            initialization.starts if initialization is not None else ()
        )
        full_anchors.extend(
            dict(start.selection) for start in initialization_starts
        )

        if baseline_selection is not None:
            baseline_plan = self.compiler.compile(
                program, registry, space, baseline_selection
            )
            baseline_key = self._selection_key(baseline_selection, program)
            all_plans[baseline_plan.digest] = baseline_plan
            full_anchors.insert(0, dict(baseline_selection))

        for round_index, original_budget in enumerate(
            selected_profile.search_rounds, start=1
        ):
            budget = original_budget
            if budget.mode == SearchMode.EXHAUSTIVE:
                budget = replace(
                    budget,
                    evaluation_limit=None,
                    result_limit=space.route_count_upper_bound,
                )
            report = self.search_engine.search(
                space,
                current_beliefs,
                budget,
                anchors=tuple(full_anchors),
            )
            proposals = list(report.proposals)
            if round_index == 1:
                fixed_proposals = [
                    RouteProposal(
                        self._selection_key(dict(start.selection), program),
                        start.predicted_utility,
                        ((f"history-start:{start.id}", start.predicted_utility),),
                    )
                    for start in initialization_starts
                ]
                if baseline_selection is not None:
                    fixed_proposals.insert(
                        0,
                        RouteProposal(
                            self._selection_key(baseline_selection, program),
                            float("-inf"),
                            (("fixed-baseline", 0.0),),
                        ),
                    )
                proposals = fixed_proposals + proposals

            new_plans: dict[str, FrozenPlan] = {}
            for proposal in proposals:
                key = self._selection_key(proposal.selection, program)
                if key in evaluated_selections:
                    continue
                plan = self.compiler.compile(program, registry, space, dict(key))
                evaluated_selections.add(key)
                all_plans[plan.digest] = plan
                new_plans[plan.digest] = plan

            if not new_plans:
                rounds.append(
                    SolverRound(
                        index=round_index,
                        search_report=report,
                        plan_digests=(),
                        receipt_ids=(),
                        belief_revision_before=current_beliefs.revision,
                        belief_revision_after=current_beliefs.revision,
                    )
                )
                continue

            control_digest = ""
            if baseline_key is not None:
                for digest, plan in new_plans.items():
                    if self._plan_selection(plan) == baseline_key:
                        control_digest = digest
                        break
            design = ExperimentDesign(
                id=f"experiment.solver-{program.id.replace('.', '-')}.round-{round_index}",
                task_case_ids=tuple(development_case_map),
                plan_digests=tuple(new_plans),
                seeds=selected_profile.seeds,
                repetitions=selected_profile.repetitions,
                objectives=objectives,
                control_plan_digest=control_digest,
                holdout_case_ids=(),
            )
            experiment = ExperimentRunner(self.executor).run(
                design,
                plans=new_plans,
                cases=case_map,
                program=program,
                registry=registry,
                space=space,
                policy=policy,
                artifact_store_factory=artifact_store_factory,
                receipt_sink=receipt_sink,
                belief_revision=current_beliefs.revision,
            )
            ledger = ledger.append(*experiment.ledger.receipts)
            revision = self._belief_revision(program, ledger, round_index)
            next_beliefs = learn_observational_beliefs(
                ledger.receipts,
                revision=revision,
                interactions=tuple(
                    (left.id, right.id)
                    for left, right in zip(
                        program.slots, program.slots[1:], strict=False
                    )
                ),
            )
            rounds.append(
                SolverRound(
                    index=round_index,
                    search_report=report,
                    plan_digests=tuple(new_plans),
                    receipt_ids=tuple(
                        receipt.id for receipt in experiment.ledger.receipts
                    ),
                    belief_revision_before=current_beliefs.revision,
                    belief_revision_after=next_beliefs.revision,
                )
            )
            current_beliefs = next_beliefs
            ranked_so_far = self._rank(
                ledger.aggregates(), all_plans, registry, objectives, selected_profile
            )
            accepted_so_far = tuple(
                item for item in ranked_so_far if item.meets_acceptance_gate
            )
            full_anchors = [
                dict(item.selection) for item in accepted_so_far[:4]
            ] or full_anchors

        development_ledger = ledger
        rankings = self._rank(
            ledger.aggregates(), all_plans, registry, objectives, selected_profile
        )
        development_eligible = tuple(
            ranking
            for ranking in rankings
            if ranking.meets_acceptance_gate and ranking.meets_objective_constraints
        )
        provisional_champion = (
            development_eligible[0].plan_digest if development_eligible else None
        )
        provisional_fallbacks = self._select_fallbacks(
            provisional_champion,
            development_eligible,
            all_plans,
            registry,
            selected_profile.fallback_count,
        )
        confirmation_shortlist = tuple(
            digest
            for digest in (
                provisional_champion,
                *(fallback.plan_digest for fallback in provisional_fallbacks),
            )
            if digest is not None
        )
        confirmed_digests: tuple[str, ...] = ()
        holdout_receipt_ids: tuple[str, ...] = ()
        if holdout_case_ids and confirmation_shortlist:
            holdout_design = ExperimentDesign(
                id=f"experiment.solver-{program.id.replace('.', '-')}.holdout",
                task_case_ids=holdout_case_ids,
                plan_digests=confirmation_shortlist,
                seeds=selected_profile.seeds,
                repetitions=selected_profile.repetitions,
                objectives=objectives,
                holdout_case_ids=holdout_case_ids,
            )
            holdout_result = ExperimentRunner(self.executor).run(
                holdout_design,
                plans={
                    digest: all_plans[digest] for digest in confirmation_shortlist
                },
                cases=case_map,
                program=program,
                registry=registry,
                space=space,
                policy=policy,
                artifact_store_factory=artifact_store_factory,
                receipt_sink=receipt_sink,
                belief_revision=current_beliefs.revision,
            )
            ledger = ledger.append(*holdout_result.ledger.receipts)
            holdout_receipt_ids = tuple(
                receipt.id for receipt in holdout_result.ledger.receipts
            )
            holdout_rankings = self._rank(
                holdout_result.aggregates,
                all_plans,
                registry,
                objectives,
                selected_profile,
            )
            confirmed_set = {
                ranking.plan_digest
                for ranking in holdout_rankings
                if ranking.meets_acceptance_gate
                and ranking.meets_objective_constraints
            }
            development_eligible = tuple(
                ranking
                for ranking in development_eligible
                if ranking.plan_digest in confirmed_set
            )
            confirmed_digests = tuple(
                ranking.plan_digest for ranking in development_eligible
            )

        champion_digest = (
            development_eligible[0].plan_digest if development_eligible else None
        )
        fallback_routes = self._select_fallbacks(
            champion_digest,
            development_eligible,
            all_plans,
            registry,
            selected_profile.fallback_count,
        )
        pareto = tuple(
            item.plan_digest for item in pareto_front(ledger.aggregates(), objectives)
        )
        return SolverResult(
            status=(
                "solved"
                if champion_digest
                else (
                    "no-holdout-confirmed-route"
                    if holdout_case_ids and provisional_champion
                    else "no-accepted-route"
                )
            ),
            profile=selected_profile,
            program_digest=program.digest,
            registry_digest=registry.digest,
            admitted_space=space,
            rounds=tuple(rounds),
            plans=all_plans,
            ledger=ledger,
            rankings=rankings,
            champion_plan_digest=champion_digest,
            fallbacks=fallback_routes,
            pareto_plan_digests=pareto,
            development_receipt_ids=tuple(
                receipt.id for receipt in development_ledger.receipts
            ),
            holdout_receipt_ids=holdout_receipt_ids,
            holdout_confirmed_plan_digests=confirmed_digests,
            initial_beliefs=initial_beliefs,
            learned_beliefs=current_beliefs,
            search_initialization_digest=(
                initialization.digest if initialization is not None else ""
            ),
        )

    @staticmethod
    def _selection_key(
        selection: Mapping[str, str], program: ProgramGraph
    ) -> tuple[tuple[str, str], ...]:
        return tuple((slot.id, selection[slot.id]) for slot in program.slots)

    @staticmethod
    def _plan_selection(plan: FrozenPlan) -> tuple[tuple[str, str], ...]:
        by_slot = {binding.slot_id: binding.candidate_id for binding in plan.bindings}
        return tuple((slot, by_slot[slot]) for slot in plan.topological_order)

    @staticmethod
    def _belief_revision(
        program: ProgramGraph, ledger: EvidenceLedger, round_index: int
    ) -> str:
        digest = sha256_digest(
            {
                "program_digest": program.digest,
                "round": round_index,
                "receipts": [
                    {
                        "id": receipt.id,
                        "accepted": receipt.accepted,
                        "assignments": dict(receipt.assignments),
                    }
                    for receipt in ledger.receipts
                ],
            }
        ).removeprefix("sha256:")[:16]
        return f"solver.observational-{digest}"

    @staticmethod
    def _rank(
        aggregates: tuple[RouteAggregate, ...],
        plans: Mapping[str, FrozenPlan],
        registry: Registry,
        objectives: tuple[Objective, ...],
        profile: SolverProfile,
    ) -> tuple[RankedRoute, ...]:
        del registry  # reserved for future resource/cost normalization policies
        constraint_ok = {
            aggregate.plan_digest: all(
                objective.metric in aggregate.metric_means
                and (
                    objective.hard_minimum is None
                    or aggregate.metric_means[objective.metric]
                    >= objective.hard_minimum
                )
                and (
                    objective.hard_maximum is None
                    or aggregate.metric_means[objective.metric]
                    <= objective.hard_maximum
                )
                for objective in objectives
            )
            for aggregate in aggregates
        }
        eligible_for_normalization = tuple(
            aggregate
            for aggregate in aggregates
            if aggregate.acceptance_rate >= profile.minimum_acceptance_rate
            and constraint_ok[aggregate.plan_digest]
        )
        bounds: dict[str, tuple[float, float]] = {}
        for objective in objectives:
            values = [
                aggregate.metric_means[objective.metric]
                for aggregate in eligible_for_normalization
                if objective.metric in aggregate.metric_means
            ]
            if values:
                bounds[objective.metric] = (min(values), max(values))

        weight_total = sum(objective.weight for objective in objectives)
        pareto_digests = {
            item.plan_digest for item in pareto_front(aggregates, objectives)
        }
        unranked: list[RankedRoute] = []
        for aggregate in aggregates:
            gate = aggregate.acceptance_rate >= profile.minimum_acceptance_rate
            score_parts: list[tuple[float, float]] = []
            for objective in objectives:
                value = aggregate.metric_means.get(objective.metric)
                bound = bounds.get(objective.metric)
                if value is None or bound is None:
                    normalized = 0.0
                elif bound[0] == bound[1]:
                    normalized = 1.0
                elif objective.direction == "maximize":
                    normalized = (value - bound[0]) / (bound[1] - bound[0])
                else:
                    normalized = (bound[1] - value) / (bound[1] - bound[0])
                score_parts.append((objective.weight, normalized))
            score = (
                sum(weight * value for weight, value in score_parts) / weight_total
                if weight_total > 0
                else 0.0
            )
            if not gate or not constraint_ok[aggregate.plan_digest]:
                score = 0.0
            plan = plans[aggregate.plan_digest]
            unranked.append(
                RankedRoute(
                    rank=0,
                    plan_digest=aggregate.plan_digest,
                    selection=UniversalSolver._plan_selection(plan),
                    acceptance_rate=aggregate.acceptance_rate,
                    accepted_runs=aggregate.accepted_runs,
                    runs=aggregate.runs,
                    objective_means={
                        objective.metric: aggregate.metric_means[objective.metric]
                        for objective in objectives
                        if objective.metric in aggregate.metric_means
                    },
                    objective_variances={
                        objective.metric: aggregate.metric_variances[objective.metric]
                        for objective in objectives
                        if objective.metric in aggregate.metric_variances
                    },
                    weighted_score=score,
                    meets_acceptance_gate=gate,
                    meets_objective_constraints=constraint_ok[aggregate.plan_digest],
                    pareto=aggregate.plan_digest in pareto_digests,
                )
            )
        ordered = sorted(
            unranked,
            key=lambda item: (
                not (item.meets_acceptance_gate and item.meets_objective_constraints),
                -item.weighted_score,
                -item.acceptance_rate,
                item.plan_digest,
            ),
        )
        return tuple(replace(item, rank=index) for index, item in enumerate(ordered, 1))

    @staticmethod
    def _select_fallbacks(
        champion_digest: str | None,
        eligible: tuple[RankedRoute, ...],
        plans: Mapping[str, FrozenPlan],
        registry: Registry,
        count: int,
    ) -> tuple[FallbackRoute, ...]:
        if champion_digest is None or count == 0:
            return ()
        ranking_by_digest = {item.plan_digest: item for item in eligible}
        remaining = [
            item.plan_digest
            for item in eligible
            if item.plan_digest != champion_digest
        ]
        selected = [champion_digest]
        fallbacks: list[FallbackRoute] = []
        while remaining and len(fallbacks) < count:
            scored: list[tuple[float, str, tuple[float, float, float, float]]] = []
            for digest in remaining:
                diversities = [
                    UniversalSolver._route_diversity(
                        plans[digest], plans[chosen], registry
                    )
                    for chosen in selected
                ]
                minimum = min(diversities, key=lambda values: values[0])
                evidence = ranking_by_digest[digest].weighted_score
                selection_score = 0.75 * evidence + 0.25 * minimum[0]
                scored.append((selection_score, digest, minimum))
            selection_score, digest, diversity = max(
                scored, key=lambda item: (item[0], item[2][0], item[1])
            )
            fallbacks.append(
                FallbackRoute(
                    priority=len(fallbacks) + 1,
                    plan_digest=digest,
                    evidence_score=ranking_by_digest[digest].weighted_score,
                    diversity_score=diversity[0],
                    selection_score=selection_score,
                    candidate_diversity=diversity[1],
                    implementation_diversity=diversity[2],
                    failure_mode_diversity=diversity[3],
                )
            )
            selected.append(digest)
            remaining.remove(digest)
        return tuple(fallbacks)

    @staticmethod
    def _route_diversity(
        left: FrozenPlan, right: FrozenPlan, registry: Registry
    ) -> tuple[float, float, float, float]:
        left_bindings = {binding.slot_id: binding for binding in left.bindings}
        right_bindings = {binding.slot_id: binding for binding in right.bindings}
        slots = sorted(set(left_bindings) & set(right_bindings))
        if not slots:
            return (1.0, 1.0, 1.0, 1.0)
        candidate = sum(
            left_bindings[slot].candidate_id != right_bindings[slot].candidate_id
            for slot in slots
        ) / len(slots)
        implementation = sum(
            left_bindings[slot].implementation_digest
            != right_bindings[slot].implementation_digest
            for slot in slots
        ) / len(slots)
        nodes = registry.node_map()
        failure_values: list[float] = []
        for slot in slots:
            left_binding = left_bindings[slot]
            right_binding = right_bindings[slot]
            left_modes = {
                mode.code
                for mode in nodes[(left_binding.node_id, left_binding.node_version)].failure_modes
            }
            right_modes = {
                mode.code
                for mode in nodes[(right_binding.node_id, right_binding.node_version)].failure_modes
            }
            union = left_modes | right_modes
            failure_values.append(
                1.0 - len(left_modes & right_modes) / len(union) if union else 0.0
            )
        failure = sum(failure_values) / len(failure_values)
        combined = 0.5 * candidate + 0.3 * implementation + 0.2 * failure
        return combined, candidate, implementation, failure


__all__ = [
    "BALANCED_PROFILE",
    "BROAD_PROFILE",
    "EXHAUSTIVE_PROFILE",
    "FallbackRoute",
    "QUICK_PROFILE",
    "RankedRoute",
    "SOLVER_MODEL_VERSION",
    "SOLVER_PROFILES",
    "SolverProfile",
    "SolverResult",
    "SolverRound",
    "UniversalSolver",
    "get_solver_profile",
]
