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
from .domain import ApprovalRequest, CaseCreate, CaseKind, InvestigationMode
from .evidence import EvidenceStore
from .extended_engine import InvestigativeSourceLoopEngine
from .mailbox import MailboxService
from .reporting import build_case_report, case_report_csv
from .repository import Repository
from .worker import SourceLoopWorker, worker_is_healthy

DEMO_KINDS = [
    "facilities_quote",
    "bpo_quote",
    "local_services_quote",
    "staffing_procurement",
    "civic_intelligence",
    "data_verification",
    "employment_agency_audit",
    "lender_disclosure_audit",
    "contractor_license_audit",
    "informal_business_verification",
    "franchise_service_audit",
]


def main() -> None:
    parser = argparse.ArgumentParser(prog="sourceloop")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the FastAPI service")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", default=8000, type=int)
    serve.add_argument("--reload", action="store_true")

    demo = subparsers.add_parser("demo", help="Run a deterministic end-to-end demo")
    demo.add_argument("--kind", choices=DEMO_KINDS, default="facilities_quote")

    worker = subparsers.add_parser("worker", help="Run the long-lived IMAP mailbox worker")
    worker.add_argument("--once", action="store_true", help="Run one mailbox cycle and exit")

    subparsers.add_parser("mailbox-sync", help="Fetch and process one batch of inbound IMAP messages")
    subparsers.add_parser("doctor", help="Check database, evidence volume, and sanitized runtime configuration")
    subparsers.add_parser("list-packs", help="List installed vertical and investigation packs")

    report = subparsers.add_parser("report", help="Render an evidence-linked case report")
    report.add_argument("--case-id", required=True)
    report.add_argument("--format", choices=["json", "csv"], default="json")

    case_file = subparsers.add_parser("case-file", help="Create and run a case from a JSON request file")
    case_file.add_argument("--file", required=True, type=Path)

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
        engine = InvestigativeSourceLoopEngine(settings, repository=repository)
        evidence = EvidenceStore(settings.evidence_dir, settings.attachment_max_bytes)
        result = MailboxService(settings, repository, engine, evidence).sync_once()
        print(result.model_dump_json(indent=2))
        return
    if args.command == "doctor":
        _doctor(settings)
        return
    if args.command == "list-packs":
        engine = InvestigativeSourceLoopEngine(settings)
        print(
            json.dumps(
                [
                    {
                        "id": pack.id,
                        "name": pack.name,
                        "case_kind": pack.case_kind.value,
                        "mode": pack.investigation_mode.value if pack.investigation_mode else None,
                        "risk_tier": pack.risk_tier.value,
                        "institutional_only": pack.institutional_only,
                    }
                    for pack in engine.packs.list()
                ],
                indent=2,
            )
        )
        return
    if args.command == "report":
        engine = InvestigativeSourceLoopEngine(settings)
        case = engine.get_case(args.case_id)
        pack = engine.packs.get(case.pack)
        if args.format == "csv":
            print(case_report_csv(case, pack), end="")
        else:
            print(json.dumps(build_case_report(case, pack), indent=2, default=str))
        return
    if args.command == "case-file":
        payload = json.loads(args.file.read_text(encoding="utf-8"))
        request = CaseCreate.model_validate(payload)
        engine = InvestigativeSourceLoopEngine(settings)
        case = engine.create_case(request)
        case = engine.run_until_blocked(case.id)
        print(case.model_dump_json(indent=2))
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
    engine = InvestigativeSourceLoopEngine(settings, repository=repository)
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
        "installed_packs": len(engine.packs.list()),
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
    engine = InvestigativeSourceLoopEngine(Settings.from_env())
    request = _demo_request(kind)

    case = engine.create_case(request)
    case = engine.run_until_blocked(case.id)
    for action in case.actions:
        if action.status.value == "pending":
            case = engine.approve_action(case.id, action.id, ApprovalRequest(approver="demo-operator"))
    if any(action.status.value == "approved" for action in case.actions):
        case = engine.dispatch_approved(case.id)
    case = engine.simulate_demo_replies(case.id)

    # A partial demo response may create a clarification. Approve and dispatch it, then
    # inject the next pack reply so the bounded conversation is represented end to end.
    for _ in range(3):
        pending = [action for action in case.actions if action.status.value == "pending"]
        if not pending:
            break
        for action in pending:
            case = engine.approve_action(case.id, action.id, ApprovalRequest(approver="demo-operator"))
        case = engine.dispatch_approved(case.id)
        case = engine.simulate_demo_replies(case.id)

    report = build_case_report(case, engine.packs.get(case.pack))
    summary = {
        "case_id": case.id,
        "title": case.title,
        "pack": case.pack,
        "risk_tier": case.risk_tier.value,
        "status": case.status.value,
        "stage": case.stage.value,
        "agent_runs": len(case.agent_runs),
        "actions": len(case.actions),
        "interactions": len(case.interactions),
        "claims": len(case.claims),
        "findings": len(case.findings),
        "quotes": len(case.quotes),
        "report": report,
    }
    print(json.dumps(summary, indent=2, default=str))


def _demo_request(kind: str) -> CaseCreate:
    common = {
        "requester_name": "Demo Research Team",
        "requester_email": "researcher@example.test",
        "demo": True,
    }
    if kind == "civic_intelligence":
        return CaseCreate(
            title="Municipal civic organization routing",
            kind=CaseKind.CIVIC_INTELLIGENCE,
            pack="civic_intelligence",
            objective="Identify the public organization, inquiry route, and public meeting information.",
            requirements={"geography": "Demonstration municipality", "purpose": "public information"},
            **common,
        )
    if kind == "data_verification":
        return CaseCreate(
            title="Verify a public business record",
            kind=CaseKind.DATA_VERIFICATION,
            pack="business_record_verification",
            objective="Confirm whether the listed business identity and public contact route remain active.",
            requirements={"record_type": "public business location", "jurisdiction": "Pennsylvania"},
            governance_acknowledgements={},
            investigation_mode=InvestigationMode.RECORD_VERIFICATION,
            **common,
        )
    pack = kind
    if kind in {"facilities_quote", "bpo_quote", "local_services_quote", "staffing_procurement"}:
        requirements = {
            "facilities_quote": {
                "service": "preventive commercial building service",
                "property_count": 5,
                "response_window": "two weeks",
                "minimum_quotes": 2,
            },
            "bpo_quote": {
                "service": "bilingual customer support",
                "seats": 30,
                "coverage": "24x7",
                "start_window": "45 days",
                "minimum_quotes": 2,
            },
            "local_services_quote": {
                "service": "weekly lawn mowing",
                "lawn_area_sqft": 9500,
                "scope": ["mowing", "edging", "blowing"],
                "geography": "Demonstration market",
                "minimum_quotes": 2,
            },
            "staffing_procurement": {
                "roles": "warehouse associates",
                "workers": 20,
                "geography": "Demonstration market",
                "shift": "second shift",
                "start_window": "three weeks",
                "minimum_quotes": 2,
            },
        }[kind]
        return CaseCreate(
            title=f"{kind.replace('_', ' ').title()} demonstration",
            kind=CaseKind.QUOTE_INTELLIGENCE,
            pack=pack,
            objective="Obtain comparable, non-binding pricing, availability, terms, and exclusions.",
            requirements=requirements,
            governance_acknowledgements={"authorized_requester": True, "research_only": True},
            investigation_mode=InvestigationMode.QUOTE_PROBE,
            **common,
        )

    acknowledgements = {
        "authorized_requester": True,
        "research_only": True,
        "public_business_channels_only": True,
        "no_fake_persona": True,
        "no_sensitive_personal_data": True,
        "no_application": True,
        "legal_review": True,
        "institutional_authority": True,
        "no_residential_mapping": True,
    }
    investigation_requirements = {
        "employment_agency_audit": {
            "geography": "Demonstration market",
            "scenario": "Warehouse associate public job inquiry",
            "research_purpose": "employment-agency practice comparison",
        },
        "lender_disclosure_audit": {
            "geography": "Demonstration State",
            "scenario": "$300 principal for 14 days",
            "research_purpose": "institutional public disclosure audit",
        },
        "contractor_license_audit": {
            "geography": "Demonstration State",
            "trade": "commercial roofing",
            "research_purpose": "public authorization and practice verification",
        },
        "informal_business_verification": {
            "geography": "Demonstration market",
            "service": "lawn and grounds maintenance",
            "research_purpose": "business identity and service verification",
        },
        "franchise_service_audit": {
            "brand_or_category": "hotel",
            "geography": "Demonstration market",
            "standardized_scenario": "One-night public rate and fee inquiry",
            "research_purpose": "location-level price and policy comparison",
        },
    }[kind]
    return CaseCreate(
        title=f"{kind.replace('_', ' ').title()} demonstration",
        kind=CaseKind.MARKET_INVESTIGATION,
        pack=pack,
        objective="Collect standardized direct-source representations for human-reviewed market analysis.",
        requirements=investigation_requirements,
        governance_acknowledgements=acknowledgements,
        **common,
    )


if __name__ == "__main__":
    main()
