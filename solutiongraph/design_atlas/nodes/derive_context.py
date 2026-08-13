"""Derive an atlas context from aggregate-only profile evidence."""

from __future__ import annotations

from typing import Any

from solutiongraph.design_atlas.profiling import context_from_profile
from solutiongraph.interrogation.model import DatasetProfile, SemanticFieldMap

_ALLOWED_REQUEST_FIELDS = frozenset({
    "task_type",
    "objective",
    "target_name",
    "group_field",
    "entity_field",
    "lifecycle_stage",
    "risk_tier",
    "modalities",
    "signals",
    "constraints",
})


def derive_context_node(
    dataset_profile: dict[str, Any],
    semantic_field_map: dict[str, Any],
    task_request: dict[str, Any],
) -> dict[str, Any]:
    """Bind declared task intent to privacy-minimized dataset characteristics."""
    if not isinstance(task_request, dict):
        raise ValueError("task_request must be an object")
    unknown = sorted(set(task_request).difference(_ALLOWED_REQUEST_FIELDS))
    if unknown:
        raise ValueError("task_request contains unsupported fields: " + ", ".join(unknown))
    missing = [
        field for field in ("task_type", "objective")
        if not isinstance(task_request.get(field), str) or not task_request[field].strip()
    ]
    if missing:
        raise ValueError("task_request requires non-empty strings: " + ", ".join(missing))
    options = dict(task_request)
    task_type = options.pop("task_type")
    objective = options.pop("objective")
    for field in (
        "target_name",
        "group_field",
        "entity_field",
        "lifecycle_stage",
        "risk_tier",
    ):
        if field in options and not isinstance(options[field], str):
            raise ValueError(f"task_request.{field} must be a string")
    for field in ("modalities", "signals", "constraints"):
        value = options.get(field, ())
        if not isinstance(value, (list, tuple)) or any(
            not isinstance(item, str) for item in value
        ):
            raise ValueError(f"task_request.{field} must be an array of strings")
        options[field] = tuple(value)
    context = context_from_profile(
        DatasetProfile.from_dict(dataset_profile),
        SemanticFieldMap.from_dict(semantic_field_map),
        task_type=task_type,
        objective=objective,
        **options,
    )
    return context.to_dict()


__all__ = ["derive_context_node"]
