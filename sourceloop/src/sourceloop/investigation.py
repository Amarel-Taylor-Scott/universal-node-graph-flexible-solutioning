"""Pack-driven investigation planning, evidence rules, and correspondence helpers."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from contextlib import suppress
from typing import Any

from .domain import (
    CaseCreate,
    CaseKind,
    CaseRecord,
    ContactRoute,
    FindingKind,
    FindingStatus,
    Interaction,
    InvestigationFinding,
    InvestigationMode,
    Quote,
    RiskTier,
    Severity,
    case_token,
    stable_key,
)
from .packs import VerticalPack


def validate_case_request(request: CaseCreate, pack: VerticalPack) -> list[str]:
    """Return deterministic validation errors before a governed case is persisted."""

    errors: list[str] = []
    if request.kind is not pack.case_kind:
        errors.append(
            f"Pack {pack.id!r} requires case kind {pack.case_kind.value!r}, not {request.kind.value!r}."
        )
    if (
        request.investigation_mode is not None
        and pack.investigation_mode is not None
        and request.investigation_mode is not pack.investigation_mode
    ):
        errors.append(
            f"Pack {pack.id!r} requires investigation mode {pack.investigation_mode.value!r}, "
            f"not {request.investigation_mode.value!r}."
        )
    if pack.requires_requester_email and not (request.requester_email or "").strip():
        errors.append(f"Pack {pack.id!r} requires a truthful requester email address.")
    if pack.institutional_only and not request.governance_acknowledgements.get("institutional_authority", False):
        errors.append("This restricted pack requires institutional_authority acknowledgement.")
    for acknowledgement in pack.required_acknowledgements:
        if not request.governance_acknowledgements.get(acknowledgement, False):
            errors.append(f"Missing required governance acknowledgement: {acknowledgement}")
    request_text = json.dumps(
        {
            "objective": request.objective,
            "requirements": request.requirements,
        },
        default=str,
        sort_keys=True,
    )
    for pattern in pack.prohibited_request_patterns:
        try:
            matched = re.search(pattern, request_text, flags=re.IGNORECASE)
        except re.error as exc:
            errors.append(f"Pack {pack.id!r} contains invalid prohibited pattern {pattern!r}: {exc}")
            continue
        if matched:
            errors.append(f"The request conflicts with prohibited pattern: {pattern}")
    for field_path in pack.required_fields:
        if _get_nested(request.requirements, field_path) in (None, "", []):
            errors.append(f"Missing required request field for pack {pack.id!r}: {field_path}")
    errors.extend(validate_contacts(request.contacts, pack))
    return errors


def validate_contacts(contacts: list[ContactRoute], pack: VerticalPack) -> list[str]:
    """Validate contact routes before they enter an elevated or restricted workflow."""

    errors: list[str] = []
    if len(contacts) > pack.max_contacts:
        errors.append(
            f"Pack {pack.id!r} permits at most {pack.max_contacts} contact route(s), not {len(contacts)}."
        )
    seen: set[str] = set()
    allowed_channels = set(pack.allowed_channels)
    for contact in contacts:
        if contact.endpoint in seen:
            errors.append(f"Duplicate contact endpoint: {contact.endpoint}")
        seen.add(contact.endpoint)
        if contact.channel not in allowed_channels:
            errors.append(
                f"Contact {contact.endpoint!r} uses channel {contact.channel!r}; allowed: {sorted(allowed_channels)}."
            )
        if pack.risk_tier in {RiskTier.ELEVATED, RiskTier.RESTRICTED} and not contact.source_public:
            errors.append(f"Contact {contact.endpoint!r} is not marked as public or customer-authorized.")
        if pack.risk_tier is RiskTier.RESTRICTED and not contact.business_only:
            errors.append(f"Restricted pack {pack.id!r} permits organizational or professional endpoints only.")
        if not contact.organization_name.strip():
            errors.append(f"Contact {contact.endpoint!r} is missing an accountable organization name.")
    return errors


def governance_snapshot(request: CaseCreate, pack: VerticalPack) -> dict[str, Any]:
    return {
        "pack_id": pack.id,
        "risk_tier": pack.risk_tier.value,
        "institutional_only": pack.institutional_only,
        "required_acknowledgements": list(pack.required_acknowledgements),
        "acknowledgements": dict(request.governance_acknowledgements),
        "allowed_channels": list(pack.allowed_channels),
        "prohibited_actions": list(pack.prohibited_actions),
        "prohibited_request_patterns": list(pack.prohibited_request_patterns),
        "sensitive_data_categories": list(pack.sensitive_data_categories),
        "message_purpose": pack.message_purpose,
        "reuse_policy": pack.reuse_policy,
    }


def response_coverage(pack: VerticalPack, body: str) -> dict[str, bool]:
    lower = body.lower()
    result: dict[str, bool] = {}
    for field in pack.response_fields:
        markers = [*field.markers, *field.aliases]
        result[field.id] = any(marker in lower for marker in markers) if markers else False
    return result


def critical_missing_fields(
    pack: VerticalPack,
    body: str,
    quote: Quote | None = None,
    previously_covered: Iterable[str] | None = None,
) -> list[str]:
    coverage = response_coverage(pack, body)
    covered = set(previously_covered or ())
    covered.update(field_id for field_id, present in coverage.items() if present)
    missing = [field.id for field in pack.response_fields if field.critical and field.id not in covered]
    if quote is not None:
        missing.extend(
            field
            for field in quote.unresolved_fields
            if field in pack.critical_quote_fields and field not in covered
        )
    return sorted(set(missing))


def evaluate_findings(
    case: CaseRecord,
    interaction: Interaction,
    pack: VerticalPack,
) -> list[InvestigationFinding]:
    """Apply transparent declarative rules to one response.

    Findings describe what the evidence says or omits. They deliberately avoid declaring
    a respondent illegal, fraudulent, or noncompliant without further human/legal review.
    """

    coverage = response_coverage(pack, interaction.body)
    aggregate_covered = set(case.response_coverage.get(interaction.endpoint, []))
    aggregate_covered.update(field for field, present in coverage.items() if present)
    contact = next((item for item in case.contacts if item.endpoint == interaction.endpoint), None)
    subject_id = contact.id if contact else interaction.endpoint
    findings: list[InvestigationFinding] = []

    for rule in pack.finding_rules:
        matched = False
        value: Any = None
        if rule.missing_field:
            matched = rule.missing_field not in aggregate_covered
            value = {"missing_field": rule.missing_field}
        if rule.patterns:
            pattern_match = _first_match(rule.patterns, interaction.body)
            if pattern_match is not None and not _matches_any(rule.negative_patterns, interaction.body):
                matched = True
                value = _capture_value(rule.value_pattern, interaction.body, pattern_match)
        if not matched:
            continue
        summary = rule.summary
        if value not in (None, ""):
            with suppress(KeyError, IndexError, ValueError):
                summary = summary.format(value=value)
        findings.append(
            InvestigationFinding(
                rule_id=rule.id,
                kind=rule.kind,
                severity=rule.severity,
                title=rule.title,
                summary=summary,
                subject_id=subject_id,
                value=value,
                evidence_ids=[interaction.evidence_id],
                confidence=rule.confidence,
                requires_human_review=rule.requires_human_review,
            )
        )

    # Every investigation response receives a neutral coverage finding so absence and
    # completeness are measurable without turning silence into an accusation.
    if case.kind is CaseKind.MARKET_INVESTIGATION:
        answered = sorted(aggregate_covered)
        missing_critical = sorted(
            field.id for field in pack.response_fields if field.critical and field.id not in aggregate_covered
        )
        findings.append(
            InvestigationFinding(
                rule_id="response_coverage",
                kind=_coverage_kind(missing_critical),
                severity=_coverage_severity(missing_critical),
                title="Direct-response field coverage",
                summary=(
                    f"The response covered {len(answered)} configured field(s); "
                    f"{len(missing_critical)} critical field(s) remain unanswered."
                ),
                subject_id=subject_id,
                value={"answered": answered, "missing_critical": missing_critical},
                evidence_ids=[interaction.evidence_id],
                confidence=1.0,
                requires_human_review=False,
            )
        )

    findings.extend(_derived_numeric_findings(case, interaction, pack, subject_id))
    return _deduplicate_findings(findings)


def resolve_superseded_findings(
    case: CaseRecord,
    interaction: Interaction,
    pack: VerticalPack,
) -> None:
    """Resolve disclosure-gap findings after a later reply supplies the missing field."""

    contact = next((item for item in case.contacts if item.endpoint == interaction.endpoint), None)
    subject_id = contact.id if contact else interaction.endpoint
    covered = set(case.response_coverage.get(interaction.endpoint, []))
    missing_rules = {rule.id: rule.missing_field for rule in pack.finding_rules if rule.missing_field}
    for finding in case.findings:
        if finding.subject_id != subject_id or finding.status is not FindingStatus.OPEN:
            continue
        if finding.rule_id == "response_coverage":
            missing = set((finding.value or {}).get("missing_critical", [])) if isinstance(finding.value, dict) else set()
            if missing and missing.issubset(covered):
                finding.status = FindingStatus.RESOLVED
                finding.review_notes = "Resolved automatically after a later direct response covered the missing fields."
        elif missing_rules.get(finding.rule_id) in covered:
            finding.status = FindingStatus.RESOLVED
            finding.review_notes = "Resolved automatically after the requested disclosure was supplied."


def merge_findings(existing: list[InvestigationFinding], incoming: Iterable[InvestigationFinding]) -> None:
    seen = {
        stable_key(item.rule_id, item.subject_id, *sorted(item.evidence_ids))
        for item in existing
    }
    for finding in incoming:
        key = stable_key(finding.rule_id, finding.subject_id, *sorted(finding.evidence_ids))
        if key not in seen:
            existing.append(finding)
            seen.add(key)


def compose_initial_message(
    case: CaseRecord,
    contact: ContactRoute,
    pack: VerticalPack,
) -> tuple[str, str]:
    token = case_token(case.id)
    subject_prefix = {
        InvestigationMode.QUOTE_PROBE: "Budgetary quote request",
        InvestigationMode.PRACTICE_AUDIT: "Business-practice information request",
        InvestigationMode.COMPLIANCE_PROBE: "Disclosure and authorization information request",
        InvestigationMode.MARKET_CENSUS: "Market coverage information request",
        InvestigationMode.RECORD_VERIFICATION: "Business record verification request",
    }.get(case.investigation_mode, "Direct-source information request")
    if case.kind is CaseKind.QUOTE_INTELLIGENCE:
        subject_prefix = "Budgetary quote request"
    elif case.kind is CaseKind.CIVIC_INTELLIGENCE:
        subject_prefix = "Public civic information request"

    subject = f"[SL:{token}] {subject_prefix}: {case.title}"
    scope_lines = "\n".join(
        f"- {key.replace('_', ' ').title()}: {_render_value(value)}"
        for key, value in sorted(case.requirements.items())
        if key not in {"legal_review_notes", "internal_notes"}
    ) or "- Please confirm the current facts needed to answer the request."
    questions = "\n".join(f"- {question}" for question in pack.question_prompts)
    if not questions:
        questions = "- Please confirm the current information and correct any inaccurate assumption."

    restricted_note = ""
    if pack.risk_tier is RiskTier.RESTRICTED:
        restricted_note = (
            "This is a research-only request. It is not a loan application, purchase, contract acceptance, "
            "or request for anyone's sensitive personal information.\n\n"
        )

    greeting = contact.role_title or "team"
    body = (
        f"Hello {greeting},\n\n"
        f"I am an automated assistant acting with {case.requester_name}'s authorization. "
        f"The purpose is {pack.message_purpose}.\n\n"
        f"Request objective:\n{case.objective}\n\n"
        f"Scenario and scope:\n{scope_lines}\n\n"
        f"Questions:\n{questions}\n\n"
        f"{restricted_note}"
        f"Your response will be treated under the pack's {pack.reuse_policy.replace('_', ' ')} reuse policy. "
        f"The aim is to {pack.respondent_value}. Reply 'no further contact' to suppress future requests to "
        "this endpoint.\n\n"
        f"Thank you,\n{case.requester_name}\nAssisted by SourceLoop"
    )
    return subject, body


def compose_followup(case: CaseRecord, pack: VerticalPack, missing_fields: list[str]) -> str:
    questions: list[str] = []
    for field_id in missing_fields:
        field = pack.field(field_id)
        questions.append(field.question if field else f"Please clarify {field_id.replace('_', ' ')}.")
    rendered = "\n".join(f"- {question}" for question in questions)
    return (
        "Hello,\n\n"
        "Thank you for the response. I am the same automated assistant continuing the authorized SourceLoop "
        "thread. To complete the comparison or verification, could you clarify only the following item(s)?\n\n"
        f"{rendered}\n\n"
        "No application, contract acceptance, or sensitive personal information is requested. Reply 'no further "
        "contact' to suppress future requests to this endpoint.\n\n"
        f"Thank you,\n{case.requester_name}\nAssisted by SourceLoop"
    )


def completion_count(case: CaseRecord, pack: VerticalPack) -> int:
    if pack.completion_basis == "quotes":
        return len(case.quotes)
    if pack.completion_basis == "responses":
        return len({item.endpoint for item in case.interactions if item.direction.value == "inbound" and item.processed})
    if pack.completion_basis == "findings":
        return len(case.findings)
    return len(case.quotes) if case.kind is CaseKind.QUOTE_INTELLIGENCE else len(case.claims)


def _first_match(patterns: list[str], body: str) -> re.Match[str] | None:
    for pattern in patterns:
        try:
            match = re.search(pattern, body, flags=re.IGNORECASE | re.MULTILINE)
        except re.error:
            continue
        if match:
            return match
    return None


def _matches_any(patterns: list[str], body: str) -> bool:
    return _first_match(patterns, body) is not None


def _capture_value(value_pattern: str | None, body: str, fallback: re.Match[str]) -> Any:
    if value_pattern:
        try:
            match = re.search(value_pattern, body, flags=re.IGNORECASE | re.MULTILINE)
        except re.error:
            match = None
        if match:
            if match.groupdict():
                return {key: value for key, value in match.groupdict().items() if value is not None}
            if match.groups():
                return match.group(1) if len(match.groups()) == 1 else list(match.groups())
            return match.group(0)
    return fallback.group(0)


def _derived_numeric_findings(
    case: CaseRecord,
    interaction: Interaction,
    pack: VerticalPack,
    subject_id: str,
) -> list[InvestigationFinding]:
    if pack.id == "lender_disclosure_audit":
        return _lender_numeric_findings(interaction, subject_id)
    if pack.id == "staffing_procurement":
        return _staffing_numeric_findings(interaction, subject_id)
    return []


def _lender_numeric_findings(
    interaction: Interaction,
    subject_id: str,
) -> list[InvestigationFinding]:
    body = interaction.body
    disbursed = _first_number(
        body,
        [
            r"(?:receives|amount disbursed|proceeds(?: are)?|funded amount(?: is)?)\s*\$([\d,]+(?:\.\d+)?)",
            r"hypothetical\s*\$([\d,]+(?:\.\d+)?)",
        ],
    )
    finance_charge = _first_number(body, [r"finance charge(?: is| of)?\s*\$([\d,]+(?:\.\d+)?)"])
    total_repayment = _first_number(
        body,
        [r"(?:total repayment|total of payments)(?: is| of)?\s*\$([\d,]+(?:\.\d+)?)"],
    )
    term_days = _first_number(
        body,
        [r"(?:hypothetical\s*\$[\d,.]+,?\s*)?(\d+(?:\.\d+)?)\s*[- ]?day", r"after\s+(\d+)\s+days"],
    )
    reported_apr = _first_number(
        body,
        [r"(?:apr|annual percentage rate)(?: is| of)?\s*([\d,]+(?:\.\d+)?)\s*%"],
    )
    findings: list[InvestigationFinding] = []
    if disbursed and finance_charge is not None and term_days:
        simple_annualized = round((finance_charge / disbursed) * (365.0 / term_days) * 100.0, 2)
        findings.append(
            InvestigationFinding(
                rule_id="derived_simple_annualized_cost",
                kind=FindingKind.DERIVED_METRIC,
                severity=Severity.INFO,
                title="Simple annualized cost estimate",
                summary=(
                    "A deterministic simple annualized cost estimate was calculated for comparison only; "
                    "it is not a legal Truth in Lending APR calculation."
                ),
                subject_id=subject_id,
                value={
                    "amount_disbursed": disbursed,
                    "finance_charge": finance_charge,
                    "term_days": term_days,
                    "simple_annualized_percent": simple_annualized,
                    "reported_apr_percent": reported_apr,
                },
                evidence_ids=[interaction.evidence_id],
                confidence=0.9,
                requires_human_review=False,
            )
        )
        if reported_apr is not None and abs(reported_apr - simple_annualized) > max(5.0, reported_apr * 0.05):
            findings.append(
                InvestigationFinding(
                    rule_id="reported_apr_differs_from_simple_estimate",
                    kind=FindingKind.NUMERIC_INCONSISTENCY,
                    severity=Severity.HIGH,
                    title="Reported APR differs from simple annualized estimate",
                    summary=(
                        "The reported APR differs materially from a simple annualized estimate. This can have "
                        "legitimate calculation causes and requires document-level review."
                    ),
                    subject_id=subject_id,
                    value={"reported_apr_percent": reported_apr, "simple_estimate_percent": simple_annualized},
                    evidence_ids=[interaction.evidence_id],
                    confidence=0.82,
                    requires_human_review=True,
                )
            )
    if disbursed is not None and finance_charge is not None and total_repayment is not None:
        expected_total = round(disbursed + finance_charge, 2)
        if abs(expected_total - total_repayment) > 1.0:
            findings.append(
                InvestigationFinding(
                    rule_id="repayment_arithmetic_mismatch",
                    kind=FindingKind.NUMERIC_INCONSISTENCY,
                    severity=Severity.HIGH,
                    title="Repayment arithmetic requires clarification",
                    summary=(
                        "The stated amount disbursed plus finance charge does not equal the stated total repayment."
                    ),
                    subject_id=subject_id,
                    value={"expected_total": expected_total, "reported_total": total_repayment},
                    evidence_ids=[interaction.evidence_id],
                    confidence=0.95,
                    requires_human_review=True,
                )
            )
    return findings


def _staffing_numeric_findings(
    interaction: Interaction,
    subject_id: str,
) -> list[InvestigationFinding]:
    body = interaction.body
    bill_rate = _first_number(body, [r"bill rate(?: is| of)?\s*\$([\d,]+(?:\.\d+)?)"])
    pay_rate = _first_number(body, [r"(?:worker |candidate )?pay rate(?: is| of)?\s*\$([\d,]+(?:\.\d+)?)"])
    stated_markup = _first_number(body, [r"([\d,]+(?:\.\d+)?)\s*%\s*(?:markup|mark-up)"])
    if bill_rate is None or pay_rate in (None, 0):
        return []
    implied_markup = round(((bill_rate - pay_rate) / pay_rate) * 100.0, 2)
    findings = [
        InvestigationFinding(
            rule_id="derived_staffing_markup",
            kind=FindingKind.DERIVED_METRIC,
            severity=Severity.INFO,
            title="Implied staffing markup",
            summary="The implied markup was calculated from the stated client bill rate and worker pay rate.",
            subject_id=subject_id,
            value={
                "bill_rate": bill_rate,
                "pay_rate": pay_rate,
                "implied_markup_percent": implied_markup,
                "reported_markup_percent": stated_markup,
            },
            evidence_ids=[interaction.evidence_id],
            confidence=0.95,
            requires_human_review=False,
        )
    ]
    if stated_markup is not None and abs(stated_markup - implied_markup) > 1.5:
        findings.append(
            InvestigationFinding(
                rule_id="staffing_markup_mismatch",
                kind=FindingKind.NUMERIC_INCONSISTENCY,
                severity=Severity.MEDIUM,
                title="Stated and implied staffing markup differ",
                summary=(
                    "The stated markup differs from the markup implied by bill and pay rates; included costs or "
                    "the pricing basis may need clarification."
                ),
                subject_id=subject_id,
                value={"reported_markup_percent": stated_markup, "implied_markup_percent": implied_markup},
                evidence_ids=[interaction.evidence_id],
                confidence=0.9,
                requires_human_review=True,
            )
        )
    return findings


def _first_number(body: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, body, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def _get_nested(payload: dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _coverage_kind(missing: list[str]) -> FindingKind:
    return FindingKind.DISCLOSURE_GAP if missing else FindingKind.POSITIVE_CONTROL


def _coverage_severity(missing: list[str]) -> Severity:
    return Severity.MEDIUM if missing else Severity.INFO


def _deduplicate_findings(findings: list[InvestigationFinding]) -> list[InvestigationFinding]:
    result: list[InvestigationFinding] = []
    seen: set[str] = set()
    for finding in findings:
        key = stable_key(finding.rule_id, finding.subject_id, json.dumps(finding.value, default=str, sort_keys=True))
        if key not in seen:
            result.append(finding)
            seen.add(key)
    return result


def _render_value(value: object) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)
