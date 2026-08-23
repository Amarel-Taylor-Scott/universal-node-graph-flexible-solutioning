"""Context exposure, prompt frames, personas, and lazy prompt variation.

Knowledge is larger than a prompt. A context policy selects which summaries a
specific strategy may inspect, and a ContextManifest records both included and
omitted references. Prompt variation is represented as a lazy Cartesian space
rather than millions of copied strings.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import product
from math import prod
from random import Random
from typing import Any

from solutiongraph.model import ID_RE, canonical_json, sha256_digest
from solutiongraph.nexting.contracts import KnowledgeState, NextQuestion

PROMPT_MODEL_VERSION = "0.1"


@dataclass(frozen=True)
class ContextExposurePolicy:
    id: str
    mode: str = "selective"
    include_tags: tuple[str, ...] = ()
    exclude_tags: tuple[str, ...] = ()
    include_reference_ids: tuple[str, ...] = ()
    include_facts: bool = True
    include_unknowns: bool = True
    include_progress: bool = True
    include_prior_attempts: bool = False
    maximum_references: int | None = 20
    maximum_summary_chars: int = 12000
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def blind(cls) -> ContextExposurePolicy:
        return cls(
            id="context.blind",
            mode="blind",
            include_facts=False,
            include_unknowns=False,
            include_progress=False,
            maximum_references=0,
        )

    @classmethod
    def minimal(cls) -> ContextExposurePolicy:
        return cls(id="context.minimal", mode="minimal", maximum_references=0)

    @classmethod
    def selective(cls) -> ContextExposurePolicy:
        return cls(id="context.selective", mode="selective")

    @classmethod
    def full(cls) -> ContextExposurePolicy:
        return cls(id="context.full", mode="full", maximum_references=None)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("context policy id must be namespaced")
        if self.mode not in (
            "blind",
            "minimal",
            "selective",
            "summary",
            "full",
        ):
            problems.append("context policy mode is invalid")
        for label, values in (
            ("include_tags", self.include_tags),
            ("exclude_tags", self.exclude_tags),
            ("include_reference_ids", self.include_reference_ids),
        ):
            if len(values) != len(set(values)):
                problems.append(f"{label} must be unique")
        if self.maximum_references is not None and self.maximum_references < 0:
            problems.append("maximum_references must be non-negative or null")
        if self.maximum_summary_chars <= 0:
            problems.append("maximum_summary_chars must be positive")
        try:
            canonical_json(dict(self.extensions))
        except (TypeError, ValueError):
            problems.append("context policy extensions must be JSON serialisable")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_model_version": PROMPT_MODEL_VERSION,
            "id": self.id,
            "mode": self.mode,
            "include_tags": list(self.include_tags),
            "exclude_tags": list(self.exclude_tags),
            "include_reference_ids": list(self.include_reference_ids),
            "include_facts": self.include_facts,
            "include_unknowns": self.include_unknowns,
            "include_progress": self.include_progress,
            "include_prior_attempts": self.include_prior_attempts,
            "maximum_references": self.maximum_references,
            "maximum_summary_chars": self.maximum_summary_chars,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class PersonaFrame:
    id: str
    role: str = "general expert"
    stance: str = "balanced"
    theory: str = ""
    analogy: str = ""
    language: str = "English"
    era: str = "present"
    objective: str = "solution quality"
    resource_regime: str = "declared budget"
    additional_instruction: str = ""

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("persona id must be namespaced")
        for label in (
            "role",
            "stance",
            "language",
            "era",
            "objective",
            "resource_regime",
        ):
            if not getattr(self, label).strip():
                problems.append(f"persona {label} must not be empty")
        return problems

    def to_dict(self) -> dict[str, str]:
        return self.__dict__.copy()


PromptPersona = PersonaFrame


@dataclass(frozen=True)
class ContextManifest:
    state_digest: str
    policy_digest: str
    included_reference_ids: tuple[str, ...]
    omitted_reference_ids: tuple[str, ...]
    included_fact_ids: tuple[str, ...]
    included_unknown_ids: tuple[str, ...]
    rendered_summary_digest: str

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_digest": self.state_digest,
            "policy_digest": self.policy_digest,
            "included_reference_ids": list(self.included_reference_ids),
            "omitted_reference_ids": list(self.omitted_reference_ids),
            "included_fact_ids": list(self.included_fact_ids),
            "included_unknown_ids": list(self.included_unknown_ids),
            "rendered_summary_digest": self.rendered_summary_digest,
        }


@dataclass(frozen=True)
class PromptFrame:
    system_instruction: str
    original_task: str
    simplified_task: str
    delegated_goal: str
    next_question: str
    known_summary: str
    unknown_summary: str
    graph_summary: str = ""
    recipe_summary: str = ""
    prior_attempts: str = ""
    constraints: str = ""
    persona: PersonaFrame = field(
        default_factory=lambda: PersonaFrame(id="persona.general-expert")
    )
    response_contract: str = "Return typed JSON proposals only."
    negative_instruction: str = ""
    counterfactual_instruction: str = ""
    additional_instruction: str = ""

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_instruction": self.system_instruction,
            "original_task": self.original_task,
            "simplified_task": self.simplified_task,
            "delegated_goal": self.delegated_goal,
            "next_question": self.next_question,
            "known_summary": self.known_summary,
            "unknown_summary": self.unknown_summary,
            "graph_summary": self.graph_summary,
            "recipe_summary": self.recipe_summary,
            "prior_attempts": self.prior_attempts,
            "constraints": self.constraints,
            "persona": self.persona.to_dict(),
            "response_contract": self.response_contract,
            "negative_instruction": self.negative_instruction,
            "counterfactual_instruction": self.counterfactual_instruction,
            "additional_instruction": self.additional_instruction,
        }


@dataclass(frozen=True)
class PromptContext:
    state: KnowledgeState
    question: NextQuestion
    exposure: ContextExposurePolicy
    persona: PersonaFrame
    original_task: str = ""
    simplified_task: str = ""
    system_instruction: str = (
        "You are proposing the next useful unit of work. Do not claim that a "
        "proposal has executed, compiled, or passed evaluation."
    )
    response_contract: str = "Return typed JSON proposals only."
    graph_summary: str = ""
    recipe_summary: str = ""
    prior_attempts: str = ""
    constraints: str = ""
    negative_instruction: str = ""
    counterfactual_instruction: str = ""
    additional_instruction: str = ""


class PromptComposer:
    """Compile a stable prompt and a receipt for its exact knowledge exposure."""

    def select_references(
        self,
        state: KnowledgeState,
        policy: ContextExposurePolicy,
    ) -> tuple[tuple[Any, ...], tuple[str, ...]]:
        if policy.mode in ("blind", "minimal"):
            return (), tuple(item.id for item in state.references)
        include_ids = set(policy.include_reference_ids)
        include_tags = set(policy.include_tags)
        exclude_tags = set(policy.exclude_tags)
        selected = []
        for item in state.references:
            tags = set(item.tags)
            if tags & exclude_tags:
                continue
            explicitly_selected = item.id in include_ids
            tag_selected = not include_tags or bool(tags & include_tags)
            if policy.mode == "full" or explicitly_selected or tag_selected:
                selected.append(item)
        selected.sort(key=lambda item: (-item.confidence, item.id))
        if policy.maximum_references is not None:
            selected = selected[: policy.maximum_references]
        selected_ids = {item.id for item in selected}
        omitted = tuple(
            item.id for item in state.references if item.id not in selected_ids
        )
        return tuple(selected), omitted

    def compose(
        self,
        context: PromptContext,
    ) -> tuple[PromptFrame, ContextManifest, str]:
        problems = (
            *context.state.validate(),
            *context.question.validate(),
            *context.exposure.validate(),
            *context.persona.validate(),
        )
        if problems:
            raise ValueError("invalid prompt context: " + "; ".join(problems))
        references, omitted = self.select_references(
            context.state,
            context.exposure,
        )
        known_lines = [
            f"- {item.id}: {item.summary}"
            for item in references
            if item.summary
        ]
        fact_ids: tuple[str, ...] = ()
        if context.exposure.include_facts:
            fact_ids = tuple(item.id for item in context.state.facts)
            known_lines.extend(
                f"- {item.subject} {item.predicate}: {item.value!r} "
                f"(confidence={item.confidence:.2f})"
                for item in context.state.facts
            )
        unknown_ids: tuple[str, ...] = ()
        unknown_summary = ""
        if context.exposure.include_unknowns:
            unknown_ids = tuple(item.id for item in context.state.unknowns)
            unknown_summary = "\n".join(
                f"- {item.id}: {item.question} "
                f"(importance={item.importance:.2f})"
                for item in context.state.unknowns
            )
        known_summary = "\n".join(known_lines)[
            : context.exposure.maximum_summary_chars
        ]
        frame = PromptFrame(
            system_instruction=context.system_instruction,
            original_task=context.original_task,
            simplified_task=context.simplified_task,
            delegated_goal=context.state.goal,
            next_question=context.question.prompt,
            known_summary=known_summary,
            unknown_summary=unknown_summary,
            graph_summary=context.graph_summary,
            recipe_summary=context.recipe_summary,
            prior_attempts=(
                context.prior_attempts
                if context.exposure.include_prior_attempts
                else ""
            ),
            constraints=context.constraints,
            persona=context.persona,
            response_contract=context.response_contract,
            negative_instruction=context.negative_instruction,
            counterfactual_instruction=context.counterfactual_instruction,
            additional_instruction=context.additional_instruction,
        )
        prompt = self.render(frame)
        manifest = ContextManifest(
            state_digest=context.state.digest,
            policy_digest=context.exposure.digest,
            included_reference_ids=tuple(item.id for item in references),
            omitted_reference_ids=omitted,
            included_fact_ids=fact_ids,
            included_unknown_ids=unknown_ids,
            rendered_summary_digest=sha256_digest(
                {"known": known_summary, "unknown": unknown_summary}
            ),
        )
        return frame, manifest, prompt

    @staticmethod
    def render(frame: PromptFrame) -> str:
        persona_lines = filter(
            None,
            (
                f"Role: {frame.persona.role}",
                f"Stance: {frame.persona.stance}",
                (
                    f"Theory: {frame.persona.theory}"
                    if frame.persona.theory
                    else ""
                ),
                (
                    f"Analogy: {frame.persona.analogy}"
                    if frame.persona.analogy
                    else ""
                ),
                f"Language: {frame.persona.language}",
                f"Era: {frame.persona.era}",
                f"Objective: {frame.persona.objective}",
                f"Resource regime: {frame.persona.resource_regime}",
                frame.persona.additional_instruction,
            ),
        )
        sections = [
            ("SYSTEM", frame.system_instruction),
            ("PERSONA", "\n".join(persona_lines)),
            ("ORIGINAL TASK", frame.original_task),
            ("SIMPLIFIED TASK", frame.simplified_task),
            ("DELEGATED GOAL", frame.delegated_goal),
            ("WHAT IS NEXT?", frame.next_question),
            ("WHAT IS PRESENTLY KNOWN", frame.known_summary),
            ("IMPORTANT UNKNOWNS", frame.unknown_summary),
            ("CURRENT GRAPH", frame.graph_summary),
            ("ACTIVE RECIPE", frame.recipe_summary),
            ("PRIOR ATTEMPTS", frame.prior_attempts),
            ("CONSTRAINTS", frame.constraints),
            ("NEGATIVE CHECK", frame.negative_instruction),
            ("COUNTERFACTUAL CHECK", frame.counterfactual_instruction),
            ("ADDITIONAL INSTRUCTION", frame.additional_instruction),
            ("RESPONSE CONTRACT", frame.response_contract),
        ]
        return "\n\n".join(
            f"## {title}\n{text}" for title, text in sections if text.strip()
        )


@dataclass(frozen=True)
class PromptAxis:
    id: str
    values: tuple[str, ...]

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("prompt axis id must be namespaced")
        if not self.values or len(self.values) != len(set(self.values)):
            problems.append("prompt axis values must be nonempty and unique")
        return problems


@dataclass(frozen=True)
class PromptGenome:
    assignments: tuple[tuple[str, str], ...]

    @property
    def digest(self) -> str:
        return sha256_digest(dict(self.assignments))

    @property
    def assignment_map(self) -> dict[str, str]:
        return dict(self.assignments)


PromptVariant = PromptGenome


class PromptVariantSpace:
    """Mixed-radix access to a prompt product without materialization."""

    def __init__(self, axes: Sequence[PromptAxis]) -> None:
        self.axes = tuple(axes)
        problems = [
            problem for axis in self.axes for problem in axis.validate()
        ]
        ids = [axis.id for axis in self.axes]
        if len(ids) != len(set(ids)):
            problems.append("prompt axis ids must be unique")
        if problems:
            raise ValueError(
                "invalid prompt variant space: " + "; ".join(problems)
            )

    @property
    def cardinality(self) -> int:
        return prod(len(axis.values) for axis in self.axes) if self.axes else 1

    def at(self, index: int) -> PromptGenome:
        if index < 0 or index >= self.cardinality:
            raise IndexError(index)
        assignments: list[tuple[str, str]] = []
        remainder = index
        for axis in reversed(self.axes):
            remainder, offset = divmod(remainder, len(axis.values))
            assignments.append((axis.id, axis.values[offset]))
        assignments.reverse()
        return PromptGenome(tuple(assignments))

    def sample(self, count: int, *, seed: int) -> tuple[PromptGenome, ...]:
        if count < 0:
            raise ValueError("count must be non-negative")
        count = min(count, self.cardinality)
        random = Random(seed)
        return tuple(
            self.at(index)
            for index in random.sample(range(self.cardinality), count)
        )

    def iter_all(self):
        if not self.axes:
            yield PromptGenome(())
            return
        for values in product(*(axis.values for axis in self.axes)):
            yield PromptGenome(
                tuple(
                    (axis.id, value)
                    for axis, value in zip(self.axes, values, strict=True)
                )
            )


__all__ = [
    "PROMPT_MODEL_VERSION",
    "ContextExposurePolicy",
    "ContextManifest",
    "PersonaFrame",
    "PromptAxis",
    "PromptComposer",
    "PromptContext",
    "PromptFrame",
    "PromptGenome",
    "PromptPersona",
    "PromptVariant",
    "PromptVariantSpace",
]
