"""Pack-aware controls for active market investigations.

This module performs deterministic checks before a case may compose external
messages. It is intentionally stricter than prompt instructions: high-risk
research requires explicit authorization, sensitive fields are rejected, and
no pack may use a fabricated persona or facilitate unlawful transactions.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, Field

from .config import Settings
from .domain import CaseKind, CaseRecord, RiskTier
from .packs import VerticalPack


class CasePolicyDecision(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    controls: dict[str, Any] = Field(default_factory=dict)


_FORBIDDEN_PURPOSE_RE = re.compile(
    r"\b(?:buy|purchase|obtain|source|arrange|facilitate|find)\b.{0,80}"
    r"\b(?:illegal|unlicensed\s+loan|stolen|contraband|fake\s+documents?|undocumented\s+workers?\s+off\s+books)\b|"
    r"\b(?:evade|avoid)\b.{0,50}\b(?:regulator|license|law\s+enforcement|tax|reporting)\b",
    re.IGNORECASE,
)
_DECEPTIVE_SCENARIO_RE = re.compile(
    r"\b(?:fake|fabricated|invented|pretend|impersonat(?:e|ing)|false)\b.{0,80}"
    r"\b(?:identity|emergency|income|credit|constituent|customer|applicant|borrower|patient|immigration|disability)\b|"
    r"\b(?:hide|conceal)\b.{0,40}\b(?:automation|requester|purpose|identity)\b",
    re.IGNORECASE,
)
_ACCUSATORY_OUTPUT_RE = re.compile(
    r"\b(?:prove|declare|label|publish|expose)\b.{0,70}\b(?:fraud|scam|criminal|illegal|predatory)\b",
    re.IGNORECASE,
)
_SENSITIVE_KEYS = {
    "ssn",
    "social_security_number",
    "bank_account",
    "bank_account_number",
    "routing_number",
    "credit_card",
    "credit_card_number",
    "cvv",
    "date_of_birth",
    "dob",
    "passport_number",
    "driver_license_number",
    "login_password",
    "password",
    "pin",
    "biometric",
    "precise_device_location",
    "private_home_address",
}
_TRANSACTION_KEYS = {
    "loan_application",
    "submit_application",
    "authorize_credit_pull",
    "credit_pull_authorization",
    "accept_offer",
    "sign_contract",
    "place_order",
    "send_payment",
    "payment_credentials",
    "purchase_illegal_service",
}


def evaluate_case_policy(settings: Settings, case: CaseRecord, pack: VerticalPack | None) -> CasePolicyDecision:
    reasons: list[str] = []
    flattened = dict(_flatten(case.requirements))
    keys = {key.lower().split(".")[-1] for key in flattened}
    serialized = f"{case.title}\n{case.objective}\n{case.requirements}"[:200_000]

    if case.kind is CaseKind.MARKET_INVESTIGATION and case.investigation_mode is None:
        reasons.append("Market investigation cases require an explicit investigation_mode.")
    if _FORBIDDEN_PURPOSE_RE.search(serialized):
        reasons.append("The requested purpose appears to facilitate an unlawful transaction or evasion.")
    if _DECEPTIVE_SCENARIO_RE.search(serialized):
        reasons.append("The scenario appears to rely on a fabricated identity, status, emergency, or hidden requester.")
    if _ACCUSATORY_OUTPUT_RE.search(serialized):
        reasons.append("SourceLoop may document discrepancies but may not pre-judge fraud, illegality, or liability.")

    sensitive = sorted(keys.intersection(_SENSITIVE_KEYS))
    if sensitive:
        reasons.append(f"Sensitive personal or payment fields are prohibited: {', '.join(sensitive)}")
    transaction_fields = sorted(keys.intersection(_TRANSACTION_KEYS))
    if transaction_fields:
        reasons.append(f"Autonomous applications, transactions, or legal commitments are prohibited: {', '.join(transaction_fields)}")

    if pack:
        prohibited = sorted(keys.intersection({field.lower().split(".")[-1] for field in pack.prohibited_requirement_fields}))
        if prohibited:
            reasons.append(f"Pack-prohibited requirement fields are present: {', '.join(prohibited)}")

        missing_operator = [
            field for field in pack.required_operator_fields if not _truthy(_lookup(case.requirements, field))
        ]
        if missing_operator:
            reasons.append(f"Required operator controls are missing: {', '.join(missing_operator)}")

        if pack.restricted or pack.risk_tier is RiskTier.RESTRICTED:
            if not settings.allow_restricted_investigations:
                reasons.append("Restricted investigation packs are disabled by deployment policy.")
            if not _truthy(case.requirements.get("authorized_research")):
                reasons.append("Restricted investigations require authorized_research=true.")
            client_type = str(case.requirements.get("client_type", "")).strip().lower()
            allowed_client_types = {
                value.strip().lower()
                for value in (pack.raw.get("allowed_client_types") or settings.restricted_client_types)
            }
            if not client_type or client_type not in allowed_client_types:
                reasons.append("Restricted investigations require an approved institutional client_type.")
            if case.max_contacts > settings.max_restricted_contacts:
                reasons.append(
                    f"Restricted investigations may contact at most {settings.max_restricted_contacts} counterparties."
                )
            if case.max_followups > 1:
                reasons.append("Restricted investigations may configure at most one follow-up per counterparty.")

    if case.kind is CaseKind.MARKET_INVESTIGATION:
        if not case.requester_email:
            reasons.append("Market investigations require an accountable requester email address.")
        if not case.contacts and not case.demo:
            # This is not a fatal policy issue at creation; the practitioner will
            # wait at HOW. It is still useful to expose as a control receipt.
            contact_state = "awaiting_discovery_or_operator_contacts"
        else:
            contact_state = "present"
    else:
        contact_state = "not_applicable"

    return CasePolicyDecision(
        allowed=not reasons,
        reasons=reasons,
        controls={
            "pack": pack.id if pack else None,
            "risk_tier": pack.risk_tier.value if pack else case.risk_tier.value,
            "restricted": bool(pack and pack.restricted),
            "contact_state": contact_state,
            "sensitive_fields_detected": sensitive,
            "transaction_fields_detected": transaction_fields,
            "external_actions_require_approval": True,
        },
    )


def missing_required_fields(case: CaseRecord, pack: VerticalPack | None) -> list[str]:
    if not pack:
        return []
    return [field for field in pack.required_fields if not _truthy(_lookup(case.requirements, field))]


def _flatten(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield from _flatten(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _flatten(child, f"{prefix}[{index}]")
    else:
        yield prefix, value


def _lookup(payload: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _truthy(value: Any) -> bool:
    return value not in (None, "", [], {}, False)
