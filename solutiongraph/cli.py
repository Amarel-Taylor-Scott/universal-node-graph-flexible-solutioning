"""Small dependency-free command line interface for SolutionGraph authoring."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from solutiongraph import __version__
from solutiongraph.executor import ExecutionError


def _template(template_id: str):
    from solutiongraph.template_library import REFERENCE_TEMPLATES

    matches = tuple(
        template for template in REFERENCE_TEMPLATES.templates if template.id == template_id
    )
    if not matches:
        known = ", ".join(template.id for template in REFERENCE_TEMPLATES.templates)
        raise ValueError(f"unknown template {template_id!r}; known templates: {known}")
    return matches[0]


def _doctor() -> int:
    from solutiongraph.arena import UNIVERSAL_DAG_ARENA
    from solutiongraph.catalog import catalog_documents
    from solutiongraph.examples.tasks import EXAMPLE_TASKS
    from solutiongraph.reference_nodes import REFERENCE_DESCRIPTORS, REFERENCE_NODE_SPECS
    from solutiongraph.schemas import load_all_schemas
    from solutiongraph.template_library import REFERENCE_TEMPLATES

    problems: list[str] = []
    problems.extend(UNIVERSAL_DAG_ARENA.validate())
    problems.extend(REFERENCE_TEMPLATES.validate())
    problems.extend(
        problem
        for node in REFERENCE_NODE_SPECS
        for problem in node.validate(f"nodes.{node.id}")
    )
    example_nodes = {
        (node.id, node.version, node.implementation_digest): node
        for example in EXAMPLE_TASKS
        for node in example.registry.nodes
    }
    problems.extend(
        problem
        for node in example_nodes.values()
        for problem in node.validate(f"example_nodes.{node.id}")
    )
    node_by_id = {node.id: node for node in REFERENCE_NODE_SPECS}
    for descriptor in REFERENCE_DESCRIPTORS:
        problems.extend(
            descriptor.validate(
                node_by_id.get(descriptor.node_id),
                f"descriptors.{descriptor.node_id}",
            )
        )
    schemas = load_all_schemas()
    documents = catalog_documents()
    if problems:
        print("SolutionGraph doctor found problems:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print(
        "SolutionGraph ready: "
        f"templates={len(REFERENCE_TEMPLATES.templates)} "
        f"atomic_slots={sum(len(item.program.slots) for item in REFERENCE_TEMPLATES.templates)} "
        f"nodes={len(REFERENCE_NODE_SPECS)} "
        f"example_nodes={len(example_nodes)} "
        f"executable_examples={len(EXAMPLE_TASKS)} "
        f"arena_tasks={len(UNIVERSAL_DAG_ARENA.tasks)} "
        f"schemas={len(schemas)} "
        f"catalog_documents={len(documents)}"
    )
    return 0


def _templates_list(
    as_json: bool,
    domains: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
) -> int:
    from solutiongraph.template_library import REFERENCE_TEMPLATES

    rows = [
        {
            "id": template.id,
            "title": template.title,
            "stages": len(template.stages),
            "atomic_slots": len(template.program.slots),
            "domains": list(template.domains),
        }
        for template in REFERENCE_TEMPLATES.matching(domains=domains, tags=tags)
    ]
    if as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    print("ID\tSTAGES\tSLOTS\tTITLE")
    for row in rows:
        print(f"{row['id']}\t{row['stages']}\t{row['atomic_slots']}\t{row['title']}")
    return 0


def _templates_show(template_id: str, as_json: bool) -> int:
    template = _template(template_id)
    if as_json:
        print(json.dumps(template.to_dict(), indent=2, sort_keys=True))
        return 0
    print(f"{template.id}@{template.version} — {template.title}")
    print(template.description)
    print(f"domains: {', '.join(template.domains)}")
    for stage_number, stage in enumerate(template.stages, start=1):
        print(f"\n{stage_number}. {stage.title} — {stage.description}")
        slots = {slot.id: slot for slot in template.program.slots}
        for slot_number, slot_id in enumerate(stage.slot_ids, start=1):
            slot = slots[slot_id]
            print(f"   {stage_number}.{slot_number} {slot.id}: {slot.purpose}")
    return 0


def _templates_validate(blueprint_path: Path) -> int:
    from solutiongraph.template_authoring import load_linear_blueprint

    blueprint = load_linear_blueprint(blueprint_path)
    template = blueprint.to_template()
    print(
        f"valid {template.id}@{template.version}: "
        f"stages={len(template.stages)} atomic_slots={len(template.program.slots)} "
        f"digest={template.digest}"
    )
    return 0


def _templates_create(blueprint_path: Path, output: Path) -> int:
    from solutiongraph.template_authoring import (
        load_linear_blueprint,
        write_solution_template,
    )

    template = load_linear_blueprint(blueprint_path).to_template()
    target = write_solution_template(template, output)
    print(
        f"wrote {template.id}@{template.version} "
        f"({len(template.program.slots)} atomic slots) to {target}"
    )
    return 0


def _catalog_export(output: Path) -> int:
    from solutiongraph.catalog import write_catalog

    written = write_catalog(output)
    print(f"wrote {len(written)} catalogue documents to {output}")
    return 0


def _examples_list(as_json: bool) -> int:
    from solutiongraph.examples import EXAMPLE_TASKS

    rows = [
        {
            "id": example.id,
            "title": example.title,
            "description": example.description,
            "slots": len(example.program.slots),
            "routes": [route.id for route in example.routes],
        }
        for example in EXAMPLE_TASKS
    ]
    if as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    print("ID\tSLOTS\tROUTES\tTITLE")
    for row in rows:
        print(f"{row['id']}\t{row['slots']}\t{len(row['routes'])}\t{row['title']}")
    return 0


def _examples_run(
    example_id: str,
    route: str,
    artifact_dir: Path | None,
    runtime: str,
    receipt_journal: Path | None,
    as_json: bool,
) -> int:
    from solutiongraph.examples import run_example
    from solutiongraph.ledger import JsonlReceiptJournal

    journal = JsonlReceiptJournal(receipt_journal) if receipt_journal else None
    report = run_example(
        example_id,
        route=route,
        artifact_root=artifact_dir,
        runtime=runtime,
        receipt_journal=journal,
    )
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if route == "all":
        experiment = report["experiment"]
        print(
            f"{example_id}: {experiment['completed_runs']} routes executed; "
            f"Pareto routes={len(experiment['pareto_plan_digests'])}"
        )
        for receipt in experiment["receipts"]:
            print(
                f"- {receipt['plan_digest'][:23]} {receipt['outcome']} "
                f"quality={receipt['metrics'].get('quality', 'n/a')} "
                f"latency_ms={receipt['metrics']['latency_ms']:.3f}"
            )
    else:
        receipt = report["execution"]["receipt"]
        print(
            f"{example_id}/{route}: {receipt['outcome']} "
            f"plan={report['plan']['digest']} artifacts={len(report['execution']['artifacts'])}"
        )
    return 0


def _verify(catalog_root: Path | None, runtime: str, as_json: bool) -> int:
    from solutiongraph.verification import verify_reference_release

    result = verify_reference_release(catalog_root=catalog_root, runtime=runtime)
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    elif result.ok:
        print(
            "SolutionGraph release verified: "
            f"runtime={runtime} "
            f"examples={len({item.example_id for item in result.route_results})} "
            f"routes={len(result.route_results)} "
            f"accepted={result.accepted_routes} "
            f"rejected_controls={result.rejected_controls} "
            f"templates={result.template_count} "
            f"atomic_slots={result.atomic_slot_count} "
            f"executable_nodes={result.executable_node_count} "
            f"schemas={result.schema_count} "
            f"conformance_checks={len(result.conformance.checks)} "
            f"catalog_documents={result.catalog_document_count} "
            f"catalog_checked={'yes' if result.catalog_checked else 'no'}"
        )
    else:
        print("SolutionGraph release verification failed:")
        for problem in result.problems:
            print(f"- {problem}")
    return 0 if result.ok else 1


def _init_project(destination: Path, template_id: str, project_id: str | None) -> int:
    from solutiongraph.scaffold import scaffold_project

    template = _template(template_id)
    written = scaffold_project(destination, template, project_id=project_id)
    print(
        f"created {destination} from {template.id}@{template.version}: "
        f"files={len(written)}"
    )
    print(f"next: open {destination / 'TASK.md'}")
    return 0


def _ledger_verify(path: Path, as_json: bool) -> int:
    from solutiongraph.ledger import JsonlReceiptJournal

    status = JsonlReceiptJournal(path).status()
    if as_json:
        print(json.dumps(status.to_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"valid receipt journal: path={status.path} "
            f"receipts={status.receipt_count} "
            f"head={status.head_digest or 'empty'} bytes={status.byte_size}"
        )
    return 0


def _conformance(as_json: bool) -> int:
    from solutiongraph.conformance import run_conformance_suite

    result = run_conformance_suite()
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"SolutionGraph advanced conformance: "
            f"{'passed' if result.ok else 'failed'} ({len(result.checks)} checks)"
        )
        for check in result.checks:
            print(f"- {'PASS' if check.passed else 'FAIL'} {check.id}: {check.details}")
    return 0 if result.ok else 1


def _load_receipt(path: Path, receipt_id: str | None):
    from solutiongraph.evidence import RunReceipt
    from solutiongraph.ledger import JsonlReceiptJournal

    if path.suffix.lower() == ".jsonl":
        receipts = JsonlReceiptJournal(path).read().receipts
        if receipt_id:
            matches = tuple(item for item in receipts if item.id == receipt_id)
            if len(matches) != 1:
                raise ValueError(
                    f"receipt id {receipt_id!r} matched {len(matches)} journal entries"
                )
            return matches[0]
        if not receipts:
            raise ValueError("receipt journal is empty")
        return receipts[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("receipt JSON must be an object")
    if "receipt" in payload and isinstance(payload["receipt"], dict):
        payload = payload["receipt"]
    elif (
        "execution" in payload
        and isinstance(payload["execution"], dict)
        and isinstance(payload["execution"].get("receipt"), dict)
    ):
        payload = payload["execution"]["receipt"]
    receipt = RunReceipt.from_dict(payload)
    if receipt_id and receipt.id != receipt_id:
        raise ValueError("receipt JSON does not contain the requested receipt id")
    return receipt


def _provenance_export(
    receipt_path: Path,
    output: Path,
    format_: str,
    receipt_id: str | None,
) -> int:
    from solutiongraph.provenance import export_provenance

    receipt = _load_receipt(receipt_path, receipt_id)
    bundle = export_provenance(receipt)
    payload = {
        "bundle": bundle.to_dict(),
        "w3c-prov": bundle.w3c_prov,
        "openlineage": bundle.openlineage,
        "slsa": bundle.slsa_provenance,
    }[format_]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {format_} provenance for {receipt.id} to {output}")
    return 0


def _checkpoint_inspect(path: Path, as_json: bool) -> int:
    from solutiongraph.durable import ExecutionCheckpoint

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("checkpoint JSON must be an object")
    checkpoint = ExecutionCheckpoint.from_dict(payload)
    if as_json:
        print(json.dumps(checkpoint.to_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"{checkpoint.id}: status={checkpoint.status} "
            f"completed_slots={len(checkpoint.completed_slots)} "
            f"plan={checkpoint.plan_digest}"
        )
        for slot in checkpoint.completed_slots:
            print(f"- {slot.slot_id}: {slot.candidate_id} ({slot.receipt.outcome})")
    return 0


def _solve_example(
    example_id: str,
    profile: str,
    runtime: str,
    artifact_dir: Path | None,
    receipt_journal: Path | None,
    allow_exhaustive: bool,
    as_json: bool,
) -> int:
    from solutiongraph.arena import solve_example
    from solutiongraph.ledger import JsonlReceiptJournal

    journal = JsonlReceiptJournal(receipt_journal) if receipt_journal else None
    report = solve_example(
        example_id,
        profile=profile,
        runtime=runtime,
        artifact_root=artifact_dir,
        receipt_journal=journal,
        allow_exhaustive=allow_exhaustive,
    )
    result = report["result"]
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if result["status"] == "solved" else 1
    print(
        f"{example_id}: {result['status']} profile={profile} runtime={runtime} "
        f"space={result['route_count_upper_bound']} evaluated={result['evaluated_plan_count']}"
    )
    champion = result["champion_plan_digest"]
    print(f"champion: {champion or 'none'}")
    for fallback in result["fallbacks"]:
        print(
            f"fallback {fallback['priority']}: {fallback['plan_digest']} "
            f"evidence={fallback['evidence_score']:.3f} "
            f"diversity={fallback['diversity_score']:.3f}"
        )
    for round_ in result["rounds"]:
        search = round_["search"]
        print(
            f"round {round_['index']}: mode={search['mode']} "
            f"searched={search['evaluated_routes']}/{search['total_cartesian_routes']} "
            f"new_plans={len(round_['plan_digests'])} complete={search['complete']}"
        )
    return 0 if result["status"] == "solved" else 1


def _arena_list(readiness: str | None, tags: tuple[str, ...], as_json: bool) -> int:
    from solutiongraph.arena import UNIVERSAL_DAG_ARENA

    tasks = UNIVERSAL_DAG_ARENA.matching(readiness=readiness, tags=tags)
    if as_json:
        print(json.dumps([task.to_dict() for task in tasks], indent=2, sort_keys=True))
        return 0
    print("ID\tREADINESS\tEXAMPLES\tTITLE")
    for task in tasks:
        print(
            f"{task.id}\t{task.readiness}\t"
            f"{','.join(task.executable_example_ids) or '-'}\t{task.title}"
        )
    return 0


def _arena_show(task_id: str, as_json: bool) -> int:
    from solutiongraph.arena import UNIVERSAL_DAG_ARENA

    task = UNIVERSAL_DAG_ARENA.get(task_id)
    if as_json:
        print(json.dumps(task.to_dict(), indent=2, sort_keys=True))
        return 0
    print(f"{task.id} — {task.title}")
    print(task.problem)
    print(f"readiness: {task.readiness}")
    print(f"template: {task.template_id}")
    print(f"input: {task.input_contract}")
    print(f"output: {task.output_contract}")
    print("stages: " + " -> ".join(task.stage_families))
    print("acceptance: " + ", ".join(task.acceptance_signals))
    if task.executable_example_ids:
        print("examples: " + ", ".join(task.executable_example_ids))
    for requirement in task.external_requirements:
        print(f"external: {requirement}")
    return 0


def _arena_run(
    task_ids: tuple[str, ...],
    profile: str,
    runtime: str,
    artifact_dir: Path | None,
    receipt_journal: Path | None,
    allow_exhaustive: bool,
    as_json: bool,
) -> int:
    from solutiongraph.arena import run_arena
    from solutiongraph.ledger import JsonlReceiptJournal

    journal = JsonlReceiptJournal(receipt_journal) if receipt_journal else None
    report = run_arena(
        task_ids or None,
        profile=profile,
        runtime=runtime,
        artifact_root=artifact_dir,
        receipt_journal=journal,
        allow_exhaustive=allow_exhaustive,
    )
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"arena: tasks={len(report['selected_task_ids'])} "
            f"executed={report['executed_example_count']} "
            f"skipped={report['skipped_task_count']} profile={profile} runtime={runtime}"
        )
        for example in report["examples"]:
            result = example["result"]
            print(
                f"- {example['example_id']}: {result['status']} "
                f"evaluated={result['evaluated_plan_count']}/"
                f"{result['route_count_upper_bound']}"
            )
        for skipped in report["skipped"]:
            print(f"- {skipped['task_id']}: skipped ({skipped['readiness']})")
    return 0 if all(
        example["result"]["status"] == "solved" for example in report["examples"]
    ) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="solutiongraph",
        description="Author, inspect, validate, and export universal solution graphs.",
    )
    parser.add_argument(
        "--version", action="version", version=f"solutiongraph {__version__}"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="Validate the installed reference assets")
    conformance = commands.add_parser(
        "conformance",
        help="Execute advanced branch, structure, topology, stream, saga, fidelity, and provenance checks",
    )
    conformance.add_argument("--json", action="store_true", help="Emit JSON")
    verify = commands.add_parser(
        "verify",
        help="Compile and execute every bundled route as a release gate",
    )
    verify.add_argument(
        "--catalog-root",
        type=Path,
        help="Also require this generated catalog directory to exactly match",
    )
    verify.add_argument(
        "--runtime",
        choices=("in-process", "subprocess"),
        default="in-process",
        help="Execution adapter used for every reference route",
    )
    verify.add_argument("--json", action="store_true", help="Emit full JSON")

    init = commands.add_parser(
        "init",
        help="Create a non-destructive starter workspace for a developer or coding agent",
    )
    init.add_argument("destination", type=Path)
    init.add_argument(
        "--template",
        default="template.document-intelligence",
        help="Reference template used as the starting semantic decomposition",
    )
    init.add_argument(
        "--project-id",
        help="Lowercase namespaced project identifier (derived from destination by default)",
    )

    templates = commands.add_parser("templates", help="Inspect and author templates")
    template_commands = templates.add_subparsers(dest="template_command", required=True)
    list_parser = template_commands.add_parser("list", help="List reference templates")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON")
    list_parser.add_argument(
        "--domain",
        action="append",
        default=[],
        help="Require an exact domain (repeatable)",
    )
    list_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Require an exact tag (repeatable)",
    )
    show_parser = template_commands.add_parser("show", help="Show one reference template")
    show_parser.add_argument("template_id")
    show_parser.add_argument("--json", action="store_true", help="Emit normative JSON")
    validate_parser = template_commands.add_parser(
        "validate", help="Validate a linear template blueprint"
    )
    validate_parser.add_argument("blueprint", type=Path)
    create_parser = template_commands.add_parser(
        "create", help="Compile a blueprint into a portable solution-template JSON file"
    )
    create_parser.add_argument("blueprint", type=Path)
    create_parser.add_argument("--output", type=Path, required=True)

    catalog = commands.add_parser("catalog", help="Work with the reference catalog")
    catalog_commands = catalog.add_subparsers(dest="catalog_command", required=True)
    export_parser = catalog_commands.add_parser("export", help="Export the reference catalog")
    export_parser.add_argument("--output", type=Path, default=Path("catalog"))

    examples = commands.add_parser(
        "examples", help="List or execute the dependency-free domain examples"
    )
    example_commands = examples.add_subparsers(dest="example_command", required=True)
    examples_list = example_commands.add_parser("list", help="List executable examples")
    examples_list.add_argument("--json", action="store_true", help="Emit JSON")
    examples_run = example_commands.add_parser("run", help="Compile and execute an example")
    examples_run.add_argument("example_id")
    examples_run.add_argument(
        "--route",
        default="all",
        help="Route name, or 'all' to run a receipt-backed comparison",
    )
    examples_run.add_argument(
        "--artifact-dir",
        type=Path,
        help="Persist content-addressed outputs instead of using memory",
    )
    examples_run.add_argument(
        "--runtime",
        choices=("in-process", "subprocess"),
        default="in-process",
        help="Run nodes locally in-process or in bounded child processes",
    )
    examples_run.add_argument(
        "--receipt-journal",
        type=Path,
        help="Append each completed run immediately to a verified JSONL journal",
    )
    examples_run.add_argument("--json", action="store_true", help="Emit full JSON")

    solve = commands.add_parser(
        "solve",
        help="Search, benchmark, rank, and select a route for one executable example",
    )
    solve.add_argument("example_id")
    solve.add_argument(
        "--profile",
        choices=("quick", "balanced", "broad", "exhaustive"),
        default="balanced",
        help="Explicit search and experiment allocation profile",
    )
    solve.add_argument(
        "--runtime",
        choices=("in-process", "subprocess"),
        default="in-process",
    )
    solve.add_argument("--artifact-dir", type=Path)
    solve.add_argument("--receipt-journal", type=Path)
    solve.add_argument(
        "--allow-exhaustive",
        action="store_true",
        help="Acknowledge that exhaustive mode has no implicit route cap",
    )
    solve.add_argument("--json", action="store_true", help="Emit full JSON")

    arena = commands.add_parser(
        "arena", help="Inspect and run the cross-domain Universal DAG Arena"
    )
    arena_commands = arena.add_subparsers(dest="arena_command", required=True)
    arena_list = arena_commands.add_parser("list", help="List arena problem families")
    arena_list.add_argument(
        "--readiness",
        choices=("executable_fixture", "template", "credentialed_connector"),
    )
    arena_list.add_argument("--tag", action="append", default=[])
    arena_list.add_argument("--json", action="store_true", help="Emit JSON")
    arena_show = arena_commands.add_parser("show", help="Show one arena task contract")
    arena_show.add_argument("task_id")
    arena_show.add_argument("--json", action="store_true", help="Emit JSON")
    arena_run = arena_commands.add_parser(
        "run", help="Solve selected tasks, or every executable fixture when omitted"
    )
    arena_run.add_argument("task_ids", nargs="*")
    arena_run.add_argument(
        "--profile",
        choices=("quick", "balanced", "broad", "exhaustive"),
        default="quick",
    )
    arena_run.add_argument(
        "--runtime",
        choices=("in-process", "subprocess"),
        default="in-process",
    )
    arena_run.add_argument("--artifact-dir", type=Path)
    arena_run.add_argument("--receipt-journal", type=Path)
    arena_run.add_argument("--allow-exhaustive", action="store_true")
    arena_run.add_argument("--json", action="store_true", help="Emit full JSON")

    ledger = commands.add_parser("ledger", help="Verify durable receipt evidence")
    ledger_commands = ledger.add_subparsers(dest="ledger_command", required=True)
    ledger_verify = ledger_commands.add_parser(
        "verify", help="Validate every receipt and the complete hash chain"
    )
    ledger_verify.add_argument("path", type=Path)
    ledger_verify.add_argument("--json", action="store_true", help="Emit JSON")

    provenance = commands.add_parser(
        "provenance", help="Export portable provenance from a run receipt"
    )
    provenance_commands = provenance.add_subparsers(
        dest="provenance_command", required=True
    )
    provenance_export = provenance_commands.add_parser(
        "export", help="Export W3C PROV, OpenLineage, SLSA, or all formats"
    )
    provenance_export.add_argument("receipt", type=Path)
    provenance_export.add_argument("--receipt-id")
    provenance_export.add_argument(
        "--format",
        dest="provenance_format",
        choices=("bundle", "w3c-prov", "openlineage", "slsa"),
        default="bundle",
    )
    provenance_export.add_argument("--output", type=Path, required=True)

    checkpoint = commands.add_parser(
        "checkpoint", help="Inspect a durable reference-executor checkpoint"
    )
    checkpoint_commands = checkpoint.add_subparsers(
        dest="checkpoint_command", required=True
    )
    checkpoint_inspect = checkpoint_commands.add_parser(
        "inspect", help="Validate and display one checkpoint JSON file"
    )
    checkpoint_inspect.add_argument("path", type=Path)
    checkpoint_inspect.add_argument("--json", action="store_true", help="Emit JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return _doctor()
        if args.command == "conformance":
            return _conformance(args.json)
        if args.command == "verify":
            return _verify(args.catalog_root, args.runtime, args.json)
        if args.command == "init":
            return _init_project(args.destination, args.template, args.project_id)
        if args.command == "templates":
            if args.template_command == "list":
                return _templates_list(args.json, tuple(args.domain), tuple(args.tag))
            if args.template_command == "show":
                return _templates_show(args.template_id, args.json)
            if args.template_command == "validate":
                return _templates_validate(args.blueprint)
            if args.template_command == "create":
                return _templates_create(args.blueprint, args.output)
        if args.command == "catalog" and args.catalog_command == "export":
            return _catalog_export(args.output)
        if args.command == "examples":
            if args.example_command == "list":
                return _examples_list(args.json)
            if args.example_command == "run":
                return _examples_run(
                    args.example_id,
                    args.route,
                    args.artifact_dir,
                    args.runtime,
                    args.receipt_journal,
                    args.json,
                )
        if args.command == "solve":
            return _solve_example(
                args.example_id,
                args.profile,
                args.runtime,
                args.artifact_dir,
                args.receipt_journal,
                args.allow_exhaustive,
                args.json,
            )
        if args.command == "arena":
            if args.arena_command == "list":
                return _arena_list(args.readiness, tuple(args.tag), args.json)
            if args.arena_command == "show":
                return _arena_show(args.task_id, args.json)
            if args.arena_command == "run":
                return _arena_run(
                    tuple(args.task_ids),
                    args.profile,
                    args.runtime,
                    args.artifact_dir,
                    args.receipt_journal,
                    args.allow_exhaustive,
                    args.json,
                )
        if args.command == "ledger" and args.ledger_command == "verify":
            return _ledger_verify(args.path, args.json)
        if args.command == "provenance" and args.provenance_command == "export":
            return _provenance_export(
                args.receipt,
                args.output,
                args.provenance_format,
                args.receipt_id,
            )
        if args.command == "checkpoint" and args.checkpoint_command == "inspect":
            return _checkpoint_inspect(args.path, args.json)
    except (ExecutionError, OSError, ValueError) as exc:
        parser.exit(2, f"solutiongraph: error: {exc}\n")
    parser.error("unsupported command")
    return 2


__all__ = ["build_parser", "main"]
