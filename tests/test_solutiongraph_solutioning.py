from __future__ import annotations

from dataclasses import replace

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry as SchemaRegistry
from referencing import Resource

from solutiongraph import (
    CallableVerifier,
    ExperimentStudyRunner,
    ExternalBenchmarkRequest,
    GraphExperimentRunner,
    GraphMutationEngine,
    InsertSlotAfterInput,
    InsertSlotBeforeOutput,
    InsertSlotOnEdge,
    MutationContext,
    Objective,
    Port,
    RemoveLinearSlot,
    ReplaceSlotContract,
    SemanticSlot,
    StudyDesign,
    TaskCaseSpec,
    TaskOracle,
    TaskSolutionEngine,
    ValueType,
    get_benchmark_adapter,
    sha256_digest,
    solve_task,
)
from solutiongraph.examples.control_mutation_experiment import (
    CONTROL_MUTATION_CASE,
    CONTROL_MUTATION_RESULT,
    CONTROL_PROGRAM,
    CONTROL_VARIANT,
    MUTATED_PROGRAM,
    _slot,
    control_mutation_experiment_spec,
)
from solutiongraph.examples.intelligent_solutioning import example_solution_request
from solutiongraph.schemas import load_all_schemas

_SCHEMAS = load_all_schemas()
_SCHEMA_REGISTRY = SchemaRegistry().with_resources(
    (schema["$id"], Resource.from_contents(schema)) for schema in _SCHEMAS.values()
)


def _validate_wire(schema_name: str, payload: object) -> None:
    errors = sorted(
        Draft202012Validator(
            _SCHEMAS[schema_name], registry=_SCHEMA_REGISTRY
        ).iter_errors(payload),
        key=lambda error: tuple(error.path),
    )
    assert not errors, "; ".join(error.message for error in errors)


def test_public_solutioning_facade_recognizes_routes_executes_and_closes_history():
    engine = TaskSolutionEngine()
    request = example_solution_request("data-cleanup", effort=1)

    assert engine.validate(request) == ()
    fingerprint = engine.recognize(request)
    assert fingerprint.attribute_map["task.family"].value == "dag.prepare.clean"
    assert fingerprint.category_matches[0].category_id == "dag.prepare.clean"

    binding = engine.bind(request)
    plans = engine.route(request, binding)
    assert len(plans) == len(binding.initialization.starts) >= 2
    assert any(start.history_blind for start in binding.initialization.starts)

    result = solve_task(request, engine=engine)
    assert result.status == "solved"
    assert result.champion is not None
    assert result.negative_transfer.status == "assessment.insufficient-matched-evidence"
    assert engine.get_evidence(result).receipts
    _validate_wire("task-solution-report.schema.json", result.to_dict())

    update = engine.learn(request, result)
    assert len(update.memory.episodes) == len(
        {receipt.plan_digest for receipt in result.solver.ledger.receipts}
    )

    warm = replace(
        request,
        id="solution.example.data-cleanup-warm-test",
        historical_memory=update.memory,
    )
    warm_binding = engine.bind(warm)
    assert warm_binding.initialization.recommendations
    assert any(
        not start.history_blind for start in warm_binding.initialization.starts
    )
    assert any(start.history_blind for start in warm_binding.initialization.starts)


def test_solutioning_rejects_oracle_drift_and_binding_reuse():
    request = example_solution_request("data-cleanup", effort=1)
    engine = TaskSolutionEngine()
    binding = engine.bind(request)

    def different_verifier(_context):
        raise AssertionError("must never execute")

    altered_case = replace(
        request.cases[0],
        verifier=CallableVerifier(request.task.oracle.id, different_verifier),
    )
    altered = replace(request, id="solution.example.oracle-drift", cases=(altered_case,))
    assert any("verifier digest differs" in item for item in engine.validate(altered))
    with pytest.raises(ValueError, match="different request"):
        engine.execute(replace(request, id="solution.example.changed"), binding)


def test_typed_mutation_constructs_the_showcase_and_receipts_ancestry():
    assert CONTROL_MUTATION_RESULT.variant.program == MUTATED_PROGRAM
    assert CONTROL_MUTATION_RESULT.receipt.external_interface_preserved
    assert CONTROL_MUTATION_RESULT.receipt.operator_id == "operator.insert-slot-after-input"
    assert CONTROL_MUTATION_RESULT.receipt.parent_variant_id == CONTROL_VARIANT.id
    _validate_wire(
        "graph-mutation-receipt.schema.json",
        CONTROL_MUTATION_RESULT.receipt.to_dict(),
    )

    duplicate = InsertSlotAfterInput(
        CONTROL_PROGRAM.slots[0],
        "payload",
        "payload",
        "payload",
    )
    with pytest.raises(ValueError, match="already exists"):
        GraphMutationEngine().apply(
            CONTROL_VARIANT,
            duplicate,
            MutationContext(
                "topology.example.invalid-duplicate",
                "Invalid duplicate",
                "example.control-mutation-invalid",
                "1.0.0",
                "Attempt a duplicate slot insertion.",
                "This invalid child must remain rejected evidence.",
                "proposer.test",
            ),
        )


def test_all_reference_mutation_operators_produce_complete_compiler_valid_graphs():
    engine = GraphMutationEngine()
    payload_ports = CONTROL_PROGRAM.slots[0]
    postprocess = SemanticSlot(
        "postprocess",
        "Apply an explicit post-estimation obligation.",
        payload_ports.inputs,
        payload_ports.outputs,
        "The result remains a typed payload.",
        required_capabilities=("experiment.clean",),
    )
    after_output = engine.apply(
        CONTROL_VARIANT,
        InsertSlotBeforeOutput(postprocess, "result", "payload", "payload"),
        MutationContext(
            "topology.test.postprocess",
            "Postprocess output",
            "program.test.postprocess",
            "1.0.0",
            "Make output postprocessing explicit.",
            "A replaceable output check may improve acceptance.",
            "proposer.test",
        ),
    )
    assert after_output.variant.program.outputs[0].source_slot == "postprocess"

    internal = SemanticSlot(
        "audit",
        "Audit the typed payload between cleaning and estimation.",
        MUTATED_PROGRAM.slots[0].inputs,
        MUTATED_PROGRAM.slots[0].outputs,
        "The audited payload preserves the typed contract.",
        required_capabilities=("experiment.clean",),
    )
    inserted = engine.apply(
        CONTROL_MUTATION_RESULT.variant,
        InsertSlotOnEdge(
            internal,
            "clean",
            "payload",
            "estimate",
            "payload",
            "payload",
            "payload",
        ),
        MutationContext(
            "topology.test.audit",
            "Audit internal edge",
            "program.test.audit",
            "1.0.0",
            "Split the cleaning-to-estimation edge with an audit obligation.",
            "An explicit audit stage can be independently substituted.",
            "proposer.test",
        ),
    )
    assert {slot.id for slot in inserted.variant.program.slots} == {
        "clean",
        "audit",
        "estimate",
    }

    removed = engine.apply(
        inserted.variant,
        RemoveLinearSlot("audit"),
        MutationContext(
            "topology.test.audit-removed",
            "Remove audit",
            "program.test.audit-removed",
            "1.0.0",
            "Ablate the internal audit obligation.",
            "The audit ablation measures whether the extra stage adds value.",
            "proposer.test",
        ),
    )
    assert removed.variant.program.edges == MUTATED_PROGRAM.edges

    replacement = replace(
        CONTROL_PROGRAM.slots[0],
        purpose="Estimate through a stricter semantic obligation.",
        success_contract="The estimate records a typed method and satisfies a stricter audit.",
    )
    replaced = engine.apply(
        CONTROL_VARIANT,
        ReplaceSlotContract(replacement),
        MutationContext(
            "topology.test.replaced-contract",
            "Replace estimator obligation",
            "program.test.replaced-contract",
            "1.0.0",
            "Refine the semantic contract while retaining the exact interface.",
            "A stricter obligation may admit a safer implementation subset.",
            "proposer.test",
        ),
    )
    assert replaced.variant.program.slots[0].purpose.startswith("Estimate through")
    assert all(
        not GraphMutationEngine().compiler.validate_program(result.variant.program)
        for result in (after_output, inserted, removed, replaced)
    )

    incompatible_slot = _slot(
        "clean",
        "experiment.clean",
        "Apply one explicit cleaning policy.",
    )
    wrong_type = ValueType("example.wrong-payload")
    incompatible_slot = replace(
        incompatible_slot,
        inputs=(Port("payload", wrong_type),),
    )
    with pytest.raises(ValueError, match="compiler-invalid"):
        GraphMutationEngine().apply(
            CONTROL_VARIANT,
            InsertSlotAfterInput(
                incompatible_slot,
                "payload",
                "payload",
                "payload",
            ),
            MutationContext(
                "topology.example.invalid-type",
                "Invalid type",
                "example.control-mutation-invalid-type",
                "1.0.0",
                "Attempt an implicit type conversion.",
                "The compiler must reject nominal type drift.",
                "proposer.test",
            ),
        )


def test_paired_study_promotes_only_noninferior_improvements_and_is_deterministic():
    graph = GraphExperimentRunner().run(control_mutation_experiment_spec())
    candidates = tuple(
        item.plan_digest
        for item in graph.comparisons
        if item.plan_digest != graph.control_plan_digest
    )
    design = StudyDesign(
        id="study.test.control-mutation",
        control_plan_digest=graph.control_plan_digest,
        candidate_plan_digests=candidates,
        objectives=graph.spec.objectives,
        task_case_ids=(CONTROL_MUTATION_CASE.id,),
        minimum_pairs=1,
        bootstrap_resamples=250,
        # This mechanism fixture keeps measured latency visible without making
        # a one-sample scheduler fluctuation decide the study verdict.
        practical_effect_thresholds=(("quality", 0.01), ("latency_ms", 1_000.0)),
    )
    first = ExperimentStudyRunner().analyze(design, graph.ledger)
    second = ExperimentStudyRunner().analyze(design, graph.ledger)

    assert first.to_dict() == second.to_dict()
    assert first.recommended_plan_digests
    assert {arm.verdict for arm in first.arms} >= {"study.promote", "study.reject"}
    _validate_wire("experiment-study-report.schema.json", first.to_dict())

    insufficient = replace(design, id="study.test.insufficient", minimum_pairs=2)
    continued = ExperimentStudyRunner().analyze(insufficient, graph.ledger)
    assert {arm.verdict for arm in continued.arms} == {"study.continue"}


def _external_request(*, metadata=None) -> ExternalBenchmarkRequest:
    table = ValueType("test.external-table")
    submission = ValueType("test.external-submission")
    oracle = TaskOracle(
        "oracle.external-regression",
        "1.0.0",
        "statistical",
        sha256_digest("external-rmse-v1"),
        "artifact://evaluators/external-rmse-v1",
        candidate_readable=False,
    )
    case = TaskCaseSpec(
        "case.external-regression.holdout",
        "holdout",
        sha256_digest("external-holdout-input-v1"),
        "artifact://cases/external-holdout-v1",
    )
    return ExternalBenchmarkRequest(
        task_id="task.external-regression",
        task_version="1.0.0",
        title="External regression",
        intent="Produce a valid prediction table for a frozen data snapshot.",
        success_contract="Pass format validation and minimize frozen RMSE.",
        inputs=(Port("training_table", table),),
        outputs=(Port("submission", submission),),
        oracle=oracle,
        objectives=(Objective("rmse", "minimize"),),
        cases=(case,),
        source_id="source.kaggle.external-regression",
        source_version="rules-v1",
        source_uri="https://www.kaggle.com/competitions/external-regression",
        metadata=metadata
        or (
            ("benchmark.dataset-license", "competition-specific"),
            ("benchmark.data-version", "snapshot-v1"),
            ("benchmark.metric-implementation", "artifact://metrics/rmse-v1"),
            ("benchmark.leakage-rules", "holdout is candidate-inaccessible"),
            ("benchmark.submission-format", "row_id,prediction"),
        ),
    )


def test_external_benchmark_adapters_are_strict_and_side_effect_free():
    adapter = get_benchmark_adapter("adapter.kaggle")
    bundle = adapter.adapt(_external_request())
    assert bundle.task.case_ids == ("case.external-regression.holdout",)
    assert dict(bundle.task.extensions)["benchmark.source-version"] == "rules-v1"
    assert bundle.limitations
    _validate_wire("external-benchmark-bundle.schema.json", bundle.to_dict())

    incomplete = _external_request(
        metadata=(("benchmark.dataset-license", "competition-specific"),)
    )
    with pytest.raises(ValueError, match="metadata is missing"):
        adapter.adapt(incomplete)


def test_every_reference_external_adapter_profile_is_valid():
    from solutiongraph import REFERENCE_BENCHMARK_ADAPTER_PROFILES

    assert len(REFERENCE_BENCHMARK_ADAPTER_PROFILES) == 6
    assert all(profile.validate() == [] for profile in REFERENCE_BENCHMARK_ADAPTER_PROFILES)
    assert {profile.source_kind for profile in REFERENCE_BENCHMARK_ADAPTER_PROFILES} == {
        "benchmark.kaggle",
        "benchmark.mle-bench",
        "benchmark.skillsbench",
        "benchmark.swe-bench",
        "benchmark.browsergym",
        "benchmark.duecare",
    }


def test_external_adapter_profiles_are_discoverable_from_cli(capsys):
    from solutiongraph.cli import main

    assert main(["benchmarks", "adapters", "--json"]) == 0
    payload = capsys.readouterr().out
    assert '"id": "adapter.kaggle"' in payload
    assert '"id": "adapter.duecare"' in payload
