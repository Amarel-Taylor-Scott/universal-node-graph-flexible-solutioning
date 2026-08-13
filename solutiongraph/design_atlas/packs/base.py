"""Concise authoring helpers for modular design-question packs."""

from __future__ import annotations

import re

from solutiongraph.design_atlas.model import (
    DecisionChoice,
    DesignPack,
    DesignQuestion,
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def branch(
    pack_key: str,
    question_key: str,
    key: str,
    label: str,
    consequence: str,
    *actions: str,
    techniques: tuple[str, ...] = (),
) -> DecisionChoice:
    action_ids = tuple(
        action if action.startswith("action.") else f"action.{_slug(action)}"
        for action in actions
    )
    return DecisionChoice(
        id=f"decision.{pack_key}.{question_key}.{key}",
        label=label,
        consequence=consequence,
        action_ids=action_ids,
        technique_tags=techniques,
    )


def q(
    pack_key: str,
    key: str,
    title: str,
    prompt: str,
    rationale: str,
    choices: tuple[DecisionChoice, ...],
    *,
    modes: tuple[str, ...] = ("llm", "human"),
    cost: int = 3,
    risk: float = 0.5,
    evidence: tuple[str, ...] = ("evidence.task-contract",),
    trigger_any: tuple[str, ...] = (),
    trigger_all: tuple[str, ...] = (),
    exclude_when: tuple[str, ...] = (),
    experiment: str = (
        "Compare feasible branches against the declared control on identical cases, "
        "seeds, resource accounting, and an independent acceptance oracle."
    ),
    stop: tuple[str, ...] = (
        "Stop when the acceptance gate fails.",
        "Stop when the declared evidence or resource budget is exhausted.",
    ),
    references: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
) -> DesignQuestion:
    return DesignQuestion(
        id=f"design-question.{pack_key}.{key}",
        version="1.0.0",
        pack_id=f"design-pack.{pack_key}",
        title=title,
        prompt=prompt,
        rationale=rationale,
        response_modes=modes,
        cost_tier=cost,
        risk_weight=risk,
        required_evidence=evidence,
        choices=choices,
        trigger_any=trigger_any,
        trigger_all=trigger_all,
        exclude_when=exclude_when,
        experiment_template=experiment,
        stop_conditions=stop,
        reference_ids=references,
        tags=(f"design-domain.{pack_key}", *tags),
    )


def standard_choices(
    pack_key: str,
    question_key: str,
    evaluate_label: str,
    baseline_label: str,
    defer_label: str = "Defer with an explicit blocker",
) -> tuple[DecisionChoice, ...]:
    return (
        branch(
            pack_key,
            question_key,
            "evaluate",
            evaluate_label,
            "Evaluate the alternatives and retain the comparative evidence.",
            f"evaluate-{pack_key}-{question_key}",
        ),
        branch(
            pack_key,
            question_key,
            "baseline",
            baseline_label,
            "Freeze the simple baseline and record why it is sufficient for this scope.",
            f"freeze-{pack_key}-{question_key}-baseline",
        ),
        branch(
            pack_key,
            question_key,
            "defer",
            defer_label,
            "Do not guess; record the missing owner, evidence, or authority as a blocker.",
            f"block-{pack_key}-{question_key}",
        ),
    )


def make_pack(
    key: str,
    title: str,
    description: str,
    stage: str,
    questions: tuple[DesignQuestion, ...],
    references: tuple[str, ...] = (),
) -> DesignPack:
    return DesignPack(
        id=f"design-pack.{key}",
        version="1.0.0",
        title=title,
        description=description,
        stage=stage,
        questions=questions,
        reference_ids=references,
    )


__all__ = ["branch", "make_pack", "q", "standard_choices"]
