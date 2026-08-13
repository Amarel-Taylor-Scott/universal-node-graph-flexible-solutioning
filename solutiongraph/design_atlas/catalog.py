"""Deterministic atlas index and honest coverage summaries."""

from __future__ import annotations

from collections import Counter
from typing import Any

from solutiongraph.design_atlas.archetypes import REFERENCE_TASK_ARCHETYPES
from solutiongraph.design_atlas.packs import (
    REFERENCE_DESIGN_PACKS,
    REFERENCE_DESIGN_QUESTIONS,
)
from solutiongraph.design_atlas.sources import REFERENCE_SOURCES
from solutiongraph.design_atlas.techniques import REFERENCE_TECHNIQUES
from solutiongraph.model import sha256_digest


def atlas_index() -> dict[str, Any]:
    source_claims = Counter(item.source_claim for item in REFERENCE_TECHNIQUES)
    phases = []
    for phase_id in dict.fromkeys(item.phase_id for item in REFERENCE_TECHNIQUES):
        entries = [item for item in REFERENCE_TECHNIQUES if item.phase_id == phase_id]
        phases.append({
            "id": phase_id,
            "title": entries[0].phase_title,
            "technique_count": len(entries),
            "path": f"design-atlas/phases/{phase_id}.json",
        })
    index = {
        "design_atlas_model_version": "0.1",
        "source_count": len(REFERENCE_SOURCES),
        "technique_count": len(REFERENCE_TECHNIQUES),
        "phase_count": len(phases),
        "pack_count": len(REFERENCE_DESIGN_PACKS),
        "question_count": len(REFERENCE_DESIGN_QUESTIONS),
        "task_archetype_count": len(REFERENCE_TASK_ARCHETYPES),
        "source_claim_counts": dict(sorted(source_claims.items())),
        "machine_maturity": {"C1": len(REFERENCE_TECHNIQUES)},
        "phases": phases,
        "packs": [
            {
                "id": pack.id,
                "title": pack.title,
                "digest": pack.digest,
                "question_count": len(pack.questions),
                "path": f"design-atlas/packs/{pack.id}.json",
            }
            for pack in REFERENCE_DESIGN_PACKS
        ],
        "archetypes": [
            {
                "id": item.id,
                "title": item.title,
                "digest": item.digest,
                "path": f"design-atlas/archetypes/{item.id}.json",
            }
            for item in REFERENCE_TASK_ARCHETYPES
        ],
        "claim_boundary": (
            "All 618 owner-supplied techniques are cataloged at C1 only. Source labels "
            "are retained for provenance and are not SolutionGraph maturity evidence."
        ),
    }
    index["digest"] = sha256_digest(index)
    return index


__all__ = ["atlas_index"]
