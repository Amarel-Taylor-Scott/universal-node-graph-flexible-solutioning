from __future__ import annotations

import json
from pathlib import Path

import pytest

from solutiongraph.authoring import define_python_node, enumerate_candidates
from solutiongraph.benchmark_library import REFERENCE_BENCHMARKS, run_benchmark
from solutiongraph.benchmarking import write_benchmark_report
from solutiongraph.cli import main
from solutiongraph.model import ParameterSpec, Port, ValueType
from solutiongraph.stdlib_pack import (
    STANDARD_LIBRARY_CANDIDATES,
    STANDARD_LIBRARY_DEFINITIONS,
    STANDARD_LIBRARY_DESCRIPTORS,
    STANDARD_LIBRARY_NODE_PACK,
    STANDARD_LIBRARY_NODE_SPECS,
    STANDARD_LIBRARY_REGISTRY,
)

ROOT = Path(__file__).parents[1]
VALUE = ValueType("test.authoring-value")


def scale_value(value: int, factor: int = 1) -> int:
    return value * factor


def requires_hidden_argument(value: int, hidden: int) -> int:
    return value + hidden


def test_python_node_authoring_checks_signature_hashes_source_and_enumerates_exactly():
    definition = define_python_node(
        node_id="test.scale-value",
        function=scale_value,
        inputs=(Port("value", VALUE),),
        outputs=(Port("value", VALUE),),
        capabilities=("test.scale",),
        description="Scale a test value.",
        parameters=(
            ParameterSpec("factor", "integer", default=1, choices=(1, 2, 4)),
        ),
    )
    candidates = enumerate_candidates(definition.spec)
    assert definition.validate() == []
    assert [candidate.parameters["factor"] for candidate in candidates] == [1, 2, 4]
    assert len({candidate.id for candidate in candidates}) == 3
    assert all(candidate.validate(definition.spec) == [] for candidate in candidates)
    with pytest.raises(ValueError, match="declared parameter grid has 3"):
        enumerate_candidates(definition.spec, max_candidates=2)

    with pytest.raises(ValueError, match="undeclared arguments: hidden"):
        define_python_node(
            node_id="test.invalid-hidden",
            function=requires_hidden_argument,
            inputs=(Port("value", VALUE),),
            outputs=(Port("value", VALUE),),
            capabilities=("test.invalid",),
            description="Invalid signature fixture.",
        )


def test_standard_library_pack_is_searchable_strict_and_has_explicit_noop_candidates():
    assert len(STANDARD_LIBRARY_NODE_SPECS) == len(STANDARD_LIBRARY_DEFINITIONS) == 19
    assert len(STANDARD_LIBRARY_CANDIDATES) == 32
    assert STANDARD_LIBRARY_NODE_PACK.validate() == []
    assert all(definition.validate() == [] for definition in STANDARD_LIBRARY_DEFINITIONS)
    assert all(
        descriptor.validate(node) == []
        for node, descriptor in zip(
            STANDARD_LIBRARY_NODE_SPECS,
            STANDARD_LIBRARY_DESCRIPTORS,
            strict=True,
        )
    )
    identity = next(node for node in STANDARD_LIBRARY_NODE_SPECS if node.id == "stdlib.records.identity")
    assert set(identity.capabilities).issuperset(
        {
            "records.normalize-keys",
            "records.trim-strings",
            "records.normalize-missing",
            "records.casefold-fields",
            "records.deduplicate",
            "records.require-fields",
        }
    )
    assert STANDARD_LIBRARY_REGISTRY.digest.startswith("sha256:")


def test_every_bundled_benchmark_and_solution_pack_has_an_exact_valid_closure():
    assert len(REFERENCE_BENCHMARKS) == 6
    assert sum(len(bundle.definition.task_cases) for bundle in REFERENCE_BENCHMARKS) == 24
    assert all(bundle.validate() == [] for bundle in REFERENCE_BENCHMARKS)
    assert all(
        bundle.definition.task_contract.oracle.candidate_readable
        and bundle.definition.suite.claim_scope == "mechanism-fixture"
        and bundle.solution_pack.readiness == "executable-fixture"
        and bundle.solution_pack.benchmark_suite_digests
        for bundle in REFERENCE_BENCHMARKS
    )
    stdlib = REFERENCE_BENCHMARKS[-1]
    assert stdlib.definition.example.compile()[0].route_count_upper_bound == 1728
    balanced = next(
        arm
        for arm in stdlib.definition.suite.arms
        if arm.id == "arm.solver-balanced"
    )
    assert balanced.anchor_route_ids == ("robust",)


def test_benchmark_executes_controls_search_holdout_and_writes_offline_report(tmp_path):
    report = run_benchmark("benchmark.stdlib-data-quality")
    assert report.ok
    results = {item.arm_id: item for item in report.arm_results}
    assert results["arm.fixed-control"].acceptance_rate < 1.0
    assert results["arm.fixed-candidate"].acceptance_rate == 1.0
    assert results["arm.solver-quick"].status == "completed-no-accepted-route"
    assert results["arm.solver-balanced"].acceptance_rate == 1.0
    assert results["arm.solver-balanced"].holdout_confirmed
    assert not results["arm.solver-balanced"].optimality_proven
    assert results["arm.solver-balanced"].evaluated_plan_count < 1728

    target = write_benchmark_report(report, tmp_path / "report.html")
    html = target.read_text(encoding="utf-8")
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "Claim boundary" in html
    assert "Champion route, left to right" in html
    assert "candidate.stdlib.records" in html
    assert report.digest in html


def test_benchmark_and_pack_cli_create_copyable_html_and_json(tmp_path, capsys):
    assert main(["benchmarks", "list"]) == 0
    assert "benchmark.stdlib-data-quality" in capsys.readouterr().out
    assert main(["packs", "show", "solution-pack.stdlib-data-quality"]) == 0
    assert "closure: valid" in capsys.readouterr().out

    html_path = tmp_path / "arena.html"
    json_path = tmp_path / "arena.json"
    assert main(
        [
            "benchmarks",
            "run",
            "benchmark.document-extraction",
            "--report-html",
            str(html_path),
            "--report-json",
            str(json_path),
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "optimality=not-claimed" in output
    assert html_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["ok"]
    assert payload["claim_scope"] == "mechanism-fixture"
    assert payload["suite"]["id"] == "benchmark.document-extraction"


def test_checked_in_benchmark_report_is_self_contained_and_under_one_megabyte():
    target = ROOT / "examples" / "universal-dag-benchmark-report.html"
    html = target.read_text(encoding="utf-8")
    assert target.stat().st_size < 1_000_000
    assert "benchmark.stdlib-data-quality" in html
    assert "Every" not in html or "route" in html
    assert "fetch(" not in html
