from __future__ import annotations

from dataclasses import replace

import pytest

from solutiongraph.model import sha256_digest
from solutiongraph.nexting.contracts import KnowledgeReference, KnowledgeState
from solutiongraph.nexting.knowledge import (
    KnowledgeQuery,
    KnowledgeSelector,
    MemoryKnowledgeStore,
)


def _reference(
    reference_id: str,
    kind: str,
    confidence: float,
    *tags: str,
) -> KnowledgeReference:
    return KnowledgeReference(
        id=reference_id,
        kind=kind,
        digest=sha256_digest(reference_id),
        tags=tuple(tags),
        confidence=confidence,
    )


def test_memory_store_requires_existing_parent_and_preserves_lineage() -> None:
    store = MemoryKnowledgeStore()
    root = KnowledgeState(
        id="state.root",
        revision="1",
        goal="Build an evidence-backed solution.",
    )
    store.put(root)
    child = replace(
        root,
        id="state.child",
        revision="2",
        parent_state_digest=root.digest,
    )
    store.put(child)
    assert store.count() == 2
    assert [state.id for state in store.lineage(child.digest)] == [
        "state.root",
        "state.child",
    ]

    orphan = replace(
        root,
        id="state.orphan",
        parent_state_digest=sha256_digest("missing-parent"),
    )
    with pytest.raises(ValueError, match="parent_state_digest"):
        store.put(orphan)


def test_knowledge_selector_is_deterministic_and_receipted() -> None:
    state = KnowledgeState(
        id="state.query-test",
        revision="1",
        goal="Select only relevant knowledge references.",
        references=(
            _reference(
                "knowledge.dataset-profile",
                "knowledge.dataset-profile",
                0.95,
                "topic.validation",
                "privacy.aggregate",
            ),
            _reference(
                "knowledge.raw-rows",
                "knowledge.raw-data",
                1.0,
                "topic.validation",
                "privacy.restricted",
            ),
            _reference(
                "knowledge.model-results",
                "knowledge.experiment-results",
                0.85,
                "topic.modeling",
                "privacy.aggregate",
            ),
        ),
    )
    query = KnowledgeQuery(
        id="knowledge-query.validation-aggregate",
        include_tags=("topic.validation",),
        exclude_tags=("privacy.restricted",),
        minimum_confidence=0.9,
        maximum_results=5,
    )
    matched, receipt = KnowledgeSelector().select(state, query)
    assert [item.id for item in matched] == ["knowledge.dataset-profile"]
    assert receipt.matched_reference_ids == ("knowledge.dataset-profile",)
    assert set(receipt.omitted_reference_ids) == {
        "knowledge.raw-rows",
        "knowledge.model-results",
    }
    assert not receipt.validate()
    assert receipt.digest.startswith("sha256:")
