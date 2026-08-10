from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import tomllib

from solutiongraph import (
    CallableVerifier,
    Compiler,
    ExecutionPolicy,
    JsonlReceiptJournal,
    LedgerIntegrityError,
    NodeExecutionFailure,
    NodeSpec,
    ReferenceExecutor,
    RunReceipt,
    RuntimeRegistry,
    SubprocessPythonRuntime,
    callable_implementation_digest,
    scaffold_project,
)
from solutiongraph.examples import run_example
from solutiongraph.ledger import JOURNAL_SCHEMA_VERSION
from solutiongraph.scaffold import SCAFFOLD_SCHEMA_VERSION
from solutiongraph.template_library import REFERENCE_TEMPLATES
from tests.test_solutiongraph_execution import (
    _equality_verifier,
    _one_slot_fixture,
    stable_identity,
)


def noisy_bytes(value: bytes) -> bytes:
    print("node output must not corrupt the protocol")
    return value


def slow_identity(value):
    time.sleep(0.25)
    return value


def test_subprocess_runtime_executes_frozen_plan_without_in_process_authority():
    program, registry = _one_slot_fixture(stable_identity)

    compiler = Compiler()
    space = compiler.admit(program, registry)
    plan = compiler.compile(
        program, registry, space, {"identity": registry.candidates[0].id}
    )
    executor = ReferenceExecutor(
        runtimes=RuntimeRegistry({
            "python": SubprocessPythonRuntime(max_memory_mb=None)
        })
    )
    result = executor.execute(
        plan,
        program,
        registry,
        space,
        {"value": {"answer": 42}},
        task_case_id="case.subprocess",
        verifier=CallableVerifier("verifier.test.equality", _equality_verifier),
        policy=ExecutionPolicy(allow_in_process_python=False),
    )
    assert result.ok
    assert result.outputs == {"value": {"answer": 42}}
    node_receipt = result.receipt.node_receipts[0]
    assert node_receipt.runtime == "python"
    assert node_receipt.runtime_adapter == "solutiongraph.python-subprocess-v1"
    assert node_receipt.isolation == "subprocess"


def test_subprocess_wire_codec_preserves_bytes_and_captures_node_stdout():
    runtime = SubprocessPythonRuntime(max_memory_mb=None)
    node = NodeSpec(
        id="test.node.noisy-bytes",
        version="1.0.0",
        implementation_digest=callable_implementation_digest(noisy_bytes),
        inputs=(),
        outputs=(),
        runtime="python",
        entrypoint=(
            "tests.test_solutiongraph_release_readiness:noisy_bytes"
        ),
    )
    assert runtime.invoke(node, {"value": b"\x00real-bytes"}, {}) == b"\x00real-bytes"


def test_subprocess_runtime_enforces_wall_clock_timeout():
    runtime = SubprocessPythonRuntime(
        timeout_seconds=0.05,
        max_memory_mb=None,
        max_cpu_seconds=None,
    )
    node = NodeSpec(
        id="test.node.slow",
        version="1.0.0",
        implementation_digest=callable_implementation_digest(slow_identity),
        inputs=(),
        outputs=(),
        runtime="python",
        entrypoint="tests.test_solutiongraph_release_readiness:slow_identity",
    )
    with pytest.raises(NodeExecutionFailure, match="exceeded"):
        runtime.invoke(node, {"value": 1}, {})


def test_receipt_journal_is_durable_round_trippable_and_tamper_evident(tmp_path):
    report = run_example("document-to-schema", route="baseline")

    receipt = RunReceipt.from_dict(report["execution"]["receipt"])
    path = tmp_path / "receipts.jsonl"
    journal = JsonlReceiptJournal(path)
    status = journal.append(receipt)
    assert status.receipt_count == 1
    assert status.head_digest.startswith("sha256:")
    assert journal.read().receipts == (receipt,)
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["schema_version"] == JOURNAL_SCHEMA_VERSION

    with pytest.raises(ValueError, match="globally unique"):
        journal.append(receipt)

    record["receipt"]["outcome"] = "failed"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(LedgerIntegrityError, match="digest does not match"):
        journal.status()


def test_receipt_journal_verification_does_not_create_a_missing_file(tmp_path):
    path = tmp_path / "missing.jsonl"
    with pytest.raises(FileNotFoundError):
        JsonlReceiptJournal(path).status()
    assert not path.exists()


def test_experiment_persists_each_subprocess_receipt_immediately(tmp_path):
    journal = JsonlReceiptJournal(tmp_path / "experiment.jsonl")
    report = run_example(
        "image-check-and-process",
        route="all",
        runtime="subprocess",
        receipt_journal=journal,
    )
    assert report["runtime"] == "subprocess"
    assert journal.status().receipt_count == len(report["experiment"]["receipts"])


def test_scaffold_is_transactional_complete_and_non_destructive(tmp_path):
    template = next(
        item
        for item in REFERENCE_TEMPLATES.templates
        if item.id == "template.document-intelligence"
    )
    destination = tmp_path / "invoice-graph"
    written = scaffold_project(destination, template)
    assert {path.name for path in written} == {
        ".gitignore",
        "AGENTS.md",
        "README.md",
        "TASK.md",
        "solution-template.json",
        "solutiongraph-project.json",
    }
    project = json.loads(
        (destination / "solutiongraph-project.json").read_text(encoding="utf-8")
    )
    assert project == {
        "schema_version": SCAFFOLD_SCHEMA_VERSION,
        "project_id": "project.invoice-graph",
        "template_id": template.id,
        "template_version": template.version,
        "template_digest": template.digest,
        "status": "template_selected",
        "next_gate": "instantiate_task_contract",
    }
    assert json.loads(
        (destination / "solution-template.json").read_text(encoding="utf-8")
    ) == template.to_dict()
    with pytest.raises(FileExistsError):
        scaffold_project(destination, template)

    broken_link = tmp_path / "existing-link"
    broken_link.symlink_to(tmp_path / "absent-target")
    with pytest.raises(FileExistsError):
        scaffold_project(broken_link, template)


def test_distribution_and_import_versions_match_and_release_is_alpha():
    root = Path(__file__).parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    from solutiongraph import __version__

    assert metadata["project"]["version"] == __version__ == "0.3.0"
    assert "Development Status :: 3 - Alpha" in metadata["project"]["classifiers"]
