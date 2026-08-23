"""Explicit routing from selected next actions to existing subsystems.

A Solver Cell should not contain a giant ``if action_kind == ...`` executor.
Routes are portable contracts and handlers are replaceable adapters.  The
router delegates only; downstream compilers, runtimes, research systems,
experiment harnesses, humans, and child cells retain their own authority.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from solutiongraph.model import ID_RE, canonical_json, sha256_digest
from solutiongraph.nexting.contracts import ActionResult, KnowledgeState, NextActionProposal

ACTION_ROUTING_MODEL_VERSION = "0.1"


def _identifiers(values: tuple[str, ...], path: str) -> list[str]:
    problems: list[str] = []
    if len(values) != len(set(values)):
        problems.append(f"{path} must be unique")
    if any(not ID_RE.fullmatch(value) for value in values):
        problems.append(f"{path} must contain namespaced identifiers")
    return problems


@dataclass(frozen=True)
class ActionRoute:
    """One declarative dispatch rule for selected next-action proposals."""

    id: str
    handler_id: str
    action_kinds: tuple[str, ...]
    priority: int = 0
    target_prefixes: tuple[str, ...] = ()
    required_proposal_tags: tuple[str, ...] = ()
    forbidden_proposal_tags: tuple[str, ...] = ()
    enabled: bool = True
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "route") -> list[str]:
        problems: list[str] = []
        for label, value in (("id", self.id), ("handler_id", self.handler_id)):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        if not self.action_kinds:
            problems.append(f"{path}.action_kinds must not be empty")
        problems.extend(_identifiers(self.action_kinds, f"{path}.action_kinds"))
        problems.extend(
            _identifiers(
                self.required_proposal_tags,
                f"{path}.required_proposal_tags",
            )
        )
        problems.extend(
            _identifiers(
                self.forbidden_proposal_tags,
                f"{path}.forbidden_proposal_tags",
            )
        )
        if set(self.required_proposal_tags) & set(self.forbidden_proposal_tags):
            problems.append(
                f"{path} required and forbidden proposal tags must be disjoint"
            )
        if len(self.target_prefixes) != len(set(self.target_prefixes)):
            problems.append(f"{path}.target_prefixes must be unique")
        if any(not prefix for prefix in self.target_prefixes):
            problems.append(f"{path}.target_prefixes must not contain empty values")
        try:
            canonical_json(dict(self.extensions))
        except (TypeError, ValueError):
            problems.append(f"{path}.extensions must be JSON serialisable")
        return problems

    def matches(self, proposal: NextActionProposal) -> bool:
        if not self.enabled or proposal.action_kind not in self.action_kinds:
            return False
        if self.target_prefixes and not any(
            proposal.target_ref.startswith(prefix) for prefix in self.target_prefixes
        ):
            return False
        tags = set(proposal.tags)
        if not set(self.required_proposal_tags).issubset(tags):
            return False
        return not bool(tags & set(self.forbidden_proposal_tags))

    def specificity(self, proposal: NextActionProposal) -> tuple[int, int, int]:
        matching_prefixes = tuple(
            prefix
            for prefix in self.target_prefixes
            if proposal.target_ref.startswith(prefix)
        )
        longest_prefix = max((len(prefix) for prefix in matching_prefixes), default=0)
        return (
            self.priority,
            longest_prefix,
            len(self.required_proposal_tags),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_routing_model_version": ACTION_ROUTING_MODEL_VERSION,
            "id": self.id,
            "handler_id": self.handler_id,
            "action_kinds": list(self.action_kinds),
            "priority": self.priority,
            "target_prefixes": list(self.target_prefixes),
            "required_proposal_tags": list(self.required_proposal_tags),
            "forbidden_proposal_tags": list(self.forbidden_proposal_tags),
            "enabled": self.enabled,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class ActionRouterSpec:
    id: str
    version: str
    routes: tuple[ActionRoute, ...]
    default_handler_id: str = ""
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "router") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.version.strip():
            problems.append(f"{path}.version must not be empty")
        route_ids = tuple(route.id for route in self.routes)
        problems.extend(_identifiers(route_ids, f"{path}.route_ids"))
        for index, route in enumerate(self.routes):
            problems.extend(route.validate(f"{path}.routes[{index}]"))
        if self.default_handler_id and not ID_RE.fullmatch(self.default_handler_id):
            problems.append(
                f"{path}.default_handler_id must be empty or namespaced"
            )
        try:
            canonical_json(dict(self.extensions))
        except (TypeError, ValueError):
            problems.append(f"{path}.extensions must be JSON serialisable")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_routing_model_version": ACTION_ROUTING_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "routes": [route.to_dict() for route in self.routes],
            "default_handler_id": self.default_handler_id,
            "extensions": dict(self.extensions),
        }


class ActionHandler(Protocol):
    handler_id: str

    def execute(
        self,
        proposal: NextActionProposal,
        state: KnowledgeState,
    ) -> ActionResult: ...


@dataclass
class FunctionalActionHandler:
    handler_id: str
    function: Callable[[NextActionProposal, KnowledgeState], ActionResult]

    def execute(
        self,
        proposal: NextActionProposal,
        state: KnowledgeState,
    ) -> ActionResult:
        return self.function(proposal, state)


class HandlerRegistry:
    def __init__(self, handlers: Sequence[ActionHandler] = ()) -> None:
        self._handlers: dict[str, ActionHandler] = {}
        for handler in handlers:
            self.register(handler)

    def register(self, handler: ActionHandler) -> None:
        if not ID_RE.fullmatch(handler.handler_id):
            raise ValueError("handler_id must be a namespaced identifier")
        if handler.handler_id in self._handlers:
            raise ValueError(f"duplicate action handler {handler.handler_id}")
        self._handlers[handler.handler_id] = handler

    def get(self, handler_id: str) -> ActionHandler:
        try:
            return self._handlers[handler_id]
        except KeyError as exc:
            raise ValueError(f"unknown action handler {handler_id!r}") from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))


@dataclass(frozen=True)
class RouteResolution:
    proposal_id: str
    route_id: str
    handler_id: str
    considered_route_ids: tuple[str, ...]
    defaulted: bool = False

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "route_id": self.route_id,
            "handler_id": self.handler_id,
            "considered_route_ids": list(self.considered_route_ids),
            "defaulted": self.defaulted,
        }


class RoutedActionExecutor:
    """Resolve one unambiguous route, then call its registered adapter."""

    def __init__(
        self,
        spec: ActionRouterSpec,
        handlers: HandlerRegistry,
    ) -> None:
        problems = spec.validate()
        missing = sorted(
            {
                route.handler_id for route in spec.routes if route.enabled
            }
            - set(handlers.ids())
        )
        if spec.default_handler_id and spec.default_handler_id not in handlers.ids():
            missing.append(spec.default_handler_id)
        if missing:
            problems.append("router references unknown handlers: " + ", ".join(missing))
        if problems:
            raise ValueError("invalid action router: " + "; ".join(problems))
        self.spec = spec
        self.handlers = handlers

    def resolve(self, proposal: NextActionProposal) -> RouteResolution:
        matching = tuple(route for route in self.spec.routes if route.matches(proposal))
        if not matching:
            if not self.spec.default_handler_id:
                raise ValueError(
                    f"no action route accepts {proposal.action_kind} for {proposal.target_ref!r}"
                )
            return RouteResolution(
                proposal_id=proposal.id,
                route_id="route.default",
                handler_id=self.spec.default_handler_id,
                considered_route_ids=(),
                defaulted=True,
            )
        ranked = sorted(
            matching,
            key=lambda route: (
                -route.specificity(proposal)[0],
                -route.specificity(proposal)[1],
                -route.specificity(proposal)[2],
                route.id,
            ),
        )
        best = ranked[0]
        if len(ranked) > 1 and ranked[1].specificity(proposal) == best.specificity(proposal):
            raise ValueError(
                "ambiguous action routes with equal specificity: "
                f"{best.id}, {ranked[1].id}"
            )
        return RouteResolution(
            proposal_id=proposal.id,
            route_id=best.id,
            handler_id=best.handler_id,
            considered_route_ids=tuple(route.id for route in ranked),
        )

    def execute(
        self,
        proposal: NextActionProposal,
        state: KnowledgeState,
    ) -> ActionResult:
        try:
            resolution = self.resolve(proposal)
        except ValueError as exc:
            return ActionResult(
                proposal_id=proposal.id,
                outcome="blocked",
                failure_class="next.action-route-unresolved",
                details={"message": str(exc)},
            )
        handler = self.handlers.get(resolution.handler_id)
        try:
            result = handler.execute(proposal, state)
        except Exception as exc:
            return ActionResult(
                proposal_id=proposal.id,
                outcome="failed",
                failure_class="next.action-handler-exception",
                details={
                    "route_resolution": resolution.to_dict(),
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                },
            )
        return ActionResult(
            proposal_id=result.proposal_id,
            outcome=result.outcome,
            produced_references=result.produced_references,
            produced_facts=result.produced_facts,
            resolved_unknown_ids=result.resolved_unknown_ids,
            metrics=result.metrics,
            failure_class=result.failure_class,
            details={
                **dict(result.details),
                "route_resolution": resolution.to_dict(),
            },
        )


__all__ = [
    "ACTION_ROUTING_MODEL_VERSION",
    "ActionHandler",
    "ActionRoute",
    "ActionRouterSpec",
    "FunctionalActionHandler",
    "HandlerRegistry",
    "RouteResolution",
    "RoutedActionExecutor",
]
