"""SourceLoop command-line entry point."""

from __future__ import annotations

import argparse
import json
import os

from .config import Settings
from .domain import ApprovalRequest, CaseCreate, CaseKind
from .engine import SourceLoopEngine


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

    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("sourceloop.api:app", host=args.host, port=args.port, reload=args.reload)
        return

    _run_demo(args.kind)


def _run_demo(kind: str) -> None:
    os.environ.setdefault("SOURCELOOP_DATABASE_URL", "sqlite:///./sourceloop-demo.db")
    os.environ.setdefault("SOURCELOOP_EMAIL_MODE", "dry_run")
    os.environ.setdefault("SOURCELOOP_ALLOW_EXTERNAL_SEND", "false")
    os.environ.setdefault("SOURCELOOP_AGENT_RUNTIME", "mock")
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
