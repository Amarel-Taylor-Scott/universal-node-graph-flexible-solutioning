"""Durable knowledge-state boundaries and deterministic reference queries.

The Solver Cell works with content-addressed references rather than requiring
all known bytes in one object or prompt.  A production implementation may
store states in files, object storage, databases, or a remote service while
preserving this protocol.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from solutiongraph.model import DIGEST_RE, ID_RE, canonical_json, sha256_digest
from solutiongraph.nexting.contracts import KnowledgeReference, KnowledgeState

KNOWLEDGE_STORE_MODEL_VERSION = "0.1"


@dataclass(frozen=True)
class KnowledgeQuery:
    """A portable selector over reference metadata, never hidden artifact reads."""

    id: str
    reference_ids: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ()
    include_tags: tuple[str, ...] = ()
    exclude_tags: tuple[str, ...] = ()
    visibility_classes: tuple[str, ...] = ()
    minimum_confidence: float = 0.0
    maximum_results: int | None = None
    require_all_include_tags: bool = False
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "knowledge_query") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        for label, values in (
            ("reference_ids", self.reference_ids),
            ("kinds", self.kinds),
            ("include_tags", self.include_tags),
            ("exclude_tags", self.exclude_tags),
            ("visibility_classes", self.visibility_classes),
        ):
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not ID_RE.fullmatch(value) for value in values):
                problems.append(
                    f"{path}.{label} must contain namespaced identifiers"
                )
        if set(self.include_tags) & set(self.exclude_tags):
            problems.append(f"{path} include and exclude tags must be disjoint")
        if not 0.0 <= self.minimum_confidence <= 1.0:
            problems.append(
                f"{path}.minimum_confidence must be between zero and one"
            )
        if self.maximum_results is not None and self.maximum_results <= 0:
            problems.append(f"{path}.maximum_results must be positive or null")
        try:
            canonical_json(dict(self.extensions))
        except (TypeError, ValueError):
            problems.append(f"{path}.extensions must be JSON serialisable")
        return problems

    def matches(self, reference: KnowledgeReference) -> bool:
        if self.reference_ids and reference.id not in self.reference_ids:
            return False
        if self.kinds and reference.kind not in self.kinds:
            return False
        if (
            self.visibility_classes
            and reference.visibility not in self.visibility_classes
        ):
            return False
        if reference.confidence < self.minimum_confidence:
            return False
        tags = set(reference.tags)
        includes = set(self.include_tags)
        if includes:
            if self.require_all_include_tags and not includes.issubset(tags):
                return False
            if not self.require_all_include_tags and not bool(includes & tags):
                return False
        return not bool(tags & set(self.exclude_tags))

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_store_model_version": KNOWLEDGE_STORE_MODEL_VERSION,
            "id": self.id,
            "reference_ids": list(self.reference_ids),
            "kinds": list(self.kinds),
            "include_tags": list(self.include_tags),
            "exclude_tags": list(self.exclude_tags),
            "visibility_classes": list(self.visibility_classes),
            "minimum_confidence": self.minimum_confidence,
            "maximum_results": self.maximum_results,
            "require_all_include_tags": self.require_all_include_tags,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class KnowledgeQueryReceipt:
    query_digest: str
    state_digest: str
    matched_reference_ids: tuple[str, ...]
    omitted_reference_ids: tuple[str, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "knowledge_query_receipt") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("query_digest", self.query_digest),
            ("state_digest", self.state_digest),
        ):
            if not DIGEST_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a sha256 digest")
        for label, values in (
            ("matched_reference_ids", self.matched_reference_ids),
            ("omitted_reference_ids", self.omitted_reference_ids),
        ):
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not ID_RE.fullmatch(value) for value in values):
                problems.append(
                    f"{path}.{label} must contain namespaced identifiers"
                )
        if set(self.matched_reference_ids) & set(self.omitted_reference_ids):
            problems.append(f"{path} matched and omitted sets must be disjoint")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_digest": self.query_digest,
            "state_digest": self.state_digest,
            "matched_reference_ids": list(self.matched_reference_ids),
            "omitted_reference_ids": list(self.omitted_reference_ids),
        }


class KnowledgeStore(Protocol):
    def put(self, state: KnowledgeState) -> str: ...

    def get(self, digest: str) -> KnowledgeState: ...

    def contains(self, digest: str) -> bool: ...

    def lineage(self, digest: str) -> tuple[KnowledgeState, ...]: ...


class MemoryKnowledgeStore:
    """Strict in-memory reference store for tests and short local sessions."""

    def __init__(self) -> None:
        self._states: dict[str, KnowledgeState] = {}

    def put(self, state: KnowledgeState) -> str:
        problems = state.validate()
        if problems:
            raise ValueError("invalid knowledge state: " + "; ".join(problems))
        digest = state.digest
        existing = self._states.get(digest)
        if existing is not None:
            if existing.to_dict() != state.to_dict():
                raise ValueError("knowledge digest collision with unequal state")
            return digest
        if state.parent_state_digest and state.parent_state_digest not in self._states:
            raise ValueError(
                "knowledge parent_state_digest must already exist in this store"
            )
        self._states[digest] = state
        return digest

    def get(self, digest: str) -> KnowledgeState:
        if not DIGEST_RE.fullmatch(digest):
            raise ValueError("knowledge digest must be a sha256 digest")
        try:
            return self._states[digest]
        except KeyError as exc:
            raise KeyError(f"unknown knowledge state {digest}") from exc

    def contains(self, digest: str) -> bool:
        return digest in self._states

    def lineage(self, digest: str) -> tuple[KnowledgeState, ...]:
        current = self.get(digest)
        reverse: list[KnowledgeState] = []
        seen: set[str] = set()
        while True:
            current_digest = current.digest
            if current_digest in seen:
                raise ValueError("knowledge-state lineage contains a cycle")
            seen.add(current_digest)
            reverse.append(current)
            if not current.parent_state_digest:
                break
            current = self.get(current.parent_state_digest)
        return tuple(reversed(reverse))

    def count(self) -> int:
        return len(self._states)


class KnowledgeSelector:
    """Resolve one deterministic query against an immutable state revision."""

    def select(
        self,
        state: KnowledgeState,
        query: KnowledgeQuery,
    ) -> tuple[tuple[KnowledgeReference, ...], KnowledgeQueryReceipt]:
        problems = (*state.validate(), *query.validate())
        if problems:
            raise ValueError("invalid knowledge query: " + "; ".join(problems))
        matched = [
            reference for reference in state.references if query.matches(reference)
        ]
        matched.sort(key=lambda item: (-item.confidence, item.id))
        if query.maximum_results is not None:
            matched = matched[: query.maximum_results]
        matched_ids = {item.id for item in matched}
        receipt = KnowledgeQueryReceipt(
            query_digest=query.digest,
            state_digest=state.digest,
            matched_reference_ids=tuple(item.id for item in matched),
            omitted_reference_ids=tuple(
                item.id for item in state.references if item.id not in matched_ids
            ),
        )
        return tuple(matched), receipt


__all__ = [
    "KNOWLEDGE_STORE_MODEL_VERSION",
    "KnowledgeQuery",
    "KnowledgeQueryReceipt",
    "KnowledgeSelector",
    "KnowledgeStore",
    "MemoryKnowledgeStore",
]
