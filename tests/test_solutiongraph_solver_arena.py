from __future__ import annotations

import json
from dataclasses import replace

import pytest

from solutiongraph import (
    EXHAUSTIVE_PROFILE,
    SOLVER_PROFILES,
    UNIVERSAL_DAG_ARENA,
    UniversalSolver,
    get_solver_profile,
)
from solutiongraph.arena import run_arena, solve_example
from solutiongraph.examples import all_examples, get_example
from solutiongraph.schemas import SCHEMA_NAMES, load_all_schemas


def test_arena_is_valid_cross_domain_and_honest_about_external_authorities():
    assert UNIVERSAL_DAG_ARENA.validate() == []
    assert len(UNIVERSAL_DAG_ARENA.tasks) >= 24
    ids = {task.id for task in UNIVERSAL_DAG_ARENA.tasks}
    assert {
        "arena.golden-customer-table",
        "arena.usps-address-verification",
        "arena.verified-product-scrape",
        "arena.invoice-accounting-schema",
        "arena.image-assurance",
        "arena.tabular-prediction",
        "arena.calibrated-forecast",
        "arena.organization-entity-graph",
        "arena.repository-repair",
        "arena.validated-analytical-dataset",
        "arena.transaction-reconciliation",
        "arena.pii-redaction",
        "arena.incident-triage",
        "arena.deployment-release",
    }.issubset(ids)

    address = UNIVERSAL_DAG_ARENA.get("arena.usps-address-verification")
    assert address.readiness == "executable_fixture"
    assert address.executable_example_ids == ("address-reference-verification",)
    assert any("not USPS" in requirement for requirement in address.external_requirements)
    production = UNIVERSAL_DAG_ARENA.get("arena.deployment-release")
    assert production.readiness == "credentialed_connector"
    assert not production.executable_example_ids


def test_every_arena_executable_points_to_a_real_typed_example():
    examples = {example.id: example for example in all_examples()}
    executable_tasks = UNIVERSAL_DAG_ARENA.matching(readiness="executable_fixture")
    assert len(executable_tasks) == 36
    for task in executable_tasks:
        for example_id in task.executable_example_ids:
            example = examples[example_id]
            space, plans = example.compile()
            assert plans
            assert all(space.choices_for(slot.id) for slot in example.program.slots)


def test_balanced_solver_learns_from_receipts_and_selects_benchmarked_fallbacks():
    example = get_example("golden-customer-table")
    result = UniversalSolver().solve(
        example.program,
        example.registry,
        cases=(example.case,),
        objectives=example.objectives,
        policy=example.policy,
        profile="balanced",
        baseline_selection=example.routes[0].selection,
    )

    assert result.status == "solved"
    assert result.admitted_space.route_count_upper_bound == 16
    assert len(result.rounds) == 2
    assert result.rounds[0].search_report.mode.value == "prior"
    assert result.rounds[1].search_report.mode.value == "beam"
    assert result.learned_beliefs.revision != result.initial_beliefs.revision
    assert result.champion is not None
    assert result.rankings[0].plan_digest == result.champion_plan_digest
    assert result.rankings[0].acceptance_rate == 1.0
    assert result.rankings[0].meets_objective_constraints
    assert all(fallback.plan_digest in result.plans for fallback in result.fallbacks)
    assert all(fallback.plan_digest != result.champion_plan_digest for fallback in result.fallbacks)
    assert len(result.ledger.receipts) == len(result.plans)
    payload = result.to_dict()
    assert payload["route_count_upper_bound"] == 16
    assert len(payload["receipts"]) == len(result.ledger.receipts)
    json.dumps(payload)


def test_exhaustive_solver_has_no_hidden_cap_and_requires_explicit_authority():
    example = get_example("address-reference-verification")
    solver = UniversalSolver()
    arguments = {
        "cases": (example.case,),
        "objectives": example.objectives,
        "policy": example.policy,
        "profile": EXHAUSTIVE_PROFILE,
        "baseline_selection": example.routes[0].selection,
    }
    with pytest.raises(ValueError, match="allow_exhaustive=True"):
        solver.solve(example.program, example.registry, **arguments)

    result = solver.solve(
        example.program,
        example.registry,
        allow_exhaustive=True,
        **arguments,
    )
    assert result.admitted_space.route_count_upper_bound == 8
    assert len(result.plans) == 8
    assert len(result.ledger.receipts) == 8
    report = result.rounds[0].search_report
    assert report.complete and report.optimality_proven
    assert report.evaluated_routes == report.total_cartesian_routes == 8


def test_holdouts_confirm_only_the_development_selected_shortlist_without_learning():
    example = get_example("organization-entity-linking")
    holdout = replace(example.case, id="case.organization-entity-linking-holdout")
    result = UniversalSolver().solve(
        example.program,
        example.registry,
        cases=(example.case, holdout),
        holdout_case_ids=(holdout.id,),
        objectives=example.objectives,
        policy=example.policy,
        profile="balanced",
        baseline_selection=example.routes[0].selection,
    )
    receipt_by_id = {receipt.id: receipt for receipt in result.ledger.receipts}
    round_receipt_ids = {
        receipt_id for round_ in result.rounds for receipt_id in round_.receipt_ids
    }
    assert all(
        receipt_by_id[receipt_id].task_case_id == example.case.id
        for receipt_id in round_receipt_ids
    )
    assert result.holdout_receipt_ids
    assert not round_receipt_ids.intersection(result.holdout_receipt_ids)
    assert all(
        receipt_by_id[receipt_id].task_case_id == holdout.id
        for receipt_id in result.holdout_receipt_ids
    )
    assert result.champion_plan_digest in result.holdout_confirmed_plan_digests
    assert max(weight.evidence_count for weight in result.learned_beliefs.candidate_weights) <= len(
        result.development_receipt_ids
    )


def test_solver_profiles_and_arena_runner_disclose_budgets_and_skips():
    assert set(SOLVER_PROFILES) == {"quick", "balanced", "broad", "exhaustive"}
    assert get_solver_profile("broad").search_rounds[-1].mode.value == "sprout"
    with pytest.raises(ValueError, match="unknown solver profile"):
        get_solver_profile("secret-unbounded-mode")

    fixture = solve_example("organization-entity-linking", profile="quick")
    assert fixture["result"]["status"] == "solved"
    report = run_arena(
        ("arena.organization-entity-graph", "arena.transaction-reconciliation"),
        profile="quick",
    )
    assert report["executed_example_count"] == 2
    assert report["skipped_task_count"] == 0
    assert report["skipped"] == []


def test_arena_and_solver_wire_schemas_are_bundled_and_strict():
    assert {"arena-task.schema.json", "solver-result.schema.json"}.issubset(SCHEMA_NAMES)
    schemas = load_all_schemas()
    assert schemas["arena-task.schema.json"]["additionalProperties"] is False
    assert schemas["solver-result.schema.json"]["additionalProperties"] is False
    assert schemas["solver-result.schema.json"]["$defs"]["ranking"]["additionalProperties"] is False
