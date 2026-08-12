"""Five-minute adapter from bundled examples to the public solutioning façade."""

from __future__ import annotations

from solutiongraph.intelligence import EffortPolicy, HistoricalMemory, TaskFingerprint
from solutiongraph.model import Port
from solutiongraph.solutioning import TaskSolutionRequest
from solutiongraph.tasking import TaskContract, TaskOracle


def example_solution_request(
    example_id: str,
    *,
    effort: int | str | EffortPolicy = 1,
    historical_memory: HistoricalMemory | None = None,
    fingerprint: TaskFingerprint | None = None,
) -> TaskSolutionRequest:
    """Project one executable fixture into a complete typed solve request."""

    from solutiongraph.examples import get_example

    example = get_example(example_id)
    family = {
        "data-cleanup": "dag.prepare.clean",
        "tabular-regression": "dag.learn.regression",
        "tabular-classification": "dag.learn.classification",
        "duecare-llm-evaluation-harness": "dag.evaluate.llm-harness",
        "geotemporal-enrichment": "dag.integrate.geotemporal",
    }.get(example_id, "dag.engineer.workflow")
    oracle = TaskOracle(
        id=example.case.verifier.identifier,
        version="1.0.0",
        kind="property",
        evaluator_digest=example.case.verifier.implementation_digest,
        implementation_ref=f"python://solutiongraph.examples:{example_id}",
        independence="separate-implementation",
        candidate_readable=True,
        description="Transparent mechanism-fixture verifier from the bundled example.",
    )
    task = TaskContract(
        id=f"task.example.{example_id}",
        version="1.0.0",
        title=example.title,
        intent=example.description,
        inputs=tuple(Port(item.name, item.value_type) for item in example.program.inputs),
        outputs=tuple(Port(item.name, item.value_type) for item in example.program.outputs),
        success_contract=example.program.success_contract,
        oracle=oracle,
        objectives=example.objectives,
        allowed_effects=example.program.allowed_effects,
        granted_permissions=example.program.granted_permissions,
        case_ids=(example.case.id,),
        tags=(family, "evidence.mechanism-fixture"),
        extensions=(
            ("task.family", family),
            ("benchmark.claim-scope", "mechanism-fixture"),
        ),
    )
    return TaskSolutionRequest(
        id=f"solution.example.{example_id}",
        task=task,
        program=example.program,
        registry=example.registry,
        cases=(example.case,),
        policy=example.policy,
        historical_memory=(
            historical_memory
            if historical_memory is not None
            else HistoricalMemory(f"memory.example.{example_id}", "1.0.0")
        ),
        fingerprint=fingerprint,
        effort=effort,
        baseline_selection=tuple(example.routes[0].selection.items()),
    )


__all__ = ["example_solution_request"]
