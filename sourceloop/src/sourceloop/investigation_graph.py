"""Graph projections for investigation findings and registry evidence."""

from __future__ import annotations

import networkx as nx

from .domain import CaseRecord
from .graph import GraphProjector


class InvestigationGraphProjector(GraphProjector):
    def build_networkx(self, cases: list[CaseRecord]) -> nx.MultiDiGraph:
        graph = super().build_networkx(cases)
        for case in cases:
            for finding in case.findings:
                graph.add_node(
                    finding.id,
                    node_type="investigation_finding",
                    label=finding.title,
                    finding_kind=finding.kind.value,
                    severity=finding.severity.value,
                    status=finding.status.value,
                    confidence=finding.confidence,
                    summary=finding.summary,
                    requires_human_review=finding.requires_human_review,
                    reviewed_by=finding.reviewed_by,
                    reviewed_at=finding.reviewed_at.isoformat() if finding.reviewed_at else None,
                )
                graph.add_edge(case.id, finding.id, relation="produced_finding", source="finding_ledger")
                if finding.subject_id in graph:
                    graph.add_edge(finding.subject_id, finding.id, relation="subject_of", source="finding_ledger")
                for evidence_id in finding.evidence_ids:
                    interaction = next(
                        (item for item in case.interactions if item.evidence_id == evidence_id),
                        None,
                    )
                    if interaction and interaction.id in graph:
                        graph.add_edge(interaction.id, finding.id, relation="supports", source="evidence_ledger")

            for check in case.registry_checks:
                graph.add_node(
                    check.id,
                    node_type="registry_check",
                    label=f"{check.registry}: {check.status}",
                    registry=check.registry,
                    query=check.query,
                    status=check.status,
                    identifier=check.identifier,
                    entity_name=check.entity_name,
                    jurisdiction=check.jurisdiction,
                    checked_at=check.checked_at.isoformat(),
                )
                graph.add_edge(case.id, check.id, relation="has_registry_check", source="registry_ledger")
                if check.subject_id and check.subject_id in graph:
                    graph.add_edge(check.subject_id, check.id, relation="checked_in_registry", source="registry_ledger")
        return graph
