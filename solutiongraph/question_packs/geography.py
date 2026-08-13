"""Geographic-coordinate, boundary, vintage, and geotemporal questions."""

from __future__ import annotations

from solutiongraph.question_packs.base import deterministic, external, human, llm, pack, q
from solutiongraph.question_packs.concepts import CENSUS_GEOCODER

GEO = (
    "concept.geography.latitude", "concept.geography.longitude",
    "concept.geography.county", "concept.geography.vintage",
    "concept.postal.city", "concept.postal.region", "concept.postal.country",
)

GEOGRAPHY_QUESTIONS = (
    q(
        "geography", "coordinate-range", "Coordinate range and axis order",
        "Are latitude and longitude finite, in range, and not accidentally swapped?",
        ("concept.geography.latitude", "concept.geography.longitude"),
        "geography.invalid-coordinate", "high",
        (deterministic("quality.coordinate-range-check"),), scope="row",
        preconditions=("precondition.records-available", "precondition.coordinates-available"),
    ),
    q(
        "geography", "zero-island", "Null-island and default coordinates",
        "Do zero, repeated centroid, or other default coordinates appear more often than plausibly expected?",
        ("concept.geography.latitude", "concept.geography.longitude"),
        "geography.default-coordinate", "high",
        (deterministic("quality.default-coordinate-check", cost_tier=2),), scope="dataset",
    ),
    q(
        "geography", "point-in-polygon", "Coordinate and administrative boundary",
        "Does the point fall within the stated city, county, region, and country for the declared boundary vintage?",
        GEO, "geography.boundary-conflict", "high",
        (external("authority.point-in-polygon", cost_tier=5),
         human("quality.review-boundary-conflict")), scope="cross-field",
        preconditions=("precondition.records-available", "precondition.coordinates-available"),
        references=(CENSUS_GEOCODER,),
    ),
    q(
        "geography", "vintage", "Boundary and code vintage",
        "Are FIPS codes, county relationships, and geometries interpreted using an explicit reference vintage?",
        ("concept.geography.county", "concept.geography.vintage"),
        "geography.vintage-ambiguous", "high",
        (deterministic("quality.geography-vintage-check"),
         external("authority.geography-vintage-lookup", cost_tier=5)), scope="pipeline",
    ),
    q(
        "geography", "geocode-method", "Coordinate derivation method",
        "Is each coordinate identified as rooftop, parcel, interpolated range, centroid, or unknown?",
        ("concept.geography.latitude", "concept.geography.longitude"),
        "geography.method-missing", "medium",
        (deterministic("quality.geocode-method-check"),
         llm("quality.audit-geocode-method")), scope="entity",
    ),
    q(
        "geography", "geotemporal-enrichment", "Time-aware geographic enrichment",
        "Were events, weather, demographics, regulations, and boundaries joined using both location and event time?",
        ("concept.geography.latitude", "concept.geography.longitude", "concept.time.instant"),
        "geography.temporal-enrichment-conflict", "high",
        (deterministic("quality.geotemporal-lineage-check", cost_tier=4),
         llm("quality.audit-geotemporal-enrichment", cost_tier=7)), scope="pipeline",
        preconditions=("precondition.records-available", "precondition.coordinates-available", "precondition.event-time-available"),
    ),
)

GEOGRAPHY_PACK = pack(
    "geography", "Geography and GIS interrogation",
    "Coordinate, boundary, derivation-method, vintage, and time-aware enrichment questions.",
    GEOGRAPHY_QUESTIONS,
)

__all__ = ["GEOGRAPHY_PACK", "GEOGRAPHY_QUESTIONS"]
