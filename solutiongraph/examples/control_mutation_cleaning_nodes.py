"""Atomic cleaning implementations for the control/mutation quickstart."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def preserve_values(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep the observed values unchanged as an explicit identity candidate."""

    result = deepcopy(payload)
    result.setdefault("methods", []).append("clean.preserve-values")
    return result


def clip_single_upper_outlier(payload: dict[str, Any]) -> dict[str, Any]:
    """Clip the largest value to the second-largest fixture observation."""

    result = deepcopy(payload)
    values = sorted(float(value) for value in result["values"])
    if len(values) >= 2:
        upper = values[-2]
        result["values"] = [min(float(value), upper) for value in result["values"]]
    result.setdefault("methods", []).append("clean.clip-single-upper-outlier")
    return result


__all__ = ["clip_single_upper_outlier", "preserve_values"]
