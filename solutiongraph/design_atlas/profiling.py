"""Aggregate-only adapters from semantic dataset profiles to design context."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from solutiongraph.design_atlas.archetypes import normalize_task_type
from solutiongraph.design_atlas.model import DesignContext
from solutiongraph.interrogation.model import DatasetProfile, SemanticFieldMap
from solutiongraph.interrogation.profiling import map_semantic_fields, profile_records
from solutiongraph.question_packs import REFERENCE_CONCEPTS

TIME_CONCEPTS = (
    "concept.time.instant",
    "concept.time.date",
    "concept.time.start",
    "concept.time.end",
)
GEO_CONCEPTS = (
    "concept.postal.address",
    "concept.postal.street",
    "concept.postal.city",
    "concept.postal.region",
    "concept.postal.code",
    "concept.postal.country",
    "concept.geography.county",
    "concept.geography.latitude",
    "concept.geography.longitude",
)


def context_from_profile(
    profile: DatasetProfile,
    field_map: SemanticFieldMap,
    *,
    task_type: str,
    objective: str,
    target_name: str = "",
    group_field: str = "",
    entity_field: str = "",
    lifecycle_stage: str = "lifecycle.prototype",
    risk_tier: str = "risk.medium",
    modalities: Sequence[str] = (),
    signals: Sequence[str] = (),
    constraints: Sequence[str] = (),
) -> DesignContext:
    """Derive safe aggregate signals; do not infer business truth from them."""
    profile_problems = profile.validate()
    map_problems = field_map.validate()
    if profile_problems or map_problems:
        raise ValueError(
            "invalid aggregate profile or semantic map: "
            + "; ".join((*profile_problems, *map_problems))
        )
    if profile.dataset_digest != field_map.dataset_digest:
        raise ValueError("profile and semantic map must describe the same dataset")

    derived = set(signals)
    derived_modalities = {"modality.tabular", *modalities}
    if any(field.missing_fraction > 0.0 for field in profile.fields):
        derived.add("signal.missing-values")
    if any(field.missing_fraction >= 0.2 for field in profile.fields):
        derived.add("signal.high-missingness")
    if profile.duplicate_row_count:
        derived.add("signal.duplicate-rows")
    if profile.column_names and (
        len(profile.column_names) >= 100
        or (profile.row_count > 0 and len(profile.column_names) / profile.row_count >= 0.2)
    ):
        derived.add("signal.wide-table")
    if any(
        field.non_missing_count > 0
        and field.distinct_count / field.non_missing_count >= 0.8
        for field in profile.fields
    ):
        derived.add("signal.high-cardinality")

    concepts = field_map.concepts
    time_fields = field_map.fields_for(TIME_CONCEPTS)
    geo_fields = field_map.fields_for(GEO_CONCEPTS)
    if time_fields:
        derived.add("signal.time-aware")
        derived_modalities.add("modality.time-series")
    if geo_fields or any(concept.startswith(("concept.geography.", "concept.postal.")) for concept in concepts):
        derived.add("signal.geospatial")
        derived_modalities.add("modality.geospatial")
    mapped_targets = field_map.fields_for(("concept.ml.target",))
    resolved_target = target_name or (mapped_targets[0] if mapped_targets else "")
    if resolved_target:
        derived.add("signal.supervised")

    return DesignContext(
        id=f"context.profile.{profile.digest.removeprefix('sha256:')[:16]}",
        task_type=normalize_task_type(task_type),
        objective=objective,
        modalities=tuple(sorted(derived_modalities)),
        lifecycle_stage=lifecycle_stage,
        risk_tier=risk_tier,
        signals=tuple(sorted(derived)),
        constraints=tuple(sorted(set(constraints))),
        row_count=profile.row_count,
        column_count=len(profile.column_names),
        target_name=resolved_target,
        time_field=time_fields[0] if time_fields else "",
        group_field=group_field,
        entity_field=entity_field,
        dataset_profile_digest=profile.digest,
        semantic_map_digest=field_map.digest,
    )


def context_from_records(
    records: Sequence[dict[str, Any]],
    *,
    task_type: str,
    objective: str,
    mapping_strategy: str = "conservative",
    source_id: str = "source.design-atlas-dataset",
    **context_options: Any,
) -> tuple[DesignContext, DatasetProfile, SemanticFieldMap]:
    """Profile records once and return the context plus its exact aggregate evidence."""
    profile = profile_records(records, source_id=source_id)
    field_map = map_semantic_fields(
        profile,
        REFERENCE_CONCEPTS,
        strategy=mapping_strategy,
    )
    context = context_from_profile(
        profile,
        field_map,
        task_type=task_type,
        objective=objective,
        **context_options,
    )
    return context, profile, field_map


__all__ = ["context_from_profile", "context_from_records"]
