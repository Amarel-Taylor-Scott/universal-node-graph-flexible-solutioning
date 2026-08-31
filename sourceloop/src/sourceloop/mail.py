"""Approval-aware dry-run and SMTP mail gateways."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Protocol

from .config import Settings
from .domain import ActionProposal, CaseRecord, OutboxRecord, new_id
from .policy import PolicyEngine
from .repository import Repository


class MailGateway(Protocol):
    def send(self, case: CaseRecord, action: ActionProposal) -> OutboxRecord: ...


class BaseMailGateway:
    def __init__(self, settings: Settings, repository: Repository, policy: PolicyEngine) -> None:
        self.settings = settings
        self.repository = repository
        self.policy = policy

    def _authorized_record(self, case: CaseRecord, action: ActionProposal, status: str) -> OutboxRecord:
        decision = self.policy.evaluate(case, action)
        action.policy_receipt = decision.model_dump(mode="json")
        if not decision.allowed:
            raise PermissionError("; ".join(decision.reasons))
        existing = self.repository.get_outbox_by_key(action.idempotency_key)
        if existing:
            return existing
        return OutboxRecord(
            id=new_id("message"),
            case_id=case.id,
            action_id=action.id,
            idempotency_key=action.idempotency_key,
            recipient=action.recipient,
            sender=self.settings.sender_email,
            subject=action.subject,
            body=action.body,
            status=status,
        )


class DryRunMailGateway(BaseMailGateway):
    """Captures the exact message in the outbox without network delivery."""

    def send(self, case: CaseRecord, action: ActionProposal) -> OutboxRecord:
        record = self._authorized_record(case, action, status="captured")
        return self.repository.record_outbox(record)


class SmtpMailGateway(BaseMailGateway):
    """Minimal SMTP adapter, disabled unless the explicit two-key gate is satisfied."""

    def send(self, case: CaseRecord, action: ActionProposal) -> OutboxRecord:
        record = self._authorized_record(case, action, status="pending_delivery")
        existing = self.repository.get_outbox_by_key(action.idempotency_key)
        if existing:
            return existing
        if not self.settings.smtp_host:
            raise RuntimeError("SOURCELOOP_SMTP_HOST is required for SMTP delivery")

        message = EmailMessage()
        message["From"] = f"{self.settings.sender_name} <{self.settings.sender_email}>"
        message["To"] = action.recipient
        message["Subject"] = action.subject
        message.set_content(action.body)

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as client:
            if self.settings.smtp_starttls:
                client.starttls()
            if self.settings.smtp_username:
                client.login(self.settings.smtp_username, self.settings.smtp_password)
            refused = client.send_message(message)
            if refused:
                raise RuntimeError(f"SMTP refused one or more recipients: {sorted(refused)}")

        delivered = record.model_copy(update={"status": "sent", "provider_message_id": message.get("Message-ID")})
        return self.repository.record_outbox(delivered)


def build_mail_gateway(settings: Settings, repository: Repository, policy: PolicyEngine) -> MailGateway:
    if settings.email_mode == "smtp":
        return SmtpMailGateway(settings, repository, policy)
    return DryRunMailGateway(settings, repository, policy)
