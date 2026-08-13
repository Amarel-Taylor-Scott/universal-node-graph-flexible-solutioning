"""Reference data-science design-question packs."""

from __future__ import annotations

from solutiongraph.design_atlas.packs.framing_data import FRAMING_DATA_PACKS
from solutiongraph.design_atlas.packs.modeling import MODELING_PACKS
from solutiongraph.design_atlas.packs.operations import OPERATIONS_PACKS
from solutiongraph.design_atlas.sources import SOURCE_BY_ID

REFERENCE_DESIGN_PACKS = (*FRAMING_DATA_PACKS, *MODELING_PACKS, *OPERATIONS_PACKS)
REFERENCE_DESIGN_QUESTIONS = tuple(
    question for pack in REFERENCE_DESIGN_PACKS for question in pack.questions
)
DESIGN_PACK_BY_ID = {pack.id: pack for pack in REFERENCE_DESIGN_PACKS}
DESIGN_QUESTION_BY_ID = {
    question.id: question for question in REFERENCE_DESIGN_QUESTIONS
}


def validate_design_packs() -> list[str]:
    problems: list[str] = []
    if len(DESIGN_PACK_BY_ID) != len(REFERENCE_DESIGN_PACKS):
        problems.append("reference design pack ids must be unique")
    if len(DESIGN_QUESTION_BY_ID) != len(REFERENCE_DESIGN_QUESTIONS):
        problems.append("reference design question ids must be unique")
    for index, pack in enumerate(REFERENCE_DESIGN_PACKS):
        problems.extend(pack.validate(f"design_packs[{index}]"))
        missing = set(pack.reference_ids).difference(SOURCE_BY_ID)
        if missing:
            problems.append(f"{pack.id} has unknown references: {sorted(missing)}")
        for question in pack.questions:
            missing = set(question.reference_ids).difference(SOURCE_BY_ID)
            if missing:
                problems.append(
                    f"{question.id} has unknown references: {sorted(missing)}"
                )
    return problems


__all__ = [
    "DESIGN_PACK_BY_ID",
    "DESIGN_QUESTION_BY_ID",
    "REFERENCE_DESIGN_PACKS",
    "REFERENCE_DESIGN_QUESTIONS",
    "validate_design_packs",
]
