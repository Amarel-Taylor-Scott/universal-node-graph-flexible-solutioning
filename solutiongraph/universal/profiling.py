"""Domain-neutral task fingerprint channels for universal design planning."""

from __future__ import annotations

from typing import Any

from solutiongraph.intelligence import FingerprintAttribute
from solutiongraph.model import sha256_digest
from solutiongraph.task_categories import (
    DEFAULT_TASK_CATEGORY_REGISTRY,
    TaskCategoryRegistry,
)
from solutiongraph.tasking import TaskContract
from solutiongraph.universal.catalog import DOMAIN_PACK_BY_ID
from solutiongraph.universal.model import FingerprintChannel, UniversalDesignContext


def _objective(objective: Any) -> dict[str, Any]:
    return {
        "metric": objective.metric,
        "direction": objective.direction,
        "weight": objective.weight,
        "hard_minimum": objective.hard_minimum,
        "hard_maximum": objective.hard_maximum,
    }


def context_from_task(
    contract: TaskContract,
    *,
    domain_pack_ids: tuple[str, ...],
    category_registry: TaskCategoryRegistry = DEFAULT_TASK_CATEGORY_REGISTRY,
) -> UniversalDesignContext:
    """Project a task contract into ten independent, domain-neutral channels."""

    problems = list(contract.validate())
    if not domain_pack_ids:
        problems.append("at least one domain pack is required")
    unknown_domains = sorted(set(domain_pack_ids) - set(DOMAIN_PACK_BY_ID))
    if unknown_domains:
        problems.append("unknown domain packs: " + ", ".join(unknown_domains))
    if problems:
        raise ValueError("invalid universal design context input: " + "; ".join(problems))

    domain_packs = tuple(DOMAIN_PACK_BY_ID[item] for item in domain_pack_ids)
    obligations = tuple(
        dict.fromkeys(
            obligation
            for pack in domain_packs
            for obligation in pack.required_obligation_ids
        )
    )
    category_matches = category_registry.classify(contract, limit=None)
    category_ids = tuple(item.category_id for item in category_matches)
    temporal_signals = tuple(
        item
        for item in category_ids
        if any(token in item for token in ("temporal", "forecast", "stream", "event"))
    )
    interface_inputs = tuple(port.to_dict() for port in contract.inputs)
    interface_outputs = tuple(port.to_dict() for port in contract.outputs)
    channels = (
        FingerprintChannel(
            "fingerprint.outcome",
            (
                ("outcome.success-contract-digest", sha256_digest(contract.success_contract)),
                ("outcome.objectives", tuple(_objective(item) for item in contract.objectives)),
                (
                    "outcome.constraints",
                    tuple(item.to_dict() for item in contract.constraints),
                ),
                ("outcome.output-count", len(contract.outputs)),
            ),
        ),
        FingerprintChannel(
            "fingerprint.interface",
            (
                ("interface.inputs", interface_inputs),
                ("interface.outputs", interface_outputs),
                (
                    "interface.schema-digests",
                    tuple(
                        port.value_type.schema_digest
                        for port in (*contract.inputs, *contract.outputs)
                        if port.value_type.schema_digest
                    ),
                ),
            ),
        ),
        FingerprintChannel(
            "fingerprint.workload",
            (
                ("workload.case-count", len(contract.case_ids)),
                ("workload.case-ids", contract.case_ids),
                ("workload.external-requirement-count", len(contract.external_requirements)),
            ),
        ),
        FingerprintChannel(
            "fingerprint.topology",
            (
                ("topology.domain-pack-ids", domain_pack_ids),
                ("topology.obligation-ids", obligations),
                ("topology.category-ids", category_ids),
            ),
            evidence_kind="evidence.inferred",
            confidence=max((item.score for item in category_matches), default=0.0),
        ),
        FingerprintChannel(
            "fingerprint.effects",
            (
                ("effects.allowed", contract.allowed_effects),
                ("effects.permissions", contract.granted_permissions),
                ("effects.effect-count", len(contract.allowed_effects)),
            ),
        ),
        FingerprintChannel(
            "fingerprint.temporal",
            (
                ("temporal.category-signals", temporal_signals),
                ("temporal.explicit", bool(temporal_signals)),
            ),
            evidence_kind="evidence.inferred",
            confidence=1.0 if temporal_signals else 0.5,
        ),
        FingerprintChannel(
            "fingerprint.risk",
            (
                ("risk.oracle-kind", contract.oracle.kind),
                ("risk.oracle-independence", contract.oracle.independence),
                ("risk.oracle-candidate-readable", contract.oracle.candidate_readable),
                ("risk.hard-constraint-count", len(contract.constraints)),
                ("risk.permission-count", len(contract.granted_permissions)),
            ),
        ),
        FingerprintChannel(
            "fingerprint.environment",
            (
                ("environment.external-requirements", contract.external_requirements),
                (
                    "environment.media-types",
                    tuple(
                        sorted(
                            {
                                port.value_type.media_type
                                for port in (*contract.inputs, *contract.outputs)
                            }
                        )
                    ),
                ),
            ),
        ),
        FingerprintChannel(
            "fingerprint.evidence",
            (
                ("evidence.oracle-id", contract.oracle.id),
                ("evidence.oracle-digest", contract.oracle.evaluator_digest),
                ("evidence.case-ids", contract.case_ids),
            ),
        ),
        FingerprintChannel(
            "fingerprint.semantics",
            (
                ("semantics.title", contract.title),
                ("semantics.intent", contract.intent),
                ("semantics.tags", contract.tags),
                ("semantics.task-id", contract.id),
            ),
        ),
    )
    identity = {
        "task": contract.digest,
        "domains": domain_pack_ids,
        "obligations": obligations,
        "channels": [item.to_dict() for item in channels],
    }
    context = UniversalDesignContext(
        id="universal-context."
        + sha256_digest(identity).removeprefix("sha256:")[:20],
        task_contract_digest=contract.digest,
        task_id=contract.id,
        domain_pack_ids=domain_pack_ids,
        obligation_ids=obligations,
        channels=channels,
    )
    context_problems = context.validate()
    if context_problems:
        raise ValueError("invalid universal design context: " + "; ".join(context_problems))
    return context


def fingerprint_attributes_from_context(
    context: UniversalDesignContext,
) -> tuple[FingerprintAttribute, ...]:
    """Create privacy-conservative historical-search attributes per channel.

    The attributes preserve each channel's digest and field names.  Raw values
    stay in the separately governed context instead of being copied into every
    historical-memory record.
    """

    problems = context.validate()
    if problems:
        raise ValueError("invalid universal design context: " + "; ".join(problems))
    return tuple(
        FingerprintAttribute(
            key=f"universal.{channel.id.removeprefix('fingerprint.')}",
            value={
                "digest": sha256_digest(channel.to_dict()),
                "fields": tuple(key for key, _ in channel.values),
            },
            evidence_kind=channel.evidence_kind,
            confidence=channel.confidence,
            source=context.id,
        )
        for channel in context.channels
    )


__all__ = ["context_from_task", "fingerprint_attributes_from_context"]
