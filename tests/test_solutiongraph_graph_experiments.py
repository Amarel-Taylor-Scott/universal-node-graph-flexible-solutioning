from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry as SchemaRegistry
from referencing import Resource

from solutiongraph.examples.control_mutation_experiment import (
    CONTROL_MUTATION_FAMILY,
    CONTROL_PROGRAM,
    MUTATED_PROGRAM,
    control_mutation_experiment_spec,
)
from solutiongraph.examples.tasks import all_examples
from solutiongraph.graph_experiments import GraphExperimentRunner
from solutiongraph.model import GraphOutput
from solutiongraph.schemas import SCHEMA_NAMES, load_all_schemas
from solutiongraph.search import SearchBudget, SearchMode
from solutiongraph.topology import TopologyFamily, TopologySearchBudget


def _validate_wire(name, payload):
    schemas = load_all_schemas()
    registry = SchemaRegistry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    errors = sorted(
        Draft202012Validator(schemas[name], registry=registry).iter_errors(payload),
        key=lambda error: tuple(error.path),
    )
    assert not errors, "; ".join(error.message for error in errors)


def test_control_and_mutated_graphs_execute_the_complete_six_route_grid():
    report = GraphExperimentRunner().run(control_mutation_experiment_spec())

    assert report.status == "completed"
    assert report.search_report.total_cartesian_routes == 6
    assert report.search_report.evaluated_routes == 6
    assert len(report.plans) == len(report.comparisons) == 6
    assert len(report.ledger.receipts) == 6
    assert report.complete_grid_evaluated
    assert report.declared_grid_optimality_proven
    assert {item.role for item in report.comparisons} == {
        "control",
        "control-topology-alternative",
        "mutation",
    }

    control = next(item for item in report.comparisons if item.role == "control")
    champion = next(
        item for item in report.comparisons if item.plan_digest == report.champion_plan_digest
    )
    assert not control.eligible
    assert champion.role == "mutation"
    assert champion.variant_id == "topology.example.cleaning-mutation"
    assert champion.objective_means["quality"] == 1.0
    assert champion.objective_deltas_from_control["quality"] > 0
    _validate_wire("graph-experiment-report.schema.json", report.to_dict())


def test_complete_grid_mode_rejects_a_result_limit_that_hides_routes():
    spec = control_mutation_experiment_spec()
    truncated = replace(
        spec,
        search_budget=TopologySearchBudget(
            route_budget=SearchBudget(SearchMode.EXHAUSTIVE, result_limit=2),
            result_limit=2,
        ),
    )
    with pytest.raises(ValueError, match="result_limit hides executable routes"):
        GraphExperimentRunner().run(truncated)


def test_topology_family_rejects_incomparable_external_interfaces_and_parent_cycles():
    changed_output = GraphOutput(
        "different_result",
        MUTATED_PROGRAM.outputs[0].value_type,
        MUTATED_PROGRAM.outputs[0].source_slot,
        MUTATED_PROGRAM.outputs[0].source_port,
    )
    incompatible_variant = replace(
        CONTROL_MUTATION_FAMILY.variants[1],
        program=replace(MUTATED_PROGRAM, outputs=(changed_output,)),
    )
    incompatible = replace(
        CONTROL_MUTATION_FAMILY,
        variants=(CONTROL_MUTATION_FAMILY.variants[0], incompatible_variant),
    )
    assert any("external inputs and outputs differ" in item for item in incompatible.validate())

    control, mutation = CONTROL_MUTATION_FAMILY.variants
    cyclic = TopologyFamily(
        CONTROL_MUTATION_FAMILY.id,
        CONTROL_MUTATION_FAMILY.version,
        CONTROL_PROGRAM.task,
        CONTROL_PROGRAM.success_contract,
        (
            replace(control, parent_variant_id=mutation.id),
            replace(mutation, parent_variant_id=control.id),
        ),
    )
    assert any("parent lineage contains a cycle" in item for item in cyclic.validate())


def test_release_facing_onboarding_counts_and_quickstart_command_do_not_drift():
    examples = all_examples()
    routes = sum(len(example.routes) for example in examples)
    controls = sum(
        route.expected_accepted is False for example in examples for route in example.routes
    )
    getting_started = Path("GETTING_STARTED.md").read_text(encoding="utf-8")
    readiness = Path("READINESS.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert f"all {routes} frozen" in getting_started
    assert f"checks {controls} declared negative controls" in getting_started
    assert f"Semantic model and {len(SCHEMA_NAMES)} strict schemas" in readiness
    assert "python examples/control_vs_mutated_graph_experiment.py" in readme
