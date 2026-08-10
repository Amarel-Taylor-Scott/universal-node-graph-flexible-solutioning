"""Content-addressed value and artifact storage for reference execution.

The store is deliberately small: production harnesses may replace it with OCI,
object-storage, database, or distributed implementations without changing the
executor contract.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from solutiongraph.model import DIGEST_RE, canonical_json


def digest_bytes(payload: bytes) -> str:
    """Return the canonical digest identity for arbitrary bytes."""
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _portable_digest_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"bytes_digest": digest_bytes(value), "size_bytes": len(value)}
    if isinstance(value, tuple):
        return [_portable_digest_value(item) for item in value]
    if isinstance(value, list):
        return [_portable_digest_value(item) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): _portable_digest_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(
        f"reference execution cannot content-address {type(value).__name__}; "
        "use a runtime codec or emit JSON, text, or bytes"
    )


def digest_value(value: Any) -> str:
    """Digest a portable runtime value without silently serializing objects."""
    payload = canonical_json(_portable_digest_value(value)).encode("utf-8")
    return digest_bytes(payload)


@dataclass(frozen=True)
class StoredArtifact:
    """One immutable content-addressed output artifact."""

    digest: str
    media_type: str
    size_bytes: int
    uri: str = ""

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not DIGEST_RE.fullmatch(self.digest):
            problems.append("artifact digest must be sha256:<64 lowercase hex chars>")
        if not self.media_type.strip():
            problems.append("artifact media_type must not be empty")
        if self.size_bytes < 0:
            problems.append("artifact size_bytes must be non-negative")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "uri": self.uri,
        }


class ArtifactStore(Protocol):
    """Minimal replaceable artifact-store boundary."""

    def put_bytes(self, payload: bytes, *, media_type: str) -> StoredArtifact: ...

    def get_bytes(self, digest: str) -> bytes: ...

    def put_json(self, value: Any) -> StoredArtifact: ...

    def get_json(self, digest: str) -> Any: ...


@dataclass
class MemoryArtifactStore:
    """Deterministic in-memory store for tests, notebooks, and small runs."""

    _values: dict[str, bytes] = field(default_factory=dict)

    def put_bytes(
        self, payload: bytes, *, media_type: str = "application/octet-stream"
    ) -> StoredArtifact:
        digest = digest_bytes(payload)
        self._values.setdefault(digest, payload)
        return StoredArtifact(digest, media_type, len(payload), f"memory://{digest}")

    def get_bytes(self, digest: str) -> bytes:
        if not DIGEST_RE.fullmatch(digest):
            raise ValueError("invalid artifact digest")
        try:
            return self._values[digest]
        except KeyError as exc:
            raise FileNotFoundError(digest) from exc

    def put_json(self, value: Any) -> StoredArtifact:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return self.put_bytes(payload, media_type="application/json")

    def get_json(self, digest: str) -> Any:
        return json.loads(self.get_bytes(digest).decode("utf-8"))


@dataclass
class FileArtifactStore:
    """Local content store with atomic, deduplicated blob writes."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, digest: str) -> Path:
        if not DIGEST_RE.fullmatch(digest):
            raise ValueError("invalid artifact digest")
        hex_digest = digest.removeprefix("sha256:")
        return self.root / "sha256" / hex_digest[:2] / hex_digest[2:]

    def put_bytes(
        self, payload: bytes, *, media_type: str = "application/octet-stream"
    ) -> StoredArtifact:
        digest = digest_bytes(payload)
        target = self._path(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
            try:
                temporary.write_bytes(payload)
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()
        return StoredArtifact(digest, media_type, len(payload), target.as_uri())

    def get_bytes(self, digest: str) -> bytes:
        return self._path(digest).read_bytes()

    def put_json(self, value: Any) -> StoredArtifact:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return self.put_bytes(payload, media_type="application/json")

    def get_json(self, digest: str) -> Any:
        return json.loads(self.get_bytes(digest).decode("utf-8"))


def store_value(
    store: ArtifactStore,
    value: Any,
    *,
    media_type: str,
) -> StoredArtifact:
    """Store one portable port value using its declared media type."""
    if isinstance(value, bytes):
        return store.put_bytes(value, media_type=media_type)
    if isinstance(value, str) and (
        media_type.startswith("text/") or media_type not in {"application/json"}
    ):
        return store.put_bytes(value.encode("utf-8"), media_type=media_type)
    return store.put_json(value)


__all__ = [
    "ArtifactStore",
    "FileArtifactStore",
    "MemoryArtifactStore",
    "StoredArtifact",
    "digest_bytes",
    "digest_value",
    "store_value",
]
