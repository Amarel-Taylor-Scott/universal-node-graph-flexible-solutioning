from __future__ import annotations

import pytest

from sourceloop.domain import (
    ActionStatus,
    ApprovalRequest,
    CaseCreate,
    CaseKind,
    ContactRoute,
    InboundEmail,
    InvestigationMode,
)
from sourceloop.extended_engine import InvestigativeSourceLoopEngine
from sourceloop.packs import PackRegistry
from sourceloop.policy import PolicyEngine


def _approve_and_dispatch(engine: InvestigativeSourceLoopEngine, case_id: str):
    case = engine.get_case(case_id)
    for action in case.actions:
        if action.status is ActionStatus.PENDING:
            case = engine.approve_action(case.id, action.id, ApprovalRequest(approver="test-reviewer"))
    return engine.dispatch_approved(case.id)


def _investigation_acknowledgements() -> dict[str, bool]:
    return {
        "institutional_authority": True,
        "authorized_requester": True,
        "legal_review": True,
        "research_only": True,
        "public_business_channels_only": True,
        "no_fake_persona": True,
        "no_application": True,
        "no_sensitive_personal_data": True,
        "no_residential_mapping": True,
    }


def test_pack_registry_contains_active_investigation_catalog() -> None:
    registry = PackRegistry()
    ids = {pack.id for pack in registry.list()}
    assert {
        "local_services_quote",
        "staffing_procurement",
        "employment_agency_audit",
        "lender_disclosure_audit",
        "contractor_license_audit",
        "informal_business_verification",
        "franchise_service_audit",
        "business_record_verification",
    }.issubset(ids)
    assert registry.require("lender_disclosure_audit").risk_tier.value == "restricted"
    assert registry.require("employment_agency_audit").response_fields


def test_restricted_lender_case_requires_explicit_governance(settings, repository) -> None:
    engine = InvestigativeSourceLoopEngine(settings, repository=repository)
    request = CaseCreate(
        title="Disclosure study",
        kind=CaseKind.MARKET_INVESTIGATION,
        pack="lender_disclosure_audit",
        objective="Collect representative public credit disclosures.",
        requester_name="Institutional Research Team",
        requester_email="research@example.test",
        requirements={
            "geography": "Example State",
            "research_purpose": "disclosure comparison",
            "scenario": "$300 for 14 days",
        },
    )
    with pytest.raises(ValueError, match="institutional_authority"):
        engine.create_case(request)

    request.governance_acknowledgements = _investigation_acknowledgements()
    case = engine.create_case(request)
    assert case.risk_tier.value == "restricted"
    assert case.governance["acknowledgements"]["legal_review"] is True


def test_employment_agency_demo_creates_reviewable_fee_finding(settings, repository) -> None:
    engine = InvestigativeSourceLoopEngine(settings, repository=repository)
    case = engine.create_case(
        CaseCreate(
            title="Employment agency public practice audit",
            kind=CaseKind.MARKET_INVESTIGATION,
            pack="employment_agency_audit",
            objective="Collect public applicant-fee and job-disclosure representations.",
            requester_name="Worker Protection Research Team",
            requester_email="research@example.test",
            demo=True,
            requirements={
                "geography": "Example market",
                "research_purpose": "public practice audit",
                "scenario": "warehouse associate inquiry",
            },
            governance_acknowledgements=_investigation_acknowledgements(),
            investigation_mode=InvestigationMode.PRACTICE_AUDIT,
        )
    )
    case = engine.run_until_blocked(case.id)
    assert case.status.value == "waiting_approval"
    case = _approve_and_dispatch(engine, case.id)
    case = engine.simulate_demo_replies(case.id)

    assert case.status.value == "completed"
    assert any(finding.rule_id == "applicant_fee_reported" for finding in case.findings)
    fee = next(finding for finding in case.findings if finding.rule_id == "applicant_fee_reported")
    assert fee.requires_human_review is True
    assert fee.evidence_ids
    assert "applicant_fee_policy" in case.response_coverage[case.contacts[0].endpoint]


def test_lender_demo_records_terms_without_becoming_an_application(settings, repository) -> None:
    engine = InvestigativeSourceLoopEngine(settings, repository=repository)
    case = engine.create_case(
        CaseCreate(
            title="Short-term credit disclosure audit",
            kind=CaseKind.MARKET_INVESTIGATION,
            pack="lender_disclosure_audit",
            objective="Collect standardized public disclosures for a hypothetical product.",
            requester_name="Authorized Compliance Lab",
            requester_email="compliance@example.test",
            demo=True,
            requirements={
                "geography": "Example State",
                "research_purpose": "institutional disclosure audit",
                "scenario": "$300 principal for 14 days",
            },
            governance_acknowledgements=_investigation_acknowledgements(),
            investigation_mode=InvestigationMode.COMPLIANCE_PROBE,
        )
    )
    case = engine.run_until_blocked(case.id)
    case = _approve_and_dispatch(engine, case.id)
    case = engine.simulate_demo_replies(case.id)

    assert case.status.value == "completed"
    rules = {finding.rule_id for finding in case.findings}
    assert "triple_digit_apr" in rules
    assert "rollover_available" in rules
    assert "ach_required" in rules
    assert all("application" not in action.body.lower() or "not a loan application" in action.body.lower() for action in case.actions)


def test_partial_investigation_response_proposes_one_narrow_followup(settings, repository) -> None:
    engine = InvestigativeSourceLoopEngine(settings, repository=repository)
    contact = ContactRoute(
        organization_name="Example Employment Agency LLC",
        role_title="Compliance team",
        endpoint="compliance@agency.example.test",
        source="public_website",
        source_public=True,
        business_only=True,
    )
    case = engine.create_case(
        CaseCreate(
            title="Agency disclosure follow-up",
            kind=CaseKind.MARKET_INVESTIGATION,
            pack="employment_agency_audit",
            objective="Verify public employment-agency practices.",
            requester_name="Research Team",
            requester_email="research@example.test",
            requirements={
                "geography": "Example market",
                "research_purpose": "practice audit",
                "scenario": "warehouse role",
            },
            contacts=[contact],
            governance_acknowledgements=_investigation_acknowledgements(),
        )
    )
    case = engine.run_until_blocked(case.id)
    case = _approve_and_dispatch(engine, case.id)
    outbound = next(item for item in case.interactions if item.direction.value == "outbound")
    case = engine.record_inbound(
        InboundEmail(
            case_id=case.id,
            thread_id=outbound.thread_id,
            sender=contact.endpoint,
            subject=f"Re: {outbound.subject}",
            body="Our legal business name is Example Employment Agency LLC.",
            provider_message_id="<partial-reply@agency.example.test>",
            in_reply_to=outbound.provider_message_id,
            references=[outbound.provider_message_id] if outbound.provider_message_id else [],
        )
    )

    pending = [action for action in case.actions if action.followup and action.status is ActionStatus.PENDING]
    assert len(pending) == 1
    assert "applicant fee" in pending[0].body.lower()
    assert pending[0].in_reply_to == "<partial-reply@agency.example.test>"
    assert any(finding.kind.value == "disclosure_gap" for finding in case.findings)


def test_policy_blocks_sensitive_personal_data_request(settings, repository) -> None:
    engine = InvestigativeSourceLoopEngine(settings, repository=repository)
    request = CaseCreate(
        title="Controlled lender audit",
        kind=CaseKind.MARKET_INVESTIGATION,
        pack="lender_disclosure_audit",
        objective="Collect public disclosure terms only.",
        requester_name="Compliance Team",
        requester_email="compliance@example.test",
        requirements={
            "geography": "Example State",
            "research_purpose": "public disclosure audit",
            "scenario": "$300 for 14 days",
        },
        contacts=[
            ContactRoute(
                organization_name="Example Lender LLC",
                role_title="Compliance team",
                endpoint="compliance@lender.example.test",
                source="public_website",
                source_public=True,
                business_only=True,
            )
        ],
        governance_acknowledgements=_investigation_acknowledgements(),
    )
    case = engine.create_case(request)
    case = engine.run_until_blocked(case.id)
    action = case.actions[0]
    action.body += " Please provide your social security number."
    action.status = ActionStatus.APPROVED
    decision = PolicyEngine(settings, repository).evaluate(case, action)
    assert decision.allowed is False
    assert any("sensitive personal" in reason for reason in decision.reasons)


def test_market_investigation_requires_explicit_pack(settings, repository) -> None:
    engine = InvestigativeSourceLoopEngine(settings, repository=repository)
    with pytest.raises(ValueError, match="explicit governed pack"):
        engine.create_case(
            CaseCreate(
                title="Unscoped investigation",
                kind=CaseKind.MARKET_INVESTIGATION,
                objective="Collect public business information.",
                requester_name="Research Team",
                requester_email="research@example.test",
                requirements={"geography": "Example market"},
            )
        )


def test_registry_check_creates_reviewable_result_and_can_be_reviewed(settings, repository) -> None:
    from sourceloop.domain import FindingReviewRequest, FindingStatus, RegistryCheckCreate

    engine = InvestigativeSourceLoopEngine(settings, repository=repository)
    case = engine.create_case(
        CaseCreate(
            title="Contractor authorization audit",
            kind=CaseKind.MARKET_INVESTIGATION,
            pack="contractor_license_audit",
            objective="Verify public contractor identity and license representations.",
            requester_name="Authorized Research Team",
            requester_email="research@example.test",
            requirements={"geography": "Example State", "trade": "roofing", "research_purpose": "verification"},
            governance_acknowledgements=_investigation_acknowledgements(),
        )
    )
    case = engine.add_registry_check(
        case.id,
        RegistryCheckCreate(
            registry="Example contractor registry",
            query="Example Roofing LLC",
            subject_id="example-roofing",
            status="not_found",
            source="https://registry.example.test/search/123",
        ),
    )
    finding = next(item for item in case.findings if item.source_scope == "registry_check")
    assert finding.kind.value == "license_unverified"
    assert finding.requires_human_review is True

    case = engine.review_finding(
        case.id,
        finding.id,
        FindingReviewRequest(
            status=FindingStatus.CORROBORATED,
            reviewer="licensed-investigator",
            notes="Confirmed against a second authoritative registry.",
        ),
    )
    reviewed = next(item for item in case.findings if item.id == finding.id)
    assert reviewed.status is FindingStatus.CORROBORATED
    assert reviewed.reviewed_by == "licensed-investigator"
    assert reviewed.reviewed_at is not None


def test_lender_demo_adds_deterministic_cost_metric(settings, repository) -> None:
    engine = InvestigativeSourceLoopEngine(settings, repository=repository)
    case = engine.create_case(
        CaseCreate(
            title="Lender arithmetic audit",
            kind=CaseKind.MARKET_INVESTIGATION,
            pack="lender_disclosure_audit",
            objective="Collect a standardized public disclosure response.",
            requester_name="Authorized Compliance Lab",
            requester_email="compliance@example.test",
            demo=True,
            requirements={
                "geography": "Example State",
                "research_purpose": "institutional disclosure audit",
                "scenario": "$300 principal for 14 days",
            },
            governance_acknowledgements=_investigation_acknowledgements(),
        )
    )
    case = engine.run_until_blocked(case.id)
    case = _approve_and_dispatch(engine, case.id)
    case = engine.simulate_demo_replies(case.id)
    metric = next(item for item in case.findings if item.rule_id == "derived_simple_annualized_cost")
    assert metric.kind.value == "derived_metric"
    assert metric.value["simple_annualized_percent"] == pytest.approx(391.07, abs=0.01)
    assert metric.requires_human_review is False


def test_staffing_demo_calculates_implied_markup(settings, repository) -> None:
    engine = InvestigativeSourceLoopEngine(settings, repository=repository)
    case = engine.create_case(
        CaseCreate(
            title="Warehouse staffing quote",
            kind=CaseKind.QUOTE_INTELLIGENCE,
            pack="staffing_procurement",
            objective="Obtain employer-side staffing proposals.",
            requester_name="Procurement Team",
            requester_email="procurement@example.test",
            demo=True,
            requirements={"roles": "warehouse associates", "workers": 20, "geography": "Example market"},
            governance_acknowledgements={"authorized_requester": True, "research_only": True},
        )
    )
    case = engine.run_until_blocked(case.id)
    case = _approve_and_dispatch(engine, case.id)
    case = engine.simulate_demo_replies(case.id)
    metrics = [item for item in case.findings if item.rule_id == "derived_staffing_markup"]
    assert metrics
    assert metrics[0].value["implied_markup_percent"] == pytest.approx(47.5)
