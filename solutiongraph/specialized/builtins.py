"""Closed reference registry for the bundled specialized capability packs."""

from solutiongraph.specialized.data_analysis import PACK as DATA_ANALYSIS_PACK
from solutiongraph.specialized.data_engineering import PACK as DATA_ENGINEERING_PACK
from solutiongraph.specialized.data_science import PACK as DATA_SCIENCE_PACK
from solutiongraph.specialized.llm_engineering import PACK as LLM_ENGINEERING_PACK
from solutiongraph.specialized.ml_engineering import PACK as ML_ENGINEERING_PACK
from solutiongraph.specialized.model import SpecializedPackRegistry
from solutiongraph.specialized.operations import PACK as OPERATIONS_PACK
from solutiongraph.specialized.software_engineering import PACK as SOFTWARE_ENGINEERING_PACK

REFERENCE_SPECIALIZED_PACKS = (
    DATA_ENGINEERING_PACK,
    DATA_ANALYSIS_PACK,
    DATA_SCIENCE_PACK,
    ML_ENGINEERING_PACK,
    LLM_ENGINEERING_PACK,
    SOFTWARE_ENGINEERING_PACK,
    OPERATIONS_PACK,
)

REFERENCE_SPECIALIZED_PACK_REGISTRY = SpecializedPackRegistry(
    id="registry.reference-specialized-packs",
    version="0.1.0",
    packs=REFERENCE_SPECIALIZED_PACKS,
    description=(
        "Bundled extraction-ready capability packs for common engineering task families. "
        "Definitions nominate assets and starting recipes; they do not replace compiler "
        "admission or exact solution-pack closure."
    ),
)

SPECIALIZED_PACK_BY_ID = {pack.id: pack for pack in REFERENCE_SPECIALIZED_PACKS}

__all__ = [
    "DATA_ANALYSIS_PACK",
    "DATA_ENGINEERING_PACK",
    "DATA_SCIENCE_PACK",
    "LLM_ENGINEERING_PACK",
    "ML_ENGINEERING_PACK",
    "OPERATIONS_PACK",
    "REFERENCE_SPECIALIZED_PACK_REGISTRY",
    "REFERENCE_SPECIALIZED_PACKS",
    "SOFTWARE_ENGINEERING_PACK",
    "SPECIALIZED_PACK_BY_ID",
]
