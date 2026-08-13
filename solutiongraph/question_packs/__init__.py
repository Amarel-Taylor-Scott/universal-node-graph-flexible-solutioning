"""Built-in, dependency-free semantic question-bank catalogue."""

from __future__ import annotations

from solutiongraph.interrogation.model import QuestionDefinition, QuestionPack
from solutiongraph.question_packs.concepts import CONCEPT_BY_ID, REFERENCE_CONCEPTS
from solutiongraph.question_packs.contact_point import CONTACT_POINT_PACK
from solutiongraph.question_packs.datetime import DATETIME_PACK
from solutiongraph.question_packs.document import DOCUMENT_PACK
from solutiongraph.question_packs.generic_tabular import GENERIC_TABULAR_PACK
from solutiongraph.question_packs.geography import GEOGRAPHY_PACK
from solutiongraph.question_packs.ml_dataset import ML_DATASET_PACK
from solutiongraph.question_packs.organization import ORGANIZATION_PACK
from solutiongraph.question_packs.person import PERSON_PACK
from solutiongraph.question_packs.postal_address import POSTAL_ADDRESS_PACK
from solutiongraph.question_packs.product import PRODUCT_PACK
from solutiongraph.question_packs.transaction import TRANSACTION_PACK

REFERENCE_QUESTION_PACKS: tuple[QuestionPack, ...] = (
    GENERIC_TABULAR_PACK,
    ORGANIZATION_PACK,
    POSTAL_ADDRESS_PACK,
    CONTACT_POINT_PACK,
    DATETIME_PACK,
    GEOGRAPHY_PACK,
    PERSON_PACK,
    PRODUCT_PACK,
    TRANSACTION_PACK,
    DOCUMENT_PACK,
    ML_DATASET_PACK,
)

QUESTION_PACK_BY_ID = {pack.id: pack for pack in REFERENCE_QUESTION_PACKS}
REFERENCE_QUESTIONS: tuple[QuestionDefinition, ...] = tuple(
    question for pack in REFERENCE_QUESTION_PACKS for question in pack.questions
)
QUESTION_BY_ID = {question.id: question for question in REFERENCE_QUESTIONS}


def validate_reference_question_packs() -> list[str]:
    problems: list[str] = []
    concept_ids = [concept.id for concept in REFERENCE_CONCEPTS]
    if len(concept_ids) != len(set(concept_ids)):
        problems.append("reference concepts must have unique ids")
    for index, concept in enumerate(REFERENCE_CONCEPTS):
        problems.extend(concept.validate(f"concepts[{index}]"))
        missing_parents = sorted(set(concept.parent_ids) - set(concept_ids))
        if missing_parents:
            problems.append(
                f"concepts[{index}] references unknown parents: " + ", ".join(missing_parents)
            )
    pack_ids = [pack.id for pack in REFERENCE_QUESTION_PACKS]
    question_ids = [question.id for question in REFERENCE_QUESTIONS]
    if len(pack_ids) != len(set(pack_ids)):
        problems.append("reference question packs must have unique ids")
    if len(question_ids) != len(set(question_ids)):
        problems.append("reference questions must have unique ids")
    for index, pack in enumerate(REFERENCE_QUESTION_PACKS):
        problems.extend(pack.validate(REFERENCE_CONCEPTS, f"question_packs[{index}]"))
    return problems


def get_question(question_id: str) -> QuestionDefinition:
    try:
        return QUESTION_BY_ID[question_id]
    except KeyError as exc:
        raise ValueError(
            f"unknown question {question_id!r}; run `solutiongraph questions list` "
            "to inspect available ids"
        ) from exc


def get_question_pack(pack_id: str) -> QuestionPack:
    try:
        return QUESTION_PACK_BY_ID[pack_id]
    except KeyError as exc:
        known = ", ".join(sorted(QUESTION_PACK_BY_ID))
        raise ValueError(
            f"unknown question pack {pack_id!r}; known packs: {known}"
        ) from exc


__all__ = [
    "CONCEPT_BY_ID",
    "QUESTION_BY_ID",
    "QUESTION_PACK_BY_ID",
    "REFERENCE_CONCEPTS",
    "REFERENCE_QUESTION_PACKS",
    "REFERENCE_QUESTIONS",
    "get_question",
    "get_question_pack",
    "validate_reference_question_packs",
]
