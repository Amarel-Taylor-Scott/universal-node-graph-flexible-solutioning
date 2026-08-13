"""Resolve a plan-bound answer set into an evidence-aware design dossier."""

from __future__ import annotations

from typing import Any

from solutiongraph.design_atlas.model import DecisionAnswer, DesignPlan
from solutiongraph.design_atlas.planning import DesignPlanner


def resolve_answers_node(
    design_plan: dict[str, Any],
    answer_set: dict[str, Any],
    resolution_policy: str = "allow-provisional",
) -> dict[str, Any]:
    """Fail closed on stale answers and, optionally, every evidence gap."""
    if resolution_policy not in {"allow-provisional", "evidence-required"}:
        raise ValueError("resolution_policy is unsupported")
    plan = DesignPlan.from_dict(design_plan)
    if not isinstance(answer_set, dict) or set(answer_set) != {"plan_digest", "answers"}:
        raise ValueError("answer_set must contain exactly plan_digest and answers")
    if answer_set["plan_digest"] != plan.digest:
        raise ValueError("answer_set.plan_digest does not match the supplied plan")
    raw_answers = answer_set["answers"]
    if not isinstance(raw_answers, list) or any(not isinstance(item, dict) for item in raw_answers):
        raise ValueError("answer_set.answers must be an array of answer objects")
    dossier = DesignPlanner().resolve(
        plan,
        tuple(DecisionAnswer.from_dict(item) for item in raw_answers),
    )
    if resolution_policy == "evidence-required":
        unresolved = [
            decision.question_id
            for decision in dossier.decisions
            if decision.status != "accepted"
        ]
        if dossier.unanswered_question_ids or dossier.blocked_question_ids or unresolved:
            raise ValueError(
                "evidence-required resolution rejected unresolved work: "
                f"unanswered={len(dossier.unanswered_question_ids)}, "
                f"blocked={len(dossier.blocked_question_ids)}, "
                f"non_accepted={len(unresolved)}"
            )
    return dossier.to_dict()


__all__ = ["resolve_answers_node"]
