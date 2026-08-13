"""Effort-aware human and LLM review planners with explicit authority."""

from __future__ import annotations

from typing import Any

from solutiongraph.design_atlas.model import DesignContext
from solutiongraph.design_atlas.planning import DesignPlanner


def _plan(
    context: dict[str, Any],
    *,
    response_mode: str,
    permission: str,
    effort_level: str,
    random_seed: int,
) -> dict[str, Any]:
    parsed = DesignContext.from_dict(context)
    plan = DesignPlanner().plan(
        parsed,
        effort=effort_level,
        available_modes=(response_mode,),
        granted_permissions=(permission,),
        random_seed=random_seed,
    )
    return plan.to_dict()


def plan_human_review_node(
    context: dict[str, Any],
    effort_level: str = "E3",
    random_seed: int = 0,
) -> dict[str, Any]:
    """Allocate the visible worklist to an explicitly authorized human reviewer."""
    return _plan(
        context,
        response_mode="human",
        permission="human.review",
        effort_level=effort_level,
        random_seed=random_seed,
    )


def plan_llm_review_node(
    context: dict[str, Any],
    effort_level: str = "E3",
    random_seed: int = 0,
) -> dict[str, Any]:
    """Allocate the same contract to an explicitly authorized model responder."""
    return _plan(
        context,
        response_mode="llm",
        permission="model.invoke",
        effort_level=effort_level,
        random_seed=random_seed,
    )


__all__ = ["plan_human_review_node", "plan_llm_review_node"]
