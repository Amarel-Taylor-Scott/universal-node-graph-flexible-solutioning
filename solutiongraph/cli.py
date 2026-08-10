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
    from solutiongraph.catalog import catalog_documents
    from solutiongraph.examples.tasks import EXAMPLE_TASKS
    from solutiongraph.examples.tasks import NODES as EXAMPLE_NODES
    from solutiongraph.reference_nodes import REFERENCE_DESCRIPTORS, REFERENCE_NODE_SPECS
    from solutiongraph.schemas import load_all_schemas
    from solutiongraph.template_library import REFERENCE_TEMPLATES

    problems: list[str] = []
    problems.extend(REFERENCE_TEMPLATES.validate())
    problems.extend(
        problem
        for node in REFERENCE_NODE_SPECS
        for problem in node.validate(f"nodes.{node.id}")
    )
    problems.extend(
        problem
        for node in EXAMPLE_NODES
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
        f"example_nodes={len(EXAMPLE_NODES)} "
        f"executable_examples={len(EXAMPLE_TASKS)} "
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
    as_json: bool,
) -> int:
    from solutiongraph.examples import run_example

    report = run_example(example_id, route=route, artifact_root=artifact_dir)
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


def _verify(catalog_root: Path | None, as_json: bool) -> int:
    from solutiongraph.verification import verify_reference_release

    result = verify_reference_release(catalog_root=catalog_root)
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    elif result.ok:
        print(
            "SolutionGraph release verified: "
            f"examples={len({item.example_id for item in result.route_results})} "
            f"routes={len(result.route_results)} "
            f"accepted={result.accepted_routes} "
            f"rejected_controls={result.rejected_controls} "
            f"templates={result.template_count} "
            f"atomic_slots={result.atomic_slot_count} "
            f"executable_nodes={result.executable_node_count} "
            f"schemas={result.schema_count} "
            f"catalog_documents={result.catalog_document_count} "
            f"catalog_checked={'yes' if result.catalog_checked else 'no'}"
        )
    else:
        print("SolutionGraph release verification failed:")
        for problem in result.problems:
            print(f"- {problem}")
    return 0 if result.ok else 1


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
    verify = commands.add_parser(
        "verify",
        help="Compile and execute every bundled route as a release gate",
    )
    verify.add_argument(
        "--catalog-root",
        type=Path,
        help="Also require this generated catalog directory to exactly match",
    )
    verify.add_argument("--json", action="store_true", help="Emit full JSON")

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
        "examples", help="List or execute the six dependency-free domain examples"
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
    examples_run.add_argument("--json", action="store_true", help="Emit full JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return _doctor()
        if args.command == "verify":
            return _verify(args.catalog_root, args.json)
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
                    args.json,
                )
    except (ExecutionError, OSError, ValueError) as exc:
        parser.exit(2, f"solutiongraph: error: {exc}\n")
    parser.error("unsupported command")
    return 2


__all__ = ["build_parser", "main"]
