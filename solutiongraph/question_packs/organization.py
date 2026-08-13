"""Organization-name, identity, and authority interrogation questions."""

from __future__ import annotations

from solutiongraph.question_packs.base import deterministic, external, human, llm, pack, q
from solutiongraph.question_packs.concepts import GLEIF, SCHEMA_ORG

NAME = (
    "concept.organization.name",
    "concept.organization.legal-name",
    "concept.organization.alternate-name",
)

ORGANIZATION_QUESTIONS = (
    q(
        "organization", "name-role", "Legal, display, and brand-name roles",
        "Are legal names, display names, DBAs, brands, divisions, and former names stored in distinct fields?",
        NAME, "organization.name-role-conflict", "high",
        (deterministic("quality.organization-name-role-check"),
         llm("quality.adjudicate-organization-name-role")), scope="entity",
        references=(SCHEMA_ORG,), abstain=("source semantics are undocumented",),
    ),
    q(
        "organization", "name-placeholders", "Organization-name placeholders",
        "Are organization names nonempty and free of placeholder, test, or address-like values?",
        NAME, "organization.name-placeholder", "high",
        (deterministic("quality.placeholder-check"),),
        repairs=("repair.normalize-missing", "repair.quarantine-record"),
    ),
    q(
        "organization", "name-punctuation", "Organization-name punctuation",
        "Do names begin or end with unexpected symbols, contain repeated punctuation, or embed control characters?",
        NAME, "organization.name-punctuation", "medium",
        (deterministic("quality.punctuation-check"),
         deterministic("quality.unicode-control-check")),
        repairs=("repair.normalize-unicode", "repair.strip-controls"),
    ),
    q(
        "organization", "branding-case", "Official branding and capitalization",
        "Does capitalization preserve known branding instead of applying naive title casing?",
        NAME, "organization.branding-case", "low",
        (deterministic("quality.case-pattern-check"),
         external("authority.organization-name-lookup", cost_tier=5),
         llm("quality.adjudicate-brand-casing")),
        abstain=("no authoritative branding evidence is available",), references=(GLEIF,),
    ),
    q(
        "organization", "legal-suffix", "Corporate suffix and jurisdiction",
        "Is the corporate suffix recognizable and consistent with the stated jurisdiction and legal-name role?",
        ("concept.organization.legal-name", "concept.organization.name"),
        "organization.legal-form-mismatch", "medium",
        (deterministic("quality.organization-suffix-check"),
         external("authority.organization-registration-lookup", cost_tier=5),
         human("quality.review-legal-form")), scope="entity",
        repairs=("repair.organization-comparison-key",),
        abstain=("jurisdiction is ambiguous", "registry coverage is unavailable"),
        references=(GLEIF,),
    ),
    q(
        "organization", "normalized-duplicates", "Normalized-name duplicates",
        "Do different records collapse to the same conservative comparison key while identifiers or addresses disagree?",
        NAME, "organization.possible-duplicate", "high",
        (deterministic("quality.organization-duplicate-check", cost_tier=3),
         llm("quality.adjudicate-organization-duplicate")), scope="entity",
        repairs=("repair.organization-comparison-key", "repair.quarantine-duplicate"),
    ),
    q(
        "organization", "identifier-consistency", "Organization identifier consistency",
        "Do legal names and addresses agree with LEI, registration, tax, or other authoritative identifiers?",
        ("concept.organization.identifier", "concept.organization.legal-name"),
        "organization.identifier-conflict", "high",
        (deterministic("quality.identifier-uniqueness-check"),
         external("authority.organization-identifier-lookup", cost_tier=5),
         human("quality.review-identifier-conflict")), scope="entity",
        preconditions=("precondition.records-available", "precondition.identifier-available"),
        references=(GLEIF,),
    ),
    q(
        "organization", "domain-consistency", "Name and web-domain consistency",
        "Are organization names, websites, and contact-email domains mutually plausible without treating similarity as proof?",
        ("concept.organization.name", "concept.organization.domain", "concept.contact.email"),
        "organization.domain-name-conflict", "medium",
        (deterministic("quality.organization-domain-check", cost_tier=3),
         llm("quality.adjudicate-domain-name")), scope="entity",
        preconditions=("precondition.records-available", "precondition.domain-available"),
    ),
    q(
        "organization", "temporal-status", "Organization status over time",
        "Are renames, mergers, dissolutions, and address changes evaluated at the record's effective date?",
        ("concept.organization.status-date", "concept.organization.legal-name"),
        "organization.temporal-status-conflict", "high",
        (deterministic("quality.datetime-parse-check"),
         external("authority.organization-history-lookup", cost_tier=6),
         human("quality.review-organization-history")), scope="entity",
        preconditions=("precondition.records-available", "precondition.event-time-available"),
    ),
)

ORGANIZATION_PACK = pack(
    "organization",
    "Organization identity interrogation",
    "Questions for organization names, legal forms, identifiers, authority evidence, duplicates, and temporal status.",
    ORGANIZATION_QUESTIONS,
)

__all__ = ["ORGANIZATION_PACK", "ORGANIZATION_QUESTIONS"]
