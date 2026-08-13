"""Postal-address and address-component interrogation questions."""

from __future__ import annotations

from solutiongraph.question_packs.base import deterministic, external, human, llm, pack, q
from solutiongraph.question_packs.concepts import CENSUS_GEOCODER, SCHEMA_ORG, USPS_PUB28

ADDRESS = (
    "concept.postal.address", "concept.postal.street", "concept.postal.unit",
    "concept.postal.city", "concept.postal.region", "concept.postal.code",
    "concept.postal.country",
)

POSTAL_ADDRESS_QUESTIONS = (
    q(
        "postal-address", "address-role", "Address role and purpose",
        "Is each address explicitly identified as physical, mailing, legal, billing, registered-agent, or operating?",
        ADDRESS, "postal.address-role-ambiguous", "medium",
        (deterministic("quality.address-role-check"), llm("quality.adjudicate-address-role")),
        scope="entity", references=(SCHEMA_ORG,),
    ),
    q(
        "postal-address", "required-components", "Country-aware address components",
        "Are required address components present for the declared country and address role?",
        ADDRESS, "postal.required-component-missing", "high",
        (deterministic("quality.address-component-check"),), scope="row",
        preconditions=("precondition.records-available", "precondition.address-available"),
        repairs=("repair.quarantine-record",),
    ),
    q(
        "postal-address", "placeholder-values", "Address placeholders",
        "Do address components contain test, unknown, repeated, or otherwise non-address placeholder values?",
        ADDRESS, "postal.placeholder-value", "high",
        (deterministic("quality.placeholder-check"),), scope="row",
        repairs=("repair.normalize-missing", "repair.quarantine-record"),
    ),
    q(
        "postal-address", "postal-format", "Country-aware postal-code format",
        "Does each postal code have a plausible format for its declared country without claiming deliverability?",
        ("concept.postal.code", "concept.postal.country"),
        "postal.postal-code-format", "high",
        (deterministic("quality.postal-format-check"),), scope="row",
        preconditions=("precondition.records-available", "precondition.postal-code-available"),
    ),
    q(
        "postal-address", "region-code", "Region and country code consistency",
        "Are state, province, region, and country codes syntactically valid and mutually consistent?",
        ("concept.postal.region", "concept.postal.country"),
        "postal.region-code-conflict", "high",
        (deterministic("quality.region-country-check"),), scope="cross-field",
        repairs=("repair.uppercase-region-code",),
    ),
    q(
        "postal-address", "delivery-line", "Delivery-line standardization",
        "Do US delivery lines use recognizable street suffixes and secondary-unit designators while preserving source values?",
        ("concept.postal.street", "concept.postal.unit"),
        "postal.delivery-line-nonstandard", "medium",
        (deterministic("quality.usps-delivery-line-check", cost_tier=2),),
        jurisdictions=("US",), references=(USPS_PUB28,),
        repairs=("repair.address-comparison-key",),
    ),
    q(
        "postal-address", "po-box-mixing", "PO Box and physical-line mixing",
        "Are PO Box, rural route, highway contract route, and physical delivery lines represented without contradictory mixing?",
        ("concept.postal.street", "concept.postal.unit"),
        "postal.delivery-mode-conflict", "medium",
        (deterministic("quality.po-box-mix-check"),), scope="row",
        jurisdictions=("US",), references=(USPS_PUB28,),
    ),
    q(
        "postal-address", "city-region-postal", "City, region, and postal relationship",
        "Do locality, region, postal code, and country agree according to a declared reference vintage?",
        ("concept.postal.city", "concept.postal.region", "concept.postal.code", "concept.postal.country"),
        "postal.locality-region-postal-conflict", "high",
        (external("authority.postal-geography-lookup", cost_tier=5),
         human("quality.review-postal-geography")), scope="cross-field",
        abstain=("reference dataset or vintage is unavailable",),
        references=(CENSUS_GEOCODER,),
    ),
    q(
        "postal-address", "geocode-evidence", "Geocode match semantics",
        "Is the geocode match type recorded, and is an interpolated range or centroid being mistaken for rooftop or deliverability proof?",
        ("concept.postal.address", "concept.geography.latitude", "concept.geography.longitude"),
        "postal.geocode-evidence-overclaim", "high",
        (external("authority.census-geocode", cost_tier=5),
         llm("quality.audit-geocode-claim")), scope="entity",
        preconditions=("precondition.records-available", "precondition.address-available"),
        references=(CENSUS_GEOCODER,),
    ),
    q(
        "postal-address", "shared-address", "Suspicious shared addresses",
        "Are implausibly many unrelated entities sharing one normalized address or unit?",
        ADDRESS, "postal.suspicious-shared-address", "medium",
        (deterministic("quality.shared-address-check", cost_tier=3),
         llm("quality.interpret-shared-address-clusters")), scope="dataset",
        repairs=("repair.quarantine-duplicate",),
    ),
)

POSTAL_ADDRESS_PACK = pack(
    "postal-address",
    "Postal address interrogation",
    "Country-aware address structure, USPS-style normalization, GIS evidence, and shared-address questions.",
    POSTAL_ADDRESS_QUESTIONS,
)

__all__ = ["POSTAL_ADDRESS_PACK", "POSTAL_ADDRESS_QUESTIONS"]
