"""Bounded typed composition of specialized-pack authoring recipes."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from solutiongraph.model import ID_RE, sha256_digest
from solutiongraph.specialized.model import PackRecipe, SpecializedPackRegistry


@dataclass(frozen=True)
class PackageCompositionRequest:
    id: str
    starting_kind_ids: tuple[str, ...]
    goal_kind_ids: tuple[str, ...]
    pack_ids: tuple[str, ...] = ()
    required_capability_ids: tuple[str, ...] = ()
    max_steps: int = 5
    state_budget: int | None = 5000
    candidate_limit: int | None = 50

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "composition_request") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be namespaced")
        for label in (
            "starting_kind_ids",
            "goal_kind_ids",
            "pack_ids",
            "required_capability_ids",
        ):
            values = getattr(self, label)
            if label in ("starting_kind_ids", "goal_kind_ids") and not values:
                problems.append(f"{path}.{label} must not be empty")
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not ID_RE.fullmatch(value) for value in values):
                problems.append(f"{path}.{label} must contain namespaced identifiers")
        if self.max_steps <= 0:
            problems.append(f"{path}.max_steps must be positive")
        if self.state_budget is not None and self.state_budget <= 0:
            problems.append(f"{path}.state_budget must be positive or null")
        if self.candidate_limit is not None and self.candidate_limit <= 0:
            problems.append(f"{path}.candidate_limit must be positive or null")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "starting_kind_ids": list(self.starting_kind_ids),
            "goal_kind_ids": list(self.goal_kind_ids),
            "pack_ids": list(self.pack_ids),
            "required_capability_ids": list(self.required_capability_ids),
            "max_steps": self.max_steps,
            "state_budget": self.state_budget,
            "candidate_limit": self.candidate_limit,
        }


@dataclass(frozen=True)
class CompositionStep:
    order: int
    pack_id: str
    recipe_id: str
    input_kind_ids: tuple[str, ...]
    output_kind_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    template_ids: tuple[str, ...]
    node_pack_ids: tuple[str, ...]

    def validate(self, path: str = "composition_step") -> list[str]:
        problems: list[str] = []
        if self.order <= 0:
            problems.append(f"{path}.order must be positive")
        for label, value in (("pack_id", self.pack_id), ("recipe_id", self.recipe_id)):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be namespaced")
        for label in (
            "input_kind_ids",
            "output_kind_ids",
            "capability_ids",
            "template_ids",
            "node_pack_ids",
        ):
            values = getattr(self, label)
            if label != "node_pack_ids" and not values:
                problems.append(f"{path}.{label} must not be empty")
            if len(values) != len(set(values)) or any(
                not ID_RE.fullmatch(value) for value in values
            ):
                problems.append(f"{path}.{label} must be unique namespaced identifiers")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "pack_id": self.pack_id,
            "recipe_id": self.recipe_id,
            "input_kind_ids": list(self.input_kind_ids),
            "output_kind_ids": list(self.output_kind_ids),
            "capability_ids": list(self.capability_ids),
            "template_ids": list(self.template_ids),
            "node_pack_ids": list(self.node_pack_ids),
        }


@dataclass(frozen=True)
class CompositionCandidate:
    id: str
    steps: tuple[CompositionStep, ...]
    available_kind_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    goal_kind_ids: tuple[str, ...]
    required_capability_ids: tuple[str, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "composition_candidate") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be namespaced")
        if not self.steps:
            problems.append(f"{path}.steps must not be empty; pass-through is never implicit")
        if tuple(step.order for step in self.steps) != tuple(range(1, len(self.steps) + 1)):
            problems.append(f"{path}.steps order must be contiguous from one")
        recipe_ids = [step.recipe_id for step in self.steps]
        if len(recipe_ids) != len(set(recipe_ids)):
            problems.append(f"{path}.steps may not repeat a recipe")
        for index, step in enumerate(self.steps):
            problems.extend(step.validate(f"{path}.steps[{index}]"))
        for label in (
            "available_kind_ids",
            "capability_ids",
            "goal_kind_ids",
            "required_capability_ids",
        ):
            values = getattr(self, label)
            if len(values) != len(set(values)) or any(
                not ID_RE.fullmatch(value) for value in values
            ):
                problems.append(f"{path}.{label} must be unique namespaced identifiers")
        if set(self.goal_kind_ids) - set(self.available_kind_ids):
            problems.append(f"{path} does not satisfy all goal kinds")
        if set(self.required_capability_ids) - set(self.capability_ids):
            problems.append(f"{path} does not satisfy all required capabilities")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "steps": [step.to_dict() for step in self.steps],
            "available_kind_ids": list(self.available_kind_ids),
            "capability_ids": list(self.capability_ids),
            "goal_kind_ids": list(self.goal_kind_ids),
            "required_capability_ids": list(self.required_capability_ids),
        }


@dataclass(frozen=True)
class PackageCompositionReport:
    id: str
    request: PackageCompositionRequest
    registry_digest: str
    searched_pack_ids: tuple[str, ...]
    total_recipe_count: int
    candidates: tuple[CompositionCandidate, ...]
    visited_state_count: int
    expanded_transition_count: int
    incompatible_transition_count: int
    repeated_recipe_count: int
    depth_limited_state_count: int
    queued_unexpanded_state_count: int
    state_budget_exhausted: bool
    candidate_limit_exhausted: bool
    observed_kind_ids: tuple[str, ...]
    observed_capability_ids: tuple[str, ...]
    unresolved_goal_kind_ids: tuple[str, ...]
    unresolved_capability_ids: tuple[str, ...]
    complete_for_declared_budget: bool
    claim_boundary: str

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(
        self, registry: SpecializedPackRegistry, path: str = "composition_report"
    ) -> list[str]:
        problems = self.request.validate(f"{path}.request")
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be namespaced")
        if self.registry_digest != registry.digest:
            problems.append(f"{path}.registry_digest does not match")
        known_packs = {pack.id for pack in registry.packs}
        if not self.searched_pack_ids or set(self.searched_pack_ids) - known_packs:
            problems.append(f"{path}.searched_pack_ids must be known and non-empty")
        if self.total_recipe_count <= 0:
            problems.append(f"{path}.total_recipe_count must be positive")
        for label in (
            "visited_state_count",
            "expanded_transition_count",
            "incompatible_transition_count",
            "repeated_recipe_count",
            "depth_limited_state_count",
            "queued_unexpanded_state_count",
        ):
            if getattr(self, label) < 0:
                problems.append(f"{path}.{label} must not be negative")
        for index, candidate in enumerate(self.candidates):
            problems.extend(candidate.validate(f"{path}.candidates[{index}]"))
        candidate_ids = [item.id for item in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            problems.append(f"{path}.candidates ids must be unique")
        for label in (
            "observed_kind_ids",
            "observed_capability_ids",
            "unresolved_goal_kind_ids",
            "unresolved_capability_ids",
        ):
            values = getattr(self, label)
            if len(values) != len(set(values)) or any(
                not ID_RE.fullmatch(value) for value in values
            ):
                problems.append(f"{path}.{label} must be unique namespaced identifiers")
        expected_complete = not self.state_budget_exhausted and not self.candidate_limit_exhausted
        if self.complete_for_declared_budget != expected_complete:
            problems.append(f"{path}.complete_for_declared_budget is inconsistent")
        if not self.claim_boundary.strip():
            problems.append(f"{path}.claim_boundary must not be empty")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "specialized_pack_model_version": "0.1",
            "id": self.id,
            "request": self.request.to_dict(),
            "request_digest": self.request.digest,
            "registry_digest": self.registry_digest,
            "searched_pack_ids": list(self.searched_pack_ids),
            "total_recipe_count": self.total_recipe_count,
            "candidates": [item.to_dict() for item in self.candidates],
            "search_accounting": {
                "visited_state_count": self.visited_state_count,
                "expanded_transition_count": self.expanded_transition_count,
                "incompatible_transition_count": self.incompatible_transition_count,
                "repeated_recipe_count": self.repeated_recipe_count,
                "depth_limited_state_count": self.depth_limited_state_count,
                "queued_unexpanded_state_count": self.queued_unexpanded_state_count,
                "state_budget_exhausted": self.state_budget_exhausted,
                "candidate_limit_exhausted": self.candidate_limit_exhausted,
                "complete_for_declared_budget": self.complete_for_declared_budget,
            },
            "observed_kind_ids": list(self.observed_kind_ids),
            "observed_capability_ids": list(self.observed_capability_ids),
            "unresolved_goal_kind_ids": list(self.unresolved_goal_kind_ids),
            "unresolved_capability_ids": list(self.unresolved_capability_ids),
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class _RecipeBinding:
    pack_id: str
    recipe: PackRecipe


@dataclass(frozen=True)
class _State:
    kinds: frozenset[str]
    capabilities: frozenset[str]
    steps: tuple[CompositionStep, ...]
    used_recipe_ids: frozenset[str]


def compose_specialized_packs(
    request: PackageCompositionRequest,
    registry: SpecializedPackRegistry,
) -> PackageCompositionReport:
    """Enumerate typed recipe chains under visible state/depth/result budgets."""

    problems = request.validate()
    if problems:
        raise ValueError("invalid package composition request: " + "; ".join(problems))
    registry_problems = registry.validate()
    if registry_problems:
        raise ValueError("invalid specialized pack registry: " + "; ".join(registry_problems))

    known_pack_ids = {pack.id for pack in registry.packs}
    searched_pack_ids = request.pack_ids or tuple(pack.id for pack in registry.packs)
    unknown = sorted(set(searched_pack_ids) - known_pack_ids)
    if unknown:
        raise ValueError("composition references unknown packs: " + ", ".join(unknown))
    selected = [registry.get(pack_id) for pack_id in searched_pack_ids]
    bindings = tuple(
        sorted(
            (_RecipeBinding(pack.id, recipe) for pack in selected for recipe in pack.recipes),
            key=lambda item: (item.pack_id, item.recipe.id),
        )
    )

    queue: deque[_State] = deque(
        (
            _State(
                kinds=frozenset(request.starting_kind_ids),
                capabilities=frozenset(),
                steps=(),
                used_recipe_ids=frozenset(),
            ),
        )
    )
    candidates: list[CompositionCandidate] = []
    visited = 0
    expanded = 0
    incompatible = 0
    repeated = 0
    depth_limited = 0
    state_budget_exhausted = False
    candidate_limit_exhausted = False
    observed_kinds = set(request.starting_kind_ids)
    observed_capabilities: set[str] = set()

    while queue:
        if request.state_budget is not None and visited >= request.state_budget:
            state_budget_exhausted = True
            break
        state = queue.popleft()
        visited += 1
        observed_kinds.update(state.kinds)
        observed_capabilities.update(state.capabilities)

        if (
            state.steps
            and set(request.goal_kind_ids) <= state.kinds
            and set(request.required_capability_ids) <= state.capabilities
        ):
            identity = sha256_digest(
                {
                    "request": request.digest,
                    "steps": [step.recipe_id for step in state.steps],
                }
            ).removeprefix("sha256:")[:20]
            candidates.append(
                CompositionCandidate(
                    id=f"composition-candidate.{identity}",
                    steps=state.steps,
                    available_kind_ids=tuple(sorted(state.kinds)),
                    capability_ids=tuple(sorted(state.capabilities)),
                    goal_kind_ids=request.goal_kind_ids,
                    required_capability_ids=request.required_capability_ids,
                )
            )
            if request.candidate_limit is not None and len(candidates) >= request.candidate_limit:
                candidate_limit_exhausted = True
                break

        if len(state.steps) >= request.max_steps:
            depth_limited += 1
            continue

        for binding in bindings:
            recipe = binding.recipe
            if recipe.id in state.used_recipe_ids:
                repeated += 1
                continue
            if not set(recipe.input_kind_ids) <= state.kinds:
                incompatible += 1
                continue
            expanded += 1
            step = CompositionStep(
                order=len(state.steps) + 1,
                pack_id=binding.pack_id,
                recipe_id=recipe.id,
                input_kind_ids=recipe.input_kind_ids,
                output_kind_ids=recipe.output_kind_ids,
                capability_ids=recipe.capability_ids,
                template_ids=recipe.template_ids,
                node_pack_ids=recipe.node_pack_ids,
            )
            queue.append(
                _State(
                    kinds=state.kinds | frozenset(recipe.output_kind_ids),
                    capabilities=state.capabilities | frozenset(recipe.capability_ids),
                    steps=(*state.steps, step),
                    used_recipe_ids=state.used_recipe_ids | {recipe.id},
                )
            )

    unresolved_goals = tuple(sorted(set(request.goal_kind_ids) - observed_kinds))
    unresolved_capabilities = tuple(
        sorted(set(request.required_capability_ids) - observed_capabilities)
    )
    report = PackageCompositionReport(
        id=f"composition.specialized.{request.digest.removeprefix('sha256:')[:16]}",
        request=request,
        registry_digest=registry.digest,
        searched_pack_ids=tuple(searched_pack_ids),
        total_recipe_count=len(bindings),
        candidates=tuple(candidates),
        visited_state_count=visited,
        expanded_transition_count=expanded,
        incompatible_transition_count=incompatible,
        repeated_recipe_count=repeated,
        depth_limited_state_count=depth_limited,
        queued_unexpanded_state_count=len(queue),
        state_budget_exhausted=state_budget_exhausted,
        candidate_limit_exhausted=candidate_limit_exhausted,
        observed_kind_ids=tuple(sorted(observed_kinds)),
        observed_capability_ids=tuple(sorted(observed_capabilities)),
        unresolved_goal_kind_ids=unresolved_goals,
        unresolved_capability_ids=unresolved_capabilities,
        complete_for_declared_budget=(not state_budget_exhausted and not candidate_limit_exhausted),
        claim_boundary=(
            "Recipe composition is an authoring hypothesis over exact declared artifact "
            "kinds. It performs no implicit conversion and does not prove that referenced "
            "templates, nodes, permissions, effects, or task-specific schemas compile "
            "together. Instantiate a ProgramGraph, freeze discovery, and run full compiler "
            "admission before execution."
        ),
    )
    report_problems = report.validate(registry)
    if report_problems:
        raise ValueError("invalid package composition report: " + "; ".join(report_problems))
    return report


__all__ = [
    "CompositionCandidate",
    "CompositionStep",
    "PackageCompositionReport",
    "PackageCompositionRequest",
    "compose_specialized_packs",
]
