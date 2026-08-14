"""CLI surface for specialized capability-pack discovery and composition."""

from __future__ import annotations

import json
from typing import Any

from solutiongraph.specialized.builtins import REFERENCE_SPECIALIZED_PACK_REGISTRY
from solutiongraph.specialized.composition import (
    PackageCompositionRequest,
    compose_specialized_packs,
)
from solutiongraph.specialized.discovery import (
    discover_installed_pack_providers,
    load_and_merge_installed_pack_providers,
    load_installed_pack_providers,
)
from solutiongraph.specialized.model import SpecializedPackRegistry
from solutiongraph.specialized.recommendation import (
    TaskPackageRequest,
    recommend_specialized_packs,
)


def add_specialized_parser(commands: Any) -> None:
    packages = commands.add_parser(
        "packages",
        help="Discover, recommend, and compose specialized capability packs",
    )
    package_commands = packages.add_subparsers(dest="specialized_package_command", required=True)

    list_parser = package_commands.add_parser("list", help="List bundled specialized packs")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON")
    list_parser.add_argument(
        "--include-installed",
        action="store_true",
        help="Explicitly import and merge installed specialized-pack providers",
    )

    show_parser = package_commands.add_parser("show", help="Show one specialized pack")
    show_parser.add_argument("pack_id")
    show_parser.add_argument("--json", action="store_true", help="Emit JSON")
    show_parser.add_argument(
        "--include-installed",
        action="store_true",
        help="Explicitly import and merge installed specialized-pack providers",
    )

    recommend = package_commands.add_parser(
        "recommend", help="Rank every specialized pack for one task description"
    )
    recommend.add_argument("description")
    recommend.add_argument("--category", action="append", default=[])
    recommend.add_argument("--input-kind", action="append", default=[])
    recommend.add_argument("--output-kind", action="append", default=[])
    recommend.add_argument("--capability", action="append", default=[])
    recommend.add_argument("--prefer", action="append", default=[])
    recommend.add_argument("--exclude", action="append", default=[])
    recommend.add_argument("--permission", action="append", default=[])
    recommend.add_argument("--limit", type=int, default=3)
    recommend.add_argument("--json", action="store_true", help="Emit JSON")
    recommend.add_argument(
        "--include-installed",
        action="store_true",
        help="Explicitly import and merge installed specialized-pack providers",
    )

    compose = package_commands.add_parser(
        "compose", help="Enumerate exact recipe chains under explicit budgets"
    )
    compose.add_argument("--input-kind", action="append", required=True)
    compose.add_argument("--output-kind", action="append", required=True)
    compose.add_argument("--pack", action="append", default=[])
    compose.add_argument("--capability", action="append", default=[])
    compose.add_argument("--max-steps", type=int, default=5)
    compose.add_argument("--state-budget", type=int, default=5000)
    compose.add_argument("--candidate-limit", type=int, default=50)
    compose.add_argument(
        "--unbounded-states",
        action="store_true",
        help="Remove the state budget; max-steps still bounds the finite search",
    )
    compose.add_argument(
        "--all-candidates",
        action="store_true",
        help="Do not stop after a result count; max-steps/state budget still apply",
    )
    compose.add_argument("--json", action="store_true", help="Emit JSON")
    compose.add_argument(
        "--include-installed",
        action="store_true",
        help="Explicitly import and merge installed specialized-pack providers",
    )

    providers = package_commands.add_parser(
        "providers", help="Inspect installed third-party pack entry points without importing"
    )
    providers.add_argument(
        "--load",
        action="store_true",
        help="Explicitly import and validate every discovered provider",
    )
    providers.add_argument("--json", action="store_true", help="Emit JSON")


def _active_registry(include_installed: bool) -> SpecializedPackRegistry:
    if not include_installed:
        return REFERENCE_SPECIALIZED_PACK_REGISTRY
    registry, _ = load_and_merge_installed_pack_providers(REFERENCE_SPECIALIZED_PACK_REGISTRY)
    return registry


def _list(as_json: bool, registry: SpecializedPackRegistry) -> int:
    if as_json:
        print(json.dumps(registry.to_dict(), indent=2, sort_keys=True))
        return 0
    print("ID\tRECIPES\tFEATURES\tMETRICS\tGATES\tEXTRACTION TARGET")
    for pack in registry.packs:
        print(
            f"{pack.id}\t{len(pack.recipes)}\t{len(pack.profiler_features)}\t"
            f"{len(pack.metrics)}\t{len(pack.gates)}\t{pack.extraction_target}"
        )
    return 0


def _show(pack_id: str, as_json: bool, registry: SpecializedPackRegistry) -> int:
    try:
        pack = registry.get(pack_id)
    except KeyError as exc:
        known = ", ".join(item.id for item in registry.packs)
        raise ValueError(f"unknown specialized pack {pack_id!r}; known packs: {known}") from exc
    if as_json:
        print(json.dumps(pack.to_dict(), indent=2, sort_keys=True))
        return 0
    print(f"{pack.id}@{pack.version} — {pack.title}")
    print(pack.description)
    print(
        f"delivery: {pack.current_distribution}:{pack.python_module} "
        f"→ future {pack.extraction_target}"
    )
    print(
        f"recipes={len(pack.recipes)} profiler_features={len(pack.profiler_features)} "
        f"metrics={len(pack.metrics)} gates={len(pack.gates)}"
    )
    print("RECIPES")
    for recipe in pack.recipes:
        print(
            f"- {recipe.id}: {', '.join(recipe.input_kind_ids)} → "
            f"{', '.join(recipe.output_kind_ids)}"
        )
    print("LIMITATIONS")
    for limitation in pack.limitations:
        print(f"- {limitation}")
    return 0


def _recommend(args: Any, registry: SpecializedPackRegistry) -> int:
    request = TaskPackageRequest(
        id="package-request.cli",
        description=args.description,
        category_ids=tuple(args.category),
        input_kind_ids=tuple(args.input_kind),
        output_kind_ids=tuple(args.output_kind),
        required_capability_ids=tuple(args.capability),
        preferred_pack_ids=tuple(args.prefer),
        excluded_pack_ids=tuple(args.exclude),
        granted_permissions=tuple(args.permission),
    )
    report = recommend_specialized_packs(
        request,
        registry,
        selection_limit=args.limit,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0
    print("RANK\tSTATUS\tSCORE\tPACK\tRECIPES")
    for rank, item in enumerate(report.recommendations, start=1):
        print(
            f"{rank}\t{item.status}\t{item.score:.3f}\t{item.pack_id}\t"
            f"{','.join(item.matching_recipe_ids) or '-'}"
        )
    print("recommended: " + (", ".join(report.recommended_pack_ids) or "none"))
    print(report.claim_boundary)
    return 0


def _compose(args: Any, registry: SpecializedPackRegistry) -> int:
    request = PackageCompositionRequest(
        id="composition-request.cli",
        starting_kind_ids=tuple(args.input_kind),
        goal_kind_ids=tuple(args.output_kind),
        pack_ids=tuple(args.pack),
        required_capability_ids=tuple(args.capability),
        max_steps=args.max_steps,
        state_budget=None if args.unbounded_states else args.state_budget,
        candidate_limit=None if args.all_candidates else args.candidate_limit,
    )
    report = compose_specialized_packs(request, registry)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0
    print(
        f"candidates={len(report.candidates)} visited={report.visited_state_count} "
        f"expanded={report.expanded_transition_count} queued={report.queued_unexpanded_state_count} "
        f"complete={str(report.complete_for_declared_budget).lower()}"
    )
    for candidate in report.candidates:
        print(
            f"{candidate.id}: "
            + " → ".join(
                f"{step.pack_id.removeprefix('specialized-pack.')}:{step.recipe_id.removeprefix('recipe.')}"
                for step in candidate.steps
            )
        )
    if not report.candidates:
        print(
            "unresolved goals: " + (", ".join(report.unresolved_goal_kind_ids) or "none observed")
        )
    print(report.claim_boundary)
    return 0


def _providers(load: bool, as_json: bool) -> int:
    references = discover_installed_pack_providers()
    payload: Any
    if load:
        payload = [item.to_dict() for item in load_installed_pack_providers(references)]
    else:
        payload = [item.to_dict() for item in references]
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if not payload:
        print("no installed specialized pack providers found")
        return 0
    if load:
        print("LOADED\tPROVIDER\tDISTRIBUTION\tPACKS\tERROR")
        for item in payload:
            reference = item["reference"]
            print(
                f"{str(item['loaded']).lower()}\t{reference['name']}\t"
                f"{reference['distribution']}\t{','.join(item['pack_ids']) or '-'}\t"
                f"{item['error'] or '-'}"
            )
    else:
        print("PROVIDER\tDISTRIBUTION\tTARGET")
        for item in payload:
            print(f"{item['name']}\t{item['distribution']}\t{item['value']}")
    return 0


def run_specialized_command(args: Any) -> int:
    command = args.specialized_package_command
    registry = _active_registry(getattr(args, "include_installed", False))
    if command == "list":
        return _list(args.json, registry)
    if command == "show":
        return _show(args.pack_id, args.json, registry)
    if command == "recommend":
        return _recommend(args, registry)
    if command == "compose":
        return _compose(args, registry)
    if command == "providers":
        return _providers(args.load, args.json)
    raise ValueError(f"unsupported specialized package command {command!r}")


__all__ = ["add_specialized_parser", "run_specialized_command"]
