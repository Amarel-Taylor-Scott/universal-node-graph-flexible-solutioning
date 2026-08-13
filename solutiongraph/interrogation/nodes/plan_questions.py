"""Effort-aware visible question planning node."""

from __future__ import annotations

from typing import Any

from solutiongraph.interrogation.execution import STANDARD_CHECK_REGISTRY
from solutiongraph.interrogation.model import DatasetProfile, SemanticFieldMap
from solutiongraph.interrogation.planning import QuestionPlanner, effort_budget
from solutiongraph.question_packs import REFERENCE_QUESTION_PACKS


def plan_questions_node(
    profile: dict[str, Any],
    semantic_field_map: dict[str, Any],
    effort_level: str = "E3",
    planning_strategy: str = "risk-first",
    random_seed: int = 0,
) -> dict[str, Any]:
    plan = QuestionPlanner().plan(
        DatasetProfile.from_dict(profile),
        SemanticFieldMap.from_dict(semantic_field_map),
        REFERENCE_QUESTION_PACKS,
        budget=effort_budget(effort_level, random_seed=random_seed),
        available_capabilities=STANDARD_CHECK_REGISTRY.capabilities,
        strategy=planning_strategy,
    )
    return plan.to_dict()


__all__ = ["plan_questions_node"]
