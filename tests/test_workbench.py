from __future__ import annotations

import json
from dataclasses import replace

import pytest

from browsergraph.cli import main
from browsergraph.demo import build_demo_workbench
from browsergraph.manifest import (
    NodeDefinition,
    NodeManifest,
    ParameterSpec,
    PortSpec,
    described_node,
    manifest_of,
    manifest_schema,
)
from browsergraph.nodes.base import Node
from browsergraph.workbench import (
    ExecutionReceipt,
    FeedbackDefinition,
    NodeCandidate,
    OptimizationObjective,
    OptimizationDecision,
    OptimizationProfile,
    WorkbenchDefinition,
    candidate_id,
    workbench_schema,
)


class ExampleNode(Node):
    kind = "example_manifest_node"
    reads = ("source",)
    writes = ("result",)
    needs_browser = False

    def __init__(self, mode: str = "safe"):
        super().__init__()
        self.mode = mode

    def run(self, ctx):
        return ctx


def test_manifest_round_trip_preserves_the_portable_contract():
    manifest = NodeManifest(
        id="tests.example",
        kind="example",
        name="Example",
        description="A completely described test node.",
        roles=("transform",),
        capabilities=("normalize",),
        inputs=(PortSpec("source", "RawValue", semantic_type="source"),),
        outputs=(PortSpec("result", "CleanValue", units="records"),),
        parameters=(ParameterSpec("mode", "string", choices=("safe", "fast")),),
        permissions=("filesystem:read",),
        resources={"memory_mb": 64},
        context={"reads": ["source"], "writes": ["result"]},
        intelligence={"mode": "deterministic"},
    ).assert_valid()

    assert NodeManifest.from_dict(manifest.to_dict()) == manifest
    assert manifest.to_dict()["context"]["reads"] == ["source"]


def test_manifest_rejects_duplicate_port_names():
    manifest = NodeManifest(
        id="tests.duplicate",
        kind="duplicate",
        name="Duplicate",
        inputs=(PortSpec("value"), PortSpec("value")),
    )
    assert any("duplicate input" in problem for problem in manifest.validate())


def test_manifest_reports_non_string_taxonomy_values_without_crashing():
    data = NodeManifest(
        id="tests.bad_role", kind="bad_role", name="Bad role",
    ).to_dict()
    data["roles"] = [7]
    with pytest.raises(ValueError, match="role values"):
        NodeManifest.from_dict(data)


def test_existing_node_gets_an_inferred_manifest():
    manifest = manifest_of(ExampleNode())
    assert manifest.id == "browsergraph.example_manifest_node"
    assert manifest.inputs[0].name == "source"
    assert manifest.outputs[0].name == "result"
    assert manifest.source.endswith("ExampleNode")


def test_described_node_attaches_full_metadata_without_changing_execution():
    @described_node(
        id="tests.described",
        name="Described node",
        inputs=(PortSpec("source", "RawValue"),),
        outputs=(PortSpec("result", "CleanValue"),),
        capabilities=("canonicalize",),
    )
    class Described(ExampleNode):
        kind = "described_example"

    manifest = manifest_of(Described)
    assert manifest.id == "tests.described"
    assert manifest.outputs[0].data_type == "CleanValue"
    assert Described().mode == "safe"
    assert NodeDefinition.from_node(Described).manifest == manifest


def test_subclass_does_not_inherit_the_wrong_attached_manifest():
    @described_node(id="tests.described_base", name="Described base")
    class DescribedBase(ExampleNode):
        kind = "described_base"

    class DescribedChild(DescribedBase):
        kind = "described_child"

    assert manifest_of(DescribedBase).id == "tests.described_base"
    assert manifest_of(DescribedChild).id == "browsergraph.described_child"


def test_node_definition_is_a_thin_factory_wrapper():
    definition = NodeDefinition.from_node(ExampleNode, name="Wrapped example")
    built = definition.build(mode="fast")
    assert isinstance(built, ExampleNode)
    assert built.mode == "fast"
    assert definition.to_dict()["name"] == "Wrapped example"


def test_metadata_only_definition_refuses_to_execute():
    definition = NodeDefinition(manifest_of(ExampleNode))
    with pytest.raises(TypeError, match="metadata-only"):
        definition.build()


def test_bundled_manifest_schema_is_machine_readable():
    schema = manifest_schema()
    assert schema["$schema"].endswith("2020-12/schema")
    assert {"id", "kind", "name", "inputs", "outputs"}.issubset(
        schema["required"])


def test_bundled_workbench_schema_standardizes_stages_candidates_and_routes():
    schema = workbench_schema()
    assert schema["properties"]["schema_version"]["const"] == "2.0"
    assert {"nodes", "candidates", "macro_stages", "stages", "solutions"}.issubset(
        schema["required"])
    assert {"feedback_channels", "optimization_profiles", "receipts",
            "optimization_decisions"}.issubset(
        schema["properties"])


def test_candidate_id_is_stable_and_parameter_sensitive():
    left = candidate_id("tests.example", {"model": "GLM", "mode": "fast"})
    right = candidate_id("tests.example", {"mode": "fast", "model": "GLM"})
    other = candidate_id("tests.example", {"model": "Qwen", "mode": "fast"})
    assert left == right
    assert left != other


def test_node_candidate_validates_bound_choices():
    manifest = NodeManifest(
        id="tests.model", kind="model", name="Model",
        parameters=(ParameterSpec("model", "string", choices=("GLM", "Qwen"),
                                  default="GLM"),),
    )
    valid = NodeCandidate(
        id=candidate_id(manifest.id, {"model": "Qwen"}),
        node_id=manifest.id,
        parameters={"model": "Qwen"},
    )
    invalid = replace(valid, parameters={"model": "Unknown"})
    assert valid.validate(manifest) == []
    assert any("is not one of" in problem for problem in invalid.validate(manifest))


def test_demo_exposes_every_atomic_candidate_in_every_substep():
    workbench = build_demo_workbench()
    assert len(workbench.macro_stages) == 6
    assert len(workbench.stages) == 21
    assert len(workbench.nodes) == 154
    assert len(workbench.candidates) == 634
    assert len(workbench.solutions) == 5
    assert len(workbench.feedback_channels) == 8
    assert len(workbench.optimization_profiles) == 4
    assert [len(stage.candidates) for stage in workbench.stages] == [
        81, 22, 23, 15, 15, 38, 29, 35, 25, 36, 29,
        33, 24, 68, 25, 19, 27, 21, 23, 26, 20,
    ]
    assert all(
        stage.candidates == stage.discover_candidates(
            list(workbench.nodes), list(workbench.candidates))
        for stage in workbench.stages
    )
    assert workbench.route_count == 1_610_460_741_842_511_132_974_400_000_000


def test_macro_stages_partition_substeps_in_contiguous_order():
    workbench = build_demo_workbench()
    flattened = tuple(
        substep
        for macro_stage in workbench.macro_stages
        for substep in macro_stage.substeps
    )
    assert flattened == tuple(stage.id for stage in workbench.stages)
    assert all(
        stage.macro_stage_id == macro_stage.id
        for macro_stage in workbench.macro_stages
        for stage in workbench.stages
        if stage.id in macro_stage.substeps
    )


def test_macro_stage_hierarchy_rejects_reordered_or_misowned_substeps():
    workbench = build_demo_workbench()
    macro_stage = workbench.macro_stages[0]
    reordered = replace(
        macro_stage,
        substeps=(macro_stage.substeps[1], macro_stage.substeps[0]) +
        macro_stage.substeps[2:],
    )
    wrong_parent = replace(workbench.stages[0], macro_stage_id="canonicalize")
    invalid = replace(
        workbench,
        macro_stages=(reordered,) + workbench.macro_stages[1:],
        stages=(wrong_parent,) + workbench.stages[1:],
    )
    problems = invalid.validate()
    assert any("expected 'acquire'" in problem for problem in problems)
    assert any("preserve the global contiguous stage order" in problem
               for problem in problems)
    empty = replace(
        workbench,
        macro_stages=(replace(macro_stage, substeps=()),) +
        workbench.macro_stages[1:],
    )
    assert any("at least one ordered substep" in problem
               for problem in empty.validate())


def test_stage_can_populate_its_complete_candidate_set_from_the_registry():
    workbench = build_demo_workbench()
    empty = replace(workbench.stages[0], candidates=())
    populated = empty.with_discovered_candidates(
        list(workbench.nodes), list(workbench.candidates))
    assert populated.candidates == workbench.stages[0].candidates


def test_parameter_choices_expand_into_visible_atomic_candidates():
    workbench = build_demo_workbench()
    browser = [candidate for candidate in workbench.candidates
               if candidate.node_id == "demo.acquire.resolve.browser"]
    parsers = [candidate for candidate in workbench.candidates
               if candidate.node_id == "demo.canonicalize.schema.llm"]
    assert len(browser) == 5 * 6 * 2
    assert len(parsers) == 6 * 3
    assert any(candidate.parameters == {
        "controller": "Playwright", "binary": "Firefox", "display": "headless",
    } for candidate in browser)
    assert any(candidate.parameters == {
        "model": "DeepSeek", "strategy": "map-reduce",
    } for candidate in parsers)


def test_demo_has_browser_binary_controller_and_model_dimensions():
    workbench = build_demo_workbench()
    nodes = {node.id: node for node in workbench.nodes}
    browser = nodes["demo.acquire.resolve.browser"]
    params = {parameter.name: parameter for parameter in browser.parameters}
    assert {"Playwright", "Selenium", "Puppeteer", "CDP"}.issubset(
        params["controller"].choices)
    assert {"Chrome", "Edge", "Firefox", "WebKit"}.issubset(
        params["binary"].choices)
    llm = nodes["demo.canonicalize.schema.llm"]
    model_choices = {parameter.name: parameter for parameter in llm.parameters}["model"].choices
    assert {"Gemini", "DeepSeek", "GLM", "Qwen"}.issubset(model_choices)


def test_workbench_round_trip_revalidates_every_solution():
    workbench = build_demo_workbench()
    assert WorkbenchDefinition.from_dict(workbench.to_dict()) == workbench


def test_workbench_rejects_a_compatible_candidate_omitted_from_a_stage():
    workbench = build_demo_workbench()
    first = replace(workbench.stages[0], candidates=workbench.stages[0].candidates[:-1])
    invalid = replace(workbench, stages=(first,) + workbench.stages[1:])
    assert any("omits compatible candidate" in problem for problem in invalid.validate())


def test_workbench_rejects_an_incompatible_candidate_contract():
    workbench = build_demo_workbench()
    original = workbench.nodes[0]
    broken = replace(original, outputs=(PortSpec("output", "WrongType"),))
    invalid = replace(workbench, nodes=(broken,) + workbench.nodes[1:])
    assert any("does not produce ResolvedReference" in problem for problem in invalid.validate())


def test_workbench_rejects_an_incomplete_solution_route():
    workbench = build_demo_workbench()
    solution = workbench.solutions[0]
    route = dict(solution.route)
    route.pop(workbench.stages[-1].id)
    invalid = replace(
        workbench,
        solutions=(replace(solution, route=route),) + workbench.solutions[1:],
    )
    assert any("omits stage" in problem for problem in invalid.validate())


def test_workbench_validation_does_not_crash_on_unknown_selected_candidate():
    workbench = build_demo_workbench()
    first_stage = replace(
        workbench.stages[0],
        candidates=workbench.stages[0].candidates + ("missing.candidate",),
    )
    solution = workbench.solutions[0]
    route = dict(solution.route)
    route[first_stage.id] = "missing.candidate"
    invalid = replace(
        workbench,
        stages=(first_stage,) + workbench.stages[1:],
        solutions=(replace(solution, route=route),),
    )
    problems = invalid.validate()
    assert any("unknown candidate" in problem for problem in problems)
    assert any("not in the candidate registry" in problem for problem in problems)


def test_conditional_pass_through_can_be_selected_on_every_optional_stage():
    workbench = build_demo_workbench()
    solution = workbench.solutions[0]
    route = dict(solution.route)
    for stage in workbench.stages:
        pass_id = f"demo.{stage.id}.pass"
        if pass_id in stage.candidates:
            route[stage.id] = pass_id
    candidate = replace(solution, id="pass_route", route=route, fallbacks={})
    assert replace(workbench, solutions=(candidate,)).validate() == []


def test_rendered_viewer_contains_every_node_and_every_solution():
    workbench = build_demo_workbench()
    html = workbench.render_html()
    assert html.lower().startswith("<!doctype html>")
    assert "__WORKBENCH_DATA__" not in html
    assert "__WORKBENCH_INITIAL_VIEW__" not in html
    assert "Macro stages run left to right" in html
    assert "ordered submatrix of atomic substeps" in html
    assert "Build one route, one atomic substep at a time" in html
    assert "Feedback and optimization remain outside macro stages and substeps" in html
    assert "Copy complete JSON" in html
    assert "Optimize every substep" in html
    assert "Decision rationale" in html
    assert "Selected route evidence summary" in html
    assert "runnable adjacent possibility lines" in html
    assert "Custom route" in html
    assert all(node.name in html for node in workbench.nodes)
    assert all(solution.name in html for solution in workbench.solutions)


def test_rendered_viewer_can_start_in_each_linear_projection():
    workbench = build_demo_workbench()
    for view in ("matrix", "network", "compare", "builder", "feedback"):
        assert f'var INITIAL_VIEW = "{view}";' in workbench.render_html(view=view)
    with pytest.raises(ValueError, match="unknown workbench view"):
        workbench.render_html(view="physics")


def test_workbench_writes_a_multi_file_projection_suite(tmp_path):
    outputs = build_demo_workbench().write_suite(tmp_path / "studio")
    assert set(outputs) == {
        "matrix", "network", "compare", "builder", "feedback", "data"}
    assert outputs["matrix"].name == "index.html"
    assert all(path.exists() for path in outputs.values())
    assert 'var INITIAL_VIEW = "compare";' in outputs["compare"].read_text()
    assert len(WorkbenchDefinition.load(outputs["data"]).candidates) == 634


def test_cli_writes_standalone_viewer_and_normalized_json(tmp_path, capsys):
    viewer = tmp_path / "workbench.html"
    data = tmp_path / "workbench.json"
    assert main([
        "workbench", "-o", str(viewer), "--export-data", str(data),
    ]) == 0
    output = capsys.readouterr().out
    assert "workbench viewer" in output
    assert viewer.read_text(encoding="utf-8").lower().startswith("<!doctype html>")
    loaded = WorkbenchDefinition.load(data)
    assert len(loaded.nodes) == 154
    assert len(loaded.candidates) == 634


def test_cli_writes_the_complete_visual_suite(tmp_path, capsys):
    suite = tmp_path / "suite"
    assert main(["workbench", "--suite", str(suite)]) == 0
    output = capsys.readouterr().out
    assert "workbench matrix" in output
    assert "workbench feedback" in output
    assert (suite / "index.html").exists()
    assert (suite / "compare-routes.html").exists()
    assert (suite / "path-network.html").exists()
    assert (suite / "build-route.html").exists()
    assert (suite / "feedback-loop.html").exists()
    assert (suite / "workbench.json").exists()


def test_feedback_and_optimization_are_typed_but_not_stages():
    workbench = build_demo_workbench()
    stage_ids = {stage.id for stage in workbench.stages}
    assert not stage_ids.intersection(channel.id for channel in workbench.feedback_channels)
    assert all(channel.validate() == [] for channel in workbench.feedback_channels)
    assert all(profile.validate() == [] for profile in workbench.optimization_profiles)
    assert sum(
        objective.weight
        for objective in workbench.optimization_profiles[0].objectives
    ) == pytest.approx(1.0)


def test_invalid_feedback_and_objective_profiles_are_rejected():
    workbench = build_demo_workbench()
    bad_channel = FeedbackDefinition(
        id="feedback.bad", name="", signal="status", scope="route",
        producer="runner", consumer="learner", action="update",
    )
    bad_profile = OptimizationProfile(
        id="profile.bad", name="Bad", objectives=(
            OptimizationObjective("quality", "sideways", -1),
        ),
    )
    invalid = replace(
        workbench,
        feedback_channels=workbench.feedback_channels + (bad_channel,),
        optimization_profiles=workbench.optimization_profiles + (bad_profile,),
    )
    problems = invalid.validate()
    assert any("feedback channel feedback.bad" in problem for problem in problems)
    assert any("optimization profile profile.bad" in problem for problem in problems)


def test_stage_and_solution_identity_contracts_are_validated():
    workbench = build_demo_workbench()
    broken_stage = replace(workbench.stages[0], name="", success="")
    broken_solution = replace(
        workbench.solutions[0], id="Invalid ID", status="", tags=("same", "same"),
    )
    invalid = replace(
        workbench,
        stages=(broken_stage,) + workbench.stages[1:],
        solutions=(broken_solution,) + workbench.solutions[1:],
    )
    problems = invalid.validate()
    assert any("stage acquire.resolve: name must not be empty" in problem for problem in problems)
    assert any("stage acquire.resolve: success must not be empty" in problem for problem in problems)
    assert any("solution Invalid ID: id" in problem for problem in problems)
    assert any("solution Invalid ID: status must not be empty" in problem for problem in problems)
    assert any("solution Invalid ID: duplicate tag" in problem for problem in problems)


def test_adjacent_stage_contracts_must_connect_before_routes_are_compiled():
    workbench = build_demo_workbench()
    broken = replace(workbench.stages[1], input_type="WrongBoundaryType")
    invalid = replace(
        workbench,
        stages=(workbench.stages[0], broken) + workbench.stages[2:],
    )
    assert any(
        "stage boundary acquire.resolve → acquire.authorize" in problem
        for problem in invalid.validate()
    )


def test_solution_fallbacks_cannot_target_an_unknown_stage():
    workbench = build_demo_workbench()
    solution = workbench.solutions[0]
    invalid_solution = replace(
        solution,
        fallbacks={**solution.fallbacks, "not_a_stage": (workbench.candidates[0].id,)},
    )
    invalid = replace(
        workbench,
        solutions=(invalid_solution,) + workbench.solutions[1:],
    )
    assert any(
        "fallbacks for unknown stage(s): not_a_stage" in problem
        for problem in invalid.validate()
    )


def test_optimization_profile_rejects_duplicate_metric_objectives():
    workbench = build_demo_workbench()
    profile = OptimizationProfile(
        id="profile.duplicate",
        name="Duplicate metric",
        objectives=(
            OptimizationObjective("quality", "maximize", 0.5),
            OptimizationObjective("quality", "maximize", 0.5),
        ),
    )
    invalid = replace(
        workbench,
        optimization_profiles=workbench.optimization_profiles + (profile,),
    )
    assert any(
        "duplicate objective metric(s): quality" in problem
        for problem in invalid.validate()
    )


def test_execution_receipts_and_optimizer_decisions_round_trip_and_validate():
    workbench = build_demo_workbench()
    solution = workbench.solutions[0]
    stage = workbench.stages[0]
    selected = solution.route[stage.id]
    receipt = ExecutionReceipt(
        id="receipt.demo.1",
        solution_id=solution.id,
        outcome="accepted",
        accepted=True,
        verifier="demo.verify.oracle",
        metrics={"quality": 0.86, "latency_ms": 410},
        stage_outcomes={stage.id: {"outcome": "succeeded"}},
        macro_stage_outcomes={"acquire": {"outcome": "succeeded"}},
        provenance={"source": "test_fixture"},
        evidence_source="test_fixture",
    )
    decision = OptimizationDecision(
        id="decision.demo.1",
        scope="substep",
        profile_id=workbench.optimization_profiles[0].id,
        selected={stage.id: selected},
        eligible_count=len(stage.candidates),
        score=0.81,
        objective_values={"quality_prior": 0.72},
        contributions={"quality_prior": 0.5},
        alternatives=tuple(stage.candidates[1:3]),
        evidence_snapshot="test_fixture",
        reason="highest eligible normalized score",
    )
    enriched = replace(
        workbench,
        receipts=(receipt,),
        optimization_decisions=(decision,),
    ).assert_valid()
    restored = WorkbenchDefinition.from_dict(enriched.to_dict())
    assert restored.receipts == (receipt,)
    assert restored.optimization_decisions == (decision,)


def test_receipts_and_decisions_cannot_reference_unknown_graph_objects():
    workbench = build_demo_workbench()
    receipt = ExecutionReceipt(
        id="receipt.bad",
        solution_id="missing.solution",
        outcome="failed",
        stage_outcomes={"missing_stage": {}},
        macro_stage_outcomes={"missing_macro": {}},
    )
    decision = OptimizationDecision(
        id="decision.bad",
        scope="route",
        profile_id="missing.profile",
        selected={"missing_stage": "missing.candidate"},
        eligible_count=1,
        alternatives=("missing.candidate",),
    )
    invalid = replace(
        workbench,
        receipts=(receipt,),
        optimization_decisions=(decision,),
    )
    problems = invalid.validate()
    assert any("references unknown solution" in problem for problem in problems)
    assert any("outcomes for unknown stage" in problem for problem in problems)
    assert any("outcomes for unknown macro stage" in problem for problem in problems)
    assert any("references unknown profile" in problem for problem in problems)
    assert any("selects unknown stage" in problem for problem in problems)
    assert any("unknown alternative" in problem for problem in problems)


def test_cli_emits_canonical_manifests_for_the_existing_registry(capsys):
    assert main(["nodes", "--json"]) == 0
    manifests = json.loads(capsys.readouterr().out)
    assert manifests
    assert all({"id", "kind", "inputs", "outputs"}.issubset(item) for item in manifests)


def test_cli_can_render_exported_custom_data(tmp_path):
    original = build_demo_workbench()
    data = tmp_path / "input.json"
    data.write_text(json.dumps(original.to_dict()), encoding="utf-8")
    viewer = tmp_path / "custom.html"
    assert main(["viewer", str(data), "-o", str(viewer)]) == 0
    assert original.title in viewer.read_text(encoding="utf-8")
