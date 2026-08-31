from __future__ import annotations

from typing import Any

from sourceloop.config import Settings
from sourceloop.domain import ActionProposal, ActionStatus, CaseKind, CaseRecord, ContactRoute
from sourceloop.mail import SmtpMailGateway
from sourceloop.policy import PolicyEngine
from sourceloop.repository import Repository


class FakeSmtp:
    instances: list[FakeSmtp] = []

    def __init__(self, host: str, port: int, timeout: int, **_: Any) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.message: Any = None
        self.started_tls = False
        self.logged_in = False
        self.__class__.instances.append(self)

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def starttls(self, **_: Any) -> None:
        self.started_tls = True

    def login(self, _username: str, _password: str) -> None:
        self.logged_in = True

    def send_message(self, message: Any) -> dict[str, object]:
        self.message = message
        return {}


def test_smtp_gateway_sends_threaded_message(monkeypatch: Any, tmp_path: Any) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'mail.db'}",
        email_mode="smtp",
        allow_external_send=True,
        sender_name="SourceLoop Test",
        sender_email="research@example.com",
        reply_to_email="replies@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="research@example.com",
        smtp_password="secret",
        smtp_starttls=True,
        smtp_ssl=False,
        evidence_dir=str(tmp_path / "evidence"),
    )
    repository = Repository(settings.database_url)
    case = CaseRecord(
        title="Threading test",
        kind=CaseKind.QUOTE_INTELLIGENCE,
        objective="Request a transparent budgetary quote.",
        requester_name="Test Buyer",
        contacts=[
            ContactRoute(
                organization_name="Example Supplier",
                role_title="Quote desk",
                endpoint="supplier@example.com",
            )
        ],
    )
    action = ActionProposal(
        status=ActionStatus.APPROVED,
        recipient="supplier@example.com",
        subject="Re: Quote [SL:ABC123]",
        body="I am an automated assistant acting with Test Buyer's authorization.",
        idempotency_key="mail-test-key",
        thread_id="thread-123",
        in_reply_to="<prior@example.com>",
        references=["<root@example.com>", "<prior@example.com>"],
    )
    monkeypatch.setattr("sourceloop.mail.smtplib.SMTP", FakeSmtp)

    record = SmtpMailGateway(settings, repository, PolicyEngine(settings, repository)).send(case, action)

    assert record.status == "sent"
    assert record.thread_id == "thread-123"
    sent = FakeSmtp.instances[-1]
    assert sent.started_tls is True
    assert sent.logged_in is True
    assert sent.message["In-Reply-To"] == "<prior@example.com>"
    assert sent.message["References"] == "<root@example.com> <prior@example.com>"
    assert sent.message["X-SourceLoop-Case-ID"] == case.id
    assert sent.message["Reply-To"] == "replies@example.com"

    duplicate = SmtpMailGateway(settings, repository, PolicyEngine(settings, repository)).send(case, action)
    assert duplicate.id == record.id
    assert len(FakeSmtp.instances) == 1
