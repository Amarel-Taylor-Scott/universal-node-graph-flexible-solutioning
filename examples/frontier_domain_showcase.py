#!/usr/bin/env python3
"""Run every frontier-domain control beside its verified reference route.

The fixtures are deliberately small and dependency-free. They demonstrate the
same compile, freeze, execute, and independently verify lifecycle across seven
very different domains; they do not claim production domain performance.
"""

from __future__ import annotations

import json

from solutiongraph.examples.frontier_tasks import FRONTIER_EXAMPLE_TASKS
from solutiongraph.examples.tasks import run_example


def main() -> int:
    results = []
    for example in FRONTIER_EXAMPLE_TASKS:
        control = run_example(example.id, route="shortcut-control")
        reference = run_example(example.id, route="reference")
        control_receipt = control["execution"]["receipt"]
        reference_receipt = reference["execution"]["receipt"]
        results.append(
            {
                "example_id": example.id,
                "slot_count": len(example.program.slots),
                "admitted_candidates_per_slot": {
                    slot_id: len(candidate_ids)
                    for slot_id, candidate_ids in reference["admitted_candidates"].items()
                },
                "control": {
                    "accepted": control_receipt["accepted"],
                    "failure_class": control_receipt["failure_class"],
                    "plan_digest": control_receipt["plan_digest"],
                },
                "reference": {
                    "accepted": reference_receipt["accepted"],
                    "quality": reference_receipt["metrics"]["quality"],
                    "plan_digest": reference_receipt["plan_digest"],
                    "output_digests": reference_receipt["output_artifacts"],
                },
            }
        )

    payload = {
        "example_count": len(results),
        "all_controls_rejected": all(not result["control"]["accepted"] for result in results),
        "all_references_accepted": all(result["reference"]["accepted"] for result in results),
        "examples": results,
        "claim_boundary": (
            "Deterministic mechanism fixtures only; production evaluation requires "
            "representative cases, independent owners, enforcing runtimes, and domain authority."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["all_controls_rejected"] and payload["all_references_accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
