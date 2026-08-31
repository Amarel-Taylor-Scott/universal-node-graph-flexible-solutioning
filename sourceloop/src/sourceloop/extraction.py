"""Deterministic baseline extraction and dual-agent reconciliation."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from .domain import CaseKind, CaseRecord, Claim, ClaimKind, Interaction, Quote

_MONEY_RE = re.compile(
    r"(?P<currency>\$|USD\s*)?(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
    r"\s*(?:/|per\s+)?(?P<unit>productive\s+hour|paid\s+hour|hour|hr|month|site|visit|seat|fte|unit)?",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_VALID_RE = re.compile(r"valid\s+(?:through|until)\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_PAYMENT_RE = re.compile(r"\bnet\s+(15|30|45|60|90)\b", re.IGNORECASE)
_LEAD_RE = re.compile(r"\b(?:lead|ramp)(?:\s+time)?\s*(?:is|:)?\s*(\d+)\s*(day|days|week|weeks)\b", re.IGNORECASE)
_SEGMENT_RE = re.compile(r"(?<=[.!?;])\s+|\n+")


def extract_reply_payload(case: CaseRecord, interaction: Interaction) -> dict[str, Any]:
    """Return schema-shaped candidates without assigning durable IDs."""

    body = interaction.body.strip()
    lower = body.lower()
    contact = next((item for item in case.contacts if item.endpoint == interaction.endpoint), None)
    organization = contact.organization_name if contact else interaction.endpoint
    subject_id = contact.id if contact else interaction.endpoint

    claims: list[dict[str, Any]] = [
        {
            "subject_id": subject_id,
            "predicate": "responded_to_case",
            "value": True,
            "kind": ClaimKind.FACT_CONFIRMATION.value,
            "confidence": 1.0,
            "geography_scope": contact.geography if contact else None,
            "evidence_ids": [interaction.evidence_id],
            "corroboration_status": "direct_response",
            "reuse_scope": "case_only",
        }
    ]

    if "do not contact" in lower or "no further contact" in lower or "unsubscribe" in lower:
        claims.append(
            {
                "subject_id": subject_id,
                "predicate": "contact_permission",
                "value": "suppressed",
                "kind": ClaimKind.REFUSAL.value,
                "confidence": 1.0,
                "evidence_ids": [interaction.evidence_id],
                "corroboration_status": "direct_response",
                "reuse_scope": "suppression_only",
            }
        )

    if case.kind is CaseKind.CIVIC_INTELLIGENCE:
        if any(token in lower for token in ("serve", "serves", "cover", "covers")):
            claims.append(
                {
                    "subject_id": subject_id,
                    "predicate": "reported_service_scope",
                    "value": body,
                    "kind": ClaimKind.RESPONDENT_REPORT.value,
                    "confidence": 0.85,
                    "geography_scope": contact.geography if contact else None,
                    "evidence_ids": [interaction.evidence_id],
                    "corroboration_status": "direct_response",
                    "reuse_scope": "case_only",
                }
            )
        referrals = [candidate.lower() for candidate in _EMAIL_RE.findall(body) if candidate.lower() != interaction.endpoint]
        for referral in sorted(set(referrals)):
            claims.append(
                {
                    "subject_id": subject_id,
                    "predicate": "referred_inquiry_to",
                    "value": referral,
                    "kind": ClaimKind.REFERRAL.value,
                    "confidence": 0.9,
                    "evidence_ids": [interaction.evidence_id],
                    "corroboration_status": "direct_response_unverified_target",
                    "reuse_scope": "case_only",
                }
            )

    quote: dict[str, Any] | None = None
    if case.kind is CaseKind.QUOTE_INTELLIGENCE:
        line_items: list[dict[str, Any]] = []
        seen: set[tuple[float, str, str]] = set()
        segments = [segment.strip() for segment in _SEGMENT_RE.split(body) if segment.strip()]
        for segment in segments:
            segment_lower = segment.lower()
            has_price_marker = any(marker in segment for marker in ("$", "USD")) or bool(
                re.search(r"\b\d+(?:\.\d+)?\s*(?:per|/)\s*", segment, re.IGNORECASE)
            )
            if not has_price_marker:
                continue
            for match in _MONEY_RE.finditer(segment):
                currency_marker = match.group("currency")
                unit_marker = match.group("unit")
                if not currency_marker and not unit_marker:
                    continue
                amount = float(match.group("amount").replace(",", ""))
                if amount == 0:
                    continue
                unit = _normalize_unit(unit_marker, segment_lower)
                description = _description_for_line(segment_lower, unit)
                key = (amount, unit, description)
                if key in seen:
                    continue
                seen.add(key)
                line_items.append(
                    {
                        "description": description,
                        "unit": unit,
                        "quantity": None,
                        "unit_price": amount,
                        "currency": "USD",
                        "one_time": unit == "one_time",
                        "assumptions": [],
                        "exclusions": [],
                    }
                )

        exclusions = [segment for segment in segments if "exclud" in segment.lower() or "not included" in segment.lower()]
        assumptions = [segment for segment in segments if "assum" in segment.lower()]
        valid_until = None
        valid_match = _VALID_RE.search(body)
        if valid_match:
            valid_until = datetime.strptime(valid_match.group(1), "%Y-%m-%d").replace(tzinfo=UTC).isoformat()

        commercial_terms: dict[str, Any] = {}
        payment_match = _PAYMENT_RE.search(body)
        if payment_match:
            commercial_terms["payment_terms"] = f"Net {payment_match.group(1)}"
        if "deposit" in lower:
            commercial_terms["deposit_mentioned"] = True

        operational_terms: dict[str, Any] = {}
        lead_match = _LEAD_RE.search(body)
        if lead_match:
            operational_terms["lead_time"] = f"{lead_match.group(1)} {lead_match.group(2).lower()}"
        if any(marker in lower for marker in ("available", "availability", "capacity", "can support")):
            operational_terms["availability_reported"] = True

        if line_items:
            quote = {
                "supplier_name": organization,
                "contact_id": contact.id if contact else None,
                "quote_type": "non_binding",
                "line_items": line_items,
                "commercial_terms": commercial_terms,
                "operational_terms": operational_terms,
                "exclusions": exclusions,
                "assumptions": assumptions,
                "currency": "USD",
                "valid_until": valid_until,
                "evidence_ids": [interaction.evidence_id],
                "extraction_confidence": 0.82,
                "unresolved_fields": _unresolved_quote_fields(lower, valid_until),
                "normalization_lineage": [
                    "Parsed directly from respondent message.",
                    "Currency normalized to USD where a dollar symbol or USD marker was present.",
                    "No quantity multiplication was applied without an explicit quantity.",
                ],
            }
        else:
            claims.append(
                {
                    "subject_id": subject_id,
                    "predicate": "quote_status",
                    "value": "response_received_without_extractable_price",
                    "kind": ClaimKind.UNCERTAINTY.value,
                    "confidence": 0.8,
                    "evidence_ids": [interaction.evidence_id],
                    "corroboration_status": "needs_human_review",
                    "reuse_scope": "case_only",
                }
            )

    return {"claims": claims, "quote": quote}


def reconcile_extractor_outputs(
    case: CaseRecord,
    interaction: Interaction,
    outputs: list[dict[str, Any]],
) -> tuple[list[Claim], Quote | None, bool]:
    """Validate two or more extractor outputs and expose disagreement explicitly."""

    usable = [output for output in outputs if isinstance(output, dict) and "claims" in output]
    if not usable:
        usable = [extract_reply_payload(case, interaction)]

    canonical = [_canonical(candidate) for candidate in usable]
    disagreement = len(set(canonical)) > 1
    selected = usable[0]

    claims = [Claim.model_validate(candidate) for candidate in selected.get("claims", [])]
    quote_payload = selected.get("quote")
    quote = Quote.model_validate(quote_payload) if quote_payload else None

    if disagreement:
        for claim in claims:
            claim.confidence = min(claim.confidence, 0.65)
            claim.corroboration_status = "extractor_disagreement"
        if quote:
            quote.extraction_confidence = min(quote.extraction_confidence, 0.65)
            quote.unresolved_fields = sorted(set(quote.unresolved_fields + ["extractor_disagreement"]))

    return claims, quote, disagreement


def _canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _normalize_unit(unit: str | None, line: str) -> str:
    candidate = (unit or "").lower().strip()
    aliases = {
        "hr": "hour",
        "productive hour": "productive_hour",
        "paid hour": "paid_hour",
        "fte": "fte_month",
        "seat": "seat_month",
    }
    if candidate in aliases:
        return aliases[candidate]
    if candidate:
        return candidate
    if "setup" in line or "implementation" in line or "one-time" in line or "one time" in line:
        return "one_time"
    return "unspecified"


def _description_for_line(line: str, unit: str) -> str:
    if "setup" in line:
        return "setup fee"
    if "implementation" in line:
        return "implementation fee"
    if "training" in line:
        return "training fee"
    if "monthly" in line or unit.endswith("month"):
        return "monthly service"
    if "visit" in line or unit == "visit":
        return "service visit"
    if unit in {"productive_hour", "paid_hour", "hour"}:
        return "hourly service"
    return "quoted service"


def _unresolved_quote_fields(lower: str, valid_until: str | None) -> list[str]:
    unresolved: list[str] = []
    if not _PAYMENT_RE.search(lower):
        unresolved.append("payment_terms")
    if "tax" not in lower:
        unresolved.append("taxes")
    if not any(marker in lower for marker in ("scope confirmed", "scope is", "subject to", "upon review")):
        unresolved.append("final_scope_confirmation")
    if valid_until is None:
        unresolved.append("quote_validity")
    return unresolved
