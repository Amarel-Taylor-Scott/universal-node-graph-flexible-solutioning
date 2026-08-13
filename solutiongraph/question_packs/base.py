"""Small authoring helpers shared by the built-in question packs."""

from __future__ import annotations

from solutiongraph.interrogation.model import (
    CheckRequirement,
    QuestionDefinition,
    QuestionPack,
    StandardsReference,
)

SOURCE = (
    "https://github.com/Amarel-Taylor-Scott/"
    "universal-node-graph-flexible-solutioning/tree/main/solutiongraph/question_packs"
)


def deterministic(
    capability: str,
    *,
    cost_tier: int = 1,
    evidence: tuple[str, ...] = ("evidence.aggregate", "evidence.row-identities"),
) -> CheckRequirement:
    return CheckRequirement(
        capability=capability,
        mode="deterministic",
        cost_tier=cost_tier,
        evidence_kinds=evidence,
    )


def external(
    capability: str,
    *,
    permission: str = "network.read",
    cost_tier: int = 5,
    optional: bool = True,
) -> CheckRequirement:
    return CheckRequirement(
        capability=capability,
        mode="external",
        optional=optional,
        effect="network.read",
        permission=permission,
        cost_tier=cost_tier,
        evidence_kinds=("evidence.authority-response", "evidence.source-vintage"),
    )


def llm(
    capability: str,
    *,
    cost_tier: int = 7,
    optional: bool = True,
) -> CheckRequirement:
    return CheckRequirement(
        capability=capability,
        mode="llm",
        optional=optional,
        effect="model.invoke",
        permission="model.invoke",
        cost_tier=cost_tier,
        evidence_kinds=("evidence.structured-model-output", "evidence.prompt-digest"),
    )


def human(capability: str, *, cost_tier: int = 9) -> CheckRequirement:
    return CheckRequirement(
        capability=capability,
        mode="human",
        optional=True,
        effect="human.review",
        permission="human.review",
        cost_tier=cost_tier,
        evidence_kinds=("evidence.reviewer-decision",),
    )


def q(
    domain: str,
    key: str,
    title: str,
    text: str,
    concepts: tuple[str, ...],
    finding: str,
    severity: str,
    checks: tuple[CheckRequirement, ...],
    *,
    scope: str = "field",
    preconditions: tuple[str, ...] = ("precondition.records-available",),
    dependencies: tuple[str, ...] = (),
    evidence: tuple[str, ...] = ("evidence.affected-count",),
    repairs: tuple[str, ...] = (),
    abstain: tuple[str, ...] = (),
    jurisdictions: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    references: tuple[StandardsReference, ...] = (),
    privacy_class: str = "privacy.aggregate",
) -> QuestionDefinition:
    return QuestionDefinition(
        id=f"question.{domain}.{key}",
        version="1.0.0",
        title=title,
        question=text,
        concept_ids=concepts,
        scope=scope,
        finding_code=finding,
        severity=severity,
        checks=checks,
        preconditions=preconditions,
        dependencies=dependencies,
        evidence_required=evidence,
        repair_families=repairs,
        abstain_when=abstain,
        jurisdictions=jurisdictions,
        tags=(f"domain.{domain}", *tags),
        references=references,
        privacy_class=privacy_class,
    )


def pack(
    domain: str,
    title: str,
    description: str,
    questions: tuple[QuestionDefinition, ...],
) -> QuestionPack:
    concepts = tuple(dict.fromkeys(
        concept for question in questions for concept in question.concept_ids
    ))
    return QuestionPack(
        id=f"question-pack.{domain}",
        version="1.0.0",
        title=title,
        description=description,
        concept_ids=concepts,
        questions=questions,
        source=SOURCE,
        license="MIT",
        extensions=(("question-pack.maturity", "reference"),),
    )


__all__ = ["SOURCE", "deterministic", "external", "human", "llm", "pack", "q"]
