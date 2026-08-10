from __future__ import annotations

import json
from pathlib import Path

import pytest

from solutiongraph import (
    CampaignBudget,
    CampaignDecision,
    CampaignLedger,
    CandidateRecord,
    EvaluationBoundary,
    sha256_digest,
)
from solutiongraph.schemas import SCHEMA_NAMES, load_all_schemas
from solutiongraph.template_library import REFERENCE_TEMPLATES


def test_campaign_budget_and_evaluation_boundary_make_limits_and_trust_explicit():
    budget = CampaignBudget(
        max_candidates=40,
        max_trials=120,
        max_parallel_trials=8,
        max_failures=12,
        max_wall_seconds=3600,
        max_cost_units=100,
        fidelity_rungs=(1.0, 3.0, 9.0),
        random_seed=42,
    )
    assert budget.validate() == []
    assert budget.to_dict()["fidelity_rungs"] == [1.0, 3.0, 9.0]

    boundary = EvaluationBoundary(
        id="evaluation.hidden-holdout",
        evaluator_digest=sha256_digest("fixed evaluator"),
        dataset_digest=sha256_digest("fixed split"),
        environment_digest=sha256_digest("reference environment"),
        hidden_case_ids=("case.holdout",),
    )
    assert boundary.validate() == []

    unsafe = EvaluationBoundary(
        id="evaluation.unsafe",
        evaluator_digest=sha256_digest("evaluator"),
        dataset_digest=sha256_digest("data"),
        environment_digest=sha256_digest("environment"),
        candidate_isolation="subprocess",
        candidate_can_read_evaluator=True,
        hidden_case_ids=("case.hidden",),
    )
    problems = unsafe.validate()
    assert any("candidate-unreadable" in problem for problem in problems)
    assert any("untrusted candidates" in problem for problem in problems)

    plain_container = EvaluationBoundary(
        id="evaluation.plain-container",
        evaluator_digest=sha256_digest("evaluator"),
        dataset_digest=sha256_digest("data"),
        environment_digest=sha256_digest("environment"),
        candidate_isolation="container",
    )
    assert any("plain container" in problem for problem in plain_container.validate())


def test_campaign_ledger_preserves_population_ancestry_and_evidence_decisions():
    seed = CandidateRecord(
        id="campaign-candidate.seed",
        plan_digest=sha256_digest("seed plan"),
        parent_ids=(),
        generation=0,
        operator="proposal.seed",
        hypothesis="Establish the fixed baseline.",
    )
    child = CandidateRecord(
        id="campaign-candidate.child",
        plan_digest=sha256_digest("child plan"),
        parent_ids=(seed.id,),
        generation=1,
        operator="proposal.mutation",
        hypothesis="Replace one admitted factorization candidate.",
        proposer="agent.reference",
        proposal_digest=sha256_digest("proposal patch"),
    )
    ledger = CampaignLedger().append_candidate(seed).append_candidate(child)
    assert ledger.ancestors(child.id) == (seed,)
    assert ledger.frontier() == (seed, child)

    decision = CampaignDecision(
        id="campaign-decision.reject-seed",
        candidate_id=seed.id,
        decision="reject",
        reason="The independent verifier rejected the holdout output.",
        receipt_ids=("run.campaign.seed",),
    )
    ledger = ledger.append_decision(decision)
    assert ledger.frontier() == (child,)
    assert ledger.to_dict()["candidates"][1]["parent_ids"] == [seed.id]

    orphan = CandidateRecord(
        id="campaign-candidate.orphan",
        plan_digest=sha256_digest("orphan plan"),
        parent_ids=("campaign-candidate.missing",),
        generation=1,
        operator="proposal.mutation",
        hypothesis="This must not be admitted without its parent.",
    )
    with pytest.raises(ValueError, match="parents must already exist"):
        ledger.append_candidate(orphan)


def test_campaign_wire_schemas_and_research_inventory_are_strict_documents():
    expected = {
        "campaign-budget.schema.json",
        "evaluation-boundary.schema.json",
        "candidate-record.schema.json",
        "campaign-ledger.schema.json",
    }
    assert expected.issubset(SCHEMA_NAMES)
    schemas = load_all_schemas()
    assert all(schemas[name]["additionalProperties"] is False for name in expected)

    landscape = json.loads(
        Path("research/package-landscape.json").read_text(encoding="utf-8")
    )
    assert landscape["policy"] == "reference-not-dependency"
    assert len(landscape["projects"]) >= 8
    assert len({project["id"] for project in landscape["projects"]}) == len(
        landscape["projects"]
    )


def test_numerical_template_decomposes_solver_choice_and_verification():
    template = next(
        item
        for item in REFERENCE_TEMPLATES.templates
        if item.id == "template.numerical-linear-system"
    )
    slot_ids = {slot.id for slot in template.program.slots}
    assert {
        "check_positive_definite",
        "estimate_condition",
        "numeric_factorization",
        "compute_residual",
        "select_fallback",
    }.issubset(slot_ids)
    assert template.validate() == []
