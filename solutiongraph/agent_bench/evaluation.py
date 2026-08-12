"""Deterministic candidate checks behind an explicit non-adversarial boundary."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from solutiongraph.agent_bench.model import AgentTrialBudget, TrialArtifact
from solutiongraph.agent_bench.tasks.common import AgentTaskBundle, CaseEvaluation
from solutiongraph.agent_bench.workspace import WorkspaceManifest, verify_protected_files
from solutiongraph.model import canonical_json

_RUNNER = r'''from __future__ import annotations
import contextlib
import importlib
import json
import sys

workspace = sys.argv[1]
sys.path.insert(0, workspace)
trusted_fixture_root = sys.argv[2]
if trusted_fixture_root:
    sys.path.insert(1, trusted_fixture_root)
payload = json.load(sys.stdin)
with contextlib.redirect_stdout(sys.stderr):
    module = importlib.import_module("solution")
    output = module.solve(payload)
sys.stdout.write(json.dumps(output, sort_keys=True, separators=(",", ":"), allow_nan=False))
'''


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _kill(process: subprocess.Popen[bytes]) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass


@dataclass(frozen=True)
class CandidateCaseResult:
    case_id: str
    split: str
    candidate_readable: bool
    executed: bool
    deterministic: bool
    evaluation: CaseEvaluation
    output_digest: str
    stderr_digest: str
    problems: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "split": self.split,
            "candidate_readable": self.candidate_readable,
            "executed": self.executed,
            "deterministic": self.deterministic,
            "accepted": self.evaluation.accepted,
            "score": self.evaluation.score,
            "metrics": dict(self.evaluation.metrics),
            "output_digest": self.output_digest,
            "stderr_digest": self.stderr_digest,
            "problems": [*self.problems, *self.evaluation.problems],
        }


@dataclass(frozen=True)
class CandidateEvaluation:
    delivered: bool
    valid: bool
    scored: bool
    accepted: bool
    artifacts: tuple[TrialArtifact, ...]
    case_results: tuple[CandidateCaseResult, ...]
    metrics: tuple[tuple[str, float], ...]
    problems: tuple[str, ...]

    @property
    def metric_map(self) -> dict[str, float]:
        return dict(self.metrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "delivered": self.delivered,
            "valid": self.valid,
            "scored": self.scored,
            "accepted": self.accepted,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "case_results": [item.to_dict() for item in self.case_results],
            "metrics": dict(self.metrics),
            "problems": list(self.problems),
        }


def _artifact(root: Path, relative: str) -> TrialArtifact | None:
    path = root / relative
    if not path.is_file():
        return None
    data = path.read_bytes()
    return TrialArtifact(relative, _digest_bytes(data), len(data))


def _source_problems(path: Path, allowed_imports: tuple[str, ...], fixture: bool) -> list[str]:
    problems: list[str] = []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        return [f"solution.py is not valid UTF-8 Python: {type(exc).__name__}: {exc}"]
    if "NotImplementedError" in source or "replace this starter" in source:
        problems.append("solution.py still contains the starter implementation")
    if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "solve" for node in tree.body):
        problems.append("solution.py must define a top-level solve function")
    allowed = {"__future__", *allowed_imports}
    if fixture:
        allowed.add("solutiongraph")
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module.split(".", 1)[0])
    blocked = sorted(set(imported) - allowed)
    if blocked:
        problems.append("solution.py imports undeclared modules: " + ", ".join(blocked))
    return problems


def _documentation_score(root: Path) -> tuple[float, list[str]]:
    path = root / "SOLUTION.md"
    if not path.is_file():
        return 0.0, ["SOLUTION.md is missing"]
    text = path.read_text(encoding="utf-8")
    checks = (
        len(text.strip()) >= 200,
        "test" in text.casefold(),
        "limitation" in text.casefold(),
        "#" in text,
    )
    score = sum(checks) / len(checks)
    return score, ([] if score == 1.0 else ["SOLUTION.md must explain architecture, tests, and limitations"])


def _diagram_score(root: Path) -> tuple[float, list[str]]:
    path = root / "solution.mmd"
    if not path.is_file():
        return 0.0, ["solution.mmd is missing"]
    text = path.read_text(encoding="utf-8").strip()
    first = text.splitlines()[0].strip() if text else ""
    edges = text.count("-->") + text.count("-.->") + text.count("==>")
    valid_header = first.startswith("flowchart ") or first.startswith("graph ")
    score = (float(valid_header) + float(edges >= 2)) / 2.0
    return score, ([] if score == 1.0 else ["solution.mmd needs a Mermaid graph/flowchart and at least two edges"])


def _read_bounded(path: Path, maximum: int) -> tuple[bytes, bool]:
    if not path.exists():
        return b"", False
    size = path.stat().st_size
    with path.open("rb") as handle:
        return handle.read(maximum), size > maximum


def _invoke_once(
    root: Path,
    payload: dict[str, Any],
    timeout: float,
    maximum_output: int,
    seed: int,
    fixture: bool,
) -> tuple[dict[str, Any] | None, bytes, tuple[str, ...]]:
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="solutiongraph-agent-eval-") as temporary:
        temporary_path = Path(temporary)
        stdout_path = temporary_path / "stdout"
        stderr_path = temporary_path / "stderr"
        environment = {
            key: os.environ[key]
            for key in ("PATH", "LANG", "LC_ALL", "TMPDIR")
            if key in os.environ
        }
        environment["PYTHONHASHSEED"] = str(seed)
        with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
            trusted_root = str(Path(__file__).parents[2]) if fixture else ""
            process = subprocess.Popen(
                [sys.executable, "-I", "-c", _RUNNER, str(root), trusted_root],
                cwd=root,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=stdout_handle,
                stderr=stderr_handle,
                shell=False,
                start_new_session=(os.name == "posix"),
            )
            try:
                process.communicate(
                    json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8"),
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                _kill(process)
                process.wait()
                problems.append("candidate case execution timed out")
        stdout, stdout_truncated = _read_bounded(stdout_path, maximum_output)
        stderr, stderr_truncated = _read_bounded(stderr_path, maximum_output)
        if stdout_truncated:
            problems.append("candidate case stdout exceeded the byte limit")
        if stderr_truncated:
            problems.append("candidate case stderr exceeded the byte limit")
        if process.returncode != 0:
            problems.append(f"candidate case process exited with {process.returncode}")
        output: dict[str, Any] | None = None
        if not problems:
            try:
                decoded = json.loads(stdout.decode("utf-8"))
                if not isinstance(decoded, dict):
                    raise ValueError("solve must return a JSON object")
                output = decoded
            except (UnicodeError, ValueError) as exc:
                problems.append(f"candidate output is not a JSON object: {exc}")
        return output, stderr, tuple(problems)


def _failed_case(bundle: AgentTaskBundle, case_id: str, split: str, readable: bool, problems: tuple[str, ...]) -> CandidateCaseResult:
    evaluation = CaseEvaluation(False, 0.0, (), problems)
    return CandidateCaseResult(case_id, split, readable, False, False, evaluation, _digest_bytes(b""), _digest_bytes(b""), problems)


def evaluate_candidate(
    root: str | Path,
    bundle: AgentTaskBundle,
    manifest: WorkspaceManifest,
    budget: AgentTrialBudget,
    *,
    seed: int,
    fixture: bool = False,
) -> CandidateEvaluation:
    """Evaluate artifacts and all cases; this is lifecycle isolation, not a sandbox."""
    root = Path(root).resolve()
    problems: list[str] = list(verify_protected_files(root, manifest))
    artifacts = tuple(
        artifact
        for relative in bundle.spec.required_artifacts
        if (artifact := _artifact(root, relative)) is not None
    )
    delivered = len(artifacts) == len(bundle.spec.required_artifacts)
    if not delivered:
        missing = sorted(set(bundle.spec.required_artifacts) - {item.path for item in artifacts})
        problems.append("required artifacts are missing: " + ", ".join(missing))
    solution_path = root / "solution.py"
    if solution_path.is_file():
        problems.extend(_source_problems(solution_path, bundle.spec.allowed_imports, fixture))
    documentation_score, documentation_problems = _documentation_score(root)
    diagram_score, diagram_problems = _diagram_score(root)
    problems.extend(documentation_problems)
    problems.extend(diagram_problems)
    structural_valid = delivered and not problems

    case_results: list[CandidateCaseResult] = []
    if solution_path.is_file() and not _source_problems(solution_path, bundle.spec.allowed_imports, fixture):
        case_timeout = max(0.1, min(10.0, budget.max_wall_seconds / max(1, len(bundle.cases) * 2)))
        for case in bundle.cases:
            if fixture:
                first = bundle.reference_solver(case.payload)
                second = bundle.reference_solver(case.payload)
                deterministic = canonical_json(first) == canonical_json(second)
                evaluation = bundle.oracle(case.payload, first, case.expected)
                case_results.append(
                    CandidateCaseResult(
                        case.id,
                        case.split,
                        case.candidate_readable,
                        True,
                        deterministic,
                        evaluation,
                        _digest_bytes(canonical_json(first).encode("utf-8")),
                        _digest_bytes(b""),
                    )
                )
                continue
            first, first_stderr, first_problems = _invoke_once(
                root, case.payload, case_timeout, budget.max_output_bytes, seed, fixture
            )
            if first is None:
                case_results.append(
                    _failed_case(bundle, case.id, case.split, case.candidate_readable, first_problems)
                )
                continue
            second, second_stderr, second_problems = _invoke_once(
                root, case.payload, case_timeout, budget.max_output_bytes, seed, fixture
            )
            deterministic = second is not None and canonical_json(first) == canonical_json(second)
            invocation_problems = (*first_problems, *second_problems)
            if not deterministic:
                invocation_problems = (*invocation_problems, "candidate output is not deterministic")
            evaluation = bundle.oracle(case.payload, first, case.expected)
            case_results.append(
                CandidateCaseResult(
                    case.id,
                    case.split,
                    case.candidate_readable,
                    True,
                    deterministic,
                    evaluation,
                    _digest_bytes(canonical_json(first).encode("utf-8")),
                    _digest_bytes(first_stderr + second_stderr),
                    tuple(invocation_problems),
                )
            )
    else:
        case_results.extend(
            _failed_case(bundle, case.id, case.split, case.candidate_readable, ("solution.py failed static validation",))
            for case in bundle.cases
        )

    executed = [item for item in case_results if item.executed]
    scored = len(executed) == len(bundle.cases)
    development = [item for item in case_results if item.candidate_readable]
    holdout = [item for item in case_results if not item.candidate_readable]
    def mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    generic_metrics = (
        ("oracle_score", mean([item.evaluation.score for item in case_results])),
        ("case_pass_rate", mean([float(item.evaluation.accepted) for item in case_results])),
        ("development_pass_rate", mean([float(item.evaluation.accepted) for item in development])),
        ("holdout_pass_rate", mean([float(item.evaluation.accepted) for item in holdout])),
        ("determinism_rate", mean([float(item.deterministic) for item in case_results])),
        ("artifact_completeness", len(artifacts) / len(bundle.spec.required_artifacts)),
        ("documentation_score", documentation_score),
        ("diagram_score", diagram_score),
        ("protected_integrity", float(not verify_protected_files(root, manifest))),
    )
    case_metric_names = sorted(
        {
            name
            for item in case_results
            for name, _ in item.evaluation.metrics
        }
    )
    case_metrics = tuple(
        (
            name,
            mean(
                [
                    dict(item.evaluation.metrics)[name]
                    for item in case_results
                    if name in dict(item.evaluation.metrics)
                ]
            ),
        )
        for name in case_metric_names
        if name not in dict(generic_metrics)
    )
    metrics = (*generic_metrics, *case_metrics)
    case_problems = [
        f"{item.case_id}: {problem}"
        for item in case_results
        for problem in (*item.problems, *item.evaluation.problems)
    ]
    problems.extend(case_problems)
    accepted = (
        structural_valid
        and scored
        and all(item.deterministic and item.evaluation.accepted for item in case_results)
    )
    return CandidateEvaluation(
        delivered=delivered,
        valid=structural_valid and scored,
        scored=scored,
        accepted=accepted,
        artifacts=artifacts,
        case_results=tuple(case_results),
        metrics=metrics,
        problems=tuple(dict.fromkeys(problems)),
    )


__all__ = [
    "CandidateCaseResult",
    "CandidateEvaluation",
    "evaluate_candidate",
]
