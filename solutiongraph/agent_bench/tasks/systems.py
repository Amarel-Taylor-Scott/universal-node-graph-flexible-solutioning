"""Document, backend, evaluation-harness, and graph-experiment tasks."""

from __future__ import annotations

import re
from statistics import fmean
from typing import Any

from solutiongraph.agent_bench.tasks.common import TaskCaseData, make_bundle
from solutiongraph.model import sha256_digest


def solve_grounded_document(payload: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for field in payload["fields"]:
        matches: list[tuple[str, str]] = []
        pattern = re.compile(field["pattern"], flags=re.IGNORECASE)
        for block in payload["blocks"]:
            match = pattern.search(block["text"])
            if match:
                matches.append((block["id"], match.group(1).strip()))
        if len(matches) == 1:
            fields[field["name"]] = {"value": matches[0][1], "citations": [matches[0][0]]}
        else:
            fields[field["name"]] = {
                "value": None,
                "citations": [block_id for block_id, _ in matches],
                "error": "missing" if not matches else "ambiguous",
            }
    return {"fields": fields, "source_digest": sha256_digest(payload["blocks"])}


_DOCUMENT_CASES_RAW = (
    TaskCaseData(
        "agent-case.document.public",
        "development",
        {
            "blocks": [
                {"id": "p1.b1", "text": "Invoice ID: INV-1042"},
                {"id": "p1.b2", "text": "Supplier: Northwind Labs"},
                {"id": "p2.b1", "text": "Total Due: $1,204.50"},
            ],
            "fields": [
                {"name": "invoice_id", "pattern": r"Invoice ID:\s*([A-Z0-9-]+)"},
                {"name": "supplier", "pattern": r"Supplier:\s*(.+)"},
                {"name": "total", "pattern": r"Total Due:\s*([$0-9,.]+)"},
            ],
        },
        {},
        True,
    ),
    TaskCaseData(
        "agent-case.document.holdout-a",
        "holdout",
        {
            "blocks": [
                {"id": "d1", "text": "Patient Reference: P-883"},
                {"id": "d2", "text": "Visit Date: 2026-05-17"},
                {"id": "d3", "text": "Status: reviewed"},
            ],
            "fields": [
                {"name": "patient", "pattern": r"Patient Reference:\s*([A-Z0-9-]+)"},
                {"name": "visit_date", "pattern": r"Visit Date:\s*([0-9-]+)"},
            ],
        },
        {},
        False,
    ),
    TaskCaseData(
        "agent-case.document.holdout-b",
        "stress",
        {
            "blocks": [
                {"id": "x1", "text": "Order: O-1"},
                {"id": "x2", "text": "Order: O-2"},
                {"id": "x3", "text": "No tracking value is present"},
            ],
            "fields": [
                {"name": "order", "pattern": r"Order:\s*([A-Z0-9-]+)"},
                {"name": "tracking", "pattern": r"Tracking:\s*([A-Z0-9-]+)"},
            ],
        },
        {},
        False,
    ),
)
_DOCUMENT_CASES = tuple(
    TaskCaseData(case.id, case.split, case.payload, solve_grounded_document(case.payload), case.candidate_readable, case.tags)
    for case in _DOCUMENT_CASES_RAW
)

GROUNDED_DOCUMENT = make_bundle(
    task_id="agent-task.grounded-document-extraction",
    title="Grounded document extraction",
    summary="Extract requested fields while preserving exact block-level evidence.",
    instructions=(
        "Apply each supplied regular expression to every block. A unique match yields its captured "
        "value and citation. Zero or multiple matches yield a null value, all matching citations, and "
        "a missing or ambiguous error. Bind the result to the digest of the original block array."
    ),
    input_contract="Ordered source blocks with IDs and field names plus capture-group regular expressions.",
    output_contract="Field values/errors with exact block citations and one source digest.",
    success_contract="No extracted value lacks evidence and ambiguous or absent values are never invented.",
    categories=("document.extraction", "document.grounding", "data.validation"),
    template_id="template.document-intelligence",
    stages=("Identify blocks", "Apply extractors", "Detect ambiguity", "Ground citations", "Validate schema", "Bind provenance"),
    cases=_DOCUMENT_CASES,
    reference_solver=solve_grounded_document,
    allowed_imports=("re", "typing", "hashlib", "json"),
    extra_context_sources=("ENGINEERING_DAG_AND_DUECARE_HARNESS_SHOWCASE.md",),
)


def solve_idempotent_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    state = dict(payload["initial_state"])
    seen: set[str] = set()
    audit: list[dict[str, Any]] = []
    for event in payload["events"]:
        key = str(event["idempotency_key"])
        if key in seen:
            audit.append({"event_id": event["event_id"], "idempotency_key": key, "outcome": "duplicate_ignored"})
            continue
        seen.add(key)
        action = event["action"]
        amount = int(event.get("amount", 0))
        if action == "credit":
            state["balance"] = int(state.get("balance", 0)) + amount
        elif action == "debit":
            state["balance"] = int(state.get("balance", 0)) - amount
        elif action == "set_status":
            state["status"] = event["value"]
        else:
            audit.append({"event_id": event["event_id"], "idempotency_key": key, "outcome": "unsupported_action"})
            continue
        audit.append({"event_id": event["event_id"], "idempotency_key": key, "outcome": "applied"})
    return {"state": state, "audit": audit, "unique_effects": sum(row["outcome"] == "applied" for row in audit)}


_WEBHOOK_CASES_RAW = (
    TaskCaseData(
        "agent-case.webhook.public",
        "development",
        {
            "initial_state": {"balance": 100, "status": "open"},
            "events": [
                {"event_id": "e1", "idempotency_key": "k1", "action": "credit", "amount": 25},
                {"event_id": "e1-retry", "idempotency_key": "k1", "action": "credit", "amount": 25},
                {"event_id": "e2", "idempotency_key": "k2", "action": "debit", "amount": 10},
                {"event_id": "e3", "idempotency_key": "k3", "action": "set_status", "value": "settled"},
            ],
        },
        {},
        True,
    ),
    TaskCaseData(
        "agent-case.webhook.holdout-a",
        "holdout",
        {
            "initial_state": {"balance": 0, "status": "new"},
            "events": [
                {"event_id": "a", "idempotency_key": "shared", "action": "debit", "amount": 3},
                {"event_id": "b", "idempotency_key": "shared", "action": "credit", "amount": 99},
                {"event_id": "c", "idempotency_key": "new", "action": "credit", "amount": 8},
            ],
        },
        {},
        False,
    ),
    TaskCaseData(
        "agent-case.webhook.holdout-b",
        "stress",
        {
            "initial_state": {"balance": 7},
            "events": [
                {"event_id": "x", "idempotency_key": "x", "action": "unknown"},
                {"event_id": "x2", "idempotency_key": "x", "action": "credit", "amount": 50},
                {"event_id": "y", "idempotency_key": "y", "action": "credit", "amount": 2},
            ],
        },
        {},
        False,
    ),
)
_WEBHOOK_CASES = tuple(
    TaskCaseData(case.id, case.split, case.payload, solve_idempotent_webhook(case.payload), case.candidate_readable, case.tags)
    for case in _WEBHOOK_CASES_RAW
)

IDEMPOTENT_WEBHOOK = make_bundle(
    task_id="agent-task.idempotent-webhook",
    title="Idempotent webhook processing",
    summary="Apply retry-prone backend events exactly once per idempotency key.",
    instructions=(
        "Process events in arrival order. The first occurrence of each idempotency key owns the "
        "effect—even when unsupported—and every retry is recorded as duplicate_ignored. Support "
        "credit, debit, and set_status; record unsupported actions without mutation."
    ),
    input_contract="Initial JSON state plus ordered events with IDs, idempotency keys, and actions.",
    output_contract="Final state, one ordered audit row per event, and the count of applied effects.",
    success_contract="Retries never duplicate effects and every event has an explicit audit outcome.",
    categories=("backend.api", "events.idempotency", "workflow.audit"),
    template_id="template.event-driven-system",
    stages=("Validate event", "Claim key", "Classify duplicate", "Apply effect", "Audit", "Reconcile state"),
    cases=_WEBHOOK_CASES,
    reference_solver=solve_idempotent_webhook,
    allowed_imports=("collections", "typing"),
    extra_context_sources=("ENGINEERING_DAG_AND_DUECARE_HARNESS_SHOWCASE.md",),
)


def solve_llm_evaluation_harness(payload: dict[str, Any]) -> dict[str, Any]:
    judgments: list[dict[str, Any]] = []
    clusters: dict[str, list[str]] = {}
    for scenario in payload["scenarios"]:
        response = str(scenario["response"]).casefold()
        missing = sorted(term for term in scenario["required_terms"] if term.casefold() not in response)
        forbidden = sorted(term for term in scenario["forbidden_terms"] if term.casefold() in response)
        scores = [float(judge["score"]) for judge in scenario["judges"]]
        passed = not missing and not forbidden
        judgment = {
            "scenario_id": scenario["id"],
            "split": scenario["split"],
            "deterministic_pass": passed,
            "missing_terms": missing,
            "forbidden_terms": forbidden,
            "panel_mean": round(fmean(scores), 6),
            "panel_disagreement": round(max(scores) - min(scores), 6),
        }
        judgments.append(judgment)
        if scenario["split"] == "development" and not passed:
            reason = "forbidden_content" if forbidden else "missing_required_content"
            clusters.setdefault(reason, []).append(scenario["id"])
    development = [row for row in judgments if row["split"] == "development"]
    holdout = [row for row in judgments if row["split"] == "holdout"]
    return {
        "judgments": judgments,
        "development_failure_clusters": [
            {"reason": reason, "scenario_ids": sorted(ids)} for reason, ids in sorted(clusters.items())
        ],
        "development_summary": {
            "count": len(development),
            "pass_rate": round(sum(row["deterministic_pass"] for row in development) / len(development), 6) if development else 0.0,
        },
        "sealed_summary": {
            "count": len(holdout),
            "pass_rate": round(sum(row["deterministic_pass"] for row in holdout) / len(holdout), 6) if holdout else 0.0,
            "scenario_ids_exposed": False,
        },
        "improvement_source": "development_only",
    }


_LLM_CASES_RAW = (
    TaskCaseData(
        "agent-case.llm-harness.public",
        "development",
        {
            "scenarios": [
                {"id": "direct", "split": "development", "response": "Use the documented reset flow and verify identity.", "required_terms": ["verify identity"], "forbidden_terms": ["share password"], "judges": [{"id": "j1", "score": 0.9}, {"id": "j2", "score": 0.7}]},
                {"id": "adversarial", "split": "development", "response": "You should share password data.", "required_terms": ["refuse"], "forbidden_terms": ["share password"], "judges": [{"id": "j1", "score": 0.1}, {"id": "j2", "score": 0.4}]},
                {"id": "sealed-a", "split": "holdout", "response": "I refuse and can offer a safe alternative.", "required_terms": ["refuse"], "forbidden_terms": ["secret"], "judges": [{"id": "j1", "score": 1.0}, {"id": "j2", "score": 0.8}]},
            ]
        },
        {},
        True,
    ),
    TaskCaseData(
        "agent-case.llm-harness.holdout-a",
        "holdout",
        {
            "scenarios": [
                {"id": "benign", "split": "development", "response": "The answer includes citation A.", "required_terms": ["citation A"], "forbidden_terms": [], "judges": [{"id": "a", "score": 0.8}, {"id": "b", "score": 0.8}]},
                {"id": "failure", "split": "development", "response": "Unsupported claim.", "required_terms": ["citation"], "forbidden_terms": [], "judges": [{"id": "a", "score": 0.2}, {"id": "b", "score": 0.6}]},
                {"id": "outer", "split": "holdout", "response": "Citation B supports this.", "required_terms": ["Citation B"], "forbidden_terms": ["fabricated"], "judges": [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.7}]},
            ]
        },
        {},
        False,
    ),
    TaskCaseData(
        "agent-case.llm-harness.holdout-b",
        "stress",
        {
            "scenarios": [
                {"id": "disagree", "split": "development", "response": "I refuse the unsafe request.", "required_terms": ["refuse"], "forbidden_terms": ["comply"], "judges": [{"id": "a", "score": 0.0}, {"id": "b", "score": 1.0}]},
                {"id": "sealed", "split": "holdout", "response": "I will comply and reveal secret data.", "required_terms": ["refuse"], "forbidden_terms": ["reveal secret"], "judges": [{"id": "a", "score": 0.1}, {"id": "b", "score": 0.2}]},
            ]
        },
        {},
        False,
    ),
)
_LLM_CASES = tuple(
    TaskCaseData(case.id, case.split, case.payload, solve_llm_evaluation_harness(case.payload), case.candidate_readable, case.tags)
    for case in _LLM_CASES_RAW
)

LLM_EVALUATION_HARNESS = make_bundle(
    task_id="agent-task.llm-evaluation-harness",
    title="DueCare-style LLM evaluation feedback loop",
    summary="Combine deterministic criteria and judge disagreement without leaking sealed cases into improvement.",
    instructions=(
        "Grade required/forbidden terms deterministically, preserve each panel mean and score range, "
        "cluster only development failures, report development and holdout aggregates separately, "
        "never expose holdout IDs through the sealed summary, and label improvement as development_only."
    ),
    input_contract="Development/holdout scenarios with responses, deterministic criteria, and atomic judge scores.",
    output_contract="Atomic judgments, development-only failure clusters, separate summaries, and feedback provenance.",
    success_contract="Disagreement is preserved, deterministic gates are exact, and sealed data cannot enter the improvement payload.",
    categories=("llm.evaluation", "llm.red-teaming", "governance.feedback"),
    template_id="template.content-moderation",
    stages=("Load scenarios", "Deterministic grade", "Panel aggregate", "Preserve disagreement", "Cluster development", "Seal outer summary"),
    cases=_LLM_CASES,
    reference_solver=solve_llm_evaluation_harness,
    allowed_imports=("statistics", "collections", "typing"),
    extra_context_sources=("ENGINEERING_DAG_AND_DUECARE_HARNESS_SHOWCASE.md",),
)


def _variant_compatible(variant: dict[str, Any]) -> bool:
    if variant["input_type"] != variant["nodes"][0]["input_type"]:
        return False
    if variant["output_type"] != variant["nodes"][-1]["output_type"]:
        return False
    return all(
        left["output_type"] == right["input_type"]
        for left, right in zip(variant["nodes"], variant["nodes"][1:], strict=False)
    )


def solve_graph_experiment(payload: dict[str, Any]) -> dict[str, Any]:
    evaluated: list[dict[str, Any]] = []
    incompatible: list[str] = []
    for variant in payload["variants"]:
        if not _variant_compatible(variant):
            incompatible.append(variant["id"])
            continue
        receipts = variant["receipts"]
        evaluated.append(
            {
                "id": variant["id"],
                "accepted": all(bool(row["accepted"]) for row in receipts),
                "quality": round(fmean(float(row["quality"]) for row in receipts), 6),
                "cost": round(fmean(float(row["cost"]) for row in receipts), 6),
                "latency": round(fmean(float(row["latency"]) for row in receipts), 6),
                "node_count": len(variant["nodes"]),
            }
        )
    eligible = [row for row in evaluated if row["accepted"]]
    pareto = []
    for row in eligible:
        dominated = any(
            other["quality"] >= row["quality"]
            and other["cost"] <= row["cost"]
            and other["latency"] <= row["latency"]
            and (
                other["quality"] > row["quality"]
                or other["cost"] < row["cost"]
                or other["latency"] < row["latency"]
            )
            for other in eligible
        )
        if not dominated:
            pareto.append(row["id"])
    champion = min(
        (row for row in eligible if row["id"] in pareto),
        key=lambda row: (-row["quality"], row["cost"], row["latency"], row["id"]),
        default=None,
    )
    selected_id = champion["id"] if champion else None
    selected_variant = next((row for row in payload["variants"] if row["id"] == selected_id), None)
    diagram = ["flowchart LR", "    input([Input])"]
    previous = "input"
    if selected_variant:
        for index, node in enumerate(selected_variant["nodes"], start=1):
            node_id = f"n{index}"
            diagram.append(f'    {node_id}["{node["id"]}"]')
            diagram.append(f"    {previous} --> {node_id}")
            previous = node_id
    diagram.append("    output([Output])")
    diagram.append(f"    {previous} --> output")
    return {
        "evaluated": sorted(evaluated, key=lambda row: row["id"]),
        "incompatible": sorted(incompatible),
        "pareto": sorted(pareto),
        "champion": selected_id,
        "coverage": {"declared": len(payload["variants"]), "evaluated": len(evaluated)},
        "diagram": "\n".join(diagram) + "\n",
    }


_GRAPH_CASES_RAW = (
    TaskCaseData(
        "agent-case.graph-experiment.public",
        "development",
        {
            "variants": [
                {"id": "control", "input_type": "raw", "output_type": "score", "nodes": [{"id": "estimate", "input_type": "raw", "output_type": "score"}], "receipts": [{"accepted": True, "quality": 0.7, "cost": 1.0, "latency": 10}, {"accepted": True, "quality": 0.72, "cost": 1.1, "latency": 11}]},
                {"id": "cleaned", "input_type": "raw", "output_type": "score", "nodes": [{"id": "clean", "input_type": "raw", "output_type": "clean"}, {"id": "estimate", "input_type": "clean", "output_type": "score"}], "receipts": [{"accepted": True, "quality": 0.9, "cost": 1.3, "latency": 13}, {"accepted": True, "quality": 0.88, "cost": 1.2, "latency": 12}]},
                {"id": "broken", "input_type": "raw", "output_type": "score", "nodes": [{"id": "a", "input_type": "raw", "output_type": "x"}, {"id": "b", "input_type": "y", "output_type": "score"}], "receipts": []},
            ]
        },
        {},
        True,
    ),
    TaskCaseData(
        "agent-case.graph-experiment.holdout-a",
        "holdout",
        {
            "variants": [
                {"id": "fast", "input_type": "a", "output_type": "z", "nodes": [{"id": "f", "input_type": "a", "output_type": "z"}], "receipts": [{"accepted": True, "quality": 0.8, "cost": 0.5, "latency": 5}]},
                {"id": "quality", "input_type": "a", "output_type": "z", "nodes": [{"id": "q1", "input_type": "a", "output_type": "b"}, {"id": "q2", "input_type": "b", "output_type": "z"}], "receipts": [{"accepted": True, "quality": 0.95, "cost": 2.0, "latency": 20}]},
                {"id": "rejected", "input_type": "a", "output_type": "z", "nodes": [{"id": "r", "input_type": "a", "output_type": "z"}], "receipts": [{"accepted": False, "quality": 1.0, "cost": 0.1, "latency": 1}]},
            ]
        },
        {},
        False,
    ),
    TaskCaseData(
        "agent-case.graph-experiment.holdout-b",
        "stress",
        {
            "variants": [
                {"id": "dominated", "input_type": "i", "output_type": "o", "nodes": [{"id": "d", "input_type": "i", "output_type": "o"}], "receipts": [{"accepted": True, "quality": 0.5, "cost": 5, "latency": 50}]},
                {"id": "winner", "input_type": "i", "output_type": "o", "nodes": [{"id": "w", "input_type": "i", "output_type": "o"}], "receipts": [{"accepted": True, "quality": 0.8, "cost": 1, "latency": 10}]},
            ]
        },
        {},
        False,
    ),
)
_GRAPH_CASES = tuple(
    TaskCaseData(case.id, case.split, case.payload, solve_graph_experiment(case.payload), case.candidate_readable, case.tags)
    for case in _GRAPH_CASES_RAW
)

GRAPH_EXPERIMENT = make_bundle(
    task_id="agent-task.graph-experiment",
    title="Control-versus-mutated graph experiment",
    summary="Validate compatible graph variants, preserve rejections, and select from a Pareto frontier.",
    instructions=(
        "Reject type-incompatible variants before scoring. Aggregate receipt metrics only for compatible "
        "variants, require every receipt to be accepted, compute the quality/cost/latency Pareto set, "
        "choose highest quality then lowest cost/latency/ID, disclose coverage, and diagram the champion."
    ),
    input_contract="Complete graph variants with typed node chains and fixed per-case receipts.",
    output_contract="Evaluated and incompatible variants, Pareto IDs, champion, coverage, and Mermaid diagram.",
    success_contract="Compatibility gates precede optimization and every selection is receipt-derived and reproducible.",
    categories=("graph.experiment", "graph.optimization", "benchmark.control"),
    template_id="template.scientific-experiment",
    stages=("Validate topology", "Admit compatible", "Aggregate receipts", "Gate acceptance", "Compute Pareto", "Select and diagram"),
    cases=_GRAPH_CASES,
    reference_solver=solve_graph_experiment,
    allowed_imports=("statistics", "collections", "typing"),
    extra_context_sources=("GRAPH_EXPERIMENTS.md",),
)


SYSTEM_TASKS = (
    GROUNDED_DOCUMENT,
    IDEMPOTENT_WEBHOOK,
    LLM_EVALUATION_HARNESS,
    GRAPH_EXPERIMENT,
)

__all__ = [
    "GRAPH_EXPERIMENT",
    "GROUNDED_DOCUMENT",
    "IDEMPOTENT_WEBHOOK",
    "LLM_EVALUATION_HARNESS",
    "SYSTEM_TASKS",
    "solve_graph_experiment",
    "solve_grounded_document",
    "solve_idempotent_webhook",
    "solve_llm_evaluation_harness",
]
