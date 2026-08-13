from __future__ import annotations

from threading import Lock

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry as SchemaRegistry
from referencing import Resource

from solutiongraph.artifacts import MemoryArtifactStore
from solutiongraph.benchmark_library import get_benchmark
from solutiongraph.catalog import catalog_documents
from solutiongraph.compiler import Compiler
from solutiongraph.evidence import ExperimentDesign
from solutiongraph.executor import (
    ExecutionError,
    ExecutionPolicy,
    ReferenceExecutor,
    callable_implementation_digest,
)
from solutiongraph.experiments import ExperimentBundle
from solutiongraph.integrations import (
    REFERENCE_INTEGRATION_ADAPTERS,
    export_frozen_plan,
    project_bpmn,
    project_cloudevents,
    project_openapi,
)
from solutiongraph.model import (
    Candidate,
    GraphInput,
    GraphOutput,
    NodeSpec,
    Port,
    ProgramGraph,
    Registry,
    SemanticSlot,
    ValueType,
    sha256_digest,
)
from solutiongraph.parallel_experiments import (
    ParallelExperimentPolicy,
    ParallelExperimentRunner,
    schedule_experiment,
)
from solutiongraph.runtime_validation import (
    CallablePayloadValidator,
    PayloadValidatorRegistry,
)
from solutiongraph.schemas import load_all_schemas
from solutiongraph.universal import (
    COVERAGE_STATUSES,
    REFERENCE_DOMAIN_PACKS,
    REFERENCE_ENGINEERING_QUESTIONS,
    REFERENCE_OBLIGATIONS,
    context_from_task,
    fingerprint_attributes_from_context,
    plan_engineering_design,
    reference_coverage_report,
    validate_universal_catalog,
)


def _validate_wire(schema_name: str, payload) -> None:
    schemas = load_all_schemas()
    registry = SchemaRegistry().with_resources(
        (name, Resource.from_contents(schema)) for name, schema in schemas.items()
    )
    errors = sorted(
        Draft202012Validator(schemas[schema_name], registry=registry).iter_errors(payload),
        key=lambda item: list(item.absolute_path),
    )
    assert errors == [], "\n".join(
        f"{'.'.join(map(str, item.absolute_path))}: {item.message}" for item in errors
    )


def test_universal_catalog_is_domain_neutral_complete_and_strict():
    assert validate_universal_catalog() == []
    assert len(REFERENCE_OBLIGATIONS) == 14
    assert len(REFERENCE_DOMAIN_PACKS) == 13
    assert len(REFERENCE_ENGINEERING_QUESTIONS) == 42
    assert {item.id for item in REFERENCE_OBLIGATIONS} == {
        f"obligation.{item}"
        for item in (
            "acquire decode validate normalize transform enrich reconcile decide "
            "persist serve verify observe recover govern"
        ).split()
    }
    assert {item.id for item in REFERENCE_DOMAIN_PACKS}.issuperset(
        {
            "domain-pack.backend-api",
            "domain-pack.security-compliance",
            "domain-pack.business-human-workflow",
            "domain-pack.science-optimization",
            "domain-pack.ai-ml",
            "domain-pack.llm-agent",
        }
    )
    for pack in REFERENCE_DOMAIN_PACKS:
        _validate_wire("universal-domain-pack.schema.json", pack.to_dict())
    for question in REFERENCE_ENGINEERING_QUESTIONS:
        _validate_wire("universal-design-question.schema.json", question.to_dict())


def test_coverage_is_derived_and_preserves_strong_thin_blocked_catalog_and_empty():
    report = reference_coverage_report()
    assert report.validate() == []
    assert tuple(status for status, _ in report.status_counts) == COVERAGE_STATUSES
    assert all(count > 0 for _, count in report.status_counts)
    assert sum(count for _, count in report.status_counts) == sum(
        len(domain.capabilities) for domain in report.domains
    )
    business = next(
        item
        for item in report.domains
        if item.domain_pack_id == "domain-pack.business-human-workflow"
    )
    assert any(item.status == "empty" for item in business.capabilities)
    assert all(
        item.maturity_level != "C7"
        for domain in report.domains
        for item in domain.capabilities
    )
    _validate_wire("universal-coverage-report.schema.json", report.to_dict())


def test_context_uses_ten_independent_channels_and_extends_historical_fingerprints():
    task = get_benchmark("benchmark.data-cleaning").definition.task_contract
    context = context_from_task(
        task,
        domain_pack_ids=("domain-pack.data-integration",),
    )
    assert len(context.channels) == 10
    assert context.validate() == []
    attributes = fingerprint_attributes_from_context(context)
    assert len(attributes) == 10
    assert len({item.key for item in attributes}) == 10
    assert all(item.source == context.id for item in attributes)
    _validate_wire("universal-design-context.schema.json", context.to_dict())


def test_engineering_effort_changes_allocation_without_hiding_questions():
    task = get_benchmark("benchmark.data-cleaning").definition.task_contract
    context = context_from_task(
        task,
        domain_pack_ids=("domain-pack.data-integration",),
    )
    small = plan_engineering_design(
        context,
        domain_pack_id="domain-pack.data-integration",
        effort="E1",
        available_modes=("deterministic", "human", "llm", "external"),
        granted_permissions=("human.review", "model.invoke", "network.read"),
        random_seed=41,
    )
    full = plan_engineering_design(
        context,
        domain_pack_id="domain-pack.data-integration",
        effort="E10",
        available_modes=("deterministic", "human", "llm", "external"),
        granted_permissions=("human.review", "model.invoke", "network.read"),
        random_seed=41,
    )
    assert len(small.items) == len(full.items) == 42
    assert small.summary["selected"] < full.summary["selected"] == 9
    assert full.summary["not-applicable"] == 33
    assert plan_engineering_design(
        context,
        domain_pack_id="domain-pack.data-integration",
        effort="E1",
        available_modes=("deterministic", "human", "llm", "external"),
        granted_permissions=("human.review", "model.invoke", "network.read"),
        random_seed=41,
    ) == small
    _validate_wire("universal-design-plan.schema.json", small.to_dict())


def test_engineering_questions_fail_closed_without_model_human_or_network_authority():
    task = get_benchmark("benchmark.data-cleaning").definition.task_contract
    context = context_from_task(
        task,
        domain_pack_ids=("domain-pack.data-integration",),
    )
    plan = plan_engineering_design(
        context,
        domain_pack_id="domain-pack.data-integration",
        effort="E10",
        available_modes=("llm", "human", "external"),
        granted_permissions=(),
    )
    assert plan.summary["selected"] == 0
    assert plan.summary["blocked"] == 9


def test_openapi_cloudevents_and_bpmn_projection_preserve_claim_boundaries():
    openapi = project_openapi(
        {
            "openapi": "3.2.0",
            "info": {"title": "Orders", "version": "1.0.0"},
            "paths": {
                "/orders/{order_id}": {
                    "get": {
                        "operationId": "getOrder",
                        "parameters": [
                            {
                                "name": "order_id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Order",
                                "content": {"application/json": {"schema": {"type": "object"}}},
                            }
                        },
                    },
                    "post": {
                        "operationId": "replaceOrder",
                        "requestBody": {
                            "content": {"application/json": {"schema": {"type": "object"}}}
                        },
                        "responses": {"204": {"description": "Replaced"}},
                    },
                }
            },
        }
    )
    assert [item.effects for item in openapi.operations] == [
        ("network.read",),
        ("network.write",),
    ]
    events = project_cloudevents(
        (
            {
                "specversion": "1.0",
                "id": "1",
                "source": "/orders",
                "type": "com.example.order.created",
                "datacontenttype": "application/json",
                "data": {"order_id": "o1"},
            },
            {
                "specversion": "1.0",
                "id": "2",
                "source": "/orders",
                "type": "com.example.order.cancelled",
                "data": {"order_id": "o1"},
            },
        )
    )
    assert len(events.operations) == 2
    bpmn = project_bpmn(
        """<?xml version="1.0"?>
        <definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">
          <process id="claims">
            <startEvent id="start" />
            <userTask id="review" name="Review claim" />
            <serviceTask id="notify" name="Notify claimant" />
            <endEvent id="done" />
            <sequenceFlow id="f1" sourceRef="start" targetRef="review" />
            <sequenceFlow id="f2" sourceRef="review" targetRef="notify" />
            <sequenceFlow id="f3" sourceRef="notify" targetRef="done" />
          </process>
        </definitions>"""
    )
    review = next(item for item in bpmn.operations if item.source_ref == "review")
    notify = next(item for item in bpmn.operations if item.source_ref == "notify")
    assert review.permissions == ("human.review",)
    assert notify.dependencies == (review.id,)
    assert all(item.limitations for item in (openapi, events, bpmn))
    for projection in (openapi, events, bpmn):
        _validate_wire("integration-projection.schema.json", projection.to_dict())
    for profile in REFERENCE_INTEGRATION_ADAPTERS:
        _validate_wire("integration-adapter.schema.json", profile.to_dict())
    with pytest.raises(ValueError, match="DTD"):
        project_bpmn('<!DOCTYPE x [<!ENTITY y "z">]><definitions/>')


def test_orchestrator_projection_preserves_exact_plan_node_and_dependencies():
    from solutiongraph.examples import get_example

    example = get_example("idempotent-api-contract")
    _, plans = example.compile()
    plan = next(iter(plans.values()))
    projection = export_frozen_plan(
        plan,
        example.program,
        example.registry,
        adapter_id="adapter.orchestrator.kubernetes",
    )
    assert projection.plan_digest == plan.digest
    assert tuple(item.slot_id for item in projection.tasks) == plan.topological_order
    assert all(item.implementation_digest.startswith("sha256:") for item in projection.tasks)
    assert any(item.dependencies for item in projection.tasks[1:])
    _validate_wire("orchestrator-plan-projection.schema.json", projection.to_dict())


SCHEMA = sha256_digest({"type": "object", "required": ["answer"]})
PAYLOAD = ValueType("test.validated-payload", schema_digest=SCHEMA)


def payload_identity(value):
    return value


def payload_invalid_output(value):
    return {"not_answer": value.get("answer")}


def validate_payload(value):
    if not isinstance(value, dict):
        return ("payload must be an object",)
    if not isinstance(value.get("answer"), int):
        return ("answer must be an integer",)
    return ()


def _validated_fixture(function):
    node = NodeSpec(
        id=f"test.node.{function.__name__.replace('_', '-')}",
        version="1.0.0",
        implementation_digest=callable_implementation_digest(function),
        inputs=(Port("value", PAYLOAD),),
        outputs=(Port("value", PAYLOAD),),
        runtime="python",
        entrypoint=f"{function.__module__}:{function.__name__}",
        capabilities=("test.payload-transform",),
    )
    candidate = Candidate(
        f"candidate.{node.id}",
        node.id,
        node.version,
        node.implementation_digest,
    )
    registry = Registry("test.validated-registry", "1.0.0", (node,), (candidate,))
    program = ProgramGraph(
        "test.validated-program",
        "1.0.0",
        "Validate payloads at runtime.",
        "The exact payload schema accepts the result.",
        (
            SemanticSlot(
                "transform",
                "Transform a payload.",
                (Port("value", PAYLOAD),),
                (Port("value", PAYLOAD),),
                "The payload remains valid.",
                required_capabilities=("test.payload-transform",),
            ),
        ),
        (),
        (GraphInput("value", PAYLOAD, "transform", "value"),),
        (GraphOutput("value", PAYLOAD, "transform", "value"),),
    )
    compiler = Compiler()
    space = compiler.admit(program, registry)
    plan = compiler.compile(program, registry, space, {"transform": candidate.id})
    validator = CallablePayloadValidator(
        "validator.test.payload",
        SCHEMA,
        validate_payload,
    )
    executor = ReferenceExecutor(
        payload_validators=PayloadValidatorRegistry((validator,), require_registered=True)
    )
    return executor, plan, program, registry, space


def test_runtime_schema_registry_rejects_invalid_inputs_and_outputs():
    assert PayloadValidatorRegistry().identity_record() != PayloadValidatorRegistry(
        require_registered=True
    ).identity_record()
    executor, plan, program, registry, space = _validated_fixture(payload_identity)
    with pytest.raises(ExecutionError, match="answer must be an integer"):
        executor.execute(
            plan,
            program,
            registry,
            space,
            {"value": {"answer": "wrong"}},
            task_case_id="case.invalid-input",
            verifier=None,
            policy=ExecutionPolicy(require_task_verifier=False),
        )

    executor, plan, program, registry, space = _validated_fixture(payload_invalid_output)
    result = executor.execute(
        plan,
        program,
        registry,
        space,
        {"value": {"answer": 7}},
        task_case_id="case.invalid-output",
        verifier=None,
        policy=ExecutionPolicy(require_task_verifier=False),
    )
    assert not result.ok
    assert result.receipt.failure_class == "runtime.schema-invalid"
    assert result.receipt.node_receipts[0].failure_class == "runtime.schema-invalid"


class _ReceiptCollector:
    def __init__(self) -> None:
        self.receipts = []

    def append(self, *receipts) -> None:
        self.receipts.extend(receipts)


def test_parallel_experiment_runner_uses_fresh_executors_and_stable_ledger_order():
    from solutiongraph.examples import get_example

    example = get_example("data-cleanup")
    space, plans_by_name = example.compile()
    plans = tuple(plans_by_name.values())
    design = ExperimentDesign(
        id="experiment.test.parallel",
        task_case_ids=(example.case.id,),
        plan_digests=tuple(item.digest for item in plans),
        seeds=(17, 29),
        repetitions=1,
        objectives=example.objectives,
        control_plan_digest=plans[0].digest,
    )
    bundle = ExperimentBundle(
        design=design,
        plans={item.digest: item for item in plans},
        cases={example.case.id: example.case},
        program=example.program,
        registry=example.registry,
        space=space,
        policy=example.policy,
    )
    created = []
    created_stores = []
    created_lock = Lock()

    def executor_factory():
        executor = ReferenceExecutor()
        with created_lock:
            created.append(executor)
        return executor

    def artifact_store_factory():
        store = MemoryArtifactStore()
        with created_lock:
            created_stores.append(store)
        return store

    collector = _ReceiptCollector()
    result = ParallelExperimentRunner(
        executor_factory,
        policy=ParallelExperimentPolicy(max_parallel_runs=3),
    ).run_bundle(
        bundle,
        artifact_store_factory=artifact_store_factory,
        receipt_sink=collector,
    )
    schedule = schedule_experiment(bundle)
    assert len(created) == len(schedule) == design.scheduled_runs
    assert len({id(item) for item in created}) == len(created)
    assert len(created_stores) == len(schedule)
    assert len({id(item) for item in created_stores}) == len(created_stores)
    assert tuple(item.id for item in result.ledger.receipts) == tuple(
        item.run_id for item in schedule
    )
    assert {item.id for item in collector.receipts} == {
        item.id for item in result.ledger.receipts
    }

    shared_executor = ReferenceExecutor()
    with pytest.raises(ValueError, match="fresh executor"):
        ParallelExperimentRunner(
            lambda: shared_executor,
            policy=ParallelExperimentPolicy(max_parallel_runs=2),
        ).run_bundle(bundle)

    shared_store = MemoryArtifactStore()
    with pytest.raises(ValueError, match="fresh store"):
        ParallelExperimentRunner(
            ReferenceExecutor,
            policy=ParallelExperimentPolicy(max_parallel_runs=2),
        ).run_bundle(bundle, artifact_store_factory=lambda: shared_store)


def test_universal_assets_are_exported_to_the_portable_catalog():
    documents = catalog_documents()
    assert documents["universal/index.json"]["obligation_count"] == 14
    assert documents["universal/index.json"]["domain_pack_count"] == 13
    assert documents["universal/index.json"]["engineering_question_count"] == 42
    assert documents["integrations/index.json"]["adapter_count"] == 7
    assert documents["index.json"]["universal_engineering"]["coverage_digest"] == (
        reference_coverage_report().digest
    )
