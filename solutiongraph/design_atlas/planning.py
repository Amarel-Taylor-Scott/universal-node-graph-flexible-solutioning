"""Effort-aware, all-visible planning and evidence-aware decision resolution."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from random import Random

from solutiongraph.design_atlas.archetypes import get_archetype
from solutiongraph.design_atlas.model import (
    CapabilityEvidence,
    DecisionAnswer,
    DecisionRecord,
    DesignContext,
    DesignDossier,
    DesignEffort,
    DesignPack,
    DesignPlan,
    DesignPlanItem,
    MaturityAssessment,
)
from solutiongraph.design_atlas.packs import (
    DESIGN_QUESTION_BY_ID,
    REFERENCE_DESIGN_PACKS,
)
from solutiongraph.model import sha256_digest

MODE_PERMISSION = {
    "deterministic": "",
    "llm": "model.invoke",
    "human": "human.review",
    "external": "network.read",
}
LEVEL_NAMES = {
    "C0": "Absent",
    "C1": "Cataloged",
    "C2": "Declared",
    "C3": "Runnable",
    "C4": "Composable",
    "C5": "Search-integrated",
    "C6": "Benchmark-validated",
    "C7": "Operational",
}


def effort_policy(level: int | str) -> DesignEffort:
    if isinstance(level, str):
        normalized = level.strip().upper().removeprefix("E")
        if not normalized.isdigit():
            raise ValueError("effort must be one of E1, E3, E5, E7, or E10")
        value = int(normalized)
    else:
        value = level
    policies = {
        1: DesignEffort("effort.e1", 12, 3, 0.08, "Task contract and highest-risk blockers."),
        3: DesignEffort("effort.e3", 28, 4, 0.12, "Core data and evaluation design."),
        5: DesignEffort("effort.e5", 56, 6, 0.16, "Broad lifecycle and specialized analysis."),
        7: DesignEffort("effort.e7", 84, 8, 0.20, "Deep risk, operations, and alternative design."),
        10: DesignEffort("effort.e10", None, 10, 0.25, "Every applicable question; no hidden cap."),
    }
    try:
        return policies[value]
    except KeyError as exc:
        raise ValueError("effort must be one of E1, E3, E5, E7, or E10") from exc


def _applicable(
    pack_id: str,
    trigger_any: tuple[str, ...],
    trigger_all: tuple[str, ...],
    exclude_when: tuple[str, ...],
    tags: frozenset[str],
    required: frozenset[str],
    optional: frozenset[str],
) -> tuple[bool, str]:
    if tags.intersection(exclude_when):
        return False, "an explicit exclusion trigger matched"
    if trigger_all and not set(trigger_all).issubset(tags):
        return False, "not every required applicability trigger matched"
    if trigger_any and not tags.intersection(trigger_any):
        return False, "no applicability trigger matched"
    if pack_id in required:
        return True, "required by the task archetype"
    if pack_id in optional:
        return True, "optional task-archetype pack matched the supplied context"
    if trigger_any or trigger_all:
        return True, "question trigger matched the supplied context"
    return False, "pack is outside the selected task archetype"


class DesignPlanner:
    """Compile a complete visible plan while allocating only eligible questions."""

    def plan(
        self,
        context: DesignContext,
        *,
        effort: int | str = "E3",
        packs: Sequence[DesignPack] = REFERENCE_DESIGN_PACKS,
        available_modes: Iterable[str] = ("human",),
        granted_permissions: Iterable[str] = ("human.review",),
        random_seed: int = 0,
    ) -> DesignPlan:
        problems = context.validate()
        if problems:
            raise ValueError("invalid design context: " + "; ".join(problems))
        archetype = get_archetype(context.task_type)
        policy = effort_policy(effort)
        modes = frozenset(available_modes)
        unknown_modes = modes.difference(MODE_PERMISSION)
        if unknown_modes:
            raise ValueError(f"unknown design response modes: {sorted(unknown_modes)}")
        permissions = frozenset(granted_permissions)
        required = frozenset(archetype.required_pack_ids)
        optional = frozenset(archetype.optional_pack_ids)
        context_tags = frozenset((*context.tags, *archetype.tags))

        facts: dict[str, tuple[str, float, str, tuple[str, ...]]] = {}
        selectable: list[tuple[float, str]] = []
        for pack in packs:
            for question in pack.questions:
                applies, applicability_reason = _applicable(
                    pack.id,
                    question.trigger_any,
                    question.trigger_all,
                    question.exclude_when,
                    context_tags,
                    required,
                    optional,
                )
                if not applies:
                    facts[question.id] = (
                        "not-applicable", 0.0, "", (applicability_reason,)
                    )
                    continue
                preferred = tuple(
                    mode
                    for mode in ("deterministic", "llm", "human", "external")
                    if mode in question.response_modes and mode in modes
                )
                authorized = tuple(
                    mode
                    for mode in preferred
                    if not MODE_PERMISSION[mode] or MODE_PERMISSION[mode] in permissions
                )
                base_priority = (
                    0.58 * question.risk_weight
                    + 0.18 * (1.0 - ((question.cost_tier - 1) / 9.0))
                    + (0.18 if pack.id in required else 0.08)
                    + (0.06 if context.risk_tier in {"risk.high", "risk.critical"} else 0.0)
                )
                priority = round(min(1.0, base_priority), 6)
                if not preferred:
                    facts[question.id] = (
                        "blocked",
                        priority,
                        "",
                        ("no declared response mode is available", applicability_reason),
                    )
                    continue
                if not authorized:
                    required_permissions = sorted(
                        {MODE_PERMISSION[mode] for mode in preferred if MODE_PERMISSION[mode]}
                    )
                    facts[question.id] = (
                        "blocked",
                        priority,
                        "",
                        (
                            "required permission was not granted: "
                            + ", ".join(required_permissions),
                            applicability_reason,
                        ),
                    )
                    continue
                mode = authorized[0]
                if question.cost_tier > policy.max_cost_tier:
                    facts[question.id] = (
                        "deferred",
                        priority,
                        mode,
                        (
                            f"cost tier {question.cost_tier} exceeds {policy.id}",
                            applicability_reason,
                        ),
                    )
                    continue
                facts[question.id] = (
                    "deferred",
                    priority,
                    mode,
                    ("eligible but not yet allocated", applicability_reason),
                )
                selectable.append((priority, question.id))

        selectable.sort(key=lambda item: (-item[0], item[1]))
        if policy.max_questions is None or len(selectable) <= policy.max_questions:
            selected = {question_id for _, question_id in selectable}
        else:
            limit = policy.max_questions
            explore_count = min(limit, max(1, round(limit * policy.exploration_fraction)))
            exploit_count = limit - explore_count
            selected = {question_id for _, question_id in selectable[:exploit_count]}
            pool = [question_id for _, question_id in selectable[exploit_count:]]
            selected.update(Random(random_seed).sample(pool, k=min(explore_count, len(pool))))

        items: list[DesignPlanItem] = []
        for pack in packs:
            for question in pack.questions:
                status, priority, mode, reasons = facts[question.id]
                if question.id in selected:
                    status = "selected"
                    reasons = ("allocated by the explicit effort policy", reasons[-1])
                items.append(
                    DesignPlanItem(
                        question_id=question.id,
                        pack_id=pack.id,
                        status=status,
                        priority=priority,
                        response_mode=mode,
                        reasons=reasons,
                    )
                )
        identity = {
            "context": context.digest,
            "archetype": archetype.id,
            "effort": policy.to_dict(),
            "seed": random_seed,
            "items": [item.to_dict() for item in items],
        }
        return DesignPlan(
            id=f"design-plan.{sha256_digest(identity).removeprefix('sha256:')[:16]}",
            context_digest=context.digest,
            archetype_id=archetype.id,
            effort=policy,
            items=tuple(items),
            random_seed=random_seed,
        )

    def resolve(
        self,
        plan: DesignPlan,
        answers: Sequence[DecisionAnswer],
    ) -> DesignDossier:
        answer_by_question: dict[str, DecisionAnswer] = {}
        for index, answer in enumerate(answers):
            problems = answer.validate(f"answers[{index}]")
            if problems:
                raise ValueError("invalid design answer: " + "; ".join(problems))
            if answer.question_id in answer_by_question:
                raise ValueError(f"duplicate answer for {answer.question_id}")
            answer_by_question[answer.question_id] = answer

        visible = {item.question_id: item for item in plan.items}
        unknown = set(answer_by_question).difference(visible)
        if unknown:
            raise ValueError(f"answers reference questions outside the plan: {sorted(unknown)}")

        decisions: list[DecisionRecord] = []
        unanswered: list[str] = []
        blocked: list[str] = []
        for item in plan.items:
            if item.status == "blocked":
                blocked.append(item.question_id)
            if item.status != "selected":
                continue
            answer = answer_by_question.get(item.question_id)
            if answer is None:
                unanswered.append(item.question_id)
                continue
            question = DESIGN_QUESTION_BY_ID[item.question_id]
            if answer.abstained:
                decisions.append(
                    DecisionRecord(
                        question_id=question.id,
                        choice_id="decision.abstain",
                        status="abstained",
                        evidence_refs=answer.evidence_refs,
                        rationale=answer.rationale,
                        assumptions=answer.assumptions,
                        action_ids=("action.resolve-blocker",),
                        experiment="",
                        stop_conditions=question.stop_conditions,
                    )
                )
                continue
            choice_by_id = {choice.id: choice for choice in question.choices}
            if answer.choice_id not in choice_by_id:
                raise ValueError(
                    f"{answer.choice_id!r} is not a branch of {question.id}"
                )
            choice = choice_by_id[answer.choice_id]
            status = "accepted" if answer.evidence_refs else "provisional"
            decisions.append(
                DecisionRecord(
                    question_id=question.id,
                    choice_id=choice.id,
                    status=status,
                    evidence_refs=answer.evidence_refs,
                    rationale=answer.rationale,
                    assumptions=answer.assumptions,
                    action_ids=choice.action_ids,
                    experiment=(
                        question.experiment_template if choice.id.endswith(".evaluate") else ""
                    ),
                    stop_conditions=question.stop_conditions,
                )
            )
        identity = {
            "plan": plan.digest,
            "decisions": [decision.to_dict() for decision in decisions],
            "unanswered": unanswered,
            "blocked": blocked,
        }
        return DesignDossier(
            id=f"design-dossier.{sha256_digest(identity).removeprefix('sha256:')[:16]}",
            plan_digest=plan.digest,
            decisions=tuple(decisions),
            unanswered_question_ids=tuple(unanswered),
            blocked_question_ids=tuple(blocked),
        )


def assess_maturity(evidence: CapabilityEvidence) -> MaturityAssessment:
    problems = evidence.validate()
    if problems:
        raise ValueError("invalid capability evidence: " + "; ".join(problems))
    gates = (
        ("C1", evidence.cataloged),
        ("C2", bool(evidence.declaration_digest)),
        ("C3", evidence.valid_smoke_tests > 0 and evidence.invalid_smoke_tests > 0),
        ("C4", evidence.compatibility_tests > 0 and evidence.leakage_tests > 0),
        ("C5", evidence.search_registered and evidence.search_tests > 0),
        ("C6", evidence.benchmark_receipts >= 3 and evidence.benchmark_seeds >= 2),
        (
            "C7",
            all(
                (
                    evidence.monitoring_evidence,
                    evidence.security_evidence,
                    evidence.privacy_evidence,
                    evidence.rollback_evidence,
                    evidence.slo_evidence,
                )
            ),
        ),
    )
    level = "C0"
    satisfied: list[str] = []
    for gate, passed in gates:
        if not passed:
            break
        level = gate
        satisfied.append(gate)
    next_index = int(level[1:]) + 1
    next_gate = f"C{next_index}" if next_index <= 7 else "complete"
    component_levels = (
        ("declaration", "C2" if gates[1][1] else "C1" if gates[0][1] else "C0"),
        ("execution", "C3" if gates[2][1] else "C0"),
        ("composition", "C4" if gates[3][1] else "C0"),
        ("search", "C5" if gates[4][1] else "C0"),
        ("benchmark", "C6" if gates[5][1] else "C0"),
        ("operations", "C7" if gates[6][1] else "C0"),
    )
    return MaturityAssessment(
        capability_id=evidence.capability_id,
        overall_level=level,
        level_name=LEVEL_NAMES[level],
        component_levels=component_levels,
        satisfied_gates=tuple(satisfied),
        next_gate=next_gate,
        evidence_digest=sha256_digest(evidence.to_dict()),
    )


__all__ = ["DesignPlanner", "assess_maturity", "effort_policy"]
