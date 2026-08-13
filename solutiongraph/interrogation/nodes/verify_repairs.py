"""Independent repair-verification node."""

from __future__ import annotations

from typing import Any

from solutiongraph.interrogation.model import (
    FindingSet,
    RepairApplicationReceipt,
    RepairProposal,
)
from solutiongraph.interrogation.verification import verify_repair


def verify_repairs_node(
    source_records: list[dict[str, Any]],
    shadow_records: list[dict[str, Any]],
    repair_proposal: dict[str, Any],
    application_receipt: dict[str, Any],
    before_findings: dict[str, Any],
    after_findings: dict[str, Any],
    strict: bool = True,
) -> dict[str, Any]:
    receipt = verify_repair(
        source_records,
        shadow_records,
        RepairProposal.from_dict(repair_proposal),
        RepairApplicationReceipt.from_dict(application_receipt),
        FindingSet.from_dict(before_findings),
        FindingSet.from_dict(after_findings),
        strict=strict,
    )
    return receipt.to_dict()


__all__ = ["verify_repairs_node"]
