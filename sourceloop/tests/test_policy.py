from __future__ import annotations

from sourceloop.domain import ActionProposal, ActionStatus, CaseKind, CaseRecord, ContactRoute
from sourceloop.policy import PolicyEngine


def test_policy_requires_approval_and_disclosure(settings, repository) -> None:
    case = CaseRecord(
        title="Policy",
        kind=CaseKind.DATA_VERIFICATION,
        objective="Verify a record.",
        requester_name="Analyst",
    )
    action = ActionProposal(recipient="person@example.com", subject="Question", body="Please answer.")
    decision = PolicyEngine(settings, repository).evaluate(case, action)
    assert decision.allowed is False
    assert any("approval" in reason.lower() for reason in decision.reasons)
    assert any("disclose" in reason.lower() for reason in decision.reasons)


def test_policy_allows_approved_disclosed_dry_run(settings, repository) -> None:
    case = CaseRecord(
        title="Policy",
        kind=CaseKind.DATA_VERIFICATION,
        objective="Verify a record.",
        requester_name="Analyst",
        contacts=[
            ContactRoute(
                organization_name="Example Organization",
                role_title="Public contact",
                endpoint="person@example.com",
            )
        ],
    )
    action = ActionProposal(
        status=ActionStatus.APPROVED,
        recipient="person@example.com",
        subject="Question",
        body="I am an automated assistant acting for Analyst.",
        idempotency_key="key",
    )
    assert PolicyEngine(settings, repository).evaluate(case, action).allowed is True
