"""Verification-plan rebinding node."""

from __future__ import annotations

from typing import Any

from solutiongraph.interrogation.model import DatasetProfile, QuestionPlan, SemanticFieldMap
from solutiongraph.interrogation.verification import rebind_plan


def rebind_plan_node(
    question_plan: dict[str, Any],
    shadow_profile: dict[str, Any],
    shadow_field_map: dict[str, Any],
) -> dict[str, Any]:
    result = rebind_plan(
        QuestionPlan.from_dict(question_plan),
        DatasetProfile.from_dict(shadow_profile),
        SemanticFieldMap.from_dict(shadow_field_map),
    )
    return result.to_dict()


__all__ = ["rebind_plan_node"]
