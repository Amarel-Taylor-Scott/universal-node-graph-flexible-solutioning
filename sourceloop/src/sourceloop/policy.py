"""Deterministic policy checks for external side effects."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .config import Settings
from .domain import ActionProposal, ActionStatus, ActionType, CaseKind, CaseRecord
from .repository import Repository

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_DISCLOSURE_RE = re.compile(r"\b(automated|ai-assisted|assisted by|automation-assisted)\b", re.IGNORECASE)
_DECEPTION_RE = re.compile(
    r"\b(pretend to be|impersonat(?:e|ing)|fake constituent|fake customer|do not disclose automation|"
    r"hide the requester|fabricated identity|astroturf)\b",
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
        if not action.idempotency_key:
            reasons.append("The action does not have an idempotency key.")
        if action.followup and not action.thread_id:
            reasons.append("A follow-up must be attached to an existing SourceLoop thread.")
        if action.followup and not action.in_reply_to:
            reasons.append("A follow-up must identify the provider message it replies to.")

        active_targets = {
            candidate.recipient
            for candidate in case.actions
            if candidate.status not in {ActionStatus.REJECTED, ActionStatus.BLOCKED}
        }
        if len(active_targets) > case.max_contacts:
            reasons.append("The case exceeds its maximum number of external contacts.")
        if case.kind is CaseKind.CIVIC_INTELLIGENCE and case.max_contacts > 3:
            reasons.append("Civic intelligence cases may not configure more than three contacts in Phase 1.")

        followups = sum(1 for candidate in case.actions if candidate.followup)
        if followups > case.max_followups * max(1, len(case.contacts)):
            reasons.append("The case exceeds its bounded follow-up allowance.")

        if self.settings.email_mode == "smtp" and not self.settings.allow_external_send:
            reasons.append("SMTP mode is configured, but external sending is not explicitly enabled.")
        if self.settings.email_mode == "smtp" and action.recipient.endswith((".test", ".invalid")):
            # Local GreenMail uses .local so the sandbox can exercise the real SMTP/IMAP loop.
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
                "max_contacts": case.max_contacts,
                "max_followups": case.max_followups,
                "suppressed": self.repository.is_suppressed(action.recipient),
            },
        )
