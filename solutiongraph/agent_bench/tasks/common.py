"""Shared task-pack records and deterministic oracle helpers."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from solutiongraph.agent_bench.model import AgentTaskSpec, task_case_spec
from solutiongraph.model import canonical_json, sha256_digest

JsonObject = dict[str, Any]
ReferenceSolver = Callable[[JsonObject], JsonObject]
CaseOracle = Callable[[JsonObject, JsonObject, JsonObject], "CaseEvaluation"]

BASE_CONTEXT_SOURCES = (
    "AGENT_PLAYBOOK.md",
    "TASK_AND_SOLUTION_PACK_PROTOCOL.md",
    "BENCHMARK_PROTOCOL.md",
    "INTELLIGENT_SOLUTIONING.md",
    ".agents/skills/solve-universal-dag/SKILL.md",
    ".agents/skills/benchmark-solution-graph/SKILL.md",
)


@dataclass(frozen=True)
class TaskCaseData:
    """Evaluator-owned payload; sealed expected values are never materialized."""

    id: str
    split: str
    payload: JsonObject
    expected: JsonObject
    candidate_readable: bool
    tags: tuple[str, ...] = ()

    @property
    def input_digest(self) -> str:
        return sha256_digest(self.payload)

    @property
    def expected_digest(self) -> str:
        return sha256_digest(self.expected)


@dataclass(frozen=True)
class CaseEvaluation:
    accepted: bool
    score: float
    metrics: tuple[tuple[str, float], ...] = ()
    problems: tuple[str, ...] = ()
    details: tuple[tuple[str, Any], ...] = ()

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not isfinite(self.score):
            problems.append("case evaluation score must be finite")
        names = tuple(name for name, _ in self.metrics)
        if len(names) != len(set(names)) or any(
            not name or not isfinite(value) for name, value in self.metrics
        ):
            problems.append("case evaluation metrics must be unique and finite")
        return problems


@dataclass(frozen=True)
class AgentTaskBundle:
    spec: AgentTaskSpec
    cases: tuple[TaskCaseData, ...]
    reference_solver: ReferenceSolver
    oracle: CaseOracle

    def validate(self) -> list[str]:
        problems = self.spec.validate()
        if tuple(case.id for case in self.cases) != tuple(
            case.id for case in self.spec.cases
        ):
            problems.append(f"{self.spec.id}: case order differs from the task spec")
        for data, spec in zip(self.cases, self.spec.cases, strict=True):
            if data.input_digest != spec.input_digest:
                problems.append(f"{data.id}: input digest differs from the task spec")
            if data.expected_digest != spec.expected_digest:
                problems.append(f"{data.id}: expected digest differs from the task spec")
            if data.candidate_readable is not spec.candidate_readable:
                problems.append(f"{data.id}: candidate visibility differs from the task spec")
            reference = self.reference_solver(data.payload)
            evaluation = self.oracle(data.payload, reference, data.expected)
            problems.extend(f"{data.id}: {problem}" for problem in evaluation.validate())
            if not evaluation.accepted:
                problems.append(f"{data.id}: reference solver does not satisfy its oracle")
        return problems

    def case(self, case_id: str) -> TaskCaseData:
        matches = tuple(case for case in self.cases if case.id == case_id)
        if not matches:
            raise ValueError(f"unknown case {case_id!r} for task {self.spec.id}")
        return matches[0]


def exact_oracle(
    _payload: JsonObject,
    candidate: JsonObject,
    expected: JsonObject,
) -> CaseEvaluation:
    accepted = canonical_json(candidate) == canonical_json(expected)
    return CaseEvaluation(
        accepted=accepted,
        score=float(accepted),
        metrics=(("exact_match", float(accepted)),),
        problems=() if accepted else ("candidate output does not exactly match the oracle",),
    )


def make_bundle(
    *,
    task_id: str,
    title: str,
    summary: str,
    instructions: str,
    input_contract: str,
    output_contract: str,
    success_contract: str,
    categories: tuple[str, ...],
    template_id: str,
    stages: tuple[str, ...],
    cases: tuple[TaskCaseData, ...],
    reference_solver: ReferenceSolver,
    oracle: CaseOracle = exact_oracle,
    acceptance_threshold: float = 1.0,
    score_direction: str = "maximize",
    score_metric: str = "oracle_score",
    allowed_imports: tuple[str, ...] = (),
    extra_context_sources: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> AgentTaskBundle:
    oracle_source = inspect.getsource(oracle)
    oracle_digest = sha256_digest(oracle_source)
    context_sources = (
        *BASE_CONTEXT_SOURCES,
        f"catalog/templates/{template_id}.json",
        *extra_context_sources,
    )
    spec = AgentTaskSpec(
        id=task_id,
        version="1.0.0",
        title=title,
        summary=summary,
        instructions=instructions,
        input_contract=input_contract,
        output_contract=output_contract,
        success_contract=success_contract,
        categories=categories,
        template_id=template_id,
        stages=stages,
        cases=tuple(
            task_case_spec(
                case.id,
                case.split,
                case.payload,
                case.expected,
                candidate_readable=case.candidate_readable,
                tags=case.tags,
            )
            for case in cases
        ),
        oracle_id=f"oracle.{task_id.removeprefix('agent-task.')}",
        oracle_digest=oracle_digest,
        score_metric=score_metric,
        score_direction=score_direction,
        acceptance_threshold=acceptance_threshold,
        context_sources=tuple(dict.fromkeys(context_sources)),
        allowed_imports=tuple(dict.fromkeys(allowed_imports)),
        limitations=(
            "Repository cases are transparent mechanism fixtures; sealed means absent from the candidate workspace, not protected by a separate host trust domain.",
            *limitations,
        ),
    )
    return AgentTaskBundle(spec, cases, reference_solver, oracle)


def mapping(value: Any, label: str = "value") -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


__all__ = [
    "AgentTaskBundle",
    "BASE_CONTEXT_SOURCES",
    "CaseEvaluation",
    "TaskCaseData",
    "exact_oracle",
    "make_bundle",
    "mapping",
]
