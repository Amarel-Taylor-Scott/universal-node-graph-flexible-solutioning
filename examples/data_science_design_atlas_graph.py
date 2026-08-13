"""Compile and execute the evidence-driven data-science design graph.

The fixture acts as a deterministic human responder so the complete example is
dependency-free. Replace only the answer-set producer to integrate a UI, agent,
or model harness; the plan and dossier contracts stay unchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from solutiongraph import (
    CallableVerifier,
    Compiler,
    ExecutionPolicy,
    ReferenceExecutor,
    RuntimeRegistry,
    SubprocessPythonRuntime,
    VerificationResult,
)
from solutiongraph.design_atlas import DecisionAnswer, DesignPlanner
from solutiongraph.design_atlas.node_pack import (
    DESIGN_ATLAS_CANDIDATES,
    DESIGN_ATLAS_PROGRAM,
    DESIGN_ATLAS_REGISTRY,
)
from solutiongraph.design_atlas.packs import DESIGN_QUESTION_BY_ID
from solutiongraph.design_atlas.profiling import context_from_profile
from solutiongraph.interrogation.profiling import map_semantic_fields, profile_records
from solutiongraph.question_packs import REFERENCE_CONCEPTS


def verify_report(context) -> VerificationResult:
    """Independently require a complete accepted E1 dossier and all renderings."""
    report = context.outputs.get("report_bundle", {})
    payload = report.get("payload", {}) if isinstance(report, dict) else {}
    dossier = payload.get("dossier", {}) if isinstance(payload, dict) else {}
    decisions = dossier.get("decisions", ()) if isinstance(dossier, dict) else ()
    accepted = (
        len(decisions) == 12
        and all(item.get("status") == "accepted" for item in decisions)
        and payload.get("plan", {}).get("summary", {}).get("selected") == 12
        and report.get("markdown", "").startswith("# Data-science design plan")
        and report.get("html", "").startswith("<!doctype html>")
    )
    return VerificationResult(
        accepted=accepted,
        outcome="complete-evidence-bound-report" if accepted else "report-contract-failed",
        metrics={"accepted_decisions": float(len(decisions))},
    )


def _candidate(node_id: str, parameters: dict) -> str:
    return next(
        candidate.id
        for candidate in DESIGN_ATLAS_CANDIDATES
        if candidate.node_id == node_id and dict(candidate.parameters) == parameters
    )


def run(output_dir: Path | None = None, runtime: str = "in-process") -> dict:
    if runtime not in {"in-process", "subprocess"}:
        raise ValueError("runtime must be in-process or subprocess")
    records = [
        {
            "customer_id": "c1",
            "state": "MA",
            "event_date": "2026-01-01",
            "renewal_value": 120.0,
        },
        {
            "customer_id": "c2",
            "state": "NY",
            "event_date": "2026-02-01",
            "renewal_value": 95.0,
        },
        {
            "customer_id": "c3",
            "state": "MA",
            "event_date": "2026-03-01",
            "renewal_value": None,
        },
    ]
    profile = profile_records(records, source_id="source.design-atlas-graph-example")
    field_map = map_semantic_fields(profile, REFERENCE_CONCEPTS, strategy="conservative")
    task_request = {
        "task_type": "regression",
        "objective": "Predict renewal value at the next customer renewal event.",
        "target_name": "renewal_value",
        "group_field": "customer_id",
        "risk_tier": "risk.medium",
    }
    context = context_from_profile(profile, field_map, **task_request)
    expected_plan = DesignPlanner().plan(
        context,
        effort="E1",
        available_modes=("human",),
        granted_permissions=("human.review",),
        random_seed=0,
    )
    answers = [
        DecisionAnswer(
            question_id=item.question_id,
            choice_id=DESIGN_QUESTION_BY_ID[item.question_id].choices[0].id,
            rationale="Fixture decision against the frozen task contract.",
            evidence_refs=(f"artifact://example/{item.question_id}.json",),
            confidence=0.8,
            responder="responder.example-human",
        ).to_dict()
        for item in expected_plan.items
        if item.status == "selected"
    ]

    compiler = Compiler()
    space = compiler.admit(DESIGN_ATLAS_PROGRAM, DESIGN_ATLAS_REGISTRY)
    frozen = compiler.compile(
        DESIGN_ATLAS_PROGRAM,
        DESIGN_ATLAS_REGISTRY,
        space,
        {
            "context": _candidate("design-atlas.derive-context", {}),
            "plan": _candidate(
                "design-atlas.plan-human-review",
                {"effort_level": "E1", "random_seed": 0},
            ),
            "resolve": _candidate(
                "design-atlas.resolve-answers",
                {"resolution_policy": "evidence-required"},
            ),
            "report": _candidate("design-atlas.render-report", {}),
        },
    )
    executor = (
        ReferenceExecutor()
        if runtime == "in-process"
        else ReferenceExecutor(
            runtimes=RuntimeRegistry({
                "python": SubprocessPythonRuntime(max_memory_mb=None),
            })
        )
    )
    result = executor.execute(
        frozen,
        DESIGN_ATLAS_PROGRAM,
        DESIGN_ATLAS_REGISTRY,
        space,
        {
            "dataset_profile": profile.to_dict(),
            "semantic_field_map": field_map.to_dict(),
            "task_request": task_request,
            "answer_set": {"plan_digest": expected_plan.digest, "answers": answers},
        },
        task_case_id="case.design-atlas-graph-example",
        verifier=CallableVerifier("verifier.design-atlas-example", verify_report),
        policy=ExecutionPolicy(
            granted_permissions=("human.review",),
            allow_in_process_python=runtime == "in-process",
        ),
    )
    if not result.ok:
        raise RuntimeError(result.error or result.receipt.failure_class)

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        report = result.outputs["report_bundle"]
        (output_dir / "design-plan.json").write_text(
            json.dumps(report["payload"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "design-plan.md").write_text(report["markdown"], encoding="utf-8")
        (output_dir / "design-plan.html").write_text(report["html"], encoding="utf-8")

    return {
        "outcome": result.receipt.outcome,
        "plan_digest": expected_plan.digest,
        "visible_questions": len(result.outputs["design_plan"]["items"]),
        "accepted_decisions": len(result.outputs["design_dossier"]["decisions"]),
        "node_receipts": len(result.receipt.node_receipts),
        "route_count_upper_bound": space.route_count_upper_bound,
        "report_output": str(output_dir) if output_dir is not None else "not written",
        "runtime": runtime,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--runtime", choices=("in-process", "subprocess"), default="in-process")
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir, args.runtime), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
