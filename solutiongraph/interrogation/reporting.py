"""Portable reports for semantic interrogation, repair, and verification runs."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from solutiongraph.interrogation.model import (
    DatasetProfile,
    FindingSet,
    QuestionPlan,
    RepairApplicationReceipt,
    RepairProposal,
    SemanticFieldMap,
    VerificationReceipt,
)
from solutiongraph.model import ID_RE, sha256_digest


@dataclass(frozen=True)
class InterrogationRunReport:
    """One content-addressed, raw-data-free interrogation evidence bundle."""

    id: str
    version: str
    source_profile: DatasetProfile
    semantic_field_map: SemanticFieldMap
    question_plan: QuestionPlan
    before_findings: FindingSet
    repair_proposal: RepairProposal
    repair_application: RepairApplicationReceipt
    shadow_profile: DatasetProfile
    shadow_field_map: SemanticFieldMap
    shadow_plan: QuestionPlan
    after_findings: FindingSet
    verification: VerificationReceipt
    configuration: tuple[tuple[str, Any], ...] = ()
    claim_scope: str = "mechanism-fixture"

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.version.strip():
            problems.append("report id and version must be valid")
        if self.claim_scope not in ("mechanism-fixture", "dataset-specific-evidence"):
            problems.append("claim_scope must be mechanism-fixture or dataset-specific-evidence")
        validators = (
            self.source_profile,
            self.semantic_field_map,
            self.question_plan,
            self.before_findings,
            self.repair_proposal,
            self.repair_application,
            self.shadow_profile,
            self.shadow_field_map,
            self.shadow_plan,
            self.after_findings,
            self.verification,
        )
        for item in validators:
            problems.extend(item.validate())
        if self.source_profile.dataset_digest != self.semantic_field_map.dataset_digest:
            problems.append("source profile and semantic map identify different datasets")
        if self.before_findings.plan_digest != self.question_plan.digest:
            problems.append("before findings do not identify the source plan")
        if self.shadow_profile.dataset_digest != self.shadow_field_map.dataset_digest:
            problems.append("shadow profile and semantic map identify different datasets")
        if self.after_findings.plan_digest != self.shadow_plan.digest:
            problems.append("after findings do not identify the shadow plan")
        if self.repair_proposal.finding_set_digest != self.before_findings.digest:
            problems.append("repair proposal does not identify the before findings")
        if self.repair_application.proposal_digest != self.repair_proposal.digest:
            problems.append("repair application does not identify the repair proposal")
        if self.verification.application_receipt_digest != self.repair_application.digest:
            problems.append("verification does not identify the repair application")
        keys = [key for key, _ in self.configuration]
        if len(keys) != len(set(keys)) or any(not ID_RE.fullmatch(key) for key in keys):
            problems.append("configuration must use unique namespaced keys")
        return problems

    def to_dict(self) -> dict[str, Any]:
        proposal = self.repair_proposal.to_dict()
        for operation in proposal["operations"]:
            operation["before_value"] = {
                "redacted": True,
                "digest": operation["before_digest"],
            }
            operation["after_value"] = {
                "redacted": True,
                "digest": sha256_digest(operation["after_value"]),
            }
        return {
            "interrogation_report_version": "0.1",
            "id": self.id,
            "version": self.version,
            "claim_scope": self.claim_scope,
            "configuration": dict(self.configuration),
            "source_profile": self.source_profile.to_dict(),
            "semantic_field_map": self.semantic_field_map.to_dict(),
            "question_plan": self.question_plan.to_dict(),
            "before_findings": self.before_findings.to_dict(),
            "repair_proposal": proposal,
            "repair_application": self.repair_application.to_dict(),
            "shadow_profile": self.shadow_profile.to_dict(),
            "shadow_field_map": self.shadow_field_map.to_dict(),
            "shadow_plan": self.shadow_plan.to_dict(),
            "after_findings": self.after_findings.to_dict(),
            "verification": self.verification.to_dict(),
            "summary": self.summary(),
        }

    def wire_dict(self) -> dict[str, Any]:
        """Return the transport representation with its content digest."""
        document = self.to_dict()
        document["digest"] = sha256_digest(document)
        return document

    def summary(self) -> dict[str, Any]:
        statuses: dict[str, int] = {}
        for item in self.question_plan.items:
            statuses[item.status] = statuses.get(item.status, 0) + 1
        outcomes: dict[str, int] = {}
        for receipt in self.before_findings.receipts:
            outcomes[receipt.outcome] = outcomes.get(receipt.outcome, 0) + 1
        return {
            "question_count": len(self.question_plan.items),
            "plan_status_counts": statuses,
            "execution_outcome_counts": outcomes,
            "finding_count_before": len(self.before_findings.findings),
            "finding_count_after": len(self.after_findings.findings),
            "repair_operation_count": len(self.repair_proposal.operations),
            "applied_operation_count": len(self.repair_application.applied_operation_ids),
            "verification_decision": self.verification.decision,
            "resolved_finding_count": len(self.verification.resolved_finding_ids),
            "remaining_finding_count": len(self.verification.remaining_finding_ids),
            "introduced_finding_count": len(self.verification.introduced_finding_ids),
        }


def render_mermaid(report: InterrogationRunReport) -> str:
    """Render the executed evidence loop as a compact Mermaid flowchart."""
    return "\n".join(
        (
            "flowchart TD",
            '  A["Profile and semantic map"] --> B["Visible question plan"]',
            '  B --> C["Checks and findings"]',
            '  C --> D["Reversible shadow repair"]',
            '  D --> E["Independent rerun and decision"]',
            f'  E --> F["{report.verification.decision.upper()}"]',
        )
    )


def render_markdown(report: InterrogationRunReport) -> str:
    summary = report.summary()
    lines = [
        f"# Semantic interrogation report: `{report.id}`",
        "",
        f"Decision: **{report.verification.decision}**  ",
        f"Report digest: `{report.wire_dict()['digest']}`  ",
        f"Dataset digest: `{report.source_profile.dataset_digest}`",
        "",
        "```mermaid",
        render_mermaid(report),
        "```",
        "",
        "## Run summary",
        "",
        "| Measure | Value |",
        "|---|---:|",
        f"| Visible questions | {summary['question_count']} |",
        f"| Executed checks | {len(report.before_findings.receipts)} |",
        f"| Findings before | {summary['finding_count_before']} |",
        f"| Findings after | {summary['finding_count_after']} |",
        f"| Proposed operations | {summary['repair_operation_count']} |",
        f"| Applied operations | {summary['applied_operation_count']} |",
        f"| Resolved findings | {summary['resolved_finding_count']} |",
        f"| Introduced findings | {summary['introduced_finding_count']} |",
        "",
        "## Plan visibility",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for status, count in sorted(summary["plan_status_counts"].items()):
        lines.append(f"| {status} | {count} |")
    lines.extend(("", "## Findings before repair", ""))
    if report.before_findings.findings:
        lines.extend(("| Severity | Code | Fields | Affected |", "|---|---|---|---:|"))
        for finding in report.before_findings.findings:
            lines.append(
                f"| {finding.severity} | `{finding.code}` | "
                f"{', '.join(finding.fields)} | {finding.affected_count} |"
            )
    else:
        lines.append("No findings were emitted by the selected checks.")
    lines.extend(("", "## Repair operations", ""))
    if report.repair_proposal.operations:
        lines.extend(("| Action | Field | Safe | Reason |", "|---|---|---|---|"))
        for operation in report.repair_proposal.operations:
            lines.append(
                f"| {operation.action} | `{operation.field_name}` | "
                f"{str(operation.safe_to_auto_apply).lower()} | {operation.reason} |"
            )
    else:
        lines.append("No conservative repair was available; uncertain cases were left unchanged.")
    lines.extend(("", "## Verification", ""))
    lines.extend(f"- {reason}" for reason in report.verification.reasons)
    lines.extend(
        (
            "",
            "## Claim boundary",
            "",
            "This report records deterministic mechanism evidence for this exact dataset and "
            "configuration. Standards references guide question meaning; they do not certify "
            "real-world truth. External, LLM, and human checks remain blocked unless their "
            "capabilities and permissions are supplied explicitly.",
            "",
        )
    )
    return "\n".join(lines)


def render_html(report: InterrogationRunReport) -> str:
    """Render a self-contained, script-free report suitable for CI artifacts."""
    summary = report.summary()
    finding_rows = "".join(
        "<tr>"
        f"<td>{html.escape(item.severity)}</td>"
        f"<td><code>{html.escape(item.code)}</code></td>"
        f"<td>{html.escape(', '.join(item.fields))}</td>"
        f"<td>{item.affected_count}</td>"
        "</tr>"
        for item in report.before_findings.findings
    ) or '<tr><td colspan="4">No findings.</td></tr>'
    reasons = "".join(f"<li>{html.escape(item)}</li>" for item in report.verification.reasons)
    status_cards = "".join(
        f'<div class="card"><strong>{count}</strong><span>{html.escape(status)}</span></div>'
        for status, count in sorted(summary["plan_status_counts"].items())
    )
    payload = html.escape(json.dumps(report.wire_dict(), indent=2, sort_keys=True))
    decision = html.escape(report.verification.decision)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Semantic interrogation report</title><style>
:root{{--ink:#172034;--muted:#5e687a;--line:#dce2ea;--surface:#f5f7fa;--accent:#3157d5}}
body{{font:15px/1.55 system-ui,sans-serif;color:var(--ink);margin:0;background:var(--surface)}}
main{{max-width:1040px;margin:auto;padding:36px}} h1{{font-size:28px;margin-bottom:4px}}
.decision{{display:inline-block;background:#e9efff;color:#183caa;padding:7px 12px;border-radius:20px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin:24px 0}}
.card{{background:white;border:1px solid var(--line);border-radius:10px;padding:16px;display:flex;flex-direction:column}}
.card strong{{font-size:24px}} .card span{{color:var(--muted)}} section{{background:white;border:1px solid var(--line);border-radius:12px;padding:20px;margin:16px 0}}
table{{width:100%;border-collapse:collapse}} th,td{{text-align:left;padding:9px;border-bottom:1px solid var(--line)}}
.flow{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;align-items:center}} .flow div{{padding:12px;background:#eef2ff;border-radius:8px;text-align:center}} .flow i{{text-align:center;color:var(--accent)}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#111827;color:#e5e7eb;padding:16px;border-radius:8px}} code{{font-family:ui-monospace,monospace}}
@media(max-width:700px){{main{{padding:18px}}.flow{{grid-template-columns:1fr}}.flow i{{transform:rotate(90deg)}}}}
</style></head><body><main>
<h1>Semantic interrogation report</h1><p><code>{html.escape(report.id)}</code></p>
<p class="decision">Decision: <strong>{decision}</strong></p>
<div class="cards"><div class="card"><strong>{summary['question_count']}</strong><span>visible questions</span></div>{status_cards}<div class="card"><strong>{summary['finding_count_before']} → {summary['finding_count_after']}</strong><span>findings</span></div><div class="card"><strong>{summary['applied_operation_count']}</strong><span>repairs applied</span></div></div>
<section><h2>Evidence loop</h2><div class="flow"><div>Profile + map</div><i>→</i><div>Plan + checks</div><i>→</i><div>Shadow repair + verify</div></div></section>
<section><h2>Findings before repair</h2><table><thead><tr><th>Severity</th><th>Code</th><th>Fields</th><th>Affected</th></tr></thead><tbody>{finding_rows}</tbody></table></section>
<section><h2>Verification</h2><ul>{reasons}</ul></section>
<section><h2>Claim boundary</h2><p>Evidence applies to this exact dataset and configuration. Standards sidecars do not certify real-world truth. External, LLM, and human checks require explicit capabilities and permissions.</p></section>
<details><summary>Portable JSON evidence</summary><pre>{payload}</pre></details>
</main></body></html>"""


def write_report_bundle(
    report: InterrogationRunReport,
    output_directory: str | Path,
) -> tuple[Path, Path, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "interrogation-report.json"
    markdown_path = output / "interrogation-report.md"
    html_path = output / "interrogation-report.html"
    json_path.write_text(
        json.dumps(report.wire_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")
    return json_path, markdown_path, html_path


__all__ = [
    "InterrogationRunReport",
    "render_html",
    "render_markdown",
    "render_mermaid",
    "write_report_bundle",
]
