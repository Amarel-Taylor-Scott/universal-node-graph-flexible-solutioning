"""Declare-before-load discovery for third-party specialized pack providers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from importlib import metadata
from typing import Any

from solutiongraph.specialized.model import (
    SPECIALIZED_PACK_ENTRY_POINT_GROUP,
    SpecializedPackDefinition,
    SpecializedPackRegistry,
)


@dataclass(frozen=True)
class PackProviderReference:
    """Import-free installed entry-point metadata."""

    name: str
    value: str
    group: str
    distribution: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "value": self.value,
            "group": self.group,
            "distribution": self.distribution,
        }


@dataclass(frozen=True)
class PackProviderLoadResult:
    reference: PackProviderReference
    loaded: bool
    packs: tuple[SpecializedPackDefinition, ...]
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference.to_dict(),
            "loaded": self.loaded,
            "pack_ids": [pack.id for pack in self.packs],
            "pack_digests": [pack.digest for pack in self.packs],
            "error": self.error,
        }


def _entry_points() -> tuple[metadata.EntryPoint, ...]:
    points = metadata.entry_points()
    if hasattr(points, "select"):
        selected = points.select(group=SPECIALIZED_PACK_ENTRY_POINT_GROUP)
    else:  # pragma: no cover - compatibility with old importlib metadata
        selected = points.get(SPECIALIZED_PACK_ENTRY_POINT_GROUP, ())
    return tuple(selected)


def discover_installed_pack_providers() -> tuple[PackProviderReference, ...]:
    """Enumerate entry-point declarations without importing provider code."""

    references = []
    for point in _entry_points():
        distribution = point.dist.name if point.dist is not None else ""
        references.append(
            PackProviderReference(
                name=point.name,
                value=point.value,
                group=point.group,
                distribution=distribution,
            )
        )
    return tuple(sorted(references, key=lambda item: (item.name, item.distribution, item.value)))


def _coerce_packs(value: Any) -> tuple[SpecializedPackDefinition, ...]:
    if callable(value) and not isinstance(value, type):
        value = value()
    if isinstance(value, SpecializedPackDefinition):
        return (value,)
    if isinstance(value, SpecializedPackRegistry):
        return value.packs
    if isinstance(value, (tuple, list)) and all(
        isinstance(item, SpecializedPackDefinition) for item in value
    ):
        return tuple(value)
    raise TypeError(
        "provider must expose a SpecializedPackDefinition, SpecializedPackRegistry, "
        "a sequence of definitions, or a zero-argument callable returning one"
    )


def load_installed_pack_provider(
    reference: PackProviderReference,
) -> PackProviderLoadResult:
    """Explicitly import and validate one previously discovered provider."""

    match = next(
        (
            point
            for point in _entry_points()
            if point.name == reference.name
            and point.value == reference.value
            and point.group == reference.group
            and (point.dist.name if point.dist is not None else "") == reference.distribution
        ),
        None,
    )
    if match is None:
        return PackProviderLoadResult(reference, False, (), "entry point is no longer installed")
    try:
        packs = _coerce_packs(match.load())
        problems = [
            problem
            for index, pack in enumerate(packs)
            for problem in pack.validate(f"provider.packs[{index}]")
        ]
        identities = [(pack.id, pack.version) for pack in packs]
        if len(identities) != len(set(identities)):
            problems.append("provider pack identities must be unique")
        if problems:
            raise ValueError("; ".join(problems))
    except Exception as exc:  # provider failures are evidence, not host crashes
        return PackProviderLoadResult(reference, False, (), f"{type(exc).__name__}: {exc}")
    return PackProviderLoadResult(reference, True, packs)


def load_installed_pack_providers(
    references: Iterable[PackProviderReference] | None = None,
) -> tuple[PackProviderLoadResult, ...]:
    selected = tuple(references) if references is not None else discover_installed_pack_providers()
    return tuple(load_installed_pack_provider(reference) for reference in selected)


def merge_specialized_packs(
    registry: SpecializedPackRegistry,
    packs: Iterable[SpecializedPackDefinition],
    *,
    registry_id: str = "registry.merged-specialized-packs",
    version: str = "0.1.0",
) -> SpecializedPackRegistry:
    """Merge exact definitions; conflicting identities fail instead of overriding."""

    by_id = {pack.id: pack for pack in registry.packs}
    for pack in packs:
        current = by_id.get(pack.id)
        if current is not None and current.digest != pack.digest:
            raise ValueError(
                f"conflicting specialized pack definition for {pack.id}: "
                f"{current.version} versus {pack.version}"
            )
        by_id[pack.id] = pack
    merged = SpecializedPackRegistry(
        id=registry_id,
        version=version,
        packs=tuple(sorted(by_id.values(), key=lambda item: item.id)),
        description=(
            "Merged specialized capability-pack registry. Exact duplicate digests are "
            "deduplicated; conflicting definitions never override one another."
        ),
    )
    problems = merged.validate()
    if problems:
        raise ValueError("invalid merged specialized pack registry: " + "; ".join(problems))
    return merged


def load_and_merge_installed_pack_providers(
    registry: SpecializedPackRegistry,
    references: Iterable[PackProviderReference] | None = None,
) -> tuple[SpecializedPackRegistry, tuple[PackProviderLoadResult, ...]]:
    """Explicitly load installed providers and merge only validated definitions.

    The operation is fail-closed: one provider failure prevents construction of
    a partial registry. Call ``load_installed_pack_providers`` directly when an
    operator wants to inspect and handle individual failures instead.
    """

    results = load_installed_pack_providers(references)
    failures = tuple(item for item in results if not item.loaded)
    if failures:
        details = "; ".join(
            f"{item.reference.distribution or '<unknown>'}:{item.reference.name}: {item.error}"
            for item in failures
        )
        raise ValueError("failed to load specialized pack providers: " + details)
    packs = tuple(pack for item in results for pack in item.packs)
    return merge_specialized_packs(registry, packs), results


__all__ = [
    "PackProviderLoadResult",
    "PackProviderReference",
    "discover_installed_pack_providers",
    "load_and_merge_installed_pack_providers",
    "load_installed_pack_provider",
    "load_installed_pack_providers",
    "merge_specialized_packs",
]
