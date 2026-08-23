from __future__ import annotations

from dataclasses import dataclass

from solutiongraph.model import sha256_digest
from solutiongraph.nexting import (
    ActionResult,
    BeliefUpdater,
    ContextExposurePolicy,
    ContextRequest,
    DecisionPolicy,
    DeterministicRuleStrategy,
    KnowledgeFact,
    KnowledgeReference,
    KnowledgeState,
    NextBudget,
    NextBeliefModel,
    PersonaFrame,
    PromptAxis,
    PromptComposer,
    PromptContext,
    PromptVariantSpace,
    Recipe,
    RecipeStep,
    RecipeStrategy,
    Rule,
    SolverCell,
    StrategyEvidence,
    StrategyManifest,
    StrategyRegistry,
    StrategySelectionPolicy,
    Unknown,
    WhatIsNextEngine,
    action_payload_digest,
    validate_action_payload,
)


def _ref(reference_id: str, summary: str = "evidence") -> KnowledgeReference:
    return KnowledgeReference(
        id=reference_id,
        kind="knowledge.test-artifact",
        digest=sha256_digest({"id": reference_id, "summary": summary}),
        summary=summary,
        tags=("knowledge.test",),
    )


def _state(*, unknown: bool = False) -> KnowledgeState:
    return KnowledgeState(
        id="state.nexting-test",
        revision="1",
        goal="Choose a robust next action.",
        references=(_ref("knowledge.task"),),
        unknowns=(
            Unknown(
                id="unknown.validation",
                question="Which validation split is trustworthy?",
                importance=0.9,
                suggested_probe_kinds=("probe.validation",),
            ),
        ) if unknown else (),
    )


def _manifest(strategy_id: str, family: str = "strategy.rules") -> StrategyManifest:
    return StrategyManifest(
        id=strategy_id,
        version="1.0.0",
        family=family,
        description="Focused test strategy.",
        deterministic=True,
    )


def test_typed_action_payload_is_content_addressed() -> None:
    payload = ContextRequest(
        selector_ids=("knowledge.task",),
        reason="Inspect the current task evidence.",
        maximum_bytes=1024,
    )
    assert not validate_action_payload("next.gather-context", payload)
    assert action_payload_digest(payload).startswith("sha256:")
    assert validate_action_payload("next.run-probe", payload)


def test_knowledge_state_digest_is_stable() -> None:
    first = _state(unknown=True)
    second = _state(unknown=True)
    assert first.digest == second.digest
    assert not first.validate()


def test_context_exposure_distinguishes_knowledge_from_prompt_context() -> None:
    state = _state(unknown=True)
    question = __import__("solutiongraph.nexting", fromlist=["NextQuestion"]).NextQuestion(
        id="question.context-test",
        state_digest=state.digest,
    )
    composer = PromptComposer()
    persona = PersonaFrame(id="persona.test")
    _, blind_manifest, blind_prompt = composer.compose(
        PromptContext(state, question, ContextExposurePolicy.blind(), persona)
    )
    _, selective_manifest, selective_prompt = composer.compose(
        PromptContext(state, question, ContextExposurePolicy.selective(), persona)
    )
    assert blind_manifest.included_reference_ids == ()
    assert selective_manifest.included_reference_ids == ("knowledge.task",)
    assert "Which validation split" not in blind_prompt
    assert "Which validation split" in selective_prompt


def test_prompt_variant_space_is_lazy_and_replayable() -> None:
    space = PromptVariantSpace((
        PromptAxis("axis.stance", ("skeptic", "builder")),
        PromptAxis("axis.scale", ("small", "medium", "large")),
    ))
    assert space.cardinality == 6
    assert space.at(0).assignment_map == {
        "axis.stance": "skeptic",
        "axis.scale": "small",
    }
    assert space.sample(3, seed=7) == space.sample(3, seed=7)


def test_recipe_readiness_depends_on_relationships_not_tuple_position() -> None:
    later = RecipeStep(
        id="recipe.train",
        action_kind="next.continue-recipe",
        title="Train baseline",
        rationale="Validation evidence is available.",
        payload={"operation": "train"},
        requires_reference_ids=("knowledge.validation",),
    )
    ready = RecipeStep(
        id="recipe.profile",
        action_kind="next.continue-recipe",
        title="Profile data",
        rationale="No prerequisite is required.",
        payload={"operation": "profile"},
    )
    strategy = RecipeStrategy(
        _manifest("strategy.recipe-test", "strategy.recipe"),
        Recipe("recipe.test", "1.0.0", "Relational recipe", (later, ready)),
    )
    state = _state()
    question_cls = __import__("solutiongraph.nexting", fromlist=["NextQuestion"]).NextQuestion
    outcome = strategy.propose(
        __import__("solutiongraph.nexting", fromlist=["StrategyContext"]).StrategyContext(
            state=state,
            question=question_cls(id="question.recipe-test", state_digest=state.digest),
            budget=NextBudget(),
            random_seed=0,
        )
    )
    assert [item.payload["recipe_step_id"] for item in outcome.proposals] == ["recipe.profile"]


def test_engine_semantically_deduplicates_rule_proposals() -> None:
    rule = Rule(
        id="rule.same-action",
        predicate=lambda _: True,
        action_kind="next.run-probe",
        title="Run the probe",
        rationale="Reduce uncertainty.",
        payload_factory=lambda _: {"probe": "validation"},
        information_gain=0.8,
        utility=0.7,
    )
    strategies = (
        DeterministicRuleStrategy(_manifest("strategy.rule-a"), (rule,)),
        DeterministicRuleStrategy(_manifest("strategy.rule-b"), (rule,)),
    )
    state = _state()
    question_cls = __import__("solutiongraph.nexting", fromlist=["NextQuestion"]).NextQuestion
    receipt = WhatIsNextEngine(StrategyRegistry(strategies)).decide(
        state,
        question_cls(id="question.dedup", state_digest=state.digest),
        budget=NextBudget(max_strategy_calls=2),
        selection_policy=StrategySelectionPolicy(
            include_strategy_ids=("strategy.rule-a", "strategy.rule-b")
        ),
    )
    assert len(receipt.clusters) == 1
    assert receipt.clusters[0].strategy_ids == ("strategy.rule-a", "strategy.rule-b")


def test_engine_can_choose_parallel_nonconflicting_actions() -> None:
    strategy = DeterministicRuleStrategy(
        _manifest("strategy.parallel"),
        (
            Rule(
                id="rule.a",
                predicate=lambda _: True,
                action_kind="next.run-probe",
                title="Probe A",
                rationale="Independent probe A.",
                payload_factory=lambda _: {"probe": "a"},
                information_gain=0.9,
                utility=0.8,
                parallel_safe=True,
                conflict_keys=("resource:a",),
            ),
            Rule(
                id="rule.b",
                predicate=lambda _: True,
                action_kind="next.run-probe",
                title="Probe B",
                rationale="Independent probe B.",
                payload_factory=lambda _: {"probe": "b"},
                information_gain=0.8,
                utility=0.7,
                parallel_safe=True,
                conflict_keys=("resource:b",),
            ),
        ),
    )
    state = _state()
    question_cls = __import__("solutiongraph.nexting", fromlist=["NextQuestion"]).NextQuestion
    receipt = WhatIsNextEngine(StrategyRegistry((strategy,))).decide(
        state,
        question_cls(id="question.parallel", state_digest=state.digest),
        budget=NextBudget(max_strategy_calls=1, max_actions=2),
        decision_policy=DecisionPolicy(allow_parallel=True),
    )
    assert receipt.decision.disposition == "parallel"
    assert len(receipt.decision.selected_proposal_ids) == 2


@dataclass
class ProbeExecutor:
    def execute(self, proposal, state) -> ActionResult:
        if proposal.action_kind != "next.run-probe":
            return ActionResult(proposal.id, "skipped")
        reference = _ref("knowledge.validation", "Grouped split is stable.")
        fact = KnowledgeFact(
            id="fact.validation-known",
            subject="task.test",
            predicate="ml.validation-known",
            value=True,
            evidence_refs=(reference.id,),
        )
        return ActionResult(
            proposal_id=proposal.id,
            outcome="succeeded",
            produced_references=(reference,),
            produced_facts=(fact,),
            resolved_unknown_ids=("unknown.validation",),
        )


def test_solver_cell_repeats_until_new_knowledge_satisfies_goal() -> None:
    strategy = DeterministicRuleStrategy(
        _manifest("strategy.cell"),
        (
            Rule(
                id="rule.probe",
                predicate=lambda context: bool(context.state.unknowns),
                action_kind="next.run-probe",
                title="Probe validation",
                rationale="Validation is unknown.",
                payload_factory=lambda _: {"probe": "validation"},
                information_gain=1.0,
                utility=0.9,
                confidence=1.0,
            ),
            Rule(
                id="rule.stop",
                predicate=lambda context: any(
                    item.predicate == "ml.validation-known" for item in context.state.facts
                ),
                action_kind="next.stop",
                title="Stop",
                rationale="The delegated validation question is resolved.",
                payload_factory=lambda _: {"reason": "goal-satisfied"},
                utility=1.0,
                confidence=1.0,
            ),
        ),
        first_match_only=True,
    )
    result = SolverCell(
        WhatIsNextEngine(StrategyRegistry((strategy,))),
        ProbeExecutor(),
    ).run(
        _state(unknown=True),
        budget=NextBudget(max_strategy_calls=1, max_iterations=4),
        selection_policy=StrategySelectionPolicy(include_strategy_ids=("strategy.cell",)),
    )
    assert result.receipt.terminal_disposition == "stop"
    assert result.state.unknowns == ()
    assert len(result.receipt.iteration_receipts) == 1
    assert len(result.decision_receipts) == 2


def test_beliefs_update_from_external_evidence() -> None:
    model = BeliefUpdater().update(
        NextBeliefModel(),
        (
            StrategyEvidence(
                strategy_id="strategy.good",
                action_kind="next.run-probe",
                reward=0.8,
                accepted=True,
                context_policy_id="context.selective",
                tags=("task.tabular",),
            ),
        ),
        revision="evidence-1",
    )
    assert model.score_strategy("strategy.good") > 0
    assert model.digest.startswith("sha256:")
