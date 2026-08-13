"""Strict, side-effect-free projections for external standards and runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE, canonical_json, sha256_digest

INTEGRATION_MODEL_VERSION = "0.1"


def _unique(values: tuple[str, ...], path: str, *, ids: bool = False) -> list[str]:
    problems: list[str] = []
    if len(values) != len(set(values)):
        problems.append(f"{path} must be unique")
    if any(not item.strip() for item in values):
        problems.append(f"{path} must not contain empty values")
    if ids and any(not ID_RE.fullmatch(item) for item in values):
        problems.append(f"{path} must contain namespaced identifiers")
    return problems


@dataclass(frozen=True)
class IntegrationAdapterProfile:
    id: str
    source_kind: str
    supported_versions: tuple[str, ...]
    output_kind: str
    description: str
    limitations: tuple[str, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "adapter_profile") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("source_kind", self.source_kind),
            ("output_kind", self.output_kind),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be namespaced")
        if not self.description.strip() or not self.supported_versions:
            problems.append(f"{path} requires a description and supported versions")
        problems.extend(_unique(self.supported_versions, f"{path}.supported_versions"))
        if not self.limitations:
            problems.append(f"{path}.limitations must preserve a claim boundary")
        problems.extend(_unique(self.limitations, f"{path}.limitations"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "integration_model_version": INTEGRATION_MODEL_VERSION,
            "id": self.id,
            "source_kind": self.source_kind,
            "supported_versions": list(self.supported_versions),
            "output_kind": self.output_kind,
            "description": self.description,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class ProjectedOperation:
    id: str
    source_ref: str
    kind: str
    label: str
    dependencies: tuple[str, ...] = ()
    input_type_ids: tuple[str, ...] = ()
    output_type_ids: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    metadata: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "projected_operation") -> list[str]:
        problems: list[str] = []
        for label, value in (("id", self.id), ("kind", self.kind)):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be namespaced")
        if not self.source_ref.strip() or not self.label.strip():
            problems.append(f"{path}.source_ref and label must not be empty")
        for label in (
            "dependencies",
            "input_type_ids",
            "output_type_ids",
            "effects",
            "permissions",
        ):
            problems.extend(_unique(getattr(self, label), f"{path}.{label}", ids=True))
        keys = [key for key, _ in self.metadata]
        if len(keys) != len(set(keys)) or any(
            not ID_RE.fullmatch(key) or "." not in key for key in keys
        ):
            problems.append(f"{path}.metadata keys must be unique and namespaced")
        try:
            canonical_json(dict(self.metadata))
        except (TypeError, ValueError):
            problems.append(f"{path}.metadata must be JSON serialisable")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_ref": self.source_ref,
            "kind": self.kind,
            "label": self.label,
            "dependencies": list(self.dependencies),
            "input_type_ids": list(self.input_type_ids),
            "output_type_ids": list(self.output_type_ids),
            "effects": list(self.effects),
            "permissions": list(self.permissions),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class IntegrationProjection:
    id: str
    adapter_id: str
    adapter_digest: str
    source_kind: str
    source_version: str
    source_digest: str
    operations: tuple[ProjectedOperation, ...]
    limitations: tuple[str, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "integration_projection") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("adapter_id", self.adapter_id),
            ("source_kind", self.source_kind),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be namespaced")
        for label, value in (
            ("adapter_digest", self.adapter_digest),
            ("source_digest", self.source_digest),
        ):
            if not DIGEST_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a sha256 digest")
        if not self.source_version.strip() or not self.operations:
            problems.append(f"{path} requires a source version and operations")
        operation_ids = [item.id for item in self.operations]
        if len(operation_ids) != len(set(operation_ids)):
            problems.append(f"{path}.operations ids must be unique")
        known = set(operation_ids)
        for index, operation in enumerate(self.operations):
            problems.extend(operation.validate(f"{path}.operations[{index}]"))
            unknown = sorted(set(operation.dependencies) - known)
            if unknown:
                problems.append(
                    f"{path}.operations[{index}] has unknown dependencies: "
                    + ", ".join(unknown)
                )
        if not self.limitations:
            problems.append(f"{path}.limitations must not be empty")
        problems.extend(_unique(self.limitations, f"{path}.limitations"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "integration_model_version": INTEGRATION_MODEL_VERSION,
            "id": self.id,
            "adapter_id": self.adapter_id,
            "adapter_digest": self.adapter_digest,
            "source_kind": self.source_kind,
            "source_version": self.source_version,
            "source_digest": self.source_digest,
            "operations": [item.to_dict() for item in self.operations],
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class OrchestratorTask:
    slot_id: str
    candidate_id: str
    node_id: str
    node_version: str
    implementation_digest: str
    runtime: str
    entrypoint: str
    parameters: tuple[tuple[str, Any], ...]
    fallback_candidate_ids: tuple[str, ...]
    dependencies: tuple[str, ...]
    effects: tuple[str, ...]
    permissions: tuple[str, ...]
    resources: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "candidate_id": self.candidate_id,
            "node_id": self.node_id,
            "node_version": self.node_version,
            "implementation_digest": self.implementation_digest,
            "runtime": self.runtime,
            "entrypoint": self.entrypoint,
            "parameters": dict(self.parameters),
            "fallback_candidate_ids": list(self.fallback_candidate_ids),
            "dependencies": list(self.dependencies),
            "effects": list(self.effects),
            "permissions": list(self.permissions),
            "resources": list(self.resources),
        }


@dataclass(frozen=True)
class OrchestratorPlanProjection:
    id: str
    adapter_id: str
    adapter_digest: str
    target: str
    target_version: str
    plan_digest: str
    program_digest: str
    registry_digest: str
    admitted_space_digest: str
    tasks: tuple[OrchestratorTask, ...]
    limitations: tuple[str, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "orchestrator_projection") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("adapter_id", self.adapter_id),
            ("target", self.target),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be namespaced")
        for label, value in (
            ("adapter_digest", self.adapter_digest),
            ("plan_digest", self.plan_digest),
            ("program_digest", self.program_digest),
            ("registry_digest", self.registry_digest),
            ("admitted_space_digest", self.admitted_space_digest),
        ):
            if not DIGEST_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a sha256 digest")
        if not self.target_version.strip() or not self.tasks:
            problems.append(f"{path} requires target version and tasks")
        task_ids = [item.slot_id for item in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            problems.append(f"{path}.tasks slot ids must be unique")
        known = set(task_ids)
        for index, task in enumerate(self.tasks):
            if not ID_RE.fullmatch(task.slot_id):
                problems.append(f"{path}.tasks[{index}].slot_id must be namespaced")
            unknown = sorted(set(task.dependencies) - known)
            if unknown:
                problems.append(
                    f"{path}.tasks[{index}] has unknown dependencies: "
                    + ", ".join(unknown)
                )
        if not self.limitations:
            problems.append(f"{path}.limitations must not be empty")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "integration_model_version": INTEGRATION_MODEL_VERSION,
            "id": self.id,
            "adapter_id": self.adapter_id,
            "adapter_digest": self.adapter_digest,
            "target": self.target,
            "target_version": self.target_version,
            "plan_digest": self.plan_digest,
            "program_digest": self.program_digest,
            "registry_digest": self.registry_digest,
            "admitted_space_digest": self.admitted_space_digest,
            "tasks": [item.to_dict() for item in self.tasks],
            "limitations": list(self.limitations),
        }


__all__ = [
    "INTEGRATION_MODEL_VERSION",
    "IntegrationAdapterProfile",
    "IntegrationProjection",
    "OrchestratorPlanProjection",
    "OrchestratorTask",
    "ProjectedOperation",
]
