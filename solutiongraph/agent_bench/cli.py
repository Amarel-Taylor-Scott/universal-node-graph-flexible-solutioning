"""CLI adapter for coding-agent benchmark planning, execution, and evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from solutiongraph.agent_bench.config import (
    command_matrix_example_suite,
    load_agent_benchmark_suite,
    reference_agent_benchmark_suite,
    write_agent_benchmark_suite,
)
from solutiongraph.agent_bench.journal import AgentTrialJournal
from solutiongraph.agent_bench.runner import (
    AgentBenchmarkRunResult,
    iter_trial_plans,
    run_agent_benchmark,
)
from solutiongraph.agent_bench.tasks import REFERENCE_AGENT_TASKS


def _tasks(as_json: bool) -> int:
    rows = [
        {
            "id": bundle.spec.id,
            "title": bundle.spec.title,
            "categories": list(bundle.spec.categories),
            "template_id": bundle.spec.template_id,
            "stages": list(bundle.spec.stages),
            "public_cases": len(bundle.spec.public_case_ids),
            "sealed_cases": len(bundle.spec.sealed_case_ids),
            "metric": bundle.spec.score_metric,
        }
        for bundle in REFERENCE_AGENT_TASKS
    ]
    if as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    print("ID\tCASES\tSTAGES\tTEMPLATE\tTITLE")
    for row in rows:
        cases = f"{row['public_cases']}+{row['sealed_cases']} sealed"
        print(
            f"{row['id']}\t{cases}\t{len(row['stages'])}\t"
            f"{row['template_id']}\t{row['title']}"
        )
    return 0


def _example_config(output: Path) -> int:
    suite = command_matrix_example_suite()
    target = write_agent_benchmark_suite(suite, output)
    print(
        f"wrote {suite.id} to {target}; enable and pin command harnesses/models "
        "before claiming model evidence"
    )
    return 0


def _plan(config: Path, as_json: bool) -> int:
    suite = load_agent_benchmark_suite(config)
    plans = tuple(iter_trial_plans(suite))
    payload = {
        "suite_id": suite.id,
        "suite_digest": suite.digest,
        "claim_scope": suite.claim_scope,
        "task_count": len(suite.task_ids),
        "conditions": list(suite.conditions),
        "enabled_harnesses": [item.id for item in suite.enabled_harnesses],
        "enabled_models": [item.id for item in suite.enabled_models],
        "compatible_harness_model_pairs": [
            [harness.id, model.id]
            for harness in suite.enabled_harnesses
            for model in suite.models_for_harness(harness)
        ],
        "seeds": list(suite.seeds),
        "repetitions": suite.repetitions,
        "total_trials": len(plans),
        "plans": [plan.to_dict() for plan in plans],
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(
        f"{suite.id}: tasks={len(suite.task_ids)} pairs="
        f"{len(payload['compatible_harness_model_pairs'])} seeds={len(suite.seeds)} "
        f"repetitions={suite.repetitions} trials={len(plans)} claim={suite.claim_scope}"
    )
    for harness, model in payload["compatible_harness_model_pairs"]:
        print(f"- {harness} × {model}")
    return 0


def _print_result(result: AgentBenchmarkRunResult, as_json: bool) -> int:
    payload = result.to_dict()
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{payload['status']}: executed={payload['executed_trials']}/"
            f"{payload['planned_trials']} accepted={payload['accepted_trials']} "
            f"paired_effects={payload['paired_effects']}"
        )
        print(f"JSON evidence: {payload['report_json']}")
        print(f"HTML analysis: {payload['report_html']}")
        print(f"Receipt journal: {payload['receipt_journal']}")
    return 0 if result.report.executed_trials == result.report.planned_trials else 1


def _smoke(output: Path, repo_root: Path | None, as_json: bool) -> int:
    result = run_agent_benchmark(
        reference_agent_benchmark_suite(), output, repo_root=repo_root
    )
    return _print_result(result, as_json)


def _run(
    config: Path,
    output: Path,
    allow_external: bool,
    max_trials: int | None,
    repo_root: Path | None,
    as_json: bool,
) -> int:
    result = run_agent_benchmark(
        load_agent_benchmark_suite(config),
        output,
        repo_root=repo_root,
        allow_external=allow_external,
        max_trials=max_trials,
    )
    return _print_result(result, as_json)


def _journal_verify(path: Path, as_json: bool) -> int:
    journal = AgentTrialJournal(path)
    status = journal.status()
    receipts = journal.receipts()
    payload = {
        "valid": True,
        "receipt_count": status.receipt_count,
        "head_digest": status.head_digest,
        "accepted_receipts": sum(receipt.accepted for receipt in receipts),
        "suite_digests": sorted({receipt.plan.suite_digest for receipt in receipts}),
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"valid agent benchmark journal: receipts={status.receipt_count} "
            f"accepted={payload['accepted_receipts']} head={status.head_digest}"
        )
    return 0


def add_agent_bench_parser(commands: argparse._SubParsersAction) -> None:
    agent_bench = commands.add_parser(
        "agent-bench",
        help="Plan and run matched control/SolutionGraph coding-agent experiments",
    )
    subcommands = agent_bench.add_subparsers(dest="agent_bench_command", required=True)
    tasks = subcommands.add_parser("tasks", help="List the ten sealed-evaluator task families")
    tasks.add_argument("--json", action="store_true", help="Emit JSON")
    example_config = subcommands.add_parser(
        "example-config", help="Write an editable multi-harness/model experiment matrix"
    )
    example_config.add_argument("--output", type=Path, required=True)
    plan = subcommands.add_parser(
        "plan", help="Validate a suite and enumerate its complete compatible allocation"
    )
    plan.add_argument("config", type=Path)
    plan.add_argument("--json", action="store_true", help="Emit every plan as JSON")
    smoke = subcommands.add_parser(
        "smoke", help="Run the deterministic 20-trial transport/evaluator smoke"
    )
    smoke.add_argument("--output", type=Path, required=True)
    smoke.add_argument("--repo-root", type=Path, help="Source checkout containing context documents")
    smoke.add_argument("--json", action="store_true", help="Emit JSON")
    run = subcommands.add_parser("run", help="Run one frozen external or fixture suite")
    run.add_argument("config", type=Path)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--repo-root", type=Path, help="Source checkout containing context documents")
    run.add_argument(
        "--allow-external",
        action="store_true",
        help="Acknowledge execution of enabled no-shell command harnesses",
    )
    run.add_argument(
        "--max-trials",
        type=int,
        help="Explicitly truncate execution while retaining unvisited trial accounting",
    )
    run.add_argument("--json", action="store_true", help="Emit JSON")
    journal = subcommands.add_parser(
        "journal-verify", help="Validate receipt objects and the complete local hash chain"
    )
    journal.add_argument("path", type=Path)
    journal.add_argument("--json", action="store_true", help="Emit JSON")


def run_agent_bench_command(args: argparse.Namespace) -> int:
    if args.agent_bench_command == "tasks":
        return _tasks(args.json)
    if args.agent_bench_command == "example-config":
        return _example_config(args.output)
    if args.agent_bench_command == "plan":
        return _plan(args.config, args.json)
    if args.agent_bench_command == "smoke":
        return _smoke(args.output, args.repo_root, args.json)
    if args.agent_bench_command == "run":
        return _run(
            args.config,
            args.output,
            args.allow_external,
            args.max_trials,
            args.repo_root,
            args.json,
        )
    if args.agent_bench_command == "journal-verify":
        return _journal_verify(args.path, args.json)
    raise ValueError(f"unsupported agent-bench command {args.agent_bench_command!r}")


__all__ = ["add_agent_bench_parser", "run_agent_bench_command"]
