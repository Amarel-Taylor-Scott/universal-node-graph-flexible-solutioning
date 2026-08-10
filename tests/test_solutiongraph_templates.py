from __future__ import annotations

from dataclasses import replace

from solutiongraph import (
    Edge,
    GraphInput,
    GraphOutput,
    Port,
    ProgramGraph,
    RefinementPolicy,
    SemanticSlot,
    SolutionTemplate,
    TemplateCatalog,
    TemplateStage,
    ValueType,
)


def template_fixture() -> SolutionTemplate:
    raw = ValueType("example.raw")
    clean = ValueType("example.clean")
    result = ValueType("example.result")
    program = ProgramGraph(
        id="template.example.pipeline",
        version="1.0.0",
        task="Transform an input into an independently accepted result.",
        success_contract="The task-specific acceptance oracle accepts the result.",
        slots=(
            SemanticSlot(
                "load",
                "Load the task input.",
                (Port("input", raw),),
                (Port("data", raw),),
                "The loaded data is complete and source-identifiable.",
                required_capabilities=("example.load",),
            ),
            SemanticSlot(
                "prepare",
                "Prepare the data for solving.",
                (Port("data", raw),),
                (Port("data", clean),),
                "Preparation preserves required information.",
                required_capabilities=("example.prepare",),
            ),
            SemanticSlot(
                "solve",
                "Produce a candidate result.",
                (Port("data", clean),),
                (Port("result", result),),
                "The result satisfies the requested output schema.",
                required_capabilities=("example.solve",),
            ),
        ),
        edges=(
            Edge("load", "data", "prepare", "data"),
            Edge("prepare", "data", "solve", "data"),
        ),
        inputs=(GraphInput("input", raw, "load", "input"),),
        outputs=(GraphOutput("result", result, "solve", "result"),),
    )
    return SolutionTemplate(
        id="example.general-pipeline",
        version="1.0.0",
        title="General pipeline",
        description="A deliberately small template fixture.",
        program=program,
        stages=(
            TemplateStage(
                "stage.prepare", "Prepare", "Acquire and prepare data.", ("load", "prepare")
            ),
            TemplateStage("stage.solve", "Solve", "Produce the result.", ("solve",)),
        ),
        refinements=(
            RefinementPolicy(
                id="example.refine-solution",
                trigger="outcome.rejected",
                scopes=("stage.solve",),
                proposal_strategy="search.sprout",
                evaluation_contract="Re-run the independent acceptance oracle.",
                stop_contract="Stop after acceptance or the declared iteration budget.",
                max_iterations=5,
            ),
        ),
        domains=("software.general",),
        tags=("pipeline",),
        extensions=(("example.owner", "core"),),
    )


def test_template_separates_atomic_slots_visual_stages_and_control_plane_loops():
    template = template_fixture()

    assert template.validate() == []
    assert [slot.id for slot in template.program.slots] == ["load", "prepare", "solve"]
    assert [stage.slot_ids for stage in template.stages] == [("load", "prepare"), ("solve",)]
    assert all(
        refinement.id not in {slot.id for slot in template.program.slots}
        for refinement in template.refinements
    )


def test_template_stage_partition_is_total_unique_and_forward_only():
    template = template_fixture()
    duplicated = replace(
        template,
        stages=(
            template.stages[0],
            replace(template.stages[1], slot_ids=("prepare", "solve")),
        ),
    )
    problems = duplicated.validate()
    assert any("more than once" in problem for problem in problems)

    backward = replace(template, stages=tuple(reversed(template.stages)))
    assert any("run backward" in problem for problem in backward.validate())


def test_refinement_loops_must_disclose_a_iteration_or_external_budget():
    template = template_fixture()
    unbounded = replace(template.refinements[0], max_iterations=None, budget_ref="")
    assert any("loops are never implicit" in problem for problem in unbounded.validate())

    externally_bounded = replace(
        unbounded,
        budget_ref="experiment.kaggle-budget",
    )
    assert externally_bounded.validate() == []


def test_instantiation_changes_task_identity_without_silently_granting_authority():
    template = template_fixture()
    instantiated = template.instantiate(
        program_id="project.ticket-123",
        program_version="0.1.0",
        task="Solve ticket 123.",
        success_contract="The ticket acceptance suite passes.",
    )

    assert instantiated.id == "project.ticket-123"
    assert instantiated.task == "Solve ticket 123."
    assert instantiated.slots == template.program.slots
    assert instantiated.granted_permissions == ()


def test_catalogue_returns_all_exact_matches_without_hidden_top_k():
    first = template_fixture()
    second = replace(first, id="example.second-pipeline", version="2.0.0")
    catalog = TemplateCatalog((second, first))

    assert catalog.validate() == []
    assert [item.id for item in catalog.matching(domains=("software.general",))] == [
        "example.general-pipeline",
        "example.second-pipeline",
    ]
    assert catalog.matching(tags=("missing",)) == ()
