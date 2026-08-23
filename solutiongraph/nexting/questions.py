"""Composable, lazy What-Is-Next question programs.

A large question bank should be represented by templates and orthogonal lenses,
not by checking millions of copied prompt strings into source control.  Each
rendered question is reproducible from its genome, state digest, context policy,
and target scope.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import prod
from random import Random
from typing import Any

from solutiongraph.model import ID_RE, canonical_json, sha256_digest
from solutiongraph.nexting.contracts import CORE_ACTION_KINDS, KnowledgeState, NextQuestion

QUESTION_PROGRAM_MODEL_VERSION = "0.1"


@dataclass(frozen=True)
class QuestionLens:
    id: str
    instruction: str
    tags: tuple[str, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "lens") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.instruction.strip():
            problems.append(f"{path}.instruction must not be empty")
        if len(self.tags) != len(set(self.tags)) or any(
            not ID_RE.fullmatch(tag) for tag in self.tags
        ):
            problems.append(f"{path}.tags must contain unique namespaced identifiers")
        try:
            canonical_json(dict(self.extensions))
        except (TypeError, ValueError):
            problems.append(f"{path}.extensions must be JSON serialisable")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "instruction": self.instruction,
            "tags": list(self.tags),
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class QuestionAxis:
    id: str
    values: tuple[QuestionLens, ...]
    optional: bool = False

    @property
    def cardinality(self) -> int:
        return len(self.values) + (1 if self.optional else 0)

    def validate(self, path: str = "axis") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.values:
            problems.append(f"{path}.values must not be empty")
        ids = [value.id for value in self.values]
        if len(ids) != len(set(ids)):
            problems.append(f"{path}.values ids must be unique")
        for index, value in enumerate(self.values):
            problems.extend(value.validate(f"{path}.values[{index}]"))
        return problems

    def value_at(self, offset: int) -> QuestionLens | None:
        if self.optional:
            if offset == 0:
                return None
            offset -= 1
        return self.values[offset]


@dataclass(frozen=True)
class QuestionTemplate:
    id: str
    version: str
    title: str
    prompt: str
    intent: str
    allowed_action_kinds: tuple[str, ...] = CORE_ACTION_KINDS
    default_scope: str = "scope.problem"
    default_context_policy_id: str = "context.selective"
    required_fact_predicates: tuple[str, ...] = ()
    required_reference_kinds: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "template") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("intent", self.intent),
            ("default_scope", self.default_scope),
            ("default_context_policy_id", self.default_context_policy_id),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        if not self.version.strip() or not self.title.strip() or not self.prompt.strip():
            problems.append(f"{path}.version, title, and prompt must not be empty")
        for label, values in (
            ("allowed_action_kinds", self.allowed_action_kinds),
            ("required_fact_predicates", self.required_fact_predicates),
            ("required_reference_kinds", self.required_reference_kinds),
            ("tags", self.tags),
        ):
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not ID_RE.fullmatch(value) for value in values):
                problems.append(
                    f"{path}.{label} must contain namespaced identifiers"
                )
        if not self.allowed_action_kinds:
            problems.append(f"{path}.allowed_action_kinds must not be empty")
        try:
            canonical_json(dict(self.extensions))
        except (TypeError, ValueError):
            problems.append(f"{path}.extensions must be JSON serialisable")
        return problems

    def applicable(self, state: KnowledgeState) -> bool:
        predicates = {fact.predicate for fact in state.facts}
        kinds = {reference.kind for reference in state.references}
        return set(self.required_fact_predicates).issubset(predicates) and set(
            self.required_reference_kinds
        ).issubset(kinds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_program_model_version": QUESTION_PROGRAM_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "prompt": self.prompt,
            "intent": self.intent,
            "allowed_action_kinds": list(self.allowed_action_kinds),
            "default_scope": self.default_scope,
            "default_context_policy_id": self.default_context_policy_id,
            "required_fact_predicates": list(self.required_fact_predicates),
            "required_reference_kinds": list(self.required_reference_kinds),
            "tags": list(self.tags),
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class QuestionGenome:
    template_id: str
    assignments: tuple[tuple[str, str], ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def assignment_map(self) -> dict[str, str]:
        return dict(self.assignments)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "assignments": dict(self.assignments),
        }


@dataclass(frozen=True)
class RenderedNextQuestion:
    question: NextQuestion
    template_digest: str
    genome: QuestionGenome
    applied_lens_ids: tuple[str, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question.to_dict(),
            "template_digest": self.template_digest,
            "genome": self.genome.to_dict(),
            "applied_lens_ids": list(self.applied_lens_ids),
        }


class QuestionUniverse:
    """Mixed-radix access to templates × lenses without eager expansion."""

    def __init__(
        self,
        templates: Sequence[QuestionTemplate],
        axes: Sequence[QuestionAxis] = (),
    ) -> None:
        self.templates = tuple(templates)
        self.axes = tuple(axes)
        problems: list[str] = []
        if not self.templates:
            problems.append("question universe must contain at least one template")
        template_ids = [template.id for template in self.templates]
        axis_ids = [axis.id for axis in self.axes]
        if len(template_ids) != len(set(template_ids)):
            problems.append("question template ids must be unique")
        if len(axis_ids) != len(set(axis_ids)):
            problems.append("question axis ids must be unique")
        for index, template in enumerate(self.templates):
            problems.extend(template.validate(f"templates[{index}]"))
        for index, axis in enumerate(self.axes):
            problems.extend(axis.validate(f"axes[{index}]"))
        if problems:
            raise ValueError("invalid question universe: " + "; ".join(problems))
        self._template_map = {template.id: template for template in self.templates}
        self._axis_map = {axis.id: axis for axis in self.axes}

    @property
    def lens_cardinality(self) -> int:
        return prod(axis.cardinality for axis in self.axes) if self.axes else 1

    @property
    def cardinality(self) -> int:
        return len(self.templates) * self.lens_cardinality

    def at(self, index: int) -> QuestionGenome:
        if index < 0 or index >= self.cardinality:
            raise IndexError(index)
        template_index, lens_index = divmod(index, self.lens_cardinality)
        assignments: list[tuple[str, str]] = []
        remainder = lens_index
        for axis in reversed(self.axes):
            remainder, offset = divmod(remainder, axis.cardinality)
            value = axis.value_at(offset)
            if value is not None:
                assignments.append((axis.id, value.id))
        assignments.reverse()
        return QuestionGenome(
            template_id=self.templates[template_index].id,
            assignments=tuple(assignments),
        )

    def sample(self, count: int, *, seed: int) -> tuple[QuestionGenome, ...]:
        if count < 0:
            raise ValueError("count must be non-negative")
        count = min(count, self.cardinality)
        random = Random(seed)
        return tuple(
            self.at(index)
            for index in random.sample(range(self.cardinality), count)
        )

    def render(
        self,
        state: KnowledgeState,
        genome: QuestionGenome,
        *,
        question_id: str,
        target_ref: str = "",
        parent_question_id: str = "",
        depth: int = 0,
        scope_override: str = "",
        context_policy_override: str = "",
    ) -> RenderedNextQuestion:
        try:
            template = self._template_map[genome.template_id]
        except KeyError as exc:
            raise ValueError(f"unknown question template {genome.template_id!r}") from exc
        if not template.applicable(state):
            raise ValueError(
                f"question template {template.id} is not applicable to the knowledge state"
            )
        assignments = genome.assignment_map
        unknown_axes = sorted(set(assignments) - set(self._axis_map))
        if unknown_axes:
            raise ValueError(
                "question genome references unknown axes: " + ", ".join(unknown_axes)
            )
        lenses: list[QuestionLens] = []
        for axis_id, lens_id in genome.assignments:
            axis = self._axis_map[axis_id]
            try:
                lens = next(value for value in axis.values if value.id == lens_id)
            except StopIteration as exc:
                raise ValueError(
                    f"unknown lens {lens_id!r} for question axis {axis_id!r}"
                ) from exc
            lenses.append(lens)
        lens_text = " ".join(lens.instruction.strip() for lens in lenses)
        formatting = {
            "goal": state.goal,
            "scope": scope_override or template.default_scope,
            "target": target_ref or "the current problem",
            "lens": lens_text,
            **assignments,
        }
        try:
            base_prompt = template.prompt.format_map(_SafeFormatMap(formatting))
        except (ValueError, KeyError) as exc:
            raise ValueError(f"question template rendering failed: {exc}") from exc
        prompt = " ".join(part for part in (base_prompt.strip(), lens_text) if part)
        context_policy = context_policy_override or assignments.get(
            "question.context-policy",
            template.default_context_policy_id,
        )
        scope = scope_override or assignments.get(
            "question.scope",
            template.default_scope,
        )
        question = NextQuestion(
            id=question_id,
            state_digest=state.digest,
            prompt=prompt,
            scope=scope,
            target_ref=target_ref,
            allowed_action_kinds=template.allowed_action_kinds,
            context_policy_id=context_policy,
            recipe_ref=state.recipe_ref,
            parent_question_id=parent_question_id,
            depth=depth,
            extensions={
                "question.template_id": template.id,
                "question.template_digest": template.digest,
                "question.genome_digest": genome.digest,
                "question.intent": template.intent,
                "question.lens_ids": [lens.id for lens in lenses],
            },
        )
        problems = question.validate()
        if problems:
            raise ValueError("rendered NextQuestion is invalid: " + "; ".join(problems))
        return RenderedNextQuestion(
            question=question,
            template_digest=template.digest,
            genome=genome,
            applied_lens_ids=tuple(lens.id for lens in lenses),
        )


class _SafeFormatMap(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


REFERENCE_NEXT_TEMPLATES = (
    QuestionTemplate(
        id="question-template.next-action",
        version="1.0.0",
        title="Next useful action",
        prompt=(
            "Given the present evidence and the goal '{goal}', what bounded work "
            "should happen next for {target}?"
        ),
        intent="question-intent.next-action",
    ),
    QuestionTemplate(
        id="question-template.missing-information",
        version="1.0.0",
        title="Missing information",
        prompt=(
            "What important information is still missing before a responsible "
            "next decision can be made for {target}, and which cheapest tests or "
            "research actions would resolve it?"
        ),
        intent="question-intent.missing-information",
        allowed_action_kinds=(
            "next.gather-context",
            "next.run-probe",
            "next.research",
            "next.ask-council",
            "next.spawn-subloop",
            "next.pause",
        ),
    ),
    QuestionTemplate(
        id="question-template.largest-weakness",
        version="1.0.0",
        title="Largest weakness",
        prompt=(
            "What is the largest evidence-backed weakness in {target}, and what "
            "single change or discriminating experiment has the highest expected "
            "value?"
        ),
        intent="question-intent.largest-weakness",
    ),
    QuestionTemplate(
        id="question-template.remove-excess",
        version="1.0.0",
        title="Remove unnecessary work",
        prompt=(
            "What has been included in {target} that is unnecessary, duplicative, "
            "fragile, or lower-value than its cost, and what ablation should test "
            "that claim?"
        ),
        intent="question-intent.simplify",
        allowed_action_kinds=(
            "next.run-probe",
            "next.mutate-graph",
            "next.evaluate",
            "next.compare",
            "next.stop",
        ),
    ),
    QuestionTemplate(
        id="question-template.analogy",
        version="1.0.0",
        title="Solve by analogy",
        prompt=(
            "Which previously solved problem, blueprint, scientific method, or "
            "engineering pattern is most analogous to {target}, where does the "
            "analogy break, and what should be tried next?"
        ),
        intent="question-intent.analogy",
        allowed_action_kinds=(
            "next.retrieve-blueprint",
            "next.research",
            "next.instantiate-graph",
            "next.propose-graph",
            "next.spawn-subloop",
        ),
    ),
    QuestionTemplate(
        id="question-template.opposite-case",
        version="1.0.0",
        title="Opposite and counterfactual",
        prompt=(
            "Assume the current leading explanation or route for {target} is "
            "wrong. What opposite hypothesis, counterexample, or alternative graph "
            "would be most informative to test next?"
        ),
        intent="question-intent.counterfactual",
    ),
)

REFERENCE_NEXT_AXES = (
    QuestionAxis(
        id="question.stance",
        values=(
            QuestionLens(
                id="lens.stance.constructive",
                instruction="Be constructive and propose an implementable next action.",
            ),
            QuestionLens(
                id="lens.stance.skeptical",
                instruction="Act as a skeptical reviewer and demand falsifiable evidence.",
            ),
            QuestionLens(
                id="lens.stance.adversarial",
                instruction="Try to break the current assumptions before improving them.",
            ),
        ),
    ),
    QuestionAxis(
        id="question.granularity",
        values=(
            QuestionLens(
                id="lens.granularity.atomic",
                instruction="Return one atomic next action.",
            ),
            QuestionLens(
                id="lens.granularity.subgraph",
                instruction="Consider the smallest useful subgraph-level intervention.",
            ),
            QuestionLens(
                id="lens.granularity.portfolio",
                instruction="Return a bounded portfolio of complementary next actions.",
            ),
        ),
    ),
    QuestionAxis(
        id="question.theory",
        values=(
            QuestionLens(
                id="lens.theory.information",
                instruction="Prioritize expected information gain and uncertainty reduction.",
            ),
            QuestionLens(
                id="lens.theory.causal",
                instruction="Separate correlation, intervention, leakage, and causal claims.",
            ),
            QuestionLens(
                id="lens.theory.optimization",
                instruction="Frame the decision as a constrained optimization problem.",
            ),
            QuestionLens(
                id="lens.theory.systems",
                instruction="Account for runtime, memory, hardware, and operational constraints.",
            ),
        ),
        optional=True,
    ),
    QuestionAxis(
        id="question.resource-regime",
        values=(
            QuestionLens(
                id="lens.resources.cheap",
                instruction="Prefer the cheapest discriminating action first.",
            ),
            QuestionLens(
                id="lens.resources.balanced",
                instruction="Balance quality, cost, latency, and reliability.",
            ),
            QuestionLens(
                id="lens.resources.frontier",
                instruction="Permit a high-cost frontier attempt only with a clear hypothesis.",
            ),
        ),
    ),
)


def reference_question_universe() -> QuestionUniverse:
    return QuestionUniverse(REFERENCE_NEXT_TEMPLATES, REFERENCE_NEXT_AXES)


__all__ = [
    "QUESTION_PROGRAM_MODEL_VERSION",
    "REFERENCE_NEXT_AXES",
    "REFERENCE_NEXT_TEMPLATES",
    "QuestionAxis",
    "QuestionGenome",
    "QuestionLens",
    "QuestionTemplate",
    "QuestionUniverse",
    "RenderedNextQuestion",
    "reference_question_universe",
]
