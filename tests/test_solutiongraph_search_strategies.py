from __future__ import annotations

import pytest

from solutiongraph import (
    AdmittedSpace,
    BeliefModel,
    CandidateWeight,
    ForbiddenCombination,
    SearchBudget,
    SearchEngine,
    SearchMode,
    sha256_digest,
)


def space(slots: int = 5, candidates: int = 3) -> AdmittedSpace:
    return AdmittedSpace(
        program_digest=sha256_digest("program"),
        registry_digest=sha256_digest("registry"),
        choices=tuple(
            (
                f"slot-{slot}",
                tuple(f"candidate-{slot}-{candidate}" for candidate in range(candidates)),
            )
            for slot in range(slots)
        ),
        decisions=(),
    )


def sprout_budget(seed: int = 17) -> SearchBudget:
    return SearchBudget(
        mode=SearchMode.SPROUT,
        evaluation_limit=12,
        result_limit=5,
        random_seed=seed,
        sampling_attempt_limit=80,
        mutation_probability=0.4,
    )


def test_random_sprouts_are_reproducible_budgeted_and_do_not_enumerate_huge_spaces():
    graph_space = space(slots=16, candidates=10)
    engine = SearchEngine()

    first = engine.search(graph_space, budget=sprout_budget())
    second = engine.search(graph_space, budget=sprout_budget())

    assert first == second
    assert first.total_cartesian_routes == 10**16
    assert first.evaluated_routes == 12
    assert first.unvisited_routes == 10**16 - 12
    assert first.sampling_attempts <= 80
    assert not first.complete and not first.optimality_proven
    assert first.to_dict()["budget"]["random_seed"] == 17


def test_sprout_search_refuses_hidden_or_irreproducible_budgets():
    engine = SearchEngine()
    graph_space = space()

    for budget in (
        SearchBudget(SearchMode.SPROUT, random_seed=1, sampling_attempt_limit=5),
        SearchBudget(SearchMode.SPROUT, evaluation_limit=2, sampling_attempt_limit=5),
        SearchBudget(SearchMode.SPROUT, evaluation_limit=2, random_seed=1),
    ):
        with pytest.raises(ValueError, match="sprout search requires"):
            engine.search(graph_space, budget=budget)


def test_sprouts_can_mutate_around_full_or_partial_suggested_starting_routes():
    graph_space = space(slots=4, candidates=3)
    anchor = {slot_id: candidates[0] for slot_id, candidates in graph_space.choices}
    report = SearchEngine().search(
        graph_space,
        budget=sprout_budget(),
        anchors=(anchor,),
    )

    assert report.evaluated_routes
    assert all(proposal.selection != anchor for proposal in report.proposals)
    assert all(
        sum(proposal.selection[slot] != candidate for slot, candidate in anchor.items()) >= 1
        for proposal in report.proposals
    )

    partial = {graph_space.choices[0][0]: graph_space.choices[0][1][0]}
    assert (
        SearchEngine()
        .search(
            graph_space,
            budget=sprout_budget(seed=4),
            anchors=(partial,),
        )
        .evaluated_routes
        == 12
    )


def test_sprout_search_preserves_prior_scoring_and_discloses_invalid_samples():
    constrained = space(slots=2, candidates=2)
    forbidden = ForbiddenCombination(
        "example.forbidden",
        (("slot-0", "candidate-0-0"), ("slot-1", "candidate-1-0")),
        "Known-incompatible pair.",
    )
    constrained = AdmittedSpace(
        constrained.program_digest,
        constrained.registry_digest,
        constrained.choices,
        constrained.decisions,
        (forbidden,),
    )
    beliefs = BeliefModel(
        revision="prior-v2",
        candidate_weights=(CandidateWeight("slot-0", "candidate-0-1", 5.0),),
    )
    report = SearchEngine().search(
        constrained,
        beliefs,
        SearchBudget(
            SearchMode.SPROUT,
            evaluation_limit=4,
            result_limit=4,
            random_seed=2,
            sampling_attempt_limit=30,
        ),
    )

    assert report.proposals[0].selection["slot-0"] == "candidate-0-1"
    assert report.invalid_samples >= 1
    assert report.evaluated_routes == 3
    assert not report.complete


def test_sprout_anchors_must_reference_only_admitted_candidates():
    graph_space = space()
    with pytest.raises(ValueError, match="unknown slots"):
        SearchEngine().search(
            graph_space,
            budget=sprout_budget(),
            anchors=({"unknown": "candidate"},),
        )
    with pytest.raises(ValueError, match="non-admitted"):
        SearchEngine().search(
            graph_space,
            budget=sprout_budget(),
            anchors=({"slot-0": "not-admitted"},),
        )
