"""Universal engineering obligations, domain packs, planning, and coverage."""

from solutiongraph.universal.catalog import (
    DOMAIN_PACK_BY_ID,
    ENGINEERING_QUESTION_BY_ID,
    OBLIGATION_BY_ID,
    REFERENCE_DOMAIN_PACKS,
    REFERENCE_ENGINEERING_QUESTIONS,
    REFERENCE_OBLIGATIONS,
    validate_universal_catalog,
)
from solutiongraph.universal.coverage import (
    RepositoryAssetInventory,
    assess_capability,
    assess_domain_pack,
    reference_asset_inventory,
    reference_coverage_report,
)
from solutiongraph.universal.model import (
    COVERAGE_STATUSES,
    FINGERPRINT_CHANNEL_IDS,
    CapabilityAssessment,
    CapabilityRequirement,
    DomainCoverageAssessment,
    DomainPack,
    EngineeringDesignPlan,
    EngineeringDesignQuestion,
    EngineeringPlanItem,
    FingerprintChannel,
    ObligationFamily,
    UniversalCoverageReport,
    UniversalDesignContext,
)
from solutiongraph.universal.planning import plan_engineering_design
from solutiongraph.universal.profiling import (
    context_from_task,
    fingerprint_attributes_from_context,
)

__all__ = [
    "COVERAGE_STATUSES",
    "CapabilityAssessment",
    "CapabilityRequirement",
    "DOMAIN_PACK_BY_ID",
    "DomainCoverageAssessment",
    "DomainPack",
    "ENGINEERING_QUESTION_BY_ID",
    "EngineeringDesignPlan",
    "EngineeringDesignQuestion",
    "EngineeringPlanItem",
    "FINGERPRINT_CHANNEL_IDS",
    "FingerprintChannel",
    "OBLIGATION_BY_ID",
    "ObligationFamily",
    "REFERENCE_DOMAIN_PACKS",
    "REFERENCE_ENGINEERING_QUESTIONS",
    "REFERENCE_OBLIGATIONS",
    "RepositoryAssetInventory",
    "UniversalCoverageReport",
    "UniversalDesignContext",
    "assess_capability",
    "assess_domain_pack",
    "context_from_task",
    "fingerprint_attributes_from_context",
    "plan_engineering_design",
    "reference_asset_inventory",
    "reference_coverage_report",
    "validate_universal_catalog",
]
