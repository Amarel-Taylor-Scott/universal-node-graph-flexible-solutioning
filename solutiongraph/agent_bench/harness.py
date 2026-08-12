"""No-shell harness invocation with an explicit deterministic smoke adapter."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from solutiongraph.agent_bench.model import (
    AgentTrialBudget,
    HarnessProfile,
    ModelProfile,
    TrialPlan,
)
from solutiongraph.agent_bench.tasks.common import AgentTaskBundle
from solutiongraph.agent_bench.workspace import WorkspaceManifest
from solutiongraph.model import sha256_digest


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bytes_digest(value: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class HarnessRun:
    started_at: str
    ended_at: str
    wall_seconds: float
    exit_code: int | None
    timed_out: bool
    command_digest: str
    stdout: bytes
    stderr: bytes
    stdout_digest: str
    stderr_digest: str
    environment_variable_names: tuple[str, ...]
    budget_enforcement: tuple[str, ...]
    isolation: str
    delivered: bool
    problems: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "wall_seconds": self.wall_seconds,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "command_digest": self.command_digest,
            "stdout_digest": self.stdout_digest,
            "stderr_digest": self.stderr_digest,
            "environment_variable_names": list(self.environment_variable_names),
            "budget_enforcement": list(self.budget_enforcement),
            "isolation": self.isolation,
            "delivered": self.delivered,
            "problems": list(self.problems),
        }


def _replace_placeholders(argument: str, values: dict[str, str]) -> str:
    result = argument
    for placeholder, value in values.items():
        result = result.replace("{" + placeholder + "}", value)
    return result


def _read_prefix(path: Path, maximum: int) -> tuple[bytes, bool]:
    size = path.stat().st_size if path.exists() else 0
    with path.open("rb") if path.exists() else open(os.devnull, "rb") as handle:
        data = handle.read(maximum)
    return data, size > maximum


def _terminate(process: subprocess.Popen[bytes]) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=2)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass


def _reference_fixture(
    workspace: Path,
    bundle: AgentTaskBundle,
    plan: TrialPlan,
    manifest: WorkspaceManifest,
    profile: HarnessProfile,
) -> HarnessRun:
    started_at = _utc_now()
    started = time.monotonic()
    source = f'''"""Deterministic transport fixture, not an LLM-generated solution."""
from solutiongraph.agent_bench.tasks import solve_reference


def solve(payload):
    return solve_reference({bundle.spec.id!r}, payload)
'''
    (workspace / "solution.py").write_text(source, encoding="utf-8", newline="\n")
    (workspace / "SOLUTION.md").write_text(
        f"""# Reference transport fixture

This fixture delegates `{bundle.spec.id}` to the evaluator-owned deterministic
reference implementation. It exists only to prove workspace materialization,
harness delivery, sealed-case invocation, receipt persistence, paired analysis,
and report generation.

## Tests

The public and sealed deterministic oracles are executed in fresh child
processes. Control and SolutionGraph conditions intentionally receive identical
fixture output, so a correct smoke report should find practical equivalence.

## Limitations

This is not model evidence, a model comparison, a security sandbox, or proof
that repository context improves code. Real conclusions require enabled command
harnesses, matched models and budgets, repeated seeds, and an external sealed
evaluation boundary.
""",
        encoding="utf-8",
        newline="\n",
    )
    (workspace / "solution.mmd").write_text(bundle.spec.mermaid(), encoding="utf-8", newline="\n")
    ended = time.monotonic()
    stdout = b"reference fixture delivered\n"
    stderr = b""
    return HarnessRun(
        started_at=started_at,
        ended_at=_utc_now(),
        wall_seconds=ended - started,
        exit_code=0,
        timed_out=False,
        command_digest=sha256_digest({"fixture": profile.id, "version": profile.version}),
        stdout=stdout,
        stderr=stderr,
        stdout_digest=_bytes_digest(stdout),
        stderr_digest=_bytes_digest(stderr),
        environment_variable_names=(),
        budget_enforcement=("fixture.no-external-process",),
        isolation="trusted-in-process-fixture",
        delivered=True,
    )


def run_harness(
    workspace: str | Path,
    bundle: AgentTaskBundle,
    plan: TrialPlan,
    manifest: WorkspaceManifest,
    profile: HarnessProfile,
    model: ModelProfile,
    *,
    allow_external: bool,
) -> HarnessRun:
    """Run one configured harness without a shell or implicit credentials."""
    workspace = Path(workspace).resolve()
    profile_problems = profile.validate()
    model_problems = model.validate()
    if profile_problems or model_problems:
        raise ValueError("invalid harness/model: " + "; ".join((*profile_problems, *model_problems)))
    if profile.kind == "fixture":
        return _reference_fixture(workspace, bundle, plan, manifest, profile)
    if not allow_external:
        raise PermissionError(
            "command harness execution requires explicit allow_external=True; planning remains available"
        )

    prompt_path = workspace / "PROMPT.md"
    prompt = prompt_path.read_text(encoding="utf-8")
    values = {
        "condition": plan.condition,
        "model": model.model,
        "model_id": model.id,
        "prompt": prompt,
        "prompt_file": str(prompt_path),
        "seed": str(plan.seed),
        "task_id": bundle.spec.id,
        "workspace": str(workspace),
    }
    argv = tuple(_replace_placeholders(argument, values) for argument in profile.command_argv)
    if not argv or not argv[0]:
        raise ValueError("expanded command_argv must contain an executable")
    environment = {
        name: os.environ[name]
        for name in ("PATH", "LANG", "LC_ALL", "TMPDIR", *profile.environment_allowlist)
        if name in os.environ
    }
    environment_names = tuple(sorted(environment))
    logs = workspace / ".agent-bench"
    logs.mkdir(exist_ok=True)
    stdout_path = logs / "stdout.log"
    stderr_path = logs / "stderr.log"
    started_at = _utc_now()
    started = time.monotonic()
    timed_out = False
    problems: list[str] = []
    with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
        process = subprocess.Popen(
            argv,
            cwd=workspace,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            shell=False,
            start_new_session=(os.name == "posix"),
        )
        try:
            exit_code = process.wait(timeout=plan.budget.max_wall_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate(process)
            exit_code = process.returncode
            problems.append("harness exceeded the declared wall-clock budget")
    wall_seconds = time.monotonic() - started
    stdout, stdout_truncated = _read_prefix(stdout_path, plan.budget.max_output_bytes)
    stderr, stderr_truncated = _read_prefix(stderr_path, plan.budget.max_output_bytes)
    if stdout_truncated:
        problems.append("stdout exceeded the recorded byte prefix")
    if stderr_truncated:
        problems.append("stderr exceeded the recorded byte prefix")
    delivered = all((workspace / path).is_file() for path in bundle.spec.required_artifacts)
    if not delivered:
        problems.append("harness did not deliver every required artifact")
    command_record = [
        "<prompt>" if argument == prompt else argument.replace(prompt, "<prompt>")
        for argument in argv
    ]
    budget_enforcement = (
        "runner.wall-clock-timeout",
        "runner.stdout-stderr-record-prefix",
        "harness-declared token/cost budgets require provider usage evidence",
    )
    return HarnessRun(
        started_at=started_at,
        ended_at=_utc_now(),
        wall_seconds=wall_seconds,
        exit_code=exit_code,
        timed_out=timed_out,
        command_digest=sha256_digest(command_record),
        stdout=stdout,
        stderr=stderr,
        stdout_digest=_bytes_digest(stdout),
        stderr_digest=_bytes_digest(stderr),
        environment_variable_names=environment_names,
        budget_enforcement=budget_enforcement,
        isolation=profile.isolation,
        delivered=delivered,
        problems=tuple(problems),
    )


def load_usage_metrics(workspace: str | Path, budget: AgentTrialBudget) -> tuple[tuple[str, float], ...]:
    """Load optional harness-reported usage without treating it as verified billing."""
    path = Path(workspace) / "agent-usage.json"
    if not path.is_file():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    allowed = ("input_tokens", "output_tokens", "total_tokens", "cost_units", "tool_calls")
    if not isinstance(payload, dict) or set(payload) - set(allowed):
        raise ValueError("agent-usage.json contains unsupported fields")
    metrics: list[tuple[str, float]] = []
    for name in allowed:
        if name in payload:
            value = float(payload[name])
            if value < 0:
                raise ValueError(f"agent-usage.json {name} must be non-negative")
            metrics.append((name, value))
    measured = dict(metrics)
    limits = (
        ("input_tokens", budget.max_input_tokens),
        ("output_tokens", budget.max_output_tokens),
        ("cost_units", budget.max_cost_units),
    )
    exceeded = [
        f"{name}={measured[name]} exceeds declared maximum {limit}"
        for name, limit in limits
        if limit is not None and name in measured and measured[name] > limit
    ]
    if exceeded:
        raise ValueError("; ".join(exceeded))
    return tuple(metrics)


__all__ = ["HarnessRun", "load_usage_metrics", "run_harness"]
