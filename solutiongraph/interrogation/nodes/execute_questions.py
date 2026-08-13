"""Deterministic question execution node."""

from __future__ import annotations

from typing import Any

from solutiongraph.interrogation.execution import QuestionExecutor
from solutiongraph.interrogation.model import (
    DatasetProfile,
    QuestionPlan,
    SemanticFieldMap,
)
from solutiongraph.question_packs import QUESTION_BY_ID


def execute_questions_node(
    records: list[dict[str, Any]],
    profile: dict[str, Any],
    semantic_field_map: dict[str, Any],
    question_plan: dict[str, Any],
) -> dict[str, Any]:
    findings = QuestionExecutor().execute(
        records,
        DatasetProfile.from_dict(profile),
        SemanticFieldMap.from_dict(semantic_field_map),
        QuestionPlan.from_dict(question_plan),
        QUESTION_BY_ID,
    )
    return findings.to_dict()


__all__ = ["execute_questions_node"]
