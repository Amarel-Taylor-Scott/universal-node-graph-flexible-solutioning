from __future__ import annotations

from sourceloop.domain import ActionProposal, ActionStatus, CaseKind, CaseRecord, ContactRoute, stable_key
from sourceloop.policy import PolicyEngine
from sourceloop.repository import Repository
from sourceloop.config import Settings


def _approved_action(case: CaseRecord) -> ActionProposal:
    action = ActionProposal(
        status=ActionStatus.APPROVED,
        recipient="public@example.test",
        organization_name="Example Organization",
        subject="Information request",
        body=(
            "I am an automated assistant acting with Test Requester's authorization. "
            "This is a one-time information request."
        ),
        approved_by="reviewer",
    )
    action.idempotency_key = stable_key(case.id, action.recipient, action.subject, action.body)
    return action


def test_policy_allows_approved_dry_run(settings: Settings, repository: Repository) -> None:
    case = CaseRecord(
        title="Test",
        kind=CaseKind.DATA_VERIFICATION,
        objective="Verify a business contact.",
        requester_name="Test Requester",
        contacts=[
            ContactRoute(
                organization_name="Example Organization",
                role_title="Public contact",
                endpoint="public@example.test",
            )
        ],
    )
    action = _approved_action(case)
    case.actions.append(action)

    decision = PolicyEngine(settings, repository).evaluate(case, action)

    assert decision.allowed is True
    assert decision.reasons == []


def test_policy_blocks_suppressed_endpoint(settings: Settings, repository: Repository) -> None:
    case = CaseRecord(
        title="Test",
        kind=CaseKind.DATA_VERIFICATION,
        objective="Verify a business contact.",
        requester_name="Test Requester",
    )
    action = _approved_action(case)
    case.actions.append(action)
    repository.add_suppression(action.recipient, "Test suppression")

    decision = PolicyEngine(settings, repository).evaluate(case, action)

    assert decision.allowed is False
    assert any("suppression" in reason.lower() for reason in decision.reasons)


def test_policy_blocks_undisclosed_automation(settings: Settings, repository: Repository) -> None:
    case = CaseRecord(
        title="Test",
        kind=CaseKind.DATA_VERIFICATION,
        objective="Verify a business contact.",
        requester_name="Test Requester",
    )
    action = _approved_action(case)
    action.body = "Please provide this information."
    action.idempotency_key = stable_key(case.id, action.recipient, action.subject, action.body)
    case.actions.append(action)

    decision = PolicyEngine(settings, repository).evaluate(case, action)

    assert decision.allowed is False
    assert any("disclose" in reason.lower() for reason in decision.reasons)
