"""Crash-resumable local checkpoints for the reference executor.

This is a durable local protocol, not a distributed scheduler or hostile-code
boundary.  A checkpoint is accepted only when plan, program, registry,
admission, inputs, environment, case, and seed identities match exactly.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from solutiongraph.artifacts import ArtifactStore, StoredArtifact, digest_bytes
from solutiongraph.evidence import NodeRunReceipt
from solutiongraph.model import DIGEST_RE, ID_RE, PORT_RE, sha256_digest

CHECKPOINT_MODEL_VERSION = "0.1"
CHECKPOINT_STATUSES = ("running", "failed", "completed")


def _fsync_directory(path: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class CheckpointOutput:
    name: str
    artifact: StoredArtifact
    value_kind: str

    def validate(self, path: str) -> list[str]:
        problems = self.artifact.validate()
        if not PORT_RE.fullmatch(self.name):
            problems.append(f"{path}.name must be a port name")
        if self.value_kind not in ("json", "text", "bytes"):
            problems.append(f"{path}.value_kind must be json, text, or bytes")
        return problems

    def load(self, store: ArtifactStore) -> Any:
        payload = store.get_bytes(self.artifact.digest)
        if digest_bytes(payload) != self.artifact.digest:
            raise ValueError("checkpoint artifact content does not match its digest")
        if len(payload) != self.artifact.size_bytes:
            raise ValueError("checkpoint artifact content does not match its size")
        if self.value_kind == "bytes":
            return payload
        text = payload.decode("utf-8")
        return json.loads(text) if self.value_kind == "json" else text

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "artifact": self.artifact.to_dict(),
            "value_kind": self.value_kind,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CheckpointOutput:
        if set(payload) != {"name", "artifact", "value_kind"}:
            raise ValueError("checkpoint output has missing or unknown fields")
        artifact = payload["artifact"]
        if not isinstance(artifact, Mapping):
            raise ValueError("checkpoint output artifact must be an object")
        if set(artifact) != {"digest", "media_type", "size_bytes", "uri"}:
            raise ValueError("checkpoint artifact has missing or unknown fields")
        if not isinstance(payload["name"], str) or not isinstance(
            payload["value_kind"], str
        ):
            raise ValueError("checkpoint output names and kinds must be strings")
        if any(
            not isinstance(artifact[field], str)
            for field in ("digest", "media_type", "uri")
        ):
            raise ValueError("checkpoint artifact text fields must be strings")
        if isinstance(artifact["size_bytes"], bool) or not isinstance(
            artifact["size_bytes"], int
        ):
            raise ValueError("checkpoint artifact size_bytes must be an integer")
        result = cls(
            name=payload["name"],
            artifact=StoredArtifact(
                digest=artifact["digest"],
                media_type=artifact["media_type"],
                size_bytes=artifact["size_bytes"],
                uri=artifact["uri"],
            ),
            value_kind=payload["value_kind"],
        )
        problems = result.validate("output")
        if problems:
            raise ValueError("invalid checkpoint output: " + "; ".join(problems))
        return result


@dataclass(frozen=True)
class SlotCheckpoint:
    slot_id: str
    candidate_id: str
    outputs: tuple[CheckpointOutput, ...]
    receipt: NodeRunReceipt

    def validate(self, path: str) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.slot_id) or not ID_RE.fullmatch(self.candidate_id):
            problems.append(f"{path} slot and candidate ids are invalid")
        if self.receipt.slot_id != self.slot_id:
            problems.append(f"{path} receipt slot does not match")
        if self.receipt.candidate_id != self.candidate_id:
            problems.append(f"{path} receipt candidate does not match")
        if self.receipt.outcome not in ("succeeded", "skipped"):
            problems.append(f"{path} may preserve only succeeded or skipped slots")
        if self.receipt.outcome == "skipped" and self.outputs:
            problems.append(f"{path} skipped slots cannot preserve outputs")
        names = [item.name for item in self.outputs]
        if len(names) != len(set(names)):
            problems.append(f"{path}.outputs must have unique names")
        for index, output in enumerate(self.outputs):
            problems.extend(output.validate(f"{path}.outputs[{index}]"))
        output_digests = tuple(sorted(item.artifact.digest for item in self.outputs))
        if tuple(sorted(self.receipt.artifact_digests)) != output_digests:
            problems.append(f"{path} receipt artifact digests do not match outputs")
        problems.extend(self.receipt.validate(f"{path}.receipt"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "candidate_id": self.candidate_id,
            "outputs": [item.to_dict() for item in self.outputs],
            "receipt": {
                "slot_id": self.receipt.slot_id,
                "candidate_id": self.receipt.candidate_id,
                "outcome": self.receipt.outcome,
                "started_at": self.receipt.started_at,
                "completed_at": self.receipt.completed_at,
                "metrics": dict(self.receipt.metrics),
                "failure_class": self.receipt.failure_class,
                "artifact_digests": list(self.receipt.artifact_digests),
                "attempt": self.receipt.attempt,
                "node_id": self.receipt.node_id,
                "implementation_digest": self.receipt.implementation_digest,
                "runtime": self.receipt.runtime,
                "runtime_adapter": self.receipt.runtime_adapter,
                "isolation": self.receipt.isolation,
                "input_digest": self.receipt.input_digest,
            },
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SlotCheckpoint:
        if set(payload) != {"slot_id", "candidate_id", "outputs", "receipt"}:
            raise ValueError("slot checkpoint has missing or unknown fields")
        if not isinstance(payload["outputs"], list) or not isinstance(
            payload["receipt"], Mapping
        ):
            raise ValueError("slot checkpoint outputs or receipt is malformed")
        if not isinstance(payload["slot_id"], str) or not isinstance(
            payload["candidate_id"], str
        ):
            raise ValueError("slot checkpoint ids must be strings")
        result = cls(
            slot_id=payload["slot_id"],
            candidate_id=payload["candidate_id"],
            outputs=tuple(
                CheckpointOutput.from_dict(item) for item in payload["outputs"]
            ),
            receipt=NodeRunReceipt.from_dict(payload["receipt"]),
        )
        problems = result.validate("slot")
        if problems:
            raise ValueError("invalid slot checkpoint: " + "; ".join(problems))
        return result


@dataclass(frozen=True)
class ExecutionCheckpoint:
    id: str
    plan_digest: str
    program_digest: str
    registry_digest: str
    admitted_space_digest: str
    input_digest: str
    environment_digest: str
    task_case_id: str
    seed: int | None
    status: str
    completed_slots: tuple[SlotCheckpoint, ...]
    failure_class: str = ""

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.task_case_id):
            problems.append("checkpoint and task case ids must be namespaced")
        for label, digest in (
            ("plan_digest", self.plan_digest),
            ("program_digest", self.program_digest),
            ("registry_digest", self.registry_digest),
            ("admitted_space_digest", self.admitted_space_digest),
            ("input_digest", self.input_digest),
            ("environment_digest", self.environment_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"checkpoint {label} must be a sha256 digest")
        if self.status not in CHECKPOINT_STATUSES:
            problems.append("checkpoint status is not recognized")
        if self.seed is not None and (
            isinstance(self.seed, bool) or not isinstance(self.seed, int)
        ):
            problems.append("checkpoint seed must be an integer or null")
        if self.failure_class and not ID_RE.fullmatch(self.failure_class):
            problems.append("checkpoint failure_class must be empty or namespaced")
        if self.status == "failed" and not self.failure_class:
            problems.append("failed checkpoints require a failure_class")
        if self.status != "failed" and self.failure_class:
            problems.append("only failed checkpoints may carry a failure_class")
        slot_ids = [item.slot_id for item in self.completed_slots]
        if len(slot_ids) != len(set(slot_ids)):
            problems.append("checkpoint completed slots must be unique")
        for index, item in enumerate(self.completed_slots):
            problems.extend(item.validate(f"completed_slots[{index}]"))
        return problems

    def assert_matches(
        self,
        *,
        plan_digest: str,
        program_digest: str,
        registry_digest: str,
        admitted_space_digest: str,
        input_digest: str,
        environment_digest: str,
        task_case_id: str,
        seed: int | None,
    ) -> None:
        expected = {
            "plan_digest": plan_digest,
            "program_digest": program_digest,
            "registry_digest": registry_digest,
            "admitted_space_digest": admitted_space_digest,
            "input_digest": input_digest,
            "environment_digest": environment_digest,
            "task_case_id": task_case_id,
            "seed": seed,
        }
        actual = {name: getattr(self, name) for name in expected}
        mismatches = sorted(name for name in expected if actual[name] != expected[name])
        if mismatches:
            raise ValueError(
                "checkpoint identity mismatch: " + ", ".join(mismatches)
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_model_version": CHECKPOINT_MODEL_VERSION,
            "id": self.id,
            "plan_digest": self.plan_digest,
            "program_digest": self.program_digest,
            "registry_digest": self.registry_digest,
            "admitted_space_digest": self.admitted_space_digest,
            "input_digest": self.input_digest,
            "environment_digest": self.environment_digest,
            "task_case_id": self.task_case_id,
            "seed": self.seed,
            "status": self.status,
            "completed_slots": [item.to_dict() for item in self.completed_slots],
            "failure_class": self.failure_class,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ExecutionCheckpoint:
        required = {
            "checkpoint_model_version", "id", "plan_digest", "program_digest",
            "registry_digest", "admitted_space_digest", "input_digest",
            "environment_digest", "task_case_id", "seed", "status",
            "completed_slots", "failure_class",
        }
        if set(payload) != required:
            raise ValueError("execution checkpoint has missing or unknown fields")
        if payload["checkpoint_model_version"] != CHECKPOINT_MODEL_VERSION:
            raise ValueError("unsupported checkpoint model version")
        if not isinstance(payload["completed_slots"], list):
            raise ValueError("checkpoint completed_slots must be an array")
        if payload["seed"] is not None and (
            isinstance(payload["seed"], bool) or not isinstance(payload["seed"], int)
        ):
            raise ValueError("checkpoint seed must be an integer or null")
        text_fields = required - {
            "checkpoint_model_version", "seed", "completed_slots"
        }
        if any(not isinstance(payload[field], str) for field in text_fields):
            raise ValueError("checkpoint identity and status fields must be strings")
        result = cls(
            id=payload["id"],
            plan_digest=payload["plan_digest"],
            program_digest=payload["program_digest"],
            registry_digest=payload["registry_digest"],
            admitted_space_digest=payload["admitted_space_digest"],
            input_digest=payload["input_digest"],
            environment_digest=payload["environment_digest"],
            task_case_id=payload["task_case_id"],
            seed=payload["seed"],
            status=payload["status"],
            completed_slots=tuple(
                SlotCheckpoint.from_dict(item) for item in payload["completed_slots"]
            ),
            failure_class=payload["failure_class"],
        )
        problems = result.validate()
        if problems:
            raise ValueError("invalid execution checkpoint: " + "; ".join(problems))
        return result


class CheckpointStore(Protocol):
    def load(self, checkpoint_id: str) -> ExecutionCheckpoint | None: ...

    def save(self, checkpoint: ExecutionCheckpoint) -> None: ...

    def clear(self, checkpoint_id: str) -> None: ...


class MemoryCheckpointStore:
    def __init__(self) -> None:
        self._checkpoints: dict[str, ExecutionCheckpoint] = {}

    def load(self, checkpoint_id: str) -> ExecutionCheckpoint | None:
        return self._checkpoints.get(checkpoint_id)

    def save(self, checkpoint: ExecutionCheckpoint) -> None:
        problems = checkpoint.validate()
        if problems:
            raise ValueError("invalid execution checkpoint: " + "; ".join(problems))
        self._checkpoints[checkpoint.id] = checkpoint

    def clear(self, checkpoint_id: str) -> None:
        self._checkpoints.pop(checkpoint_id, None)


class FileCheckpointStore:
    """Atomic local JSON checkpoint store suitable for process crash recovery."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, checkpoint_id: str) -> Path:
        if not ID_RE.fullmatch(checkpoint_id):
            raise ValueError("checkpoint id must be namespaced")
        safe = checkpoint_id.replace("/", "_").replace(":", "_")
        return self.root / f"{safe}.json"

    def load(self, checkpoint_id: str) -> ExecutionCheckpoint | None:
        path = self._path(checkpoint_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("checkpoint document must be an object")
        return ExecutionCheckpoint.from_dict(payload)

    def save(self, checkpoint: ExecutionCheckpoint) -> None:
        problems = checkpoint.validate()
        if problems:
            raise ValueError("invalid execution checkpoint: " + "; ".join(problems))
        target = self._path(checkpoint.id)
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        payload = json.dumps(
            checkpoint.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n"
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            _fsync_directory(target.parent)
        finally:
            if temporary.exists():
                temporary.unlink()

    def clear(self, checkpoint_id: str) -> None:
        path = self._path(checkpoint_id)
        if path.exists():
            path.unlink()
            _fsync_directory(path.parent)


__all__ = [
    "CHECKPOINT_MODEL_VERSION",
    "CHECKPOINT_STATUSES",
    "CheckpointOutput",
    "CheckpointStore",
    "ExecutionCheckpoint",
    "FileCheckpointStore",
    "MemoryCheckpointStore",
    "SlotCheckpoint",
]
