from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from solutiongraph import (
    CallableVerifier,
    Candidate,
    Compiler,
    ExecutionError,
    ExecutionPolicy,
    FileArtifactStore,
    GraphInput,
    GraphOutput,
    Idempotency,
    MemoryArtifactStore,
    NodeExecutionFailure,
    NodeSpec,
    Port,
    ProgramGraph,
    ReferenceExecutor,
    Registry,
    SemanticSlot,
    ValueType,
    VerificationResult,
    callable_implementation_digest,
    digest_value,
    sha256_digest,
)
from solutiongraph.examples import EXAMPLE_TASKS, run_example
from solutiongraph.examples.tasks import EXAMPLE_REGISTRY
from solutiongraph.schemas import SCHEMA_NAMES, load_all_schemas

TEST_VALUE = ValueType("test.execution-value")
_FLAKY_CALLS = 0


def always_fails(value):
    raise NodeExecutionFailure("test.primary-failed", "primary failed")


def flaky_identity(value):
    global _FLAKY_CALLS
    _FLAKY_CALLS += 1
    if _FLAKY_CALLS == 1:
        raise NodeExecutionFailure("test.transient", "retry me", retryable=True)
    return value


def stable_identity(value):
    return value


def _one_slot_fixture(*functions):
    nodes = tuple(
        NodeSpec(
            id=f"test.node.{function.__name__.replace('_', '-')}",
            version="1.0.0",
            implementation_digest=callable_implementation_digest(function),
            inputs=(Port("value", TEST_VALUE),),
            outputs=(Port("value", TEST_VALUE),),
            runtime="python",
            entrypoint=f"tests.test_solutiongraph_execution:{function.__name__}",
            capabilities=("test.identity",),
            idempotency=Idempotency.IDEMPOTENT,
        )
        for function in functions
    )
    candidates = tuple(
        Candidate(
            id=f"candidate.{node.id}",
            node_id=node.id,
            node_version=node.version,
            implementation_digest=node.implementation_digest,
        )
        for node in nodes
    )
    program = ProgramGraph(
        id="test.execution-program",
        version="1.0.0",
        task="Return the supplied value.",
        success_contract="An independent verifier observes structural equality.",
        slots=(SemanticSlot(
            id="identity",
            purpose="Return the value.",
            inputs=(Port("value", TEST_VALUE),),
            outputs=(Port("value", TEST_VALUE),),
            success_contract="Output equals input.",
            required_capabilities=("test.identity",),
        ),),
        edges=(),
        inputs=(GraphInput("value", TEST_VALUE, "identity", "value"),),
        outputs=(GraphOutput("value", TEST_VALUE, "identity", "value"),),
    )
    registry = Registry("test.execution-registry", "1.0.0", nodes, candidates)
    return program, registry


def _equality_verifier(context):
    accepted = context.outputs["value"] == context.inputs["value"]
    return VerificationResult(accepted, "equal" if accepted else "different", {"quality": float(accepted)})


def test_memory_and_file_artifact_stores_are_content_addressed_and_deduplicated(tmp_path):
    memory = MemoryArtifactStore()
    first = memory.put_json({"b": 2, "a": 1})
    second = memory.put_json({"a": 1, "b": 2})
    assert first.digest == second.digest
    assert memory.get_json(first.digest) == {"a": 1, "b": 2}

    files = FileArtifactStore(tmp_path / "artifacts")
    stored = files.put_bytes(b"real bytes", media_type="application/octet-stream")
    assert files.get_bytes(stored.digest) == b"real bytes"
    assert stored.uri.startswith("file:")
    assert digest_value({"payload": b"real bytes"}).startswith("sha256:")


def test_compiler_freezes_ordered_fallbacks_and_executor_activates_them():
    program, registry = _one_slot_fixture(always_fails, stable_identity)
    compiler = Compiler()
    space = compiler.admit(program, registry)
    primary, fallback = (candidate.id for candidate in registry.candidates)
    plan = compiler.compile(
        program,
        registry,
        space,
        {"identity": primary},
        fallbacks={"identity": (fallback,)},
    )
    assert plan.admitted_space_digest == space.digest
    assert [item.candidate_id for item in plan.fallbacks] == [fallback]

    result = ReferenceExecutor().execute(
        plan,
        program,
        registry,
        space,
        {"value": {"answer": 42}},
        task_case_id="case.fallback",
        verifier=CallableVerifier("verifier.test.equality", _equality_verifier),
        policy=ExecutionPolicy(),
    )
    assert result.ok
    assert result.outputs == {"value": {"answer": 42}}
    assert [item.outcome for item in result.receipt.node_receipts] == ["failed", "succeeded"]
    assert result.receipt.assignments == (("identity", fallback),)
    assert result.receipt.metrics["fallback_activations"] == 1.0
    assert result.receipt.verifier_digest == callable_implementation_digest(
        _equality_verifier
    )


def test_retry_requires_explicit_retryable_failure_and_idempotency():
    global _FLAKY_CALLS
    _FLAKY_CALLS = 0
    program, registry = _one_slot_fixture(flaky_identity)
    compiler = Compiler()
    space = compiler.admit(program, registry)
    plan = compiler.compile(program, registry, space, {"identity": registry.candidates[0].id})
    result = ReferenceExecutor().execute(
        plan,
        program,
        registry,
        space,
        {"value": "retry-safe"},
        task_case_id="case.retry",
        verifier=CallableVerifier("verifier.test.equality", _equality_verifier),
        policy=ExecutionPolicy(max_attempts_per_candidate=2),
    )
    assert result.ok
    assert [item.attempt for item in result.receipt.node_receipts] == [1, 2]
    assert result.receipt.metrics["retries"] == 1.0


def test_runtime_rechecks_policy_and_implementation_identity():
    program, registry = _one_slot_fixture(stable_identity)
    original = registry.nodes[0]
    changed_node = replace(original, implementation_digest=sha256_digest("wrong bytes"))
    changed_candidate = replace(
        registry.candidates[0], implementation_digest=changed_node.implementation_digest
    )
    changed_registry = replace(
        registry, nodes=(changed_node,), candidates=(changed_candidate,)
    )
    compiler = Compiler()
    space = compiler.admit(program, changed_registry)
    plan = compiler.compile(
        program, changed_registry, space, {"identity": changed_candidate.id}
    )
    result = ReferenceExecutor().execute(
        plan,
        program,
        changed_registry,
        space,
        {"value": 1},
        task_case_id="case.digest-mismatch",
        verifier=CallableVerifier("verifier.test.equality", _equality_verifier),
        policy=ExecutionPolicy(),
    )
    assert not result.ok
    assert result.receipt.failure_class == "runtime.implementation-digest-mismatch"

    with pytest.raises(ExecutionError, match="in-process"):
        ReferenceExecutor().execute(
            plan,
            program,
            changed_registry,
            space,
            {"value": 1},
            task_case_id="case.policy",
            verifier=CallableVerifier("verifier.test.equality", _equality_verifier),
            policy=ExecutionPolicy(allow_in_process_python=False),
        )


@pytest.mark.parametrize("example", EXAMPLE_TASKS, ids=lambda item: item.id)
def test_every_real_world_example_compiles_full_registry_and_executes_real_routes(example):
    space, plans = example.compile()
    assert len(space.decisions) == len(example.program.slots) * len(EXAMPLE_REGISTRY.candidates)
    assert all(space.choices_for(slot.id) for slot in example.program.slots)
    assert len({plan.digest for plan in plans.values()}) == len(plans)

    report = run_example(example.id, route="all")
    receipts = report["experiment"]["receipts"]
    assert len(receipts) == len(example.routes)
    assert any(receipt["accepted"] is True for receipt in receipts)
    assert all(receipt["admitted_space_digest"] == space.digest for receipt in receipts)
    assert all(receipt["node_receipts"] for receipt in receipts)


def test_new_execution_wire_schemas_are_bundled_and_strict_json_documents():
    schemas = load_all_schemas()
    assert set(schemas) == set(SCHEMA_NAMES)
    assert {
        "admitted-space.schema.json",
        "artifact-record.schema.json",
        "execution-policy.schema.json",
        "verification-result.schema.json",
    }.issubset(schemas)
    assert all(schema.get("additionalProperties") is False for name, schema in schemas.items() if name in {
        "admitted-space.schema.json",
        "artifact-record.schema.json",
        "execution-policy.schema.json",
        "verification-result.schema.json",
    })


def test_five_notebooks_are_valid_and_call_the_executable_example_api():
    notebooks = sorted(Path("notebooks").glob("0[1-5]_*.ipynb"))
    assert len(notebooks) == 5
    for path in notebooks:
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["nbformat"] == 4
        code = "\n".join(
            "".join(cell.get("source", []))
            for cell in document["cells"]
            if cell["cell_type"] == "code"
        )
        assert "run_example" in code
        compile(code, str(path), "exec")
