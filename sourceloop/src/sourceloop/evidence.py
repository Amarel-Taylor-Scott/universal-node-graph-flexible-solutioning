"""Filesystem-backed immutable evidence storage for raw email and attachments."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from .domain import AttachmentInfo

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class EvidenceStore:
    """Stores raw evidence under an application-owned volume.

    The paths returned by this class are internal identifiers. They should not be
    exposed directly by a public web server without a tenant-aware authorization layer.
    """

    def __init__(self, root: str | Path, attachment_max_bytes: int) -> None:
        self.root = Path(root).expanduser().resolve()
        self.attachment_max_bytes = attachment_max_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def store_raw_email(self, case_id: str, evidence_id: str, raw_message: bytes) -> str:
        directory = self._case_directory(case_id) / evidence_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "message.eml"
        self._write_once(path, raw_message)
        return str(path.relative_to(self.root))

    def store_attachment(
        self,
        case_id: str,
        evidence_id: str,
        filename: str,
        content_type: str,
        payload: bytes,
    ) -> AttachmentInfo:
        digest = hashlib.sha256(payload).hexdigest()
        safe_name = self._safe_filename(filename or "attachment.bin")
        if len(payload) > self.attachment_max_bytes:
            return AttachmentInfo(
                filename=safe_name,
                content_type=content_type or "application/octet-stream",
                size_bytes=len(payload),
                sha256=digest,
                evidence_path=None,
                status="rejected_too_large",
            )
        directory = self._case_directory(case_id) / evidence_id / "attachments"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{digest[:16]}-{safe_name}"
        self._write_once(path, payload)
        return AttachmentInfo(
            filename=safe_name,
            content_type=content_type or "application/octet-stream",
            size_bytes=len(payload),
            sha256=digest,
            evidence_path=str(path.relative_to(self.root)),
            status="stored_quarantined",
        )

    def _case_directory(self, case_id: str) -> Path:
        safe_case = self._safe_filename(case_id)
        path = (self.root / safe_case).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("Unsafe evidence path")
        return path

    @staticmethod
    def _safe_filename(value: str) -> str:
        sanitized = _SAFE_NAME.sub("_", Path(value).name).strip("._")
        return sanitized[:180] or "unnamed"

    @staticmethod
    def _write_once(path: Path, payload: bytes) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            return
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
