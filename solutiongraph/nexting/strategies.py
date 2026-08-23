"""Pluggable ways to answer a What-Is-Next question.

Strategies propose work only.  They cannot compile a graph, grant authority,
execute code, judge their own output, or promote a candidate.  Deterministic
rules, relational recipes, similarity retrieval, probes, research, LLMs,
councils, and protected random exploration share one outcome contract.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from math import isfinite
from random import Random
from time import monotonic
from typing import Any, Protocol

from solutiongraph.model import ID_RE, canonical_json, sha256_digest
from solutiongraph.nexting.contracts import (
    KnowledgeState,
    NextActionProposal,
    NextBudget,
    NextQuestion,
    StrategyOutcome,
)
from solutiongraph.nexting.prompts import (
    ContextExposurePolicy,
    PersonaFrame,
    PromptComposer,
    PromptContext,
)

STRATEGY_MODEL_VERSION = "0.1"
LLM_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["proposals"],
    "additionalProperties": False,
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["action_kind", "title", "rationale", "payload", "confidence"],
                "properties": {
                    "action_kind": {"type": "string"},
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "target_ref": {"type": "string"},
                    "payload": {"type": "object"},
                    "expected_outputs": {"type": "array", "items": {"type": "string"}},
                    "expected_information_gain": {"type": "number", "minimum": 0, "maximum": 1},
                    "expected_utility": {"type": "number", "minimum": 0, "maximum": 1},
                    "expected_cost": {"type": "number", "minimum": 0},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "uncertainty": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        }
    },
}


def _proposal_id(strategy_id: str, question_id: str, payload: Mapping[str, Any]) -> str:
    suffix = sha256_digest({"strategy": strategy_id, "question": question_id,
                            "payload": dict(payload)}).removeprefix("sha256:")[:24]
    return f"proposal.{suffix}"


def _bounded(value: Any, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        return default
    return min(1.0, max(0.0, float(value)))


@dataclass(frozen=True)
class StrategyManifest:
    id: str
    version: str
    family: str
    description: str
    context_policy_id: str = "context.selective"
    deterministic: bool = False
    cost_tier: int = 1
    capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    blind_lane: bool = False
    random_lane: bool = False
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        for label, value in (("id", self.id), ("family", self.family),
                             ("context_policy_id", self.context_policy_id)):
            if not ID_RE.fullmatch(value):
                problems.append(f"strategy {label} must be namespaced")
        if not self.version.strip() or not self.description.strip():
            problems.append("strategy version and description are required")
        if self.cost_tier < 0:
            problems.append("strategy cost_tier must be non-negative")
        for label, values in (("capabilities", self.capabilities), ("dependencies", self.dependencies)):
            if len(values) != len(set(values)) or any(not ID_RE.fullmatch(item) for item in values):
                problems.append(f"strategy {label} must contain unique namespaced identifiers")
        try:
            canonical_json(dict(self.extensions))
        except (TypeError, ValueError):
            problems.append("strategy extensions must be JSON serialisable")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_model_version": STRATEGY_MODEL_VERSION,
            "id": self.id, "version": self.version, "family": self.family,
            "description": self.description, "context_policy_id": self.context_policy_id,
            "deterministic": self.deterministic, "cost_tier": self.cost_tier,
            "capabilities": list(self.capabilities), "dependencies": list(self.dependencies),
            "blind_lane": self.blind_lane, "random_lane": self.random_lane,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class StrategyContext:
    state: KnowledgeState
    question: NextQuestion
    budget: NextBudget
    random_seed: int
    original_task: str = ""
    simplified_task: str = ""
    graph_summary: str = ""
    recipe_summary: str = ""
    prior_attempts: str = ""
    constraints: str = ""


class NextStrategy(Protocol):
    manifest: StrategyManifest

    def propose(self, context: StrategyContext) -> StrategyOutcome: ...


@dataclass(frozen=True)
class Rule:
    id: str
    predicate: Callable[[StrategyContext], bool]
    action_kind: str
    title: str
    rationale: str
    payload_factory: Callable[[StrategyContext], Mapping[str, Any]]
    target_factory: Callable[[StrategyContext], str] = lambda _: ""
    information_gain: float = 0.0
    utility: float = 0.5
    cost: float = 0.0
    confidence: float = 1.0
    parallel_safe: bool = False
    conflict_keys: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


# Earlier authoring name retained as an alias.
RuleClause = Rule


class DeterministicRuleStrategy:
    def __init__(
        self,
        manifest: StrategyManifest,
        rules: Sequence[Rule],
        *,
        first_match_only: bool = False,
    ) -> None:
        self.manifest = manifest
        self.rules = tuple(rules)
        self.first_match_only = first_match_only

    def propose(self, context: StrategyContext) -> StrategyOutcome:
        proposals: list[NextActionProposal] = []
        diagnostics: list[str] = []
        for rule in self.rules:
            if not ID_RE.fullmatch(rule.id) or not ID_RE.fullmatch(rule.action_kind):
                diagnostics.append(f"invalid rule identity {rule.id!r}")
                continue
            if rule.action_kind not in context.question.allowed_action_kinds:
                continue
            try:
                matched = rule.predicate(context)
            except Exception as exc:
                diagnostics.append(f"{rule.id}: predicate failed: {type(exc).__name__}: {exc}")
                continue
            if not matched:
                continue
            try:
                payload = dict(rule.payload_factory(context))
                target = rule.target_factory(context)
                canonical_json(payload)
            except Exception as exc:
                diagnostics.append(f"{rule.id}: payload failed: {type(exc).__name__}: {exc}")
                continue
            proposal = NextActionProposal(
                id=_proposal_id(self.manifest.id, context.question.id, payload),
                question_id=context.question.id,
                action_kind=rule.action_kind,
                title=rule.title,
                rationale=rule.rationale,
                strategy_id=self.manifest.id,
                target_ref=target,
                payload=payload,
                expected_information_gain=_bounded(rule.information_gain, 0.0),
                expected_utility=_bounded(rule.utility, 0.5),
                expected_cost=max(0.0, rule.cost),
                confidence=_bounded(rule.confidence, 1.0),
                uncertainty=1.0 - _bounded(rule.confidence, 1.0),
                parallel_safe=rule.parallel_safe,
                conflict_keys=rule.conflict_keys,
                tags=("strategy.deterministic-rule", *rule.tags),
                extensions={"rule_id": rule.id},
            )
            proposals.append(proposal)
            if self.first_match_only:
                break
        return StrategyOutcome(
            self.manifest.id,
            context.question.id,
            tuple(proposals),
            diagnostics=tuple(diagnostics),
            abstained=not proposals,
        )


# Shorter public alias used by the first prototype.
RuleStrategy = DeterministicRuleStrategy


class GoalSatisfactionStrategy:
    def __init__(
        self,
        manifest: StrategyManifest,
        predicate: Callable[[StrategyContext], bool],
        *,
        rationale: str = "The delegated Solver Cell goal is satisfied.",
    ) -> None:
        self.manifest = manifest
        self.predicate = predicate
        self.rationale = rationale

    def propose(self, context: StrategyContext) -> StrategyOutcome:
        if "next.stop" not in context.question.allowed_action_kinds:
            return StrategyOutcome(self.manifest.id, context.question.id, abstained=True)
        try:
            satisfied = self.predicate(context)
        except Exception as exc:
            return StrategyOutcome(
                self.manifest.id,
                context.question.id,
                diagnostics=(f"goal predicate failed: {type(exc).__name__}: {exc}",),
                abstained=True,
            )
        if not satisfied:
            return StrategyOutcome(self.manifest.id, context.question.id, abstained=True)
        payload = {"reason": "delegated-goal-satisfied"}
        proposal = NextActionProposal(
            id=_proposal_id(self.manifest.id, context.question.id, payload),
            question_id=context.question.id,
            action_kind="next.stop",
            title="Stop the delegated Solver Cell",
            rationale=self.rationale,
            strategy_id=self.manifest.id,
            payload=payload,
            expected_utility=1.0,
            confidence=1.0,
            uncertainty=0.0,
            tags=("strategy.goal-satisfaction",),
        )
        return StrategyOutcome(self.manifest.id, context.question.id, (proposal,))


@dataclass(frozen=True)
class RecipeStep:
    id: str
    action_kind: str
    title: str
    rationale: str
    payload: Mapping[str, Any]
    requires_reference_ids: tuple[str, ...] = ()
    requires_fact_predicates: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    target_ref: str = ""
    parallel_safe: bool = False
    conflict_keys: tuple[str, ...] = ()

    def ready(self, state: KnowledgeState) -> bool:
        refs = set(state.reference_map)
        predicates = {item.predicate for item in state.facts}
        completed = {
            str(item.value)
            for item in state.facts
            if item.predicate == "next.recipe-step-completed"
        }
        return (
            self.id not in completed
            and set(self.requires_reference_ids).issubset(refs)
            and set(self.requires_fact_predicates).issubset(predicates)
        )


@dataclass(frozen=True)
class Recipe:
    id: str
    version: str
    title: str
    steps: tuple[RecipeStep, ...]

    @property
    def digest(self) -> str:
        return sha256_digest({
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "steps": [
                {
                    "id": item.id,
                    "action_kind": item.action_kind,
                    "payload": dict(item.payload),
                    "requires_reference_ids": list(item.requires_reference_ids),
                    "requires_fact_predicates": list(item.requires_fact_predicates),
                    "produces": list(item.produces),
                }
                for item in self.steps
            ],
        })


class RecipeStrategy:
    """Choose every ready recipe instruction; tuple position has no semantics."""

    def __init__(self, manifest: StrategyManifest, recipe: Recipe) -> None:
        self.manifest = manifest
        self.recipe = recipe

    def propose(self, context: StrategyContext) -> StrategyOutcome:
        proposals: list[NextActionProposal] = []
        for step in sorted(self.recipe.steps, key=lambda item: item.id):
            if not step.ready(context.state):
                continue
            if step.action_kind not in context.question.allowed_action_kinds:
                continue
            payload = {**dict(step.payload), "recipe_id": self.recipe.id, "recipe_step_id": step.id}
            proposals.append(
                NextActionProposal(
                    id=_proposal_id(self.manifest.id, context.question.id, payload),
                    question_id=context.question.id,
                    action_kind=step.action_kind,
                    title=step.title,
                    rationale=step.rationale,
                    strategy_id=self.manifest.id,
                    target_ref=step.target_ref,
                    payload=payload,
                    expected_outputs=step.produces,
                    expected_utility=0.75,
                    confidence=1.0,
                    uncertainty=0.0,
                    parallel_safe=step.parallel_safe,
                    conflict_keys=step.conflict_keys,
                    tags=("strategy.recipe",),
                )
            )
        return StrategyOutcome(
            self.manifest.id,
            context.question.id,
            tuple(proposals),
            abstained=not proposals,
        )


@dataclass(frozen=True)
class SimilarityMatch:
    blueprint_ref: str
    score: float
    rationale: str
    evidence_refs: tuple[str, ...] = ()
    compatible: bool = True


# Earlier descriptive name retained.
BlueprintMatch = SimilarityMatch


class SimilarityRetriever(Protocol):
    def retrieve(self, context: StrategyContext, limit: int) -> Sequence[SimilarityMatch]: ...


class SimilarityStrategy:
    def __init__(
        self,
        manifest: StrategyManifest,
        retriever: SimilarityRetriever,
        *,
        limit: int = 5,
        instantiate: bool = False,
    ) -> None:
        self.manifest = manifest
        self.retriever = retriever
        self.limit = limit
        self.instantiate = instantiate

    def propose(self, context: StrategyContext) -> StrategyOutcome:
        kind = "next.instantiate-graph" if self.instantiate else "next.retrieve-blueprint"
        if kind not in context.question.allowed_action_kinds:
            return StrategyOutcome(self.manifest.id, context.question.id, abstained=True)
        try:
            matches = tuple(self.retriever.retrieve(context, self.limit))
        except Exception as exc:
            return StrategyOutcome(
                self.manifest.id,
                context.question.id,
                diagnostics=(f"similarity retrieval failed: {type(exc).__name__}: {exc}",),
                abstained=True,
            )
        proposals = []
        for match in matches:
            if not match.compatible:
                continue
            score = _bounded(match.score, 0.0)
            payload = {"blueprint_ref": match.blueprint_ref, "similarity": score,
                       "evidence_refs": list(match.evidence_refs)}
            proposals.append(
                NextActionProposal(
                    id=_proposal_id(self.manifest.id, context.question.id, payload),
                    question_id=context.question.id,
                    action_kind=kind,
                    title=f"Use analogous blueprint {match.blueprint_ref}",
                    rationale=match.rationale,
                    strategy_id=self.manifest.id,
                    target_ref=match.blueprint_ref,
                    payload=payload,
                    expected_information_gain=0.35,
                    expected_utility=score,
                    confidence=score,
                    uncertainty=1.0 - score,
                    tags=("strategy.similarity",),
                )
            )
        return StrategyOutcome(
            self.manifest.id,
            context.question.id,
            tuple(proposals),
            abstained=not proposals,
        )


class ProbeStrategy:
    def __init__(self, manifest: StrategyManifest, *, maximum_probes: int = 5) -> None:
        self.manifest = manifest
        self.maximum_probes = maximum_probes

    def propose(self, context: StrategyContext) -> StrategyOutcome:
        if "next.run-probe" not in context.question.allowed_action_kinds:
            return StrategyOutcome(self.manifest.id, context.question.id, abstained=True)
        proposals = []
        for unknown in sorted(context.state.unknowns, key=lambda item: (-item.importance, item.id))[: self.maximum_probes]:
            probe_kinds = unknown.suggested_probe_kinds or ("probe.information-gathering",)
            payload = {"unknown_id": unknown.id, "question": unknown.question,
                       "probe_kinds": list(probe_kinds)}
            proposals.append(
                NextActionProposal(
                    id=_proposal_id(self.manifest.id, context.question.id, payload),
                    question_id=context.question.id,
                    action_kind="next.run-probe",
                    title=f"Probe {unknown.id}",
                    rationale="The next intervention is underdetermined until this uncertainty is reduced.",
                    strategy_id=self.manifest.id,
                    payload=payload,
                    expected_information_gain=unknown.importance,
                    expected_utility=unknown.importance * 0.8,
                    expected_cost=0.1,
                    confidence=0.95,
                    uncertainty=0.05,
                    parallel_safe=True,
                    conflict_keys=(f"unknown:{unknown.id}",),
                    tags=("strategy.probe-first",),
                )
            )
        return StrategyOutcome(
            self.manifest.id,
            context.question.id,
            tuple(proposals),
            abstained=not proposals,
        )


class ResearchStrategy:
    def __init__(
        self,
        manifest: StrategyManifest,
        query_factory: Callable[[StrategyContext], str],
        *,
        source_kinds: tuple[str, ...] = (),
        freshness_days: int | None = None,
        blind_to_prior_work: bool = False,
    ) -> None:
        self.manifest = manifest
        self.query_factory = query_factory
        self.source_kinds = source_kinds
        self.freshness_days = freshness_days
        self.blind_to_prior_work = blind_to_prior_work

    def propose(self, context: StrategyContext) -> StrategyOutcome:
        if "next.research" not in context.question.allowed_action_kinds:
            return StrategyOutcome(self.manifest.id, context.question.id, abstained=True)
        try:
            query = self.query_factory(context).strip()
        except Exception as exc:
            return StrategyOutcome(
                self.manifest.id,
                context.question.id,
                diagnostics=(f"research query failed: {type(exc).__name__}: {exc}",),
                abstained=True,
            )
        if not query:
            return StrategyOutcome(self.manifest.id, context.question.id, abstained=True)
        payload = {"query": query, "source_kinds": list(self.source_kinds),
                   "freshness_days": self.freshness_days,
                   "blind_to_prior_work": self.blind_to_prior_work}
        proposal = NextActionProposal(
            id=_proposal_id(self.manifest.id, context.question.id, payload),
            question_id=context.question.id,
            action_kind="next.research",
            title="Research missing external evidence",
            rationale="The next decision depends on information outside the current knowledge boundary.",
            strategy_id=self.manifest.id,
            payload=payload,
            expected_information_gain=0.8,
            expected_utility=0.6,
            expected_cost=float(self.manifest.cost_tier) / 10.0,
            confidence=0.85,
            uncertainty=0.15,
            tags=("strategy.research",),
        )
        return StrategyOutcome(self.manifest.id, context.question.id, (proposal,))


class ModelClient(Protocol):
    model_id: str

    def generate(
        self,
        prompt: str,
        *,
        response_schema: Mapping[str, Any],
        seed: int,
    ) -> Mapping[str, Any]: ...


# Earlier generic name retained.
ModelAdapter = ModelClient


class ProposalParser(Protocol):
    def parse(
        self,
        response: Mapping[str, Any],
        *,
        strategy_id: str,
        question: NextQuestion,
        prompt_digest: str,
        context_manifest_digest: str,
        model_id: str,
    ) -> Sequence[NextActionProposal]: ...


class LLMNextStrategy:
    def __init__(
        self,
        manifest: StrategyManifest,
        model: ModelClient,
        parser: ProposalParser,
        *,
        exposure: ContextExposurePolicy | None = None,
        persona: PersonaFrame | None = None,
        composer: PromptComposer | None = None,
        response_schema: Mapping[str, Any] = LLM_RESPONSE_SCHEMA,
    ) -> None:
        self.manifest = manifest
        self.model = model
        self.parser = parser
        self.exposure = exposure or ContextExposurePolicy.selective()
        self.persona = persona or PersonaFrame(id="persona.general-expert")
        self.composer = composer or PromptComposer()
        self.response_schema = response_schema

    def propose(self, context: StrategyContext) -> StrategyOutcome:
        prompt_context = PromptContext(
            state=context.state,
            question=context.question,
            exposure=self.exposure,
            persona=self.persona,
            original_task=context.original_task,
            simplified_task=context.simplified_task,
            graph_summary=context.graph_summary,
            recipe_summary=context.recipe_summary,
            prior_attempts=context.prior_attempts,
            constraints=context.constraints,
        )
        try:
            _, manifest, prompt = self.composer.compose(prompt_context)
            prompt_digest = sha256_digest(prompt)
            started = monotonic()
            response = self.model.generate(
                prompt,
                response_schema=self.response_schema,
                seed=context.random_seed,
            )
            latency = monotonic() - started
            proposals = tuple(
                self.parser.parse(
                    response,
                    strategy_id=self.manifest.id,
                    question=context.question,
                    prompt_digest=prompt_digest,
                    context_manifest_digest=manifest.digest,
                    model_id=self.model.model_id,
                )
            )
        except Exception as exc:
            return StrategyOutcome(
                self.manifest.id,
                context.question.id,
                diagnostics=(f"model strategy failed: {type(exc).__name__}: {exc}",),
                abstained=True,
            )
        admitted = tuple(
            proposal for proposal in proposals
            if proposal.action_kind in context.question.allowed_action_kinds
        )
        return StrategyOutcome(
            self.manifest.id,
            context.question.id,
            admitted,
            diagnostics=(
                () if len(admitted) == len(proposals)
                else ("one or more model proposals used disallowed action kinds",)
            ),
            abstained=not admitted,
            cost_units=float(self.manifest.cost_tier),
            latency_seconds=latency,
        )


class CouncilStrategy:
    """Run member strategies independently and preserve every member lineage."""

    def __init__(
        self,
        manifest: StrategyManifest,
        members: Sequence[NextStrategy],
        *,
        diversity_discount: float = 0.95,
    ) -> None:
        self.manifest = manifest
        self.members = tuple(members)
        self.diversity_discount = min(1.0, max(0.0, diversity_discount))

    def propose(self, context: StrategyContext) -> StrategyOutcome:
        proposals: list[NextActionProposal] = []
        diagnostics: list[str] = []
        cost = 0.0
        latency = 0.0
        for index, member in enumerate(self.members):
            member_context = replace(context, random_seed=context.random_seed + index + 1)
            try:
                outcome = member.propose(member_context)
            except Exception as exc:
                diagnostics.append(f"{member.manifest.id}: {type(exc).__name__}: {exc}")
                continue
            diagnostics.extend(f"{member.manifest.id}: {item}" for item in outcome.diagnostics)
            cost += outcome.cost_units
            latency = max(latency, outcome.latency_seconds)
            for proposal in outcome.proposals:
                lineage_payload = {
                    "member_proposal_id": proposal.id,
                    "member_strategy_id": member.manifest.id,
                    "semantic_identity": proposal.semantic_identity,
                }
                proposals.append(
                    replace(
                        proposal,
                        id=_proposal_id(self.manifest.id, context.question.id, lineage_payload),
                        strategy_id=self.manifest.id,
                        confidence=min(1.0, proposal.confidence * self.diversity_discount),
                        uncertainty=min(1.0, proposal.uncertainty + (1.0 - self.diversity_discount)),
                        correlation_group=(proposal.correlation_group or f"council.{member.manifest.id}"),
                        extensions={**dict(proposal.extensions),
                                    "council_member": member.manifest.id,
                                    "member_proposal_id": proposal.id},
                    )
                )
        return StrategyOutcome(
            self.manifest.id,
            context.question.id,
            tuple(proposals),
            diagnostics=tuple(diagnostics),
            abstained=not proposals,
            cost_units=cost,
            latency_seconds=latency,
        )


class RandomExplorationStrategy:
    def __init__(self, manifest: StrategyManifest, action_kinds: Sequence[str]) -> None:
        self.manifest = manifest
        self.action_kinds = tuple(action_kinds)

    def propose(self, context: StrategyContext) -> StrategyOutcome:
        choices = sorted(set(self.action_kinds) & set(context.question.allowed_action_kinds))
        if not choices:
            return StrategyOutcome(self.manifest.id, context.question.id, abstained=True)
        action_kind = Random(context.random_seed).choice(choices)
        payload = {"seed": context.random_seed, "exploration_action": action_kind,
                   "target_ref": context.question.target_ref}
        proposal = NextActionProposal(
            id=_proposal_id(self.manifest.id, context.question.id, payload),
            question_id=context.question.id,
            action_kind=action_kind,
            title=f"Protected exploration: {action_kind}",
            rationale="Sample a valid underexplored answer family to avoid premature convergence.",
            strategy_id=self.manifest.id,
            target_ref=context.question.target_ref,
            payload=payload,
            expected_information_gain=0.5,
            expected_utility=0.2,
            expected_cost=0.05,
            confidence=0.25,
            uncertainty=0.75,
            tags=("strategy.random-exploration",),
        )
        return StrategyOutcome(self.manifest.id, context.question.id, (proposal,))


class StrategyRegistry:
    def __init__(self, strategies: Sequence[NextStrategy] = ()) -> None:
        self._strategies: dict[str, NextStrategy] = {}
        for strategy in strategies:
            self.register(strategy)

    def register(self, strategy: NextStrategy) -> None:
        problems = strategy.manifest.validate()
        if problems:
            raise ValueError("invalid strategy manifest: " + "; ".join(problems))
        if strategy.manifest.id in self._strategies:
            raise ValueError(f"duplicate next strategy {strategy.manifest.id}")
        self._strategies[strategy.manifest.id] = strategy

    def get(self, strategy_id: str) -> NextStrategy:
        try:
            return self._strategies[strategy_id]
        except KeyError as exc:
            raise ValueError(f"unknown next strategy {strategy_id!r}") from exc

    def all(self) -> tuple[NextStrategy, ...]:
        return tuple(self._strategies[key] for key in sorted(self._strategies))

    def by_family(self, family: str) -> tuple[NextStrategy, ...]:
        return tuple(item for item in self.all() if item.manifest.family == family)


__all__ = [
    "LLM_RESPONSE_SCHEMA", "STRATEGY_MODEL_VERSION", "BlueprintMatch",
    "CouncilStrategy", "DeterministicRuleStrategy", "GoalSatisfactionStrategy",
    "LLMNextStrategy", "ModelAdapter", "ModelClient", "NextStrategy",
    "ProbeStrategy", "ProposalParser", "RandomExplorationStrategy", "Recipe",
    "RecipeStep", "RecipeStrategy", "ResearchStrategy", "Rule", "RuleClause",
    "RuleStrategy", "SimilarityMatch", "SimilarityRetriever", "SimilarityStrategy",
    "StrategyContext", "StrategyManifest", "StrategyRegistry",
]
