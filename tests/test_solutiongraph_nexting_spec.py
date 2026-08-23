from __future__ import annotations

from solutiongraph.model import sha256_digest
from solutiongraph.nexting.contracts import (
    ActionResult,
    KnowledgeReference,
    KnowledgeState,
    NextActionProposal,
)
from solutiongraph.nexting.routing import (
    ActionRoute,
    ActionRouterSpec,
    FunctionalActionHandler,
    HandlerRegistry,
    RoutedActionExecutor,
)
from solutiongraph.nexting.spec import (
    CellAuthority,
    CellRunRequest,
    CellWorkspace,
    MissionContract,
    SolverCellSpec,
)


def _state() -> KnowledgeState:
    return KnowledgeState(
        id="state.routing-test",
        revision="1",
        goal="Route one bounded action.",
    )


def _proposal(*, target_ref: str = "graph.model") -> NextActionProposal:
    return NextActionProposal(
        id="proposal.routing-test",
        question_id="question.routing-test",
        action_kind="next.mutate-graph",
        title="Mutate model graph",
        rationale="Test a compiler-gated graph change.",
        strategy_id="strategy.routing-test",
        target_ref=target_ref,
        payload={"operation": "replace-model"},
        confidence=1.0,
        uncertainty=0.0,
        tags=("proposal.test",),
    )


def test_portable_solver_cell_spec_is_content_addressed() -> None:
    mission = MissionContract(
        id="mission.validation-design",
        version="1.0.0",
        goal="Select a leakage-resistant validation contract.",
        success_predicate_refs=("predicate.validation-selected",),
        objective_refs=("metric.validation-stability",),
        required_output_kinds=("knowledge.validation-contract",),
    )
    authority = CellAuthority(
        id="authority.validation-cell",
        allowed_action_kinds=(
            "next.run-probe",
            "next.compare",
            "next.stop",
        ),
        allowed_runtime_ids=("runtime.local-python",),
        maximum_child_depth=4,
    )
    workspace = CellWorkspace(
        id="workspace.validation-cell",
        knowledge_store_ref="store.knowledge",
        artifact_store_ref="store.artifacts",
        event_journal_ref="journal.nexting",
        history_refs=("history.kaggle",),
        blueprint_catalog_refs=("catalog.validation-blueprints",),
    )
    spec = SolverCellSpec(
        id="cell.validation-design",
        version="1.0.0",
        title="Validation design specialist",
        mission=mission,
        authority=authority,
        workspace=workspace,
        strategy_ids=("strategy.validation-rules", "strategy.validation-llm"),
        question_factory_ref="factory.validation-next-question",
        strategy_selection_policy_ref="policy.validation-strategy-selection",
        context_policy_ref="context.selective",
        action_router_ref="router.validation-cell",
        state_reducer_ref="reducer.append-only",
        role_profile_refs=("role.data-scientist", "role.leakage-auditor"),
    )
    assert not spec.validate()
    assert spec.digest == sha256_digest(spec.to_dict())

    request = CellRunRequest(
        id="cell-run.validation-design-1",
        cell_spec_digest=spec.digest,
        initial_state_digest=_state().digest,
        delegated_scope_ref="scope.validation",
        random_seed=17,
    )
    assert not request.validate()
    assert request.digest.startswith("sha256:")


def test_router_prefers_more_specific_target_route() -> None:
    calls: list[str] = []

    def generic_handler(proposal, state) -> ActionResult:
        calls.append("generic")
        return ActionResult(proposal.id, "succeeded")

    def model_handler(proposal, state) -> ActionResult:
        calls.append("model")
        reference = KnowledgeReference(
            id="knowledge.model-route",
            kind="knowledge.test-artifact",
            digest=sha256_digest("model-route"),
        )
        return ActionResult(
            proposal.id,
            "succeeded",
            produced_references=(reference,),
        )

    handlers = HandlerRegistry(
        (
            FunctionalActionHandler("handler.generic-graph", generic_handler),
            FunctionalActionHandler("handler.model-graph", model_handler),
        )
    )
    router = RoutedActionExecutor(
        ActionRouterSpec(
            id="router.test",
            version="1.0.0",
            routes=(
                ActionRoute(
                    id="route.generic-graph",
                    handler_id="handler.generic-graph",
                    action_kinds=("next.mutate-graph",),
                ),
                ActionRoute(
                    id="route.model-graph",
                    handler_id="handler.model-graph",
                    action_kinds=("next.mutate-graph",),
                    target_prefixes=("graph.model",),
                ),
            ),
        ),
        handlers,
    )
    result = router.execute(_proposal(), _state())
    assert result.outcome == "succeeded"
    assert calls == ["model"]
    assert result.details["route_resolution"]["route_id"] == "route.model-graph"


def test_router_blocks_equal_specificity_ambiguity() -> None:
    handler = FunctionalActionHandler(
        "handler.same",
        lambda proposal, state: ActionResult(proposal.id, "succeeded"),
    )
    router = RoutedActionExecutor(
        ActionRouterSpec(
            id="router.ambiguous",
            version="1.0.0",
            routes=(
                ActionRoute(
                    id="route.ambiguous-a",
                    handler_id="handler.same",
                    action_kinds=("next.mutate-graph",),
                    priority=10,
                ),
                ActionRoute(
                    id="route.ambiguous-b",
                    handler_id="handler.same",
                    action_kinds=("next.mutate-graph",),
                    priority=10,
                ),
            ),
        ),
        HandlerRegistry((handler,)),
    )
    result = router.execute(_proposal(), _state())
    assert result.outcome == "blocked"
    assert result.failure_class == "next.action-route-unresolved"
