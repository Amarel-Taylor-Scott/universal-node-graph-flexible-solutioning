from solutiongraph.llm_search import (
    ContextEnvelope,
    ModelRoute,
    Proposal,
    ProposalVote,
    QuestionSpace,
    SearchBudget,
    aggregate_votes,
    build_prompt_assignments,
    deduplicate_proposals,
    describe_search_space,
)


def test_question_space_is_huge_lazy_and_indexable():
    space = QuestionSpace()
    assert space.size == 417348771840
    assert len(space.sample(5, seed=7)) == 5
    assert space.at(0).validate() == []
    assert list(space.iter_all(limit=3)) == [space.at(0), space.at(1), space.at(2)]


def test_stratified_sampling_is_reproducible():
    space = QuestionSpace()
    left = space.stratified_sample(40, seed=11)
    right = space.stratified_sample(40, seed=11)
    assert left == right
    assert len({item.digest for item in left}) == 40
    assert len({item.family for item in left}) >= 20


def test_context_projection_enforces_blind_and_full_views():
    context = ContextEnvelope(
        task="predict target",
        schema="x:int",
        graph="graph",
        failures="fold leak",
        research="paper",
        history="old trials",
    )
    assert context.project("blind") == {}
    assert context.project("task_only") == {"task": "predict target"}
    full = context.project("full_history")
    assert set(full) == {"task", "schema", "graph", "failures", "research", "history"}


def test_build_assignments_cycles_models_and_respects_budget():
    routes = (
        ModelRoute(id="model.deepseek", model="deepseek-v4-flash"),
        ModelRoute(id="model.kimi", model="kimi-k2.7-code"),
    )
    assignments = build_prompt_assignments(
        space=QuestionSpace(),
        context=ContextEnvelope(task="regression", schema="a,b,target"),
        routes=routes,
        budget=SearchBudget(max_prompt_specs=10, max_model_calls=6, seed=3),
    )
    assert len(assignments) == 6
    assert [item.route.id for item in assignments] == [
        "model.deepseek",
        "model.kimi",
        "model.deepseek",
        "model.kimi",
        "model.deepseek",
        "model.kimi",
    ]


def test_votes_measure_support_and_disagreement():
    votes = (
        ProposalVote("proposal.one", "model.a", 0.9, 1.0, "strong"),
        ProposalVote("proposal.one", "model.b", 0.1, 1.0, "weak"),
    )
    summary = aggregate_votes(votes)[0]
    assert summary.weighted_support == 0.5
    assert summary.mean_confidence == 1.0
    assert round(summary.disagreement, 10) == 0.4
    assert summary.voter_count == 2


def test_proposal_dedupe_ignores_case_and_spacing_in_hypothesis():
    a = Proposal(
        id="proposal.a",
        kind="mutation",
        summary="x",
        hypothesis="Feature interaction helps",
        operations=("add_node",),
    )
    b = Proposal(
        id="proposal.b",
        kind="mutation",
        summary="y",
        hypothesis="  feature   interaction HELPS ",
        operations=("add_node",),
    )
    assert deduplicate_proposals((a, b)) == (a,)


def test_search_space_description_is_stable():
    description = describe_search_space()
    assert description["size"] == 417348771840
    assert description["axes"]["context_views"] == 12
