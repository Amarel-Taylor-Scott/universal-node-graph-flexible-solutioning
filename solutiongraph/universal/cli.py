"""Focused CLI for universal domain packs, coverage, and design checklists."""

from __future__ import annotations

import argparse
import json

from solutiongraph.model import Port
from solutiongraph.tasking import TaskContract, TaskOracle
from solutiongraph.universal.catalog import (
    DOMAIN_PACK_BY_ID,
    OBLIGATION_BY_ID,
    REFERENCE_DOMAIN_PACKS,
    REFERENCE_ENGINEERING_QUESTIONS,
    REFERENCE_OBLIGATIONS,
)
from solutiongraph.universal.coverage import reference_coverage_report
from solutiongraph.universal.planning import plan_engineering_design
from solutiongraph.universal.profiling import context_from_task


def add_universal_parser(commands: argparse._SubParsersAction) -> None:
    universal = commands.add_parser(
        "universal",
        help="Inspect domain-neutral obligations, domain packs, coverage, and checklists",
    )
    subcommands = universal.add_subparsers(dest="universal_command", required=True)
    obligations = subcommands.add_parser("obligations", help="List obligation families")
    obligations.add_argument("--json", action="store_true")
    domains = subcommands.add_parser("domains", help="List domain packs")
    domains.add_argument("--json", action="store_true")
    show = subcommands.add_parser("show", help="Show one domain pack and evidence coverage")
    show.add_argument("domain_pack_id")
    show.add_argument("--json", action="store_true")
    coverage = subcommands.add_parser("coverage", help="Show evidence-derived coverage")
    coverage.add_argument("--json", action="store_true")
    questions = subcommands.add_parser("questions", help="List engineering questions")
    questions.add_argument("--obligation")
    questions.add_argument("--json", action="store_true")
    plan = subcommands.add_parser(
        "plan", help="Plan an all-visible checklist for one executable example"
    )
    plan.add_argument("example_id")
    plan.add_argument("--domain", required=True, dest="domain_pack_id")
    plan.add_argument(
        "--effort", choices=("E1", "E3", "E5", "E7", "E10"), default="E3"
    )
    plan.add_argument(
        "--mode",
        action="append",
        choices=("deterministic", "human", "llm", "external"),
        default=[],
    )
    plan.add_argument("--permission", action="append", default=[])
    plan.add_argument("--random-seed", type=int, default=0)
    plan.add_argument("--json", action="store_true")


def _example_contract(example_id: str) -> TaskContract:
    from solutiongraph.examples import get_example

    example = get_example(example_id)
    verifier = example.case.verifier
    return TaskContract(
        id=f"task.example.{example.id}",
        version="1.0.0",
        title=example.title,
        intent=example.program.task,
        inputs=tuple(
            Port(item.name, item.value_type, description=f"Example input {item.name}.")
            for item in example.program.inputs
        ),
        outputs=tuple(
            Port(item.name, item.value_type, description=f"Example output {item.name}.")
            for item in example.program.outputs
        ),
        success_contract=example.program.success_contract,
        oracle=TaskOracle(
            id=verifier.identifier,
            version="1.0.0",
            kind="property",
            evaluator_digest=verifier.implementation_digest,
            implementation_ref=f"verifier://{verifier.identifier}",
            independence="separate-implementation",
            candidate_readable=True,
            description="Transparent mechanism-fixture verifier.",
        ),
        objectives=example.objectives,
        allowed_effects=example.program.allowed_effects,
        granted_permissions=example.program.granted_permissions,
        case_ids=(example.case.id,),
        tags=("fixture.example",),
        extensions=(("example.id", example.id),),
    )


def _emit(payload: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))


def run_universal_command(args: argparse.Namespace) -> int:
    if args.universal_command == "obligations":
        payload = [item.to_dict() for item in REFERENCE_OBLIGATIONS]
        if args.json:
            _emit(payload, True)
        else:
            print("ID\tTITLE\tQUESTION")
            for item in REFERENCE_OBLIGATIONS:
                print(f"{item.id}\t{item.title}\t{item.design_prompt}")
        return 0
    if args.universal_command == "domains":
        report = reference_coverage_report()
        assessments = {item.domain_pack_id: item for item in report.domains}
        payload = [
            {
                **pack.to_dict(),
                "coverage": assessments[pack.id].to_dict(),
            }
            for pack in REFERENCE_DOMAIN_PACKS
        ]
        if args.json:
            _emit(payload, True)
        else:
            print("ID\tCAPABILITIES\tLOWEST\tTITLE")
            for pack in REFERENCE_DOMAIN_PACKS:
                assessment = assessments[pack.id]
                print(
                    f"{pack.id}\t{len(assessment.capabilities)}\t"
                    f"{assessment.lowest_maturity_level}\t{pack.title}"
                )
        return 0
    if args.universal_command == "show":
        if args.domain_pack_id not in DOMAIN_PACK_BY_ID:
            raise ValueError(f"unknown domain pack {args.domain_pack_id!r}")
        pack = DOMAIN_PACK_BY_ID[args.domain_pack_id]
        assessment = next(
            item
            for item in reference_coverage_report().domains
            if item.domain_pack_id == pack.id
        )
        payload = {"domain_pack": pack.to_dict(), "coverage": assessment.to_dict()}
        if args.json:
            _emit(payload, True)
        else:
            print(f"{pack.id} — {pack.title}")
            print(pack.description)
            for item in assessment.capabilities:
                print(
                    f"- {item.capability_id}: {item.status} {item.maturity_level} "
                    f"routes={item.route_count_upper_bound}"
                )
            for limitation in pack.limitations:
                print(f"limitation: {limitation}")
        return 0
    if args.universal_command == "coverage":
        report = reference_coverage_report()
        if args.json:
            _emit(report.to_dict(), True)
        else:
            print("STATUS\tCOUNT")
            for status, count in report.status_counts:
                print(f"{status}\t{count}")
            print(report.claim_boundary)
        return 0
    if args.universal_command == "questions":
        obligation_id = args.obligation
        if obligation_id and not obligation_id.startswith("obligation."):
            obligation_id = "obligation." + obligation_id
        if obligation_id and obligation_id not in OBLIGATION_BY_ID:
            raise ValueError(f"unknown obligation {obligation_id!r}")
        questions = tuple(
            item
            for item in REFERENCE_ENGINEERING_QUESTIONS
            if not obligation_id or item.obligation_id == obligation_id
        )
        if args.json:
            _emit([item.to_dict() for item in questions], True)
        else:
            print("ID\tPRIORITY\tCOST\tPROMPT")
            for item in questions:
                print(f"{item.id}\t{item.priority}\t{item.effort_cost}\t{item.prompt}")
        return 0
    if args.universal_command == "plan":
        if args.domain_pack_id not in DOMAIN_PACK_BY_ID:
            raise ValueError(f"unknown domain pack {args.domain_pack_id!r}")
        contract = _example_contract(args.example_id)
        context = context_from_task(
            contract,
            domain_pack_ids=(args.domain_pack_id,),
        )
        plan = plan_engineering_design(
            context,
            domain_pack_id=args.domain_pack_id,
            effort=args.effort,
            available_modes=tuple(args.mode) or ("deterministic",),
            granted_permissions=tuple(args.permission),
            random_seed=args.random_seed,
        )
        payload = {"context": context.to_dict(), "plan": plan.to_dict()}
        if args.json:
            _emit(payload, True)
        else:
            summary = plan.summary
            print(
                f"universal plan: domain={args.domain_pack_id} effort={args.effort} "
                f"selected={summary['selected']} deferred={summary['deferred']} "
                f"blocked={summary['blocked']} not-applicable={summary['not-applicable']}"
            )
            for item in plan.items:
                if item.status == "selected":
                    question = next(
                        question
                        for question in REFERENCE_ENGINEERING_QUESTIONS
                        if question.id == item.question_id
                    )
                    print(f"- [{item.response_mode}] {question.prompt}")
        return 0
    raise ValueError(f"unsupported universal command {args.universal_command!r}")


__all__ = ["add_universal_parser", "run_universal_command"]
