"""Person-name and identity-field questions."""

from __future__ import annotations

from solutiongraph.question_packs.base import deterministic, human, llm, pack, q

PERSON = (
    "concept.person.name", "concept.person.given-name", "concept.person.family-name",
)

PERSON_QUESTIONS = (
    q(
        "person", "name-components", "Name-component consistency",
        "Do full, given, and family name fields agree without assuming one global name order?",
        PERSON, "person.name-component-conflict", "medium",
        (deterministic("quality.person-name-component-check"),
         llm("quality.adjudicate-person-name-components")), scope="entity",
    ),
    q(
        "person", "placeholder", "Person-name placeholders",
        "Are names free of titles-only, initials-only, test, anonymous, or contact-role placeholders?",
        PERSON, "person.name-placeholder", "high",
        (deterministic("quality.placeholder-check"),),
        repairs=("repair.normalize-missing", "repair.quarantine-record"),
    ),
    q(
        "person", "punctuation-script", "Punctuation, script, and diacritics",
        "Are apostrophes, hyphens, diacritics, and non-Latin scripts preserved while control or spoofing characters are flagged?",
        PERSON, "person.name-script-anomaly", "medium",
        (deterministic("quality.unicode-control-check"),
         deterministic("quality.person-name-script-check", cost_tier=2)),
        repairs=("repair.normalize-unicode",),
    ),
    q(
        "person", "duplicate-identity", "Possible duplicate people",
        "Do similar names plus shared contacts or addresses indicate duplicates without collapsing distinct people?",
        PERSON, "person.possible-duplicate", "high",
        (deterministic("quality.person-duplicate-check", cost_tier=3),
         human("quality.review-person-duplicate")), scope="entity",
    ),
    q(
        "person", "privacy", "Person-data minimization",
        "Are personal names and contact details exposed only to nodes that require them?",
        PERSON, "person.privacy-boundary", "critical",
        (human("quality.review-person-privacy"),), scope="pipeline",
        privacy_class="privacy.personal",
    ),
)

PERSON_PACK = pack(
    "person", "Person identity interrogation",
    "Name components, scripts, placeholders, entity resolution, and privacy questions.",
    PERSON_QUESTIONS,
)

__all__ = ["PERSON_PACK", "PERSON_QUESTIONS"]
