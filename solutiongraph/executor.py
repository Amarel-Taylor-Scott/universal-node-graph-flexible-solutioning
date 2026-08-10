"""A small, strict reference executor for content-addressed frozen plans.

This module proves the executor boundary; it is not a security sandbox. The
default Python adapter runs in-process and refuses undeclared runtimes, effects,
permissions, bindings, and implementation identities. Production harnesses can
replace the runtime adapters and artifact store while preserving these types.
"""

from __future__ import annotations

import importlib
import inspect
import platform
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Protocol

from solutiongraph.artifacts import (
    ArtifactStore,
    MemoryArtifactStore,
    StoredArtifact,
    digest_value,
    store_value,
)
from solutiongraph.compiler import Compiler
from solutiongraph.evidence import NodeRunReceipt, RunReceipt
from solutiongraph.model import (
    AdmittedSpace,
    Cardinality,
    FrozenPlan,
    Idempotency,
    NodeSpec,
    PlanBinding,
    PlanFallback,
    ProgramGraph,
    Registry,
    ID_RE,
    sha256_digest,
)


EXECUTOR_ID = "solutiongraph.reference-python-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def callable_implementation_digest(function: Callable[..., Any]) -> str:
    """Hash inspected Python source using the NodeSpec reference convention."""
    return sha256_digest(inspect.getsource(function))


class ExecutionError(RuntimeError):
    """Raised when a plan cannot legally start or a caller requests fail-fast."""


class NodeExecutionFailure(RuntimeError):
    """A node-reported stable failure class with explicit retry semantics."""

    def __init__(self, failure_class: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.failure_class = failure_class
        self.retryable = retryable


@dataclass(frozen=True)
class ExecutionPolicy:
    """Executor-local authority and recovery limits, separate from the program."""

    allowed_runtimes: tuple[str, ...] = ("python",)
    granted_permissions: tuple[str, ...] = ()
    allowed_effects: tuple[str, ...] = ()
    max_attempts_per_candidate: int = 1
    verify_implementation_digests: bool = True
    require_task_verifier: bool = True
    allow_in_process_python: bool = True

    def validate(self) -> list[str]:
        problems: list[str] = []
        for label, values in (
            ("allowed_runtimes", self.allowed_runtimes),
            ("granted_permissions", self.granted_permissions),
            ("allowed_effects", self.allowed_effects),
        ):
            if not values and label == "allowed_runtimes":
                problems.append("allowed_runtimes must not be empty")
            if len(values) != len(set(values)):
                problems.append(f"{label} must be unique")
        if self.max_attempts_per_candidate <= 0:
            problems.append("max_attempts_per_candidate must be positive")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_runtimes": list(self.allowed_runtimes),
            "granted_permissions": list(self.granted_permissions),
            "allowed_effects": list(self.allowed_effects),
            "max_attempts_per_candidate": self.max_attempts_per_candidate,
            "verify_implementation_digests": self.verify_implementation_digests,
            "require_task_verifier": self.require_task_verifier,
            "allow_in_process_python": self.allow_in_process_python,
        }


@dataclass(frozen=True)
class VerificationResult:
    """Independent task- or node-level verdict and measured objective values."""

    accepted: bool
    outcome: str
    metrics: Mapping[str, float] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.outcome.strip():
            problems.append("verification outcome must not be empty")
        for name, value in self.metrics.items():
            if not name.strip() or not isinstance(value, (int, float)):
                problems.append("verification metrics must be named numbers")
        return problems


@dataclass(frozen=True)
class VerificationContext:
    plan: FrozenPlan
    program: ProgramGraph
    task_case_id: str
    inputs: Mapping[str, Any]
    outputs: Mapping[str, Any]
    output_artifacts: Mapping[str, StoredArtifact]
    node_receipts: tuple[NodeRunReceipt, ...]
    seed: int | None


class Verifier(Protocol):
    identifier: str
    implementation_digest: str

    def verify(self, context: VerificationContext) -> VerificationResult: ...


@dataclass(frozen=True)
class CallableVerifier:
    """Thin wrapper that keeps verifier identity separate from its callable."""

    identifier: str
    function: Callable[[VerificationContext], VerificationResult]

    @property
    def implementation_digest(self) -> str:
        return callable_implementation_digest(self.function)

    def verify(self, context: VerificationContext) -> VerificationResult:
        result = self.function(context)
        problems = result.validate()
        if problems:
            raise ValueError("invalid verification result: " + "; ".join(problems))
        return result


class RuntimeAdapter(Protocol):
    runtime_id: str
    isolation: str

    def implementation_digest(self, node: NodeSpec) -> str: ...

    def invoke(
        self,
        node: NodeSpec,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
    ) -> Any: ...


@dataclass
class PythonRuntime:
    """Import and call a Python entrypoint in-process.

    This adapter is suitable for conformance tests and trusted local examples.
    It deliberately advertises ``in_process`` isolation so a policy or harness
    can reject it and install a subprocess/container adapter instead.
    """

    runtime_id: str = "python"
    isolation: str = "in_process"
    _cache: dict[str, Callable[..., Any]] = field(default_factory=dict)

    def resolve(self, entrypoint: str) -> Callable[..., Any]:
        if entrypoint in self._cache:
            return self._cache[entrypoint]
        module_name, separator, attribute = entrypoint.partition(":")
        if not separator or not module_name or not attribute:
            raise ExecutionError(
                f"python entrypoint must use module:callable syntax: {entrypoint!r}"
            )
        function = getattr(importlib.import_module(module_name), attribute, None)
        if not callable(function):
            raise ExecutionError(f"python entrypoint is not callable: {entrypoint!r}")
        self._cache[entrypoint] = function
        return function

    def implementation_digest(self, node: NodeSpec) -> str:
        return callable_implementation_digest(self.resolve(node.entrypoint))

    def invoke(
        self,
        node: NodeSpec,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
    ) -> Any:
        arguments = dict(inputs)
        overlap = set(arguments).intersection(parameters)
        if overlap:
            raise ExecutionError(
                "node port and parameter names overlap at runtime: "
                + ", ".join(sorted(overlap))
            )
        arguments.update(parameters)
        return self.resolve(node.entrypoint)(**arguments)


@dataclass
class RuntimeRegistry:
    """Runtime-adapter registry injected by the harness."""

    adapters: Mapping[str, RuntimeAdapter] = field(
        default_factory=lambda: {"python": PythonRuntime()}
    )

    def resolve(self, runtime_id: str) -> RuntimeAdapter:
        try:
            return self.adapters[runtime_id]
        except KeyError as exc:
            raise ExecutionError(f"no runtime adapter is registered for {runtime_id!r}") from exc


@dataclass
class CircuitBreaker:
    """Small candidate-scoped circuit breaker; state is never written into a plan."""

    failure_threshold: int = 3
    _failures: dict[str, int] = field(default_factory=dict)
    _open: set[str] = field(default_factory=set)

    def is_open(self, candidate_id: str) -> bool:
        return candidate_id in self._open

    def record_success(self, candidate_id: str) -> None:
        self._failures.pop(candidate_id, None)
        self._open.discard(candidate_id)

    def record_failure(self, candidate_id: str) -> None:
        if self.failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        failures = self._failures.get(candidate_id, 0) + 1
        self._failures[candidate_id] = failures
        if failures >= self.failure_threshold:
            self._open.add(candidate_id)


@dataclass(frozen=True)
class ExecutionResult:
    outputs: Mapping[str, Any]
    output_artifacts: Mapping[str, StoredArtifact]
    receipt: RunReceipt
    artifacts: tuple[StoredArtifact, ...]
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.receipt.outcome in {"accepted", "completed_unverified"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "outputs": dict(self.outputs),
            "output_artifacts": {
                name: artifact.to_dict()
                for name, artifact in self.output_artifacts.items()
            },
            "receipt": self.receipt.to_dict(),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "error": self.error,
        }


def _binding_to_fallback(binding: PlanBinding) -> PlanFallback:
    return PlanFallback(
        slot_id=binding.slot_id,
        priority=0,
        candidate_id=binding.candidate_id,
        node_id=binding.node_id,
        node_version=binding.node_version,
        implementation_digest=binding.implementation_digest,
        parameters=binding.parameters,
    )


def _candidate_map(plan: FrozenPlan) -> dict[str, tuple[PlanFallback, ...]]:
    primaries = {
        binding.slot_id: (_binding_to_fallback(binding),)
        for binding in plan.bindings
    }
    grouped: dict[str, list[PlanFallback]] = {
        slot_id: list(bindings) for slot_id, bindings in primaries.items()
    }
    for fallback in sorted(plan.fallbacks, key=lambda item: (item.slot_id, item.priority)):
        grouped.setdefault(fallback.slot_id, []).append(fallback)
    return {slot_id: tuple(bindings) for slot_id, bindings in grouped.items()}


def _split_outputs(node: NodeSpec, result: Any) -> dict[str, Any]:
    if not node.outputs:
        if result not in (None, {}):
            raise NodeExecutionFailure(
                "runtime.output-shape",
                f"{node.id} declares no outputs but returned a value",
            )
        return {}
    if len(node.outputs) == 1:
        return {node.outputs[0].name: result}
    if not isinstance(result, Mapping):
        raise NodeExecutionFailure(
            "runtime.output-shape",
            f"{node.id} must return a mapping for multiple output ports",
        )
    expected = {port.name for port in node.outputs}
    actual = set(result)
    if expected != actual:
        raise NodeExecutionFailure(
            "runtime.output-shape",
            f"{node.id} returned ports {sorted(actual)}; expected {sorted(expected)}",
        )
    return dict(result)


def _validate_cardinality(node: NodeSpec, outputs: Mapping[str, Any]) -> None:
    for port in node.outputs:
        value = outputs[port.name]
        if port.cardinality == Cardinality.ONE and value is None:
            raise NodeExecutionFailure(
                "runtime.cardinality", f"required output {node.id}.{port.name} is null"
            )
        if port.cardinality in (Cardinality.MANY, Cardinality.STREAM) and not isinstance(
            value, (list, tuple)
        ):
            raise NodeExecutionFailure(
                "runtime.cardinality",
                f"output {node.id}.{port.name} must be a list or tuple",
            )


class ReferenceExecutor:
    """Execute compiler-validated plans and emit content-addressed receipts."""

    def __init__(
        self,
        *,
        runtimes: RuntimeRegistry | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.runtimes = runtimes or RuntimeRegistry()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    def execute(
        self,
        plan: FrozenPlan,
        program: ProgramGraph,
        registry: Registry,
        space: AdmittedSpace,
        inputs: Mapping[str, Any],
        *,
        task_case_id: str,
        verifier: Verifier | None,
        policy: ExecutionPolicy,
        artifact_store: ArtifactStore | None = None,
        seed: int | None = None,
        belief_revision: str = "",
        run_id: str = "",
    ) -> ExecutionResult:
        """Execute one frozen plan after reconstructing and comparing it exactly."""
        policy_problems = policy.validate()
        if policy_problems:
            raise ExecutionError("invalid execution policy: " + "; ".join(policy_problems))
        if policy.require_task_verifier and verifier is None:
            raise ExecutionError("execution policy requires an independent task verifier")
        if verifier is not None:
            if not ID_RE.fullmatch(verifier.identifier):
                raise ExecutionError("verifier identifier must be a namespaced identifier")
            if not getattr(verifier, "implementation_digest", ""):
                raise ExecutionError("verifier must expose an implementation digest")
        self._validate_plan(plan, program, registry, space)
        self._validate_inputs(program, inputs)
        self._validate_authority(plan, registry, policy)

        store = artifact_store or MemoryArtifactStore()
        started_at = _now()
        started_clock = perf_counter()
        node_receipts: list[NodeRunReceipt] = []
        artifacts: dict[str, StoredArtifact] = {}
        slot_outputs: dict[tuple[str, str], Any] = {}
        actual_assignments: dict[str, str] = {}
        candidates_by_slot = _candidate_map(plan)
        node_map = registry.node_map()
        graph_inputs = {
            (item.target_slot, item.target_port): inputs[item.name]
            for item in program.inputs
        }
        edges_by_target: dict[str, list[Any]] = {}
        for edge in plan.edges:
            edges_by_target.setdefault(edge.target_slot, []).append(edge)

        failure_class = ""
        error_message = ""
        fallback_activations = 0
        retry_count = 0

        for slot_id in plan.topological_order:
            candidate_inputs = self._slot_inputs(
                slot_id,
                program,
                graph_inputs,
                edges_by_target,
                slot_outputs,
            )
            input_digest = digest_value(candidate_inputs)
            completed = False
            for candidate_index, binding in enumerate(candidates_by_slot[slot_id]):
                if candidate_index:
                    fallback_activations += 1
                node = node_map[(binding.node_id, binding.node_version)]
                if self.circuit_breaker.is_open(binding.candidate_id):
                    timestamp = _now()
                    node_receipts.append(NodeRunReceipt(
                        slot_id=slot_id,
                        candidate_id=binding.candidate_id,
                        outcome="blocked",
                        started_at=timestamp,
                        completed_at=timestamp,
                        failure_class="runtime.circuit-open",
                        attempt=1,
                        node_id=node.id,
                        implementation_digest=node.implementation_digest,
                        runtime=node.runtime,
                        input_digest=input_digest,
                    ))
                    continue

                for attempt in range(1, policy.max_attempts_per_candidate + 1):
                    attempt_started = _now()
                    attempt_clock = perf_counter()
                    try:
                        values, produced = self._invoke_candidate(
                            binding,
                            node,
                            candidate_inputs,
                            store,
                            policy,
                        )
                        elapsed_ms = (perf_counter() - attempt_clock) * 1000
                        for artifact in produced.values():
                            artifacts.setdefault(artifact.digest, artifact)
                        node_receipts.append(NodeRunReceipt(
                            slot_id=slot_id,
                            candidate_id=binding.candidate_id,
                            outcome="succeeded",
                            started_at=attempt_started,
                            completed_at=_now(),
                            metrics={"latency_ms": elapsed_ms},
                            artifact_digests=tuple(
                                produced[name].digest for name in sorted(produced)
                            ),
                            attempt=attempt,
                            node_id=node.id,
                            implementation_digest=node.implementation_digest,
                            runtime=node.runtime,
                            input_digest=input_digest,
                        ))
                        for name, value in values.items():
                            slot_outputs[(slot_id, name)] = value
                        actual_assignments[slot_id] = binding.candidate_id
                        self.circuit_breaker.record_success(binding.candidate_id)
                        failure_class = ""
                        error_message = ""
                        completed = True
                        break
                    except NodeExecutionFailure as exc:
                        elapsed_ms = (perf_counter() - attempt_clock) * 1000
                        node_receipts.append(NodeRunReceipt(
                            slot_id=slot_id,
                            candidate_id=binding.candidate_id,
                            outcome="failed",
                            started_at=attempt_started,
                            completed_at=_now(),
                            metrics={"latency_ms": elapsed_ms},
                            failure_class=exc.failure_class,
                            attempt=attempt,
                            node_id=node.id,
                            implementation_digest=node.implementation_digest,
                            runtime=node.runtime,
                            input_digest=input_digest,
                        ))
                        self.circuit_breaker.record_failure(binding.candidate_id)
                        may_retry = (
                            exc.retryable
                            and node.idempotency != Idempotency.NON_IDEMPOTENT
                            and attempt < policy.max_attempts_per_candidate
                        )
                        if may_retry:
                            retry_count += 1
                            continue
                        failure_class = exc.failure_class
                        error_message = str(exc)
                        break
                    except Exception as exc:  # entrypoint boundary: preserve taxonomy
                        elapsed_ms = (perf_counter() - attempt_clock) * 1000
                        failure_class = "runtime.exception"
                        error_message = f"{type(exc).__name__}: {exc}"
                        node_receipts.append(NodeRunReceipt(
                            slot_id=slot_id,
                            candidate_id=binding.candidate_id,
                            outcome="failed",
                            started_at=attempt_started,
                            completed_at=_now(),
                            metrics={"latency_ms": elapsed_ms},
                            failure_class=failure_class,
                            attempt=attempt,
                            node_id=node.id,
                            implementation_digest=node.implementation_digest,
                            runtime=node.runtime,
                            input_digest=input_digest,
                        ))
                        self.circuit_breaker.record_failure(binding.candidate_id)
                        break
                if completed:
                    break
            if not completed:
                break

        outputs: dict[str, Any] = {}
        output_artifacts: dict[str, StoredArtifact] = {}
        verification_details: Mapping[str, Any] = {}
        verifier_id = verifier.identifier if verifier else ""
        verifier_digest = verifier.implementation_digest if verifier else ""
        accepted: bool | None = False if failure_class else None
        outcome = "failed" if failure_class else "completed_unverified"
        verification_metrics: Mapping[str, float] = {}

        if not failure_class:
            for item in program.outputs:
                value = slot_outputs[(item.source_slot, item.source_port)]
                outputs[item.name] = value
                artifact = store_value(store, value, media_type=item.value_type.media_type)
                artifacts.setdefault(artifact.digest, artifact)
                output_artifacts[item.name] = artifact
            if verifier is not None:
                try:
                    verdict = verifier.verify(VerificationContext(
                        plan=plan,
                        program=program,
                        task_case_id=task_case_id,
                        inputs=dict(inputs),
                        outputs=outputs,
                        output_artifacts=output_artifacts,
                        node_receipts=tuple(node_receipts),
                        seed=seed,
                    ))
                    accepted = verdict.accepted
                    outcome = "accepted" if verdict.accepted else "rejected"
                    failure_class = "" if verdict.accepted else "verification.rejected"
                    verification_details = verdict.details
                    verification_metrics = verdict.metrics
                except Exception as exc:
                    accepted = False
                    outcome = "failed"
                    failure_class = "verification.error"
                    error_message = f"{type(exc).__name__}: {exc}"

        completed_at = _now()
        latency_ms = (perf_counter() - started_clock) * 1000
        metrics = {
            "latency_ms": latency_ms,
            "node_attempts": float(len(node_receipts)),
            "fallback_activations": float(fallback_activations),
            "retries": float(retry_count),
            **{name: float(value) for name, value in verification_metrics.items()},
        }
        if not run_id:
            receipt_key = {
                "plan": plan.digest,
                "case": task_case_id,
                "seed": seed,
                "started_at": started_at,
            }
            run_id = f"run.{program.id}.{sha256_digest(receipt_key)[7:23]}"
        environment_digest = sha256_digest({
            "executor": EXECUTOR_ID,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "runtimes": sorted(self.runtimes.adapters),
        })
        receipt = RunReceipt(
            id=run_id,
            plan_digest=plan.digest,
            program_digest=program.digest,
            task_case_id=task_case_id,
            outcome=outcome,
            accepted=accepted,
            verifier=verifier_id,
            assignments=tuple(
                (slot_id, actual_assignments.get(slot_id, candidates_by_slot[slot_id][0].candidate_id))
                for slot_id in plan.topological_order
            ),
            verifier_digest=verifier_digest,
            metrics=metrics,
            node_receipts=tuple(node_receipts),
            seed=seed,
            started_at=started_at,
            completed_at=completed_at,
            failure_class=failure_class,
            executor=EXECUTOR_ID,
            environment_digest=environment_digest,
            input_digest=digest_value(inputs),
            belief_revision=belief_revision,
            admitted_space_digest=space.digest,
            output_artifacts=tuple(
                (name, output_artifacts[name].digest) for name in sorted(output_artifacts)
            ),
            verification_details=verification_details,
        )
        problems = receipt.validate()
        if problems:
            raise ExecutionError("executor produced an invalid receipt: " + "; ".join(problems))
        return ExecutionResult(
            outputs=outputs,
            output_artifacts=output_artifacts,
            receipt=receipt,
            artifacts=tuple(artifacts[digest] for digest in sorted(artifacts)),
            error=error_message,
        )

    @staticmethod
    def _validate_plan(
        plan: FrozenPlan,
        program: ProgramGraph,
        registry: Registry,
        space: AdmittedSpace,
    ) -> None:
        if space.digest != plan.admitted_space_digest:
            raise ExecutionError("frozen plan was produced from another admitted space")
        selection = {binding.slot_id: binding.candidate_id for binding in plan.bindings}
        fallbacks: dict[str, list[PlanFallback]] = {}
        for fallback in plan.fallbacks:
            fallbacks.setdefault(fallback.slot_id, []).append(fallback)
        fallback_ids = {
            slot_id: tuple(
                item.candidate_id for item in sorted(items, key=lambda item: item.priority)
            )
            for slot_id, items in fallbacks.items()
        }
        expected = Compiler().compile(
            program,
            registry,
            space,
            selection,
            fallbacks=fallback_ids,
        )
        if expected != plan:
            raise ExecutionError(
                "frozen plan does not exactly match the supplied program, registry, "
                "admitted space, bindings, or fallbacks"
            )

    @staticmethod
    def _validate_inputs(program: ProgramGraph, inputs: Mapping[str, Any]) -> None:
        expected = {item.name for item in program.inputs}
        actual = set(inputs)
        if expected != actual:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if extra:
                details.append("unknown: " + ", ".join(extra))
            raise ExecutionError("graph input mismatch (" + "; ".join(details) + ")")
        digest_value(inputs)

    def _validate_authority(
        self,
        plan: FrozenPlan,
        registry: Registry,
        policy: ExecutionPolicy,
    ) -> None:
        node_map = registry.node_map()
        bindings = [*plan.bindings, *plan.fallbacks]
        for binding in bindings:
            node = node_map[(binding.node_id, binding.node_version)]
            if node.runtime not in policy.allowed_runtimes:
                raise ExecutionError(
                    f"runtime {node.runtime!r} is not allowed for {binding.candidate_id}"
                )
            adapter = self.runtimes.resolve(node.runtime)
            if (
                node.runtime == "python"
                and adapter.isolation == "in_process"
                and not policy.allow_in_process_python
            ):
                raise ExecutionError("policy forbids the in-process Python runtime")
            missing_permissions = sorted(
                set(node.permissions) - set(policy.granted_permissions)
            )
            if missing_permissions:
                raise ExecutionError(
                    f"executor policy does not grant {binding.candidate_id}: "
                    + ", ".join(missing_permissions)
                )
            disallowed_effects = sorted(set(node.effects) - set(policy.allowed_effects))
            if disallowed_effects:
                raise ExecutionError(
                    f"executor policy does not allow {binding.candidate_id}: "
                    + ", ".join(disallowed_effects)
                )

    @staticmethod
    def _slot_inputs(
        slot_id: str,
        program: ProgramGraph,
        graph_inputs: Mapping[tuple[str, str], Any],
        edges_by_target: Mapping[str, list[Any]],
        slot_outputs: Mapping[tuple[str, str], Any],
    ) -> dict[str, Any]:
        slot = next(item for item in program.slots if item.id == slot_id)
        values: dict[str, list[Any]] = {}
        for port in slot.inputs:
            key = (slot_id, port.name)
            if key in graph_inputs:
                values.setdefault(port.name, []).append(graph_inputs[key])
        for edge in edges_by_target.get(slot_id, []):
            values.setdefault(edge.target_port, []).append(
                slot_outputs[(edge.source_slot, edge.source_port)]
            )
        resolved: dict[str, Any] = {}
        for port in slot.inputs:
            produced = values.get(port.name, [])
            if port.cardinality in (Cardinality.MANY, Cardinality.STREAM):
                resolved[port.name] = produced
            elif produced:
                resolved[port.name] = produced[0]
        return resolved

    def _invoke_candidate(
        self,
        binding: PlanBinding | PlanFallback,
        node: NodeSpec,
        inputs: Mapping[str, Any],
        store: ArtifactStore,
        policy: ExecutionPolicy,
    ) -> tuple[dict[str, Any], dict[str, StoredArtifact]]:
        adapter = self.runtimes.resolve(node.runtime)
        if policy.verify_implementation_digests:
            actual_digest = adapter.implementation_digest(node)
            if actual_digest != binding.implementation_digest:
                raise NodeExecutionFailure(
                    "runtime.implementation-digest-mismatch",
                    f"entrypoint digest for {node.id} does not match the frozen plan",
                )
        result = adapter.invoke(node, inputs, dict(binding.parameters))
        outputs = _split_outputs(node, result)
        _validate_cardinality(node, outputs)
        produced = {
            port.name: store_value(
                store,
                outputs[port.name],
                media_type=port.value_type.media_type,
            )
            for port in node.outputs
        }
        return outputs, produced


__all__ = [
    "CallableVerifier",
    "CircuitBreaker",
    "EXECUTOR_ID",
    "ExecutionError",
    "ExecutionPolicy",
    "ExecutionResult",
    "NodeExecutionFailure",
    "PythonRuntime",
    "ReferenceExecutor",
    "RuntimeAdapter",
    "RuntimeRegistry",
    "VerificationContext",
    "VerificationResult",
    "Verifier",
    "callable_implementation_digest",
]
