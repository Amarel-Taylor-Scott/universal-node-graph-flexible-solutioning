"""Domain-neutral semantic templates and bounded refinement policies.

A template describes obligations and their visible stage/submatrix grouping. It
does not select implementations. Refinement policies belong to the control
plane and therefore never appear as executable slots in the contained program.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from solutiongraph.compiler import Compiler
from solutiongraph.model import ID_RE, ProgramGraph, canonical_json, sha256_digest

TEMPLATE_MODEL_VERSION = "0.1"


def _validate_extensions(extensions: tuple[tuple[str, Any], ...], path: str) -> list[str]:
    problems: list[str] = []
    keys = [key for key, _ in extensions]
    if len(keys) != len(set(keys)):
        problems.append(f"{path} keys must be unique")
    for key, value in extensions:
        if not ID_RE.fullmatch(key) or "." not in key:
            problems.append(f"{path}.{key} must use a namespaced key")
        try:
            canonical_json(value)
        except (TypeError, ValueError):
            problems.append(f"{path}.{key} must be JSON serialisable")
    return problems


@dataclass(frozen=True)
class TemplateStage:
    """One visual submatrix containing contiguous atomic semantic slots."""

    id: str
    title: str
    description: str
    slot_ids: tuple[str, ...]
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "stage") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.title and description must not be empty")
        if not self.slot_ids:
            problems.append(f"{path}.slot_ids must not be empty")
        if len(self.slot_ids) != len(set(self.slot_ids)):
            problems.append(f"{path}.slot_ids must be unique")
        if any(not ID_RE.fullmatch(slot_id) for slot_id in self.slot_ids):
            problems.append(f"{path}.slot_ids contains an invalid identifier")
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "slot_ids": list(self.slot_ids),
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class RefinementPolicy:
    """A bounded proposal/evaluation loop outside the executable program."""

    id: str
    trigger: str
    scopes: tuple[str, ...]
    proposal_strategy: str
    evaluation_contract: str
    stop_contract: str
    max_iterations: int | None = None
    budget_ref: str = ""
    retain_history: bool = True
    refresh_registry_snapshot: bool = False
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "refinement") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("trigger", self.trigger),
            ("proposal_strategy", self.proposal_strategy),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        if not self.scopes or len(self.scopes) != len(set(self.scopes)):
            problems.append(f"{path}.scopes must be non-empty and unique")
        if any(scope != "program" and not ID_RE.fullmatch(scope) for scope in self.scopes):
            problems.append(f"{path}.scopes contains an invalid identifier")
        if not self.evaluation_contract.strip() or not self.stop_contract.strip():
            problems.append(f"{path}.evaluation_contract and stop_contract must not be empty")
        if self.max_iterations is not None and self.max_iterations <= 0:
            problems.append(f"{path}.max_iterations must be positive or null")
        if self.max_iterations is None and not self.budget_ref:
            problems.append(
                f"{path} needs max_iterations or an external budget_ref; loops are never implicit"
            )
        if self.budget_ref and not ID_RE.fullmatch(self.budget_ref):
            problems.append(f"{path}.budget_ref must be a namespaced identifier")
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trigger": self.trigger,
            "scopes": list(self.scopes),
            "proposal_strategy": self.proposal_strategy,
            "evaluation_contract": self.evaluation_contract,
            "stop_contract": self.stop_contract,
            "max_iterations": self.max_iterations,
            "budget_ref": self.budget_ref,
            "retain_history": self.retain_history,
            "refresh_registry_snapshot": self.refresh_registry_snapshot,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class SolutionTemplate:
    """A reusable semantic program blueprint, independent of node catalogues."""

    id: str
    version: str
    title: str
    description: str
    program: ProgramGraph
    stages: tuple[TemplateStage, ...]
    refinements: tuple[RefinementPolicy, ...] = ()
    domains: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "template") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.version.strip() or not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.version, title, and description must not be empty")
        stage_ids = [stage.id for stage in self.stages]
        if not stage_ids or len(stage_ids) != len(set(stage_ids)):
            problems.append(f"{path}.stages must be non-empty with unique ids")
        for index, stage in enumerate(self.stages):
            problems.extend(stage.validate(f"{path}.stages[{index}]"))
        for index, refinement in enumerate(self.refinements):
            problems.extend(refinement.validate(f"{path}.refinements[{index}]"))
        for label, values in (("domains", self.domains), ("tags", self.tags)):
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not ID_RE.fullmatch(value) for value in values):
                problems.append(f"{path}.{label} contains an invalid identifier")

        program_slots = {slot.id for slot in self.program.slots}
        grouped = [slot_id for stage in self.stages for slot_id in stage.slot_ids]
        grouped_set = set(grouped)
        duplicates = sorted({slot_id for slot_id in grouped if grouped.count(slot_id) > 1})
        if duplicates:
            problems.append(f"{path}.stages assign slots more than once: " + ", ".join(duplicates))
        missing = sorted(program_slots - grouped_set)
        unknown = sorted(grouped_set - program_slots)
        if missing:
            problems.append(f"{path}.stages omit slots: " + ", ".join(missing))
        if unknown:
            problems.append(f"{path}.stages reference unknown slots: " + ", ".join(unknown))

        stage_by_slot = {
            slot_id: index for index, stage in enumerate(self.stages) for slot_id in stage.slot_ids
        }
        for edge in self.program.edges:
            source_stage = stage_by_slot.get(edge.source_slot)
            target_stage = stage_by_slot.get(edge.target_slot)
            if (
                source_stage is not None
                and target_stage is not None
                and source_stage > target_stage
            ):
                problems.append(
                    f"{path}.stages run backward across edge {edge.source_slot}->{edge.target_slot}"
                )

        valid_scopes = program_slots | set(stage_ids) | {"program"}
        for refinement in self.refinements:
            invalid_scopes = sorted(set(refinement.scopes) - valid_scopes)
            if invalid_scopes:
                problems.append(
                    f"{path}.refinements.{refinement.id} has unknown scopes: "
                    + ", ".join(invalid_scopes)
                )

        problems.extend(
            f"{path}.program: {diagnostic.code} {diagnostic.message}"
            for diagnostic in Compiler().validate_program(self.program)
        )
        problems.extend(_validate_extensions(self.extensions, f"{path}.extensions"))
        return problems

    def instantiate(
        self,
        *,
        program_id: str,
        program_version: str,
        task: str,
        success_contract: str,
        allowed_effects: tuple[str, ...] | None = None,
        granted_permissions: tuple[str, ...] | None = None,
    ) -> ProgramGraph:
        """Create a task-specific semantic program without selecting any nodes."""
        return replace(
            self.program,
            id=program_id,
            version=program_version,
            task=task,
            success_contract=success_contract,
            allowed_effects=(
                self.program.allowed_effects if allowed_effects is None else allowed_effects
            ),
            granted_permissions=(
                self.program.granted_permissions
                if granted_permissions is None
                else granted_permissions
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_model_version": TEMPLATE_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "domains": list(self.domains),
            "tags": list(self.tags),
            "program": self.program.to_dict(),
            "stages": [stage.to_dict() for stage in self.stages],
            "refinements": [refinement.to_dict() for refinement in self.refinements],
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class TemplateCatalog:
    """Small exact catalogue; ranking is explicit and never hides matching entries."""

    templates: tuple[SolutionTemplate, ...]

    def validate(self) -> list[str]:
        problems: list[str] = []
        identities = [(template.id, template.version) for template in self.templates]
        if len(identities) != len(set(identities)):
            problems.append("catalogue template identities must be unique")
        for index, template in enumerate(self.templates):
            problems.extend(template.validate(f"templates[{index}]"))
        return problems

    def matching(
        self,
        *,
        domains: tuple[str, ...] = (),
        tags: tuple[str, ...] = (),
    ) -> tuple[SolutionTemplate, ...]:
        """Return every exact metadata match in deterministic identity order."""
        domain_set = set(domains)
        tag_set = set(tags)
        return tuple(
            sorted(
                (
                    template
                    for template in self.templates
                    if domain_set.issubset(template.domains) and tag_set.issubset(template.tags)
                ),
                key=lambda template: (template.id, template.version),
            )
        )
