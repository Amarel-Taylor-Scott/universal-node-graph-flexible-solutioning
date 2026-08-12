"""Strict JSON loading and reference matrices for agent benchmarks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from solutiongraph.agent_bench.model import (
    AGENT_BENCH_CONDITIONS,
    AgentBenchmarkSuite,
    AgentTrialBudget,
    HarnessProfile,
    ModelProfile,
)
from solutiongraph.agent_bench.tasks import REFERENCE_AGENT_TASKS


def reference_agent_benchmark_suite() -> AgentBenchmarkSuite:
    """Fast transport/evaluator smoke; deliberately not model efficacy evidence."""
    return AgentBenchmarkSuite(
        id="agent-benchmark.reference-smoke",
        version="1.0.0",
        title="Ten-task SolutionGraph agent benchmark transport smoke",
        task_ids=tuple(bundle.spec.id for bundle in REFERENCE_AGENT_TASKS),
        conditions=AGENT_BENCH_CONDITIONS,
        harnesses=(
            HarnessProfile(
                id="harness.reference-fixture",
                kind="fixture",
                version="1.0.0",
                compatible_model_ids=("model.reference-fixture",),
                isolation="trusted-in-process-fixture",
                notes="Deterministic evaluator-owned reference; never include in model-quality claims.",
            ),
        ),
        models=(
            ModelProfile(
                id="model.reference-fixture",
                provider="fixture",
                model="deterministic-reference",
                revision="1.0.0",
                size_class="unknown",
                settings=(("deterministic", True),),
                notes="No model is called.",
            ),
        ),
        seeds=(101,),
        repetitions=1,
        budget=AgentTrialBudget(
            max_wall_seconds=60,
            max_output_bytes=1_000_000,
            max_context_bytes=1_000_000,
        ),
        claim_scope="mechanism-fixture",
        bootstrap_resamples=500,
        confidence_level=0.95,
        practical_effect=0.02,
        allow_promotion=False,
        limitations=(
            "The reference harness bypasses model generation and is expected to produce equivalent control/treatment outcomes.",
        ),
    )


def command_matrix_example_suite() -> AgentBenchmarkSuite:
    """Editable multi-harness/multi-model matrix with external adapters disabled."""
    reference = reference_agent_benchmark_suite()
    return AgentBenchmarkSuite(
        id="agent-benchmark.command-matrix-example",
        version="1.0.0",
        title="Ten-task multi-harness, small-to-frontier A/B matrix",
        task_ids=reference.task_ids,
        conditions=AGENT_BENCH_CONDITIONS,
        harnesses=(
            reference.harnesses[0],
            HarnessProfile(
                id="harness.opencode",
                kind="command",
                version="operator-pin-required",
                command_argv=(
                    "opencode",
                    "run",
                    "--model",
                    "{model}",
                    "--dir",
                    "{workspace}",
                    "{prompt}",
                ),
                enabled=False,
                compatible_model_ids=(
                    "model.small-local",
                    "model.medium",
                    "model.large",
                    "model.frontier",
                ),
                isolation="external-unspecified",
                notes="OpenCode headless run syntax: https://opencode.ai/docs/cli/; pin and verify the installed version.",
            ),
            HarnessProfile(
                id="harness.aider",
                kind="command",
                version="operator-pin-required",
                command_argv=(
                    "aider",
                    "--model",
                    "{model}",
                    "--message-file",
                    "{prompt_file}",
                    "--yes-always",
                    "--no-git",
                    "--no-auto-commits",
                    "--no-check-update",
                    "--analytics-disable",
                    "--read",
                    "TASK.md",
                    "--read",
                    "task.json",
                    "--read",
                    "AGENT_PROTOCOL.md",
                    "--read",
                    "inputs/public-case.json",
                    "--read",
                    "public_tests/test_public.py",
                    "--read",
                    "context/AGENT_CONTEXT.md",
                    "--file",
                    "solution.py",
                ),
                enabled=False,
                compatible_model_ids=(
                    "model.small-local",
                    "model.medium",
                    "model.large",
                    "model.frontier",
                ),
                isolation="external-unspecified",
                notes="Aider message-file syntax: https://aider.chat/docs/config/options.html; pin and verify the installed version.",
            ),
            HarnessProfile(
                id="harness.private-command",
                kind="command",
                version="operator-pin-required",
                command_argv=(
                    "replace-with-agent-cli",
                    "--model",
                    "{model}",
                    "--workspace",
                    "{workspace}",
                    "--prompt-file",
                    "{prompt_file}",
                ),
                enabled=False,
                compatible_model_ids=(
                    "model.small-local",
                    "model.medium",
                    "model.large",
                    "model.frontier",
                ),
                isolation="external-unspecified",
                notes="Use for local/private harness names without teaching the core a vendor-specific capability.",
            ),
        ),
        models=(
            reference.models[0],
            ModelProfile(
                id="model.small-local",
                provider="replace-provider",
                model="replace-provider/replace-small-model",
                revision="pin-required",
                size_class="small",
                settings=(("temperature", 0),),
                enabled=False,
            ),
            ModelProfile(
                id="model.medium",
                provider="replace-provider",
                model="replace-provider/replace-medium-model",
                revision="pin-required",
                size_class="medium",
                settings=(("temperature", 0),),
                enabled=False,
            ),
            ModelProfile(
                id="model.large",
                provider="replace-provider",
                model="replace-provider/replace-large-model",
                revision="pin-required",
                size_class="large",
                settings=(("temperature", 0),),
                enabled=False,
            ),
            ModelProfile(
                id="model.frontier",
                provider="replace-provider",
                model="replace-provider/replace-frontier-model",
                revision="pin-required",
                size_class="frontier",
                settings=(("temperature", 0),),
                enabled=False,
            ),
        ),
        seeds=(101, 202, 303),
        repetitions=1,
        budget=AgentTrialBudget(
            max_wall_seconds=1_800,
            max_output_bytes=2_000_000,
            max_context_bytes=1_000_000,
            max_input_tokens=64_000,
            max_output_tokens=16_000,
            max_cost_units=25.0,
        ),
        claim_scope="internal-dataset",
        bootstrap_resamples=2_000,
        confidence_level=0.95,
        practical_effect=0.02,
        acceptance_noninferiority_margin=0.02,
        allow_promotion=False,
        limitations=(
            "Replace every placeholder, pin harness/model revisions, choose explicit credential variable names, and declare an enforcing isolation boundary before external execution.",
        ),
    )


def _keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ValueError(f"{path} keys differ; missing={missing}, extra={extra}")


def suite_from_dict(value: dict[str, Any]) -> AgentBenchmarkSuite:
    expected = {
        "agent_bench_model_version",
        "id",
        "version",
        "title",
        "task_ids",
        "conditions",
        "harnesses",
        "models",
        "seeds",
        "repetitions",
        "budget",
        "claim_scope",
        "bootstrap_resamples",
        "confidence_level",
        "practical_effect",
        "acceptance_noninferiority_margin",
        "allow_promotion",
        "limitations",
    }
    _keys(value, expected, "suite")
    harnesses: list[HarnessProfile] = []
    for index, item in enumerate(value["harnesses"]):
        _keys(
            item,
            {
                "id",
                "kind",
                "version",
                "command_argv",
                "compatible_model_ids",
                "environment_allowlist",
                "enabled",
                "isolation",
                "notes",
            },
            f"suite.harnesses[{index}]",
        )
        harnesses.append(
            HarnessProfile(
                id=item["id"],
                kind=item["kind"],
                version=item["version"],
                command_argv=tuple(item["command_argv"]),
                compatible_model_ids=tuple(item["compatible_model_ids"]),
                environment_allowlist=tuple(item["environment_allowlist"]),
                enabled=item["enabled"],
                isolation=item["isolation"],
                notes=item["notes"],
            )
        )
    models: list[ModelProfile] = []
    for index, item in enumerate(value["models"]):
        _keys(
            item,
            {
                "id",
                "provider",
                "model",
                "revision",
                "size_class",
                "context_window",
                "settings",
                "enabled",
                "notes",
            },
            f"suite.models[{index}]",
        )
        models.append(
            ModelProfile(
                id=item["id"],
                provider=item["provider"],
                model=item["model"],
                revision=item["revision"],
                size_class=item["size_class"],
                context_window=item["context_window"],
                settings=tuple(sorted(item["settings"].items())),
                enabled=item["enabled"],
                notes=item["notes"],
            )
        )
    budget_value = value["budget"]
    _keys(
        budget_value,
        {
            "max_wall_seconds",
            "max_output_bytes",
            "max_context_bytes",
            "max_input_tokens",
            "max_output_tokens",
            "max_cost_units",
        },
        "suite.budget",
    )
    suite = AgentBenchmarkSuite(
        id=value["id"],
        version=value["version"],
        title=value["title"],
        task_ids=tuple(value["task_ids"]),
        conditions=tuple(value["conditions"]),
        harnesses=tuple(harnesses),
        models=tuple(models),
        seeds=tuple(value["seeds"]),
        repetitions=value["repetitions"],
        budget=AgentTrialBudget(**budget_value),
        claim_scope=value["claim_scope"],
        bootstrap_resamples=value["bootstrap_resamples"],
        confidence_level=value["confidence_level"],
        practical_effect=value["practical_effect"],
        acceptance_noninferiority_margin=value["acceptance_noninferiority_margin"],
        allow_promotion=value["allow_promotion"],
        limitations=tuple(value["limitations"]),
    )
    known = tuple(bundle.spec.id for bundle in REFERENCE_AGENT_TASKS)
    problems = suite.validate(known)
    if problems:
        raise ValueError("invalid agent benchmark suite: " + "; ".join(problems))
    return suite


def load_agent_benchmark_suite(path: str | Path) -> AgentBenchmarkSuite:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("agent benchmark suite root must be an object")
    return suite_from_dict(value)


def write_agent_benchmark_suite(suite: AgentBenchmarkSuite, path: str | Path) -> Path:
    problems = suite.validate(tuple(bundle.spec.id for bundle in REFERENCE_AGENT_TASKS))
    if problems:
        raise ValueError("invalid agent benchmark suite: " + "; ".join(problems))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(suite.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return target


__all__ = [
    "command_matrix_example_suite",
    "load_agent_benchmark_suite",
    "reference_agent_benchmark_suite",
    "suite_from_dict",
    "write_agent_benchmark_suite",
]
