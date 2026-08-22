from __future__ import annotations

import pytest

from solutiongraph.kaggle_swarm import (
    CompetitionFormat,
    KaggleCampaignPlanner,
    KaggleCompetitionProfile,
    KaggleExperimentObservation,
    KaggleExperimentPolicy,
    KaggleRewardPolicy,
    MetricDirection,
    SubmissionBudget,
)
from solutiongraph.proposal_space import ContextExposure
from solutiongraph.proposal_swarm import ModelEndpoint


def _profile() -> KaggleCompetitionProfile:
    return KaggleCompetitionProfile(
        id="kaggle.competition.fixture",
        competition_slug="fixture-competition",
        task_statement="Predict a binary target from mixed tabular data.",
        metric_name="roc_auc",
        metric_direction=MetricDirection.MAXIMIZE,
        competition_format=CompetitionFormat.CODE,
        target_columns=("target",),
        id_columns=("id",),
        group_columns=("customer_id",),
        code_competition=True,
        internet_allowed=False,
        external_data_allowed=False,
        maximum_submissions_per_day=5,
        runtime_limit_seconds=32_400,
        gpu_limit="one competition GPU",
    )


def test_profile_and_policy_validate_code_competition_constraints() -> None:
    assert not _profile().validate()
    assert not KaggleExperimentPolicy().validate()
    assert KaggleExperimentPolicy(public_leaderboard_weight=0.11).validate()


def test_default_reward_does_not_learn_from_public_leaderboard() -> None:
    base = dict(
        proposal_id="proposal.fixture",
        question_variant_id="question.variant.fixture",
        model_endpoint_id="model-endpoint.fixture",
        compiler_valid=True,
        executable=True,
        accepted_by_local_oracle=True,
        normalized_local_cv_lift=0.10,
        normalized_holdout_lift=0.08,
        robustness_score=0.8,
        novelty_score=0.4,
        runtime_cost_ratio=1.0,
    )
    positive = KaggleExperimentObservation(
        **base, normalized_public_leaderboard_lift=100.0
    )
    negative = KaggleExperimentObservation(
        **base, normalized_public_leaderboard_lift=-100.0
    )
    reward = KaggleRewardPolicy()
    assert reward.reward(positive, KaggleExperimentPolicy()) == reward.reward(
        negative, KaggleExperimentPolicy()
    )


def test_reward_public_leaderboard_weight_is_capped() -> None:
    with pytest.raises(ValueError, match="cap"):
        KaggleRewardPolicy(public_leaderboard_weight=0.2).reward(
            KaggleExperimentObservation(
                proposal_id="proposal.fixture",
                question_variant_id="question.variant.fixture",
                model_endpoint_id="model-endpoint.fixture",
                compiler_valid=True,
                executable=True,
                accepted_by_local_oracle=True,
            ),
            KaggleExperimentPolicy(),
        )


def test_submission_budget_requires_reservation_and_exact_consumption() -> None:
    budget = SubmissionBudget(3).reserve(2)
    assert budget.remaining == 1
    budget = budget.consume(1)
    assert budget.used == 1
    assert budget.reserved == 1
    budget = budget.release(1)
    assert budget.remaining == 2
    with pytest.raises(ValueError):
        budget.consume(1)


def test_task_reframe_portfolio_mixes_deterministic_and_context_diverse_llm_lanes() -> None:
    endpoints = (
        ModelEndpoint("model-endpoint.one", "adapter.ollama", "model-one"),
        ModelEndpoint("model-endpoint.two", "adapter.ollama", "model-two"),
    )
    portfolio = KaggleCampaignPlanner().build_portfolio(
        _profile(), endpoints, preset_id="kaggle-preset.task-reframe", random_seed=11,
        deterministic_route_trials=40, deterministic_mutation_trials=20,
    )
    assert portfolio.deterministic_route_trials == 40
    assert portfolio.deterministic_mutation_trials == 20
    assert portfolio.submission_budget.maximum_total == 20
    assert len(portfolio.llm_swarm_plan.lanes) == 24
    assert {lane.question.context_exposure for lane in portfolio.llm_swarm_plan.lanes} == {
        ContextExposure.NONE,
        ContextExposure.HYBRID,
        ContextExposure.FULL,
    }


def test_kaggle_context_never_exposes_private_holdout() -> None:
    context = KaggleCampaignPlanner.context(
        _profile(),
        rules="No internet and no external data.",
        graph_summary="baseline graph",
        hidden_holdout="PRIVATE LABELS AND SCORES",
    )
    full = context.project(ContextExposure.FULL)
    assert "baseline graph" in full.text
    assert "PRIVATE LABELS AND SCORES" not in full.text
    assert "internet_allowed=False" in full.text
