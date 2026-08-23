"""Strategy allocation, proposal reconciliation, and the recursive Solver Cell.

The engine chooses proposals; it does not compile or execute graphs.  The
SolverCell delegates selected actions through an ActionExecutor and updates an
immutable KnowledgeState through a StateReducer.  Loop ordinals are receipts,
never semantic graph positions.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from math import isfinite
from statistics import fmean
from typing import Any, Protocol

from solutiongraph.model import ID_RE, sha256_digest
from solutiongraph.nexting.contracts import (
    CORE_ACTION_KINDS,
    ActionResult,
    DecisionPolicy,
    KnowledgeState,
    LoopIterationReceipt,
    NextActionProposal,
    NextBudget,
    NextDecision,
    NextDecisionReceipt,
    NextQuestion,
    ProposalCluster,
    SolverCellReceipt,
    StrategyOutcome,
)
from solutiongraph.nexting.strategies import (
    NextStrategy,
    StrategyContext,
    StrategyRegistry,
)

ENGINE_MODEL_VERSION = "0.1"


class StrategyBeliefs(Protocol):
    def score_strategy(self, strategy_id: str) -> float: ...


@dataclass(frozen=True)
class StrategySelectionPolicy:
    id: str = "next.selection.diverse-anytime"
    include_strategy_ids: tuple[str, ...] = ()
    exclude_strategy_ids: tuple[str, ...] = ()
    required_families: tuple[str, ...] = ()
    maximum_per_family: int | None = None
    exploration_weight: float = 0.25
    uncertainty_weight: float = 0.25

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("strategy selection policy id must be namespaced")
        for label, values in (
            ("include_strategy_ids", self.include_strategy_ids),
            ("exclude_strategy_ids", self.exclude_strategy_ids),
            ("required_families", self.required_families),
        ):
            if len(values) != len(set(values)):
                problems.append(f"{label} must be unique")
            if any(not ID_RE.fullmatch(item) for item in values):
                problems.append(f"{label} must contain namespaced identifiers")
        if set(self.include_strategy_ids) & set(self.exclude_strategy_ids):
            problems.append("included and excluded strategy sets must be disjoint")
        if self.maximum_per_family is not None and self.maximum_per_family <= 0:
            problems.append("maximum_per_family must be positive or null")
        for label, value in (
            ("exploration_weight", self.exploration_weight),
            ("uncertainty_weight", self.uncertainty_weight),
        ):
            if not isfinite(value) or value < 0:
                problems.append(f"{label} must be finite and non-negative")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_model_version": ENGINE_MODEL_VERSION,
            "id": self.id,
            "include_strategy_ids": list(self.include_strategy_ids),
            "exclude_strategy_ids": list(self.exclude_strategy_ids),
            "required_families": list(self.required_families),
            "maximum_per_family": self.maximum_per_family,
            "exploration_weight": self.exploration_weight,
            "uncertainty_weight": self.uncertainty_weight,
        }


@dataclass(frozen=True)
class RankedCluster:
    rank: int
    score: float
    cluster: ProposalCluster

    @property
    def digest(self) -> str:
        return sha256_digest({
            "rank": self.rank,
            "score": self.score,
            "cluster_digest": self.cluster.digest,
        })


@dataclass(frozen=True)
class NextEngineResult:
    receipt: NextDecisionReceipt
    ranking: tuple[RankedCluster, ...]

    @property
    def decision(self) -> NextDecision:
        return self.receipt.decision


class WhatIsNextEngine:
    def __init__(self, registry: StrategyRegistry) -> None:
        self.registry = registry

    def decide(
        self,
        state: KnowledgeState,
        question: NextQuestion,
        *,
        budget: NextBudget | None = None,
        selection_policy: StrategySelectionPolicy | None = None,
        decision_policy: DecisionPolicy | None = None,
        beliefs: StrategyBeliefs | None = None,
        original_task: str = "",
        simplified_task: str = "",
        graph_summary: str = "",
        recipe_summary: str = "",
        prior_attempts: str = "",
        constraints: str = "",
    ) -> NextDecisionReceipt:
        budget = budget or NextBudget()
        selection_policy = selection_policy or StrategySelectionPolicy()
        decision_policy = decision_policy or DecisionPolicy()
        problems = [*state.validate(), *question.validate(), *budget.validate(),
                    *selection_policy.validate()]
        if question.state_digest != state.digest:
            problems.append("question state digest differs from supplied knowledge state")
        if question.depth > budget.max_depth:
            problems.append("question exceeds the Solver Cell recursion depth budget")
        if problems:
            raise ValueError("invalid What-Is-Next request: " + "; ".join(problems))

        selected, skipped = self._select_strategies(
            selection_policy,
            budget,
            beliefs,
        )
        outcomes = self._run_strategies(
            selected,
            state,
            question,
            budget,
            original_task=original_task,
            simplified_task=simplified_task,
            graph_summary=graph_summary,
            recipe_summary=recipe_summary,
            prior_attempts=prior_attempts,
            constraints=constraints,
        )
        clusters = self._cluster(outcomes)
        ranked = tuple(sorted(
            clusters,
            key=lambda item: (-self._cluster_score(item, decision_policy), item.semantic_identity),
        ))
        decision = self._choose(question, ranked, budget, decision_policy)
        receipt_id = "next-receipt." + sha256_digest({
            "state": state.digest,
            "question": question.digest,
            "strategies": [item.manifest.id for item in selected],
            "outcomes": [item.digest for item in outcomes],
            "decision": decision.digest,
        }).removeprefix("sha256:")[:24]
        return NextDecisionReceipt(
            id=receipt_id,
            state_digest=state.digest,
            question_digest=question.digest,
            budget_digest=budget.digest,
            policy_digest=decision_policy.digest,
            selected_strategy_ids=tuple(item.manifest.id for item in selected),
            skipped_strategy_ids=tuple(item.manifest.id for item in skipped),
            outcomes=outcomes,
            clusters=ranked,
            decision=decision,
        )

    def decide_result(
        self,
        state: KnowledgeState,
        question: NextQuestion,
        **kwargs: Any,
    ) -> NextEngineResult:
        decision_policy = kwargs.get("decision_policy") or DecisionPolicy()
        receipt = self.decide(state, question, **kwargs)
        ranking = tuple(
            RankedCluster(index + 1, self._cluster_score(cluster, decision_policy), cluster)
            for index, cluster in enumerate(receipt.clusters)
        )
        return NextEngineResult(receipt, ranking)

    def _select_strategies(
        self,
        policy: StrategySelectionPolicy,
        budget: NextBudget,
        beliefs: StrategyBeliefs | None,
    ) -> tuple[tuple[NextStrategy, ...], tuple[NextStrategy, ...]]:
        all_strategies = list(self.registry.all())
        by_id = {item.manifest.id: item for item in all_strategies}
        excluded = set(policy.exclude_strategy_ids)
        candidates = [item for item in all_strategies if item.manifest.id not in excluded]
        if policy.include_strategy_ids:
            unknown = sorted(set(policy.include_strategy_ids) - set(by_id))
            if unknown:
                raise ValueError("selection policy references unknown strategies: " + ", ".join(unknown))
            candidates = [by_id[item] for item in policy.include_strategy_ids if item not in excluded]

        required: list[NextStrategy] = []
        for family in policy.required_families:
            family_items = [item for item in candidates if item.manifest.family == family]
            if family_items:
                required.append(sorted(family_items, key=lambda item: item.manifest.id)[0])

        blind_target = int(round(budget.max_strategy_calls * budget.protected_blind_fraction))
        random_target = int(round(budget.max_strategy_calls * budget.protected_random_fraction))
        protected = [
            *sorted((item for item in candidates if item.manifest.blind_lane), key=lambda item: item.manifest.id)[:blind_target],
            *sorted((item for item in candidates if item.manifest.random_lane), key=lambda item: item.manifest.id)[:random_target],
        ]

        def score(strategy: NextStrategy) -> tuple[float, int, str]:
            belief = beliefs.score_strategy(strategy.manifest.id) if beliefs is not None else 0.0
            exploration = policy.exploration_weight if strategy.manifest.random_lane else 0.0
            uncertainty = policy.uncertainty_weight if strategy.manifest.blind_lane else 0.0
            return (belief + exploration + uncertainty - 0.01 * strategy.manifest.cost_tier,
                    -strategy.manifest.cost_tier, strategy.manifest.id)

        ordered = sorted(candidates, key=lambda item: (-score(item)[0], item.manifest.id))
        selected: list[NextStrategy] = []
        family_counts: dict[str, int] = defaultdict(int)
        for strategy in (*required, *protected, *ordered):
            if strategy in selected:
                continue
            family = strategy.manifest.family
            if policy.maximum_per_family is not None and family_counts[family] >= policy.maximum_per_family:
                continue
            selected.append(strategy)
            family_counts[family] += 1
            if len(selected) >= budget.max_strategy_calls:
                break
        selected_ids = {item.manifest.id for item in selected}
        skipped = tuple(item for item in all_strategies if item.manifest.id not in selected_ids)
        return tuple(selected), skipped

    @staticmethod
    def _run_strategies(
        strategies: Sequence[NextStrategy],
        state: KnowledgeState,
        question: NextQuestion,
        budget: NextBudget,
        **context_fields: str,
    ) -> tuple[StrategyOutcome, ...]:
        if not strategies:
            return ()

        def invoke(index: int, strategy: NextStrategy) -> StrategyOutcome:
            context = StrategyContext(
                state=state,
                question=question,
                budget=budget,
                random_seed=budget.random_seed + index,
                **context_fields,
            )
            try:
                return strategy.propose(context)
            except Exception as exc:
                return StrategyOutcome(
                    strategy.manifest.id,
                    question.id,
                    diagnostics=(f"strategy raised {type(exc).__name__}: {exc}",),
                    abstained=True,
                )

        outcomes: dict[str, StrategyOutcome] = {}
        with ThreadPoolExecutor(max_workers=min(budget.max_parallel, len(strategies))) as pool:
            futures = {
                pool.submit(invoke, index, strategy): strategy.manifest.id
                for index, strategy in enumerate(strategies)
            }
            for future in as_completed(futures):
                outcome = future.result()
                outcomes[outcome.strategy_id] = outcome

        ordered: list[StrategyOutcome] = []
        proposal_count = 0
        cost = 0.0
        for strategy in strategies:
            outcome = outcomes[strategy.manifest.id]
            remaining = max(0, budget.max_proposals - proposal_count)
            proposals = outcome.proposals[:remaining]
            if budget.max_cost_units is not None and cost + outcome.cost_units > budget.max_cost_units:
                outcome = replace(
                    outcome,
                    proposals=(),
                    diagnostics=(*outcome.diagnostics, "strategy outcome excluded by cost budget"),
                    abstained=True,
                )
            else:
                outcome = replace(outcome, proposals=proposals)
                cost += outcome.cost_units
                proposal_count += len(proposals)
            ordered.append(outcome)
        return tuple(ordered)

    @staticmethod
    def _cluster(outcomes: Sequence[StrategyOutcome]) -> tuple[ProposalCluster, ...]:
        groups: dict[str, list[NextActionProposal]] = defaultdict(list)
        for outcome in outcomes:
            for proposal in outcome.proposals:
                groups[proposal.semantic_identity].append(proposal)
        clusters: list[ProposalCluster] = []
        for identity, members in groups.items():
            representative = max(
                members,
                key=lambda item: (
                    item.expected_utility + item.expected_information_gain + item.confidence
                    - item.uncertainty - item.expected_cost,
                    item.id,
                ),
            )
            clusters.append(
                ProposalCluster(
                    semantic_identity=identity,
                    representative=representative,
                    member_ids=tuple(sorted(item.id for item in members)),
                    strategy_ids=tuple(sorted({item.strategy_id for item in members})),
                    aggregate_confidence=fmean(item.confidence for item in members),
                    aggregate_uncertainty=fmean(item.uncertainty for item in members),
                )
            )
        return tuple(clusters)

    @staticmethod
    def _cluster_score(cluster: ProposalCluster, policy: DecisionPolicy) -> float:
        item = cluster.representative
        diversity = max(0, len(cluster.strategy_ids) - 1)
        return (
            policy.utility_weight * item.expected_utility
            + policy.information_gain_weight * item.expected_information_gain
            + policy.confidence_weight * cluster.aggregate_confidence
            + policy.priority_weight * item.priority
            + policy.diversity_bonus * diversity
            - policy.uncertainty_penalty * cluster.aggregate_uncertainty
            - policy.cost_penalty * item.expected_cost
        )

    def _choose(
        self,
        question: NextQuestion,
        ranked: Sequence[ProposalCluster],
        budget: NextBudget,
        policy: DecisionPolicy,
    ) -> NextDecision:
        eligible = [item for item in ranked if item.aggregate_confidence >= policy.minimum_confidence]
        if not eligible:
            return NextDecision(
                id=f"decision.{question.id}.defer",
                question_id=question.id,
                disposition="defer",
                selected_proposal_ids=(),
                rationale="No admissible proposal met the decision policy.",
                confidence=0.0,
                ranked_cluster_digests=tuple(item.digest for item in ranked),
            )
        first = eligible[0].representative
        if first.action_kind in ("next.stop", "next.pause"):
            return NextDecision(
                id=f"decision.{question.id}.terminal",
                question_id=question.id,
                disposition="stop",
                selected_proposal_ids=(first.id,),
                rationale=first.rationale,
                confidence=eligible[0].aggregate_confidence,
                ranked_cluster_digests=tuple(item.digest for item in ranked),
            )
        selected = [eligible[0]]
        if policy.allow_parallel and first.parallel_safe:
            occupied = set(first.conflict_keys)
            for cluster in eligible[1:]:
                proposal = cluster.representative
                if len(selected) >= budget.max_actions:
                    break
                if not proposal.parallel_safe or occupied & set(proposal.conflict_keys):
                    continue
                selected.append(cluster)
                occupied.update(proposal.conflict_keys)
        disposition = "parallel" if len(selected) > 1 else "one"
        return NextDecision(
            id=f"decision.{question.id}.{disposition}",
            question_id=question.id,
            disposition=disposition,
            selected_proposal_ids=tuple(item.representative.id for item in selected),
            rationale=(
                "Selected a conflict-free portfolio of ready next actions."
                if len(selected) > 1
                else selected[0].representative.rationale
            ),
            confidence=fmean(item.aggregate_confidence for item in selected),
            ranked_cluster_digests=tuple(item.digest for item in ranked),
        )


class QuestionFactory(Protocol):
    def build(self, state: KnowledgeState, *, iteration: int, depth: int) -> NextQuestion: ...


@dataclass(frozen=True)
class DefaultQuestionFactory:
    scope: str = "scope.problem"
    target_ref: str = ""
    context_policy_id: str = "context.selective"
    allowed_action_kinds: tuple[str, ...] = ()

    def build(self, state: KnowledgeState, *, iteration: int, depth: int) -> NextQuestion:
        return NextQuestion(
            id=f"question.solver-cell-{iteration}",
            state_digest=state.digest,
            scope=self.scope,
            target_ref=self.target_ref,
            context_policy_id=self.context_policy_id,
            recipe_ref=state.recipe_ref,
            depth=depth,
            allowed_action_kinds=self.allowed_action_kinds or CORE_ACTION_KINDS,
        )


class ActionExecutor(Protocol):
    def execute(self, proposal: NextActionProposal, state: KnowledgeState) -> ActionResult: ...


class StateReducer(Protocol):
    def reduce(
        self,
        state: KnowledgeState,
        results: Sequence[ActionResult],
        *,
        iteration: int,
    ) -> KnowledgeState: ...


class AppendOnlyStateReducer:
    """Reference reducer that adds evidence and removes explicitly resolved unknowns."""

    def reduce(
        self,
        state: KnowledgeState,
        results: Sequence[ActionResult],
        *,
        iteration: int,
    ) -> KnowledgeState:
        references = {item.id: item for item in state.references}
        facts = {item.id: item for item in state.facts}
        resolved: set[str] = set()
        for result in results:
            for item in result.produced_references:
                references[item.id] = item
            for item in result.produced_facts:
                facts[item.id] = item
            resolved.update(result.resolved_unknown_ids)
        return replace(
            state,
            revision=f"{state.revision}.{iteration + 1}",
            references=tuple(references[key] for key in sorted(references)),
            facts=tuple(facts[key] for key in sorted(facts)),
            unknowns=tuple(item for item in state.unknowns if item.id not in resolved),
            parent_state_digest=state.digest,
        )


@dataclass(frozen=True)
class SolverCellResult:
    state: KnowledgeState
    receipt: SolverCellReceipt
    decision_receipts: tuple[NextDecisionReceipt, ...]


class SolverCell:
    """Observe, ask What-Is-Next, delegate, record evidence, and repeat."""

    def __init__(
        self,
        engine: WhatIsNextEngine,
        executor: ActionExecutor,
        *,
        reducer: StateReducer | None = None,
        question_factory: QuestionFactory | None = None,
    ) -> None:
        self.engine = engine
        self.executor = executor
        self.reducer = reducer or AppendOnlyStateReducer()
        self.question_factory = question_factory or DefaultQuestionFactory()

    def run(
        self,
        initial_state: KnowledgeState,
        *,
        budget: NextBudget | None = None,
        selection_policy: StrategySelectionPolicy | None = None,
        decision_policy: DecisionPolicy | None = None,
        beliefs: StrategyBeliefs | None = None,
        depth: int = 0,
        original_task: str = "",
        simplified_task: str = "",
        graph_summary: str = "",
        recipe_summary: str = "",
        constraints: str = "",
    ) -> SolverCellResult:
        budget = budget or NextBudget()
        state = initial_state
        decisions: list[NextDecisionReceipt] = []
        iterations: list[LoopIterationReceipt] = []
        no_progress = 0
        terminal = "exhausted"
        reason = "Solver Cell iteration budget exhausted."

        for iteration in range(budget.max_iterations):
            question = self.question_factory.build(state, iteration=iteration, depth=depth)
            receipt = self.engine.decide(
                state,
                question,
                budget=budget,
                selection_policy=selection_policy,
                decision_policy=decision_policy,
                beliefs=beliefs,
                original_task=original_task,
                simplified_task=simplified_task,
                graph_summary=graph_summary,
                recipe_summary=recipe_summary,
                constraints=constraints,
            )
            decisions.append(receipt)
            if receipt.decision.disposition in ("stop", "defer"):
                terminal = "stop" if receipt.decision.disposition == "stop" else "blocked"
                reason = receipt.decision.rationale
                break

            proposal_map = {
                proposal.id: proposal
                for outcome in receipt.outcomes
                for proposal in outcome.proposals
            }
            selected = [proposal_map[item] for item in receipt.decision.selected_proposal_ids]
            if receipt.decision.disposition == "parallel" and len(selected) > 1:
                with ThreadPoolExecutor(max_workers=min(budget.max_parallel, len(selected))) as pool:
                    futures = {pool.submit(self.executor.execute, item, state): item.id for item in selected}
                    result_map = {futures[future]: future.result() for future in as_completed(futures)}
                results = tuple(result_map[item.id] for item in selected)
            else:
                results = tuple(self.executor.execute(item, state) for item in selected)

            next_state = self.reducer.reduce(state, results, iteration=iteration)
            progressed = next_state.digest != state.digest and any(
                result.outcome == "succeeded" for result in results
            )
            no_progress = 0 if progressed else no_progress + 1
            iteration_receipt = LoopIterationReceipt(
                id=f"iteration.solver-cell-{iteration}",
                iteration=iteration,
                prior_state_digest=state.digest,
                decision_receipt_digest=receipt.digest,
                action_results=results,
                next_state_digest=next_state.digest,
                progress_observed=progressed,
            )
            iterations.append(iteration_receipt)
            state = next_state
            if no_progress >= budget.max_no_progress:
                terminal = "blocked"
                reason = "No measurable progress within the configured ceiling."
                break

        cell_receipt = SolverCellReceipt(
            id="solver-cell-receipt." + sha256_digest({
                "initial": initial_state.digest,
                "final": state.digest,
                "iterations": [item.digest for item in iterations],
                "terminal": terminal,
            }).removeprefix("sha256:")[:24],
            initial_state_digest=initial_state.digest,
            final_state_digest=state.digest,
            iteration_receipts=tuple(iterations),
            terminal_disposition=terminal,
            reason=reason,
        )
        return SolverCellResult(state, cell_receipt, tuple(decisions))


__all__ = [
    "ENGINE_MODEL_VERSION", "ActionExecutor", "AppendOnlyStateReducer",
    "DefaultQuestionFactory", "NextEngineResult", "QuestionFactory", "RankedCluster",
    "SolverCell", "SolverCellResult", "StateReducer", "StrategyBeliefs",
    "StrategySelectionPolicy", "WhatIsNextEngine",
]
