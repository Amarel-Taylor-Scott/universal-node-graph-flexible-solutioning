"""Email, telephone, and contact-point interrogation questions."""

from __future__ import annotations

from solutiongraph.question_packs.base import deterministic, external, human, llm, pack, q
from solutiongraph.question_packs.concepts import E164, RFC5322, SCHEMA_ORG

CONTACT_POINT_QUESTIONS = (
    q(
        "contact-point", "email-syntax", "Email syntax",
        "Are email addresses syntactically plausible after trimming and Unicode-domain normalization?",
        ("concept.contact.email",), "contact.email-syntax", "high",
        (deterministic("quality.email-syntax-check"),), references=(RFC5322,),
        repairs=("repair.normalize-email-domain",),
    ),
    q(
        "contact-point", "email-domain", "Email-domain plausibility",
        "Does the email domain have a plausible relationship to the organization domain without treating it as ownership proof?",
        ("concept.contact.email", "concept.organization.domain"),
        "contact.email-domain-conflict", "medium",
        (deterministic("quality.email-domain-check", cost_tier=2),
         external("authority.dns-domain-lookup", cost_tier=5)), scope="entity",
    ),
    q(
        "contact-point", "email-ownership", "Mailbox ownership and deliverability boundary",
        "Is syntactic validity being distinguished from mailbox ownership, consent, and deliverability?",
        ("concept.contact.email",), "contact.email-evidence-overclaim", "high",
        (human("quality.review-email-authority"),), scope="pipeline",
        abstain=("active probing is not explicitly authorized",),
        privacy_class="privacy.contact",
    ),
    q(
        "contact-point", "phone-format", "International phone format",
        "Can each phone number be parsed with explicit country context and represented without losing its extension?",
        ("concept.contact.telephone", "concept.postal.country"),
        "contact.phone-format", "high",
        (deterministic("quality.phone-format-check"),), references=(E164,),
        repairs=("repair.normalize-e164-when-explicit",),
    ),
    q(
        "contact-point", "phone-country", "Phone and country consistency",
        "Does the international calling code agree with the address country, and are exceptions explicitly recorded?",
        ("concept.contact.telephone", "concept.postal.country"),
        "contact.phone-country-conflict", "medium",
        (deterministic("quality.phone-country-check", cost_tier=2),), scope="cross-field",
    ),
    q(
        "contact-point", "contact-placeholders", "Contact placeholders and repetition",
        "Are phone numbers and emails free of placeholder values or suspicious reuse across unrelated entities?",
        ("concept.contact.telephone", "concept.contact.email"),
        "contact.placeholder-or-reuse", "high",
        (deterministic("quality.placeholder-check"),
         deterministic("quality.contact-reuse-check", cost_tier=2)), scope="dataset",
    ),
    q(
        "contact-point", "role-account", "Role versus personal mailbox",
        "Is a role mailbox distinguished from a person-specific mailbox when workflow semantics require it?",
        ("concept.contact.email", "concept.contact.type"),
        "contact.role-account-mismatch", "low",
        (deterministic("quality.role-account-check"),
         llm("quality.adjudicate-contact-role")), scope="entity",
    ),
    q(
        "contact-point", "service-context", "Contact type, language, and service area",
        "Are contact type, supported language, service area, and business-hour attributes mutually consistent?",
        ("concept.contact.type", "concept.contact.language"),
        "contact.service-context-conflict", "medium",
        (deterministic("quality.contact-context-check", cost_tier=3),
         human("quality.review-contact-context")), scope="entity", references=(SCHEMA_ORG,),
    ),
)

CONTACT_POINT_PACK = pack(
    "contact-point",
    "Contact-point interrogation",
    "Email, telephone, contact-role, reuse, authority, and service-context questions.",
    CONTACT_POINT_QUESTIONS,
)

__all__ = ["CONTACT_POINT_PACK", "CONTACT_POINT_QUESTIONS"]
