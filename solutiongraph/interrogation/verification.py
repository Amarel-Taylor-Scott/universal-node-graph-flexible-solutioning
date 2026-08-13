"""Independent shadow verification for proposed data repairs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from solutiongraph.executor import callable_implementation_digest
from solutiongraph.interrogation.model import (
    DatasetProfile,
    Finding,
    FindingSet,
    QuestionPlan,
    RepairApplicationReceipt,
    RepairProposal,
    SemanticFieldMap,
    VerificationReceipt,
)
from solutiongraph.model import canonical_json


def rebind_plan(
    plan: QuestionPlan,
    profile: DatasetProfile,
    field_map: SemanticFieldMap,
) -> QuestionPlan:
    """Bind the same visible question decisions to a repaired shadow profile.

    Verification intentionally reruns the original selected checks.  It does
    not silently re-plan a smaller or easier suite after seeing the repair.
    """
    if profile.dataset_digest != field_map.dataset_digest:
        raise ValueError("profile and semantic field map identify different datasets")
    rebound = QuestionPlan(
        dataset_profile_digest=profile.digest,
        semantic_field_map_digest=field_map.digest,
        question_pack_digests=plan.question_pack_digests,
        budget=plan.budget,
        items=plan.items,
        planner_id="planner.verification-rebind",
        planner_version="1.0.0",
        historical_revision=plan.historical_revision,
        warnings=(
            *plan.warnings,
            "Selected checks were preserved from the source plan for independent shadow verification.",
        ),
    )
    problems = rebound.validate()
    if problems:
        raise ValueError("invalid rebound verification plan: " + "; ".join(problems))
    return rebound


def _finding_signature(finding: Finding) -> tuple[str, str, tuple[str, ...]]:
    """Return a dataset-independent identity for before/after comparison."""
    return finding.question_id, finding.code, tuple(sorted(finding.fields))


def _changed_targets(
    before: Sequence[Mapping[str, Any]],
    after: Sequence[Mapping[str, Any]],
) -> tuple[set[tuple[int, str]], int]:
    if len(before) != len(after):
        return {(-1, "__row-count__")}, 0
    changed: set[tuple[int, str]] = set()
    unchanged = 0
    for index, (left, right) in enumerate(zip(before, after, strict=True)):
        for field in set(left) | set(right):
            left_present = field in left
            right_present = field in right
            if left_present == right_present and (
                not left_present or canonical_json(left[field]) == canonical_json(right[field])
            ):
                unchanged += 1
            else:
                changed.add((index, field))
    return changed, unchanged


def verify_repair(
    source_records: Sequence[Mapping[str, Any]],
    shadow_records: Sequence[Mapping[str, Any]],
    proposal: RepairProposal,
    application: RepairApplicationReceipt,
    before_findings: FindingSet,
    after_findings: FindingSet,
    *,
    strict: bool = True,
) -> VerificationReceipt:
    """Compare source and shadow evidence and fail closed on unexplained change."""
    if application.proposal_digest != proposal.digest:
        raise ValueError("application receipt does not identify the proposal")
    if before_findings.digest != proposal.finding_set_digest:
        raise ValueError("proposal does not identify the before finding set")
    if before_findings.dataset_digest != proposal.dataset_digest:
        raise ValueError("proposal does not identify the source dataset")
    if after_findings.dataset_digest != application.output_dataset_digest:
        raise ValueError("after findings do not identify the applied shadow dataset")

    before_by_signature = {
        _finding_signature(finding): finding for finding in before_findings.findings
    }
    after_by_signature = {
        _finding_signature(finding): finding for finding in after_findings.findings
    }
    before_signatures = set(before_by_signature)
    after_signatures = set(after_by_signature)
    resolved = tuple(
        before_by_signature[key].id for key in sorted(before_signatures - after_signatures)
    )
    remaining = tuple(
        after_by_signature[key].id for key in sorted(before_signatures & after_signatures)
    )
    introduced = tuple(
        after_by_signature[key].id for key in sorted(after_signatures - before_signatures)
    )

    changed, unchanged = _changed_targets(source_records, shadow_records)
    applied_ids = set(application.applied_operation_ids)
    applied_operations = tuple(
        operation for operation in proposal.operations if operation.id in applied_ids
    )
    declared_targets = {(item.row_index, item.field_name) for item in applied_operations}
    unexplained = sorted(changed - declared_targets)
    declared_but_unchanged = sorted(declared_targets - changed)
    introduced_severities = {
        after_by_signature[key].severity for key in after_signatures - before_signatures
    }
    remaining_severities = {
        after_by_signature[key].severity for key in before_signatures & after_signatures
    }

    reasons: list[str] = []
    if resolved:
        reasons.append(f"{len(resolved)} finding signatures resolved")
    if remaining:
        reasons.append(f"{len(remaining)} finding signatures remain")
    if introduced:
        reasons.append(f"{len(introduced)} finding signatures were introduced")
    if unexplained:
        reasons.append(f"{len(unexplained)} changed cells were not declared by the proposal")
    if declared_but_unchanged:
        reasons.append(
            f"{len(declared_but_unchanged)} applied operation targets did not change value"
        )
    if application.errors:
        reasons.append(f"application recorded {len(application.errors)} errors")

    if application.status in ("failed", "partial") or unexplained:
        decision = "reject"
    elif any(not operation.safe_to_auto_apply for operation in applied_operations):
        decision = "quarantine"
        reasons.append("review-only operations require explicit approval")
    elif {"critical", "high"} & introduced_severities:
        decision = "reject"
        reasons.append("a high-severity finding was introduced")
    elif application.status == "no-change" or not applied_operations:
        decision = "no-change"
    elif strict and introduced:
        decision = "quarantine"
        reasons.append("strict verification quarantines any newly introduced finding")
    elif strict and {"critical", "high"} & remaining_severities:
        decision = "quarantine"
        reasons.append("a high-severity source finding remains")
    elif not resolved:
        decision = "quarantine"
        reasons.append("the repair changed data without resolving a finding signature")
    else:
        decision = "promote"
        reasons.append("declared reversible changes improved the rerun check evidence")

    verifier_digest = callable_implementation_digest(verify_repair)
    receipt = VerificationReceipt(
        id=(
            "verification."
            + application.digest.removeprefix("sha256:")[:24]
            + (".strict" if strict else ".balanced")
        ),
        proposal_digest=proposal.digest,
        application_receipt_digest=application.digest,
        before_finding_set_digest=before_findings.digest,
        after_finding_set_digest=after_findings.digest,
        verifier_id="verifier.independent-shadow-diff",
        verifier_version="1.0.0",
        verifier_digest=verifier_digest,
        independence="independence.separate-controller",
        resolved_finding_ids=resolved,
        remaining_finding_ids=remaining,
        introduced_finding_ids=introduced,
        unchanged_field_count=unchanged,
        decision=decision,
        reasons=tuple(reasons) or ("no finding or data change was observed",),
    )
    problems = receipt.validate()
    if problems:
        raise ValueError("invalid verification receipt: " + "; ".join(problems))
    return receipt


__all__ = ["rebind_plan", "verify_repair"]
