from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

from jsonschema import Draft202012Validator
from referencing import Registry as SchemaRegistry
from referencing import Resource

from solutiongraph.catalog import catalog_documents
from solutiongraph.cli import main
from solutiongraph.schemas import load_all_schemas
from solutiongraph.specialized import (
    REFERENCE_SPECIALIZED_PACK_REGISTRY,
    REFERENCE_SPECIALIZED_PACKS,
    SPECIALIZED_PACK_ENTRY_POINT_GROUP,
    PackageCompositionRequest,
    TaskPackageRequest,
    compose_specialized_packs,
    merge_specialized_packs,
    recommend_specialized_packs,
    reference_specialized_asset_inventory,
    validate_specialized_pack_catalog,
)
from solutiongraph.specialized import discovery as pack_discovery


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


def test_specialized_pack_registry_is_strict_asset_resolved_and_extraction_ready():
    registry = REFERENCE_SPECIALIZED_PACK_REGISTRY
    assert registry.validate() == []
    assert validate_specialized_pack_catalog(registry) == []
    assert len(REFERENCE_SPECIALIZED_PACKS) == 26
    assert sum(len(pack.recipes) for pack in REFERENCE_SPECIALIZED_PACKS) == 89
    assert sum(len(pack.profiler_features) for pack in REFERENCE_SPECIALIZED_PACKS) == 127
    assert sum(len(pack.metrics) for pack in REFERENCE_SPECIALIZED_PACKS) == 118
    assert sum(len(pack.gates) for pack in REFERENCE_SPECIALIZED_PACKS) == 55
    assert {pack.id for pack in REFERENCE_SPECIALIZED_PACKS} == {
        "specialized-pack.data-engineering",
        "specialized-pack.data-analysis",
        "specialized-pack.data-science",
        "specialized-pack.ml-engineering",
        "specialized-pack.llm-engineering",
        "specialized-pack.software-engineering",
        "specialized-pack.operations",
        "specialized-pack.llm-evaluation-safety",
        "specialized-pack.cybersecurity",
        "specialized-pack.privacy-governance-compliance",
        "specialized-pack.document-intelligence",
        "specialized-pack.media-intelligence",
        "specialized-pack.three-d-simulation",
        "specialized-pack.game-engineering",
        "specialized-pack.geospatial-temporal",
        "specialized-pack.robotics-control",
        "specialized-pack.scientific-computing-digital-twins",
        "specialized-pack.embedded-iot",
        "specialized-pack.healthcare-biomedical",
        "specialized-pack.finance-risk-fraud",
        "specialized-pack.supply-chain-planning",
        "specialized-pack.product-experimentation",
        "specialized-pack.search-recommendation",
        "specialized-pack.knowledge-research",
        "specialized-pack.education-assessment",
        "specialized-pack.creative-content-production",
    }
    assert all(pack.current_distribution == "browsergraph" for pack in registry.packs)
    assert all(pack.extraction_target.startswith("solutiongraph-pack-") for pack in registry.packs)
    assert all(
        pack.python_module.startswith("solutiongraph.specialized.") for pack in registry.packs
    )
    assert all(
        any(item.easy_to_compute for item in pack.profiler_features) for pack in registry.packs
    )
    assert all(
        any(
            item.value_kind == "vector"
            and item.mode == "model"
            and item.permissions == ("model.invoke",)
            and item.requirements == ("requirement.exact-embedding-space-identity",)
            for item in pack.profiler_features
        )
        for pack in registry.packs
    )
    assert reference_specialized_asset_inventory().digest.startswith("sha256:")


def test_specialized_pack_wire_schemas_cover_registry_requests_and_reports():
    registry = REFERENCE_SPECIALIZED_PACK_REGISTRY
    _validate_wire("specialized-pack-registry.schema.json", registry.to_dict())
    for pack in registry.packs:
        _validate_wire("specialized-pack.schema.json", pack.to_dict())

    recommendation = recommend_specialized_packs(
        TaskPackageRequest(
            "package-request.schema-test",
            "Clean and enrich company address data with GIS and time evidence",
        ),
        registry,
    )
    _validate_wire("specialized-task-request.schema.json", recommendation.request.to_dict())
    _validate_wire("specialized-recommendation-report.schema.json", recommendation.to_dict())

    composition = compose_specialized_packs(
        PackageCompositionRequest(
            "composition-request.schema-test",
            ("artifact.raw-records",),
            ("artifact.deployed-model",),
            pack_ids=(
                "specialized-pack.data-engineering",
                "specialized-pack.data-science",
                "specialized-pack.ml-engineering",
            ),
            max_steps=4,
            state_budget=1000,
            candidate_limit=3,
        ),
        registry,
    )
    _validate_wire("specialized-composition-request.schema.json", composition.request.to_dict())
    _validate_wire("specialized-composition-report.schema.json", composition.to_dict())


def test_recommendation_is_diverse_deterministic_and_keeps_every_pack_visible():
    registry = REFERENCE_SPECIALIZED_PACK_REGISTRY
    examples = (
        (
            "Clean company addresses, validate ZIP codes, and enrich GIS and event time",
            "specialized-pack.data-engineering",
        ),
        (
            "Analyze user cohorts, funnels, retention, and user flows",
            "specialized-pack.data-analysis",
        ),
        (
            "Build a leakage-safe robust regression model with conformal intervals",
            "specialized-pack.data-science",
        ),
        (
            "Deploy and monitor a model with drift detection and verified rollback",
            "specialized-pack.ml-engineering",
        ),
        (
            "Build a RAG evaluation and red-team harness with LLM judges",
            "specialized-pack.llm-engineering",
        ),
        (
            "Repair a backend API repository, run regression tests, and stage a release",
            "specialized-pack.software-engineering",
        ),
        (
            "Triage an SRE incident using observability, SLOs, and a recovery runbook",
            "specialized-pack.operations",
        ),
    )
    for index, (description, expected) in enumerate(examples):
        request = TaskPackageRequest(f"package-request.case-{index}", description)
        first = recommend_specialized_packs(request, registry, selection_limit=1)
        second = recommend_specialized_packs(request, registry, selection_limit=1)
        assert first == second
        assert first.recommended_pack_ids == (expected,)
        assert first.recommendations[0].pack_id == expected
        assert len(first.recommendations) == len(registry.packs)
        assert first.validate(registry) == []
        assert "does not select nodes" in first.claim_boundary


def test_exact_categories_capabilities_preferences_exclusions_and_interfaces_are_visible():
    registry = REFERENCE_SPECIALIZED_PACK_REGISTRY
    report = recommend_specialized_packs(
        TaskPackageRequest(
            "package-request.structured",
            "A typed task",
            category_ids=("dag.generate.synthetic.adversarial",),
            input_kind_ids=("artifact.llm-system",),
            output_kind_ids=("artifact.llm-evaluation-report",),
            required_capability_ids=("llm.red-team",),
            preferred_pack_ids=("specialized-pack.llm-engineering",),
            excluded_pack_ids=("specialized-pack.software-engineering",),
        ),
        registry,
        selection_limit=2,
    )
    winner = report.recommendations[0]
    assert winner.pack_id == "specialized-pack.llm-engineering"
    assert winner.status == "candidate"
    assert winner.matched_capability_ids == ("llm.red-team",)
    assert winner.matched_input_kind_ids == ("artifact.llm-system",)
    assert winner.matched_output_kind_ids == ("artifact.llm-evaluation-report",)
    excluded = next(
        item
        for item in report.recommendations
        if item.pack_id == "specialized-pack.software-engineering"
    )
    assert excluded.status == "excluded"
    assert excluded.score == 0.0


def test_frontier_verticals_are_recommended_without_effectful_sibling_poisoning():
    registry = REFERENCE_SPECIALIZED_PACK_REGISTRY
    examples = (
        ("Defensive cybersecurity investigation of security telemetry", "cybersecurity"),
        ("Validate a 3D mesh, materials, collision, and LOD budget", "three-d-simulation"),
        ("Run deterministic game replay and balance playtests", "game-engineering"),
        ("Validate robot motion planning in safety simulation", "robotics-control"),
        ("Validate IoT telemetry and stage firmware rollout", "embedded-iot"),
        ("Reconcile a financial ledger and score fraud risk", "finance-risk-fraud"),
        ("Build hybrid search and recommendation ranking", "search-recommendation"),
        ("Author curriculum and validate assessment rubrics", "education-assessment"),
        ("Produce creative campaign content with brand and rights review", "creative-content-production"),
    )
    for index, (description, suffix) in enumerate(examples):
        report = recommend_specialized_packs(
            TaskPackageRequest(f"package-request.frontier-{index}", description),
            registry,
            selection_limit=1,
        )
        assert report.recommended_pack_ids == (f"specialized-pack.{suffix}",)

    read_only = recommend_specialized_packs(
        TaskPackageRequest(
            "package-request.cyber-read-only",
            "Investigate suspicious security telemetry and preserve evidence",
        ),
        registry,
        selection_limit=1,
    )
    assert read_only.recommended_pack_ids == ("specialized-pack.cybersecurity",)
    assert read_only.recommendations[0].blocked_permissions == ()

    effectful = recommend_specialized_packs(
        TaskPackageRequest(
            "package-request.cyber-response",
            "Contain and recover a security incident",
            output_kind_ids=("artifact.recovery-evidence",),
        ),
        registry,
        selection_limit=1,
    )
    cyber = next(
        item for item in effectful.recommendations
        if item.pack_id == "specialized-pack.cybersecurity"
    )
    assert cyber.status == "partial"
    assert cyber.blocked_permissions == ("system.write",)


def test_typed_recipe_composition_finds_cross_pack_routes_without_implicit_conversion():
    registry = REFERENCE_SPECIALIZED_PACK_REGISTRY
    report = compose_specialized_packs(
        PackageCompositionRequest(
            "composition-request.raw-to-deployed-model",
            ("artifact.raw-records",),
            ("artifact.deployed-model",),
            pack_ids=(
                "specialized-pack.data-engineering",
                "specialized-pack.data-science",
                "specialized-pack.ml-engineering",
            ),
            max_steps=4,
            state_budget=10000,
            candidate_limit=10,
        ),
        registry,
    )
    assert report.candidates
    assert report.expanded_transition_count > 0
    assert report.incompatible_transition_count > 0
    assert report.candidate_limit_exhausted
    assert report.queued_unexpanded_state_count > 0
    assert report.validate(registry) == []
    for candidate in report.candidates:
        available = {"artifact.raw-records"}
        for step in candidate.steps:
            assert set(step.input_kind_ids) <= available
            available.update(step.output_kind_ids)
        assert "artifact.deployed-model" in available
        assert len({step.recipe_id for step in candidate.steps}) == len(candidate.steps)
    assert any(
        tuple(step.pack_id for step in candidate.steps)
        == (
            "specialized-pack.data-engineering",
            "specialized-pack.data-science",
            "specialized-pack.ml-engineering",
        )
        for candidate in report.candidates
    )


def test_composition_failure_and_budgets_are_reported_instead_of_inventing_adapters():
    registry = REFERENCE_SPECIALIZED_PACK_REGISTRY
    report = compose_specialized_packs(
        PackageCompositionRequest(
            "composition-request.no-path",
            ("artifact.raw-records",),
            ("artifact.control-evidence",),
            pack_ids=("specialized-pack.data-science",),
            max_steps=2,
            state_budget=10,
            candidate_limit=2,
        ),
        registry,
    )
    assert report.candidates == ()
    assert "artifact.control-evidence" in report.unresolved_goal_kind_ids
    assert report.total_recipe_count == 5
    assert "no implicit conversion" in report.claim_boundary.lower()


def test_provider_discovery_does_not_import_until_explicit_load(monkeypatch, capsys):
    loaded: list[str] = []
    pack = REFERENCE_SPECIALIZED_PACKS[0]

    class Point:
        name = "test-pack"
        value = "test_provider:PACK"
        group = SPECIALIZED_PACK_ENTRY_POINT_GROUP
        dist = SimpleNamespace(name="solutiongraph-pack-test")

        @staticmethod
        def load():
            loaded.append("loaded")
            return pack

    monkeypatch.setattr(pack_discovery, "_entry_points", lambda: (Point(),))
    references = pack_discovery.discover_installed_pack_providers()
    assert loaded == []
    assert references[0].distribution == "solutiongraph-pack-test"
    result = pack_discovery.load_installed_pack_provider(references[0])
    assert loaded == ["loaded"]
    assert result.loaded
    assert result.packs == (pack,)

    assert main(["packages", "list", "--include-installed", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert loaded == ["loaded", "loaded"]
    assert len(payload["packs"]) == len(REFERENCE_SPECIALIZED_PACKS)
    assert payload["id"] == "registry.merged-specialized-packs"


def test_merging_deduplicates_exact_packs_and_rejects_conflicting_identity():
    registry = REFERENCE_SPECIALIZED_PACK_REGISTRY
    pack = registry.packs[0]
    merged = merge_specialized_packs(registry, (pack,))
    assert len(merged.packs) == len(registry.packs)
    conflicting = replace(pack, title=pack.title + " changed")
    try:
        merge_specialized_packs(registry, (conflicting,))
    except ValueError as exc:
        assert "conflicting specialized pack definition" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("conflicting provider was accepted")

    different_version = replace(pack, version="999.0.0")
    try:
        merge_specialized_packs(registry, (different_version,))
    except ValueError as exc:
        assert "conflicting specialized pack definition" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("ambiguous second pack version was accepted")

    duplicate_recipe = replace(
        registry.packs[1],
        recipes=(pack.recipes[0], *registry.packs[1].recipes[1:]),
    )
    duplicate_registry = replace(
        registry,
        packs=(registry.packs[0], duplicate_recipe, *registry.packs[2:]),
    )
    assert any(
        "recipes ids must be globally unique" in problem
        for problem in duplicate_registry.validate()
    )


def test_catalog_cli_and_distribution_entry_points_publish_the_specialized_layer(capsys):
    documents = catalog_documents()
    index = documents["specialized-packs/index.json"]
    assert index["pack_count"] == 26
    assert index["recipe_count"] == 89
    assert documents["index.json"]["specialized_packages"]["gate_count"] == 55
    assert all(
        f"specialized-packs/packs/{pack.id}.json" in documents
        for pack in REFERENCE_SPECIALIZED_PACKS
    )

    assert main(["packages", "list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["packs"]) == 26
    assert (
        main(
            [
                "packages",
                "recommend",
                "LLM RAG red-team evaluation harness",
                "--limit",
                "1",
                "--json",
            ]
        )
        == 0
    )
    recommendation = json.loads(capsys.readouterr().out)
    assert recommendation["recommended_pack_ids"] == ["specialized-pack.llm-engineering"]
    assert len(recommendation["recommendations"]) == 26

    root = Path(__file__).parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    points = project["project"]["entry-points"][SPECIALIZED_PACK_ENTRY_POINT_GROUP]
    assert set(points) == {pack.entry_point_name for pack in REFERENCE_SPECIALIZED_PACKS}
    assert set(points.values()) == {
        f"{pack.python_module}:PACK" for pack in REFERENCE_SPECIALIZED_PACKS
    }
