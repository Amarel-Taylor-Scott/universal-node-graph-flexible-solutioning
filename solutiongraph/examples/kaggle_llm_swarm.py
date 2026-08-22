"""Offline, deterministic Kaggle proposal-swarm demonstration.

Run with:

    python -m solutiongraph.examples.kaggle_llm_swarm

The fixture uses a recorded model adapter.  Replace it with
``solutiongraph.integrations.ollama.OllamaAdapter`` to call configured local
Ollama models.
"""
from __future__ import annotations

import json

from solutiongraph.kaggle_swarm import (
    CompetitionFormat,
    KaggleCampaignPlanner,
    KaggleCompetitionProfile,
    MetricDirection,
)
from solutiongraph.proposal_space import ProposalKind
from solutiongraph.proposal_swarm import (
    ModelEndpoint,
    ProposalSwarmEngine,
    RecordedLanguageModelAdapter,
)


def main() -> None:
    profile = KaggleCompetitionProfile(
        id="kaggle.competition.example",
        competition_slug="example-tabular",
        task_statement="Predict a binary target from mixed tabular features.",
        metric_name="roc_auc",
        metric_direction=MetricDirection.MAXIMIZE,
        competition_format=CompetitionFormat.CLASSIC,
        target_columns=("target",),
        id_columns=("id",),
        group_columns=("customer_id",),
        internet_allowed=True,
        external_data_allowed=False,
    )
    endpoints = (
        ModelEndpoint("model-endpoint.example-a", "adapter.recorded", "example-a"),
        ModelEndpoint("model-endpoint.example-b", "adapter.recorded", "example-b"),
    )
    planner = KaggleCampaignPlanner()
    portfolio = planner.build_portfolio(
        profile,
        endpoints,
        preset_id="kaggle-preset.task-reframe",
        random_seed=7,
        deterministic_route_trials=16,
        deterministic_mutation_trials=8,
    )
    context = planner.context(
        profile,
        rules="Use only permitted competition data.",
        schema="id: integer; customer_id: integer; target: binary; features: mixed",
        graph_summary="baseline preprocessing -> gradient boosting -> out-of-fold validation",
        failures="No group-aware split has been executed.",
        hidden_holdout="This sealed text is never prompt-visible.",
    )
    recorded = RecordedLanguageModelAdapter(
        "adapter.recorded",
        responses={},
        default_response=json.dumps({
            "kind": ProposalKind.DIAGNOSTIC.value,
            "title": "Test group-aware validation",
            "rationale": "Related customer rows may cross the current folds.",
            "hypothesis": "Group folds will reduce optimistic validation bias.",
            "target_ref": "graph.baseline",
            "payload": {
                "findings": ["group leakage has not been excluded"],
                "evidence_needed": ["row and target overlap by customer_id"],
                "priority_order": ["audit groups", "run paired fold experiment"],
            },
            "confidence": 0.7,
            "uncertainty": 0.4,
            "evidence_refs": [],
            "parent_proposal_ids": [],
            "risk_flags": ["risk.validation-mismatch"],
        }),
    )
    receipt = ProposalSwarmEngine().run(
        portfolio.llm_swarm_plan,
        context,
        {"adapter.recorded": recorded},
    )
    print(json.dumps({
        "portfolio_digest": portfolio.digest,
        "swarm_run_digest": receipt.digest,
        "attempted_requests": receipt.attempted_requests,
        "failures": receipt.failures,
        "distinct_proposals": len(receipt.proposals),
        "duplicates": len(receipt.duplicate_proposals),
        "first_proposal": receipt.proposals[0].to_dict() if receipt.proposals else None,
    }, indent=2))


if __name__ == "__main__":
    main()
