"""Reference saga execution with explicit effect nodes and compensation receipts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from solutiongraph.artifacts import digest_value
from solutiongraph.executor import ExecutionPolicy, NodeExecutionFailure, RuntimeRegistry
from solutiongraph.model import DIGEST_RE, ID_RE, NodeSpec, canonical_json, sha256_digest

SAGA_MODEL_VERSION = "0.1"


@dataclass(frozen=True)
class SagaStep:
    id: str
    action: NodeSpec
    compensation: NodeSpec | None
    idempotency_key: str
    action_parameters: Mapping[str, Any] = field(default_factory=dict)
    compensation_parameters: Mapping[str, Any] = field(default_factory=dict)

    def validate(self, path: str = "step") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be namespaced")
        problems.extend(self.action.validate(f"{path}.action"))
        if self.compensation is not None:
            problems.extend(self.compensation.validate(f"{path}.compensation"))
        for label, node in (
            ("action", self.action),
            ("compensation", self.compensation),
        ):
            if node is None:
                continue
            if [port.name for port in node.inputs] != ["state"]:
                problems.append(f"{path}.{label} must declare exactly one state input")
            if [port.name for port in node.outputs] != ["state"]:
                problems.append(f"{path}.{label} must declare exactly one state output")
        if self.action.effects and not self.idempotency_key:
            problems.append(f"{path} effectful actions require an idempotency key")
        expected_keys = (
            ("action", self.action, self.action_parameters, self.idempotency_key),
            (
                "compensation",
                self.compensation,
                self.compensation_parameters,
                f"{self.idempotency_key}:compensation",
            ),
        )
        for label, node, parameters, expected_key in expected_keys:
            if (
                node is not None
                and "idempotency_key" in parameters
                and parameters["idempotency_key"] != expected_key
            ):
                problems.append(
                    f"{path}.{label}_parameters cannot override the saga idempotency key"
                )
        if set(self.action_parameters) - {item.name for item in self.action.parameters}:
            problems.append(f"{path}.action_parameters contain unknown names")
        if self.compensation is None and self.compensation_parameters:
            problems.append(f"{path} has compensation parameters without a node")
        if self.compensation is not None and (
            set(self.compensation_parameters)
            - {item.name for item in self.compensation.parameters}
        ):
            problems.append(f"{path}.compensation_parameters contain unknown names")
        return problems


@dataclass(frozen=True)
class SagaAttemptReceipt:
    step_id: str
    phase: str
    node_id: str
    implementation_digest: str
    outcome: str
    input_digest: str
    idempotency_key: str
    output_digest: str = ""
    failure_class: str = ""
    message: str = ""

    def validate(self, path: str = "attempt") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.step_id) or not ID_RE.fullmatch(self.node_id):
            problems.append(f"{path} step_id and node_id must be namespaced")
        if self.phase not in ("action", "compensation"):
            problems.append(f"{path}.phase must be action or compensation")
        if self.outcome not in ("succeeded", "failed"):
            problems.append(f"{path}.outcome must be succeeded or failed")
        if not DIGEST_RE.fullmatch(self.implementation_digest):
            problems.append(f"{path}.implementation_digest must be sha256")
        if not DIGEST_RE.fullmatch(self.input_digest):
            problems.append(f"{path}.input_digest must be sha256")
        if not self.idempotency_key:
            problems.append(f"{path}.idempotency_key must not be empty")
        if self.output_digest and not DIGEST_RE.fullmatch(self.output_digest):
            problems.append(f"{path}.output_digest must be empty or sha256")
        if self.failure_class and not ID_RE.fullmatch(self.failure_class):
            problems.append(f"{path}.failure_class must be empty or namespaced")
        if self.outcome == "succeeded" and not self.output_digest:
            problems.append(f"{path} succeeded attempt requires output_digest")
        if self.outcome == "failed" and not self.failure_class:
            problems.append(f"{path} failed attempt requires failure_class")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "phase": self.phase,
            "node_id": self.node_id,
            "implementation_digest": self.implementation_digest,
            "outcome": self.outcome,
            "input_digest": self.input_digest,
            "idempotency_key": self.idempotency_key,
            "output_digest": self.output_digest,
            "failure_class": self.failure_class,
            "message": self.message,
        }


@dataclass(frozen=True)
class SagaResult:
    id: str
    outcome: str
    state: Any
    attempts: tuple[SagaAttemptReceipt, ...]
    committed_steps: tuple[str, ...]
    compensated_steps: tuple[str, ...]
    uncompensated_steps: tuple[str, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("saga result id must be namespaced")
        if self.outcome not in ("committed", "compensated", "compensation_failed"):
            problems.append("saga result outcome is not recognized")
        try:
            canonical_json(self.state)
        except (TypeError, ValueError):
            problems.append("saga result state must be JSON-compatible")
        for index, attempt in enumerate(self.attempts):
            problems.extend(attempt.validate(f"attempts[{index}]"))
        for label, values in (
            ("committed_steps", self.committed_steps),
            ("compensated_steps", self.compensated_steps),
            ("uncompensated_steps", self.uncompensated_steps),
        ):
            if len(values) != len(set(values)):
                problems.append(f"saga result {label} must be unique")
            if any(not ID_RE.fullmatch(value) for value in values):
                problems.append(f"saga result {label} must contain identifiers")
        if not set(self.compensated_steps).issubset(self.committed_steps):
            problems.append("compensated steps must be committed steps")
        if not set(self.uncompensated_steps).issubset(self.committed_steps):
            problems.append("uncompensated steps must be committed steps")
        if set(self.compensated_steps) & set(self.uncompensated_steps):
            problems.append("a step cannot be both compensated and uncompensated")
        if self.outcome == "committed" and (
            self.compensated_steps or self.uncompensated_steps
        ):
            problems.append("committed saga cannot contain compensation results")
        if self.outcome == "compensation_failed" and not self.uncompensated_steps:
            problems.append("compensation_failed requires uncompensated steps")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "saga_model_version": SAGA_MODEL_VERSION,
            "id": self.id,
            "outcome": self.outcome,
            "state": self.state,
            "attempts": [item.to_dict() for item in self.attempts],
            "committed_steps": list(self.committed_steps),
            "compensated_steps": list(self.compensated_steps),
            "uncompensated_steps": list(self.uncompensated_steps),
        }


class SagaRunner:
    """Run an ordered effect transaction and compensate completed actions on failure."""

    def __init__(self, runtimes: RuntimeRegistry | None = None) -> None:
        self.runtimes = runtimes or RuntimeRegistry()

    def _authorize(self, node: NodeSpec, policy: ExecutionPolicy) -> None:
        if node.runtime not in policy.allowed_runtimes:
            raise ValueError(f"runtime {node.runtime!r} is not allowed")
        adapter = self.runtimes.resolve(node.runtime)
        if (
            node.runtime == "python"
            and adapter.isolation == "in_process"
            and not policy.allow_in_process_python
        ):
            raise ValueError("policy forbids the in-process Python runtime")
        missing_permissions = sorted(set(node.permissions) - set(policy.granted_permissions))
        disallowed_effects = sorted(set(node.effects) - set(policy.allowed_effects))
        if missing_permissions:
            raise ValueError("missing permissions: " + ", ".join(missing_permissions))
        if disallowed_effects:
            raise ValueError("disallowed effects: " + ", ".join(disallowed_effects))
        if policy.verify_implementation_digests:
            actual = adapter.implementation_digest(node)
            if actual != node.implementation_digest:
                raise ValueError(f"implementation digest mismatch for {node.id}")

    def _invoke(
        self,
        step_id: str,
        phase: str,
        node: NodeSpec,
        state: Any,
        idempotency_key: str,
        parameters: Mapping[str, Any],
        policy: ExecutionPolicy,
    ) -> tuple[Any, SagaAttemptReceipt]:
        input_digest = digest_value(state)
        try:
            self._authorize(node, policy)
            invocation_parameters = dict(parameters)
            if any(item.name == "idempotency_key" for item in node.parameters):
                invocation_parameters["idempotency_key"] = idempotency_key
            result = self.runtimes.resolve(node.runtime).invoke(
                node, {"state": state}, invocation_parameters
            )
            output_digest = digest_value(result)
            return result, SagaAttemptReceipt(
                step_id,
                phase,
                node.id,
                node.implementation_digest,
                "succeeded",
                input_digest,
                idempotency_key,
                output_digest,
            )
        except NodeExecutionFailure as exc:
            return state, SagaAttemptReceipt(
                step_id,
                phase,
                node.id,
                node.implementation_digest,
                "failed",
                input_digest,
                idempotency_key,
                failure_class=exc.failure_class,
                message=str(exc),
            )
        except Exception as exc:
            return state, SagaAttemptReceipt(
                step_id,
                phase,
                node.id,
                node.implementation_digest,
                "failed",
                input_digest,
                idempotency_key,
                failure_class="runtime.exception",
                message=f"{type(exc).__name__}: {exc}",
            )

    def run(
        self,
        saga_id: str,
        steps: tuple[SagaStep, ...],
        initial_state: Any,
        *,
        policy: ExecutionPolicy,
        require_compensation: bool = True,
    ) -> SagaResult:
        problems = policy.validate()
        if not ID_RE.fullmatch(saga_id):
            problems.append("saga id must be namespaced")
        if not steps:
            problems.append("saga steps must not be empty")
        ids = [step.id for step in steps]
        if len(ids) != len(set(ids)):
            problems.append("saga step ids must be unique")
        effect_keys = [
            step.idempotency_key for step in steps if step.action.effects
        ]
        if len(effect_keys) != len(set(effect_keys)):
            problems.append("effectful saga steps must use unique idempotency keys")
        for index, step in enumerate(steps):
            problems.extend(step.validate(f"steps[{index}]"))
        if problems:
            raise ValueError("invalid saga: " + "; ".join(problems))
        try:
            canonical_json(initial_state)
        except (TypeError, ValueError) as exc:
            raise ValueError("saga initial_state must be JSON-compatible") from exc

        state = initial_state
        attempts: list[SagaAttemptReceipt] = []
        completed: list[SagaStep] = []
        failed = False
        for step in steps:
            state, receipt = self._invoke(
                step.id,
                "action",
                step.action,
                state,
                step.idempotency_key,
                step.action_parameters,
                policy,
            )
            attempts.append(receipt)
            if receipt.outcome != "succeeded":
                failed = True
                break
            completed.append(step)
        if not failed:
            result = SagaResult(
                saga_id,
                "committed",
                state,
                tuple(attempts),
                tuple(step.id for step in completed),
                (),
                (),
            )
            result_problems = result.validate()
            if result_problems:
                raise RuntimeError(
                    "saga runner produced an invalid result: "
                    + "; ".join(result_problems)
                )
            return result

        compensated: list[str] = []
        uncompensated: list[str] = []
        compensation_failed = False
        for step in reversed(completed):
            if step.compensation is None:
                uncompensated.append(step.id)
                compensation_failed = compensation_failed or require_compensation
                continue
            state, receipt = self._invoke(
                step.id,
                "compensation",
                step.compensation,
                state,
                f"{step.idempotency_key}:compensation",
                step.compensation_parameters,
                policy,
            )
            attempts.append(receipt)
            if receipt.outcome == "succeeded":
                compensated.append(step.id)
            else:
                uncompensated.append(step.id)
                compensation_failed = True
        result = SagaResult(
            saga_id,
            "compensation_failed" if compensation_failed else "compensated",
            state,
            tuple(attempts),
            tuple(step.id for step in completed),
            tuple(compensated),
            tuple(uncompensated),
        )
        result_problems = result.validate()
        if result_problems:
            raise RuntimeError(
                "saga runner produced an invalid result: "
                + "; ".join(result_problems)
            )
        return result


__all__ = [
    "SAGA_MODEL_VERSION",
    "SagaAttemptReceipt",
    "SagaResult",
    "SagaRunner",
    "SagaStep",
]
