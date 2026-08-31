"""Approval-aware dry-run and SMTP gateways with durable idempotent reservations."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Protocol

from .config import Settings
from .domain import ActionProposal, CaseRecord, OutboxRecord, new_id, stable_key
from .policy import PolicyEngine
from .repository import Repository


class MailGateway(Protocol):
    def send(self, case: CaseRecord, action: ActionProposal) -> OutboxRecord: ...


class BaseMailGateway:
    def __init__(self, settings: Settings, repository: Repository, policy: PolicyEngine) -> None:
        self.settings = settings
        self.repository = repository
        self.policy = policy

    def _reserve(self, case: CaseRecord, action: ActionProposal, status: str) -> tuple[OutboxRecord, bool]:
        decision = self.policy.evaluate(case, action)
        action.policy_receipt = decision.model_dump(mode="json")
        if not decision.allowed:
            raise PermissionError("; ".join(decision.reasons))
        domain = self.settings.sender_email.partition("@")[2] or None
        provider_message_id = make_msgid(
            idstring=f"sourceloop.{case.id}.{action.id}",
            domain=domain,
        )
        thread_id = action.thread_id or f"thread_{stable_key(case.id, action.recipient)[:20]}"
        record = OutboxRecord(
            id=new_id("message"),
            case_id=case.id,
            action_id=action.id,
            idempotency_key=action.idempotency_key,
            recipient=action.recipient,
            sender=self.settings.sender_email,
            subject=action.subject,
            body=action.body,
            status=status,
            provider_message_id=provider_message_id,
            thread_id=thread_id,
            in_reply_to=action.in_reply_to,
            references=action.references,
        )
        return self.repository.reserve_outbox(record)


class DryRunMailGateway(BaseMailGateway):
    """Captures the exact message in the outbox without network delivery."""

    def send(self, case: CaseRecord, action: ActionProposal) -> OutboxRecord:
        record, _ = self._reserve(case, action, status="captured")
        return record


class SmtpMailGateway(BaseMailGateway):
    """SMTP transport guarded by approval, policy, suppression, and a two-key send gate."""

    def send(self, case: CaseRecord, action: ActionProposal) -> OutboxRecord:
        record, created = self._reserve(case, action, status="reserved")
        if not created:
            if record.status in {"sent", "captured"}:
                return record
            raise RuntimeError(
                f"Message reservation already exists with status {record.status!r}; "
                "automatic resend is blocked to prevent duplicates"
            )

        message = EmailMessage()
        message["From"] = f"{self.settings.sender_name} <{self.settings.sender_email}>"
        message["To"] = action.recipient
        message["Reply-To"] = action.reply_to or self.settings.effective_reply_to
        message["Subject"] = action.subject
        message["Date"] = formatdate(localtime=False)
        message["Message-ID"] = record.provider_message_id
        message["X-SourceLoop-Case-ID"] = case.id
        message["X-SourceLoop-Action-ID"] = action.id
        message["X-SourceLoop-Thread-ID"] = record.thread_id
        if action.in_reply_to:
            message["In-Reply-To"] = action.in_reply_to
        if action.references:
            message["References"] = " ".join(action.references)
        message.set_content(action.body)

        try:
            if self.settings.smtp_ssl:
                client: smtplib.SMTP = smtplib.SMTP_SSL(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=self.settings.smtp_timeout_seconds,
                    context=ssl.create_default_context(),
                )
            else:
                client = smtplib.SMTP(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=self.settings.smtp_timeout_seconds,
                )
            with client:
                if self.settings.smtp_starttls:
                    client.starttls(context=ssl.create_default_context())
                if self.settings.smtp_username:
                    client.login(self.settings.smtp_username, self.settings.smtp_password)
                refused = client.send_message(message)
                if refused:
                    raise RuntimeError(f"SMTP refused one or more recipients: {sorted(refused)}")
            return self.repository.update_outbox_status(
                action.idempotency_key,
                "sent",
                provider_message_id=record.provider_message_id,
            )
        except Exception as exc:
            self.repository.update_outbox_status(
                action.idempotency_key,
                "delivery_unknown",
                provider_message_id=record.provider_message_id,
                last_error=str(exc),
            )
            raise


def build_mail_gateway(settings: Settings, repository: Repository, policy: PolicyEngine) -> MailGateway:
    if settings.email_mode == "smtp":
        return SmtpMailGateway(settings, repository, policy)
    return DryRunMailGateway(settings, repository, policy)
