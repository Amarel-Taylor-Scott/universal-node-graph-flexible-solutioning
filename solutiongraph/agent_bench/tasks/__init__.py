"""Ten diverse, dependency-free agent benchmark task packs."""

from __future__ import annotations

from typing import Any

from solutiongraph.agent_bench.tasks.common import AgentTaskBundle
from solutiongraph.agent_bench.tasks.data import DATA_TASKS
from solutiongraph.agent_bench.tasks.ml import ML_TASKS
from solutiongraph.agent_bench.tasks.systems import SYSTEM_TASKS

REFERENCE_AGENT_TASKS: tuple[AgentTaskBundle, ...] = (
    *DATA_TASKS,
    *ML_TASKS,
    *SYSTEM_TASKS,
)


def get_agent_task(task_id: str) -> AgentTaskBundle:
    matches = tuple(bundle for bundle in REFERENCE_AGENT_TASKS if bundle.spec.id == task_id)
    if not matches:
        known = ", ".join(bundle.spec.id for bundle in REFERENCE_AGENT_TASKS)
        raise ValueError(f"unknown agent benchmark task {task_id!r}; known tasks: {known}")
    return matches[0]


def solve_reference(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run the evaluator-owned reference implementation for transport smoke tests."""
    return get_agent_task(task_id).reference_solver(payload)


def validate_reference_agent_tasks() -> list[str]:
    problems: list[str] = []
    ids = tuple(bundle.spec.id for bundle in REFERENCE_AGENT_TASKS)
    if len(ids) != 10:
        problems.append(f"reference agent task suite must contain exactly 10 tasks; observed {len(ids)}")
    if len(ids) != len(set(ids)):
        problems.append("reference agent task IDs must be unique")
    for bundle in REFERENCE_AGENT_TASKS:
        problems.extend(bundle.validate())
    return problems


__all__ = [
    "AgentTaskBundle",
    "REFERENCE_AGENT_TASKS",
    "get_agent_task",
    "solve_reference",
    "validate_reference_agent_tasks",
]
