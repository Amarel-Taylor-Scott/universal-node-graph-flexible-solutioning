from __future__ import annotations

from solutiongraph.nexting.contracts import KnowledgeState
from solutiongraph.nexting.questions import (
    QuestionAxis,
    QuestionLens,
    QuestionTemplate,
    QuestionUniverse,
    reference_question_universe,
)


def _state() -> KnowledgeState:
    return KnowledgeState(
        id="state.question-universe",
        revision="1",
        goal="Build a robust competition solution.",
    )


def test_reference_question_universe_is_large_but_lazy() -> None:
    universe = reference_question_universe()
    expected = len(universe.templates)
    for axis in universe.axes:
        expected *= axis.cardinality
    assert universe.cardinality == expected
    assert universe.cardinality > 500
    assert universe.sample(5, seed=42) == universe.sample(5, seed=42)


def test_rendered_question_records_template_and_genome() -> None:
    universe = reference_question_universe()
    genome = universe.at(0)
    rendered = universe.render(
        _state(),
        genome,
        question_id="question.rendered-next",
        target_ref="graph.current-solution",
    )
    assert rendered.question.state_digest == _state().digest
    assert rendered.question.target_ref == "graph.current-solution"
    assert rendered.question.extensions["question.genome_digest"] == genome.digest
    assert rendered.template_digest.startswith("sha256:")
    assert not rendered.question.validate()


def test_optional_axis_adds_a_no-lens_variant() -> None:
    template = QuestionTemplate(
        id="question-template.test",
        version="1.0.0",
        title="Test",
        prompt="What is next for {target}?",
        intent="question-intent.test",
    )
    axis = QuestionAxis(
        id="question.optional-lens",
        values=(
            QuestionLens(
                id="lens.optional.test",
                instruction="Use the optional test lens.",
            ),
        ),
        optional=True,
    )
    universe = QuestionUniverse((template,), (axis,))
    assert universe.cardinality == 2
    assert universe.at(0).assignments == ()
    assert universe.at(1).assignment_map == {
        "question.optional-lens": "lens.optional.test"
    }
