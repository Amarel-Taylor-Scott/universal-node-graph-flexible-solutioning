from __future__ import annotations

import json
from dataclasses import replace

from jsonschema import Draft202012Validator
from referencing import Registry as SchemaRegistry
from referencing import Resource

from solutiongraph import (
    DEFAULT_TASK_CATEGORY_REGISTRY,
    EmbeddingSimilarityChannel,
    FingerprintAttribute,
    HistoricalEpisode,
    HistoricalMemory,
    HistoricalOutcome,
    HistoricalRetriever,
    HistoryInformedPlanner,
    LaneOutcome,
    MemoryArtifactStore,
    Objective,
    Port,
    TaskCategoryMatch,
    TaskContract,
    TaskEmbedding,
    TaskFingerprint,
    TaskOracle,
    UniversalSolver,
    ValueType,
    assess_negative_transfer,
    close_solver_history,
    effort_policy,
    fingerprint_from_contract,
    historical_episode_from_receipts,
    profile_tabular_records,
    sha256_digest,
)
from solutiongraph.examples import get_example
from solutiongraph.schemas import load_all_schemas

_SCHEMAS = load_all_schemas()
_SCHEMA_REGISTRY = SchemaRegistry().with_resources(
    (schema["$id"], Resource.from_contents(schema)) for schema in _SCHEMAS.values()
)


def _validate_wire(schema_name: str, payload: object) -> None:
    errors = sorted(
        Draft202012Validator(_SCHEMAS[schema_name], registry=_SCHEMA_REGISTRY).iter_errors(payload),
        key=lambda error: tuple(error.path),
    )
    assert not errors, "; ".join(error.message for error in errors)


def _regression_contract() -> TaskContract:
    records = ValueType("test.records")
    predictions = ValueType("test.predictions")
    return TaskContract(
        id="task.health-risk-regression",
        version="1.0.0",
        title="Health risk regression",
        intent="Predict a continuous health risk score from longitudinal patient data.",
        inputs=(Port("records", records),),
        outputs=(Port("predictions", predictions),),
        success_contract="Minimize holdout RMSE without patient leakage.",
        oracle=TaskOracle(
            id="oracle.health-risk",
            version="1.0.0",
            kind="property",
            evaluator_digest=sha256_digest("health-risk-evaluator"),
            implementation_ref="python://tests:health_risk_oracle",
        ),
        objectives=(Objective("rmse", "minimize"),),
        tags=("dag.learn.regression", "domain.health"),
        extensions=(
            ("task.family", "dag.learn.regression"),
            ("semantic.domain_labels", ("health", "longitudinal")),
        ),
    )


def _fingerprint(
    *,
    task_id: str,
    family: str,
    domain: str,
    dataset_family_id: str,
    columns: int = 12,
) -> TaskFingerprint:
    return TaskFingerprint(
        task_contract_digest=sha256_digest(task_id),
        task_id=task_id,
        dataset_family_id=dataset_family_id,
        knowledge_layer="K5",
        legal_information_boundary="boundary.train-only",
        profile_policy_id="profile.test",
        attributes=(
            FingerprintAttribute("task.family", family),
            FingerprintAttribute("semantic.domain_labels", (domain,)),
            FingerprintAttribute("data.n_columns", columns),
            FingerprintAttribute("missing.fraction.mean", 0.08),
        ),
        category_matches=(TaskCategoryMatch(family, 1.0, (family,), "evidence.declared"),),
    )


def _episode(
    *,
    episode_id: str,
    fingerprint: TaskFingerprint,
    route_id: str,
    selection: dict[str, str],
    lift: float,
    dataset_family_id: str | None = None,
) -> HistoricalEpisode:
    accepted = lift >= 0
    return HistoricalEpisode(
        id=episode_id,
        task_contract_digest=fingerprint.task_contract_digest,
        fingerprint_digest=fingerprint.digest,
        dataset_family_id=dataset_family_id or fingerprint.dataset_family_id,
        route_id=route_id,
        selection=tuple(selection.items()),
        outcomes=(
            HistoricalOutcome(
                "normalized.utility",
                "maximize",
                lift,
                lift,
                normalized_lift=lift,
            ),
        ),
        accepted=accepted,
        status="status.accepted" if accepted else "status.rejected",
        source_lane="start.historical-replay",
        optimizer_id="optimizer.typed-beam",
        effort_policy_id="effort.5",
        failures=() if accepted else ("failure.negative-transfer",),
    )


def test_common_dag_taxonomy_is_extensible_and_covers_requested_families():
    registry = DEFAULT_TASK_CATEGORY_REGISTRY
    assert registry.validate() == []
    ids = {category.id for category in registry.categories}
    assert len(ids) >= 70
    assert {
        "dag.prepare.clean",
        "dag.prepare.verify",
        "dag.integrate.enrich",
        "dag.generate.synthetic",
        "dag.learn.regression",
        "dag.learn.classification",
        "dag.evaluate.llm-harness",
        "dag.evaluate.outer",
    }.issubset(ids)

    regression_matches = registry.classify(_regression_contract())
    assert regression_matches[0].category_id == "dag.learn.regression"
    assert "dag.learn" in {match.category_id for match in regression_matches}
    llm_contract = replace(
        _regression_contract(),
        id="task.llm-evaluation",
        title="LLM test and evaluation harness",
        intent="Run blinded LLM graders, safety tests, and an outer evaluation.",
        tags=("dag.evaluate.llm-harness", "dag.evaluate.outer"),
        extensions=(("task.family", "dag.evaluate.llm-harness"),),
    )
    llm_ids = {match.category_id for match in registry.classify(llm_contract)}
    assert {
        "dag.evaluate",
        "dag.evaluate.llm-harness",
        "dag.evaluate.outer",
    }.issubset(llm_ids)
    _validate_wire("task-category-registry.schema.json", registry.to_dict())


def test_progressive_tabular_profile_is_deterministic_aggregate_only_and_schema_valid():
    base = fingerprint_from_contract(
        _regression_contract(),
        dataset_family_id="dataset.health-cohort",
    )
    records = [
        {
            "age": 20 + index,
            "marker": None if index % 7 == 0 else index * 1.7,
            "cohort": "secret-cohort-name" if index % 2 else "control",
            "target": 0.5 * index + (index % 3),
        }
        for index in range(40)
    ]
    first = profile_tabular_records(
        base, records, target_field="target", sample_limit=31, random_seed=17
    )
    second = profile_tabular_records(
        base, records, target_field="target", sample_limit=31, random_seed=17
    )

    assert first.digest == second.digest
    assert first.knowledge_layer == "K4"
    assert first.attribute_map["target.kind"].value == "target.regression"
    assert first.attribute_map["data.n_rows"].value == 40
    assert "secret-cohort-name" not in json.dumps(first.to_dict())
    _validate_wire("task-fingerprint.schema.json", first.to_dict())

    missing_target = profile_tabular_records(
        base,
        ({"feature": None},),
        target_field="target",
    )
    assert missing_target.knowledge_layer == "K2"
    assert missing_target.attribute_map["types.counts"].value == {"missing": 1}
    assert any("not present" in warning for warning in missing_target.warnings)


def test_historical_retrieval_combines_task_domain_shape_failures_and_conflicts():
    query = _fingerprint(
        task_id="task.query-regression",
        family="dag.learn.regression",
        domain="health",
        dataset_family_id="dataset.query",
    )
    health = replace(query, dataset_family_id="dataset.health-a")
    health_b = replace(query, dataset_family_id="dataset.health-b", task_id="task.health-b")
    finance = _fingerprint(
        task_id="task.finance-regression",
        family="dag.learn.regression",
        domain="finance",
        dataset_family_id="dataset.finance",
        columns=80,
    )
    classification = _fingerprint(
        task_id="task.health-classification",
        family="dag.learn.classification",
        domain="health",
        dataset_family_id="dataset.health-classification",
    )
    selection = {"slot.model": "node.model-tree", "slot.post": "node.post-calibrate"}
    episodes = (
        _episode(
            episode_id="episode.health-win",
            fingerprint=health,
            route_id="route.health-tree",
            selection=selection,
            lift=0.9,
        ),
        _episode(
            episode_id="episode.health-duplicate-family",
            fingerprint=health,
            route_id="route.health-tree",
            selection=selection,
            lift=0.7,
        ),
        _episode(
            episode_id="episode.health-loss",
            fingerprint=health_b,
            route_id="route.health-tree",
            selection=selection,
            lift=-0.2,
        ),
        _episode(
            episode_id="episode.finance",
            fingerprint=finance,
            route_id="route.finance-linear",
            selection={"slot.model": "node.model-linear", "slot.post": "node.post-none"},
            lift=0.4,
        ),
        _episode(
            episode_id="episode.classification",
            fingerprint=classification,
            route_id="route.health-classifier",
            selection={"slot.model": "node.model-classifier", "slot.post": "node.post-calibrate"},
            lift=0.8,
        ),
    )
    memory = HistoricalMemory(
        "memory.task-history",
        "1",
        (health, health_b, finance, classification),
        episodes,
    )

    recommendations = HistoricalRetriever().retrieve(query, memory)
    by_route = {item.route_id: item for item in recommendations}
    health_recommendation = by_route["route.health-tree"]
    assert (
        health_recommendation.fused_similarity > by_route["route.finance-linear"].fused_similarity
    )
    assert set(health_recommendation.episode_ids) == {
        "episode.health-win",
        "episode.health-duplicate-family",
        "episode.health-loss",
    }
    assert set(health_recommendation.conflicting_episode_ids) == set(
        health_recommendation.episode_ids
    )
    assert health_recommendation.negative_transfer_risk > 0
    _validate_wire("historical-memory.schema.json", memory.to_dict())


def test_effort_is_multidimensional_for_arbitrary_levels_and_maximum():
    one = effort_policy(1)
    seven = effort_policy(7)
    maximum = effort_policy("maximum")
    assert one.fingerprint_layer == "K2"
    assert seven.level == 7 and seven.fingerprint_layer == "K5"
    assert len(seven.search_rounds) > len(one.search_rounds)
    assert maximum.level > 100 and maximum.fingerprint_layer == "K8"
    assert maximum.protected_history_blind_lane


def test_embedding_similarity_requires_exact_encoder_space_identity():
    query = replace(
        _fingerprint(
            task_id="task.embedding-query",
            family="dag.learn.regression",
            domain="health",
            dataset_family_id="dataset.query",
        ),
        embeddings=(
            TaskEmbedding(
                "embedding.task-profile",
                "encoder.profile",
                "1",
                (1.0, 0.0),
            ),
        ),
    )
    compatible = replace(
        query,
        task_id="task.embedding-compatible",
        dataset_family_id="dataset.compatible",
        embeddings=(
            TaskEmbedding(
                "embedding.task-profile",
                "encoder.profile",
                "1",
                (0.9, 0.1),
            ),
        ),
    )
    incompatible = replace(
        compatible,
        embeddings=(
            TaskEmbedding(
                "embedding.task-profile",
                "encoder.profile",
                "2",
                (0.9, 0.1),
            ),
        ),
    )

    channel = EmbeddingSimilarityChannel()
    assert channel.score(query, compatible).similarity > 0.99
    assert channel.score(query, incompatible).coverage == 0.0


def test_planner_and_solver_execute_historical_and_history_blind_starting_points():
    example = get_example("golden-customer-table")
    space, _ = example.compile()
    query = _fingerprint(
        task_id="task.golden-customer",
        family="dag.integrate.entity-resolution",
        domain="customer",
        dataset_family_id="dataset.query",
    )
    historical = replace(query, dataset_family_id="dataset.customer-a")
    canonical = example.routes[0].selection
    historical_route = max(
        example.routes,
        key=lambda route: sum(route.selection[slot] != canonical[slot] for slot in canonical),
    )
    episode = _episode(
        episode_id="episode.golden-customer-win",
        fingerprint=historical,
        route_id="route.golden-customer-win",
        selection=dict(historical_route.selection),
        lift=0.8,
    )
    memory = HistoricalMemory(
        "memory.golden-customer",
        "1",
        (historical,),
        (episode,),
    )
    initialization = HistoryInformedPlanner().plan(
        space,
        query,
        memory,
        effort=1,
        canonical_selection=canonical,
        random_seed=31,
    )

    assert initialization.validate(space) == []
    assert any(not start.history_blind for start in initialization.starts)
    assert any(start.history_blind for start in initialization.starts)
    assert any(allocation.protected for allocation in initialization.optimizer_allocations)
    _validate_wire("search-initialization.schema.json", initialization.to_dict())

    result = UniversalSolver().solve(
        example.program,
        example.registry,
        cases=(example.case,),
        objectives=example.objectives,
        policy=example.policy,
        initialization=initialization,
    )
    evaluated = {
        tuple((binding.slot_id, binding.candidate_id) for binding in plan.bindings)
        for plan in result.plans.values()
    }
    assert tuple(historical_route.selection.items()) in evaluated
    assert result.profile.id == "effort.1"
    assert result.search_initialization_digest == initialization.digest
    _validate_wire("solver-result.schema.json", result.to_dict())

    champion_receipts = tuple(
        receipt
        for receipt in result.ledger.receipts
        if receipt.plan_digest == result.champion_plan_digest
    )
    ingested = historical_episode_from_receipts(
        query,
        "route.solver-observation",
        champion_receipts,
        example.objectives,
        source_lane="start.solver-observation",
        optimizer_id="optimizer.universal-solver",
        effort_policy_id=result.profile.id,
        budget={"budget.route-evaluations": float(len(result.plans))},
        registry_digest=result.registry_digest,
    )
    assert ingested.validate() == []
    assert ingested.registry_digest == result.registry_digest
    assert dict(ingested.extensions)["evidence.receipt_ids"]
    _validate_wire(
        "historical-memory.schema.json",
        HistoricalMemory(
            "memory.ingested",
            "1",
            (query,),
            (ingested,),
        ).to_dict(),
    )

    artifact_store = MemoryArtifactStore()
    update = close_solver_history(
        HistoricalMemory("memory.closed-solver-history", "1"),
        query,
        result,
        example.objectives,
        artifact_store=artifact_store,
    )
    assert update.validate() == []
    assert len(update.memory.episodes) == len(
        {receipt.plan_digest for receipt in result.ledger.receipts}
    )
    assert {episode.source_lane for episode in update.memory.episodes}
    assert artifact_store.get_json(update.snapshot_artifact.digest) == json.loads(
        json.dumps(update.memory.to_dict())
    )
    _validate_wire("historical-memory.schema.json", update.memory.to_dict())
    _validate_wire("historical-memory-update.schema.json", update.to_dict())
    assert all(attribution.validate() == [] for attribution in result.lane_attributions)
    assert all(
        sum(
            attribution.primary and attribution.plan_digest == plan_digest
            for attribution in result.lane_attributions
        )
        == 1
        for plan_digest in {receipt.plan_digest for receipt in result.ledger.receipts}
    )


def test_negative_transfer_requires_matched_budget_and_opens_escape_lanes():
    budget_a = sha256_digest({"budget": "a"})
    budget_b = sha256_digest({"budget": "b"})
    insufficient = assess_negative_transfer(
        (
            LaneOutcome(
                "start.historical",
                "start.historical-replay",
                budget_a,
                0.1,
                True,
            ),
            LaneOutcome(
                "start.random",
                "start.random-history-blind",
                budget_b,
                0.8,
                True,
            ),
        )
    )
    assert insufficient.status == "assessment.insufficient-matched-evidence"

    miss = assess_negative_transfer(
        (
            LaneOutcome(
                "start.historical",
                "start.historical-replay",
                budget_a,
                0.1,
                True,
            ),
            LaneOutcome(
                "start.random",
                "start.random-history-blind",
                budget_a,
                0.8,
                True,
            ),
        )
    )
    assert miss.prior_miss and miss.regret is not None
    assert abs(miss.regret - 0.7) < 1e-12
    assert "start.random-history-blind" in miss.recommended_lanes
