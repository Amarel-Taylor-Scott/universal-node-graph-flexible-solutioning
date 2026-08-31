"""Evidence-linked case reports and price/disclosure summaries."""

from __future__ import annotations

import csv
import io
import statistics
from collections import Counter, defaultdict
from typing import Any

from .domain import CaseRecord, Direction
from .packs import VerticalPack


def build_case_report(case: CaseRecord, pack: VerticalPack | None) -> dict[str, Any]:
    inbound = [item for item in case.interactions if item.direction is Direction.INBOUND]
    outbound = [item for item in case.interactions if item.direction is Direction.OUTBOUND]
    response_endpoints = {item.endpoint for item in inbound}
    contacted_endpoints = {item.endpoint for item in outbound}
    severity = Counter(finding.severity.value for finding in case.findings)
    finding_kind = Counter(finding.kind.value for finding in case.findings)

    price_by_unit: dict[str, list[float]] = defaultdict(list)
    for quote in case.quotes:
        for item in quote.line_items:
            price_by_unit[f"{item.currency}:{item.unit}"].append(item.unit_price)

    market_prices = {
        unit: {
            "count": len(values),
            "minimum": min(values),
            "median": statistics.median(values),
            "maximum": max(values),
            "mean": round(statistics.fmean(values), 2),
        }
        for unit, values in sorted(price_by_unit.items())
    }

    critical_fields = [field.id for field in (pack.response_fields if pack else []) if field.critical]
    coverage_rows = []
    for endpoint in sorted(response_endpoints):
        covered = set(case.response_coverage.get(endpoint, []))
        coverage_rows.append(
            {
                "endpoint": endpoint,
                "covered": sorted(covered),
                "missing_critical": sorted(set(critical_fields) - covered),
                "coverage_ratio": round(len(covered) / max(1, len(pack.response_fields if pack else [])), 3),
            }
        )

    open_findings = [finding for finding in case.findings if finding.status.value == "open"]
    evidence_ids = sorted(
        {
            evidence_id
            for interaction in case.interactions
            for evidence_id in [interaction.evidence_id]
        }
        | {
            evidence_id
            for finding in case.findings
            for evidence_id in finding.evidence_ids
        }
        | {
            evidence_id
            for quote in case.quotes
            for evidence_id in quote.evidence_ids
        }
    )

    return {
        "case": {
            "id": case.id,
            "title": case.title,
            "kind": case.kind.value,
            "pack": case.pack,
            "status": case.status.value,
            "stage": case.stage.value,
            "objective": case.objective,
            "requester_name": case.requester_name,
            "risk_tier": case.risk_tier.value,
            "investigation_mode": case.investigation_mode.value if case.investigation_mode else None,
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
        },
        "activity": {
            "contacts_selected": len(case.contacts),
            "unique_endpoints_contacted": len(contacted_endpoints),
            "unique_respondents": len(response_endpoints),
            "response_rate": round(len(response_endpoints) / max(1, len(contacted_endpoints)), 3),
            "outbound_messages": len(outbound),
            "inbound_messages": len(inbound),
            "followups": sum(1 for action in case.actions if action.followup),
            "suppressed_responses": sum(
                1
                for finding in case.findings
                if finding.kind.value == "policy_risk" and "suppression" in finding.title.lower()
            ),
        },
        "results": {
            "claims": len(case.claims),
            "quotes": len(case.quotes),
            "findings": len(case.findings),
            "registry_checks": len(case.registry_checks),
            "open_findings": len(open_findings),
            "reviewed_findings": sum(1 for finding in case.findings if finding.reviewed_at is not None),
            "completion_quality": _completion_quality(case, coverage_rows),
            "findings_by_severity": dict(sorted(severity.items())),
            "findings_by_kind": dict(sorted(finding_kind.items())),
        },
        "market_prices": market_prices,
        "response_coverage": coverage_rows,
        "quotes": [
            {
                "id": quote.id,
                "supplier": quote.supplier_name,
                "normalized_total": quote.normalized_total,
                "currency": quote.currency,
                "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
                "confidence": quote.extraction_confidence,
                "unresolved_fields": quote.unresolved_fields,
                "line_items": [item.model_dump(mode="json") for item in quote.line_items],
                "evidence_ids": quote.evidence_ids,
            }
            for quote in case.quotes
        ],
        "findings": [finding.model_dump(mode="json") for finding in case.findings],
        "registry_checks": [check.model_dump(mode="json") for check in case.registry_checks],
        "governance": case.governance,
        "evidence_ids": evidence_ids,
        "interpretation_notice": (
            "Findings describe direct-source statements, omissions, and registry results. "
            "They are not automatic legal conclusions or accusations."
        ),
    }


def case_report_csv(case: CaseRecord, pack: VerticalPack | None) -> str:
    report = build_case_report(case, pack)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "record_id", "subject", "field", "value", "confidence", "evidence_ids"])
    for quote in report["quotes"]:
        for index, item in enumerate(quote["line_items"]):
            writer.writerow(
                [
                    "quote",
                    quote["id"],
                    quote["supplier"],
                    f"line_item_{index}:{item['description']}",
                    f"{item['currency']} {item['unit_price']} per {item['unit']}",
                    quote["confidence"],
                    ";".join(quote["evidence_ids"]),
                ]
            )
    for finding in report["findings"]:
        writer.writerow(
            [
                "finding",
                finding["id"],
                finding["subject_id"],
                f"{finding['severity']}:{finding['kind']}",
                finding["summary"],
                finding["confidence"],
                ";".join(finding["evidence_ids"]),
            ]
        )
    for check in report["registry_checks"]:
        writer.writerow(
            [
                "registry_check",
                check["id"],
                check.get("entity_name") or check["query"],
                check["registry"],
                check["status"],
                "",
                ";".join(check["evidence_ids"]),
            ]
        )
    return output.getvalue()


def _completion_quality(case: CaseRecord, coverage_rows: list[dict[str, Any]]) -> str:
    if case.status.value != "completed":
        return "in_progress"
    if any(row["missing_critical"] for row in coverage_rows):
        return "completed_with_disclosure_gaps"
    if any(finding.status.value == "open" and finding.severity.value in {"high", "critical"} for finding in case.findings):
        return "completed_with_high_priority_review"
    return "complete"
