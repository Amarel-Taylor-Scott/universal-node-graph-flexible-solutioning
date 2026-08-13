"""Reversible shadow-application node."""

from __future__ import annotations

from typing import Any

from solutiongraph.interrogation.model import RepairProposal
from solutiongraph.interrogation.repair import apply_repair_shadow


def apply_shadow_node(
    records: list[dict[str, Any]],
    repair_proposal: dict[str, Any],
    include_review_operations: bool = False,
) -> dict[str, Any]:
    shadow, receipt = apply_repair_shadow(
        records,
        RepairProposal.from_dict(repair_proposal),
        include_review_operations=include_review_operations,
    )
    return {"shadow_records": shadow, "application_receipt": receipt.to_dict()}


__all__ = ["apply_shadow_node"]
