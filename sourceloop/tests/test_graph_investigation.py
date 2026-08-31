from __future__ import annotations

from sourceloop.domain import (
    CaseKind,
    CaseRecord,
    ContactRoute,
    FindingKind,
    InvestigationFinding,
    InvestigationMode,
)
from sourceloop.graph import GraphProjector


def test_graph_projects_investigation_findings_and_evidence() -> None:
    contact = ContactRoute(
        organization_name="Example Service",
        role_title="Public business contact",
        endpoint="info@example.test",
    )
    finding = InvestigationFinding(
        subject_id=contact.id,
        field="quoted_price",
        value={"amount": 45, "currency": "USD", "unit": "visit"},
        kind=FindingKind.PRICE_OBSERVATION,
        evidence_ids=["evidence_1"],
    )
    case = CaseRecord(
        title="Local price probe",
        kind=CaseKind.MARKET_INVESTIGATION,
        pack="local_services_quote",
        investigation_mode=InvestigationMode.QUOTE_PROBE,
        objective="Obtain current pricing.",
        requester_name="Researcher",
        requester_email="researcher@example.test",
        contacts=[contact],
        findings=[finding],
    )

    graph = GraphProjector().build_networkx([case])

    assert graph.nodes[finding.id]["node_type"] == "investigation_finding"
    assert graph.has_edge(case.id, finding.id)
    assert graph.has_edge(contact.id, finding.id)
    assert graph.has_edge(finding.id, "evidence:evidence_1")
