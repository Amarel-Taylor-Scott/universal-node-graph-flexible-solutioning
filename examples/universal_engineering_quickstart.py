"""Inspect, plan, and project one domain-neutral engineering task offline."""

from __future__ import annotations

import json

from solutiongraph.benchmark_library import get_benchmark
from solutiongraph.examples import get_example
from solutiongraph.integrations import export_frozen_plan, project_openapi
from solutiongraph.universal import (
    context_from_task,
    plan_engineering_design,
    reference_coverage_report,
)


def main() -> None:
    task = get_benchmark("benchmark.data-cleaning").definition.task_contract
    context = context_from_task(
        task,
        domain_pack_ids=("domain-pack.data-integration",),
    )
    design_plan = plan_engineering_design(
        context,
        domain_pack_id="domain-pack.data-integration",
        effort="E3",
        available_modes=("deterministic",),
        random_seed=41,
    )

    api = project_openapi(
        {
            "openapi": "3.2.0",
            "info": {"title": "Orders", "version": "1.0.0"},
            "paths": {
                "/orders/{order_id}": {
                    "get": {
                        "operationId": "getOrder",
                        "responses": {
                            "200": {
                                "description": "Order",
                                "content": {
                                    "application/json": {
                                        "schema": {"type": "object"}
                                    }
                                },
                            }
                        },
                    }
                }
            },
        }
    )

    example = get_example("idempotent-api-contract")
    _, plans = example.compile()
    route_id = sorted(plans)[0]
    orchestrator = export_frozen_plan(
        plans[route_id],
        example.program,
        example.registry,
        adapter_id="adapter.orchestrator.kubernetes",
    )
    coverage = reference_coverage_report()

    print(
        json.dumps(
            {
                "task_context": {
                    "id": context.id,
                    "channel_ids": [item.id for item in context.channels],
                },
                "engineering_plan": {
                    "effort": design_plan.effort,
                    "summary": design_plan.summary,
                    "digest": design_plan.digest,
                },
                "openapi_projection": {
                    "operation_ids": [item.id for item in api.operations],
                    "limitations": list(api.limitations),
                },
                "orchestrator_projection": {
                    "route_id": route_id,
                    "plan_digest": orchestrator.plan_digest,
                    "task_count": len(orchestrator.tasks),
                    "limitations": list(orchestrator.limitations),
                },
                "coverage": dict(coverage.status_counts),
                "claim_boundary": coverage.claim_boundary,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
