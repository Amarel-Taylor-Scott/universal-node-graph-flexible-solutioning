from __future__ import annotations

from sourceloop.domain import CaseKind, InvestigationMode, PractitionerStage, RiskTier
from sourceloop.packs import PackRegistry


def test_registry_loads_commercial_and_investigation_product_families() -> None:
    registry = PackRegistry()
    identifiers = {pack.id for pack in registry.list()}

    assert {
        "civic_intelligence",
        "facilities_quote",
        "bpo_quote",
        "local_services_quote",
        "staffing_procurement",
        "employment_practice_audit",
        "lender_disclosure_audit",
        "contractor_license_verification",
        "informal_market_census",
        "franchise_service_audit",
        "investigative_market_integrity",
    }.issubset(identifiers)


def test_investigation_pack_contains_typed_workflow_controls() -> None:
    pack = PackRegistry().get("employment_practice_audit")

    assert pack is not None
    assert pack.case_kind is CaseKind.MARKET_INVESTIGATION
    assert pack.investigation_mode is InvestigationMode.PRACTICE_AUDIT
    assert pack.risk_tier is RiskTier.RESTRICTED
    assert pack.restricted is True
    assert pack.roles_for(PractitionerStage.HOW, [])
    assert "email" in pack.allowed_channels
    assert "ssn" in pack.prohibited_requirement_fields


def test_pack_kind_mismatch_is_rejected() -> None:
    registry = PackRegistry()

    try:
        registry.validate_case_selection(CaseKind.QUOTE_INTELLIGENCE, "lender_disclosure_audit")
    except ValueError as exc:
        assert "requires case kind" in str(exc)
    else:
        raise AssertionError("Expected case-kind mismatch to be rejected")
