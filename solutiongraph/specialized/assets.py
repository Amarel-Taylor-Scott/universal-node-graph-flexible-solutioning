"""Exact checked-in asset inventory for specialized-pack cross-reference checks."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from typing import Any

from solutiongraph.model import sha256_digest
from solutiongraph.specialized.model import SpecializedPackDefinition, SpecializedPackRegistry


@dataclass(frozen=True)
class SpecializedAssetInventory:
    """Closed-world identifier inventory for one repository release."""

    domain_pack_ids: tuple[str, ...]
    category_ids: tuple[str, ...]
    template_ids: tuple[str, ...]
    node_pack_ids: tuple[str, ...]
    question_pack_ids: tuple[str, ...]
    design_pack_ids: tuple[str, ...]
    example_ids: tuple[str, ...]
    benchmark_ids: tuple[str, ...]
    agent_benchmark_ids: tuple[str, ...]
    arena_task_ids: tuple[str, ...]
    adapter_ids: tuple[str, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_pack_ids": list(self.domain_pack_ids),
            "category_ids": list(self.category_ids),
            "template_ids": list(self.template_ids),
            "node_pack_ids": list(self.node_pack_ids),
            "question_pack_ids": list(self.question_pack_ids),
            "design_pack_ids": list(self.design_pack_ids),
            "example_ids": list(self.example_ids),
            "benchmark_ids": list(self.benchmark_ids),
            "agent_benchmark_ids": list(self.agent_benchmark_ids),
            "arena_task_ids": list(self.arena_task_ids),
            "adapter_ids": list(self.adapter_ids),
        }


@lru_cache(maxsize=1)
def reference_specialized_asset_inventory() -> SpecializedAssetInventory:
    from solutiongraph.agent_bench.config import (
        command_matrix_example_suite,
        reference_agent_benchmark_suite,
    )
    from solutiongraph.arena import UNIVERSAL_DAG_ARENA
    from solutiongraph.benchmark_library import REFERENCE_BENCHMARKS
    from solutiongraph.design_atlas import REFERENCE_DESIGN_PACKS
    from solutiongraph.examples import all_examples
    from solutiongraph.integrations import REFERENCE_INTEGRATION_ADAPTERS
    from solutiongraph.pack_library import REFERENCE_NODE_PACKS
    from solutiongraph.question_packs import REFERENCE_QUESTION_PACKS
    from solutiongraph.stdlib_pack import STANDARD_LIBRARY_NODE_PACK
    from solutiongraph.task_categories import DEFAULT_TASK_CATEGORY_REGISTRY
    from solutiongraph.template_library import REFERENCE_TEMPLATES
    from solutiongraph.universal import REFERENCE_DOMAIN_PACKS

    node_packs = (*REFERENCE_NODE_PACKS, STANDARD_LIBRARY_NODE_PACK)
    return SpecializedAssetInventory(
        domain_pack_ids=tuple(sorted(item.id for item in REFERENCE_DOMAIN_PACKS)),
        category_ids=tuple(sorted(item.id for item in DEFAULT_TASK_CATEGORY_REGISTRY.categories)),
        template_ids=tuple(sorted(item.id for item in REFERENCE_TEMPLATES.templates)),
        node_pack_ids=tuple(sorted({item.id for item in node_packs})),
        question_pack_ids=tuple(sorted(item.id for item in REFERENCE_QUESTION_PACKS)),
        design_pack_ids=tuple(sorted(item.id for item in REFERENCE_DESIGN_PACKS)),
        example_ids=tuple(sorted(item.id for item in all_examples())),
        benchmark_ids=tuple(sorted(item.id for item in REFERENCE_BENCHMARKS)),
        agent_benchmark_ids=tuple(
            sorted(
                {
                    reference_agent_benchmark_suite().id,
                    command_matrix_example_suite().id,
                }
            )
        ),
        arena_task_ids=tuple(sorted(item.id for item in UNIVERSAL_DAG_ARENA.tasks)),
        adapter_ids=tuple(sorted(item.id for item in REFERENCE_INTEGRATION_ADAPTERS)),
    )


def _unknown(values: tuple[str, ...], known: tuple[str, ...], path: str) -> list[str]:
    missing = sorted(set(values) - set(known))
    return [f"{path} references unknown assets: {', '.join(missing)}"] if missing else []


def validate_specialized_pack_assets(
    pack: SpecializedPackDefinition,
    inventory: SpecializedAssetInventory,
    path: str = "specialized_pack",
) -> list[str]:
    problems: list[str] = []
    problems.extend(
        _unknown(pack.domain_pack_ids, inventory.domain_pack_ids, f"{path}.domain_pack_ids")
    )
    problems.extend(
        _unknown(pack.task_category_ids, inventory.category_ids, f"{path}.task_category_ids")
    )
    for index, recipe in enumerate(pack.recipes):
        recipe_path = f"{path}.recipes[{index}]"
        for label, known in (
            ("category_ids", inventory.category_ids),
            ("template_ids", inventory.template_ids),
            ("node_pack_ids", inventory.node_pack_ids),
            ("question_pack_ids", inventory.question_pack_ids),
            ("design_pack_ids", inventory.design_pack_ids),
            ("example_ids", inventory.example_ids),
            ("benchmark_ids", inventory.benchmark_ids),
            ("agent_benchmark_ids", inventory.agent_benchmark_ids),
            ("arena_task_ids", inventory.arena_task_ids),
            ("adapter_ids", inventory.adapter_ids),
        ):
            problems.extend(_unknown(getattr(recipe, label), known, f"{recipe_path}.{label}"))
    return problems


def validate_specialized_pack_catalog(
    registry: SpecializedPackRegistry,
    inventory: SpecializedAssetInventory | None = None,
) -> list[str]:
    """Validate structure, asset references, and built-in module bindings."""

    inventory = inventory or reference_specialized_asset_inventory()
    problems = list(registry.validate())
    for index, pack in enumerate(registry.packs):
        path = f"specialized_pack_registry.packs[{index}]"
        problems.extend(validate_specialized_pack_assets(pack, inventory, path))
        try:
            module_pack = import_module(pack.python_module).PACK
        except (ImportError, AttributeError) as exc:
            problems.append(f"{path}.python_module cannot expose PACK: {exc}")
        else:
            if module_pack != pack:
                problems.append(f"{path}.python_module PACK differs from registry definition")
    return problems


__all__ = [
    "SpecializedAssetInventory",
    "reference_specialized_asset_inventory",
    "validate_specialized_pack_assets",
    "validate_specialized_pack_catalog",
]
