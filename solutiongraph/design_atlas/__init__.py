"""Data-science design atlas public API."""

from solutiongraph.design_atlas.archetypes import (
    ARCHETYPE_BY_ID,
    REFERENCE_TASK_ARCHETYPES,
    get_archetype,
    normalize_task_type,
    validate_archetypes,
)
from solutiongraph.design_atlas.catalog import atlas_index
from solutiongraph.design_atlas.model import (
    DESIGN_ATLAS_MODEL_VERSION,
    CapabilityEvidence,
    DecisionAnswer,
    DesignContext,
    DesignDossier,
    DesignPlan,
    MaturityAssessment,
    TaskArchetype,
    Technique,
)
from solutiongraph.design_atlas.node_pack import (
    DESIGN_ATLAS_NODE_PACK,
    DESIGN_ATLAS_NODE_SPECS,
    DESIGN_ATLAS_PROGRAM,
    DESIGN_ATLAS_REGISTRY,
    design_atlas_program,
)
from solutiongraph.design_atlas.packs import (
    DESIGN_PACK_BY_ID,
    DESIGN_QUESTION_BY_ID,
    REFERENCE_DESIGN_PACKS,
    REFERENCE_DESIGN_QUESTIONS,
    validate_design_packs,
)
from solutiongraph.design_atlas.planning import DesignPlanner, assess_maturity, effort_policy
from solutiongraph.design_atlas.profiling import context_from_profile, context_from_records
from solutiongraph.design_atlas.sources import REFERENCE_SOURCES, validate_sources
from solutiongraph.design_atlas.techniques import (
    REFERENCE_TECHNIQUES,
    TECHNIQUE_BY_ID,
    TECHNIQUES_BY_PHASE,
    validate_techniques,
)


def validate_design_atlas() -> list[str]:
    return [
        *validate_sources(),
        *validate_techniques(),
        *validate_design_packs(),
        *validate_archetypes(),
    ]


__all__ = [
    "ARCHETYPE_BY_ID",
    "CapabilityEvidence",
    "DESIGN_ATLAS_MODEL_VERSION",
    "DESIGN_ATLAS_NODE_PACK",
    "DESIGN_ATLAS_NODE_SPECS",
    "DESIGN_ATLAS_PROGRAM",
    "DESIGN_ATLAS_REGISTRY",
    "DESIGN_PACK_BY_ID",
    "DESIGN_QUESTION_BY_ID",
    "DecisionAnswer",
    "DesignContext",
    "DesignDossier",
    "DesignPlan",
    "DesignPlanner",
    "MaturityAssessment",
    "REFERENCE_DESIGN_PACKS",
    "REFERENCE_DESIGN_QUESTIONS",
    "REFERENCE_SOURCES",
    "REFERENCE_TASK_ARCHETYPES",
    "REFERENCE_TECHNIQUES",
    "TECHNIQUE_BY_ID",
    "TECHNIQUES_BY_PHASE",
    "TaskArchetype",
    "Technique",
    "assess_maturity",
    "atlas_index",
    "context_from_profile",
    "context_from_records",
    "design_atlas_program",
    "effort_policy",
    "get_archetype",
    "normalize_task_type",
    "validate_design_atlas",
]
