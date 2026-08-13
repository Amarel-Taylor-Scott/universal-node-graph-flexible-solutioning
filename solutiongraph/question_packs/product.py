"""Product identity, brand, hierarchy, and identifier questions."""

from __future__ import annotations

from solutiongraph.question_packs.base import deterministic, external, human, llm, pack, q

PRODUCT = (
    "concept.product.name", "concept.product.identifier", "concept.product.brand",
)

PRODUCT_QUESTIONS = (
    q(
        "product", "identifier-shape", "Product identifier shape",
        "Do SKU, UPC, EAN, GTIN, and internal identifiers follow their declared schemes?",
        ("concept.product.identifier",), "product.identifier-invalid", "high",
        (deterministic("quality.product-identifier-check"),
         external("authority.product-identifier-lookup", cost_tier=5)),
    ),
    q(
        "product", "identifier-uniqueness", "Product identifier uniqueness",
        "Does one identifier map to one intended product level rather than conflicting variants?",
        ("concept.product.identifier",), "product.identifier-conflict", "high",
        (deterministic("quality.identifier-uniqueness-check"),), scope="entity",
    ),
    q(
        "product", "name-brand", "Product name and brand consistency",
        "Do product names, brands, and manufacturers agree without duplicating brand tokens incorrectly?",
        ("concept.product.name", "concept.product.brand"),
        "product.name-brand-conflict", "medium",
        (deterministic("quality.product-brand-check", cost_tier=2),
         llm("quality.adjudicate-product-brand")), scope="entity",
    ),
    q(
        "product", "variant-level", "Product and variant granularity",
        "Are size, color, package, and regional variants distinguished from parent products?",
        PRODUCT, "product.variant-granularity-conflict", "high",
        (deterministic("quality.product-variant-check", cost_tier=3),
         human("quality.review-product-variant")), scope="entity",
    ),
    q(
        "product", "duplicates", "Duplicate product entities",
        "Do normalized names and identifiers expose duplicate or conflicting product records?",
        PRODUCT, "product.possible-duplicate", "medium",
        (deterministic("quality.product-duplicate-check", cost_tier=3),), scope="dataset",
        repairs=("repair.quarantine-duplicate",),
    ),
    q(
        "product", "temporal-validity", "Product lifecycle validity",
        "Are discontinued, renamed, recalled, or region-restricted products interpreted at the relevant date?",
        PRODUCT, "product.temporal-status-conflict", "high",
        (external("authority.product-history-lookup", cost_tier=6),
         human("quality.review-product-history")), scope="entity",
    ),
)

PRODUCT_PACK = pack(
    "product", "Product interrogation",
    "Product identifiers, brands, variants, duplicates, and lifecycle questions.",
    PRODUCT_QUESTIONS,
)

__all__ = ["PRODUCT_PACK", "PRODUCT_QUESTIONS"]
