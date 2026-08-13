"""Conservative repair proposal, shadow application, and reversal."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from typing import Any

from solutiongraph.interrogation.model import (
    Finding,
    FindingSet,
    PatchOperation,
    RepairApplicationReceipt,
    RepairProposal,
)
from solutiongraph.interrogation.profiling import records_digest
from solutiongraph.model import sha256_digest


def _row_id(index: int, record: Mapping[str, Any]) -> str:
    explicit = next(
        (record[key] for key in ("record_id", "row_id", "id") if key in record),
        None,
    )
    identity = {"index": index, "explicit": explicit, "record": dict(record)}
    return "row." + sha256_digest(identity).removeprefix("sha256:")


def _operation_id(
    finding_id: str,
    row_index: int,
    field_name: str,
    action: str,
    after_value: Any,
) -> str:
    digest = sha256_digest(
        {
            "finding_id": finding_id,
            "row_index": row_index,
            "field_name": field_name,
            "action": action,
            "after_value": after_value,
        }
    ).removeprefix("sha256:")
    return "patch." + digest


def _organization_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    suffixes = {
        "inc", "incorporated", "corp", "corporation", "co", "company", "llc", "llp",
        "lp", "ltd", "limited", "plc", "gmbh", "ag", "sa", "bv", "nv", "pte", "pty",
    }
    tokens = re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", value).casefold())
    while tokens and tokens[-1] in suffixes:
        tokens.pop()
    return " ".join(tokens)


def _safe_iso(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}", text):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("/", "-"))
    except ValueError:
        return None
    return parsed.isoformat()


class RepairProposalEngine:
    """Generate patches without silently rewriting authoritative source fields."""

    id = "repairer.conservative-data-patches"
    version = "1.0.0"

    def propose(
        self,
        records: Sequence[Mapping[str, Any]],
        finding_set: FindingSet,
        *,
        strategy: str = "safe-only",
    ) -> RepairProposal:
        if strategy not in ("safe-only", "safe-and-review"):
            raise ValueError("strategy must be safe-only or safe-and-review")
        dataset_digest = records_digest(records)
        if dataset_digest != finding_set.dataset_digest:
            raise ValueError("records do not match the finding set dataset")
        row_lookup = {_row_id(index, record): index for index, record in enumerate(records)}
        operations: list[PatchOperation] = []
        seen_targets: set[tuple[int, str]] = set()
        for finding in finding_set.findings:
            operations.extend(
                self._operations_for_finding(
                    records,
                    finding,
                    row_lookup,
                    include_review=strategy == "safe-and-review",
                    seen_targets=seen_targets,
                )
            )
        families = tuple(
            dict.fromkeys(
                family
                for finding in finding_set.findings
                for family in finding.remediation_families
            )
        )
        result = RepairProposal(
            dataset_digest=dataset_digest,
            finding_set_digest=finding_set.digest,
            repair_family=families[0] if len(families) == 1 else "repair.mixed",
            strategy=f"repair-strategy.{strategy}",
            operations=tuple(operations),
            proposer_id=self.id,
            proposer_version=self.version,
            requires_approval=any(not item.safe_to_auto_apply for item in operations),
            notes=(
                "Source records are never mutated in place; this proposal is applied only to a shadow copy.",
                "Legal names are preserved; organization normalization creates a separate comparison key.",
            ),
        )
        problems = result.validate()
        if problems:
            raise ValueError("invalid repair proposal: " + "; ".join(problems))
        return result

    def _operations_for_finding(
        self,
        records: Sequence[Mapping[str, Any]],
        finding: Finding,
        row_lookup: Mapping[str, int],
        *,
        include_review: bool,
        seen_targets: set[tuple[int, str]],
    ) -> list[PatchOperation]:
        operations: list[PatchOperation] = []
        row_ids = finding.row_ids
        if not row_ids and finding.affected_count and records:
            row_ids = (_row_id(0, records[0]),)
        for row_id in row_ids:
            if row_id not in row_lookup:
                continue
            row_index = row_lookup[row_id]
            record = records[row_index]
            for field in finding.fields:
                if field.startswith("__") or field not in record:
                    continue
                before = record[field]
                after = before
                action = "replace"
                safe = False
                reason = ""
                if finding.code.endswith("whitespace-anomaly") and isinstance(before, str):
                    after = re.sub(r"[ \t]{2,}", " ", before.strip())
                    safe = after != before
                    reason = "Trim edge whitespace and collapse repeated horizontal spaces."
                elif finding.code in (
                    "data.unicode-or-control",
                    "organization.name-punctuation",
                    "person.name-script-anomaly",
                ) and isinstance(before, str):
                    after = "".join(
                        character
                        for character in unicodedata.normalize("NFC", before)
                        if not (
                            unicodedata.category(character).startswith("C")
                            and character not in "\n\r\t"
                        )
                    )
                    safe = after != before
                    reason = "Apply canonical NFC and remove non-printing controls."
                elif finding.code == "contact.email-syntax" and isinstance(before, str):
                    candidate = before.strip()
                    if "@" in candidate:
                        local, domain = candidate.rsplit("@", 1)
                        after = local + "@" + domain.casefold().rstrip(".")
                        safe = bool(re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", after)) and after != before
                        reason = "Trim the address and case-fold only the domain portion."
                elif finding.code == "contact.phone-format" and isinstance(before, str):
                    extension = re.search(r"(?:x|ext)\s*(\d+)$", before, re.I)
                    base = re.split(r"(?:x|ext)\s*\d+$", before, flags=re.I)[0]
                    digits = re.sub(r"\D", "", base)
                    if before.strip().startswith("+") and 7 <= len(digits) <= 15:
                        after = "+" + digits + (f" x{extension.group(1)}" if extension else "")
                        safe = after != before
                        reason = "Normalize an already explicit international number without inferring country."
                elif finding.code == "postal.region-code-conflict" and isinstance(before, str):
                    candidate = before.strip().upper()
                    if re.fullmatch(r"[A-Z]{2,3}", candidate):
                        after = candidate
                        safe = after != before
                        reason = "Normalize case only; no jurisdiction is inferred."
                elif finding.code == "datetime.unparseable-or-ambiguous":
                    candidate = _safe_iso(before)
                    if candidate is not None:
                        after = candidate
                        safe = after != before
                        reason = "Convert an unambiguous year-first value to ISO 8601."
                elif finding.code == "organization.legal-form-mismatch":
                    key = _organization_key(before)
                    target = field + "__comparison_key"
                    if key and target not in record:
                        field = target
                        before = None
                        after = key
                        action = "add"
                        safe = True
                        reason = "Add a conservative comparison key while preserving the legal name."
                if safe and after != before:
                    target = (row_index, field)
                    if target in seen_targets:
                        continue
                    seen_targets.add(target)
                    operations.append(
                        PatchOperation(
                            id=_operation_id(finding.id, row_index, field, action, after),
                            finding_id=finding.id,
                            row_id=row_id,
                            row_index=row_index,
                            field_name=field,
                            action=action,
                            before_digest=sha256_digest(before),
                            before_value=before,
                            after_value=after,
                            safe_to_auto_apply=True,
                            reason=reason,
                        )
                    )
            if include_review and not any(item.finding_id == finding.id for item in operations):
                review_field = finding.fields[0] if finding.fields else "__record__"
                target = (row_index, "_solutiongraph_review")
                if target in seen_targets:
                    continue
                seen_targets.add(target)
                before = record.get("_solutiongraph_review")
                after = {
                    "finding_id": finding.id,
                    "code": finding.code,
                    "severity": finding.severity,
                }
                operations.append(
                    PatchOperation(
                        id=_operation_id(finding.id, row_index, review_field, "quarantine", after),
                        finding_id=finding.id,
                        row_id=row_id,
                        row_index=row_index,
                        field_name="_solutiongraph_review",
                        action="quarantine",
                        before_digest=sha256_digest(before),
                        before_value=before,
                        after_value=after,
                        safe_to_auto_apply=False,
                        reason="Retain the record in a review queue; do not guess a correction.",
                    )
                )
        return operations


def apply_repair_shadow(
    records: Sequence[Mapping[str, Any]],
    proposal: RepairProposal,
    *,
    include_review_operations: bool = False,
) -> tuple[list[dict[str, Any]], RepairApplicationReceipt]:
    """Apply validated operations to a deep shadow copy and retain exact receipt identity."""
    input_digest = records_digest(records)
    if input_digest != proposal.dataset_digest:
        raise ValueError("repair proposal does not identify these input records")
    shadow: list[dict[str, Any]] = deepcopy([dict(record) for record in records])
    applied: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []
    for operation in proposal.operations:
        if not operation.safe_to_auto_apply and not include_review_operations:
            skipped.append(operation.id)
            continue
        if operation.row_index >= len(shadow):
            skipped.append(operation.id)
            errors.append(f"{operation.id}: row index is unavailable")
            continue
        record = shadow[operation.row_index]
        current = record.get(operation.field_name)
        if sha256_digest(current) != operation.before_digest:
            skipped.append(operation.id)
            errors.append(f"{operation.id}: before-value digest mismatch")
            continue
        if operation.action in ("add", "replace", "quarantine"):
            record[operation.field_name] = deepcopy(operation.after_value)
        elif operation.action == "remove":
            record.pop(operation.field_name, None)
        else:  # model validation should make this unreachable
            skipped.append(operation.id)
            errors.append(f"{operation.id}: unsupported action")
            continue
        applied.append(operation.id)
    output_digest = records_digest(shadow)
    if errors and applied:
        status = "partial"
    elif errors:
        status = "failed"
    elif not applied:
        status = "no-change"
    else:
        status = "applied"
    receipt = RepairApplicationReceipt(
        id="repair-application." + proposal.digest.removeprefix("sha256:"),
        proposal_digest=proposal.digest,
        input_dataset_digest=input_digest,
        output_dataset_digest=output_digest,
        applied_operation_ids=tuple(applied),
        skipped_operation_ids=tuple(skipped),
        status=status,
        errors=tuple(errors),
    )
    problems = receipt.validate()
    if problems:
        raise ValueError("invalid repair application receipt: " + "; ".join(problems))
    return shadow, receipt


def reverse_repair_shadow(
    shadow_records: Sequence[Mapping[str, Any]],
    proposal: RepairProposal,
    application: RepairApplicationReceipt,
) -> list[dict[str, Any]]:
    """Reverse exactly the applied operations, failing closed on changed outputs."""
    if application.proposal_digest != proposal.digest:
        raise ValueError("application receipt does not identify the repair proposal")
    if records_digest(shadow_records) != application.output_dataset_digest:
        raise ValueError("shadow records changed after the recorded application")
    restored: list[dict[str, Any]] = deepcopy([dict(record) for record in shadow_records])
    by_id = {operation.id: operation for operation in proposal.operations}
    for operation_id in reversed(application.applied_operation_ids):
        operation = by_id[operation_id]
        record = restored[operation.row_index]
        if operation.action == "add":
            record.pop(operation.field_name, None)
        else:
            record[operation.field_name] = deepcopy(operation.before_value)
    if records_digest(restored) != application.input_dataset_digest:
        raise ValueError("reversed records do not match the original dataset digest")
    return restored


__all__ = [
    "RepairProposalEngine",
    "apply_repair_shadow",
    "reverse_repair_shadow",
]
