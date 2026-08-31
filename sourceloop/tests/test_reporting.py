from __future__ import annotations

from sourceloop.domain import (
    CaseKind,
    CaseRecord,
    FindingKind,
    InvestigationFinding,
    Quote,
    QuoteLineItem,
    Severity,
)
from sourceloop.packs import PackRegistry
from sourceloop.reporting import build_case_report, case_report_csv


def test_report_summarizes_prices_findings_and_governance() -> None:
    case = CaseRecord(
        title="Local quote report",
        kind=CaseKind.QUOTE_INTELLIGENCE,
        objective="Compare prices.",
        requester_name="Buyer",
        pack="local_services_quote",
        quotes=[
            Quote(
                supplier_name="A",
                line_items=[QuoteLineItem(description="mowing", unit="visit", unit_price=48)],
                evidence_ids=["evidence-a"],
            ),
            Quote(
                supplier_name="B",
                line_items=[QuoteLineItem(description="mowing", unit="visit", unit_price=52)],
                evidence_ids=["evidence-b"],
            ),
        ],
        findings=[
            InvestigationFinding(
                rule_id="fee",
                kind=FindingKind.REPORTED_FEE,
                severity=Severity.LOW,
                title="Fee",
                summary="Bagging fee reported.",
                subject_id="contact-b",
                evidence_ids=["evidence-b"],
            )
        ],
        governance={"reuse_policy": "buyer_private"},
    )
    pack = PackRegistry().require("local_services_quote")
    report = build_case_report(case, pack)
    assert report["market_prices"]["USD:visit"]["median"] == 50.0
    assert report["results"]["findings"] == 1
    assert set(report["evidence_ids"]) == {"evidence-a", "evidence-b"}
    csv_output = case_report_csv(case, pack)
    assert "mowing" in csv_output
    assert "Bagging fee reported" in csv_output
