"""Conservative repair-proposal node."""

from __future__ import annotations

from typing import Any

from solutiongraph.interrogation.model import FindingSet
from solutiongraph.interrogation.repair import RepairProposalEngine


def propose_repairs_node(
    records: list[dict[str, Any]],
    finding_set: dict[str, Any],
    repair_strategy: str = "safe-only",
) -> dict[str, Any]:
    proposal = RepairProposalEngine().propose(
        records,
        FindingSet.from_dict(finding_set),
        strategy=repair_strategy,
    )
    return proposal.to_dict()


__all__ = ["propose_repairs_node"]
