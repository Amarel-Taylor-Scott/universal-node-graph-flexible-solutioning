"""Installed-wheel conformance checks for advanced reference mechanisms."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from solutiongraph.adaptive import (
    SuccessiveHalvingPolicy,
    TrialObservation,
    run_successive_halving,
)
from solutiongraph.artifacts import MemoryArtifactStore
from solutiongraph.compiler import Compiler
from solutiongraph.durable import MemoryCheckpointStore
from solutiongraph.evidence import RunReceipt
from solutiongraph.executor import (
    CallableVerifier,
    ExecutionPolicy,
    NodeExecutionFailure,
    ReferenceExecutor,
    VerificationResult,
    callable_implementation_digest,
)
from solutiongraph.model import (
    Candidate,
    Cardinality,
    Edge,
    GraphInput,
    GraphOutput,
    Idempotency,
    NodeSpec,
    Port,
    ProgramGraph,
    Registry,
    SemanticSlot,
    SlotKind,
    ValueType,
    sha256_digest,
)
from solutiongraph.provenance import export_provenance
from solutiongraph.saga import SagaRunner, SagaStep
from solutiongraph.search import SearchBudget, SearchMode
from solutiongraph.streaming import ReferenceStreamEngine, StreamEvent, WindowPolicy
from solutiongraph.structured import LoopPolicy, StructuredCompiler, SubgraphCatalog
from solutiongraph.topology import (
    TopologyFamily,
    TopologySearchBudget,
    TopologySearchEngine,
    TopologyVariant,
)

CONFORMANCE_MODEL_VERSION = "0.1"
CONTROL_VALUE = ValueType("conformance.value")
CONTROL_ROUTE = ValueType("conformance.route")
CONTROL_STATE = ValueType("conformance.state")
_DURABLE_PREPARE_CALLS = 0
_DURABLE_FINISH_CALLS = 0


def preserve(value):
    return value


def increment(value):
    return value + 1


def increment_state(state):
    return state + 1


def durable_prepare(value):
    global _DURABLE_PREPARE_CALLS
    _DURABLE_PREPARE_CALLS += 1
    return value + 1


def durable_finish(value):
    global _DURABLE_FINISH_CALLS
    _DURABLE_FINISH_CALLS += 1
    if _DURABLE_FINISH_CALLS == 1:
        raise NodeExecutionFailure("conformance.pause", "simulated interruption")
    return value * 2


def choose(value):
    return "positive" if value >= 0 else "negative"


def double(value):
    return value * 2


def absolute(value):
    return abs(value)


def merge(positive=None, negative=None):
    present = [value for value in (positive, negative) if value is not None]
    if len(present) != 1:
        raise ValueError("one branch result is required")
    return present[0]


def reserve(state):
    return {**state, "reserved": True}


def fail_commit(state):
    raise NodeExecutionFailure("conformance.commit-failed", "expected failure")


def release(state):
    return {**state, "reserved": False, "compensated": True}


def _node(
    id_: str,
    function: Callable[..., Any],
    capability: str,
    inputs: tuple[Port, ...],
    outputs: tuple[Port, ...],
    *,
    effects: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
) -> NodeSpec:
    return NodeSpec(
        id=id_,
        version="1.0.0",
        implementation_digest=callable_implementation_digest(function),
        inputs=inputs,
        outputs=outputs,
        runtime="python",
        entrypoint=f"{function.__module__}:{function.__name__}",
        capabilities=(capability,),
        effects=effects,
        permissions=permissions,
        idempotency=Idempotency.IDEMPOTENT,
    )


def _registry(id_: str, nodes: tuple[NodeSpec, ...]) -> Registry:
    return Registry(
        id_,
        "1.0.0",
        nodes,
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


@dataclass(frozen=True)
class ConformanceCheck:
    id: str
    passed: bool
    details: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "passed": self.passed, "details": self.details}


@dataclass(frozen=True)
class ConformanceResult:
    checks: tuple[ConformanceCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conformance_model_version": CONFORMANCE_MODEL_VERSION,
            "ok": self.ok,
            "check_count": len(self.checks),
            "checks": [check.to_dict() for check in self.checks],
        }


def _branch_run() -> tuple[bool, RunReceipt]:
    nodes = (
        _node("conformance.prepare", preserve, "control.prepare", (Port("value", CONTROL_VALUE),), (Port("value", CONTROL_VALUE),)),
        _node("conformance.choose", choose, "control.choose", (Port("value", CONTROL_VALUE),), (Port("route", CONTROL_ROUTE),)),
        _node("conformance.double", double, "control.positive", (Port("value", CONTROL_VALUE),), (Port("result", CONTROL_VALUE),)),
        _node("conformance.absolute", absolute, "control.negative", (Port("value", CONTROL_VALUE),), (Port("result", CONTROL_VALUE),)),
        _node(
            "conformance.merge", merge, "control.merge",
            (
                Port("positive", CONTROL_VALUE, Cardinality.OPTIONAL),
                Port("negative", CONTROL_VALUE, Cardinality.OPTIONAL),
            ),
            (Port("result", CONTROL_VALUE),),
        ),
    )
    registry = _registry("registry.conformance-branch", nodes)
    slots = (
        SemanticSlot("prepare", "Prepare.", (Port("value", CONTROL_VALUE),), (Port("value", CONTROL_VALUE),), "Preserved.", required_capabilities=("control.prepare",)),
        SemanticSlot("choose", "Choose.", (Port("value", CONTROL_VALUE),), (Port("route", CONTROL_ROUTE),), "Route emitted.", kind=SlotKind.BRANCH, required_capabilities=("control.choose",)),
        SemanticSlot("positive", "Positive arm.", (Port("value", CONTROL_VALUE),), (Port("result", CONTROL_VALUE),), "Doubled.", required_capabilities=("control.positive",), activation_slot="choose", activation_port="route", activation_values=("positive",)),
        SemanticSlot("negative", "Negative arm.", (Port("value", CONTROL_VALUE),), (Port("result", CONTROL_VALUE),), "Absolute.", required_capabilities=("control.negative",), activation_slot="choose", activation_port="route", activation_values=("negative",)),
        SemanticSlot(
            "merge", "Merge.",
            (
                Port("positive", CONTROL_VALUE, Cardinality.OPTIONAL),
                Port("negative", CONTROL_VALUE, Cardinality.OPTIONAL),
            ),
            (Port("result", CONTROL_VALUE),),
            "One result emitted.", required_capabilities=("control.merge",),
        ),
    )
    program = ProgramGraph(
        "conformance.branch-program", "1.0.0",
        "Execute one data-dependent branch.", "Exactly one arm produces the result.",
        slots,
        (
            Edge("prepare", "value", "choose", "value"),
            Edge("prepare", "value", "positive", "value"),
            Edge("prepare", "value", "negative", "value"),
            Edge("positive", "result", "merge", "positive"),
            Edge("negative", "result", "merge", "negative"),
        ),
        (GraphInput("value", CONTROL_VALUE, "prepare", "value"),),
        (GraphOutput("result", CONTROL_VALUE, "merge", "result"),),
    )
    compiler = Compiler()
    space = compiler.admit(program, registry)
    selection = {
        slot.id: next(
            candidate for candidate in space.choices_for(slot.id)
        )
        for slot in slots
    }
    plan = compiler.compile(program, registry, space, selection)
    result = ReferenceExecutor().execute(
        plan, program, registry, space, {"value": 3},
        task_case_id="case.conformance-branch",
        verifier=CallableVerifier(
            "verifier.conformance-branch",
            lambda context: VerificationResult(
                context.outputs["result"] == 6,
                "branch-checked",
                {"quality": float(context.outputs["result"] == 6)},
            ),
        ),
        policy=ExecutionPolicy(),
    )
    return (
        result.ok
        and sum(item.outcome == "skipped" for item in result.receipt.node_receipts) == 1,
        result.receipt,
    )


def _structured_check() -> bool:
    child = ProgramGraph(
        "conformance.child", "1.0.0", "Increment state.", "State increments once.",
        (SemanticSlot("increment", "Increment.", (Port("state", CONTROL_VALUE),), (Port("state", CONTROL_VALUE),), "Incremented.", required_capabilities=("control.increment",)),),
        (),
        (GraphInput("state", CONTROL_VALUE, "increment", "state"),),
        (GraphOutput("state", CONTROL_VALUE, "increment", "state"),),
    )
    parent = ProgramGraph(
        "conformance.loop", "1.0.0", "Increment state.", "State increments three times.",
        (SemanticSlot("loop", "Bounded loop.", (Port("state", CONTROL_VALUE),), (Port("state", CONTROL_VALUE),), "Bound honored.", kind=SlotKind.LOOP, subgraph_ref=child.id),),
        (),
        (GraphInput("state", CONTROL_VALUE, "loop", "state"),),
        (GraphOutput("state", CONTROL_VALUE, "loop", "state"),),
    )
    lowered = StructuredCompiler().lower(
        parent,
        SubgraphCatalog("catalog.conformance", "1.0.0", (child,)),
        loop_policies=(LoopPolicy("loop", 3, (("state", "state"),)),),
    )
    return (
        len(lowered.program.slots) == 3
        and not Compiler().validate_program(lowered.program)
        and lowered.receipt.expansions[0].iterations == 3
    )


def _topology_check() -> bool:
    node = _node("conformance.topology.identity", preserve, "control.identity", (Port("value", CONTROL_VALUE),), (Port("value", CONTROL_VALUE),))
    registry = _registry("registry.conformance-topology", (node,))

    def graph(id_: str, slots: tuple[str, ...]) -> ProgramGraph:
        return ProgramGraph(
            id_, "1.0.0", "Preserve a value.", "The same value is emitted.",
            tuple(SemanticSlot(slot, "Preserve.", (Port("value", CONTROL_VALUE),), (Port("value", CONTROL_VALUE),), "Preserved.", required_capabilities=("control.identity",)) for slot in slots),
            tuple(Edge(left, "value", right, "value") for left, right in zip(slots, slots[1:], strict=False)),
            (GraphInput("value", CONTROL_VALUE, slots[0], "value"),),
            (GraphOutput("result", CONTROL_VALUE, slots[-1], "value"),),
        )

    family = TopologyFamily(
        "topology.conformance", "1.0.0", "Preserve a value.", "The same value is emitted.",
        (
            TopologyVariant("topology.conformance-direct", "Direct", graph("conformance.direct", ("preserve",)), "Minimum depth."),
            TopologyVariant("topology.conformance-staged", "Staged", graph("conformance.staged", ("prepare", "preserve")), "Explicit preparation."),
        ),
    )
    report = TopologySearchEngine().search(
        family,
        registry,
        budget=TopologySearchBudget(
            SearchBudget(SearchMode.EXHAUSTIVE, result_limit=4), result_limit=4
        ),
    )
    return report.complete and report.total_topologies == 2 and report.evaluated_routes == 2


def _stream_check() -> bool:
    result = ReferenceStreamEngine().run(
        (
            StreamEvent("event.conformance-one", "k", 1.0, 1),
            StreamEvent("event.conformance-two", "k", 12.0, 12),
            StreamEvent("event.conformance-late", "k", 8.0, 8),
        ),
        WindowPolicy("window.conformance", 10.0, 10.0, allowed_lateness=5.0),
        sum,
    )
    return result.receipt.late_accepted_count == 1 and any(
        item.reason == "late" and item.retracts for item in result.emissions
    )


def _durable_check() -> bool:
    global _DURABLE_PREPARE_CALLS, _DURABLE_FINISH_CALLS
    _DURABLE_PREPARE_CALLS = 0
    _DURABLE_FINISH_CALLS = 0
    prepare_node = _node(
        "conformance.durable.prepare",
        durable_prepare,
        "durable.prepare",
        (Port("value", CONTROL_VALUE),),
        (Port("value", CONTROL_VALUE),),
    )
    finish_node = _node(
        "conformance.durable.finish",
        durable_finish,
        "durable.finish",
        (Port("value", CONTROL_VALUE),),
        (Port("result", CONTROL_VALUE),),
    )
    registry = _registry(
        "registry.conformance-durable", (prepare_node, finish_node)
    )
    program = ProgramGraph(
        "conformance.durable-program",
        "1.0.0",
        "Resume an interrupted graph.",
        "The completed prefix is not repeated.",
        (
            SemanticSlot(
                "prepare",
                "Prepare.",
                (Port("value", CONTROL_VALUE),),
                (Port("value", CONTROL_VALUE),),
                "Prepared.",
                required_capabilities=("durable.prepare",),
            ),
            SemanticSlot(
                "finish",
                "Finish.",
                (Port("value", CONTROL_VALUE),),
                (Port("result", CONTROL_VALUE),),
                "Finished.",
                required_capabilities=("durable.finish",),
            ),
        ),
        (Edge("prepare", "value", "finish", "value"),),
        (GraphInput("value", CONTROL_VALUE, "prepare", "value"),),
        (GraphOutput("result", CONTROL_VALUE, "finish", "result"),),
    )
    compiler = Compiler()
    space = compiler.admit(program, registry)
    plan = compiler.compile(
        program,
        registry,
        space,
        {
            "prepare": f"candidate.{prepare_node.id}",
            "finish": f"candidate.{finish_node.id}",
        },
    )
    checkpoint_store = MemoryCheckpointStore()
    artifact_store = MemoryArtifactStore()
    verifier = CallableVerifier(
        "verifier.conformance-durable",
        lambda context: VerificationResult(
            context.outputs.get("result") == 6,
            "durable-checked",
            {"quality": float(context.outputs.get("result") == 6)},
        ),
    )
    executor = ReferenceExecutor()
    first = executor.execute(
        plan,
        program,
        registry,
        space,
        {"value": 2},
        task_case_id="case.conformance-durable",
        verifier=verifier,
        policy=ExecutionPolicy(),
        artifact_store=artifact_store,
        checkpoint_store=checkpoint_store,
        checkpoint_id="checkpoint.conformance-durable",
    )
    resumed = executor.execute(
        plan,
        program,
        registry,
        space,
        {"value": 2},
        task_case_id="case.conformance-durable",
        verifier=verifier,
        policy=ExecutionPolicy(),
        artifact_store=artifact_store,
        checkpoint_store=checkpoint_store,
        checkpoint_id="checkpoint.conformance-durable",
        resume=True,
    )
    return (
        not first.ok
        and resumed.ok
        and resumed.outputs == {"result": 6}
        and resumed.receipt.metrics.get("resumed_slots") == 1.0
        and _DURABLE_PREPARE_CALLS == 1
    )


def _saga_check() -> bool:
    reserve_node = _node(
        "conformance.saga.reserve", reserve, "saga.reserve",
        (Port("state", CONTROL_STATE),), (Port("state", CONTROL_STATE),),
        effects=("external.write",), permissions=("external.write",),
    )
    fail_node = _node(
        "conformance.saga.fail", fail_commit, "saga.commit",
        (Port("state", CONTROL_STATE),), (Port("state", CONTROL_STATE),),
        effects=("external.write",), permissions=("external.write",),
    )
    release_node = _node(
        "conformance.saga.release", release, "saga.release",
        (Port("state", CONTROL_STATE),), (Port("state", CONTROL_STATE),),
        effects=("external.write",), permissions=("external.write",),
    )
    result = SagaRunner().run(
        "saga.conformance",
        (
            SagaStep("saga-step.conformance-reserve", reserve_node, release_node, "reserve-1"),
            SagaStep("saga-step.conformance-commit", fail_node, None, "commit-1"),
        ),
        {},
        policy=ExecutionPolicy(
            allowed_effects=("external.write",),
            granted_permissions=("external.write",),
        ),
    )
    return result.outcome == "compensated" and result.state.get("compensated") is True


def _fidelity_check() -> bool:
    plans = tuple(sha256_digest(f"conformance-plan-{index}") for index in range(6))
    quality = {digest: float(index) for index, digest in enumerate(plans)}
    run = run_successive_halving(
        plans,
        SuccessiveHalvingPolicy(
            "policy.conformance-halving", "metric.quality", "maximize", 1, 9, 3
        ),
        lambda digest, resource: TrialObservation(digest, resource, quality[digest]),
    )
    return len(run.rungs) == 3 and run.finalist_plan_digests == (plans[-1],)


def run_conformance_suite() -> ConformanceResult:
    checks: list[ConformanceCheck] = []
    branch_receipt: RunReceipt | None = None
    operations: tuple[tuple[str, Callable[[], bool]], ...] = (
        ("conformance.structured-lowering", _structured_check),
        ("conformance.topology-search", _topology_check),
        ("conformance.event-time-stream", _stream_check),
        ("conformance.durable-resume", _durable_check),
        ("conformance.saga-compensation", _saga_check),
        ("conformance.multi-fidelity", _fidelity_check),
    )
    try:
        passed, branch_receipt = _branch_run()
        checks.append(ConformanceCheck(
            "conformance.conditional-branch", passed, "one arm ran and one was skipped"
        ))
    except Exception as exc:
        checks.append(ConformanceCheck(
            "conformance.conditional-branch", False, f"{type(exc).__name__}: {exc}"
        ))
    for check_id, operation in operations:
        try:
            passed = operation()
            checks.append(ConformanceCheck(check_id, passed, "mechanism executed"))
        except Exception as exc:
            checks.append(ConformanceCheck(
                check_id, False, f"{type(exc).__name__}: {exc}"
            ))
    if branch_receipt is not None:
        try:
            bundle = export_provenance(branch_receipt)
            openlineage_run_id = bundle.openlineage.get("run", {}).get("runId", "")
            passed = bool(
                bundle.w3c_prov.get("activity")
                and len(bundle.w3c_prov["activity"])
                == 1 + len(branch_receipt.node_receipts)
                and bundle.openlineage.get("eventType") == "COMPLETE"
                and str(UUID(openlineage_run_id)) == openlineage_run_id
                and bundle.slsa_provenance.get("predicateType")
                == "https://slsa.dev/provenance/v1"
            )
            checks.append(ConformanceCheck(
                "conformance.provenance", passed, "W3C PROV, OpenLineage, and SLSA exported"
            ))
        except Exception as exc:
            checks.append(ConformanceCheck(
                "conformance.provenance", False, f"{type(exc).__name__}: {exc}"
            ))
    return ConformanceResult(tuple(checks))


__all__ = [
    "CONFORMANCE_MODEL_VERSION",
    "ConformanceCheck",
    "ConformanceResult",
    "run_conformance_suite",
]
