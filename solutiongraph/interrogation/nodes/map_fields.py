"""Conservative semantic field mapping node."""

from __future__ import annotations

from typing import Any

from solutiongraph.interrogation.model import DatasetProfile
from solutiongraph.interrogation.profiling import map_semantic_fields
from solutiongraph.question_packs import REFERENCE_CONCEPTS


def map_fields_node(
    profile: dict[str, Any],
    mapping_strategy: str = "conservative",
) -> dict[str, Any]:
    mapped = map_semantic_fields(
        DatasetProfile.from_dict(profile),
        REFERENCE_CONCEPTS,
        strategy=mapping_strategy,
    )
    return mapped.to_dict()


__all__ = ["map_fields_node"]
