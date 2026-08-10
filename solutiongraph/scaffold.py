"""Transactional starter-workspace generation for developers and LLM harnesses."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from solutiongraph.templates import SolutionTemplate

SCAFFOLD_SCHEMA_VERSION = "1.0"


def default_project_id(path: Path) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", path.name.lower()).strip("-")
    if not slug:
        raise ValueError("project directory name must contain a letter or number")
    if not slug[0].isalpha():
        slug = f"graph-{slug}"
    return f"project.{slug}"


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _readme(project_id: str, template: SolutionTemplate) -> str:
    return f"""# {project_id}

This workspace was generated from `{template.id}@{template.version}` using
SolutionGraph. It intentionally contains a semantic template and harness
contract—not invented implementations or fake benchmark results.

## Start here

1. Open `TASK.md` and state the concrete outcome, typed inputs/outputs, policy
   limits, and independent acceptance oracle.
2. Refine `solution-template.json`: remove only obligations proven irrelevant,
   split oversized slots, and replace schematic value types with domain types.
3. Discover or author strict node contracts and freeze a registry snapshot.
4. Compile every candidate/slot admission before selecting a route.
5. Execute a baseline and alternatives, persist artifacts and `receipts.jsonl`,
   and let evidence update beliefs only after independent verification.

## Verify the framework installation

```bash
solutiongraph doctor
solutiongraph verify --catalog-root /path/to/framework/catalog --runtime subprocess
solutiongraph templates show {template.id}
```

## Safety boundary

The bundled subprocess adapter provides lifecycle isolation and resource
bounds; it is not a hostile-code sandbox. Do not execute untrusted generated
nodes without an enforcing microVM, Wasm, or remote trust boundary. Never let
candidate code read or write hidden evaluators.

The complete architecture and current readiness limits are maintained in the
[upstream repository](https://github.com/Amarel-Taylor-Scott/universal-node-graph-flexible-solutioning).
"""


def _task_guide(template: SolutionTemplate) -> str:
    stages = "\n".join(
        f"- `{stage.id}` — {stage.title}: {stage.description}"
        for stage in template.stages
    )
    return f"""# Task contract intake

Answer these before a coding harness authors nodes or routes:

1. What observable outcome is required?
2. What named, versioned input values enter the graph?
3. What named, versioned output values must leave it?
4. Which independent oracle can accept or reject the outcome?
5. Which effects and permissions are allowed—and which are forbidden?
6. What quality, cost, latency, reliability, privacy, and resource constraints
   are hard gates versus optimization objectives?
7. Which cases are development, validation, and untouched holdout cases?
8. Which failure classes require retry, fallback, human review, or termination?

The selected starting template exposes these visible submatrices:

{stages}

Treat every atomic slot inside `solution-template.json` as a semantic
obligation. A slot is not a tool, provider, model, optimizer, or feedback step.
"""


def _agent_instructions(project_id: str, template: SolutionTemplate) -> str:
    return f"""# SolutionGraph workspace instructions

Project: `{project_id}`
Starting template: `{template.id}@{template.version}`

Build this task as a typed semantic graph. Keep task contract, semantic slots,
node definitions, admitted candidates, beliefs, frozen plans, and receipts as
separate objects. A node may be selected only after full compiler admission.

Required sequence:

1. Complete `TASK.md` from user evidence; never invent authority or acceptance.
2. Refine the checked-in template into exact types and atomic obligations.
3. Search compatible registries, retain coverage receipts, and freeze a closed
   snapshot. Similar descriptions or embeddings never prove compatibility.
4. Author missing nodes with exact ports, versions, digests, parameters,
   effects, permissions, failure modes, runtimes, and independent verifiers.
5. Compile before execution. Do not perform implicit conversion or hide finite
   choices inside a node.
6. Run a fixed baseline and bounded alternatives; persist every success,
   rejection, failure, seed, artifact, and receipt.
7. Keep optimization outside the task DAG. Scores may order only valid routes.

Do not call lifecycle subprocesses or plain containers hostile-code sandboxes.
Untrusted generated code and confidential evaluators require separate enforced
trust domains.
"""


def scaffold_project(
    destination: str | Path,
    template: SolutionTemplate,
    *,
    project_id: str | None = None,
) -> tuple[Path, ...]:
    """Create a complete starter workspace without overwriting existing data."""
    destination = Path(destination)
    project_id = project_id or default_project_id(destination)
    if not re.fullmatch(r"[a-z][a-z0-9_.:/-]*", project_id):
        raise ValueError("project_id must be a lowercase namespaced identifier")
    if os.path.lexists(destination):
        raise FileExistsError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    files = {
        "solutiongraph-project.json": _json({
            "schema_version": SCAFFOLD_SCHEMA_VERSION,
            "project_id": project_id,
            "template_id": template.id,
            "template_version": template.version,
            "template_digest": template.digest,
            "status": "template_selected",
            "next_gate": "instantiate_task_contract",
        }),
        "solution-template.json": _json(template.to_dict()),
        "README.md": _readme(project_id, template),
        "TASK.md": _task_guide(template),
        "AGENTS.md": _agent_instructions(project_id, template),
        ".gitignore": ".artifacts/\nreceipts.jsonl\n__pycache__/\n",
    }
    try:
        for relative, content in files.items():
            target = temporary / relative
            target.write_text(content, encoding="utf-8", newline="\n")
        # Recheck immediately before the atomic rename so an existing file,
        # directory, or broken symlink is never intentionally replaced.
        if os.path.lexists(destination):
            raise FileExistsError(f"destination already exists: {destination}")
        os.rename(temporary, destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return tuple(destination / relative for relative in sorted(files))


__all__ = [
    "SCAFFOLD_SCHEMA_VERSION",
    "default_project_id",
    "scaffold_project",
]
