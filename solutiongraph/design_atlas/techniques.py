"""Load the normalized 618-entry owner-supplied technique inventory."""

from __future__ import annotations

import json
from importlib.resources import files

from solutiongraph.design_atlas.model import Technique


def _load() -> tuple[Technique, ...]:
    payload = json.loads(
        files("solutiongraph.design_atlas")
        .joinpath("data/techniques.json")
        .read_text(encoding="utf-8")
    )
    return tuple(
        Technique(
            id=item["id"],
            ordinal=item["ordinal"],
            phase_id=item["phase_id"],
            phase_title=item["phase_title"],
            family=item["family"],
            title=item["title"],
            examples=item["examples"],
            source_claim=item["source_claim"],
            source_note=item["source_note"],
            source_id=item["source_id"],
            owner=item["owner"],
            references=tuple(item["references"]),
            tags=tuple(item["tags"]),
        )
        for item in payload
    )


REFERENCE_TECHNIQUES = _load()
TECHNIQUE_BY_ID = {item.id: item for item in REFERENCE_TECHNIQUES}
TECHNIQUES_BY_PHASE = {
    phase_id: tuple(item for item in REFERENCE_TECHNIQUES if item.phase_id == phase_id)
    for phase_id in dict.fromkeys(item.phase_id for item in REFERENCE_TECHNIQUES)
}


def validate_techniques() -> list[str]:
    problems: list[str] = []
    if len(REFERENCE_TECHNIQUES) != 618:
        problems.append(
            f"owner technique inventory must contain 618 rows; found {len(REFERENCE_TECHNIQUES)}"
        )
    if len(TECHNIQUE_BY_ID) != len(REFERENCE_TECHNIQUES):
        problems.append("technique ids must be unique")
    for index, technique in enumerate(REFERENCE_TECHNIQUES):
        problems.extend(technique.validate(f"techniques[{index}]"))
    return problems


__all__ = [
    "REFERENCE_TECHNIQUES",
    "TECHNIQUE_BY_ID",
    "TECHNIQUES_BY_PHASE",
    "validate_techniques",
]
