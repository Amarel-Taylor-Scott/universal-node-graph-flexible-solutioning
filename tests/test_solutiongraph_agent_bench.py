from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry as SchemaRegistry
from referencing import Resource

from solutiongraph.agent_bench import (
    REFERENCE_AGENT_TASKS,
    AgentJournalIntegrityError,
    AgentTrialJournal,
    command_matrix_example_suite,
    iter_trial_plans,
    load_agent_benchmark_suite,
    reference_agent_benchmark_suite,
    run_agent_benchmark,
    validate_reference_agent_tasks,
)
from solutiongraph.agent_bench.model import HarnessProfile
from solutiongraph.agent_bench.workspace import materialize_workspace
from solutiongraph.cli import main
from solutiongraph.schemas import load_all_schemas

ROOT = Path(__file__).parents[1]
EXAMPLE_CONFIG = ROOT / "examples" / "agent-benchmark-matrix.example.json"
NOTEBOOK = ROOT / "notebooks" / "06_llm_harness_ab_arena.ipynb"


def _validate_wire(name: str, payload: dict) -> None:
    schemas = load_all_schemas()
    registry = SchemaRegistry().with_resources(
        (schema["$id"], Resource.from_contents(schema))
        for schema in schemas.values()
    )
    errors = sorted(
        Draft202012Validator(schemas[name], registry=registry).iter_errors(payload),
        key=lambda error: tuple(error.path),
    )
    assert not errors, "; ".join(error.message for error in errors)


def test_ten_diverse_agent_tasks_have_public_and_sealed_oracle_contracts():
    assert validate_reference_agent_tasks() == []
    assert len(REFERENCE_AGENT_TASKS) == 10
    assert len({bundle.spec.template_id for bundle in REFERENCE_AGENT_TASKS}) >= 7
    assert len({category for bundle in REFERENCE_AGENT_TASKS for category in bundle.spec.categories}) >= 10
    assert all(bundle.spec.public_case_ids for bundle in REFERENCE_AGENT_TASKS)
    assert all(len(bundle.spec.sealed_case_ids) >= 2 for bundle in REFERENCE_AGENT_TASKS)
    assert all("flowchart LR" in bundle.spec.mermaid() for bundle in REFERENCE_AGENT_TASKS)
    for bundle in REFERENCE_AGENT_TASKS:
        _validate_wire("agent-task.schema.json", bundle.spec.to_dict())


def test_reference_and_command_suites_enumerate_only_compatible_pairs():
    reference = reference_agent_benchmark_suite()
    assert reference.validate(tuple(bundle.spec.id for bundle in REFERENCE_AGENT_TASKS)) == []
    assert reference.total_trials == len(tuple(iter_trial_plans(reference))) == 20
    first_conditions = [
        plan.condition
        for index, plan in enumerate(iter_trial_plans(reference))
        if index % 2 == 0
    ]
    assert first_conditions.count("control") == first_conditions.count("solutiongraph") == 5

    command = command_matrix_example_suite()
    assert command.total_trials == 60
    assert {
        (plan.harness_id, plan.model_id) for plan in iter_trial_plans(command)
    } == {("harness.reference-fixture", "model.reference-fixture")}
    enabled_external = replace(
        command,
        harnesses=tuple(
            replace(harness, enabled=harness.id == "harness.opencode")
            for harness in command.harnesses
        ),
        models=tuple(replace(model, enabled=True) for model in command.models),
    )
    pairs = {
        (plan.harness_id, plan.model_id) for plan in iter_trial_plans(enabled_external)
    }
    assert len(pairs) == 4
    assert all(harness == "harness.opencode" for harness, _ in pairs)
    assert all(model != "model.reference-fixture" for _, model in pairs)
    _validate_wire("agent-benchmark-suite.schema.json", command.to_dict())


def test_workspace_isolates_the_context_intervention_without_changing_prompt(tmp_path):
    suite = reference_agent_benchmark_suite()
    plans = [
        plan
        for plan in iter_trial_plans(suite)
        if plan.task_id == REFERENCE_AGENT_TASKS[0].spec.id
    ]
    by_condition = {plan.condition: plan for plan in plans}
    bundle = REFERENCE_AGENT_TASKS[0]
    control_root = tmp_path / "control"
    treatment_root = tmp_path / "treatment"
    control = materialize_workspace(control_root, ROOT, bundle, by_condition["control"])
    treatment = materialize_workspace(
        treatment_root, ROOT, bundle, by_condition["solutiongraph"]
    )

    assert control.prompt_digest == treatment.prompt_digest
    assert (control_root / "TASK.md").read_bytes() == (treatment_root / "TASK.md").read_bytes()
    assert (control_root / "task.json").read_bytes() == (treatment_root / "task.json").read_bytes()
    assert (control_root / "inputs" / "public-case.json").read_bytes() == (
        treatment_root / "inputs" / "public-case.json"
    ).read_bytes()
    assert control.context_bytes == 0
    assert treatment.context_bytes > 0
    assert (control_root / "context" / "AGENT_CONTEXT.md").read_text() == ""
    assert (treatment_root / "context" / "AGENT_CONTEXT.md").stat().st_size > 0
    assert (treatment_root / "context" / "starting-points.json").is_file()
    assert (treatment_root / "context" / "task-graph.mmd").is_file()
    assert not (control_root / ".agent-bench-workspace.json").exists()
    published_task = json.loads((treatment_root / "task.json").read_text(encoding="utf-8"))
    assert all(
        set(case) == {
            "id",
            "split",
            "input_digest",
            "expected_digest",
            "candidate_readable",
            "tags",
        }
        for case in published_task["cases"]
    )
    assert len(list((treatment_root / "inputs").glob("*.json"))) == 1


def test_twenty_trial_smoke_produces_accepted_receipts_equivalence_and_reports(tmp_path):
    result = run_agent_benchmark(
        reference_agent_benchmark_suite(), tmp_path / "agent-smoke"
    )
    report = result.report

    assert report.status == "benchmark.completed"
    assert report.planned_trials == report.executed_trials == report.accepted_trials == 20
    assert len(report.effects) == 36
    assert {effect.metric for effect in report.effects if effect.scope == "task"} >= {
        "rmse",
        "minority_f1",
        "mae",
    }
    assert {effect.inference for effect in report.effects} == {"practically-equivalent"}
    assert report.decisions == ()
    assert report.unmatched_receipt_ids == ()
    assert sum(1 for _ in result.receipt_journal.open(encoding="utf-8")) == 20
    assert len(list((result.output_dir / "workspace-manifests").glob("*.json"))) == 20
    assert len(list((result.output_dir / "diagrams").glob("*.mmd"))) == 10
    assert "No winner or promotion decision" in result.report_html.read_text(encoding="utf-8")
    _validate_wire("agent-benchmark-report.schema.json", report.to_dict())
    for receipt in report.receipts:
        assert receipt.lifecycle == ("ATTEMPTED", "DELIVERED", "VALID", "SCORED", "ACCEPTED")
        _validate_wire("agent-trial-receipt.schema.json", receipt.to_dict())

    journal = AgentTrialJournal(result.receipt_journal)
    assert journal.status().receipt_count == 20
    assert len(journal.receipts()) == 20


def test_agent_receipt_journal_detects_tampering(tmp_path):
    result = run_agent_benchmark(
        reference_agent_benchmark_suite(), tmp_path / "untampered"
    )
    lines = result.receipt_journal.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["receipt"]["accepted"] = False
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    tampered = tmp_path / "tampered.jsonl"
    tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(AgentJournalIntegrityError, match="receipt digest"):
        AgentTrialJournal(tampered).status()


def test_partial_pilot_and_external_authority_are_explicit(tmp_path):
    suite = reference_agent_benchmark_suite()
    partial = run_agent_benchmark(suite, tmp_path / "partial", max_trials=3)
    manifest = json.loads(partial.run_manifest.read_text(encoding="utf-8"))
    assert partial.report.status == "benchmark.completed-partial"
    assert partial.report.executed_trials == 3
    assert partial.report.skipped_trials == 17
    assert manifest["unvisited_trials"] == manifest["budget_skipped_trials"] == 17
    assert not manifest["complete"]

    command = HarnessProfile(
        id="harness.permission-test",
        kind="command",
        version="1.0.0",
        command_argv=("never-run",),
        compatible_model_ids=("model.reference-fixture",),
    )
    external = replace(suite, harnesses=(command,))
    with pytest.raises(PermissionError, match="--allow-external"):
        run_agent_benchmark(external, tmp_path / "blocked")
    assert not (tmp_path / "blocked").exists()


def test_example_config_notebook_and_cli_workflow(tmp_path, capsys):
    loaded = load_agent_benchmark_suite(EXAMPLE_CONFIG)
    assert loaded == command_matrix_example_suite()
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) >= 8
    assert "run_agent_benchmark" in json.dumps(notebook)
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), f"notebook-cell-{index}", "exec")

    assert main(["agent-bench", "tasks"]) == 0
    assert "agent-task.graph-experiment" in capsys.readouterr().out
    generated = tmp_path / "generated.json"
    assert main(["agent-bench", "example-config", "--output", str(generated)]) == 0
    capsys.readouterr()
    assert load_agent_benchmark_suite(generated) == loaded
    assert main(["agent-bench", "plan", str(generated)]) == 0
    planned = capsys.readouterr().out
    assert "trials=60" in planned
    output = tmp_path / "cli-smoke"
    assert main(["agent-bench", "smoke", "--output", str(output)]) == 0
    assert "executed=20/20" in capsys.readouterr().out
    assert main(
        ["agent-bench", "journal-verify", str(output / "trial-receipts.jsonl")]
    ) == 0
    assert "receipts=20" in capsys.readouterr().out
