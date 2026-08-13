from __future__ import annotations

import json
from copy import deepcopy

from jsonschema import Draft202012Validator
from referencing import Registry as SchemaRegistry
from referencing import Resource

from solutiongraph.cli import main
from solutiongraph.compiler import Compiler
from solutiongraph.interrogation.engine import InterrogationEngine
from solutiongraph.interrogation.execution import STANDARD_CHECK_REGISTRY
from solutiongraph.interrogation.learning import (
    QuestionUtilityMemory,
    QuestionUtilityObservation,
)
from solutiongraph.interrogation.node_pack import (
    INTERROGATION_CANDIDATES,
    INTERROGATION_DESCRIPTORS,
    INTERROGATION_NODE_DEFINITIONS,
    INTERROGATION_NODE_PACK,
    INTERROGATION_NODE_SPECS,
    INTERROGATION_PROGRAM,
    INTERROGATION_REGISTRY,
)
from solutiongraph.interrogation.planning import QuestionPlanner, effort_budget
from solutiongraph.interrogation.profiling import map_semantic_fields, profile_records
from solutiongraph.interrogation.repair import reverse_repair_shadow
from solutiongraph.model import sha256_digest
from solutiongraph.question_packs import (
    REFERENCE_CONCEPTS,
    REFERENCE_QUESTION_PACKS,
    REFERENCE_QUESTIONS,
    validate_reference_question_packs,
)
from solutiongraph.schemas import load_all_schemas

DIRTY_ORGANIZATIONS = [
    {
        "record_id": "org-1",
        "company_name": " Acme Inc.  ",
        "street": "1 Main St",
        "city": "Boston",
        "state": "ma",
        "zip": "02108",
        "email": "OPS@EXAMPLE.COM.",
        "event_date": "2025/01/03",
        "target": 0,
    },
    {
        "record_id": "org-2",
        "company_name": "Acme Incorporated",
        "street": "",
        "city": "Boston",
        "state": "MA",
        "zip": "bad",
        "email": "not-an-email",
        "event_date": "01/02/03",
        "target": 0,
    },
    {
        "record_id": "org-3",
        "company_name": "N/A",
        "street": "1 Main St",
        "city": "Boston",
        "state": "MA",
        "zip": "02108",
        "email": "x@example.com",
        "event_date": "2025-01-02",
        "target": 1,
    },
]


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


def test_reference_question_bank_is_complete_strict_and_separate_from_nodes():
    assert len(REFERENCE_CONCEPTS) == 46
    assert len(REFERENCE_QUESTION_PACKS) == 11
    assert len(REFERENCE_QUESTIONS) == 86
    assert validate_reference_question_packs() == []
    assert STANDARD_CHECK_REGISTRY.validate() == []
    question_ids = {item.id for item in REFERENCE_QUESTIONS}
    node_ids = {item.id for item in INTERROGATION_NODE_SPECS}
    assert question_ids.isdisjoint(node_ids)
    for concept in REFERENCE_CONCEPTS:
        _validate_wire("concept-definition.schema.json", concept.to_dict())
    for pack in REFERENCE_QUESTION_PACKS:
        _validate_wire("question-pack.schema.json", pack.to_dict())


def test_mapping_and_effort_planning_preserve_every_question_and_block_authority():
    profile = profile_records(DIRTY_ORGANIZATIONS)
    field_map = map_semantic_fields(profile, REFERENCE_CONCEPTS)
    assert field_map.dataset_digest == profile.dataset_digest
    assert "concept.organization.name" in field_map.concepts
    assert "concept.postal.region" in field_map.concepts
    assert "concept.ml.target" in field_map.concepts

    planner = QuestionPlanner()
    small = planner.plan(
        profile,
        field_map,
        REFERENCE_QUESTION_PACKS,
        budget=effort_budget("E1", random_seed=7),
        available_capabilities=STANDARD_CHECK_REGISTRY.capabilities,
    )
    broad = planner.plan(
        profile,
        field_map,
        REFERENCE_QUESTION_PACKS,
        budget=effort_budget("E10", random_seed=7),
        available_capabilities=STANDARD_CHECK_REGISTRY.capabilities,
    )
    assert len(small.items) == len(broad.items) == len(REFERENCE_QUESTIONS)
    assert sum(item.status == "selected" for item in small.items) <= 12
    assert sum(item.status == "selected" for item in broad.items) > 12
    external_or_model = [
        item
        for item in broad.items
        if item.status == "blocked"
        and any("unavailable" in reason or "not granted" in reason for reason in item.reasons)
    ]
    assert external_or_model
    _validate_wire("dataset-profile.schema.json", profile.to_dict())
    _validate_wire("semantic-field-map.schema.json", field_map.to_dict())
    _validate_wire("question-plan.schema.json", small.to_dict())


def test_history_changes_priority_but_never_hides_questions():
    profile = profile_records(DIRTY_ORGANIZATIONS)
    field_map = map_semantic_fields(profile, REFERENCE_CONCEPTS)
    question_id = "question.generic-tabular.placeholders"
    observations = tuple(
        QuestionUtilityObservation(
            id=f"observation.helpful-{index}",
            question_id=question_id,
            task_fingerprint_digest=sha256_digest("organization-quality-task"),
            context_tags=("domain.organization",),
            finding_produced=True,
            repair_proposed=True,
            repair_promoted=True,
            false_correction=False,
        )
        for index in range(6)
    )
    memory = QuestionUtilityMemory("memory.test-questions", "1.0.0", observations)
    plan = QuestionPlanner().plan(
        profile,
        field_map,
        REFERENCE_QUESTION_PACKS,
        budget=effort_budget("E3"),
        available_capabilities=STANDARD_CHECK_REGISTRY.capabilities,
        history=memory,
        context_tags=("domain.organization",),
    )
    item = next(item for item in plan.items if item.question_id == question_id)
    assert item.historical_observations == 6
    assert item.historical_utility > 0.5
    assert len(plan.items) == len(REFERENCE_QUESTIONS)


def test_end_to_end_shadow_loop_is_reversible_receipted_and_raw_data_free():
    source = deepcopy(DIRTY_ORGANIZATIONS)
    report = InterrogationEngine().run(source, effort="E3", random_seed=17)
    assert source == DIRTY_ORGANIZATIONS
    assert len(report.question_plan.items) == 86
    assert len(report.before_findings.receipts) == 30
    assert report.before_findings.findings
    assert report.repair_proposal.operations
    assert report.repair_application.applied_operation_ids
    assert report.verification.decision in {"promote", "quarantine", "no-change"}
    assert report.verification.independence == "independence.separate-controller"
    assert report.verification.verifier_digest.startswith("sha256:")
    serialized = json.dumps(report.wire_dict(), sort_keys=True)
    assert "OPS@EXAMPLE.COM" not in serialized
    assert "not-an-email" not in serialized

    applied_lookup = set(report.repair_application.applied_operation_ids)
    proposal_lookup = {item.id: item for item in report.repair_proposal.operations}
    shadow = deepcopy(source)
    for operation_id in report.repair_application.applied_operation_ids:
        operation = proposal_lookup[operation_id]
        if operation.action in ("add", "replace", "quarantine"):
            shadow[operation.row_index][operation.field_name] = deepcopy(operation.after_value)
        else:
            shadow[operation.row_index].pop(operation.field_name, None)
    assert applied_lookup
    restored = reverse_repair_shadow(shadow, report.repair_proposal, report.repair_application)
    assert restored == source

    _validate_wire("finding-set.schema.json", report.before_findings.to_dict())
    _validate_wire("repair-proposal.schema.json", report.repair_proposal.to_dict())
    _validate_wire("verification-receipt.schema.json", report.verification.to_dict())
    _validate_wire("interrogation-report.schema.json", report.wire_dict())


def test_interrogation_node_pack_exposes_a_real_compatible_search_space():
    assert len(INTERROGATION_NODE_DEFINITIONS) == len(INTERROGATION_NODE_SPECS) == 8
    assert len(INTERROGATION_CANDIDATES) == 43
    assert INTERROGATION_NODE_PACK.validate() == []
    assert all(item.validate() == [] for item in INTERROGATION_NODE_DEFINITIONS)
    by_id = {item.id: item for item in INTERROGATION_NODE_SPECS}
    assert all(
        descriptor.validate(by_id[descriptor.node_id]) == []
        for descriptor in INTERROGATION_DESCRIPTORS
    )
    admitted = Compiler().admit(INTERROGATION_PROGRAM, INTERROGATION_REGISTRY)
    assert admitted.route_count_upper_bound == 8640
    assert len(admitted.decisions) == len(INTERROGATION_PROGRAM.slots) * len(
        INTERROGATION_CANDIDATES
    )
    assert all(admitted.choices_for(slot.id) for slot in INTERROGATION_PROGRAM.slots)


def test_question_cli_maps_plans_runs_and_writes_self_contained_reports(tmp_path, capsys):
    dataset = tmp_path / "organizations.json"
    dataset.write_text(json.dumps(DIRTY_ORGANIZATIONS), encoding="utf-8")
    assert main(["concepts", "map", str(dataset)]) == 0
    assert "concept.organization.name" in capsys.readouterr().out
    assert main(["questions", "plan", str(dataset), "--effort", "E1"]) == 0
    assert "visible=86" in capsys.readouterr().out
    output = tmp_path / "report"
    assert main(
        [
            "questions", "run", str(dataset), "--effort", "E3",
            "--random-seed", "17", "--output-dir", str(output),
        ]
    ) == 0
    text = capsys.readouterr().out
    assert "decision=" in text
    payload = json.loads((output / "interrogation-report.json").read_text(encoding="utf-8"))
    html = (output / "interrogation-report.html").read_text(encoding="utf-8")
    markdown = (output / "interrogation-report.md").read_text(encoding="utf-8")
    assert payload["summary"]["question_count"] == 86
    assert "fetch(" not in html and "XMLHttpRequest" not in html
    assert "Claim boundary" in html
    assert "```mermaid" in markdown
