"""Strict authoring helpers for reusable linear solution templates.

The full :class:`~solutiongraph.templates.SolutionTemplate` model supports any
valid DAG.  ``LinearTemplateBlueprint`` is a deliberately smaller convenience
format for the common left-to-right stage/slot matrix.  It removes boilerplate
without weakening validation or hiding implementation choices.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from solutiongraph.model import (
    ID_RE,
    Edge,
    GraphInput,
    GraphOutput,
    Port,
    ProgramGraph,
    SemanticSlot,
    ValueType,
    canonical_json,
)
from solutiongraph.templates import RefinementPolicy, SolutionTemplate, TemplateStage

BLUEPRINT_MODEL_VERSION = "0.1"


def _duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if values.count(value) > 1}))


def _validate_identifiers(values: tuple[str, ...], path: str) -> list[str]:
    problems: list[str] = []
    duplicates = _duplicates(values)
    if duplicates:
        problems.append(f"{path} must be unique: {', '.join(duplicates)}")
    if any(not ID_RE.fullmatch(value) for value in values):
        problems.append(f"{path} must contain lowercase namespaced identifiers")
    return problems


def _strict_object(
    value: Any,
    *,
    path: str,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    keys = set(value)
    missing = sorted(required - keys)
    unknown = sorted(keys - required - optional)
    if missing:
        raise ValueError(f"{path} is missing: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{path} has unknown field(s): {', '.join(unknown)}")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{path} must be a string")
    return value


def _strings(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{path} must be an array of strings")
    return tuple(value)


def _extensions(value: Any, path: str) -> tuple[tuple[str, Any], ...]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    return tuple(sorted(value.items()))


@dataclass(frozen=True)
class SlotBlueprint:
    """One explicit atomic obligation in an author-friendly blueprint."""

    id: str
    purpose: str
    success_contract: str
    required_capabilities: tuple[str, ...]
    allowed_effects: tuple[str, ...] = ()
    optional: bool = False

    def validate(self, path: str = "slot") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a lowercase namespaced identifier")
        if not self.purpose.strip():
            problems.append(f"{path}.purpose must not be empty")
        if not self.success_contract.strip():
            problems.append(f"{path}.success_contract must not be empty")
        if not self.required_capabilities:
            problems.append(f"{path}.required_capabilities must not be empty")
        problems.extend(
            _validate_identifiers(
                self.required_capabilities,
                f"{path}.required_capabilities",
            )
        )
        problems.extend(_validate_identifiers(self.allowed_effects, f"{path}.allowed_effects"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "purpose": self.purpose,
            "success_contract": self.success_contract,
            "required_capabilities": list(self.required_capabilities),
            "allowed_effects": list(self.allowed_effects),
            "optional": self.optional,
        }

    @classmethod
    def from_dict(cls, value: Any, path: str = "slot") -> SlotBlueprint:
        data = _strict_object(
            value,
            path=path,
            required=frozenset(
                {"id", "purpose", "success_contract", "required_capabilities"}
            ),
            optional=frozenset({"allowed_effects", "optional"}),
        )
        optional = data.get("optional", False)
        if not isinstance(optional, bool):
            raise ValueError(f"{path}.optional must be a boolean")
        return cls(
            id=_string(data["id"], f"{path}.id"),
            purpose=_string(data["purpose"], f"{path}.purpose"),
            success_contract=_string(
                data["success_contract"], f"{path}.success_contract"
            ),
            required_capabilities=_strings(
                data["required_capabilities"], f"{path}.required_capabilities"
            ),
            allowed_effects=_strings(
                data.get("allowed_effects", []), f"{path}.allowed_effects"
            ),
            optional=optional,
        )


@dataclass(frozen=True)
class StageBlueprint:
    """One visible submatrix with an ordered set of atomic slots."""

    id: str
    title: str
    description: str
    slots: tuple[SlotBlueprint, ...]

    def validate(self, path: str = "stage") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a lowercase namespaced identifier")
        if not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.title and description must not be empty")
        if not self.slots:
            problems.append(f"{path}.slots must not be empty")
        slot_ids = tuple(slot.id for slot in self.slots)
        duplicates = _duplicates(slot_ids)
        if duplicates:
            problems.append(f"{path}.slots ids must be unique: {', '.join(duplicates)}")
        for index, slot in enumerate(self.slots):
            problems.extend(slot.validate(f"{path}.slots[{index}]"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "slots": [slot.to_dict() for slot in self.slots],
        }

    @classmethod
    def from_dict(cls, value: Any, path: str = "stage") -> StageBlueprint:
        data = _strict_object(
            value,
            path=path,
            required=frozenset({"id", "title", "description", "slots"}),
        )
        raw_slots = data["slots"]
        if not isinstance(raw_slots, list):
            raise ValueError(f"{path}.slots must be an array")
        return cls(
            id=_string(data["id"], f"{path}.id"),
            title=_string(data["title"], f"{path}.title"),
            description=_string(data["description"], f"{path}.description"),
            slots=tuple(
                SlotBlueprint.from_dict(slot, f"{path}.slots[{index}]")
                for index, slot in enumerate(raw_slots)
            ),
        )


@dataclass(frozen=True)
class LinearTemplateBlueprint:
    """Portable source format for a left-to-right stage/slot template."""

    id: str
    version: str
    title: str
    description: str
    task: str
    success_contract: str
    domains: tuple[str, ...]
    tags: tuple[str, ...]
    stages: tuple[StageBlueprint, ...]
    allowed_effects: tuple[str, ...] = ()
    granted_permissions: tuple[str, ...] = ()
    invariants: tuple[str, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "blueprint") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a lowercase namespaced identifier")
        for label, value in (
            ("version", self.version),
            ("title", self.title),
            ("description", self.description),
            ("task", self.task),
            ("success_contract", self.success_contract),
        ):
            if not value.strip():
                problems.append(f"{path}.{label} must not be empty")
        if not self.stages:
            problems.append(f"{path}.stages must not be empty")
        stage_ids = tuple(stage.id for stage in self.stages)
        duplicates = _duplicates(stage_ids)
        if duplicates:
            problems.append(f"{path}.stages ids must be unique: {', '.join(duplicates)}")
        for index, stage in enumerate(self.stages):
            problems.extend(stage.validate(f"{path}.stages[{index}]"))
        all_slot_ids = tuple(slot.id for stage in self.stages for slot in stage.slots)
        duplicates = _duplicates(all_slot_ids)
        if duplicates:
            problems.append(
                f"{path}.slots must be globally unique: {', '.join(duplicates)}"
            )
        for label, values in (
            ("domains", self.domains),
            ("tags", self.tags),
            ("allowed_effects", self.allowed_effects),
            ("granted_permissions", self.granted_permissions),
        ):
            problems.extend(_validate_identifiers(values, f"{path}.{label}"))
        if len(self.invariants) != len(set(self.invariants)):
            problems.append(f"{path}.invariants must be unique")
        extension_keys = tuple(key for key, _ in self.extensions)
        problems.extend(_validate_identifiers(extension_keys, f"{path}.extensions"))
        if any("." not in key for key in extension_keys):
            problems.append(f"{path}.extensions keys must be namespaced")
        for key, value in self.extensions:
            try:
                canonical_json(value)
            except (TypeError, ValueError):
                problems.append(f"{path}.extensions.{key} must be JSON serialisable")
        return problems

    def to_template(self) -> SolutionTemplate:
        """Compile the authoring blueprint into the normative template model."""
        problems = self.validate()
        if problems:
            raise ValueError("invalid linear template blueprint:\n- " + "\n- ".join(problems))

        flat_slots = tuple(slot for stage in self.stages for slot in stage.slots)
        state_types = tuple(
            ValueType(f"{self.id}.state-{index}")
            for index in range(len(flat_slots) + 1)
        )
        slots: list[SemanticSlot] = []
        edges: list[Edge] = []
        cursor = 0
        for stage in self.stages:
            for slot in stage.slots:
                slots.append(
                    SemanticSlot(
                        id=slot.id,
                        purpose=slot.purpose,
                        inputs=(Port("state", state_types[cursor]),),
                        outputs=(Port("state", state_types[cursor + 1]),),
                        success_contract=slot.success_contract,
                        group=(stage.id,),
                        required_capabilities=slot.required_capabilities,
                        allowed_effects=slot.allowed_effects,
                        optional=slot.optional,
                    )
                )
                if cursor:
                    edges.append(
                        Edge(flat_slots[cursor - 1].id, "state", slot.id, "state")
                    )
                cursor += 1

        program = ProgramGraph(
            id=f"program.{self.id}",
            version=self.version,
            task=self.task,
            success_contract=self.success_contract,
            slots=tuple(slots),
            edges=tuple(edges),
            inputs=(GraphInput("input", state_types[0], flat_slots[0].id, "state"),),
            outputs=(
                GraphOutput("result", state_types[-1], flat_slots[-1].id, "state"),
            ),
            allowed_effects=self.allowed_effects,
            granted_permissions=self.granted_permissions,
            invariants=self.invariants,
        )
        template = SolutionTemplate(
            id=self.id,
            version=self.version,
            title=self.title,
            description=self.description,
            program=program,
            stages=tuple(
                TemplateStage(
                    stage.id,
                    stage.title,
                    stage.description,
                    tuple(slot.id for slot in stage.slots),
                )
                for stage in self.stages
            ),
            refinements=_default_refinements(self.id),
            domains=self.domains,
            tags=self.tags,
            extensions=(
                ("universal.template-source", "linear-blueprint"),
                *self.extensions,
            ),
        )
        template_problems = template.validate()
        if template_problems:
            raise ValueError(
                "blueprint compiled to an invalid solution template:\n- "
                + "\n- ".join(template_problems)
            )
        return template

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint_model_version": BLUEPRINT_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "task": self.task,
            "success_contract": self.success_contract,
            "domains": list(self.domains),
            "tags": list(self.tags),
            "allowed_effects": list(self.allowed_effects),
            "granted_permissions": list(self.granted_permissions),
            "invariants": list(self.invariants),
            "stages": [stage.to_dict() for stage in self.stages],
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, value: Any, path: str = "blueprint") -> LinearTemplateBlueprint:
        data = _strict_object(
            value,
            path=path,
            required=frozenset(
                {
                    "blueprint_model_version",
                    "id",
                    "version",
                    "title",
                    "description",
                    "task",
                    "success_contract",
                    "domains",
                    "tags",
                    "stages",
                }
            ),
            optional=frozenset(
                {
                    "allowed_effects",
                    "granted_permissions",
                    "invariants",
                    "extensions",
                }
            ),
        )
        model_version = _string(
            data["blueprint_model_version"], f"{path}.blueprint_model_version"
        )
        if model_version != BLUEPRINT_MODEL_VERSION:
            raise ValueError(
                f"{path}.blueprint_model_version must be {BLUEPRINT_MODEL_VERSION!r}"
            )
        raw_stages = data["stages"]
        if not isinstance(raw_stages, list):
            raise ValueError(f"{path}.stages must be an array")
        return cls(
            id=_string(data["id"], f"{path}.id"),
            version=_string(data["version"], f"{path}.version"),
            title=_string(data["title"], f"{path}.title"),
            description=_string(data["description"], f"{path}.description"),
            task=_string(data["task"], f"{path}.task"),
            success_contract=_string(
                data["success_contract"], f"{path}.success_contract"
            ),
            domains=_strings(data["domains"], f"{path}.domains"),
            tags=_strings(data["tags"], f"{path}.tags"),
            stages=tuple(
                StageBlueprint.from_dict(stage, f"{path}.stages[{index}]")
                for index, stage in enumerate(raw_stages)
            ),
            allowed_effects=_strings(
                data.get("allowed_effects", []), f"{path}.allowed_effects"
            ),
            granted_permissions=_strings(
                data.get("granted_permissions", []), f"{path}.granted_permissions"
            ),
            invariants=_strings(data.get("invariants", []), f"{path}.invariants"),
            extensions=_extensions(data.get("extensions", {}), f"{path}.extensions"),
        )


def _default_refinements(template_id: str) -> tuple[RefinementPolicy, ...]:
    return (
        RefinementPolicy(
            id=f"{template_id}.repair-rejected-route",
            trigger="outcome.rejected",
            scopes=("program",),
            proposal_strategy="search.sprout",
            evaluation_contract=(
                "Compile the proposal and re-run the task's independent acceptance oracle."
            ),
            stop_contract=(
                "Stop at acceptance, explicit experiment exhaustion, or eight proposals."
            ),
            max_iterations=8,
            retain_history=True,
        ),
        RefinementPolicy(
            id=f"{template_id}.revisit-registry",
            trigger="registry.coverage-gap",
            scopes=("program",),
            proposal_strategy="discovery.refresh",
            evaluation_contract=(
                "Negotiate again, preserve a new discovery receipt, then recompile."
            ),
            stop_contract="Stop after one new closed-world snapshot is admitted.",
            max_iterations=1,
            refresh_registry_snapshot=True,
        ),
    )


def build_reference_linear_template(
    *,
    template_id: str,
    title: str,
    description: str,
    domains: tuple[str, ...],
    tags: tuple[str, ...],
    stages: tuple[tuple[str, str, str, tuple[tuple[str, str], ...]], ...],
) -> SolutionTemplate:
    """Build a checked-in reference template from concise stage data.

    Reference templates use a mechanically derived success contract. External
    authors should use ``LinearTemplateBlueprint`` and write each contract
    explicitly.
    """
    blueprint = LinearTemplateBlueprint(
        id=template_id,
        version="1.0.0",
        title=title,
        description=description,
        task=f"Instantiate the {title} obligations for a task-specific contract.",
        success_contract=(
            "A task-specific independent acceptance oracle accepts the final result."
        ),
        domains=domains,
        tags=tags,
        stages=tuple(
            StageBlueprint(
                id=stage_id,
                title=stage_title,
                description=stage_description,
                slots=tuple(
                    SlotBlueprint(
                        id=slot_id,
                        purpose=purpose,
                        success_contract=(
                            f"{purpose.rstrip('.')} and preserve every invariant required "
                            "by later slots."
                        ),
                        required_capabilities=(
                            f"{template_id}.{slot_id}.perform",
                        ),
                    )
                    for slot_id, purpose in stage_slots
                ),
            )
            for stage_id, stage_title, stage_description, stage_slots in stages
        ),
        extensions=(("universal.template-state", "schematic; refine before execution"),),
    )
    return blueprint.to_template()


def load_linear_blueprint(path: str | Path) -> LinearTemplateBlueprint:
    """Load and strictly parse one JSON blueprint."""
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source}: invalid JSON: {exc.msg}") from exc
    return LinearTemplateBlueprint.from_dict(value, str(source))


def write_solution_template(template: SolutionTemplate, path: str | Path) -> Path:
    """Write one canonical, portable solution-template JSON document."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(template.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


__all__ = [
    "BLUEPRINT_MODEL_VERSION",
    "LinearTemplateBlueprint",
    "SlotBlueprint",
    "StageBlueprint",
    "build_reference_linear_template",
    "load_linear_blueprint",
    "write_solution_template",
]
