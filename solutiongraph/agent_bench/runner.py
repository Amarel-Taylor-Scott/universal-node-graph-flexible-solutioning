"""End-to-end allocation, harness delivery, evaluation, receipts, and reports."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from solutiongraph.agent_bench.analysis import AgentBenchmarkReport, analyze_agent_benchmark
from solutiongraph.agent_bench.evaluation import CandidateEvaluation, evaluate_candidate
from solutiongraph.agent_bench.harness import HarnessRun, load_usage_metrics, run_harness
from solutiongraph.agent_bench.journal import AgentTrialJournal
from solutiongraph.agent_bench.model import (
    TRIAL_LIFECYCLE,
    AgentBenchmarkSuite,
    AgentTrialReceipt,
    HarnessProfile,
    TrialPlan,
    stable_trial_id,
)
from solutiongraph.agent_bench.reporting import write_agent_benchmark_report
from solutiongraph.agent_bench.tasks import REFERENCE_AGENT_TASKS
from solutiongraph.agent_bench.workspace import materialize_workspace
from solutiongraph.model import sha256_digest


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class AgentBenchmarkRunResult:
    report: AgentBenchmarkReport
    output_dir: Path
    report_json: Path
    report_html: Path
    receipt_journal: Path
    run_manifest: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.report.status,
            "output_dir": str(self.output_dir),
            "report_json": str(self.report_json),
            "report_html": str(self.report_html),
            "receipt_journal": str(self.receipt_journal),
            "run_manifest": str(self.run_manifest),
            "planned_trials": self.report.planned_trials,
            "executed_trials": self.report.executed_trials,
            "accepted_trials": self.report.accepted_trials,
            "paired_effects": len(self.report.effects),
            "decisions": [item.to_dict() for item in self.report.decisions],
            "evidence_digest": self.report.evidence_digest,
        }


def iter_trial_plans(
    suite: AgentBenchmarkSuite,
    tasks=REFERENCE_AGENT_TASKS,
) -> Iterator[TrialPlan]:
    """Stream the complete enabled Cartesian allocation with no hidden cap."""
    task_by_id = {bundle.spec.id: bundle for bundle in tasks}
    problems = suite.validate(tuple(task_by_id))
    if problems:
        raise ValueError("invalid agent benchmark suite: " + "; ".join(problems))
    cell_number = 0
    for task_id in suite.task_ids:
        task = task_by_id[task_id]
        for harness in suite.enabled_harnesses:
            for model in suite.models_for_harness(harness):
                for seed in suite.seeds:
                    for repetition in range(suite.repetitions):
                        conditions = (
                            suite.conditions
                            if cell_number % 2 == 0
                            else tuple(reversed(suite.conditions))
                        )
                        cell_number += 1
                        for condition in conditions:
                            yield TrialPlan(
                                id=stable_trial_id(
                                    suite.id,
                                    task_id,
                                    condition,
                                    harness.id,
                                    model.id,
                                    seed,
                                    repetition,
                                ),
                                suite_digest=suite.digest,
                                task_id=task_id,
                                task_digest=task.spec.digest,
                                condition=condition,
                                harness_id=harness.id,
                                harness_version=harness.version,
                                model_id=model.id,
                                model_revision=model.revision,
                                seed=seed,
                                repetition=repetition,
                                budget=suite.budget,
                            )


def _failed_harness(profile: HarnessProfile, message: str) -> HarnessRun:
    now = _utc_now()
    payload = message.encode("utf-8", errors="replace")
    digest = "sha256:" + __import__("hashlib").sha256(payload).hexdigest()
    return HarnessRun(
        started_at=now,
        ended_at=now,
        wall_seconds=0.0,
        exit_code=None,
        timed_out=False,
        command_digest=sha256_digest({"harness": profile.id, "failure": type(message).__name__}),
        stdout=b"",
        stderr=payload,
        stdout_digest=sha256_digest(""),
        stderr_digest=digest,
        environment_variable_names=(),
        budget_enforcement=("runner.preflight-or-invocation-failure",),
        isolation=profile.isolation,
        delivered=False,
        problems=(message,),
    )


def _empty_evaluation(bundle) -> CandidateEvaluation:
    return CandidateEvaluation(
        delivered=False,
        valid=False,
        scored=False,
        accepted=False,
        artifacts=(),
        case_results=(),
        metrics=(
            ("oracle_score", 0.0),
            ("case_pass_rate", 0.0),
            ("development_pass_rate", 0.0),
            ("holdout_pass_rate", 0.0),
            ("determinism_rate", 0.0),
            ("artifact_completeness", 0.0),
            ("documentation_score", 0.0),
            ("diagram_score", 0.0),
            ("protected_integrity", 1.0),
        ),
        problems=(f"{bundle.spec.id}: candidate artifacts were not delivered",),
    )


def _receipt(
    plan: TrialPlan,
    manifest,
    harness: HarnessRun,
    evaluation: CandidateEvaluation,
    usage: tuple[tuple[str, float], ...],
) -> AgentTrialReceipt:
    harness_success = harness.exit_code == 0 and not harness.timed_out
    lifecycle = ["ATTEMPTED"]
    if harness.delivered:
        lifecycle.append("DELIVERED")
        if harness_success and evaluation.valid:
            lifecycle.append("VALID")
            if evaluation.scored:
                lifecycle.append("SCORED")
                if evaluation.accepted:
                    lifecycle.append("ACCEPTED")
    metrics = dict(evaluation.metrics)
    metrics["wall_seconds"] = harness.wall_seconds
    metrics["harness_success"] = float(harness_success)
    metrics.update(dict(usage))
    receipt = AgentTrialReceipt(
        id=f"agent-receipt.{plan.id.removeprefix('agent-trial.')}",
        plan=plan,
        plan_digest=plan.digest,
        prompt_digest=manifest.prompt_digest,
        context_digest=manifest.context_digest,
        context_bytes=manifest.context_bytes,
        workspace_manifest_digest=manifest.digest,
        lifecycle=tuple(lifecycle),
        started_at=harness.started_at,
        ended_at=harness.ended_at,
        wall_seconds=harness.wall_seconds,
        exit_code=harness.exit_code,
        timed_out=harness.timed_out,
        command_digest=harness.command_digest,
        stdout_digest=harness.stdout_digest,
        stderr_digest=harness.stderr_digest,
        artifacts=evaluation.artifacts,
        metrics=tuple(sorted(metrics.items())),
        accepted=lifecycle == list(TRIAL_LIFECYCLE),
        problems=tuple(dict.fromkeys((*harness.problems, *evaluation.problems))),
        environment_variable_names=harness.environment_variable_names,
        budget_enforcement=harness.budget_enforcement,
        isolation=harness.isolation,
    )
    problems = receipt.validate()
    if problems:
        raise ValueError("invalid agent trial receipt: " + "; ".join(problems))
    return receipt


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _resolve_repo_root(
    repo_root: str | Path | None,
    tasks,
) -> Path:
    required = tuple(
        dict.fromkeys(
            source
            for bundle in tasks
            for source in bundle.spec.context_sources
        )
    )
    if repo_root is not None:
        candidates = (Path(repo_root).resolve(),)
    else:
        cwd = Path.cwd().resolve()
        candidates = (*cwd.parents, cwd, Path(__file__).parents[2].resolve())
        candidates = tuple(dict.fromkeys(reversed(candidates)))
    for candidate in candidates:
        if candidate.is_dir() and all((candidate / source).is_file() for source in required):
            return candidate
    missing = required[0] if required else "AGENT_PLAYBOOK.md"
    raise FileNotFoundError(
        "could not locate the repository context root; run from a source checkout "
        f"or pass repo_root/--repo-root (required file example: {missing})"
    )


def run_agent_benchmark(
    suite: AgentBenchmarkSuite,
    output_dir: str | Path,
    *,
    repo_root: str | Path | None = None,
    allow_external: bool = False,
    max_trials: int | None = None,
    tasks=REFERENCE_AGENT_TASKS,
) -> AgentBenchmarkRunResult:
    """Run the declared matrix and retain every successful and failed receipt."""
    task_by_id = {bundle.spec.id: bundle for bundle in tasks}
    if len(task_by_id) != len(tasks):
        raise ValueError("agent benchmark task IDs must be unique")
    problems = suite.validate(tuple(task_by_id))
    if problems:
        raise ValueError("invalid agent benchmark suite: " + "; ".join(problems))
    if max_trials is not None and max_trials <= 0:
        raise ValueError("max_trials must be positive or omitted")
    if any(item.kind == "command" for item in suite.enabled_harnesses) and not allow_external:
        raise PermissionError("enabled command harnesses require --allow-external")
    output_dir = Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"benchmark output already exists: {output_dir}")
    repo_root = _resolve_repo_root(repo_root, tuple(task_by_id.values()))
    all_plans = tuple(iter_trial_plans(suite, tasks))
    selected_plans = all_plans if max_trials is None else all_plans[:max_trials]
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        (temporary / "workspaces").mkdir()
        (temporary / "workspace-manifests").mkdir()
        (temporary / "evaluations").mkdir()
        (temporary / "receipts").mkdir()
        (temporary / "diagrams").mkdir()
        _write_json(temporary / "suite.json", suite.to_dict())
        for task_id in suite.task_ids:
            task = task_by_id[task_id]
            (temporary / "diagrams" / f"{task_id}.mmd").write_text(
                task.spec.mermaid(), encoding="utf-8", newline="\n"
            )
        run_manifest = {
            "run_model_version": "0.1",
            "suite_id": suite.id,
            "suite_digest": suite.digest,
            "total_cartesian_trials": len(all_plans),
            "allocated_trials": len(selected_plans),
            "heuristic_skipped_trials": 0,
            "budget_skipped_trials": len(all_plans) - len(selected_plans),
            "unvisited_trials": len(all_plans) - len(selected_plans),
            "complete": len(selected_plans) == len(all_plans),
            "allow_external": allow_external,
            "plans": [plan.to_dict() for plan in selected_plans],
        }
        _write_json(temporary / "run-manifest.json", run_manifest)
        harnesses = {item.id: item for item in suite.harnesses}
        models = {item.id: item for item in suite.models}
        journal_path = temporary / "trial-receipts.jsonl"
        journal = AgentTrialJournal(journal_path)
        receipts: list[AgentTrialReceipt] = []
        for plan in selected_plans:
            bundle = task_by_id[plan.task_id]
            harness_profile = harnesses[plan.harness_id]
            model = models[plan.model_id]
            workspace = temporary / "workspaces" / plan.id
            manifest = materialize_workspace(workspace, repo_root, bundle, plan)
            _write_json(
                temporary / "workspace-manifests" / f"{plan.id}.json",
                manifest.to_dict(),
            )
            try:
                harness_run = run_harness(
                    workspace,
                    bundle,
                    plan,
                    manifest,
                    harness_profile,
                    model,
                    allow_external=allow_external,
                )
            except Exception as exc:
                harness_run = _failed_harness(
                    harness_profile,
                    f"{type(exc).__name__}: {exc}",
                )
            evaluation = (
                evaluate_candidate(
                    workspace,
                    bundle,
                    manifest,
                    suite.budget,
                    seed=plan.seed,
                    fixture=harness_profile.kind == "fixture",
                )
                if harness_run.delivered
                else _empty_evaluation(bundle)
            )
            try:
                usage = load_usage_metrics(workspace, suite.budget)
            except (OSError, ValueError) as exc:
                usage = ()
                evaluation = CandidateEvaluation(
                    evaluation.delivered,
                    evaluation.valid,
                    evaluation.scored,
                    False,
                    evaluation.artifacts,
                    evaluation.case_results,
                    evaluation.metrics,
                    (*evaluation.problems, f"invalid usage evidence: {exc}"),
                )
            receipt = _receipt(plan, manifest, harness_run, evaluation, usage)
            journal.append(receipt)
            receipts.append(receipt)
            _write_json(temporary / "receipts" / f"{receipt.id}.json", receipt.to_dict())
            _write_json(
                temporary / "evaluations" / f"{plan.id}.json",
                {"trial_plan": plan.to_dict(), "harness": harness_run.to_dict(), "evaluation": evaluation.to_dict()},
            )
        report = analyze_agent_benchmark(
            suite,
            tuple(receipts),
            planned_trials=len(all_plans),
            task_specs=tuple(task_by_id[task_id].spec for task_id in suite.task_ids),
        )
        write_agent_benchmark_report(
            report,
            tuple(task_by_id[task_id] for task_id in suite.task_ids),
            json_path=temporary / "report.json",
            html_path=temporary / "report.html",
        )
        if output_dir.exists() or output_dir.is_symlink():
            raise FileExistsError(f"benchmark output already exists: {output_dir}")
        temporary.rename(output_dir)
    except BaseException:
        failed = output_dir.with_name(output_dir.name + ".failed")
        if not failed.exists() and temporary.exists():
            temporary.rename(failed)
        else:
            shutil.rmtree(temporary, ignore_errors=True)
        raise
    return AgentBenchmarkRunResult(
        report=report,
        output_dir=output_dir,
        report_json=output_dir / "report.json",
        report_html=output_dir / "report.html",
        receipt_journal=output_dir / "trial-receipts.jsonl",
        run_manifest=output_dir / "run-manifest.json",
    )


__all__ = ["AgentBenchmarkRunResult", "iter_trial_plans", "run_agent_benchmark"]
