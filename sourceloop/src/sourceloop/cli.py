"""SourceLoop command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from .config import Settings
from .domain import ApprovalRequest, CaseCreate, CaseKind
from .engine import SourceLoopEngine
from .evidence import EvidenceStore
from .mailbox import MailboxService
from .repository import Repository
from .worker import SourceLoopWorker, worker_is_healthy


def main() -> None:
    parser = argparse.ArgumentParser(prog="sourceloop")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the FastAPI service")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", default=8000, type=int)
    serve.add_argument("--reload", action="store_true")

    demo = subparsers.add_parser("demo", help="Run a deterministic end-to-end demo")
    demo.add_argument(
        "--kind",
        choices=["facilities_quote", "bpo_quote", "civic_intelligence", "data_verification"],
        default="facilities_quote",
    )

    worker = subparsers.add_parser("worker", help="Run the long-lived IMAP mailbox worker")
    worker.add_argument("--once", action="store_true", help="Run one mailbox cycle and exit")

    subparsers.add_parser("mailbox-sync", help="Fetch and process one batch of inbound IMAP messages")
    subparsers.add_parser("doctor", help="Check database, evidence volume, and sanitized runtime configuration")

    worker_health = subparsers.add_parser("worker-health", help="Check the persisted mailbox-worker heartbeat")
    worker_health.add_argument("--max-age", type=int, default=120)

    sandbox_reply = subparsers.add_parser(
        "sandbox-reply",
        help="Send a correlated reply through the configured SMTP sandbox",
    )
    sandbox_reply.add_argument("--case-id", required=True)
    sandbox_reply.add_argument("--from-address", default="supplier1@supplier.local")
    sandbox_reply.add_argument("--body", required=True)

    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("sourceloop.api:app", host=args.host, port=args.port, reload=args.reload)
        return
    if args.command == "demo":
        _run_demo(args.kind)
        return

    settings = Settings.from_env()
    if args.command == "worker":
        instance = SourceLoopWorker(settings)
        if args.once:
            print(instance.sync_once().model_dump_json(indent=2))
        else:
            instance.run_forever()
        return
    if args.command == "mailbox-sync":
        repository = Repository(settings.database_url)
        engine = SourceLoopEngine(settings, repository=repository)
        evidence = EvidenceStore(settings.evidence_dir, settings.attachment_max_bytes)
        result = MailboxService(settings, repository, engine, evidence).sync_once()
        print(result.model_dump_json(indent=2))
        return
    if args.command == "doctor":
        _doctor(settings)
        return
    if args.command == "worker-health":
        healthy, message = worker_is_healthy(Repository(settings.database_url), settings.worker_id, args.max_age)
        print(message)
        raise SystemExit(0 if healthy else 1)
    if args.command == "sandbox-reply":
        _send_sandbox_reply(settings, args.case_id, args.from_address, args.body)
        return


def _doctor(settings: Settings) -> None:
    repository = Repository(settings.database_url)
    repository.ping()
    evidence = Path(settings.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=True)
    probe = evidence / ".sourceloop-write-probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    payload = {
        "status": "ok",
        "database": "reachable",
        "evidence_dir": str(evidence),
        "email_mode": settings.email_mode,
        "external_send_enabled": settings.allow_external_send,
        "smtp_host_configured": bool(settings.smtp_host),
        "mailbox_mode": settings.mailbox_mode,
        "imap_host_configured": bool(settings.imap_host),
        "agent_runtime": settings.agent_runtime,
        "environment": settings.environment,
    }
    print(json.dumps(payload, indent=2))


def _send_sandbox_reply(settings: Settings, case_id: str, from_address: str, body: str) -> None:
    if settings.environment not in {"development", "test", "sandbox"}:
        raise RuntimeError("sandbox-reply is disabled outside development/test/sandbox environments")
    if settings.email_mode != "smtp" or not settings.smtp_host:
        raise RuntimeError("sandbox-reply requires configured SMTP mode")
    repository = Repository(settings.database_url)
    messages = [row for row in repository.list_outbox() if row.case_id == case_id]
    if not messages:
        raise RuntimeError(f"No outbound messages exist for case {case_id}")
    outbound = messages[0]
    message = EmailMessage()
    message["From"] = from_address
    message["To"] = settings.effective_reply_to
    message["Subject"] = f"Re: {outbound.subject}"
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(idstring=f"sandbox.reply.{case_id}")
    if outbound.provider_message_id:
        message["In-Reply-To"] = outbound.provider_message_id
        message["References"] = outbound.provider_message_id
    message.set_content(body)

    if settings.smtp_ssl:
        client: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
            context=ssl.create_default_context(),
        )
    else:
        client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)
    with client:
        if settings.smtp_starttls:
            client.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        refused = client.send_message(message)
        if refused:
            raise RuntimeError(f"SMTP refused recipient(s): {sorted(refused)}")
    print(json.dumps({"status": "sent", "case_id": case_id, "message_id": message["Message-ID"]}, indent=2))


def _run_demo(kind: str) -> None:
    os.environ.setdefault("SOURCELOOP_DATABASE_URL", "sqlite:///./sourceloop-demo.db")
    os.environ.setdefault("SOURCELOOP_EMAIL_MODE", "dry_run")
    os.environ.setdefault("SOURCELOOP_ALLOW_EXTERNAL_SEND", "false")
    os.environ.setdefault("SOURCELOOP_AGENT_RUNTIME", "mock")
    os.environ.setdefault("SOURCELOOP_EVIDENCE_DIR", "./.sourceloop-evidence")
    engine = SourceLoopEngine(Settings.from_env())

    if kind == "civic_intelligence":
        request = CaseCreate(
            title="Municipal civic organization routing",
            kind=CaseKind.CIVIC_INTELLIGENCE,
            pack="civic_intelligence",
            objective=(
                "Identify the public organization that serves the municipality, the appropriate public inquiry "
                "route, and current public meeting information."
            ),
            requester_name="Demo Requester",
            demo=True,
            requirements={"geography": "Demonstration municipality", "purpose": "public information"},
        )
    elif kind == "data_verification":
        request = CaseCreate(
            title="Verify a public business record",
            kind=CaseKind.DATA_VERIFICATION,
            objective="Confirm whether the listed business location and public contact route remain active.",
            requester_name="Demo Requester",
            demo=True,
            requirements={"record_type": "public business location"},
        )
    else:
        pack = "bpo_quote" if kind == "bpo_quote" else "facilities_quote"
        title = "Bilingual support BPO quote" if kind == "bpo_quote" else "Commercial facilities service quote"
        requirements = (
            {
                "service": "bilingual customer support",
                "seats": 30,
                "coverage": "24x7",
                "start_window": "45 days",
                "minimum_quotes": 2,
            }
            if kind == "bpo_quote"
            else {
                "service": "preventive commercial building service",
                "property_count": 5,
                "response_window": "two weeks",
                "minimum_quotes": 2,
            }
        )
        request = CaseCreate(
            title=title,
            kind=CaseKind.QUOTE_INTELLIGENCE,
            pack=pack,
            objective="Obtain comparable, non-binding budgetary quotes from a small qualified respondent panel.",
            requester_name="Demo Procurement Team",
            demo=True,
            requirements=requirements,
        )

    case = engine.create_case(request)
    case = engine.run_until_blocked(case.id)
    for action in case.actions:
        case = engine.approve_action(case.id, action.id, ApprovalRequest(approver="demo-operator"))
    case = engine.dispatch_approved(case.id)
    case = engine.simulate_demo_replies(case.id)

    summary = {
        "case_id": case.id,
        "title": case.title,
        "status": case.status.value,
        "stage": case.stage.value,
        "agent_runs": len(case.agent_runs),
        "actions": len(case.actions),
        "interactions": len(case.interactions),
        "claims": len(case.claims),
        "quotes": [
            {
                "supplier": quote.supplier_name,
                "line_items": len(quote.line_items),
                "normalized_total": quote.normalized_total,
                "unresolved_fields": quote.unresolved_fields,
            }
            for quote in case.quotes
        ],
        "outbox": [record.model_dump(mode="json") for record in engine.repository.list_outbox()],
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
