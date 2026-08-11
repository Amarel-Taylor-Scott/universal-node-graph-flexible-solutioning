"""Portable task contracts and content-addressed solution packs.

The semantic program explains *how a task is decomposed*.  This module keeps
the definition of *what counts as solving the task* separate from that
program, from node implementations, and from experiment evidence.  That
separation is the trust boundary that allows many graph implementations to be
compared against one stable problem definition.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from solutiongraph.discovery import ArtifactReference, NodePackManifest
from solutiongraph.evidence import Objective
from solutiongraph.model import (
    DIGEST_RE,
    ID_RE,
    FrozenPlan,
    Port,
    ProgramGraph,
    Registry,
    canonical_json,
    sha256_digest,
)

TASK_MODEL_VERSION = "0.1"
SOLUTION_PACK_MODEL_VERSION = "0.1"
CASE_SPLITS = ("development", "validation", "holdout", "stress")
ORACLE_KINDS = (
    "exact",
    "property",
    "cross-implementation",
    "statistical",
    "human",
    "external-authority",
)
ORACLE_INDEPENDENCE = (
    "independent",
    "separate-implementation",
    "producer-self-check",
)
CONSTRAINT_OPERATORS = ("eq", "ne", "lt", "lte", "gt", "gte", "in", "not-in")
SOLUTION_PACK_READINESS = (
    "template",
    "executable-fixture",
    "credentialed-connector",
    "production-adapter",
)


def _duplicates(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if values.count(value) > 1}))


def _objective_dict(objective: Objective) -> dict[str, Any]:
    return {
        "metric": objective.metric,
        "direction": objective.direction,
        "weight": objective.weight,
        "hard_minimum": objective.hard_minimum,
        "hard_maximum": objective.hard_maximum,
    }


def _extension_problems(
    extensions: tuple[tuple[str, Any], ...], path: str
) -> list[str]:
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
class TaskOracle:
    """Identity and trust properties of the evaluator for a task contract."""

    id: str
    version: str
    kind: str
    evaluator_digest: str
    implementation_ref: str
    independence: str = "independent"
    candidate_readable: bool = False
    description: str = ""

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "oracle") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a lowercase namespaced identifier")
        if not self.version.strip():
            problems.append(f"{path}.version must not be empty")
        if self.kind not in ORACLE_KINDS:
            problems.append(f"{path}.kind must be one of {', '.join(ORACLE_KINDS)}")
        if not DIGEST_RE.fullmatch(self.evaluator_digest):
            problems.append(f"{path}.evaluator_digest must be a sha256 digest")
        if not self.implementation_ref.strip():
            problems.append(f"{path}.implementation_ref must not be empty")
        if self.independence not in ORACLE_INDEPENDENCE:
            problems.append(
                f"{path}.independence must be one of {', '.join(ORACLE_INDEPENDENCE)}"
            )
        if not isinstance(self.candidate_readable, bool):
            problems.append(f"{path}.candidate_readable must be boolean")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "kind": self.kind,
            "evaluator_digest": self.evaluator_digest,
            "implementation_ref": self.implementation_ref,
            "independence": self.independence,
            "candidate_readable": self.candidate_readable,
            "description": self.description,
        }


@dataclass(frozen=True)
class TaskConstraint:
    """One machine-readable hard gate that is not an optimization objective."""

    id: str
    target: str
    operator: str
    value: Any
    unit: str = ""
    description: str = ""

    def validate(self, path: str = "constraint") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a lowercase namespaced identifier")
        if not self.target.strip():
            problems.append(f"{path}.target must not be empty")
        if self.operator not in CONSTRAINT_OPERATORS:
            problems.append(
                f"{path}.operator must be one of {', '.join(CONSTRAINT_OPERATORS)}"
            )
        try:
            canonical_json(self.value)
        except (TypeError, ValueError):
            problems.append(f"{path}.value must be JSON serialisable")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target": self.target,
            "operator": self.operator,
            "value": self.value,
            "unit": self.unit,
            "description": self.description,
        }


@dataclass(frozen=True)
class TaskCaseSpec:
    """Portable identity for one immutable evaluator case.

    Input and expected-output bytes remain artifacts.  The task case points to
    them by digest so private holdouts do not have to be embedded in a pack.
    """

    id: str
    split: str
    input_digest: str
    fixture_ref: str
    expected_output_digest: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "task_case") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a lowercase namespaced identifier")
        if self.split not in CASE_SPLITS:
            problems.append(f"{path}.split must be one of {', '.join(CASE_SPLITS)}")
        if not DIGEST_RE.fullmatch(self.input_digest):
            problems.append(f"{path}.input_digest must be a sha256 digest")
        if self.expected_output_digest and not DIGEST_RE.fullmatch(
            self.expected_output_digest
        ):
            problems.append(f"{path}.expected_output_digest must be empty or a sha256 digest")
        if not self.fixture_ref.strip():
            problems.append(f"{path}.fixture_ref must not be empty")
        if len(self.tags) != len(set(self.tags)):
            problems.append(f"{path}.tags must be unique")
        if any(not ID_RE.fullmatch(tag) for tag in self.tags):
            problems.append(f"{path}.tags must contain namespaced identifiers")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_model_version": TASK_MODEL_VERSION,
            "id": self.id,
            "split": self.split,
            "input_digest": self.input_digest,
            "fixture_ref": self.fixture_ref,
            "expected_output_digest": self.expected_output_digest,
            "description": self.description,
            "tags": list(self.tags),
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class TaskContract:
    """Stable problem meaning against which multiple graph programs compete."""

    id: str
    version: str
    title: str
    intent: str
    inputs: tuple[Port, ...]
    outputs: tuple[Port, ...]
    success_contract: str
    oracle: TaskOracle
    objectives: tuple[Objective, ...]
    constraints: tuple[TaskConstraint, ...] = ()
    allowed_effects: tuple[str, ...] = ()
    granted_permissions: tuple[str, ...] = ()
    case_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    external_requirements: tuple[str, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "task_contract") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a lowercase namespaced identifier")
        if not self.version.strip():
            problems.append(f"{path}.version must not be empty")
        for label, value in (
            ("title", self.title),
            ("intent", self.intent),
            ("success_contract", self.success_contract),
        ):
            if not value.strip():
                problems.append(f"{path}.{label} must not be empty")
        for label, ports in (("inputs", self.inputs), ("outputs", self.outputs)):
            names = [port.name for port in ports]
            if len(names) != len(set(names)):
                problems.append(f"{path}.{label} names must be unique")
            for index, port in enumerate(ports):
                problems.extend(port.validate(f"{path}.{label}[{index}]"))
        problems.extend(self.oracle.validate(f"{path}.oracle"))
        if not self.objectives:
            problems.append(f"{path}.objectives must not be empty")
        objective_names = [objective.metric for objective in self.objectives]
        if len(objective_names) != len(set(objective_names)):
            problems.append(f"{path}.objectives must name unique metrics")
        for index, objective in enumerate(self.objectives):
            problems.extend(
                f"{path}.objectives[{index}]: {problem}"
                for problem in objective.validate()
            )
        constraint_ids = [constraint.id for constraint in self.constraints]
        if len(constraint_ids) != len(set(constraint_ids)):
            problems.append(f"{path}.constraints ids must be unique")
        for index, constraint in enumerate(self.constraints):
            problems.extend(constraint.validate(f"{path}.constraints[{index}]"))
        for label, values in (
            ("allowed_effects", self.allowed_effects),
            ("granted_permissions", self.granted_permissions),
            ("case_ids", self.case_ids),
            ("tags", self.tags),
        ):
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not ID_RE.fullmatch(value) for value in values):
                problems.append(f"{path}.{label} must contain namespaced identifiers")
        if any(not item.strip() for item in self.external_requirements):
            problems.append(f"{path}.external_requirements must not contain empty values")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def validate_program(self, program: ProgramGraph) -> list[str]:
        """Check that a semantic program is a faithful implementation candidate."""
        problems: list[str] = []
        program_inputs = {item.name: item for item in program.inputs}
        program_outputs = {item.name: item for item in program.outputs}
        contract_inputs = {item.name: item for item in self.inputs}
        contract_outputs = {item.name: item for item in self.outputs}
        if set(program_inputs) != set(contract_inputs):
            problems.append("program graph inputs do not exactly match the task contract")
        if set(program_outputs) != set(contract_outputs):
            problems.append("program graph outputs do not exactly match the task contract")
        for name in sorted(set(program_inputs) & set(contract_inputs)):
            if not program_inputs[name].value_type.is_assignable_to(
                contract_inputs[name].value_type
            ):
                problems.append(f"program input {name} type does not match the task contract")
        for name in sorted(set(program_outputs) & set(contract_outputs)):
            if not program_outputs[name].value_type.is_assignable_to(
                contract_outputs[name].value_type
            ):
                problems.append(f"program output {name} type does not match the task contract")
        if program.success_contract != self.success_contract:
            problems.append("program success_contract does not exactly match the task contract")
        undeclared_effects = sorted(set(program.allowed_effects) - set(self.allowed_effects))
        if undeclared_effects:
            problems.append(
                "program requests task-undeclared effects: " + ", ".join(undeclared_effects)
            )
        undeclared_permissions = sorted(
            set(program.granted_permissions) - set(self.granted_permissions)
        )
        if undeclared_permissions:
            problems.append(
                "program requests task-undeclared permissions: "
                + ", ".join(undeclared_permissions)
            )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_model_version": TASK_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "intent": self.intent,
            "inputs": [port.to_dict() for port in self.inputs],
            "outputs": [port.to_dict() for port in self.outputs],
            "success_contract": self.success_contract,
            "oracle": self.oracle.to_dict(),
            "objectives": [_objective_dict(item) for item in self.objectives],
            "constraints": [item.to_dict() for item in self.constraints],
            "allowed_effects": list(self.allowed_effects),
            "granted_permissions": list(self.granted_permissions),
            "case_ids": list(self.case_ids),
            "tags": list(self.tags),
            "external_requirements": list(self.external_requirements),
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class SolutionPackManifest:
    """Portable, content-addressed closure for a task and its solution assets."""

    id: str
    version: str
    title: str
    description: str
    readiness: str
    task_contract_digest: str
    program_digests: tuple[str, ...]
    registry_digests: tuple[str, ...]
    node_pack_digests: tuple[str, ...]
    task_case_digests: tuple[str, ...]
    evaluator_digests: tuple[str, ...]
    baseline_plan_digests: tuple[str, ...] = ()
    benchmark_suite_digests: tuple[str, ...] = ()
    artifacts: tuple[ArtifactReference, ...] = ()
    source: str = ""
    license: str = ""
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "solution_pack") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a lowercase namespaced identifier")
        if not self.version.strip():
            problems.append(f"{path}.version must not be empty")
        if not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.title and description must not be empty")
        if self.readiness not in SOLUTION_PACK_READINESS:
            problems.append(
                f"{path}.readiness must be one of {', '.join(SOLUTION_PACK_READINESS)}"
            )
        if not DIGEST_RE.fullmatch(self.task_contract_digest):
            problems.append(f"{path}.task_contract_digest must be a sha256 digest")
        digest_fields = (
            ("program_digests", self.program_digests),
            ("registry_digests", self.registry_digests),
            ("node_pack_digests", self.node_pack_digests),
            ("task_case_digests", self.task_case_digests),
            ("evaluator_digests", self.evaluator_digests),
            ("baseline_plan_digests", self.baseline_plan_digests),
            ("benchmark_suite_digests", self.benchmark_suite_digests),
        )
        for label, values in digest_fields:
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not DIGEST_RE.fullmatch(value) for value in values):
                problems.append(f"{path}.{label} must contain sha256 digests")
        if not self.program_digests:
            problems.append(f"{path}.program_digests must not be empty")
        if not self.registry_digests:
            problems.append(f"{path}.registry_digests must not be empty")
        if self.readiness != "template":
            if not self.task_case_digests:
                problems.append(f"{path}.task_case_digests are required when executable")
            if not self.evaluator_digests:
                problems.append(f"{path}.evaluator_digests are required when executable")
        artifact_names = [artifact.name for artifact in self.artifacts]
        if len(artifact_names) != len(set(artifact_names)):
            problems.append(f"{path}.artifacts names must be unique")
        for index, artifact in enumerate(self.artifacts):
            problems.extend(artifact.validate(f"{path}.artifacts[{index}]"))
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "solution_pack_model_version": SOLUTION_PACK_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "readiness": self.readiness,
            "task_contract_digest": self.task_contract_digest,
            "program_digests": list(self.program_digests),
            "registry_digests": list(self.registry_digests),
            "node_pack_digests": list(self.node_pack_digests),
            "task_case_digests": list(self.task_case_digests),
            "evaluator_digests": list(self.evaluator_digests),
            "baseline_plan_digests": list(self.baseline_plan_digests),
            "benchmark_suite_digests": list(self.benchmark_suite_digests),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "source": self.source,
            "license": self.license,
            "extensions": dict(self.extensions),
        }


def validate_solution_pack_closure(
    manifest: SolutionPackManifest,
    *,
    task_contract: TaskContract,
    programs: Iterable[ProgramGraph],
    registries: Iterable[Registry],
    node_packs: Iterable[NodePackManifest],
    task_cases: Iterable[TaskCaseSpec],
    evaluator_digests: Iterable[str],
    baseline_plans: Iterable[FrozenPlan] = (),
    benchmark_suite_digests: Iterable[str] = (),
) -> list[str]:
    """Require the manifest to describe the supplied closure exactly.

    No undeclared or missing graph, registry, case, evaluator, plan, or suite
    is tolerated.  This avoids the common failure where a manifest describes
    one experiment while execution silently uses a mutable workspace.
    """
    problems = manifest.validate()
    problems.extend(task_contract.validate())
    if manifest.task_contract_digest != task_contract.digest:
        problems.append("solution pack task_contract_digest does not match the contract")
    observed: Mapping[str, set[str]] = {
        "program_digests": {item.digest for item in programs},
        "registry_digests": {item.digest for item in registries},
        "node_pack_digests": {item.digest for item in node_packs},
        "task_case_digests": {item.digest for item in task_cases},
        "evaluator_digests": set(evaluator_digests),
        "baseline_plan_digests": {item.digest for item in baseline_plans},
        "benchmark_suite_digests": set(benchmark_suite_digests),
    }
    for label, actual in observed.items():
        declared = set(getattr(manifest, label))
        if actual != declared:
            missing = sorted(declared - actual)
            extra = sorted(actual - declared)
            if missing:
                problems.append(f"solution pack closure is missing {label}: {', '.join(missing)}")
            if extra:
                problems.append(f"solution pack closure has undeclared {label}: {', '.join(extra)}")
    case_ids = {item.id for item in task_cases}
    if case_ids != set(task_contract.case_ids):
        problems.append("solution pack task cases do not exactly match task_contract.case_ids")
    for index, program in enumerate(programs):
        problems.extend(
            f"programs[{index}]: {problem}"
            for problem in task_contract.validate_program(program)
        )
    return problems


__all__ = [
    "CASE_SPLITS",
    "CONSTRAINT_OPERATORS",
    "ORACLE_INDEPENDENCE",
    "ORACLE_KINDS",
    "SOLUTION_PACK_MODEL_VERSION",
    "SOLUTION_PACK_READINESS",
    "TASK_MODEL_VERSION",
    "SolutionPackManifest",
    "TaskCaseSpec",
    "TaskConstraint",
    "TaskContract",
    "TaskOracle",
    "validate_solution_pack_closure",
]
