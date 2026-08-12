"""Transactional, non-leaking workspaces for control/treatment coding trials."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any

from solutiongraph.agent_bench.model import TrialPlan
from solutiongraph.agent_bench.tasks.common import AgentTaskBundle
from solutiongraph.model import DIGEST_RE, sha256_digest

WORKSPACE_MODEL_VERSION = "0.1"


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _digest_bytes(value: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class WorkspaceFile:
    path: str
    digest: str
    size_bytes: int
    protected: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "digest": self.digest,
            "size_bytes": self.size_bytes,
            "protected": self.protected,
        }


@dataclass(frozen=True)
class WorkspaceManifest:
    trial_id: str
    trial_plan_digest: str
    task_id: str
    task_digest: str
    condition: str
    prompt_digest: str
    context_digest: str
    context_bytes: int
    files: tuple[WorkspaceFile, ...]
    candidate_paths: tuple[str, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def protected_files(self) -> tuple[WorkspaceFile, ...]:
        return tuple(item for item in self.files if item.protected)

    def validate(self) -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("trial_plan_digest", self.trial_plan_digest),
            ("task_digest", self.task_digest),
            ("prompt_digest", self.prompt_digest),
            ("context_digest", self.context_digest),
        ):
            if not DIGEST_RE.fullmatch(value):
                problems.append(f"workspace.{label} must be a sha256 digest")
        if self.context_bytes < 0:
            problems.append("workspace.context_bytes must be non-negative")
        paths = tuple(item.path for item in self.files)
        if len(paths) != len(set(paths)):
            problems.append("workspace file paths must be unique")
        if len(self.candidate_paths) != len(set(self.candidate_paths)):
            problems.append("workspace candidate_paths must be unique")
        if set(self.candidate_paths) & {item.path for item in self.protected_files}:
            problems.append("candidate paths cannot also be protected")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_model_version": WORKSPACE_MODEL_VERSION,
            "trial_id": self.trial_id,
            "trial_plan_digest": self.trial_plan_digest,
            "task_id": self.task_id,
            "task_digest": self.task_digest,
            "condition": self.condition,
            "prompt_digest": self.prompt_digest,
            "context_digest": self.context_digest,
            "context_bytes": self.context_bytes,
            "files": [item.to_dict() for item in self.files],
            "candidate_paths": list(self.candidate_paths),
        }


def _task_markdown(bundle: AgentTaskBundle) -> str:
    spec = bundle.spec
    return f"""# {spec.title}

{spec.summary}

## Required behavior

{spec.instructions}

## Contract

- Input: {spec.input_contract}
- Output: {spec.output_contract}
- Independent success: {spec.success_contract}
- Primary metric: `{spec.score_metric}` ({spec.score_direction})

Implement `solve(payload)` in `solution.py`. It must return a JSON-compatible
object and must be deterministic for identical input. The evaluator imports the
module in a fresh process for each case.

Create two explanatory artifacts:

- `SOLUTION.md`: architecture, assumptions, complexity, tests, and limitations.
- `solution.mmd`: a Mermaid `flowchart` or `graph` with at least two explicit edges.

Only candidate-readable development cases are present under `inputs/`. Sealed
case bytes and expected values are not copied into this workspace.
"""


def _agent_protocol() -> str:
    return """# Neutral coding-agent protocol

1. Read `TASK.md`, `task.json`, and `inputs/public-case.json`.
2. Implement only the requested candidate artifacts. Do not edit the task,
   prompt, context, input, runner, or public-test files.
3. Run `python public_tests/test_public.py` before finishing.
4. Do not traverse outside this workspace or look for evaluator/holdout files.
5. Do not use a network service or install dependencies.
6. Explain the implementation and produce a Mermaid solution diagram.

The evaluator—not this agent or its model—decides validity and acceptance.
"""


def _prompt(bundle: AgentTaskBundle) -> str:
    return f"""Complete the coding task in this workspace.

If repository-derived, digest-pinned materials exist under `context/`, use them
as planning and verification aids. Critique them against the concrete task;
they are suggestions, not executable truth. Do not assume the pack contains material.

Required final files: `solution.py`, `SOLUTION.md`, and `solution.mmd`.
Run the public test. Preserve every protected file. Do not access parent paths,
hidden cases, credentials, or the network. Finish only after the code, written
solution, and diagram agree.

Task: {bundle.spec.title}
"""


def _public_test(case_id: str) -> str:
    return f'''"""Candidate-readable smoke test; the independent evaluator has additional cases."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from solution import solve

case = json.loads((ROOT / "inputs" / "public-case.json").read_text(encoding="utf-8"))
observed = solve(case["input"])
if observed != case["expected"]:
    raise AssertionError("public case {case_id} did not match the expected output")
print("public case passed")
'''


def _starter_solution() -> str:
    return '''"""Implement the task's deterministic solve(payload) entrypoint."""
from __future__ import annotations


def solve(payload):
    raise NotImplementedError("replace this starter with a general solution")
'''


def _starting_points(bundle: AgentTaskBundle, seed: int) -> dict[str, Any]:
    rng = Random(seed)
    sprouts = [
        {"id": "sprout.contract-first", "focus": "derive exact input/output invariants before code"},
        {"id": "sprout.oracle-first", "focus": "work backward from independent acceptance and failure cases"},
        {"id": "sprout.data-first", "focus": "profile public structure, edge cases, and deterministic ordering"},
        {"id": "sprout.modular", "focus": "separate normalization, transformation, validation, and packaging"},
    ]
    rng.shuffle(sprouts)
    return {
        "task_id": bundle.spec.id,
        "task_digest": bundle.spec.digest,
        "seed": seed,
        "template_id": bundle.spec.template_id,
        "suggested_stages": list(bundle.spec.stages),
        "sprouts": sprouts,
        "protected_blind_lane": "the control arm receives none of these suggestions",
        "authority": "proposal-order-only; compiler/oracle acceptance remains independent",
    }


def _write_context(
    root: Path,
    repo_root: Path,
    bundle: AgentTaskBundle,
    plan: TrialPlan,
) -> tuple[str, int]:
    context_root = root / "context"
    context_root.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    if plan.condition == "solutiongraph":
        for relative in bundle.spec.context_sources:
            source = (repo_root / relative).resolve()
            try:
                source.relative_to(repo_root.resolve())
            except ValueError as exc:
                raise ValueError(f"context source escapes repository root: {relative}") from exc
            if not source.is_file():
                raise FileNotFoundError(f"context source does not exist: {relative}")
            target = context_root / "repository" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            target.write_bytes(data)
            copied.append({"path": f"repository/{relative}", "digest": _digest_bytes(data), "size_bytes": len(data)})
        generated = {
            "task-fingerprint.json": {
                "task_id": bundle.spec.id,
                "task_digest": bundle.spec.digest,
                "categories": list(bundle.spec.categories),
                "attributes": {
                    "stage_count": len(bundle.spec.stages),
                    "public_case_count": len(bundle.spec.public_case_ids),
                    "sealed_case_count": len(bundle.spec.sealed_case_ids),
                    "output_requires_code": True,
                    "output_requires_diagram": True,
                },
                "raw_record_content_included": False,
            },
            "starting-points.json": _starting_points(bundle, plan.seed),
            "task-graph.mmd": bundle.spec.mermaid(),
        }
        for name, value in generated.items():
            data = (value if isinstance(value, str) else _json(value)).encode("utf-8")
            (context_root / name).write_bytes(data)
            copied.append({"path": name, "digest": _digest_bytes(data), "size_bytes": len(data)})
    copied.sort(key=lambda item: item["path"])
    aggregate = ""
    if copied:
        sections = [
            "# Digest-pinned SolutionGraph context\n",
            "These materials nominate approaches; independent acceptance still controls.\n",
        ]
        for item in copied:
            text = (context_root / item["path"]).read_text(
                encoding="utf-8", errors="replace"
            )
            sections.append(f"\n## {item['path']}\n\n{text.rstrip()}\n")
        aggregate = "".join(sections)
    (context_root / "AGENT_CONTEXT.md").write_text(
        aggregate, encoding="utf-8", newline="\n"
    )
    aggregate_bytes = aggregate.encode("utf-8")
    copied.append(
        {
            "path": "AGENT_CONTEXT.md",
            "digest": _digest_bytes(aggregate_bytes),
            "size_bytes": len(aggregate_bytes),
            "derived_from": [item["path"] for item in copied],
        }
    )
    copied.sort(key=lambda item: item["path"])
    context_digest = sha256_digest(copied)
    context_bytes = sum(item["size_bytes"] for item in copied)
    if plan.condition == "solutiongraph":
        manifest = {
            "context_digest": context_digest,
            "context_bytes": context_bytes,
            "files": copied,
            "candidate_visibility": "candidate-readable",
            "admission_effect": "none; context nominates approaches but cannot grant validity",
        }
        (context_root / "manifest.json").write_text(
            _json(manifest), encoding="utf-8", newline="\n"
        )
        (context_root / "README.md").write_text(
            "Repository-derived context is digest-pinned in manifest.json. Treat it as a set "
            "of starting hypotheses, not as test answers or authority.\n",
            encoding="utf-8",
            newline="\n",
        )
    return context_digest, context_bytes


def materialize_workspace(
    destination: str | Path,
    repo_root: str | Path,
    bundle: AgentTaskBundle,
    plan: TrialPlan,
) -> WorkspaceManifest:
    """Create one immutable trial workspace without overwriting existing data."""
    destination = Path(destination)
    repo_root = Path(repo_root).resolve()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"workspace already exists: {destination}")
    if plan.task_id != bundle.spec.id or plan.task_digest != bundle.spec.digest:
        raise ValueError("trial plan does not match the task bundle")
    if plan.validate():
        raise ValueError("invalid trial plan: " + "; ".join(plan.validate()))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        (temporary / "inputs").mkdir()
        (temporary / "public_tests").mkdir()
        public_case = next(case for case in bundle.cases if case.candidate_readable)
        (temporary / "TASK.md").write_text(_task_markdown(bundle), encoding="utf-8", newline="\n")
        (temporary / "AGENT_PROTOCOL.md").write_text(_agent_protocol(), encoding="utf-8", newline="\n")
        (temporary / "task.json").write_text(_json(bundle.spec.to_dict()), encoding="utf-8", newline="\n")
        (temporary / "inputs" / "public-case.json").write_text(
            _json({"case_id": public_case.id, "input": public_case.payload, "expected": public_case.expected}),
            encoding="utf-8",
            newline="\n",
        )
        (temporary / "public_tests" / "test_public.py").write_text(
            _public_test(public_case.id), encoding="utf-8", newline="\n"
        )
        (temporary / "solution.py").write_text(_starter_solution(), encoding="utf-8", newline="\n")
        prompt = _prompt(bundle)
        (temporary / "PROMPT.md").write_text(prompt, encoding="utf-8", newline="\n")
        context_digest, context_bytes = _write_context(temporary, repo_root, bundle, plan)
        if plan.budget.max_context_bytes is not None and context_bytes > plan.budget.max_context_bytes:
            raise ValueError(
                f"context pack is {context_bytes} bytes, above the declared "
                f"{plan.budget.max_context_bytes}-byte budget"
            )
        candidate_paths = bundle.spec.required_artifacts
        file_records: list[WorkspaceFile] = []
        for path in sorted(item for item in temporary.rglob("*") if item.is_file()):
            relative = path.relative_to(temporary).as_posix()
            data = path.read_bytes()
            file_records.append(
                WorkspaceFile(
                    relative,
                    _digest_bytes(data),
                    len(data),
                    relative not in candidate_paths,
                )
            )
        manifest = WorkspaceManifest(
            trial_id=plan.id,
            trial_plan_digest=plan.digest,
            task_id=bundle.spec.id,
            task_digest=bundle.spec.digest,
            condition=plan.condition,
            prompt_digest=sha256_digest(prompt),
            context_digest=context_digest,
            context_bytes=context_bytes,
            files=tuple(file_records),
            candidate_paths=candidate_paths,
        )
        problems = manifest.validate()
        if problems:
            raise ValueError("invalid workspace manifest: " + "; ".join(problems))
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"workspace already exists: {destination}")
        os.rename(temporary, destination)
        return manifest
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def verify_protected_files(root: str | Path, manifest: WorkspaceManifest) -> tuple[str, ...]:
    """Return every missing or mutated non-candidate file."""
    root = Path(root)
    problems: list[str] = []
    for record in manifest.protected_files:
        path = root / record.path
        if not path.is_file():
            problems.append(f"protected file is missing: {record.path}")
            continue
        if _digest_bytes(path.read_bytes()) != record.digest:
            problems.append(f"protected file was modified: {record.path}")
    return tuple(problems)


__all__ = [
    "WORKSPACE_MODEL_VERSION",
    "WorkspaceFile",
    "WorkspaceManifest",
    "materialize_workspace",
    "verify_protected_files",
]
