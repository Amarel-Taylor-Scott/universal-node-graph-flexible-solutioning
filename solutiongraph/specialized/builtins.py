"""Closed reference registry for the bundled specialized capability packs."""

from solutiongraph.specialized.creative_content_production import (
    PACK as CREATIVE_CONTENT_PRODUCTION_PACK,
)
from solutiongraph.specialized.cybersecurity import PACK as CYBERSECURITY_PACK
from solutiongraph.specialized.data_analysis import PACK as DATA_ANALYSIS_PACK
from solutiongraph.specialized.data_engineering import PACK as DATA_ENGINEERING_PACK
from solutiongraph.specialized.data_science import PACK as DATA_SCIENCE_PACK
from solutiongraph.specialized.document_intelligence import PACK as DOCUMENT_INTELLIGENCE_PACK
from solutiongraph.specialized.education_assessment import PACK as EDUCATION_ASSESSMENT_PACK
from solutiongraph.specialized.embedded_iot import PACK as EMBEDDED_IOT_PACK
from solutiongraph.specialized.finance_risk_fraud import PACK as FINANCE_RISK_FRAUD_PACK
from solutiongraph.specialized.game_engineering import PACK as GAME_ENGINEERING_PACK
from solutiongraph.specialized.geospatial_temporal import PACK as GEOSPATIAL_TEMPORAL_PACK
from solutiongraph.specialized.healthcare_biomedical import PACK as HEALTHCARE_BIOMEDICAL_PACK
from solutiongraph.specialized.knowledge_research import PACK as KNOWLEDGE_RESEARCH_PACK
from solutiongraph.specialized.llm_engineering import PACK as LLM_ENGINEERING_PACK
from solutiongraph.specialized.llm_evaluation_safety import PACK as LLM_EVALUATION_SAFETY_PACK
from solutiongraph.specialized.media_intelligence import PACK as MEDIA_INTELLIGENCE_PACK
from solutiongraph.specialized.ml_engineering import PACK as ML_ENGINEERING_PACK
from solutiongraph.specialized.model import SpecializedPackRegistry
from solutiongraph.specialized.operations import PACK as OPERATIONS_PACK
from solutiongraph.specialized.privacy_governance_compliance import (
    PACK as PRIVACY_GOVERNANCE_COMPLIANCE_PACK,
)
from solutiongraph.specialized.product_experimentation import PACK as PRODUCT_EXPERIMENTATION_PACK
from solutiongraph.specialized.robotics_control import PACK as ROBOTICS_CONTROL_PACK
from solutiongraph.specialized.scientific_computing_digital_twins import (
    PACK as SCIENTIFIC_COMPUTING_DIGITAL_TWINS_PACK,
)
from solutiongraph.specialized.search_recommendation import PACK as SEARCH_RECOMMENDATION_PACK
from solutiongraph.specialized.software_engineering import PACK as SOFTWARE_ENGINEERING_PACK
from solutiongraph.specialized.supply_chain_planning import PACK as SUPPLY_CHAIN_PLANNING_PACK
from solutiongraph.specialized.three_d_simulation import PACK as THREE_D_SIMULATION_PACK

REFERENCE_SPECIALIZED_PACKS = (
    DATA_ENGINEERING_PACK,
    DATA_ANALYSIS_PACK,
    DATA_SCIENCE_PACK,
    ML_ENGINEERING_PACK,
    LLM_ENGINEERING_PACK,
    SOFTWARE_ENGINEERING_PACK,
    OPERATIONS_PACK,
    LLM_EVALUATION_SAFETY_PACK,
    CYBERSECURITY_PACK,
    PRIVACY_GOVERNANCE_COMPLIANCE_PACK,
    DOCUMENT_INTELLIGENCE_PACK,
    MEDIA_INTELLIGENCE_PACK,
    THREE_D_SIMULATION_PACK,
    GAME_ENGINEERING_PACK,
    GEOSPATIAL_TEMPORAL_PACK,
    ROBOTICS_CONTROL_PACK,
    SCIENTIFIC_COMPUTING_DIGITAL_TWINS_PACK,
    EMBEDDED_IOT_PACK,
    HEALTHCARE_BIOMEDICAL_PACK,
    FINANCE_RISK_FRAUD_PACK,
    SUPPLY_CHAIN_PLANNING_PACK,
    PRODUCT_EXPERIMENTATION_PACK,
    SEARCH_RECOMMENDATION_PACK,
    KNOWLEDGE_RESEARCH_PACK,
    EDUCATION_ASSESSMENT_PACK,
    CREATIVE_CONTENT_PRODUCTION_PACK,
)

REFERENCE_SPECIALIZED_PACK_REGISTRY = SpecializedPackRegistry(
    id="registry.reference-specialized-packs",
    version="0.2.0",
    packs=REFERENCE_SPECIALIZED_PACKS,
    description=(
        "Bundled extraction-ready capability packs for common engineering task families. "
        "Definitions nominate assets and starting recipes; they do not replace compiler "
        "admission or exact solution-pack closure."
    ),
)

SPECIALIZED_PACK_BY_ID = {pack.id: pack for pack in REFERENCE_SPECIALIZED_PACKS}

__all__ = [
    "CREATIVE_CONTENT_PRODUCTION_PACK",
    "CYBERSECURITY_PACK",
    "DATA_ANALYSIS_PACK",
    "DATA_ENGINEERING_PACK",
    "DATA_SCIENCE_PACK",
    "DOCUMENT_INTELLIGENCE_PACK",
    "EDUCATION_ASSESSMENT_PACK",
    "EMBEDDED_IOT_PACK",
    "FINANCE_RISK_FRAUD_PACK",
    "GAME_ENGINEERING_PACK",
    "GEOSPATIAL_TEMPORAL_PACK",
    "HEALTHCARE_BIOMEDICAL_PACK",
    "KNOWLEDGE_RESEARCH_PACK",
    "LLM_ENGINEERING_PACK",
    "LLM_EVALUATION_SAFETY_PACK",
    "MEDIA_INTELLIGENCE_PACK",
    "ML_ENGINEERING_PACK",
    "OPERATIONS_PACK",
    "PRIVACY_GOVERNANCE_COMPLIANCE_PACK",
    "PRODUCT_EXPERIMENTATION_PACK",
    "REFERENCE_SPECIALIZED_PACK_REGISTRY",
    "REFERENCE_SPECIALIZED_PACKS",
    "ROBOTICS_CONTROL_PACK",
    "SCIENTIFIC_COMPUTING_DIGITAL_TWINS_PACK",
    "SEARCH_RECOMMENDATION_PACK",
    "SOFTWARE_ENGINEERING_PACK",
    "SPECIALIZED_PACK_BY_ID",
    "SUPPLY_CHAIN_PLANNING_PACK",
    "THREE_D_SIMULATION_PACK",
]
