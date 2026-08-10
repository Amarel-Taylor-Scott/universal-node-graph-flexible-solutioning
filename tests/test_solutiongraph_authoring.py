from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from solutiongraph.cli import main
from solutiongraph.schemas import SCHEMA_NAMES
from solutiongraph.template_authoring import (
    LinearTemplateBlueprint,
    load_linear_blueprint,
    write_solution_template,
)
from solutiongraph.template_library import REFERENCE_TEMPLATES

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "custom-template-blueprint.json"


def test_strict_blueprint_compiles_to_the_normative_template_model():
    blueprint = load_linear_blueprint(EXAMPLE)
    template = blueprint.to_template()

    assert blueprint.validate() == []
    assert template.validate() == []
    assert template.id == "template.example-csv-report"
    assert [stage.slot_ids for stage in template.stages] == [
        ("load_csv", "validate_schema"),
        ("profile_columns", "render_report"),
    ]
    assert template.program.granted_permissions == ()
    assert template.program.slots[0].allowed_effects == ("filesystem.read",)
    assert dict(template.extensions)["universal.template-source"] == "linear-blueprint"


def test_blueprint_round_trip_and_template_export_are_deterministic(tmp_path):
    source = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    blueprint = LinearTemplateBlueprint.from_dict(source)
    assert LinearTemplateBlueprint.from_dict(blueprint.to_dict()) == blueprint

    first = write_solution_template(blueprint.to_template(), tmp_path / "first.json")
    second = write_solution_template(blueprint.to_template(), tmp_path / "second.json")
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8"))["id"] == blueprint.id


def test_blueprint_rejects_unknown_fields_duplicates_and_missing_capabilities():
    source = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    source["mystery"] = True
    with pytest.raises(ValueError, match="unknown field"):
        LinearTemplateBlueprint.from_dict(source)

    valid = load_linear_blueprint(EXAMPLE)
    duplicate_stage = replace(valid.stages[1], slots=(valid.stages[0].slots[0],))
    duplicate = replace(valid, stages=(valid.stages[0], duplicate_stage))
    assert any("globally unique" in problem for problem in duplicate.validate())

    missing_capability = replace(valid.stages[0].slots[0], required_capabilities=())
    broken_stage = replace(
        valid.stages[0],
        slots=(missing_capability, *valid.stages[0].slots[1:]),
    )
    broken = replace(valid, stages=(broken_stage, *valid.stages[1:]))
    assert any("required_capabilities must not be empty" in item for item in broken.validate())


def test_cli_lists_shows_validates_creates_and_runs_doctor(tmp_path, capsys):
    assert main(["doctor"]) == 0
    doctor = capsys.readouterr().out
    assert "templates=19" in doctor
    assert "atomic_slots=339" in doctor
    assert f"schemas={len(SCHEMA_NAMES)}" in doctor
    assert "executable_examples=13" in doctor
    assert "arena_tasks=24" in doctor

    assert main(["templates", "list"]) == 0
    listed = capsys.readouterr().out
    assert "template.document-intelligence" in listed
    assert "template.scientific-experiment" in listed

    assert main(["templates", "list", "--domain", "machine-learning.time-series"]) == 0
    filtered = capsys.readouterr().out
    assert "template.time-series-forecasting" in filtered
    assert "template.web-automation" not in filtered

    assert main(["templates", "show", "template.web-automation"]) == 0
    shown = capsys.readouterr().out
    assert "Perceive" in shown
    assert "locate_target" in shown

    assert main(["templates", "validate", str(EXAMPLE)]) == 0
    assert "valid template.example-csv-report" in capsys.readouterr().out

    output = tmp_path / "compiled.json"
    assert main(
        ["templates", "create", str(EXAMPLE), "--output", str(output)]
    ) == 0
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["template_model_version"] == "0.1"

    assert main(["examples", "list"]) == 0
    examples = capsys.readouterr().out
    assert "browse-and-scrape" in examples
    assert "tabular-regression" in examples
    assert "tabular-classification" in examples


def test_reference_catalog_spans_nineteen_templates_and_339_atomic_slots():
    assert REFERENCE_TEMPLATES.validate() == []
    assert len(REFERENCE_TEMPLATES.templates) == 19
    assert sum(len(template.program.slots) for template in REFERENCE_TEMPLATES.templates) == 339
    assert {
        "template.api-service",
        "template.document-intelligence",
        "template.image-processing",
        "template.incident-response",
        "template.numerical-linear-system",
        "template.scientific-experiment",
        "template.web-automation",
    }.issubset({template.id for template in REFERENCE_TEMPLATES.templates})
