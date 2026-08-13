"""Adaptive, visibility-preserving question-plan compilation."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from random import Random

from solutiongraph.interrogation.learning import (
    EMPTY_QUESTION_UTILITY_MEMORY,
    QuestionUtilityProvider,
)
from solutiongraph.interrogation.model import (
    DatasetProfile,
    InterrogationBudget,
    QuestionDefinition,
    QuestionPack,
    QuestionPlan,
    QuestionPlanItem,
    SemanticFieldMap,
)

SEVERITY_WEIGHT = {
    "info": 0.05,
    "low": 0.20,
    "medium": 0.45,
    "high": 0.75,
    "critical": 1.00,
}


def effort_budget(
    level: int | str,
    *,
    granted_permissions: Iterable[str] = (),
    random_seed: int = 0,
) -> InterrogationBudget:
    """Return the standard progressive effort policy.

    All questions remain visible under every level.  The budget changes only
    which eligible questions are selected for execution.
    """
    if isinstance(level, str):
        normalized = level.strip().upper().removeprefix("E")
        if not normalized.isdigit():
            raise ValueError("effort must be one of E1, E3, E5, E7, or E10")
        effort = int(normalized)
    else:
        effort = level
    settings = {
        1: (("deterministic",), 1, 12, False, 0.05),
        3: (("deterministic",), 3, 30, False, 0.10),
        5: (("deterministic", "external"), 5, 60, False, 0.12),
        7: (("deterministic", "external", "llm"), 7, 100, False, 0.15),
        10: (("deterministic", "external", "llm", "human"), 10, None, True, 0.20),
    }
    if effort not in settings:
        raise ValueError("effort must be one of E1, E3, E5, E7, or E10")
    modes, max_tier, max_questions, exhaustive, exploration = settings[effort]
    result = InterrogationBudget(
        id=f"effort.interrogation-{effort}",
        effort_level=effort,
        allowed_modes=modes,
        granted_permissions=tuple(dict.fromkeys(granted_permissions)),
        max_cost_tier=max_tier,
        max_questions=max_questions,
        exhaustive=exhaustive,
        exploration_fraction=exploration,
        random_seed=random_seed,
    )
    problems = result.validate()
    if problems:
        raise ValueError("invalid effort budget: " + "; ".join(problems))
    return result


def _concept_fields(
    question: QuestionDefinition,
    profile: DatasetProfile,
    field_map: SemanticFieldMap,
) -> tuple[str, ...]:
    if "concept.dataset.recordset" in question.concept_ids:
        return profile.column_names
    return field_map.fields_for(question.concept_ids)


def _precondition_available(
    precondition: str,
    profile: DatasetProfile,
    field_map: SemanticFieldMap,
) -> bool:
    concepts = field_map.concepts
    mapping = {
        "precondition.records-available": profile.row_count > 0,
        "precondition.mapped-fields-available": bool(field_map.matches),
        "precondition.identifier-available": bool(
            concepts
            & {
                "concept.dataset.record-id",
                "concept.organization.identifier",
                "concept.product.identifier",
                "concept.transaction.id",
                "concept.document.identifier",
            }
        ),
        "precondition.source-available": "concept.dataset.source" in concepts,
        "precondition.country-context-available": "concept.postal.country" in concepts,
        "precondition.address-available": bool(
            concepts
            & {
                "concept.postal.address",
                "concept.postal.street",
                "concept.postal.city",
                "concept.postal.code",
            }
        ),
        "precondition.postal-code-available": "concept.postal.code" in concepts,
        "precondition.domain-available": "concept.organization.domain" in concepts,
        "precondition.event-time-available": bool(
            concepts
            & {
                "concept.time.instant",
                "concept.time.date",
                "concept.time.start",
                "concept.time.end",
                "concept.organization.status-date",
            }
        ),
        "precondition.start-end-available": {
            "concept.time.start",
            "concept.time.end",
        } <= concepts,
        "precondition.reference-clock-available": False,
        "precondition.coordinates-available": {
            "concept.geography.latitude",
            "concept.geography.longitude",
        } <= concepts,
        "precondition.target-available": "concept.ml.target" in concepts,
        "precondition.split-available": "concept.ml.split" in concepts,
    }
    return mapping.get(precondition, False)


def _profile_risk(
    question: QuestionDefinition,
    fields: tuple[str, ...],
    profile: DatasetProfile,
) -> float:
    relevant = [profile.field_map[field] for field in fields if field in profile.field_map]
    if not relevant:
        return 0.0
    capabilities = {check.capability for check in question.checks}
    risk = 0.0
    if "quality.placeholder-check" in capabilities:
        risk += min(0.3, sum(item.placeholder_count for item in relevant) / max(1, profile.row_count))
    if "quality.unicode-control-check" in capabilities:
        risk += min(
            0.25,
            sum(item.control_character_count + item.non_nfc_count for item in relevant)
            / max(1, profile.row_count),
        )
    if "quality.whitespace-check" in capabilities:
        risk += min(
            0.2,
            sum(item.leading_or_trailing_space_count for item in relevant)
            / max(1, profile.row_count),
        )
    if "quality.duplicate-record-check" in capabilities and profile.duplicate_row_count:
        risk += min(0.3, profile.duplicate_row_count / max(1, profile.row_count))
    if any(item.missing_fraction > 0.25 for item in relevant):
        risk += 0.08
    return min(risk, 0.45)


class QuestionPlanner:
    """Compile a complete visible plan and select only within explicit budgets."""

    id = "planner.semantic-interrogation"
    version = "1.0.0"

    def plan(
        self,
        profile: DatasetProfile,
        field_map: SemanticFieldMap,
        packs: Sequence[QuestionPack],
        *,
        budget: InterrogationBudget,
        available_capabilities: Iterable[str],
        history: QuestionUtilityProvider = EMPTY_QUESTION_UTILITY_MEMORY,
        context_tags: tuple[str, ...] = (),
        strategy: str = "risk-first",
    ) -> QuestionPlan:
        if strategy not in ("risk-first", "coverage-first"):
            raise ValueError("strategy must be risk-first or coverage-first")
        if profile.dataset_digest != field_map.dataset_digest:
            raise ValueError("profile and semantic map identify different datasets")
        for item, label in ((profile, "profile"), (field_map, "field map"), (budget, "budget")):
            problems = item.validate()
            if problems:
                raise ValueError(f"invalid {label}: " + "; ".join(problems))
        available = set(available_capabilities)
        granted = set(budget.granted_permissions)
        rng = Random(budget.random_seed)
        raw_items: list[QuestionPlanItem] = []
        for question_pack in packs:
            for question in question_pack.questions:
                fields = _concept_fields(question, profile, field_map)
                dataset_question = "concept.dataset.recordset" in question.concept_ids
                if not fields and not dataset_question:
                    raw_items.append(
                        QuestionPlanItem(
                            question.id,
                            question.digest,
                            question_pack.id,
                            "not-applicable",
                            (),
                            0.0,
                            reasons=("no mapped field satisfies the question concepts",),
                        )
                    )
                    continue
                missing_preconditions = tuple(
                    item
                    for item in question.preconditions
                    if not _precondition_available(item, profile, field_map)
                )
                if missing_preconditions:
                    raw_items.append(
                        QuestionPlanItem(
                            question.id,
                            question.digest,
                            question_pack.id,
                            "blocked",
                            fields,
                            SEVERITY_WEIGHT[question.severity],
                            reasons=tuple(
                                f"unsatisfied {precondition}" for precondition in missing_preconditions
                            ),
                        )
                    )
                    continue
                eligible_check = None
                rejection_reasons: list[str] = []
                for check in question.checks:
                    if check.mode not in budget.allowed_modes:
                        rejection_reasons.append(f"mode {check.mode} is outside effort policy")
                        continue
                    if check.cost_tier > budget.max_cost_tier:
                        rejection_reasons.append(
                            f"cost tier {check.cost_tier} exceeds {budget.max_cost_tier}"
                        )
                        continue
                    if check.permission and check.permission not in granted:
                        rejection_reasons.append(f"permission {check.permission} is not granted")
                        continue
                    if check.capability not in available:
                        rejection_reasons.append(f"capability {check.capability} is unavailable")
                        continue
                    eligible_check = check
                    break
                estimate = history.estimate(question.id, context_tags)
                confidence_values = [
                    match.confidence
                    for match in field_map.matches
                    if match.field_name in fields
                ]
                mapping_confidence = (
                    sum(confidence_values) / len(confidence_values)
                    if confidence_values
                    else 1.0
                )
                priority = SEVERITY_WEIGHT[question.severity]
                priority += _profile_risk(question, fields, profile)
                priority += 0.12 * (mapping_confidence - 0.5)
                priority += 0.18 * (estimate.posterior_mean - 0.5)
                if strategy == "coverage-first":
                    priority += 0.08 / max(1, len(fields))
                priority += rng.random() * 0.001
                if eligible_check is None:
                    raw_items.append(
                        QuestionPlanItem(
                            question.id,
                            question.digest,
                            question_pack.id,
                            "blocked",
                            fields,
                            priority,
                            reasons=tuple(dict.fromkeys(rejection_reasons)),
                            historical_observations=estimate.observation_count,
                            historical_utility=estimate.posterior_mean,
                        )
                    )
                    continue
                raw_items.append(
                    QuestionPlanItem(
                        question.id,
                        question.digest,
                        question_pack.id,
                        "selected",
                        fields,
                        priority,
                        selected_capability=eligible_check.capability,
                        selected_mode=eligible_check.mode,
                        reasons=(f"eligible under {budget.id}",),
                        historical_observations=estimate.observation_count,
                        historical_utility=estimate.posterior_mean,
                    )
                )
        eligible = [item for item in raw_items if item.status == "selected"]
        selected_ids: set[str]
        if budget.exhaustive or budget.max_questions is None or len(eligible) <= budget.max_questions:
            selected_ids = {item.question_id for item in eligible}
        else:
            limit = budget.max_questions
            exploration_count = min(limit, round(limit * budget.exploration_fraction))
            exploitation_count = limit - exploration_count
            ranked = sorted(eligible, key=lambda item: (-item.priority, item.question_id))
            exploitation = ranked[:exploitation_count]
            remaining = ranked[exploitation_count:]
            rng.shuffle(remaining)
            exploration = remaining[:exploration_count]
            selected_ids = {item.question_id for item in (*exploitation, *exploration)}
        finalized: list[QuestionPlanItem] = []
        for item in raw_items:
            if item.status == "selected" and item.question_id not in selected_ids:
                finalized.append(
                    QuestionPlanItem(
                        question_id=item.question_id,
                        question_digest=item.question_digest,
                        pack_id=item.pack_id,
                        status="deferred",
                        fields=item.fields,
                        priority=item.priority,
                        selected_capability=item.selected_capability,
                        selected_mode=item.selected_mode,
                        reasons=(f"eligible but deferred by {budget.id} execution budget",),
                        historical_observations=item.historical_observations,
                        historical_utility=item.historical_utility,
                    )
                )
            else:
                finalized.append(item)
        finalized.sort(
            key=lambda item: (
                {"selected": 0, "deferred": 1, "blocked": 2, "not-applicable": 3}[item.status],
                -item.priority,
                item.question_id,
            )
        )
        result = QuestionPlan(
            dataset_profile_digest=profile.digest,
            semantic_field_map_digest=field_map.digest,
            question_pack_digests=tuple(item.digest for item in packs),
            budget=budget,
            items=tuple(finalized),
            planner_id=self.id,
            planner_version=self.version,
            historical_revision=history.digest,
            warnings=(
                "All applicable questions remain visible; deferred and blocked questions were not executed.",
            ),
        )
        problems = result.validate()
        if problems:
            raise ValueError("invalid question plan: " + "; ".join(problems))
        return result


__all__ = ["QuestionPlanner", "SEVERITY_WEIGHT", "effort_budget"]
