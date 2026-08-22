from __future__ import annotations

import json

from solutiongraph.proposal_space import (
    ContextBundle,
    ContextExposure,
    ProposalKind,
    default_kaggle_question_space,
)
from solutiongraph.proposal_swarm import (
    ModelEndpoint,
    ProposalCampaignPolicy,
    ProposalCampaignState,
    ProposalJudgment,
    ProposalSwarmEngine,
    RecordedLanguageModelAdapter,
    SwarmBudget,
    SwarmPattern,
    SwarmPlanner,
    aggregate_judgments,
    pareto_proposal_ids,
)


def _response(title: str = "Leakage audit") -> str:
    return json.dumps({
        "kind": ProposalKind.DIAGNOSTIC.value,
        "title": title,
        "rationale": "Validation can be optimistic when related rows cross folds.",
        "hypothesis": "Group folds will better estimate private performance.",
        "target_ref": "graph.current",
        "payload": {
            "findings": ["possible group leakage"],
            "evidence_needed": ["group overlap matrix"],
            "priority_order": ["identify groups", "rebuild folds"],
        },
        "confidence": 0.8,
        "uncertainty": 0.3,
        "evidence_refs": [],
        "parent_proposal_ids": [],
        "risk_flags": ["risk.validation-mismatch"],
    })


def _endpoints() -> tuple[ModelEndpoint, ...]:
    return (
        ModelEndpoint("model-endpoint.primary", "adapter.recorded", "model-a"),
        ModelEndpoint("model-endpoint.secondary", "adapter.recorded", "model-b"),
    )


def test_blind_full_hybrid_plan_has_three_distinct_context_lanes() -> None:
    space = default_kaggle_question_space()
    questions = tuple(space.iter_variants(limit=2, seed=2))
    plan = SwarmPlanner().plan(
        plan_id="swarm-plan.fixture",
        pattern=SwarmPattern.BLIND_FULL_HYBRID,
        endpoints=_endpoints(),
        questions=questions,
        budget=SwarmBudget(max_requests=6, max_parallel=3, max_failures=2),
        question_space_digest=space.digest,
        random_seed=2,
    )
    assert len(plan.lanes) == 6
    assert len({lane.id for lane in plan.lanes}) == 6
    assert {lane.question.context_exposure for lane in plan.lanes} == {
        ContextExposure.NONE,
        ContextExposure.HYBRID,
        ContextExposure.FULL,
    }


def test_swarm_run_preserves_hidden_context_and_deduplicates_proposals() -> None:
    space = default_kaggle_question_space()
    questions = tuple(space.iter_variants(limit=2, seed=4))
    plan = SwarmPlanner().plan(
        plan_id="swarm-plan.run-fixture",
        pattern=SwarmPattern.BLIND_FULL_HYBRID,
        endpoints=_endpoints(),
        questions=questions,
        budget=SwarmBudget(max_requests=6, max_parallel=2, max_failures=2),
        question_space_digest=space.digest,
        random_seed=4,
    )
    adapter = RecordedLanguageModelAdapter(
        "adapter.recorded", responses={}, default_response=_response()
    )
    context = ContextBundle(
        "context.fixture",
        sections=(
            ("task", "predict a binary target"),
            ("graph_summary", "baseline -> features -> model"),
            ("failures", "group split not tested"),
        ),
        hidden_sections=(("private_holdout", "SECRET TARGETS"),),
    )
    receipt = ProposalSwarmEngine().run(
        plan, context, {"adapter.recorded": adapter}
    )
    assert receipt.attempted_requests == 6
    assert receipt.failures == 0
    assert len(receipt.proposals) == 1
    assert len(receipt.duplicate_proposals) == 5
    assert all("SECRET TARGETS" not in request.user_prompt for request in adapter.requests)


def test_swarm_cost_budget_is_enforced_before_scheduling_more_work() -> None:
    space = default_kaggle_question_space()
    questions = tuple(space.iter_variants(limit=6, seed=8))
    expensive = (
        ModelEndpoint(
            "model-endpoint.expensive", "adapter.recorded", "model-a",
            cost_units_per_request=1.0,
        ),
    )
    plan = SwarmPlanner().plan(
        plan_id="swarm-plan.cost-fixture",
        pattern=SwarmPattern.INDEPENDENT,
        endpoints=expensive,
        questions=questions,
        budget=SwarmBudget(
            max_requests=6, max_parallel=3, max_failures=1, max_cost_units=2.5
        ),
        question_space_digest=space.digest,
    )
    adapter = RecordedLanguageModelAdapter(
        "adapter.recorded", responses={}, default_response=_response()
    )
    receipt = ProposalSwarmEngine().run(
        plan, ContextBundle("context.cost", (("task", "predict"),)),
        {"adapter.recorded": adapter},
    )
    assert receipt.attempted_requests == 2
    assert receipt.cost_units == 2.0


def test_panel_preserves_disagreement_and_pareto_front() -> None:
    judgments = (
        ProposalJudgment(
            "judgment.a", "proposal.a", "judge.a",
            {"quality": 0.9, "cost": 0.4}, "support", "strong local lift", 0.9,
        ),
        ProposalJudgment(
            "judgment.b", "proposal.a", "judge.b",
            {"quality": 0.5, "cost": 0.2}, "review", "uncertain robustness", 0.6,
        ),
    )
    report_a = aggregate_judgments(judgments)
    report_b = aggregate_judgments((
        ProposalJudgment(
            "judgment.c", "proposal.b", "judge.c",
            {"quality": 0.6, "cost": 0.1}, "support", "cheap reliable baseline", 0.7,
        ),
    ))
    assert dict(report_a.disagreement)["quality"] > 0
    assert report_a.independent_judges == 2
    assert pareto_proposal_ids(
        (report_a, report_b), {"quality": "maximize", "cost": "minimize"}
    ) == ("proposal.a", "proposal.b")


def test_campaign_stops_after_novelty_patience() -> None:
    policy = ProposalCampaignPolicy(max_rounds=10, questions_per_round=2, novelty_patience=2)
    question = default_kaggle_question_space().variant_at(1)
    state = ProposalCampaignState()
    state = state.observe(question, "model-endpoint.primary", 0.5, ("proposal.one",))
    assert not state.should_stop(policy)
    state = state.observe(question, "model-endpoint.primary", 0.0, ())
    state = state.observe(question, "model-endpoint.primary", 0.0, ())
    assert state.should_stop(policy)
