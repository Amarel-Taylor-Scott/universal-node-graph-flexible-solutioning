"""Effort-aware, all-visible planning for common engineering obligations."""

from __future__ import annotations

from random import Random

from solutiongraph.universal.catalog import (
    DOMAIN_PACK_BY_ID,
    REFERENCE_ENGINEERING_QUESTIONS,
)
from solutiongraph.universal.model import (
    EngineeringDesignPlan,
    EngineeringPlanItem,
    UniversalDesignContext,
)

MODE_PERMISSION = {
    "deterministic": "",
    "human": "human.review",
    "llm": "model.invoke",
    "external": "network.read",
}
EFFORT_BUDGETS = {"E1": 10, "E3": 28, "E5": 55, "E7": 90, "E10": None}


def _effort(value: str | int) -> str:
    normalized = str(value).strip().upper()
    if not normalized.startswith("E"):
        normalized = "E" + normalized
    if normalized not in EFFORT_BUDGETS:
        raise ValueError("effort must be one of E1, E3, E5, E7, or E10")
    return normalized


def plan_engineering_design(
    context: UniversalDesignContext,
    *,
    domain_pack_id: str,
    effort: str | int = "E3",
    available_modes: tuple[str, ...] = ("deterministic",),
    granted_permissions: tuple[str, ...] = (),
    random_seed: int = 0,
) -> EngineeringDesignPlan:
    """Allocate design attention without hiding deferred or blocked questions."""

    problems = context.validate()
    if problems:
        raise ValueError("invalid universal design context: " + "; ".join(problems))
    if domain_pack_id not in DOMAIN_PACK_BY_ID:
        raise ValueError(f"unknown domain pack {domain_pack_id!r}")
    if domain_pack_id not in context.domain_pack_ids:
        raise ValueError("selected domain pack is not present in the design context")
    effort_id = _effort(effort)
    unsupported_modes = sorted(set(available_modes) - set(MODE_PERMISSION))
    if unsupported_modes:
        raise ValueError("unsupported response modes: " + ", ".join(unsupported_modes))

    pack = DOMAIN_PACK_BY_ID[domain_pack_id]
    applicable_ids = set(pack.required_obligation_ids) & set(context.obligation_ids)
    permissions = set(granted_permissions)
    random = Random(random_seed)
    ranked: list[tuple[float, object, str]] = []
    unavailable: dict[str, str] = {}
    for question in REFERENCE_ENGINEERING_QUESTIONS:
        if question.obligation_id not in applicable_ids:
            continue
        mode = ""
        for candidate_mode in question.response_modes:
            required = MODE_PERMISSION[candidate_mode]
            if candidate_mode in available_modes and (not required or required in permissions):
                mode = candidate_mode
                break
        if not mode:
            unavailable[question.id] = (
                "no declared response mode has its required authority"
            )
            continue
        # The jitter is a recorded exploration lane.  Priority remains dominant
        # and the same seed always yields the same allocation.
        score = question.priority * 100 - question.effort_cost * 5 + random.random()
        ranked.append((-score, question, mode))
    ranked.sort(key=lambda item: (item[0], item[1].id))

    budget = EFFORT_BUDGETS[effort_id]
    selected: dict[str, str] = {}
    spent = 0
    for _, question, mode in ranked:
        if budget is None or spent + question.effort_cost <= budget:
            selected[question.id] = mode
            spent += question.effort_cost

    items: list[EngineeringPlanItem] = []
    for question in REFERENCE_ENGINEERING_QUESTIONS:
        if question.obligation_id not in applicable_ids:
            status = "not-applicable"
            mode = ""
            reason = "the obligation is outside this domain pack"
        elif question.id in unavailable:
            status = "blocked"
            mode = ""
            reason = unavailable[question.id]
        elif question.id in selected:
            status = "selected"
            mode = selected[question.id]
            reason = f"selected within the {effort_id} cost budget"
        else:
            status = "deferred"
            mode = next(
                (
                    candidate_mode
                    for candidate_mode in question.response_modes
                    if candidate_mode in available_modes
                    and (
                        not MODE_PERMISSION[candidate_mode]
                        or MODE_PERMISSION[candidate_mode] in permissions
                    )
                ),
                "",
            )
            reason = f"applicable but outside the {effort_id} cost budget"
        items.append(
            EngineeringPlanItem(
                question_id=question.id,
                status=status,
                response_mode=mode,
                reason=reason,
                priority=question.priority,
                effort_cost=question.effort_cost,
            )
        )
    plan = EngineeringDesignPlan(
        context_digest=context.digest,
        domain_pack_id=domain_pack_id,
        effort=effort_id,
        random_seed=random_seed,
        items=tuple(items),
    )
    plan_problems = plan.validate()
    if plan_problems:
        raise ValueError("invalid engineering design plan: " + "; ".join(plan_problems))
    return plan


__all__ = ["EFFORT_BUDGETS", "MODE_PERMISSION", "plan_engineering_design"]
