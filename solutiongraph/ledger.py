"""Tamper-evident, append-only JSONL persistence for run receipts.

The journal is a durable local evidence primitive, not an immutable database or
authorization system.  Each line is independently parseable and chained to the
previous record digest.  File locking, append mode, flush, and fsync make a
successful append durable on ordinary local filesystems; external modification
is detected on the next read or append.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from solutiongraph.evidence import EvidenceLedger, RunReceipt
from solutiongraph.model import DIGEST_RE, sha256_digest

try:  # pragma: no cover - exercised on POSIX CI; absent on Windows
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

JOURNAL_SCHEMA_VERSION = "1.0"
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


class LedgerIntegrityError(ValueError):
    """Raised when a journal is truncated, malformed, reordered, or modified."""


@dataclass(frozen=True)
class JournalStatus:
    path: str
    receipt_count: int
    head_digest: str
    byte_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "receipt_count": self.receipt_count,
            "head_digest": self.head_digest,
            "byte_size": self.byte_size,
        }


def _thread_lock(path: Path) -> threading.Lock:
    key = str(path.resolve(strict=False))
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


@contextmanager
def _exclusive_file(path: Path, *, create: bool):
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise LedgerIntegrityError(f"receipt journal must not be a symlink: {path}")
    flags = os.O_RDWR | os.O_APPEND
    if create:
        flags |= os.O_CREAT
    flags |= getattr(os, "O_NOFOLLOW", 0)
    with _thread_lock(path):
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise LedgerIntegrityError(f"cannot open receipt journal {path}: {exc}") from exc
        handle: BinaryIO | None = None
        try:
            handle = os.fdopen(descriptor, "r+b", buffering=0)
            descriptor = -1
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield handle
        finally:
            if handle is not None:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()
            elif descriptor >= 0:
                os.close(descriptor)


def _fsync_parent(path: Path) -> None:
    """Persist a newly created directory entry where the platform permits it."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path.parent, flags)
    except OSError:  # pragma: no cover - directory fsync is platform/filesystem specific
        return
    try:
        os.fsync(descriptor)
    except OSError:  # pragma: no cover - some filesystems reject directory fsync
        pass
    finally:
        os.close(descriptor)


def _canonical_line(record: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _record_body(
    sequence: int,
    previous_digest: str,
    receipt: RunReceipt,
) -> dict[str, Any]:
    return {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "sequence": sequence,
        "previous_digest": previous_digest,
        "receipt": receipt.to_dict(),
    }


def _parse(data: bytes, path: Path) -> tuple[EvidenceLedger, str]:
    if data and not data.endswith(b"\n"):
        raise LedgerIntegrityError(f"receipt journal has a truncated final record: {path}")
    ledger = EvidenceLedger()
    previous_digest = ""
    for index, raw_line in enumerate(data.splitlines(), start=1):
        if not raw_line:
            raise LedgerIntegrityError(f"receipt journal contains a blank record at line {index}")
        try:
            record = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LedgerIntegrityError(
                f"receipt journal contains invalid JSON at line {index}: {exc}"
            ) from exc
        expected_keys = {
            "schema_version", "sequence", "previous_digest", "receipt", "record_digest"
        }
        if not isinstance(record, dict) or set(record) != expected_keys:
            raise LedgerIntegrityError(
                f"receipt journal record {index} has missing or unknown fields"
            )
        if record["schema_version"] != JOURNAL_SCHEMA_VERSION:
            raise LedgerIntegrityError(
                f"receipt journal record {index} uses unsupported schema version"
            )
        if record["sequence"] != index:
            raise LedgerIntegrityError(
                f"receipt journal record {index} has sequence {record['sequence']!r}"
            )
        if record["previous_digest"] != previous_digest:
            raise LedgerIntegrityError(
                f"receipt journal hash chain breaks at record {index}"
            )
        digest = record["record_digest"]
        if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
            raise LedgerIntegrityError(
                f"receipt journal record {index} has an invalid digest"
            )
        body = {key: record[key] for key in expected_keys - {"record_digest"}}
        if sha256_digest(body) != digest:
            raise LedgerIntegrityError(
                f"receipt journal record {index} digest does not match its content"
            )
        try:
            receipt = RunReceipt.from_dict(record["receipt"])
            ledger = ledger.append(receipt)
        except (TypeError, ValueError) as exc:
            raise LedgerIntegrityError(
                f"receipt journal record {index} contains invalid evidence: {exc}"
            ) from exc
        previous_digest = digest
    return ledger, previous_digest


@dataclass(frozen=True)
class JsonlReceiptJournal:
    """Append and verify content-chained run receipts in one local JSONL file."""

    path: Path

    def __init__(self, path: str | Path):
        object.__setattr__(self, "path", Path(path))

    def append(self, *receipts: RunReceipt) -> JournalStatus:
        if not receipts:
            return self.status()
        for receipt in receipts:
            problems = receipt.validate()
            if problems:
                raise ValueError("invalid evidence: " + "; ".join(problems))
        with _exclusive_file(self.path, create=True) as handle:
            handle.seek(0)
            data = handle.read()
            ledger, previous_digest = _parse(data, self.path)
            existing_ids = {receipt.id for receipt in ledger.receipts}
            incoming_ids = [receipt.id for receipt in receipts]
            if len(incoming_ids) != len(set(incoming_ids)) or existing_ids.intersection(
                incoming_ids
            ):
                raise ValueError("receipt ids must be globally unique")
            lines: list[bytes] = []
            sequence = len(ledger.receipts)
            for receipt in receipts:
                sequence += 1
                body = _record_body(sequence, previous_digest, receipt)
                previous_digest = sha256_digest(body)
                lines.append(_canonical_line({**body, "record_digest": previous_digest}))
            handle.seek(0, os.SEEK_END)
            for line in lines:
                handle.write(line)
            os.fsync(handle.fileno())
            _fsync_parent(self.path)
            byte_size = handle.tell()
        return JournalStatus(
            path=str(self.path),
            receipt_count=sequence,
            head_digest=previous_digest,
            byte_size=byte_size,
        )

    def read(self) -> EvidenceLedger:
        with _exclusive_file(self.path, create=False) as handle:
            handle.seek(0)
            ledger, _ = _parse(handle.read(), self.path)
        return ledger

    def status(self) -> JournalStatus:
        with _exclusive_file(self.path, create=False) as handle:
            handle.seek(0)
            data = handle.read()
            ledger, head_digest = _parse(data, self.path)
        return JournalStatus(
            path=str(self.path),
            receipt_count=len(ledger.receipts),
            head_digest=head_digest,
            byte_size=len(data),
        )


__all__ = [
    "JOURNAL_SCHEMA_VERSION",
    "JournalStatus",
    "JsonlReceiptJournal",
    "LedgerIntegrityError",
]
