"""Deterministic policy checks for external side effects."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from .config import Settings
from .domain import ActionProposal, ActionStatus, ActionType, CaseKind, CaseRecord, RiskTier
from .repository import Repository

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_DISCLOSURE_RE = re.compile(r"\b(automated|ai-assisted|assisted by|automation-assisted)\b", re.IGNORECASE)
_DECEPTION_RE = re.compile(
    r"\b(pretend to be|impersonat(?:e|ing)|fake constituent|fake customer|fake jobseeker|"
    r"do not disclose automation|hide the requester|fabricated identity|astroturf|secret shopper identity)\b",
    re.IGNORECASE,
)
_SENSITIVE_REQUEST_RE = re.compile(
    r"\b(?:send|provide|share|upload|enter)\b.{0,50}\b(?:social security number|ssn|bank account number|"
    r"routing number|date of birth|password|login credentials|one-time code|credit card number)\b",
    re.IGNORECASE | re.DOTALL,
)
_TRANSACTION_RE = re.compile(
    r"\b(?:accept the loan|submit the application|authorize a hard credit pull|sign the contract|place the order|"
    r"send the deposit|transfer the funds|purchase the service)\b",
    re.IGNORECASE,
)


class PolicyDecision(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    controls: dict[str, object] = Field(default_factory=dict)


class PolicyEngine:
    """Evaluates a proposal and re-evaluates it immediately before dispatch."""

    def __init__(self, settings: Settings, repository: Repository) -> None:
        self.settings = settings
        self.repository = repository

    def evaluate(self, case: CaseRecord, action: ActionProposal) -> PolicyDecision:
        reasons: list[str] = []
        governance = case.governance or {}
        acknowledgements = governance.get("acknowledgements", {})

        if action.action_type is not ActionType.SEND_EMAIL:
            reasons.append("Only typed send_email actions are supported by this gateway.")
        if action.approval_required and action.status is not ActionStatus.APPROVED:
            reasons.append("The action has not received the required approval.")
        if not _EMAIL_RE.match(action.recipient):
            reasons.append("The recipient endpoint is not a syntactically valid email address.")
        if self.repository.is_suppressed(action.recipient):
            reasons.append("The recipient endpoint is on the suppression list.")
        if not case.requester_name.strip():
            reasons.append("A truthful requester identity is required.")
        if not case.objective.strip():
            reasons.append("The case purpose is missing.")
        if not action.subject.strip() or len(action.subject) > 250:
            reasons.append("The subject must be present and no longer than 250 characters.")
        if not action.body.strip() or len(action.body) > 100_000:
            reasons.append("The message body is empty or exceeds the safety limit.")
        if not _DISCLOSURE_RE.search(action.body):
            reasons.append("The message does not disclose automated or AI assistance.")
        if _DECEPTION_RE.search(action.body):
            reasons.append("The message contains a prohibited deception or impersonation instruction.")
        if _SENSITIVE_REQUEST_RE.search(action.body):
            reasons.append("The message requests sensitive personal or authentication information.")
        if _TRANSACTION_RE.search(action.body):
            reasons.append("The message attempts an application, purchase, contract acceptance, or funds transfer.")
        if not action.idempotency_key:
            reasons.append("The action does not have an idempotency key.")
        if action.followup and not action.thread_id:
            reasons.append("A follow-up must be attached to an existing SourceLoop thread.")
        if action.followup and not action.in_reply_to:
            reasons.append("A follow-up must identify the provider message it replies to.")

        contact = next((item for item in case.contacts if item.endpoint == action.recipient), None)
        if contact is None:
            reasons.append("The recipient is not an approved contact route on this case.")
        else:
            if contact.channel not in set(governance.get("allowed_channels", ["email"])):
                reasons.append("The contact channel is not allowed by the case governance profile.")
            if case.risk_tier in {RiskTier.ELEVATED, RiskTier.RESTRICTED} and not contact.source_public:
                reasons.append("Elevated and restricted investigations require a public or customer-authorized endpoint.")
            if case.risk_tier is RiskTier.RESTRICTED and not contact.business_only:
                reasons.append("Restricted investigations may contact only organizational or professional endpoints.")
            if not contact.organization_name.strip():
                reasons.append("An accountable organization name is required for external investigation outreach.")

        active_targets = {
            candidate.recipient
            for candidate in case.actions
            if candidate.status not in {ActionStatus.REJECTED, ActionStatus.BLOCKED}
        }
        if len(active_targets) > case.max_contacts:
            reasons.append("The case exceeds its maximum number of external contacts.")
        if case.kind is CaseKind.CIVIC_INTELLIGENCE and case.max_contacts > 3:
            reasons.append("Civic intelligence cases may not configure more than three contacts.")
        if case.risk_tier is RiskTier.RESTRICTED and case.max_contacts > 3:
            reasons.append("Restricted investigations may not configure more than three contacts.")

        followups = sum(1 for candidate in case.actions if candidate.followup)
        if followups > case.max_followups * max(1, len(case.contacts)):
            reasons.append("The case exceeds its bounded follow-up allowance.")

        if case.risk_tier in {RiskTier.ELEVATED, RiskTier.RESTRICTED} and not (case.requester_email or "").strip():
            reasons.append("Elevated and restricted cases require a requester email address.")
        if governance.get("institutional_only") and not acknowledgements.get("institutional_authority"):
            reasons.append("The institutional-authority acknowledgement is missing.")
        for required in governance.get("required_acknowledgements", []):
            if not acknowledgements.get(required):
                reasons.append(f"Required governance acknowledgement is missing: {required}")

        request_text = json.dumps(
            {"objective": case.objective, "requirements": case.requirements, "message": action.body},
            default=str,
            sort_keys=True,
        )
        for pattern in governance.get("prohibited_request_patterns", []):
            try:
                if re.search(pattern, request_text, flags=re.IGNORECASE):
                    reasons.append(f"The case or message matches a prohibited request pattern: {pattern}")
            except re.error:
                reasons.append(f"The governance profile contains an invalid prohibited pattern: {pattern}")

        if self.settings.email_mode == "smtp" and not self.settings.allow_external_send:
            reasons.append("SMTP mode is configured, but external sending is not explicitly enabled.")
        if self.settings.email_mode == "smtp" and action.recipient.endswith((".test", ".invalid")):
            reasons.append("Reserved demonstration domains cannot be used for external SMTP delivery.")
        if self.settings.email_mode not in {"dry_run", "smtp"}:
            reasons.append("Unknown email mode; only dry_run and smtp are supported.")

        return PolicyDecision(
            allowed=not reasons,
            reasons=reasons,
            controls={
                "email_mode": self.settings.email_mode,
                "external_send_enabled": self.settings.allow_external_send,
                "approval_required": action.approval_required,
                "followup": action.followup,
                "risk_tier": case.risk_tier.value,
                "pack": case.pack,
                "max_contacts": case.max_contacts,
                "max_followups": case.max_followups,
                "suppressed": self.repository.is_suppressed(action.recipient),
                "public_contact_route": contact.source_public if contact else False,
                "business_only": contact.business_only if contact else False,
            },
        )
