from __future__ import annotations

from sourceloop.domain import ApprovalRequest, CaseCreate, CaseKind, CaseStatus, InboundEmail
from sourceloop.engine import SourceLoopEngine


def _quote_case() -> CaseCreate:
    return CaseCreate(
        title="Five-building facilities quote",
        kind=CaseKind.QUOTE_INTELLIGENCE,
        pack="facilities_quote",
        objective="Obtain comparable non-binding service quotes.",
        requester_name="Test Procurement",
        demo=True,
        requirements={
            "service": "commercial preventive maintenance",
            "property_count": 5,
            "minimum_quotes": 2,
        },
    )


def _approve_and_dispatch(engine: SourceLoopEngine, case_id: str):
    case = engine.get_case(case_id)
    for action in case.actions:
        if action.status.value == "pending":
            case = engine.approve_action(case.id, action.id, ApprovalRequest(approver="test-reviewer"))
    return engine.dispatch_approved(case.id)


def test_end_to_end_quote_practitioner(engine: SourceLoopEngine) -> None:
    case = engine.create_case(_quote_case())
    case = engine.run_until_blocked(case.id)

    assert case.status is CaseStatus.WAITING_APPROVAL
    assert case.stage.value == "act"
    assert len(case.actions) == 3
    assert len(case.contacts) == 3
    assert all(action.status.value == "pending" for action in case.actions)
    assert all("[SL:" in action.subject for action in case.actions)
    assert len(case.agent_runs) >= 10

    case = _approve_and_dispatch(engine, case.id)

    assert case.status is CaseStatus.WAITING_EXTERNAL
    assert len(engine.repository.list_outbox()) == 3
    assert all(row.provider_message_id for row in engine.repository.list_outbox())
    assert len([item for item in case.interactions if item.direction.value == "outbound"]) == 3

    case = engine.simulate_demo_replies(case.id)

    assert case.status is CaseStatus.COMPLETED
    assert case.graph_committed is True
    assert len(case.quotes) >= 2
    assert all(quote.line_items for quote in case.quotes)
    assert all(quote.evidence_ids for quote in case.quotes)
    assert any(event.event_type == "case_completed" for event in engine.repository.list_events(case.id))


def test_incomplete_quote_generates_threaded_followup(engine: SourceLoopEngine) -> None:
    case = engine.create_case(_quote_case())
    case = engine.run_until_blocked(case.id)
    case = _approve_and_dispatch(engine, case.id)
    outbound = case.interactions[0]

    case = engine.record_inbound(
        InboundEmail(
            case_id=case.id,
            thread_id=outbound.thread_id,
            sender=outbound.endpoint,
            subject=f"Re: {outbound.subject}",
            body="$125 per visit. Taxes are excluded. Scope is confirmed for the stated portfolio.",
            provider_message_id="<supplier-partial@example.test>",
            in_reply_to=outbound.provider_message_id,
            references=[outbound.provider_message_id] if outbound.provider_message_id else [],
        )
    )

    followups = [action for action in case.actions if action.followup]
    assert case.status is CaseStatus.WAITING_APPROVAL
    assert len(followups) == 1
    assert followups[0].thread_id == outbound.thread_id
    assert followups[0].in_reply_to == "<supplier-partial@example.test>"
    assert "payment terms" in followups[0].body.lower()
    assert "date through which" in followups[0].body.lower()


def test_civic_case_is_contact_bounded(engine: SourceLoopEngine) -> None:
    case = engine.create_case(
        CaseCreate(
            title="Public organization routing",
            kind=CaseKind.CIVIC_INTELLIGENCE,
            pack="civic_intelligence",
            objective="Confirm the public organization and inquiry route serving a municipality.",
            requester_name="Test Resident",
            demo=True,
            requirements={"geography": "Example municipality"},
        )
    )
    case = engine.run_until_blocked(case.id)

    assert case.max_contacts == 3
    assert case.max_followups == 1
    assert len(case.contacts) <= 3
    assert case.status is CaseStatus.WAITING_APPROVAL


def test_non_demo_case_waits_for_contact_discovery(engine: SourceLoopEngine) -> None:
    case = engine.create_case(
        CaseCreate(
            title="Unseeded verification",
            kind=CaseKind.DATA_VERIFICATION,
            objective="Verify an operational record.",
            requester_name="Test Analyst",
            requirements={"record_type": "business"},
        )
    )
    case = engine.run_until_blocked(case.id)

    assert case.status is CaseStatus.WAITING_INPUT
    assert case.stage.value == "how"
    assert case.actions == []


def test_opt_out_creates_suppression(engine: SourceLoopEngine) -> None:
    case = engine.create_case(_quote_case())
    case = engine.run_until_blocked(case.id)
    case = _approve_and_dispatch(engine, case.id)
    outbound = case.interactions[0]

    engine.record_inbound(
        InboundEmail(
            case_id=case.id,
            thread_id=outbound.thread_id,
            sender=outbound.endpoint,
            subject=f"Re: {outbound.subject}",
            body="Please do not contact this endpoint again.",
            provider_message_id="<optout@example.test>",
            in_reply_to=outbound.provider_message_id,
        )
    )

    assert engine.repository.is_suppressed(outbound.endpoint)
