"""Semantic question banks, typed interrogation plans, and shadow repair.

The package keeps its import surface lazy so question-pack modules can depend
on the immutable model without creating a catalogue/engine import cycle.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from solutiongraph.interrogation.model import (
    INTERROGATION_MODEL_VERSION,
    CheckRequirement,
    ConceptDefinition,
    DatasetProfile,
    FieldConceptMatch,
    FieldProfile,
    Finding,
    FindingSet,
    InterrogationBudget,
    PatchOperation,
    QuestionDefinition,
    QuestionPack,
    QuestionPlan,
    QuestionPlanItem,
    QuestionReceipt,
    RepairApplicationReceipt,
    RepairProposal,
    SemanticFieldMap,
    StandardsReference,
    VerificationReceipt,
)

_LAZY_EXPORTS = {
    "InterrogationEngine": ("solutiongraph.interrogation.engine", "InterrogationEngine"),
    "QuestionPlanner": ("solutiongraph.interrogation.planning", "QuestionPlanner"),
    "effort_budget": ("solutiongraph.interrogation.planning", "effort_budget"),
    "QuestionExecutor": ("solutiongraph.interrogation.execution", "QuestionExecutor"),
    "STANDARD_CHECK_REGISTRY": (
        "solutiongraph.interrogation.execution",
        "STANDARD_CHECK_REGISTRY",
    ),
    "RepairProposalEngine": (
        "solutiongraph.interrogation.repair",
        "RepairProposalEngine",
    ),
    "apply_repair_shadow": (
        "solutiongraph.interrogation.repair",
        "apply_repair_shadow",
    ),
    "reverse_repair_shadow": (
        "solutiongraph.interrogation.repair",
        "reverse_repair_shadow",
    ),
    "profile_records": ("solutiongraph.interrogation.profiling", "profile_records"),
    "map_semantic_fields": (
        "solutiongraph.interrogation.profiling",
        "map_semantic_fields",
    ),
    "verify_repair": ("solutiongraph.interrogation.verification", "verify_repair"),
    "InterrogationRunReport": (
        "solutiongraph.interrogation.reporting",
        "InterrogationRunReport",
    ),
    "write_report_bundle": (
        "solutiongraph.interrogation.reporting",
        "write_report_bundle",
    ),
    "QuestionUtilityMemory": (
        "solutiongraph.interrogation.learning",
        "QuestionUtilityMemory",
    ),
    "QuestionUtilityObservation": (
        "solutiongraph.interrogation.learning",
        "QuestionUtilityObservation",
    ),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


__all__ = [
    "INTERROGATION_MODEL_VERSION",
    "CheckRequirement",
    "ConceptDefinition",
    "DatasetProfile",
    "FieldConceptMatch",
    "FieldProfile",
    "Finding",
    "FindingSet",
    "InterrogationBudget",
    "PatchOperation",
    "QuestionDefinition",
    "QuestionPack",
    "QuestionPlan",
    "QuestionPlanItem",
    "QuestionReceipt",
    "RepairApplicationReceipt",
    "RepairProposal",
    "SemanticFieldMap",
    "StandardsReference",
    "VerificationReceipt",
    *_LAZY_EXPORTS,
]
