"""Atomic estimation implementations for the control/mutation quickstart."""

from __future__ import annotations

from copy import deepcopy
from statistics import fmean, median
from typing import Any


def estimate_mean(payload: dict[str, Any]) -> dict[str, Any]:
    """Estimate the center with the arithmetic mean."""

    result = deepcopy(payload)
    result["estimate"] = fmean(float(value) for value in result["values"])
    result.setdefault("methods", []).append("estimate.mean")
    return result


def estimate_median(payload: dict[str, Any]) -> dict[str, Any]:
    """Estimate the center with the median."""

    result = deepcopy(payload)
    result["estimate"] = float(median(float(value) for value in result["values"]))
    result.setdefault("methods", []).append("estimate.median")
    return result


__all__ = ["estimate_mean", "estimate_median"]
