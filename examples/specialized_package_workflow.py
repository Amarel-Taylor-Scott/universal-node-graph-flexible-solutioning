#!/usr/bin/env python3
"""Recommend vertical packages and compose a cross-package starting route.

This example is dependency-free and advisory: the resulting recipes still
need to be instantiated as a typed graph and pass ordinary compiler admission.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from solutiongraph.specialized import (
    REFERENCE_SPECIALIZED_PACK_REGISTRY,
    PackageCompositionRequest,
    TaskPackageRequest,
    compose_specialized_packs,
    recommend_specialized_packs,
)


@dataclass(frozen=True)
class WorkflowCase:
    id: str
    description: str
    input_kind: str
    output_kind: str


CASES = (
    WorkflowCase(
        "customer-model",
        "Validate and enrich customer addresses, then train and deploy a model",
        "artifact.raw-records",
        "artifact.deployed-model",
    ),
    WorkflowCase(
        "repository-release",
        "Repair a backend repository, verify regressions, and stage a release",
        "artifact.repository",
        "artifact.release-candidate",
    ),
    WorkflowCase(
        "rag-evaluation",
        "Build a grounded RAG system and run a sealed red-team evaluation harness",
        "artifact.document-corpus",
        "artifact.llm-evaluation-report",
    ),
)


def main() -> int:
    registry = REFERENCE_SPECIALIZED_PACK_REGISTRY
    nominations = []
    for case in CASES:
        report = recommend_specialized_packs(
            TaskPackageRequest(
                id=f"package-request.example-{case.id}",
                description=case.description,
                input_kind_ids=(case.input_kind,),
                output_kind_ids=(case.output_kind,),
            ),
            registry,
            selection_limit=3,
        )
        nominations.append(
            {
                "case_id": case.id,
                "recommended_pack_ids": list(report.recommended_pack_ids),
                "all_visible_pack_count": len(report.recommendations),
                "report_digest": report.digest,
            }
        )

    composition = compose_specialized_packs(
        PackageCompositionRequest(
            id="composition-request.example-customer-model",
            starting_kind_ids=("artifact.raw-records",),
            goal_kind_ids=("artifact.deployed-model",),
            max_steps=4,
            state_budget=10_000,
            candidate_limit=5,
        ),
        registry,
    )
    payload = {
        "specialized_pack_registry_digest": registry.digest,
        "nominations": nominations,
        "composition": {
            "candidate_count": len(composition.candidates),
            "first_recipe_chain": [
                {
                    "pack_id": step.pack_id,
                    "recipe_id": step.recipe_id,
                    "input_kind_ids": list(step.input_kind_ids),
                    "output_kind_ids": list(step.output_kind_ids),
                }
                for step in composition.candidates[0].steps
            ],
            "search_accounting": composition.to_dict()["search_accounting"],
            "claim_boundary": composition.claim_boundary,
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
