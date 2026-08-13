from __future__ import annotations

import json
from collections import Counter

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry as SchemaRegistry
from referencing import Resource

from solutiongraph.catalog import catalog_documents
from solutiongraph.cli import main
from solutiongraph.compiler import Compiler
from solutiongraph.design_atlas import (
    REFERENCE_DESIGN_PACKS,
    REFERENCE_DESIGN_QUESTIONS,
    REFERENCE_SOURCES,
    REFERENCE_TASK_ARCHETYPES,
    REFERENCE_TECHNIQUES,
    CapabilityEvidence,
    DecisionAnswer,
    DesignContext,
    DesignPlanner,
    assess_maturity,
    atlas_index,
    validate_design_atlas,
)
from solutiongraph.design_atlas.node_pack import (
    DESIGN_ATLAS_CANDIDATES,
    DESIGN_ATLAS_DESCRIPTORS,
    DESIGN_ATLAS_NODE_DEFINITIONS,
    DESIGN_ATLAS_NODE_PACK,
    DESIGN_ATLAS_NODE_SPECS,
    DESIGN_ATLAS_PROGRAM,
    DESIGN_ATLAS_REGISTRY,
    design_atlas_program,
)
from solutiongraph.design_atlas.profiling import context_from_records
from solutiongraph.design_atlas.reporting import render_markdown
from solutiongraph.executor import (
    CallableVerifier,
    ExecutionPolicy,
    ReferenceExecutor,
    VerificationResult,
)
from solutiongraph.model import sha256_digest
from solutiongraph.schemas import load_all_schemas


def _validate_wire(schema_name: str, payload) -> None:
    schemas = load_all_schemas()
    registry = SchemaRegistry().with_resources(
        (name, Resource.from_contents(schema)) for name, schema in schemas.items()
    )
    errors = sorted(
        Draft202012Validator(schemas[schema_name], registry=registry).iter_errors(payload),
        key=lambda item: list(item.absolute_path),
    )
    assert errors == [], "\n".join(
        f"{'.'.join(map(str, item.absolute_path))}: {item.message}" for item in errors
    )


def _regression_context(**changes) -> DesignContext:
    values = {
        "id": "context.test.regression",
        "task_type": "task.tabular-regression",
        "objective": "Predict a continuous outcome for each customer at renewal time.",
        "modalities": ("modality.tabular",),
        "target_name": "renewal_value",
        "group_field": "customer_id",
        "row_count": 5000,
        "column_count": 40,
    }
    values.update(changes)
    return DesignContext(**values)


def _atlas_verifier(context) -> VerificationResult:
    bundle = context.outputs.get("report_bundle", {})
    payload = bundle.get("payload", {}) if isinstance(bundle, dict) else {}
    plan = payload.get("plan", {}) if isinstance(payload, dict) else {}
    accepted = (
        plan.get("summary", {}).get("selected") == 12
        and len(payload.get("dossier", {}).get("decisions", ())) == 12
        and "<!doctype html>" in bundle.get("html", "")
    )
    return VerificationResult(
        accepted,
        "complete-evidence-bound-report" if accepted else "invalid-report-bundle",
        {"quality": float(accepted)},
    )


def test_atlas_normalizes_every_supplied_technique_without_promoting_source_claims():
    assert validate_design_atlas() == []
    assert len(REFERENCE_TECHNIQUES) == 618
    assert len(REFERENCE_DESIGN_PACKS) == 28
    assert len(REFERENCE_DESIGN_QUESTIONS) == 112
    assert len(REFERENCE_TASK_ARCHETYPES) == 31
    assert len(REFERENCE_SOURCES) == 12
    assert Counter(item.source_claim for item in REFERENCE_TECHNIQUES) == {
        "reported-implemented": 134,
        "reported-partial": 21,
        "reported-designed": 37,
        "reported-absent": 426,
    }
    assert {item.to_dict()["maturity_floor"] for item in REFERENCE_TECHNIQUES} == {"C1"}
    assert all("unverified supplied inventory" in item.to_dict()["claim_boundary"] for item in REFERENCE_TECHNIQUES)
    index = atlas_index()
    assert index["phase_count"] == 20
    assert index["machine_maturity"] == {"C1": 618}


def test_every_atlas_contract_has_a_strict_wire_schema():
    for technique in REFERENCE_TECHNIQUES:
        _validate_wire("design-technique.schema.json", technique.to_dict())
    for question in REFERENCE_DESIGN_QUESTIONS:
        _validate_wire("design-question.schema.json", question.to_dict())
    for pack in REFERENCE_DESIGN_PACKS:
        _validate_wire("design-pack.schema.json", pack.to_dict())
    for archetype in REFERENCE_TASK_ARCHETYPES:
        _validate_wire("task-archetype.schema.json", archetype.to_dict())


def test_effort_changes_allocation_but_never_hides_questions():
    planner = DesignPlanner()
    context = _regression_context()
    small = planner.plan(context, effort="E1", random_seed=11)
    broad = planner.plan(context, effort="E10", random_seed=11)
    repeated = planner.plan(context, effort="E1", random_seed=11)
    assert len(small.items) == len(broad.items) == len(REFERENCE_DESIGN_QUESTIONS)
    assert sum(item.status == "selected" for item in small.items) == 12
    assert sum(item.status == "selected" for item in broad.items) > 12
    assert small == repeated
    assert any(item.status == "not-applicable" for item in broad.items)
    assert {item.question_id for item in small.items} == {
        item.id for item in REFERENCE_DESIGN_QUESTIONS
    }
    _validate_wire("design-context.schema.json", context.to_dict())
    _validate_wire("design-plan.schema.json", small.to_dict())


def test_llm_design_questions_require_explicit_model_authority():
    context = _regression_context()
    blocked = DesignPlanner().plan(
        context,
        effort="E3",
        available_modes=("llm",),
        granted_permissions=(),
    )
    allowed = DesignPlanner().plan(
        context,
        effort="E3",
        available_modes=("llm",),
        granted_permissions=("model.invoke",),
    )
    assert sum(item.status == "blocked" for item in blocked.items) > 0
    assert sum(item.status == "selected" for item in blocked.items) == 0
    assert sum(item.status == "selected" for item in allowed.items) == 28
    assert all(
        item.response_mode == "llm" for item in allowed.items if item.status == "selected"
    )


def test_aggregate_profile_derives_context_signals_and_evidence_digests():
    records = [
        {"store_id": "s1", "city": "Boston", "state": "MA", "event_date": "2026-01-01", "target": 1.0},
        {"store_id": "s2", "city": "Albany", "state": "NY", "event_date": "2026-01-02", "target": None},
    ]
    context, profile, field_map = context_from_records(
        records,
        task_type="regression",
        objective="Predict target at event time.",
        target_name="target",
        group_field="store_id",
    )
    assert context.dataset_profile_digest == profile.digest
    assert context.semantic_map_digest == field_map.digest
    assert "signal.missing-values" in context.signals
    assert "signal.time-aware" in context.signals
    assert "signal.geospatial" in context.signals
    assert {"modality.tabular", "modality.time-series", "modality.geospatial"}.issubset(
        context.modalities
    )
    serialized = json.dumps(context.to_dict(), sort_keys=True)
    assert "Boston" not in serialized and "Albany" not in serialized
    _validate_wire("design-context.schema.json", context.to_dict())


def test_decision_resolution_distinguishes_evidenced_provisional_and_invalid_answers():
    planner = DesignPlanner()
    plan = planner.plan(_regression_context(), effort="E1")
    selected = [item for item in plan.items if item.status == "selected"]
    from solutiongraph.design_atlas.packs import DESIGN_QUESTION_BY_ID

    first_question = DESIGN_QUESTION_BY_ID[selected[0].question_id]
    second_question = DESIGN_QUESTION_BY_ID[selected[1].question_id]
    dossier = planner.resolve(
        plan,
        (
            DecisionAnswer(
                first_question.id,
                first_question.choices[0].id,
                "The comparison is linked to the task evidence.",
                ("artifact://evidence/task-contract.json",),
                confidence=0.8,
                responder="responder.test",
            ),
            DecisionAnswer(
                second_question.id,
                second_question.choices[1].id,
                "A baseline was chosen but evidence has not been attached.",
                confidence=0.4,
                responder="responder.test",
            ),
        ),
    )
    assert [record.status for record in dossier.decisions] == ["accepted", "provisional"]
    assert len(dossier.unanswered_question_ids) == 10
    assert dossier.decisions[0].experiment
    _validate_wire("design-answer.schema.json", DecisionAnswer(
        first_question.id,
        first_question.choices[0].id,
        "Evidence-backed answer.",
        ("artifact://evidence/task-contract.json",),
        responder="responder.test",
    ).to_dict())
    _validate_wire("design-dossier.schema.json", dossier.to_dict())
    with pytest.raises(ValueError, match="not a branch"):
        planner.resolve(
            plan,
            (
                DecisionAnswer(
                    first_question.id,
                    "decision.invalid.choice",
                    "Invalid branch",
                    responder="responder.test",
                ),
            ),
        )


def test_maturity_is_derived_from_contiguous_evidence_gates():
    digest = sha256_digest({"manifest": "median-imputer"})
    catalog_only = assess_maturity(
        CapabilityEvidence("capability.test.imputer", cataloged=True)
    )
    runnable = assess_maturity(
        CapabilityEvidence(
            "capability.test.imputer",
            cataloged=True,
            declaration_digest=digest,
            valid_smoke_tests=2,
            invalid_smoke_tests=2,
        )
    )
    attempted_leap = assess_maturity(
        CapabilityEvidence(
            "capability.test.imputer",
            cataloged=True,
            benchmark_receipts=100,
            benchmark_seeds=20,
        )
    )
    operational = assess_maturity(
        CapabilityEvidence(
            "capability.test.imputer",
            cataloged=True,
            declaration_digest=digest,
            valid_smoke_tests=2,
            invalid_smoke_tests=2,
            compatibility_tests=4,
            leakage_tests=3,
            search_registered=True,
            search_tests=2,
            benchmark_receipts=6,
            benchmark_seeds=3,
            monitoring_evidence=("monitor.json",),
            security_evidence=("security.json",),
            privacy_evidence=("privacy.json",),
            rollback_evidence=("rollback.json",),
            slo_evidence=("slo.json",),
        )
    )
    assert catalog_only.overall_level == "C1"
    assert runnable.overall_level == "C3"
    assert attempted_leap.overall_level == "C1"
    assert operational.overall_level == "C7"
    _validate_wire(
        "capability-evidence.schema.json",
        CapabilityEvidence("capability.test.imputer", cataloged=True).to_dict(),
    )


def test_atlas_is_exported_into_the_portable_catalog():
    documents = catalog_documents()
    assert documents["design-atlas/index.json"]["technique_count"] == 618
    assert documents["design-atlas/index.json"]["question_count"] == 112
    assert all(
        f"design-atlas/techniques/{item.id}.json" in documents
        for item in REFERENCE_TECHNIQUES
    )
    assert all(
        f"design-atlas/questions/{item.id}.json" in documents
        for item in REFERENCE_DESIGN_QUESTIONS
    )


def test_design_atlas_node_pack_is_typed_authority_aware_and_executable():
    assert len(DESIGN_ATLAS_NODE_DEFINITIONS) == len(DESIGN_ATLAS_NODE_SPECS) == 5
    assert len(DESIGN_ATLAS_CANDIDATES) == 34
    assert DESIGN_ATLAS_NODE_PACK.validate() == []
    assert all(item.validate() == [] for item in DESIGN_ATLAS_NODE_DEFINITIONS)
    by_id = {item.id: item for item in DESIGN_ATLAS_NODE_SPECS}
    assert all(
        descriptor.validate(by_id[descriptor.node_id]) == []
        for descriptor in DESIGN_ATLAS_DESCRIPTORS
    )

    compiler = Compiler()
    human_space = compiler.admit(DESIGN_ATLAS_PROGRAM, DESIGN_ATLAS_REGISTRY)
    assert human_space.route_count_upper_bound == 30
    assert len(human_space.choices_for("plan")) == 15
    assert all(
        DESIGN_ATLAS_REGISTRY.candidate_map()[candidate_id].node_id
        == "design-atlas.plan-human-review"
        for candidate_id in human_space.choices_for("plan")
    )
    llm_program = design_atlas_program(granted_permissions=("model.invoke",))
    llm_space = compiler.admit(llm_program, DESIGN_ATLAS_REGISTRY)
    assert len(llm_space.choices_for("plan")) == 15
    assert all(
        DESIGN_ATLAS_REGISTRY.candidate_map()[candidate_id].node_id
        == "design-atlas.plan-llm-review"
        for candidate_id in llm_space.choices_for("plan")
    )

    context, profile, field_map = context_from_records(
        [
            {"customer_id": "c1", "renewal_value": 10.0},
            {"customer_id": "c2", "renewal_value": 12.0},
        ],
        task_type="regression",
        objective="Predict renewal value.",
        target_name="renewal_value",
        group_field="customer_id",
    )
    expected_plan = DesignPlanner().plan(
        context,
        effort="E1",
        available_modes=("human",),
        granted_permissions=("human.review",),
        random_seed=0,
    )
    from solutiongraph.design_atlas.packs import DESIGN_QUESTION_BY_ID

    answers = [
        DecisionAnswer(
            item.question_id,
            DESIGN_QUESTION_BY_ID[item.question_id].choices[0].id,
            "Selected against the fixed task contract.",
            (f"artifact://evidence/{item.question_id}.json",),
            confidence=0.8,
            responder="responder.test",
        ).to_dict()
        for item in expected_plan.items
        if item.status == "selected"
    ]
    task_request = {
        "task_type": "regression",
        "objective": "Predict renewal value.",
        "target_name": "renewal_value",
        "group_field": "customer_id",
    }
    answer_set = {"plan_digest": expected_plan.digest, "answers": answers}
    _validate_wire("design-task-request.schema.json", task_request)
    _validate_wire("design-answer-set.schema.json", answer_set)
    selections = {}
    target_parameters = {
        "context": {},
        "plan": {"effort_level": "E1", "random_seed": 0},
        "resolve": {"resolution_policy": "evidence-required"},
        "report": {},
    }
    target_nodes = {
        "context": "design-atlas.derive-context",
        "plan": "design-atlas.plan-human-review",
        "resolve": "design-atlas.resolve-answers",
        "report": "design-atlas.render-report",
    }
    for slot_id, node_id in target_nodes.items():
        selections[slot_id] = next(
            candidate.id
            for candidate in DESIGN_ATLAS_CANDIDATES
            if candidate.node_id == node_id
            and dict(candidate.parameters) == target_parameters[slot_id]
        )
    frozen = compiler.compile(
        DESIGN_ATLAS_PROGRAM,
        DESIGN_ATLAS_REGISTRY,
        human_space,
        selections,
    )
    result = ReferenceExecutor().execute(
        frozen,
        DESIGN_ATLAS_PROGRAM,
        DESIGN_ATLAS_REGISTRY,
        human_space,
        {
            "dataset_profile": profile.to_dict(),
            "semantic_field_map": field_map.to_dict(),
            "task_request": task_request,
            "answer_set": answer_set,
        },
        task_case_id="case.design-atlas-regression",
        verifier=CallableVerifier("verifier.design-atlas-report", _atlas_verifier),
        policy=ExecutionPolicy(granted_permissions=("human.review",)),
    )
    assert result.ok
    assert len(result.receipt.node_receipts) == 4
    assert result.outputs["context"] == context.to_dict()
    assert result.outputs["design_plan"] == expected_plan.to_dict()
    assert all(
        item["status"] == "accepted"
        for item in result.outputs["design_dossier"]["decisions"]
    )
    _validate_wire("design-report-bundle.schema.json", result.outputs["report_bundle"])


def test_atlas_cli_lists_plans_and_writes_self_contained_reports(tmp_path, capsys):
    assert main(["atlas", "coverage"]) == 0
    assert "techniques=618" in capsys.readouterr().out
    assert main(["atlas", "techniques", "--phase", "4", "--query", "imputation"]) == 0
    assert "imputation" in capsys.readouterr().out.casefold()
    output = tmp_path / "atlas-plan"
    assert main([
        "atlas", "plan", "--task-type", "regression",
        "--objective", "Predict renewal value", "--target-name", "renewal_value",
        "--effort", "E1", "--output-dir", str(output),
    ]) == 0
    assert "visible=112" in capsys.readouterr().out
    payload = json.loads((output / "design-plan.json").read_text(encoding="utf-8"))
    markdown = (output / "design-plan.md").read_text(encoding="utf-8")
    html = (output / "design-plan.html").read_text(encoding="utf-8")
    assert payload["plan"]["summary"]["selected"] == 12
    assert "```mermaid" in markdown
    assert "Claim boundary" in markdown
    assert "fetch(" not in html and "XMLHttpRequest" not in html
    context = _regression_context()
    assert "Complete visibility ledger" in render_markdown(
        context, DesignPlanner().plan(context, effort="E1")
    )


def test_atlas_cli_resolves_structured_answers(tmp_path, capsys):
    context = _regression_context()
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context.to_dict()), encoding="utf-8")
    plan = DesignPlanner().plan(context, effort="E1")
    selected = next(item for item in plan.items if item.status == "selected")
    from solutiongraph.design_atlas.packs import DESIGN_QUESTION_BY_ID

    question = DESIGN_QUESTION_BY_ID[selected.question_id]
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps([DecisionAnswer(
        question.id,
        question.choices[0].id,
        "Compare the branches under the fixed task oracle.",
        ("artifact://evidence/task-contract.json",),
        responder="responder.test",
    ).to_dict()]), encoding="utf-8")
    output = tmp_path / "dossier.json"
    assert main([
        "atlas", "resolve", str(context_path), str(answers_path),
        "--effort", "E1", "--output", str(output),
    ]) == 0
    assert "decisions=1" in capsys.readouterr().out
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["decisions"][0]["status"] == "accepted"
    assert len(payload["unanswered_question_ids"]) == 11
