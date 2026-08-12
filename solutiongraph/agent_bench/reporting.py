"""Authoritative JSON and self-contained HTML/SVG agent-benchmark reports."""

from __future__ import annotations

import json
from collections import defaultdict
from html import escape
from pathlib import Path

from solutiongraph.agent_bench.analysis import AgentBenchmarkReport
from solutiongraph.agent_bench.tasks.common import AgentTaskBundle


def _task_svg(bundle: AgentTaskBundle) -> str:
    stages = bundle.spec.stages
    width = max(760, 70 + len(stages) * 150)
    height = 145
    boxes: list[str] = []
    arrows: list[str] = []
    for index, stage in enumerate(stages):
        x = 35 + index * 150
        boxes.append(
            f'<rect x="{x}" y="42" width="120" height="52" rx="12" fill="#111d35" stroke="#68e0cf"/>'
            f'<text x="{x + 60}" y="65" text-anchor="middle" fill="#eff8ff" font-size="11">'
            f'{escape(stage[:24])}</text>'
        )
        if index:
            previous = 35 + (index - 1) * 150 + 120
            arrows.append(
                f'<line x1="{previous}" y1="68" x2="{x}" y2="68" stroke="#f5b84b" stroke-width="2" marker-end="url(#arrow)"/>'
            )
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(bundle.spec.title)} graph">'
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#f5b84b"/></marker></defs>'
        + "".join(arrows)
        + "".join(boxes)
        + "</svg>"
    )


def _fmt(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _acceptance_rows(report: AgentBenchmarkReport) -> str:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for receipt in report.receipts:
        grouped[(receipt.plan.task_id, receipt.plan.condition)].append(float(receipt.accepted))
    tasks = sorted({task for task, _ in grouped})
    rows: list[str] = []
    for task in tasks:
        control = sum(grouped[(task, "control")]) / len(grouped[(task, "control")]) if grouped[(task, "control")] else 0.0
        treatment = sum(grouped[(task, "solutiongraph")]) / len(grouped[(task, "solutiongraph")]) if grouped[(task, "solutiongraph")] else 0.0
        rows.append(
            "<tr>"
            f"<td><code>{escape(task)}</code></td><td>{_fmt(control)}</td><td>{_fmt(treatment)}</td>"
            f'<td><div class="meter"><i style="width:{100 * control:.1f}%"></i></div></td>'
            f'<td><div class="meter treatment"><i style="width:{100 * treatment:.1f}%"></i></div></td>'
            "</tr>"
        )
    return "".join(rows)


def _effect_rows(report: AgentBenchmarkReport) -> str:
    rows: list[str] = []
    for effect in report.effects:
        if effect.scope != "overall":
            continue
        rows.append(
            "<tr>"
            f"<td><code>{escape(effect.harness_id)}</code></td>"
            f"<td><code>{escape(effect.model_id)}</code></td>"
            f"<td>{escape(effect.metric)}</td><td>{effect.pairs}</td>"
            f"<td>{_fmt(effect.control_mean)}</td><td>{_fmt(effect.solutiongraph_mean)}</td>"
            f"<td>{_fmt(effect.oriented_mean_delta)}</td>"
            f"<td>[{_fmt(effect.confidence_lower)}, {_fmt(effect.confidence_upper)}]</td>"
            f"<td><span class=\"pill {escape(effect.inference)}\">{escape(effect.inference)}</span></td>"
            "</tr>"
        )
    return "".join(rows) or '<tr><td colspan="9">No complete paired cells.</td></tr>'


def render_agent_benchmark_html(
    report: AgentBenchmarkReport,
    tasks: tuple[AgentTaskBundle, ...],
) -> str:
    diagrams = "".join(
        f'<details><summary><code>{escape(bundle.spec.id)}</code> — {escape(bundle.spec.title)}</summary>'
        f'{_task_svg(bundle)}<pre>{escape(bundle.spec.mermaid())}</pre></details>'
        for bundle in tasks
        if bundle.spec.id in report.suite.task_ids
    )
    limitations = "".join(f"<li>{escape(item)}</li>" for item in report.limitations)
    decisions = "".join(
        f'<li><strong>{escape(item.state)}</strong> — {escape(item.reason)}</li>'
        for item in report.decisions
    ) or "<li>No winner or promotion decision met the predeclared gates.</li>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(report.suite.title)}</title>
<style>
:root{{--bg:#07101f;--panel:#0d1930;--ink:#edf6ff;--muted:#9fb1c7;--mint:#68e0cf;--gold:#f5b84b;--red:#ff7a8a}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(135deg,#07101f,#101c36);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1320px;margin:auto;padding:40px 24px 80px}} h1{{font-size:clamp(30px,5vw,58px);line-height:1.02;margin:.2em 0}} h2{{margin-top:42px}}
.eyebrow{{color:var(--mint);text-transform:uppercase;letter-spacing:.15em;font-size:12px}} .sub{{max-width:850px;color:var(--muted);font-size:18px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:28px 0}} .stat,.panel,details{{background:rgba(13,25,48,.92);border:1px solid #203657;border-radius:16px;padding:18px}}
.stat b{{display:block;font-size:28px;color:var(--gold)}} table{{width:100%;border-collapse:collapse;background:rgba(13,25,48,.92);border-radius:14px;overflow:hidden}} th,td{{text-align:left;padding:10px;border-bottom:1px solid #203657;vertical-align:top}} th{{color:var(--mint);font-size:12px;text-transform:uppercase}}
code,pre{{font-family:ui-monospace,monospace}} pre{{white-space:pre-wrap;color:#cfe0f5;background:#07101f;padding:14px;border-radius:10px;overflow:auto}} .meter{{height:10px;background:#182944;border-radius:99px;overflow:hidden;min-width:100px}} .meter i{{display:block;height:100%;background:var(--gold)}} .meter.treatment i{{background:var(--mint)}}
.pill{{display:inline-block;padding:3px 8px;border-radius:99px;background:#243654;font-size:12px}} .solutiongraph-superior{{background:#164b42}} .control-superior{{background:#592b37}} .practically-equivalent{{background:#4b3b17}}
details{{margin:12px 0}} summary{{cursor:pointer}} svg{{width:100%;height:auto;min-height:130px}} a{{color:var(--mint)}}
</style></head><body><main>
<div class="eyebrow">SolutionGraph agent benchmark · {escape(report.suite.claim_scope)}</div>
<h1>{escape(report.suite.title)}</h1>
<p class="sub">Matched control versus repository-context trials. JSON is the evidence authority; this HTML is a self-contained projection. Report status: <strong>{escape(report.status)}</strong>.</p>
<section class="stats">
<div class="stat"><span>Planned trials</span><b>{report.planned_trials}</b></div>
<div class="stat"><span>Executed</span><b>{report.executed_trials}</b></div>
<div class="stat"><span>Accepted</span><b>{report.accepted_trials}</b></div>
<div class="stat"><span>Paired effects</span><b>{len(report.effects)}</b></div>
<div class="stat"><span>Unmatched</span><b>{len(report.unmatched_receipt_ids)}</b></div>
</section>
<h2>Acceptance by task</h2>
<table><thead><tr><th>Task</th><th>Control</th><th>SolutionGraph</th><th>Control visual</th><th>Treatment visual</th></tr></thead><tbody>{_acceptance_rows(report)}</tbody></table>
<h2>Overall paired effects</h2>
<table><thead><tr><th>Harness</th><th>Model</th><th>Metric</th><th>Pairs</th><th>Control</th><th>SolutionGraph</th><th>Oriented Δ</th><th>Interval</th><th>Inference</th></tr></thead><tbody>{_effect_rows(report)}</tbody></table>
<h2>Selection and promotion</h2><div class="panel"><ul>{decisions}</ul></div>
<h2>Typed task diagrams</h2>{diagrams}
<h2>Validity threats and limits</h2><div class="panel"><ul>{limitations}</ul></div>
<h2>Evidence identity</h2><div class="panel"><code>{escape(report.evidence_digest)}</code><br><code>{escape(report.suite.digest)}</code></div>
</main></body></html>"""


def write_agent_benchmark_report(
    report: AgentBenchmarkReport,
    tasks: tuple[AgentTaskBundle, ...],
    *,
    json_path: str | Path,
    html_path: str | Path,
) -> tuple[Path, Path]:
    json_target = Path(json_path)
    html_target = Path(html_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    html_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    html_target.write_text(
        render_agent_benchmark_html(report, tasks), encoding="utf-8", newline="\n"
    )
    return json_target, html_target


__all__ = ["render_agent_benchmark_html", "write_agent_benchmark_report"]
