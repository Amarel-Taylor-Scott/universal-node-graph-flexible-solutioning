"""Fsync-backed local hash chain for agent trial receipts."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from solutiongraph.agent_bench.model import (
    AgentTrialBudget,
    AgentTrialReceipt,
    TrialArtifact,
    TrialPlan,
)
from solutiongraph.model import sha256_digest

AGENT_JOURNAL_VERSION = "0.1"


class AgentJournalIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class AgentJournalStatus:
    receipt_count: int
    head_digest: str


def _budget(value: dict[str, Any]) -> AgentTrialBudget:
    return AgentTrialBudget(**value)


def receipt_from_dict(value: dict[str, Any]) -> AgentTrialReceipt:
    plan = value["plan"]
    trial = TrialPlan(
        id=plan["id"],
        suite_digest=plan["suite_digest"],
        task_id=plan["task_id"],
        task_digest=plan["task_digest"],
        condition=plan["condition"],
        harness_id=plan["harness_id"],
        harness_version=plan["harness_version"],
        model_id=plan["model_id"],
        model_revision=plan["model_revision"],
        seed=plan["seed"],
        repetition=plan["repetition"],
        budget=_budget(plan["budget"]),
    )
    return AgentTrialReceipt(
        id=value["id"],
        plan=trial,
        plan_digest=value["plan_digest"],
        prompt_digest=value["prompt_digest"],
        context_digest=value["context_digest"],
        context_bytes=value["context_bytes"],
        workspace_manifest_digest=value["workspace_manifest_digest"],
        lifecycle=tuple(value["lifecycle"]),
        started_at=value["started_at"],
        ended_at=value["ended_at"],
        wall_seconds=value["wall_seconds"],
        exit_code=value["exit_code"],
        timed_out=value["timed_out"],
        command_digest=value["command_digest"],
        stdout_digest=value["stdout_digest"],
        stderr_digest=value["stderr_digest"],
        artifacts=tuple(TrialArtifact(**item) for item in value["artifacts"]),
        metrics=tuple(sorted((name, float(metric)) for name, metric in value["metrics"].items())),
        accepted=value["accepted"],
        problems=tuple(value["problems"]),
        environment_variable_names=tuple(value["environment_variable_names"]),
        budget_enforcement=tuple(value["budget_enforcement"]),
        isolation=value["isolation"],
    )


class AgentTrialJournal:
    """Local tamper-evident evidence; not authenticated WORM storage."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                record = json.loads(line)
            except ValueError as exc:
                raise AgentJournalIntegrityError(f"line {line_number} is not JSON") from exc
            records.append(record)
        self._verify(records)
        return records

    @staticmethod
    def _verify(records: list[dict[str, Any]]) -> None:
        previous = ""
        ids: set[str] = set()
        for index, record in enumerate(records, start=1):
            required = {
                "journal_version",
                "sequence",
                "previous_digest",
                "receipt_digest",
                "receipt",
                "record_digest",
            }
            if not isinstance(record, dict) or set(record) != required:
                raise AgentJournalIntegrityError(f"record {index} has an invalid shape")
            if record["journal_version"] != AGENT_JOURNAL_VERSION or record["sequence"] != index:
                raise AgentJournalIntegrityError(f"record {index} has an invalid version or sequence")
            if record["previous_digest"] != previous:
                raise AgentJournalIntegrityError(f"record {index} breaks the previous-digest chain")
            receipt = receipt_from_dict(record["receipt"])
            problems = receipt.validate()
            if problems:
                raise AgentJournalIntegrityError(f"record {index} contains an invalid receipt: {'; '.join(problems)}")
            if receipt.id in ids:
                raise AgentJournalIntegrityError(f"record {index} repeats receipt ID {receipt.id}")
            ids.add(receipt.id)
            if record["receipt_digest"] != receipt.digest:
                raise AgentJournalIntegrityError(f"record {index} receipt digest does not match")
            body = {key: value for key, value in record.items() if key != "record_digest"}
            expected = sha256_digest(body)
            if record["record_digest"] != expected:
                raise AgentJournalIntegrityError(f"record {index} record digest does not match")
            previous = record["record_digest"]

    def append(self, receipt: AgentTrialReceipt) -> AgentJournalStatus:
        problems = receipt.validate()
        if problems:
            raise ValueError("invalid agent trial receipt: " + "; ".join(problems))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        with lock_path.open("a+b") as lock:
            if os.name == "posix":
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            records = self._records()
            if any(record["receipt"]["id"] == receipt.id for record in records):
                raise ValueError(f"agent trial receipt IDs must be globally unique: {receipt.id}")
            previous = records[-1]["record_digest"] if records else ""
            body = {
                "journal_version": AGENT_JOURNAL_VERSION,
                "sequence": len(records) + 1,
                "previous_digest": previous,
                "receipt_digest": receipt.digest,
                "receipt": receipt.to_dict(),
            }
            record = {**body, "record_digest": sha256_digest(body)}
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return AgentJournalStatus(len(records) + 1, record["record_digest"])

    def receipts(self) -> tuple[AgentTrialReceipt, ...]:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        return tuple(receipt_from_dict(record["receipt"]) for record in self._records())

    def status(self) -> AgentJournalStatus:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        records = self._records()
        return AgentJournalStatus(len(records), records[-1]["record_digest"] if records else "")


__all__ = [
    "AGENT_JOURNAL_VERSION",
    "AgentJournalIntegrityError",
    "AgentJournalStatus",
    "AgentTrialJournal",
    "receipt_from_dict",
]
