from __future__ import annotations

import json

import pytest

from solutiongraph.proposal_space import (
    ContextBundle,
    ContextExposure,
    ProposalKind,
    QuestionValueModel,
    deduplicate_proposals,
    default_kaggle_question_space,
    parse_proposals,
)


def _diagnostic_response(*, title: str = "Audit leakage") -> str:
    return json.dumps({
        "kind": ProposalKind.DIAGNOSTIC.value,
        "title": title,
        "rationale": "The current validation may not match the hidden distribution.",
        "hypothesis": "A group-aware split will lower optimistic bias.",
        "target_ref": "graph.current",
        "payload": {
            "findings": ["possible group leakage"],
            "evidence_needed": ["group overlap report"],
            "priority_order": ["audit groups", "rebuild folds"],
        },
        "confidence": 0.7,
        "uncertainty": 0.4,
        "evidence_refs": [],
        "parent_proposal_ids": [],
        "risk_flags": ["risk.validation-mismatch"],
    })


def test_default_space_is_massive_lazy_and_reproducible() -> None:
    space = default_kaggle_question_space()
    assert space.count > 1_000_000_000
    first = tuple(space.iter_variants(limit=32, seed=17, start=3))
    replay = tuple(space.iter_variants(limit=32, seed=17, start=3))
    other = tuple(space.iter_variants(limit=32, seed=18, start=3))
    assert [item.id for item in first] == [item.id for item in replay]
    assert len({item.id for item in first}) == 32
    assert [item.id for item in first] != [item.id for item in other]


def test_question_exposure_change_creates_a_new_identity() -> None:
    question = default_kaggle_question_space().variant_at(0, seed=1)
    blind = question.with_exposure(ContextExposure.NONE)
    full = question.with_exposure(ContextExposure.FULL)
    assert blind.id != full.id
    assert blind.context_exposure == ContextExposure.NONE
    assert full.context_exposure == ContextExposure.FULL


def test_context_projection_never_releases_hidden_sections() -> None:
    bundle = ContextBundle(
        "context.test",
        sections=(("task", "predict target"), ("graph_summary", "three obligations")),
        hidden_sections=(("private_holdout", "SECRET LABELS"),),
    )
    assert not bundle.validate()
    projection = bundle.project(ContextExposure.FULL)
    assert "predict target" in projection.text
    assert "three obligations" in projection.text
    assert "SECRET LABELS" not in projection.text
    assert "private_holdout" not in projection.text


def test_strict_proposal_parse_and_exact_semantic_deduplication() -> None:
    raw = json.dumps({
        "proposals": [json.loads(_diagnostic_response()), json.loads(_diagnostic_response())]
    })
    proposals = parse_proposals(
        raw,
        proposer_id="swarm.lane.fixture",
        question_variant_id="question.variant.fixture",
        model_id="fixture-model",
    )
    assert len(proposals) == 2
    retained, duplicates = deduplicate_proposals(proposals)
    assert len(retained) == 1
    assert duplicates == ((proposals[1].id, proposals[0].id),)


def test_proposal_parser_rejects_unknown_payload_fields() -> None:
    value = json.loads(_diagnostic_response())
    value["payload"]["self_approve"] = True
    with pytest.raises(ValueError, match="unknown"):
        parse_proposals(
            json.dumps(value),
            proposer_id="swarm.lane.fixture",
            question_variant_id="question.variant.fixture",
        )


def test_question_value_model_learns_factor_preferences_without_removing_exploration() -> None:
    space = default_kaggle_question_space()
    preferred = space.variant_at(0, seed=3)
    weak = space.variant_at(space.count // 2, seed=3)
    model = QuestionValueModel()
    for _ in range(12):
        model = model.update(preferred, "model-endpoint.primary", 1.0)
        model = model.update(weak, "model-endpoint.primary", -0.5)
    assert model.score(preferred, model_endpoint_id="model-endpoint.primary", exploration=0.0) > model.score(
        weak, model_endpoint_id="model-endpoint.primary", exploration=0.0
    )
