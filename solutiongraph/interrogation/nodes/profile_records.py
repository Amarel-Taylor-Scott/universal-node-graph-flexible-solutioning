"""Aggregate-only record profiling node."""

from __future__ import annotations

from typing import Any

from solutiongraph.interrogation.profiling import profile_records


def profile_records_node(
    records: list[dict[str, Any]],
    sample_limit: int = 0,
) -> dict[str, Any]:
    portable = [dict(record) for record in records]
    profile = profile_records(
        portable,
        source_id="source.graph-records",
        sample_limit=sample_limit,
    )
    return {"records": portable, "profile": profile.to_dict()}


__all__ = ["profile_records_node"]
