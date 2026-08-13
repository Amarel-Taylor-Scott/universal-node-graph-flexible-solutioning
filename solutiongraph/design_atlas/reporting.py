"""Portable JSON, Markdown, and self-contained HTML atlas reports."""

from __future__ import annotations

import html
import json
from pathlib import Path

from solutiongraph.design_atlas.model import DesignContext, DesignDossier, DesignPlan
from solutiongraph.design_atlas.packs import DESIGN_QUESTION_BY_ID
from solutiongraph.design_atlas.sources import SOURCE_BY_ID


def _detail(plan: DesignPlan) -> list[dict]:
    rows: list[dict] = []
    for item in plan.items:
        question = DESIGN_QUESTION_BY_ID[item.question_id]
        row = item.to_dict()
        row.update({
            "title": question.title,
            "prompt": question.prompt,
            "rationale": question.rationale,
            "required_evidence": list(question.required_evidence),
            "choices": [choice.to_dict() for choice in question.choices],
            "experiment_template": question.experiment_template,
            "stop_conditions": list(question.stop_conditions),
            "references": [SOURCE_BY_ID[source].to_dict() for source in question.reference_ids],
        })
        rows.append(row)
    return rows


def plan_payload(
    context: DesignContext,
    plan: DesignPlan,
    dossier: DesignDossier | None = None,
) -> dict:
    payload = {
        "context": context.to_dict(),
        "plan": plan.to_dict(),
        "question_details": _detail(plan),
        "dossier": dossier.to_dict() if dossier else None,
        "claim_boundary": (
            "This report is a decision worklist. It does not make a proposed technique "
            "executable, compiler-valid, benchmark-validated, or production-ready."
        ),
    }
    return payload


def render_markdown(
    context: DesignContext,
    plan: DesignPlan,
    dossier: DesignDossier | None = None,
) -> str:
    payload = plan_payload(context, plan, dossier)
    summary = plan.to_dict()["summary"]
    lines = [
        f"# Data-science design plan: {context.id}",
        "",
        "> Claim boundary: this is an evidence-seeking decision worklist, not proof that "
        "a technique or graph is executable or superior.",
        "",
        f"- Task archetype: `{plan.archetype_id}`",
        f"- Objective: {context.objective}",
        f"- Effort: `{plan.effort.id}` — {plan.effort.description}",
        f"- Plan digest: `{plan.digest}`",
        f"- Visible questions: {len(plan.items)}",
        "- Statuses: " + ", ".join(f"{key}={value}" for key, value in summary.items()),
        "",
        "```mermaid",
        "flowchart TD",
        '    A["Task contract"] --> B["Data and semantic review"]',
        '    B --> C["Model and experiment design"]',
        '    C --> D["Risk and operations review"]',
        '    D --> E["Typed graph handoff"]',
        '    E -. "new evidence" .-> C',
        "```",
        "",
        "## Selected questions",
        "",
    ]
    selected = [row for row in payload["question_details"] if row["status"] == "selected"]
    for index, row in enumerate(selected, 1):
        lines.extend([
            f"### {index}. {row['title']}",
            "",
            row["prompt"],
            "",
            f"Why: {row['rationale']}",
            "",
            "Evidence: " + ", ".join(f"`{item}`" for item in row["required_evidence"]),
            "",
            "Branches:",
            "",
        ])
        for choice in row["choices"]:
            lines.append(f"- `{choice['id']}` — {choice['label']}: {choice['consequence']}")
        if row["references"]:
            lines.extend(["", "Sources:", ""])
            for source in row["references"]:
                lines.append(f"- [{source['title']}]({source['url']}) — {source['claim']}")
        lines.append("")
    lines.extend([
        "## Complete visibility ledger",
        "",
        "| Status | Priority | Question | Pack | Reason |",
        "|---|---:|---|---|---|",
    ])
    for row in payload["question_details"]:
        reason = "; ".join(row["reasons"]).replace("|", "\\|")
        lines.append(
            f"| {row['status']} | {row['priority']:.3f} | `{row['question_id']}` | "
            f"`{row['pack_id']}` | {reason} |"
        )
    if dossier:
        lines.extend([
            "",
            "## Decision dossier",
            "",
            f"- Accepted/provisional/abstained records: {len(dossier.decisions)}",
            f"- Unanswered selected questions: {len(dossier.unanswered_question_ids)}",
            f"- Blocked questions: {len(dossier.blocked_question_ids)}",
        ])
    return "\n".join(lines) + "\n"


def render_html(
    context: DesignContext,
    plan: DesignPlan,
    dossier: DesignDossier | None = None,
) -> str:
    payload = plan_payload(context, plan, dossier)
    summary = plan.to_dict()["summary"]
    cards = "".join(
        f'<div class="card"><strong>{value}</strong><span>{html.escape(key)}</span></div>'
        for key, value in summary.items()
    )
    rows = []
    for row in payload["question_details"]:
        choices = "".join(
            f"<li><code>{html.escape(choice['id'])}</code> — {html.escape(choice['label'])}</li>"
            for choice in row["choices"]
        )
        rows.append(
            f'<article class="question {html.escape(row["status"])}">'
            f'<div class="meta"><span>{html.escape(row["status"])}</span>'
            f'<span>{row["priority"]:.3f}</span><code>{html.escape(row["pack_id"])}</code></div>'
            f'<h2>{html.escape(row["title"])}</h2><p>{html.escape(row["prompt"])}</p>'
            f'<p class="why">{html.escape(row["rationale"])}</p><ul>{choices}</ul></article>'
        )
    embedded = (
        json.dumps(payload, sort_keys=True)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Design atlas — {html.escape(context.id)}</title>
<style>
:root{{--bg:#f5f7fb;--ink:#172033;--muted:#68738a;--line:#dce2ee;--accent:#3157d5;--card:#fff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif}}
main{{max-width:1080px;margin:auto;padding:42px 24px 80px}}h1{{font-size:34px;margin-bottom:6px}}.lede{{color:var(--muted);max-width:850px}}
.cards{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:28px 0}}.card,.question{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}
.card strong{{display:block;font-size:28px}}.card span,.meta{{color:var(--muted)}}.question{{margin:14px 0}}.question h2{{font-size:20px}}
.meta{{display:flex;gap:12px;align-items:center}}.meta span:first-child{{color:var(--accent);font-weight:700}}.why{{border-left:3px solid var(--line);padding-left:12px;color:var(--muted)}}
code{{font-size:12px}}@media(max-width:700px){{.cards{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><main><h1>Data-science design atlas</h1>
<p class="lede"><strong>{html.escape(plan.archetype_id)}</strong> — {html.escape(context.objective)}</p>
<p class="lede">Claim boundary: this is an evidence-seeking worklist, not an implementation or performance claim.</p>
<div class="cards">{cards}</div>{''.join(rows)}
<script id="design-atlas-payload" type="application/json">{embedded}</script></main></body></html>"""


def write_plan_bundle(
    context: DesignContext,
    plan: DesignPlan,
    output_dir: Path,
    dossier: DesignDossier | None = None,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "design-plan.json"
    markdown_path = output_dir / "design-plan.md"
    html_path = output_dir / "design-plan.html"
    json_path.write_text(
        json.dumps(plan_payload(context, plan, dossier), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(context, plan, dossier), encoding="utf-8")
    html_path.write_text(render_html(context, plan, dossier), encoding="utf-8")
    return json_path, markdown_path, html_path


__all__ = [
    "plan_payload",
    "render_html",
    "render_markdown",
    "write_plan_bundle",
]
