"""Primary and official sources behind the reference decision packs."""

from __future__ import annotations

from solutiongraph.design_atlas.model import ResearchReference

REFERENCE_SOURCES = (
    ResearchReference(
        "source.nist.ai-rmf-1",
        "NIST AI Risk Management Framework 1.0",
        "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf",
        "source.official-standard",
        "AI risk work should connect governance, context mapping, measurement, and management.",
        "NIST AI 100-1 (2023)",
    ),
    ResearchReference(
        "source.nist.ai-rmf-playbook",
        "NIST AI RMF Playbook",
        "https://airc.nist.gov/airmf-resources/playbook/",
        "source.official-guidance",
        "Risk actions are context-dependent suggestions rather than a universal linear checklist.",
        "accessed 2026-08-13",
    ),
    ResearchReference(
        "source.sklearn.common-pitfalls",
        "scikit-learn common pitfalls and recommended practices",
        "https://scikit-learn.org/stable/common_pitfalls.html",
        "source.official-documentation",
        "Preprocessing, selection, and other learned transforms must be fitted without test leakage.",
        "scikit-learn stable documentation",
    ),
    ResearchReference(
        "source.sklearn.cross-validation",
        "scikit-learn cross-validation guide",
        "https://scikit-learn.org/stable/modules/cross_validation.html",
        "source.official-documentation",
        "Evaluation splits and randomness must match the data-generating and deployment structure.",
        "scikit-learn stable documentation",
    ),
    ResearchReference(
        "source.tensorflow.data-validation",
        "TensorFlow Data Validation guide",
        "https://www.tensorflow.org/tfx/guide/tfdv",
        "source.official-documentation",
        "Schemas, anomalies, training-serving skew, and longitudinal drift are distinct checks.",
        "TensorFlow TFX documentation",
    ),
    ResearchReference(
        "source.gebru.datasheets",
        "Datasheets for Datasets",
        "https://arxiv.org/abs/1803.09010",
        "source.primary-research",
        "Dataset motivation, composition, collection, use, distribution, and maintenance need documentation.",
        "Gebru et al. (2021)",
    ),
    ResearchReference(
        "source.pushkarna.data-cards",
        "Data Cards: Purposeful and Transparent Dataset Documentation",
        "https://arxiv.org/abs/2204.01075",
        "source.primary-research",
        "Dataset documentation should be structured for stakeholder decisions across the lifecycle.",
        "Pushkarna et al. (2022)",
    ),
    ResearchReference(
        "source.mitchell.model-cards",
        "Model Cards for Model Reporting",
        "https://arxiv.org/abs/1810.03993",
        "source.primary-research",
        "Models should disclose intended use, evaluation context, limitations, and relevant subgroup results.",
        "Mitchell et al. (2019)",
    ),
    ResearchReference(
        "source.breck.ml-test-score",
        "The ML Test Score",
        "https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/",
        "source.primary-research",
        "Production readiness includes data, model, infrastructure, and monitoring tests beyond offline quality.",
        "Breck et al. (2017)",
    ),
    ResearchReference(
        "source.nist.adversarial-ml",
        "NIST Adversarial Machine Learning Taxonomy",
        "https://csrc.nist.gov/pubs/ai/100/2/e2025/final",
        "source.official-standard",
        "Threat modeling should distinguish lifecycle stage, attacker goals, capability, and knowledge.",
        "NIST AI 100-2 E2025",
    ),
    ResearchReference(
        "source.stanford.helm",
        "Holistic Evaluation of Language Models",
        "https://arxiv.org/abs/2211.09110",
        "source.primary-research",
        "Language-model evaluation should make scenarios, metrics, coverage, and raw observations explicit.",
        "Liang et al. (2022)",
    ),
    ResearchReference(
        "source.mlcommons.safety-methodology",
        "MLCommons AILuminate safety methodology",
        "https://mlcommons.org/ailuminate/safety-methodology/",
        "source.official-benchmark-methodology",
        "Safety benchmark scope, personas, evaluator uncertainty, and coverage limitations must be disclosed.",
        "accessed 2026-08-13",
    ),
)

SOURCE_BY_ID = {source.id: source for source in REFERENCE_SOURCES}


def validate_sources() -> list[str]:
    problems: list[str] = []
    if len(SOURCE_BY_ID) != len(REFERENCE_SOURCES):
        problems.append("reference source ids must be unique")
    for index, source in enumerate(REFERENCE_SOURCES):
        problems.extend(source.validate(f"sources[{index}]"))
    return problems


__all__ = ["REFERENCE_SOURCES", "SOURCE_BY_ID", "validate_sources"]
