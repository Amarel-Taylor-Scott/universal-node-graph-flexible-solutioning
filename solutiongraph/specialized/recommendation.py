"""Transparent all-visible recommendation for specialized capability packs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from typing import Any

from solutiongraph.model import ID_RE, sha256_digest
from solutiongraph.specialized.model import SpecializedPackDefinition, SpecializedPackRegistry
from solutiongraph.task_categories import DEFAULT_TASK_CATEGORY_REGISTRY
from solutiongraph.tasking import TaskContract


def _normalized_text(value: str) -> str:
    words = re.sub(r"[^\w]+", " ", value.casefold()).replace("_", " ")
    return " ".join(words.split())


def _contains_term(text: str, term: str) -> bool:
    normalized_term = _normalized_text(term)
    return bool(normalized_term) and f" {normalized_term} " in f" {text} "


@dataclass(frozen=True)
class TaskPackageRequest:
    """Implementation-neutral hints used only to nominate capability packs."""

    id: str
    description: str
    category_ids: tuple[str, ...] = ()
    input_kind_ids: tuple[str, ...] = ()
    output_kind_ids: tuple[str, ...] = ()
    required_capability_ids: tuple[str, ...] = ()
    preferred_pack_ids: tuple[str, ...] = ()
    excluded_pack_ids: tuple[str, ...] = ()
    granted_permissions: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "task_package_request") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be namespaced")
        if not self.description.strip():
            problems.append(f"{path}.description must not be empty")
        for label in (
            "category_ids",
            "input_kind_ids",
            "output_kind_ids",
            "required_capability_ids",
            "preferred_pack_ids",
            "excluded_pack_ids",
            "granted_permissions",
        ):
            values = getattr(self, label)
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not ID_RE.fullmatch(value) for value in values):
                problems.append(f"{path}.{label} must contain namespaced identifiers")
        overlap = sorted(set(self.preferred_pack_ids) & set(self.excluded_pack_ids))
        if overlap:
            problems.append(
                f"{path} cannot prefer and exclude the same packs: {', '.join(overlap)}"
            )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "category_ids": list(self.category_ids),
            "input_kind_ids": list(self.input_kind_ids),
            "output_kind_ids": list(self.output_kind_ids),
            "required_capability_ids": list(self.required_capability_ids),
            "preferred_pack_ids": list(self.preferred_pack_ids),
            "excluded_pack_ids": list(self.excluded_pack_ids),
            "granted_permissions": list(self.granted_permissions),
        }


@dataclass(frozen=True)
class PackRecommendation:
    pack_id: str
    pack_digest: str
    score: float
    status: str
    components: tuple[tuple[str, float], ...]
    matched_category_ids: tuple[str, ...]
    matched_terms: tuple[str, ...]
    matched_capability_ids: tuple[str, ...]
    missing_capability_ids: tuple[str, ...]
    matched_input_kind_ids: tuple[str, ...]
    matched_output_kind_ids: tuple[str, ...]
    matching_recipe_ids: tuple[str, ...]
    blocked_permissions: tuple[str, ...]
    reasons: tuple[str, ...]

    def validate(self, path: str = "recommendation") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.pack_id):
            problems.append(f"{path}.pack_id must be namespaced")
        if not self.pack_digest.startswith("sha256:"):
            problems.append(f"{path}.pack_digest must be a sha256 digest")
        if not isfinite(self.score) or not 0.0 <= self.score <= 1.0:
            problems.append(f"{path}.score must be finite and between zero and one")
        if self.status not in ("candidate", "partial", "excluded"):
            problems.append(f"{path}.status is unsupported")
        component_names = [key for key, _ in self.components]
        if len(component_names) != len(set(component_names)):
            problems.append(f"{path}.components names must be unique")
        if any(not isfinite(value) or not 0.0 <= value <= 1.0 for _, value in self.components):
            problems.append(f"{path}.components must be between zero and one")
        for label in (
            "matched_category_ids",
            "matched_capability_ids",
            "missing_capability_ids",
            "matched_input_kind_ids",
            "matched_output_kind_ids",
            "matching_recipe_ids",
            "blocked_permissions",
        ):
            values = getattr(self, label)
            if len(values) != len(set(values)) or any(
                not ID_RE.fullmatch(value) for value in values
            ):
                problems.append(f"{path}.{label} must be unique namespaced identifiers")
        if len(self.matched_terms) != len(set(self.matched_terms)):
            problems.append(f"{path}.matched_terms must be unique")
        if not self.reasons:
            problems.append(f"{path}.reasons must not be empty")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "pack_digest": self.pack_digest,
            "score": self.score,
            "status": self.status,
            "components": dict(self.components),
            "matched_category_ids": list(self.matched_category_ids),
            "matched_terms": list(self.matched_terms),
            "matched_capability_ids": list(self.matched_capability_ids),
            "missing_capability_ids": list(self.missing_capability_ids),
            "matched_input_kind_ids": list(self.matched_input_kind_ids),
            "matched_output_kind_ids": list(self.matched_output_kind_ids),
            "matching_recipe_ids": list(self.matching_recipe_ids),
            "blocked_permissions": list(self.blocked_permissions),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class PackageRecommendationReport:
    id: str
    request: TaskPackageRequest
    registry_digest: str
    recommendations: tuple[PackRecommendation, ...]
    recommended_pack_ids: tuple[str, ...]
    selection_limit: int
    scoring_method: str
    claim_boundary: str

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(
        self, registry: SpecializedPackRegistry, path: str = "recommendation_report"
    ) -> list[str]:
        problems = self.request.validate(f"{path}.request")
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be namespaced")
        if self.registry_digest != registry.digest:
            problems.append(f"{path}.registry_digest does not match the registry")
        if self.selection_limit <= 0:
            problems.append(f"{path}.selection_limit must be positive")
        if not self.scoring_method.strip() or not self.claim_boundary.strip():
            problems.append(f"{path}.scoring_method and claim_boundary must not be empty")
        expected = {pack.id for pack in registry.packs}
        actual = [item.pack_id for item in self.recommendations]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            problems.append(f"{path}.recommendations must expose every registry pack once")
        for index, item in enumerate(self.recommendations):
            problems.extend(item.validate(f"{path}.recommendations[{index}]"))
        if len(self.recommended_pack_ids) != len(set(self.recommended_pack_ids)):
            problems.append(f"{path}.recommended_pack_ids must be unique")
        if len(self.recommended_pack_ids) > self.selection_limit:
            problems.append(f"{path}.recommended_pack_ids exceeds selection_limit")
        if set(self.recommended_pack_ids) - expected:
            problems.append(f"{path}.recommended_pack_ids contains unknown packs")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "specialized_pack_model_version": "0.1",
            "id": self.id,
            "request": self.request.to_dict(),
            "request_digest": self.request.digest,
            "registry_digest": self.registry_digest,
            "recommendations": [item.to_dict() for item in self.recommendations],
            "recommended_pack_ids": list(self.recommended_pack_ids),
            "selection_limit": self.selection_limit,
            "scoring_method": self.scoring_method,
            "claim_boundary": self.claim_boundary,
        }


def request_from_task_contract(contract: TaskContract) -> TaskPackageRequest:
    """Derive transparent lexical/category hints from a task contract."""

    matches = DEFAULT_TASK_CATEGORY_REGISTRY.classify(contract, limit=None)
    return TaskPackageRequest(
        id=f"package-request.{contract.id}",
        description=" ".join((contract.title, contract.intent, contract.success_contract)),
        category_ids=tuple(item.category_id for item in matches),
        input_kind_ids=tuple(port.value_type.id for port in contract.inputs),
        output_kind_ids=tuple(port.value_type.id for port in contract.outputs),
        granted_permissions=contract.granted_permissions,
    )


def _category_closure(pack: SpecializedPackDefinition) -> set[str]:
    closure = set(pack.task_category_ids)
    frontier = list(closure)
    while frontier:
        category_id = frontier.pop()
        try:
            parents = DEFAULT_TASK_CATEGORY_REGISTRY.get(category_id).parent_ids
        except KeyError:
            continue
        for parent in parents:
            if parent not in closure:
                closure.add(parent)
                frontier.append(parent)
    return closure


def _recipe_score(request: TaskPackageRequest, pack: SpecializedPackDefinition, recipe) -> float:
    score = 0.0
    if set(request.category_ids) & set(recipe.category_ids):
        score += 0.35
    if set(request.required_capability_ids) & set(recipe.capability_ids):
        score += 0.25
    if set(request.input_kind_ids) & set(recipe.input_kind_ids):
        score += 0.20
    if set(request.output_kind_ids) & set(recipe.output_kind_ids):
        score += 0.20
    text = _normalized_text(request.description)
    recipe_words = (*pack.signal_terms, recipe.title, recipe.description)
    if any(_contains_term(text, term) for term in recipe_words):
        score += 0.25
    return min(score, 1.0)


def recommend_specialized_packs(
    request: TaskPackageRequest,
    registry: SpecializedPackRegistry,
    *,
    selection_limit: int = 3,
) -> PackageRecommendationReport:
    """Rank every pack with inspectable evidence and no hidden candidate filter."""

    request_problems = request.validate()
    if request_problems:
        raise ValueError("invalid task package request: " + "; ".join(request_problems))
    registry_problems = registry.validate()
    if registry_problems:
        raise ValueError("invalid specialized pack registry: " + "; ".join(registry_problems))
    if selection_limit <= 0:
        raise ValueError("selection_limit must be positive")

    known_pack_ids = {pack.id for pack in registry.packs}
    unknown = sorted(
        (set(request.preferred_pack_ids) | set(request.excluded_pack_ids)) - known_pack_ids
    )
    if unknown:
        raise ValueError("request references unknown specialized packs: " + ", ".join(unknown))

    normalized = _normalized_text(request.description)
    recommendations: list[PackRecommendation] = []
    for pack in registry.packs:
        category_closure = _category_closure(pack)
        matched_categories = tuple(sorted(set(request.category_ids) & category_closure))
        matched_terms = tuple(
            sorted(term for term in pack.signal_terms if _contains_term(normalized, term))
        )
        capabilities = set(pack.capability_ids)
        matched_capabilities = tuple(sorted(set(request.required_capability_ids) & capabilities))
        missing_capabilities = tuple(sorted(set(request.required_capability_ids) - capabilities))
        matched_inputs = tuple(sorted(set(request.input_kind_ids) & set(pack.input_kind_ids)))
        matched_outputs = tuple(sorted(set(request.output_kind_ids) & set(pack.output_kind_ids)))

        active: list[tuple[str, float, float]] = [("terms", min(len(matched_terms) / 3, 1.0), 0.25)]
        if request.category_ids:
            active.append(
                (
                    "categories",
                    len(matched_categories) / len(set(request.category_ids)),
                    0.30,
                )
            )
        if request.required_capability_ids:
            active.append(
                (
                    "capabilities",
                    len(matched_capabilities) / len(set(request.required_capability_ids)),
                    0.25,
                )
            )
        if request.input_kind_ids:
            active.append(
                (
                    "inputs",
                    len(matched_inputs) / len(set(request.input_kind_ids)),
                    0.10,
                )
            )
        if request.output_kind_ids:
            active.append(
                (
                    "outputs",
                    len(matched_outputs) / len(set(request.output_kind_ids)),
                    0.10,
                )
            )
        if pack.id in request.preferred_pack_ids:
            active.append(("preference", 1.0, 0.15))
        total_weight = sum(weight for _, _, weight in active)
        score = sum(value * weight for _, value, weight in active) / total_weight

        recipe_scores = sorted(
            ((_recipe_score(request, pack, recipe), recipe.id) for recipe in pack.recipes),
            key=lambda item: (-item[0], item[1]),
        )
        matching_recipes = tuple(
            recipe_id for score_value, recipe_id in recipe_scores if score_value > 0
        )
        best_recipe_score = recipe_scores[0][0]
        best_recipe_ids = {
            recipe_id
            for score_value, recipe_id in recipe_scores
            if score_value == best_recipe_score and score_value > 0
        }
        considered_recipes = [
            recipe for recipe in pack.recipes if recipe.id in best_recipe_ids
        ] or list(pack.recipes)
        # A pack is permission-blocked only when every equally best recipe needs
        # the same ungranted permission.  Unioning permissions across every
        # loosely matched recipe made a read-only investigation look effectful
        # merely because the same pack also offered an optional response recipe.
        permission_sets = [set(recipe.permissions) for recipe in considered_recipes]
        unavoidable_permissions = (
            set.intersection(*permission_sets) if permission_sets else set()
        )
        blocked_permissions = tuple(
            sorted(unavoidable_permissions - set(request.granted_permissions))
        )

        interface_gap = bool(request.input_kind_ids and not matched_inputs) or bool(
            request.output_kind_ids and not matched_outputs
        )
        if pack.id in request.excluded_pack_ids:
            status = "excluded"
            score = 0.0
        elif missing_capabilities or interface_gap or blocked_permissions:
            status = "partial"
        else:
            status = "candidate"
        reasons: list[str] = []
        if matched_categories:
            reasons.append("matched task categories: " + ", ".join(matched_categories))
        if matched_terms:
            reasons.append("matched description terms: " + ", ".join(matched_terms))
        if matched_capabilities:
            reasons.append("covered requested capabilities: " + ", ".join(matched_capabilities))
        if matched_inputs or matched_outputs:
            reasons.append("matched declared recipe interfaces")
        if missing_capabilities:
            reasons.append("missing requested capabilities: " + ", ".join(missing_capabilities))
        if interface_gap:
            reasons.append("no recipe exactly matches at least one requested interface kind")
        if blocked_permissions:
            reasons.append(
                "every equally best recipe needs ungranted permissions: "
                + ", ".join(blocked_permissions)
            )
        if pack.id in request.preferred_pack_ids:
            reasons.append("received an explicit user preference prior")
        if pack.id in request.excluded_pack_ids:
            reasons.append("explicitly excluded by the request")
        if not reasons:
            reasons.append("no positive evidence matched; retained for all-visible comparison")

        recommendations.append(
            PackRecommendation(
                pack_id=pack.id,
                pack_digest=pack.digest,
                score=round(max(0.0, min(score, 1.0)), 6),
                status=status,
                components=tuple((name, round(value, 6)) for name, value, _ in active),
                matched_category_ids=matched_categories,
                matched_terms=matched_terms,
                matched_capability_ids=matched_capabilities,
                missing_capability_ids=missing_capabilities,
                matched_input_kind_ids=matched_inputs,
                matched_output_kind_ids=matched_outputs,
                matching_recipe_ids=matching_recipes,
                blocked_permissions=blocked_permissions,
                reasons=tuple(reasons),
            )
        )

    recommendations.sort(
        key=lambda item: (
            item.status == "excluded",
            item.status == "partial",
            -item.score,
            item.pack_id,
        )
    )
    recommended = tuple(
        item.pack_id for item in recommendations if item.status != "excluded" and item.score > 0
    )[:selection_limit]
    report = PackageRecommendationReport(
        id=f"recommendation.specialized.{request.digest.removeprefix('sha256:')[:16]}",
        request=request,
        registry_digest=registry.digest,
        recommendations=tuple(recommendations),
        recommended_pack_ids=recommended,
        selection_limit=selection_limit,
        scoring_method=(
            "Deterministic weighted evidence over exact category, lexical signal, requested "
            "capability, and exact recipe-interface matches; scores are ranking heuristics, "
            "not compatibility probabilities."
        ),
        claim_boundary=(
            "This report nominates all visible specialized packs and starting recipes. "
            "It does not select nodes, grant authority, prove route compatibility, or replace "
            "compiler admission, execution evidence, and independent acceptance."
        ),
    )
    problems = report.validate(registry)
    if problems:
        raise ValueError("invalid package recommendation report: " + "; ".join(problems))
    return report


__all__ = [
    "PackRecommendation",
    "PackageRecommendationReport",
    "TaskPackageRequest",
    "recommend_specialized_packs",
    "request_from_task_contract",
]
