"""Portable provenance projections for immutable SolutionGraph receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from solutiongraph.evidence import RunReceipt
from solutiongraph.model import FrozenPlan, sha256_digest

PROVENANCE_MODEL_VERSION = "0.1"
REPOSITORY_URL = (
    "https://github.com/Amarel-Taylor-Scott/"
    "universal-node-graph-flexible-solutioning"
)
RAW_SCHEMA_ROOT = (
    "https://raw.githubusercontent.com/Amarel-Taylor-Scott/"
    "universal-node-graph-flexible-solutioning/main/solutiongraph/schemas"
)


def _hex(digest: str) -> str:
    return digest.removeprefix("sha256:")


def to_w3c_prov(receipt: RunReceipt, plan: FrozenPlan | None = None) -> dict[str, Any]:
    """Project one run into a compact PROV-JSON-compatible document."""
    activity_id = f"solutiongraph:run/{receipt.id}"
    plan_id = f"solutiongraph:plan/{_hex(receipt.plan_digest)}"
    entities: dict[str, Any] = {
        plan_id: {
            "prov:type": "solutiongraph:FrozenPlan",
            "solutiongraph:digest": receipt.plan_digest,
        }
    }
    for name, digest in receipt.output_artifacts:
        entities[f"solutiongraph:artifact/{_hex(digest)}"] = {
            "prov:type": "solutiongraph:Artifact",
            "solutiongraph:name": name,
            "solutiongraph:digest": digest,
        }
    activity = {
        activity_id: {
            "prov:type": "solutiongraph:GraphExecution",
            "prov:startTime": receipt.started_at,
            "prov:endTime": receipt.completed_at,
            "solutiongraph:outcome": receipt.outcome,
            "solutiongraph:programDigest": receipt.program_digest,
            "solutiongraph:environmentDigest": receipt.environment_digest,
            "solutiongraph:verifier": receipt.verifier,
            "solutiongraph:verifierDigest": receipt.verifier_digest,
        }
    }
    used = {
        f"solutiongraph:used/{receipt.id}/plan": {
            "prov:activity": activity_id,
            "prov:entity": plan_id,
        }
    }
    generated = {
        f"solutiongraph:generated/{receipt.id}/{name}": {
            "prov:entity": f"solutiongraph:artifact/{_hex(digest)}",
            "prov:activity": activity_id,
        }
        for name, digest in receipt.output_artifacts
    }
    informed: dict[str, Any] = {}
    for index, node_receipt in enumerate(receipt.node_receipts, start=1):
        node_activity_id = f"solutiongraph:node-run/{receipt.id}/{index}"
        activity[node_activity_id] = {
            "prov:type": "solutiongraph:NodeExecution",
            "prov:startTime": node_receipt.started_at,
            "prov:endTime": node_receipt.completed_at,
            "solutiongraph:slot": node_receipt.slot_id,
            "solutiongraph:candidate": node_receipt.candidate_id,
            "solutiongraph:node": node_receipt.node_id,
            "solutiongraph:outcome": node_receipt.outcome,
            "solutiongraph:attempt": node_receipt.attempt,
            "solutiongraph:implementationDigest": (
                node_receipt.implementation_digest
            ),
            "solutiongraph:runtime": node_receipt.runtime,
            "solutiongraph:runtimeAdapter": node_receipt.runtime_adapter,
            "solutiongraph:isolation": node_receipt.isolation,
            "solutiongraph:failureClass": node_receipt.failure_class,
        }
        informed[f"solutiongraph:informed/{receipt.id}/{index}"] = {
            "prov:informed": node_activity_id,
            "prov:informant": activity_id,
        }
        if node_receipt.input_digest:
            input_entity_id = (
                f"solutiongraph:node-input/{_hex(node_receipt.input_digest)}"
            )
            entities.setdefault(input_entity_id, {
                "prov:type": "solutiongraph:NodeInput",
                "solutiongraph:digest": node_receipt.input_digest,
            })
            used[f"solutiongraph:used/{receipt.id}/{index}/input"] = {
                "prov:activity": node_activity_id,
                "prov:entity": input_entity_id,
            }
        for artifact_index, digest in enumerate(
            node_receipt.artifact_digests, start=1
        ):
            artifact_id = f"solutiongraph:artifact/{_hex(digest)}"
            entities.setdefault(artifact_id, {
                "prov:type": "solutiongraph:Artifact",
                "solutiongraph:digest": digest,
            })
            generated[
                f"solutiongraph:generated/{receipt.id}/{index}/{artifact_index}"
            ] = {
                "prov:entity": artifact_id,
                "prov:activity": node_activity_id,
            }
    document: dict[str, Any] = {
        "prefix": {
            "prov": "http://www.w3.org/ns/prov#",
            "solutiongraph": "https://github.com/Amarel-Taylor-Scott/"
            "universal-node-graph-flexible-solutioning/ns/",
        },
        "entity": entities,
        "activity": activity,
        "used": used,
        "wasGeneratedBy": generated,
        "wasInformedBy": informed,
    }
    if plan is not None:
        document["entity"][plan_id]["solutiongraph:bindings"] = {
            binding.slot_id: binding.candidate_id for binding in plan.bindings
        }
    return document


def to_openlineage(
    receipt: RunReceipt,
    *,
    namespace: str = "solutiongraph",
) -> dict[str, Any]:
    """Project a receipt into an OpenLineage RunEvent with custom facets."""
    event_type = "COMPLETE" if receipt.outcome in (
        "accepted", "rejected", "completed_unverified"
    ) else "FAIL"
    run_id = str(uuid5(
        NAMESPACE_URL,
        f"{receipt.id}:{receipt.plan_digest}:{receipt.task_case_id}",
    ))
    return {
        "eventType": event_type,
        "eventTime": receipt.completed_at or receipt.started_at,
        "run": {
            "runId": run_id,
            "facets": {
                "solutiongraph_execution": {
                    "_producer": REPOSITORY_URL,
                    "_schemaURL": f"{RAW_SCHEMA_ROOT}/openlineage-execution-facet.schema.json",
                    "receiptId": receipt.id,
                    "planDigest": receipt.plan_digest,
                    "programDigest": receipt.program_digest,
                    "admittedSpaceDigest": receipt.admitted_space_digest,
                    "environmentDigest": receipt.environment_digest,
                    "inputDigest": receipt.input_digest,
                    "taskCaseId": receipt.task_case_id,
                    "seed": receipt.seed,
                    "assignments": dict(receipt.assignments),
                    "metrics": dict(receipt.metrics),
                    "verifier": receipt.verifier,
                    "verifierDigest": receipt.verifier_digest,
                    "beliefRevision": receipt.belief_revision,
                    "outcome": receipt.outcome,
                    "accepted": receipt.accepted,
                }
            },
        },
        "job": {"namespace": namespace, "name": receipt.task_case_id},
        "inputs": [],
        "outputs": [
            {
                "namespace": f"{namespace}/artifacts",
                "name": name,
                "facets": {
                    "solutiongraph_artifact": {
                        "_producer": REPOSITORY_URL,
                        "_schemaURL": f"{RAW_SCHEMA_ROOT}/openlineage-artifact-facet.schema.json",
                        "digest": digest,
                    },
                },
            }
            for name, digest in receipt.output_artifacts
        ],
        "producer": REPOSITORY_URL,
        "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json",
    }


def to_slsa_provenance(
    receipt: RunReceipt,
    *,
    builder_id: str = "https://github.com/Amarel-Taylor-Scott/"
    "universal-node-graph-flexible-solutioning/reference-executor",
) -> dict[str, Any]:
    """Project a receipt into an in-toto Statement using SLSA provenance v1."""
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": name, "digest": {"sha256": _hex(digest)}}
            for name, digest in receipt.output_artifacts
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": f"{REPOSITORY_URL}/blob/main/EXECUTION_PROTOCOL.md#required-lifecycle",
                "externalParameters": {
                    "planDigest": receipt.plan_digest,
                    "programDigest": receipt.program_digest,
                    "taskCaseId": receipt.task_case_id,
                    "seed": receipt.seed,
                },
                "internalParameters": {
                    "assignments": dict(receipt.assignments),
                    "beliefRevision": receipt.belief_revision,
                },
                "resolvedDependencies": [
                    {
                        "uri": "pkg:generic/solutiongraph-plan@"
                        f"{_hex(receipt.plan_digest)}",
                        "digest": {"sha256": _hex(receipt.plan_digest)},
                    },
                    {
                        "uri": "pkg:generic/solutiongraph-program@"
                        f"{_hex(receipt.program_digest)}",
                        "digest": {"sha256": _hex(receipt.program_digest)},
                    },
                ],
            },
            "runDetails": {
                "builder": {"id": builder_id},
                "metadata": {
                    "invocationId": receipt.id,
                    "startedOn": receipt.started_at,
                    "finishedOn": receipt.completed_at,
                },
                "byproducts": [
                    {
                        "name": "solutiongraph-run-receipt",
                        "content": receipt.to_dict(),
                    }
                ],
            },
        },
    }


@dataclass(frozen=True)
class ProvenanceBundle:
    receipt_id: str
    receipt_digest: str
    w3c_prov: dict[str, Any]
    openlineage: dict[str, Any]
    slsa_provenance: dict[str, Any]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "provenance_model_version": PROVENANCE_MODEL_VERSION,
            "receipt_id": self.receipt_id,
            "receipt_digest": self.receipt_digest,
            "w3c_prov": self.w3c_prov,
            "openlineage": self.openlineage,
            "slsa_provenance": self.slsa_provenance,
        }


def export_provenance(
    receipt: RunReceipt,
    plan: FrozenPlan | None = None,
) -> ProvenanceBundle:
    problems = receipt.validate()
    if problems:
        raise ValueError("invalid run receipt: " + "; ".join(problems))
    if plan is not None and plan.digest != receipt.plan_digest:
        raise ValueError("plan digest does not match the receipt")
    return ProvenanceBundle(
        receipt_id=receipt.id,
        receipt_digest=sha256_digest(receipt.to_dict()),
        w3c_prov=to_w3c_prov(receipt, plan),
        openlineage=to_openlineage(receipt),
        slsa_provenance=to_slsa_provenance(receipt),
    )


__all__ = [
    "PROVENANCE_MODEL_VERSION",
    "ProvenanceBundle",
    "export_provenance",
    "to_openlineage",
    "to_slsa_provenance",
    "to_w3c_prov",
]
