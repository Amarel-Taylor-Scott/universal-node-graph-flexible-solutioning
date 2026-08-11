from __future__ import annotations

import json
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry as SchemaRegistry
from referencing import Resource

from solutiongraph import (
    CallableVerifier,
    Candidate,
    Cardinality,
    CompatibilityCatalog,
    Compiler,
    ExecutionCheckpoint,
    ExecutionPolicy,
    FailureMode,
    FileArtifactStore,
    FileCheckpointStore,
    GraphInput,
    GraphOutput,
    Idempotency,
    LoopPolicy,
    NodeCompatibilityProfile,
    NodeExecutionFailure,
    NodeSpec,
    ParameterSpec,
    Port,
    PortSemantics,
    ProgramGraph,
    ReferenceExecutor,
    ReferenceStreamEngine,
    Registry,
    SagaRunner,
    SagaStep,
    SearchBudget,
    SearchMode,
    SemanticSlot,
    SlotKind,
    StreamEvent,
    StructuredCompiler,
    SubgraphCatalog,
    SuccessiveHalvingPolicy,
    TopologyFamily,
    TopologySearchBudget,
    TopologySearchEngine,
    TopologyVariant,
    TrialObservation,
    ValueType,
    VerificationResult,
    WindowPolicy,
    callable_implementation_digest,
    export_provenance,
    run_successive_halving,
    sha256_digest,
)
from solutiongraph.cli import main
from solutiongraph.model import Edge
from solutiongraph.schemas import load_all_schemas

VALUE = ValueType("test.universal-value")
ROUTE = ValueType("test.universal-route")
STATE = ValueType("test.universal-state")

_SCHEMAS = load_all_schemas()
_SCHEMA_REGISTRY = SchemaRegistry().with_resources(
    (schema["$id"], Resource.from_contents(schema))
    for schema in _SCHEMAS.values()
)


def _validate_wire(schema_name, payload):
    errors = sorted(
        Draft202012Validator(
            _SCHEMAS[schema_name], registry=_SCHEMA_REGISTRY
        ).iter_errors(payload),
        key=lambda error: tuple(error.path),
    )
    assert not errors, "; ".join(error.message for error in errors)


def identity(value):
    return value


def increment(value):
    return value + 1


def increment_state(state):
    return state + 1


def prepare_value(value):
    return value


def decide_route(value):
    return "positive" if value >= 0 else "negative"


def positive_arm(value):
    return value * 2


def negative_arm(value):
    return abs(value)


def merge_arms(positive=None, negative=None):
    selected = [value for value in (positive, negative) if value is not None]
    if len(selected) != 1:
        raise ValueError("exactly one branch arm must be active")
    return selected[0]


_DURABLE_PREPARE_CALLS = 0
_DURABLE_FINISH_CALLS = 0


def durable_prepare(value):
    global _DURABLE_PREPARE_CALLS
    _DURABLE_PREPARE_CALLS += 1
    return value + 1


def durable_finish(value):
    global _DURABLE_FINISH_CALLS
    _DURABLE_FINISH_CALLS += 1
    if _DURABLE_FINISH_CALLS == 1:
        raise NodeExecutionFailure("test.pause", "external approval is pending")
    return value * 2


def saga_reserve_keyed(state, idempotency_key):
    return {**state, "reserved": True, "action_key": idempotency_key}


def saga_fail(state):
    raise NodeExecutionFailure("test.remote-failure", "commit failed")


def saga_release(state):
    return {**state, "reserved": False, "compensated": True}


def _node(
    node_id,
    function,
    capability,
    inputs,
    outputs,
    *,
    effects=(),
    permissions=(),
    failure_modes=(),
    parameters=(),
):
    return NodeSpec(
        id=node_id,
        version="1.0.0",
        implementation_digest=callable_implementation_digest(function),
        inputs=inputs,
        outputs=outputs,
        runtime="python",
        entrypoint=f"{function.__module__}:{function.__name__}",
        parameters=parameters,
        capabilities=(capability,),
        effects=effects,
        permissions=permissions,
        idempotency=Idempotency.IDEMPOTENT,
        failure_modes=failure_modes,
    )


def _registry(*nodes):
    return Registry(
        "test.universal-registry",
        "1.0.0",
        tuple(nodes),
        tuple(
            Candidate(
                f"candidate.{node.id}",
                node.id,
                node.version,
                node.implementation_digest,
            )
            for node in nodes
        ),
    )


def _selection(registry, mapping):
    return {
        slot: f"candidate.{node_id}"
        for slot, node_id in mapping.items()
    }


def _result_verifier(expected):
    def verify(context):
        accepted = context.outputs["result"] == expected
        return VerificationResult(
            accepted,
            "matched" if accepted else "mismatch",
            {"quality": float(accepted)},
        )

    return CallableVerifier("verifier.test.universal", verify)


def _branch_fixture(value):
    nodes = (
        _node("test.branch.prepare", prepare_value, "branch.prepare", (Port("value", VALUE),), (Port("value", VALUE),)),
        _node("test.branch.decide", decide_route, "branch.decide", (Port("value", VALUE),), (Port("route", ROUTE),)),
        _node("test.branch.positive", positive_arm, "branch.positive", (Port("value", VALUE),), (Port("result", VALUE),)),
        _node("test.branch.negative", negative_arm, "branch.negative", (Port("value", VALUE),), (Port("result", VALUE),)),
        _node(
            "test.branch.merge",
            merge_arms,
            "branch.merge",
            (
                Port("positive", VALUE, Cardinality.OPTIONAL),
                Port("negative", VALUE, Cardinality.OPTIONAL),
            ),
            (Port("result", VALUE),),
        ),
    )
    registry = _registry(*nodes)
    program = ProgramGraph(
        "test.conditional-branch",
        "1.0.0",
        "Select exactly one data-dependent branch.",
        "The selected branch result is emitted and the other branch is skipped.",
        (
            SemanticSlot("prepare", "Prepare input.", (Port("value", VALUE),), (Port("value", VALUE),), "Value is preserved.", required_capabilities=("branch.prepare",)),
            SemanticSlot("decide", "Choose a branch.", (Port("value", VALUE),), (Port("route", ROUTE),), "Route is explicit.", kind=SlotKind.BRANCH, required_capabilities=("branch.decide",)),
            SemanticSlot("positive", "Run positive arm.", (Port("value", VALUE),), (Port("result", VALUE),), "Positive transform completes.", required_capabilities=("branch.positive",), activation_slot="decide", activation_port="route", activation_values=("positive",)),
            SemanticSlot("negative", "Run negative arm.", (Port("value", VALUE),), (Port("result", VALUE),), "Negative transform completes.", required_capabilities=("branch.negative",), activation_slot="decide", activation_port="route", activation_values=("negative",)),
            SemanticSlot(
                "merge",
                "Merge exactly one active arm.",
                (
                    Port("positive", VALUE, Cardinality.OPTIONAL),
                    Port("negative", VALUE, Cardinality.OPTIONAL),
                ),
                (Port("result", VALUE),),
                "Exactly one optional input is present.",
                required_capabilities=("branch.merge",),
            ),
        ),
        (
            Edge("prepare", "value", "decide", "value"),
            Edge("prepare", "value", "positive", "value"),
            Edge("prepare", "value", "negative", "value"),
            Edge("positive", "result", "merge", "positive"),
            Edge("negative", "result", "merge", "negative"),
        ),
        (GraphInput("value", VALUE, "prepare", "value"),),
        (GraphOutput("result", VALUE, "merge", "result"),),
    )
    compiler = Compiler()
    space = compiler.admit(program, registry)
    plan = compiler.compile(
        program,
        registry,
        space,
        _selection(registry, {
            "prepare": "test.branch.prepare",
            "decide": "test.branch.decide",
            "positive": "test.branch.positive",
            "negative": "test.branch.negative",
            "merge": "test.branch.merge",
        }),
    )
    expected = value * 2 if value >= 0 else abs(value)
    result = ReferenceExecutor().execute(
        plan,
        program,
        registry,
        space,
        {"value": value},
        task_case_id="case.conditional-branch",
        verifier=_result_verifier(expected),
        policy=ExecutionPolicy(),
    )
    return result


def test_data_dependent_branch_executes_one_arm_and_receipts_the_skip():
    result = _branch_fixture(5)
    assert result.ok
    assert result.outputs == {"result": 10}
    outcomes = {item.slot_id: item.outcome for item in result.receipt.node_receipts}
    assert outcomes["positive"] == "succeeded"
    assert outcomes["negative"] == "skipped"
    assert result.receipt.metrics["skipped_slots"] == 1.0


def test_compiler_requires_optional_merge_for_conditional_outputs():
    program = ProgramGraph(
        "test.invalid-conditional-output",
        "1.0.0",
        "Demonstrate an unsafe conditional edge.",
        "Unsafe conditional outputs are rejected before execution.",
        (
            SemanticSlot(
                "decide",
                "Choose an arm.",
                (Port("value", VALUE),),
                (Port("route", ROUTE),),
                "A route is emitted.",
                kind=SlotKind.BRANCH,
            ),
            SemanticSlot(
                "arm",
                "Run conditionally.",
                (Port("value", VALUE),),
                (Port("result", VALUE),),
                "A result is emitted when active.",
                activation_slot="decide",
                activation_port="route",
                activation_values=("positive",),
            ),
            SemanticSlot(
                "sink",
                "Consume a required result.",
                (Port("result", VALUE),),
                (Port("result", VALUE),),
                "A required result is present.",
            ),
        ),
        (Edge("arm", "result", "sink", "result"),),
        (
            GraphInput("decision_value", VALUE, "decide", "value"),
            GraphInput("arm_value", VALUE, "arm", "value"),
        ),
        (GraphOutput("result", VALUE, "arm", "result"),),
    )
    codes = {item.code for item in Compiler().validate_program(program)}
    assert "UNG-ACTIVATION-004" in codes
    assert "UNG-ACTIVATION-005" in codes


def test_composites_and_bounded_loops_lower_to_plain_compiler_valid_dags():
    identity_node = _node("test.structure.identity", identity, "structure.identity", (Port("value", VALUE),), (Port("value", VALUE),))
    increment_node = _node("test.structure.increment", increment, "structure.increment", (Port("value", VALUE),), (Port("value", VALUE),))
    registry = _registry(identity_node, increment_node)
    child = ProgramGraph(
        "test.structure-child",
        "1.0.0",
        "Transform a value.",
        "The transformed value is emitted.",
        (
            SemanticSlot("identity", "Preserve.", (Port("value", VALUE),), (Port("value", VALUE),), "Preserved.", required_capabilities=("structure.identity",)),
            SemanticSlot("increment", "Increment.", (Port("value", VALUE),), (Port("value", VALUE),), "Incremented.", required_capabilities=("structure.increment",)),
        ),
        (Edge("identity", "value", "increment", "value"),),
        (GraphInput("value", VALUE, "identity", "value"),),
        (GraphOutput("value", VALUE, "increment", "value"),),
    )
    parent = ProgramGraph(
        "test.structure-parent",
        "1.0.0",
        "Transform a value.",
        "The transformed value is emitted.",
        (SemanticSlot("transform", "Run child graph.", (Port("value", VALUE),), (Port("value", VALUE),), "Child contract holds.", kind=SlotKind.COMPOSITE, subgraph_ref=child.id),),
        (),
        (GraphInput("value", VALUE, "transform", "value"),),
        (GraphOutput("value", VALUE, "transform", "value"),),
    )
    lowered = StructuredCompiler().lower(
        parent, SubgraphCatalog("catalog.test-structure", "1.0.0", (child,))
    )
    assert [slot.id for slot in lowered.program.slots] == [
        "transform/identity", "transform/increment"
    ]
    compiler = Compiler()
    space = compiler.admit(lowered.program, registry)
    plan = compiler.compile(
        lowered.program,
        registry,
        space,
        _selection(registry, {
            "transform/identity": "test.structure.identity",
            "transform/increment": "test.structure.increment",
        }),
    )
    result = ReferenceExecutor().execute(
        plan,
        lowered.program,
        registry,
        space,
        {"value": 1},
        task_case_id="case.composite",
        verifier=CallableVerifier(
            "verifier.test.composite",
            lambda context: VerificationResult(
                context.outputs["value"] == 2,
                "matched",
                {"quality": float(context.outputs["value"] == 2)},
            ),
        ),
        policy=ExecutionPolicy(),
    )
    assert result.ok

    loop_body = ProgramGraph(
        "test.loop-body",
        "1.0.0",
        "Transform loop state.",
        "One bounded iteration increments state.",
        (SemanticSlot("increment", "Increment state.", (Port("state", VALUE),), (Port("state", VALUE),), "State increments.", required_capabilities=("structure.increment",)),),
        (),
        (GraphInput("state", VALUE, "increment", "state"),),
        (GraphOutput("state", VALUE, "increment", "state"),),
    )
    loop_node = _node(
        "test.structure.increment-state",
        increment_state,
        "structure.increment",
        (Port("state", VALUE),),
        (Port("state", VALUE),),
    )
    loop_registry = _registry(loop_node)
    loop_parent = ProgramGraph(
        "test.loop-parent",
        "1.0.0",
        "Transform loop state.",
        "Three bounded iterations increment state.",
        (SemanticSlot("iterate", "Repeat a bounded body.", (Port("state", VALUE),), (Port("state", VALUE),), "Bound is honored.", kind=SlotKind.LOOP, subgraph_ref=loop_body.id),),
        (),
        (GraphInput("state", VALUE, "iterate", "state"),),
        (GraphOutput("state", VALUE, "iterate", "state"),),
    )
    loop_lowered = StructuredCompiler().lower(
        loop_parent,
        SubgraphCatalog("catalog.test-loop", "1.0.0", (loop_body,)),
        loop_policies=(LoopPolicy("iterate", 3, (("state", "state"),)),),
    )
    loop_space = compiler.admit(loop_lowered.program, loop_registry)
    loop_selection = {
        slot.id: loop_registry.candidates[0].id for slot in loop_lowered.program.slots
    }
    loop_plan = compiler.compile(
        loop_lowered.program, loop_registry, loop_space, loop_selection
    )
    loop_result = ReferenceExecutor().execute(
        loop_plan,
        loop_lowered.program,
        loop_registry,
        loop_space,
        {"state": 0},
        task_case_id="case.bounded-loop",
        verifier=CallableVerifier(
            "verifier.test.loop",
            lambda context: VerificationResult(
                context.outputs["state"] == 3,
                "bounded",
                {"quality": float(context.outputs["state"] == 3)},
            ),
        ),
        policy=ExecutionPolicy(),
    )
    assert loop_result.outputs == {"state": 3}
    assert len(loop_result.receipt.node_receipts) == 3


def test_topology_search_counts_and_searches_multiple_graph_shapes():
    identity_node = _node("test.topology.identity", identity, "topology.transform", (Port("value", VALUE),), (Port("value", VALUE),))
    increment_node = _node("test.topology.increment", increment, "topology.transform", (Port("value", VALUE),), (Port("value", VALUE),))
    registry = _registry(identity_node, increment_node)

    def program(program_id, slot_ids):
        slots = tuple(
            SemanticSlot(slot_id, "Transform.", (Port("value", VALUE),), (Port("value", VALUE),), "Typed value emitted.", required_capabilities=("topology.transform",))
            for slot_id in slot_ids
        )
        return ProgramGraph(
            program_id,
            "1.0.0",
            "Transform a value through an admissible topology.",
            "A typed result is emitted.",
            slots,
            tuple(
                Edge(left, "value", right, "value")
                for left, right in zip(slot_ids, slot_ids[1:], strict=False)
            ),
            (GraphInput("value", VALUE, slot_ids[0], "value"),),
            (GraphOutput("result", VALUE, slot_ids[-1], "value"),),
        )

    family = TopologyFamily(
        "topology.test-family",
        "1.0.0",
        "Transform a value through an admissible topology.",
        "A typed result is emitted.",
        (
            TopologyVariant("topology.direct", "Direct", program("test.topology-direct", ("transform",)), "Minimum depth.", 0.2),
            TopologyVariant("topology.staged", "Staged", program("test.topology-staged", ("prepare", "transform")), "Expose an extra interchangeable stage.", 0.0, "topology.direct", ("operator.insert-slot",)),
        ),
    )
    report = TopologySearchEngine().search(
        family,
        registry,
        budget=TopologySearchBudget(
            SearchBudget(SearchMode.EXHAUSTIVE, result_limit=10),
            result_limit=10,
        ),
    )
    assert report.total_topologies == 2
    assert report.total_cartesian_routes == 6
    assert report.evaluated_routes == 6
    assert report.complete
    assert {item.variant_id for item in report.proposals} == {
        "topology.direct", "topology.staged"
    }
    assert TopologySearchEngine().compile(
        family, registry, report.proposals[0]
    ).digest.startswith("sha256:")
    _validate_wire("topology-search-report.schema.json", report.to_dict())


def test_reference_executor_resumes_exact_checkpoint_without_repeating_prefix(tmp_path):
    global _DURABLE_PREPARE_CALLS, _DURABLE_FINISH_CALLS
    _DURABLE_PREPARE_CALLS = 0
    _DURABLE_FINISH_CALLS = 0
    prepare = _node("test.durable.prepare", durable_prepare, "durable.prepare", (Port("value", VALUE),), (Port("value", VALUE),))
    finish = _node(
        "test.durable.finish",
        durable_finish,
        "durable.finish",
        (Port("value", VALUE),),
        (Port("result", VALUE),),
        failure_modes=(FailureMode("test.pause", False),),
    )
    registry = _registry(prepare, finish)
    program = ProgramGraph(
        "test.durable-program",
        "1.0.0",
        "Resume a failed two-step execution.",
        "The completed prefix is not repeated.",
        (
            SemanticSlot("prepare", "Prepare.", (Port("value", VALUE),), (Port("value", VALUE),), "Prepared.", required_capabilities=("durable.prepare",)),
            SemanticSlot("finish", "Finish.", (Port("value", VALUE),), (Port("result", VALUE),), "Finished.", required_capabilities=("durable.finish",)),
        ),
        (Edge("prepare", "value", "finish", "value"),),
        (GraphInput("value", VALUE, "prepare", "value"),),
        (GraphOutput("result", VALUE, "finish", "result"),),
    )
    compiler = Compiler()
    space = compiler.admit(program, registry)
    plan = compiler.compile(
        program,
        registry,
        space,
        _selection(registry, {"prepare": prepare.id, "finish": finish.id}),
    )
    checkpoint_store = FileCheckpointStore(tmp_path / "checkpoints")
    artifact_store = FileArtifactStore(tmp_path / "artifacts")
    executor = ReferenceExecutor()
    first = executor.execute(
        plan,
        program,
        registry,
        space,
        {"value": 2},
        task_case_id="case.durable-resume",
        verifier=_result_verifier(6),
        policy=ExecutionPolicy(),
        artifact_store=artifact_store,
        checkpoint_store=checkpoint_store,
        checkpoint_id="checkpoint.test.durable-resume",
    )
    assert not first.ok
    assert _DURABLE_PREPARE_CALLS == 1
    checkpoint = checkpoint_store.load("checkpoint.test.durable-resume")
    assert checkpoint is not None
    _validate_wire("execution-checkpoint.schema.json", checkpoint.to_dict())
    tampered = checkpoint.to_dict()
    tampered["completed_slots"][0]["outputs"][0]["artifact"]["size_bytes"] += 1
    parsed_tampered = ExecutionCheckpoint.from_dict(tampered)
    with pytest.raises(ValueError, match="does not match its size"):
        parsed_tampered.completed_slots[0].outputs[0].load(artifact_store)
    tampered["completed_slots"][0]["outputs"][0]["artifact"]["digest"] = (
        sha256_digest("tampered")
    )
    with pytest.raises(ValueError, match="artifact digests do not match"):
        ExecutionCheckpoint.from_dict(tampered)
    checkpoint_path = (
        tmp_path / "checkpoints" / "checkpoint.test.durable-resume.json"
    )
    assert main(["checkpoint", "inspect", str(checkpoint_path), "--json"]) == 0
    resumed = executor.execute(
        plan,
        program,
        registry,
        space,
        {"value": 2},
        task_case_id="case.durable-resume",
        verifier=_result_verifier(6),
        policy=ExecutionPolicy(),
        artifact_store=artifact_store,
        checkpoint_store=checkpoint_store,
        checkpoint_id="checkpoint.test.durable-resume",
        resume=True,
    )
    assert resumed.ok
    assert resumed.outputs == {"result": 6}
    assert resumed.receipt.metrics["resumed_slots"] == 1.0
    assert _DURABLE_PREPARE_CALLS == 1
    assert checkpoint_store.load("checkpoint.test.durable-resume") is None


def test_streaming_watermarks_late_data_and_retractions_are_explicit():
    events = (
        StreamEvent("event.one", "account-a", 1.0, 1),
        StreamEvent("event.two", "account-a", 12.0, 12),
        StreamEvent("event.three", "account-a", 8.0, 8),
        StreamEvent("event.four", "account-a", 4.0, 4),
    )
    result = ReferenceStreamEngine().run(
        events,
        WindowPolicy("window.test.tumbling", 10.0, 10.0, allowed_lateness=5.0),
        sum,
    )
    assert result.receipt.accepted_event_count == 3
    assert result.receipt.late_accepted_count == 1
    assert result.receipt.dropped_event_ids == ("event.four",)
    first_window = [item for item in result.emissions if item.window_start == 0.0]
    assert [item.reason for item in first_window] == ["on-time", "late"]
    assert first_window[-1].value == 9
    assert first_window[-1].retracts == first_window[0].id
    for event in events:
        _validate_wire("stream-event.schema.json", event.to_dict())
    _validate_wire("stream-result.schema.json", result.to_dict())


def test_saga_compensates_completed_effect_nodes_in_reverse_order():
    reserve = _node(
        "test.saga.reserve", saga_reserve_keyed, "saga.reserve",
        (Port("state", STATE),), (Port("state", STATE),),
        effects=("external.write",), permissions=("external.write",),
        parameters=(
            ParameterSpec(
                "idempotency_key",
                "string",
                required=True,
                description="Saga-owned downstream idempotency token.",
            ),
        ),
    )
    fail = _node(
        "test.saga.fail", saga_fail, "saga.fail",
        (Port("state", STATE),), (Port("state", STATE),),
        effects=("external.write",), permissions=("external.write",),
    )
    release = _node(
        "test.saga.release", saga_release, "saga.release",
        (Port("state", STATE),), (Port("state", STATE),),
        effects=("external.write",), permissions=("external.write",),
    )
    result = SagaRunner().run(
        "saga.test.order",
        (
            SagaStep("saga-step.reserve", reserve, release, "order-1:reserve"),
            SagaStep("saga-step.commit", fail, None, "order-1:commit"),
        ),
        {"order": "order-1"},
        policy=ExecutionPolicy(
            allowed_effects=("external.write",),
            granted_permissions=("external.write",),
        ),
    )
    assert result.outcome == "compensated"
    assert result.compensated_steps == ("saga-step.reserve",)
    assert result.state["compensated"] is True
    assert result.state["action_key"] == "order-1:reserve"
    assert [item.phase for item in result.attempts] == [
        "action", "action", "compensation"
    ]
    assert [item.idempotency_key for item in result.attempts] == [
        "order-1:reserve",
        "order-1:commit",
        "order-1:reserve:compensation",
    ]
    assert result.validate() == []
    _validate_wire("saga-result.schema.json", result.to_dict())


def test_multi_fidelity_runner_profiles_ports_and_provenance_are_machine_readable():
    digests = tuple(sha256_digest(f"plan-{index}") for index in range(6))
    quality = {digest: float(index) for index, digest in enumerate(digests)}
    run = run_successive_halving(
        digests,
        SuccessiveHalvingPolicy(
            "policy.test.halving",
            "metric.quality",
            "maximize",
            1.0,
            9.0,
            reduction_factor=3,
        ),
        lambda digest, resource: TrialObservation(
            digest, resource, quality[digest], accepted=True
        ),
    )
    assert [item.resource for item in run.rungs] == [1.0, 3.0, 9.0]
    assert run.finalist_plan_digests == (digests[-1],)
    assert run.consumed_resource == 21.0
    _validate_wire("successive-halving-run.schema.json", run.to_dict())

    source = _node("test.compat.source", identity, "compat.source", (Port("value", VALUE),), (Port("value", VALUE),))
    target = _node("test.compat.target", identity, "compat.target", (Port("value", VALUE),), (Port("value", VALUE),))
    registry = _registry(source, target)
    catalog = CompatibilityCatalog(
        "compatibility.test",
        "1.0.0",
        (
            NodeCompatibilityProfile(
                source.id,
                source.version,
                source.implementation_digest,
                ports=(PortSemantics("output", "value", False, "event-time", "event-time", "timestamp", ("data.customer",)),),
                state_mode="stateless",
                cache_mode="content",
            ),
            NodeCompatibilityProfile(
                target.id,
                target.version,
                target.implementation_digest,
                ports=(PortSemantics("input", "value", False, "stable", "processing-time", data_classifications=()),),
                state_mode="stateless",
                cache_mode="never",
            ),
        ),
    )
    assert not catalog.validate(registry)
    edge_problems = catalog.edge_problems(source, "value", target, "value")
    assert any("ordering" in problem for problem in edge_problems)
    assert any("time domain" in problem for problem in edge_problems)
    assert any("data.customer" in problem for problem in edge_problems)
    assert catalog.node_problems(
        source,
        data_residency="residency.us",
        require_checkpointable=True,
        require_compensation=True,
        require_complete=True,
    ) == (
        "data residency compatibility is unknown",
        "node is not declared checkpointable",
        "node has no declared compensation node",
    )
    _validate_wire("compatibility-catalog.schema.json", catalog.to_dict())

    branch = _branch_fixture(-4)
    bundle = export_provenance(branch.receipt)
    assert bundle.w3c_prov["activity"]
    assert bundle.openlineage["eventType"] == "COMPLETE"
    assert str(UUID(bundle.openlineage["run"]["runId"])) == (
        bundle.openlineage["run"]["runId"]
    )
    assert len(bundle.w3c_prov["activity"]) == (
        1 + len(branch.receipt.node_receipts)
    )
    assert bundle.slsa_provenance["predicateType"] == "https://slsa.dev/provenance/v1"
    assert bundle.digest.startswith("sha256:")
    _validate_wire(
        "openlineage-execution-facet.schema.json",
        bundle.openlineage["run"]["facets"]["solutiongraph_execution"],
    )
    for output in bundle.openlineage["outputs"]:
        _validate_wire(
            "openlineage-artifact-facet.schema.json",
            output["facets"]["solutiongraph_artifact"],
        )


def test_provenance_export_cli_round_trips_a_run_receipt(tmp_path):
    receipt = _branch_fixture(3).receipt
    source = tmp_path / "receipt.json"
    output = tmp_path / "provenance.json"
    source.write_text(json.dumps(receipt.to_dict()), encoding="utf-8")
    assert main([
        "provenance",
        "export",
        str(source),
        "--format",
        "bundle",
        "--output",
        str(output),
    ]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["receipt_id"] == receipt.id
    assert payload["openlineage"]["eventType"] == "COMPLETE"
