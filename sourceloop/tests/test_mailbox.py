from __future__ import annotations

from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path

from sourceloop.domain import ApprovalRequest, CaseCreate, CaseKind
from sourceloop.engine import SourceLoopEngine
from sourceloop.evidence import EvidenceStore
from sourceloop.mailbox import MailboxService, RawMailboxMessage, parse_email


class FakeMailbox:
    def __init__(self, messages: list[RawMailboxMessage]) -> None:
        self.messages = messages
        self.seen: list[str] = []

    def fetch_messages(self) -> list[RawMailboxMessage]:
        return self.messages

    def mark_seen(self, uid: str) -> None:
        self.seen.append(uid)

    def close(self) -> None:
        return None


def _raw_reply(*, message_id: str, in_reply_to: str, subject: str, sender: str, body: str) -> bytes:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = "research@example.test"
    message["Subject"] = subject
    message["Message-ID"] = message_id
    message["In-Reply-To"] = in_reply_to
    message["References"] = in_reply_to
    message.set_content(body)
    message.add_attachment(b"sample", maintype="application", subtype="octet-stream", filename="quote.bin")
    return message.as_bytes(policy=SMTP)


def test_parse_email_extracts_text_headers_and_attachment() -> None:
    raw = _raw_reply(
        message_id="<reply@example.test>",
        in_reply_to="<outbound@example.test>",
        subject="Re: [SL:ABCDEF123456] Quote",
        sender="Supplier <supplier@example.test>",
        body="Pricing is $10 per hour.",
    )
    parsed = parse_email(raw)
    assert parsed.sender == "supplier@example.test"
    assert parsed.message_id == "<reply@example.test>"
    assert parsed.in_reply_to == "<outbound@example.test>"
    assert "Pricing is $10" in parsed.body
    assert parsed.attachments[0].filename == "quote.bin"


def test_mailbox_sync_correlates_in_reply_to_and_is_idempotent(
    engine: SourceLoopEngine,
    settings,
    tmp_path: Path,
) -> None:
    case = engine.create_case(
        CaseCreate(
            title="Mailbox quote",
            kind=CaseKind.QUOTE_INTELLIGENCE,
            pack="facilities_quote",
            objective="Obtain two comparable quotes.",
            requester_name="Mailbox Buyer",
            demo=True,
            requirements={"service": "maintenance", "minimum_quotes": 2},
        )
    )
    case = engine.run_until_blocked(case.id)
    for action in case.actions:
        case = engine.approve_action(case.id, action.id, ApprovalRequest(approver="mailbox-test"))
    case = engine.dispatch_approved(case.id)
    outbound = engine.repository.list_outbox()[0]
    raw = _raw_reply(
        message_id="<mailbox-reply@example.test>",
        in_reply_to=outbound.provider_message_id or "",
        subject=f"Re: {outbound.subject}",
        sender=outbound.recipient,
        body=(
            "$125 per visit. Taxes are excluded. Payment terms are Net 30. "
            "Scope is confirmed. Valid through 2026-10-15."
        ),
    )
    mailbox = FakeMailbox([RawMailboxMessage(uid="1", raw=raw)])
    evidence = EvidenceStore(tmp_path / "evidence", settings.attachment_max_bytes)
    service = MailboxService(settings, engine.repository, engine, evidence)

    first = service.sync_once(mailbox)
    second = service.sync_once(mailbox)

    assert first.processed == 1
    assert second.duplicates == 1
    reloaded = engine.get_case(case.id)
    inbound = [item for item in reloaded.interactions if item.direction.value == "inbound"]
    assert len(inbound) == 1
    assert inbound[0].raw_evidence_path
    assert inbound[0].attachments[0].status == "stored_quarantined"
    assert mailbox.seen == ["1", "1"]
