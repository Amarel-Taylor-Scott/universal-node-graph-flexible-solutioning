"""Bundled cross-domain benchmark fixtures and portable solution packs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from solutiongraph.benchmarking import (
    BenchmarkArm,
    BenchmarkDefinition,
    BenchmarkRunner,
    BenchmarkSuite,
)
from solutiongraph.compiler import Compiler
from solutiongraph.discovery import NodePackManifest
from solutiongraph.examples import get_example
from solutiongraph.experiments import ExperimentCase
from solutiongraph.model import FrozenPlan, Port, sha256_digest
from solutiongraph.pack_library import REAL_WORLD_EXAMPLE_NODE_PACK, REPOSITORY_SOURCE
from solutiongraph.stdlib_pack import STANDARD_LIBRARY_NODE_PACK
from solutiongraph.tasking import (
    SolutionPackManifest,
    TaskCaseSpec,
    TaskConstraint,
    TaskContract,
    TaskOracle,
    validate_solution_pack_closure,
)


@dataclass(frozen=True)
class BenchmarkBundle:
    """One executable benchmark plus the portable closure that describes it."""

    definition: BenchmarkDefinition
    solution_pack: SolutionPackManifest
    baseline_plans: tuple[FrozenPlan, ...]
    node_pack: NodePackManifest

    @property
    def id(self) -> str:
        return self.definition.suite.id

    def validate(self) -> list[str]:
        problems = self.definition.validate()
        problems.extend(
            validate_solution_pack_closure(
                self.solution_pack,
                task_contract=self.definition.task_contract,
                programs=(self.definition.example.program,),
                registries=(self.definition.example.registry,),
                node_packs=(self.node_pack,),
                task_cases=self.definition.task_cases,
                evaluator_digests=(
                    self.definition.task_contract.oracle.evaluator_digest,
                ),
                baseline_plans=self.baseline_plans,
                benchmark_suite_digests=(self.definition.suite.digest,),
            )
        )
        return problems


def _bundle(
    *,
    suffix: str,
    example_id: str,
    description: str,
    cases: tuple[tuple[str, str, dict[str, Any], str], ...],
    fixed_route_ids: tuple[str, str],
    tags: tuple[str, ...],
    node_pack: NodePackManifest = REAL_WORLD_EXAMPLE_NODE_PACK,
) -> BenchmarkBundle:
    example = get_example(example_id)
    verifier = example.case.verifier
    verifier_function = getattr(verifier, "function", None)
    implementation_ref = (
        f"python://{verifier_function.__module__}:{verifier_function.__name__}"
        if verifier_function is not None
        else f"verifier://{verifier.identifier}"
    )
    runtime_cases = tuple(
        ExperimentCase(
            id=f"case.benchmark.{suffix}.{case_suffix}",
            inputs=inputs,
            verifier=verifier,
        )
        for case_suffix, _, inputs, _ in cases
    )
    portable_cases = tuple(
        TaskCaseSpec(
            id=runtime.id,
            split=split,
            input_digest=sha256_digest(inputs),
            fixture_ref=f"inline://solutiongraph/benchmark/{suffix}/{case_suffix}",
            description=case_description,
            tags=("fixture.synthetic", *tags),
            extensions=(("fixture.license", "CC0-1.0"),),
        )
        for runtime, (case_suffix, split, inputs, case_description) in zip(
            runtime_cases, cases, strict=True
        )
    )
    task = TaskContract(
        id=f"task.benchmark.{suffix}",
        version="1.0.0",
        title=example.title,
        intent=example.program.task,
        inputs=tuple(
            Port(item.name, item.value_type, description=f"Task input {item.name}.")
            for item in example.program.inputs
        ),
        outputs=tuple(
            Port(item.name, item.value_type, description=f"Task output {item.name}.")
            for item in example.program.outputs
        ),
        success_contract=example.program.success_contract,
        oracle=TaskOracle(
            id=verifier.identifier,
            version="1.0.0",
            kind="property",
            evaluator_digest=verifier.implementation_digest,
            implementation_ref=implementation_ref,
            independence="separate-implementation",
            candidate_readable=True,
            description=(
                "Bundled deterministic acceptance oracle. It is separate from node "
                "implementations but readable because these are transparent fixtures."
            ),
        ),
        objectives=example.objectives,
        constraints=(
            TaskConstraint(
                id="constraint.acceptance",
                target="verification.accepted",
                operator="eq",
                value=True,
                description="A route is eligible only when the independent oracle accepts it.",
            ),
        ),
        allowed_effects=example.program.allowed_effects,
        granted_permissions=example.program.granted_permissions,
        case_ids=tuple(item.id for item in portable_cases),
        tags=("benchmark.synthetic", *tags),
        external_requirements=(
            "These bundled synthetic cases prove framework mechanics; replace them with "
            "representative, licensed development and hidden holdout data before making "
            "production or domain-performance claims.",
        ),
        extensions=(("benchmark.claim-scope", "mechanism-fixture"),),
    )
    arms = (
        BenchmarkArm(
            "arm.fixed-control",
            "Fixed control",
            "Execute the declared control route without route search.",
            "fixed-route",
            route_id=fixed_route_ids[0],
        ),
        BenchmarkArm(
            "arm.fixed-candidate",
            "Fixed candidate",
            "Execute the stronger hand-authored candidate without route search.",
            "fixed-route",
            route_id=fixed_route_ids[1],
        ),
        BenchmarkArm(
            "arm.solver-quick",
            "Quick solver",
            "Use one prior-guided proposal under the explicit quick allocation.",
            "solver-profile",
            solver_profile="quick",
        ),
        BenchmarkArm(
            "arm.solver-balanced",
            "Balanced solver",
            "Use prior plus bounded beam search and retain evidence-diverse fallbacks.",
            "solver-profile",
            solver_profile="balanced",
            anchor_route_ids=(fixed_route_ids[1],),
        ),
    )
    suite = BenchmarkSuite(
        id=f"benchmark.{suffix}",
        version="1.0.0",
        title=f"{example.title} arena",
        description=description,
        example_id=example.id,
        task_contract_digest=task.digest,
        program_digest=example.program.digest,
        registry_digest=example.registry.digest,
        task_case_digests=tuple(item.digest for item in portable_cases),
        arms=arms,
        seeds=(0, 1729),
        repetitions=1,
        holdout_case_ids=(runtime_cases[-1].id,),
        claim_scope="mechanism-fixture",
        dataset_license="CC0-1.0",
        source=REPOSITORY_SOURCE,
        notes=(
            "All inputs are small synthetic fixtures committed by value digest.",
            "Latency is observed runtime evidence, not a cross-machine performance claim.",
            "Only a complete exhaustive arm may claim optimality over the admitted space.",
        ),
    )
    definition = BenchmarkDefinition(
        suite=suite,
        task_contract=task,
        task_cases=portable_cases,
        cases=runtime_cases,
        example=example,
    )
    compiler = Compiler()
    space = compiler.admit(example.program, example.registry)
    fixed_routes = tuple(
        next(route for route in example.routes if route.id == route_id)
        for route_id in fixed_route_ids
    )
    baseline_plans = tuple(
        compiler.compile(
            example.program,
            example.registry,
            space,
            route.selection,
            fallbacks=route.fallback_map(),
        )
        for route in fixed_routes
    )
    solution_pack = SolutionPackManifest(
        id=f"solution-pack.{suffix}",
        version="1.0.0",
        title=f"{example.title} solution pack",
        description=(
            "Content-addressed task, program, registry, node pack, cases, oracle, "
            "fixed baselines, and benchmark allocation for this executable fixture."
        ),
        readiness="executable-fixture",
        task_contract_digest=task.digest,
        program_digests=(example.program.digest,),
        registry_digests=(example.registry.digest,),
        node_pack_digests=(node_pack.digest,),
        task_case_digests=tuple(item.digest for item in portable_cases),
        evaluator_digests=(task.oracle.evaluator_digest,),
        baseline_plan_digests=tuple(plan.digest for plan in baseline_plans),
        benchmark_suite_digests=(suite.digest,),
        source=REPOSITORY_SOURCE,
        license="MIT",
        extensions=(("benchmark.claim-scope", suite.claim_scope),),
    )
    bundle = BenchmarkBundle(definition, solution_pack, baseline_plans, node_pack)
    problems = bundle.validate()
    if problems:
        raise ValueError(f"invalid bundled benchmark {suffix}: " + "; ".join(problems))
    return bundle


DOCUMENT_EXTRACTION = _bundle(
    suffix="document-extraction",
    example_id="document-to-schema",
    description=(
        "Compare fixed and solver-selected normalization/extraction routes over "
        "format variations of one typed invoice contract."
    ),
    cases=(
        (
            "canonical",
            "development",
            {"document": "INVOICE\nName: Taylor Amarel\nInvoice Total: $125.50\n"},
            "Canonical line-oriented invoice.",
        ),
        (
            "spacing",
            "development",
            {"document": "  Name :   Taylor Amarel  \r\nInvoice   Total : $125.50\r\n"},
            "Irregular spacing and CRLF line endings.",
        ),
        (
            "extra-fields",
            "validation",
            {"document": "Vendor: Example Co\nName: Taylor Amarel\nInvoice Total: $125.50\nMemo: paid\n"},
            "Additional fields outside the requested schema.",
        ),
        (
            "holdout-case",
            "holdout",
            {"document": "name: Taylor Amarel\ninvoice-total: $125.50\n"},
            "Held-out key spelling variation.",
        ),
    ),
    fixed_route_ids=("baseline", "alternative"),
    tags=("domain.document", "task.extraction"),
)


IMAGE_ASSURANCE = _bundle(
    suffix="image-assurance",
    example_id="image-check-and-process",
    description=(
        "Compare decode, enhancement, and measurement combinations on deterministic "
        "portable grayscale images."
    ),
    cases=(
        (
            "gradient",
            "development",
            {"document": "P2\n4 3\n15\n0 2 4 6\n8 10 12 14\n1 3 5 7\n"},
            "Low-bit-depth gradient.",
        ),
        (
            "comments",
            "development",
            {"document": "P2\n# dimensions\n4 3\n31\n0 1 2 3\n4 8 16 31\n7 9 11 13\n"},
            "Commented header and wider range.",
        ),
        (
            "sparse",
            "validation",
            {"document": "P2\n4 3\n255\n0 0 0 255\n0 4 8 12\n16 32 64 128\n"},
            "Sparse histogram with an extreme pixel.",
        ),
        (
            "holdout-case",
            "holdout",
            {"document": "P2\n4 3\n9\n9 8 7 6\n5 4 3 2\n1 0 1 2\n"},
            "Held-out descending intensity pattern.",
        ),
    ),
    fixed_route_ids=("baseline", "enhanced"),
    tags=("domain.image", "task.assurance"),
)


DATA_CLEANING = _bundle(
    suffix="data-cleaning",
    example_id="data-cleanup",
    description=(
        "Compare exact and normalized entity cleanup routes on punctuation, casing, "
        "key, phone, and duplicate variations."
    ),
    cases=(
        (
            "company-punctuation",
            "development",
            {"records": [
                {"Company": "ACME, Inc.", "Email": "A@EXAMPLE.COM", "Phone": "(555) 0100"},
                {"company": "Acme Inc", "email": "a@example.com", "phone": "555-0100"},
                {"company": "Beta LLC", "email": "b@example.com", "phone": "555-0200"},
            ]},
            "Company punctuation and email casing variation.",
        ),
        (
            "spacing",
            "development",
            {"records": [
                {"company": "North-Star Co", "email": "N@EXAMPLE.COM"},
                {"Company": "North Star Co", "email": "n@example.com"},
                {"company": "South LLC", "email": "s@example.com"},
            ]},
            "Separator and key-case variation.",
        ),
        (
            "exact-repeat",
            "validation",
            {"records": [
                {"company": "Delta Ltd", "email": "d@example.com"},
                {"company": "Delta Ltd", "email": "d@example.com"},
                {"company": "Epsilon LLC", "email": "e@example.com"},
            ]},
            "Exact repeat control.",
        ),
        (
            "holdout-case",
            "holdout",
            {"records": [
                {"Company": "Orbit+Labs", "email": "o@example.com", "phone": "+1 555 0300"},
                {"company": "Orbit Labs", "Email": "O@EXAMPLE.COM", "phone": "15550300"},
                {"company": "Zenith Corp", "email": "z@example.com"},
            ]},
            "Held-out symbol and phone-format variation.",
        ),
    ),
    fixed_route_ids=("baseline", "robust"),
    tags=("domain.data", "task.cleaning"),
)


TABULAR_REGRESSION = _bundle(
    suffix="tabular-regression",
    example_id="tabular-regression",
    description=(
        "Compare split/model paths on exact synthetic linear relationships with a "
        "separate holdout and bounded search allocations."
    ),
    cases=tuple(
        (
            case_suffix,
            split,
            {
                "dataset": {
                    "rows": [
                        {"x": value, "y": slope * value + intercept}
                        for value in range(start, start + 12)
                    ],
                    "predict": [start + 13, start + 17],
                }
            },
            case_description,
        )
        for case_suffix, split, slope, intercept, start, case_description in (
            ("positive", "development", 2, 1, 1, "Positive slope and nonzero intercept."),
            ("negative", "development", -1.5, 20, 0, "Negative slope."),
            ("fractional", "validation", 0.25, -3, 4, "Fractional slope."),
            ("holdout-case", "holdout", 3.5, 7, -5, "Held-out range and slope."),
        )
    ),
    fixed_route_ids=("control", "linear"),
    tags=("domain.ml", "task.regression"),
)


TABULAR_CLASSIFICATION = _bundle(
    suffix="tabular-classification",
    example_id="tabular-classification",
    description=(
        "Compare majority and threshold classifiers across shifted deterministic "
        "binary decision boundaries."
    ),
    cases=tuple(
        (
            case_suffix,
            split,
            {
                "dataset": {
                    "rows": [
                        {"x": value, "label": int(value > threshold)}
                        for value in range(start, start + 12)
                    ],
                    "predict": [start, threshold + 1, start + 15],
                }
            },
            case_description,
        )
        for case_suffix, split, start, threshold, case_description in (
            ("centered", "development", 1, 6, "Centered threshold."),
            ("low-boundary", "development", 0, 4, "Lower decision boundary."),
            ("shifted", "validation", 10, 15, "Shifted feature range."),
            ("holdout-case", "holdout", -6, -1, "Held-out negative feature range."),
        )
    ),
    fixed_route_ids=("control", "threshold"),
    tags=("domain.ml", "task.classification"),
)


STDLIB_DATA_QUALITY = _bundle(
    suffix="stdlib-data-quality",
    example_id="stdlib-data-quality",
    description=(
        "Exercise a reusable node pack across a 1,728-route admitted cleanup space, "
        "including explicit pass-through candidates at every optional transformation."
    ),
    cases=(
        (
            "case-and-spacing",
            "development",
            {"records": [
                {"Company": " Acme Labs ", "Email": "A@EXAMPLE.COM", "Status": "N/A"},
                {"company": "acme labs", "email": "a@example.com", "status": ""},
                {"Company": "Beta LLC", "Email": "b@example.com", "Status": "active"},
            ]},
            "Key, case, whitespace, and missing-sentinel variation.",
        ),
        (
            "email-case",
            "development",
            {"records": [
                {"company": "Gamma", "email": "G@EXAMPLE.COM"},
                {"Company": "gamma", "Email": "g@example.com"},
                {"company": "Delta", "email": "d@example.com"},
            ]},
            "Email casing variation across duplicate entities.",
        ),
        (
            "exact-repeat",
            "validation",
            {"records": [
                {"company": "Epsilon", "email": "e@example.com"},
                {"company": "Epsilon", "email": "e@example.com"},
                {"company": "Zeta", "email": "z@example.com"},
            ]},
            "Exact duplicate control.",
        ),
        (
            "holdout-case",
            "holdout",
            {"records": [
                {"Company": " Eta Group", "Email": "ETA@EXAMPLE.COM "},
                {"company": "eta group", "email": "eta@example.com"},
                {"Company": "Theta LLC", "Email": "theta@example.com"},
            ]},
            "Held-out mixed key, case, and outer-whitespace variation.",
        ),
    ),
    fixed_route_ids=("control", "robust"),
    tags=("domain.data", "task.quality"),
    node_pack=STANDARD_LIBRARY_NODE_PACK,
)


REFERENCE_BENCHMARKS = (
    DOCUMENT_EXTRACTION,
    IMAGE_ASSURANCE,
    DATA_CLEANING,
    TABULAR_REGRESSION,
    TABULAR_CLASSIFICATION,
    STDLIB_DATA_QUALITY,
)


def get_benchmark(benchmark_id: str) -> BenchmarkBundle:
    try:
        return next(item for item in REFERENCE_BENCHMARKS if item.id == benchmark_id)
    except StopIteration as exc:
        known = ", ".join(item.id for item in REFERENCE_BENCHMARKS)
        raise ValueError(
            f"unknown benchmark {benchmark_id!r}; known benchmarks: {known}"
        ) from exc


def run_benchmark(
    benchmark_id: str,
    *,
    runtime: str = "in-process",
    artifact_root: str | None = None,
    receipt_sink=None,
):
    return BenchmarkRunner().run(
        get_benchmark(benchmark_id).definition,
        runtime=runtime,
        artifact_root=artifact_root,
        receipt_sink=receipt_sink,
    )


__all__ = [
    "BenchmarkBundle",
    "DATA_CLEANING",
    "DOCUMENT_EXTRACTION",
    "IMAGE_ASSURANCE",
    "REFERENCE_BENCHMARKS",
    "STDLIB_DATA_QUALITY",
    "TABULAR_CLASSIFICATION",
    "TABULAR_REGRESSION",
    "get_benchmark",
    "run_benchmark",
]
