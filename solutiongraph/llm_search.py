"""Combinatorial LLM-guided proposal search for universal solution graphs.

This module does not execute models or mutate executable plans directly.  It
generates inspectable prompt specifications, structured proposal contracts, and
vote summaries that an outer campaign can connect to model providers, the graph
compiler, and the independent evaluator.

The important design choice is that *questions are generated lazily*.  A useful
search space can contain millions or billions of distinct prompt combinations
without storing millions of strings or paying for millions of model calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import isfinite, prod
from random import Random
from typing import Any, Iterable, Iterator, Sequence

from solutiongraph.model import ID_RE, sha256_digest

SEARCH_MODEL_VERSION = "0.1"

TARGETS = (
    "task", "objective", "validation", "data", "column", "row", "feature",
    "cleaning", "imputation", "encoding", "scaling", "augmentation", "model",
    "loss", "optimizer", "ensemble", "postprocess", "graph", "subgraph", "node",
    "edge", "route", "package", "runtime", "memory", "hardware",
)

CONTEXT_VIEWS = (
    "blind", "task_only", "schema_only", "blueprint", "local_neighborhood",
    "graph_only", "results_only", "failures_only", "research_only",
    "partial_history", "full_history", "counterfactual_history",
)

INTENTS = (
    "reframe", "diagnose", "propose", "criticize", "simplify", "expand",
    "replace", "reorder", "factor", "compose", "decompose", "mutate",
    "optimize", "verify", "falsify", "compare", "ablate", "search", "ensemble",
    "compress", "accelerate", "stabilize",
)

QUESTION_FAMILIES = (
    "what_next", "what_missing", "what_excessive", "greatest_opportunity",
    "greatest_weakness", "top_concern", "bottom_concern", "pros_cons",
    "assumptions", "failure_modes", "leakage", "validation_mismatch",
    "distribution_shift", "feature_interactions", "data_quality", "uncertainty",
    "calibration", "robustness", "efficiency", "cost", "memory", "hardware",
    "package_discovery", "analogy", "opposite_strategy", "minimal_solution",
    "maximal_solution", "symbolic_hybrid", "supervised_unsupervised_hybrid",
    "ensemble_diversity", "research_transfer", "competition_transfer",
)

LENSES = (
    "kaggle_grandmaster", "tabular_ml", "deep_learning", "time_series",
    "computer_vision", "nlp", "recommendation", "causal_inference",
    "bayesian_statistics", "frequentist_statistics", "information_theory",
    "optimization_theory", "computational_complexity", "numerical_analysis",
    "signal_processing", "control_theory", "physics", "symbolic_math",
    "software_architecture", "data_engineering", "mlops", "adversarial_review",
    "resource_constrained_engineer", "research_scientist",
    "competition_postmortem", "outsider",
)

TIME_LENSES = (
    "modern", "pre_deep_learning", "classical_statistics", "future_hardware",
    "extreme_compute", "extreme_scarcity",
)

LANGUAGE_LENSES = (
    "native", "translate_reasoning_once", "translate_reasoning_twice",
    "formal_mathematical", "pseudocode_first",
)

EVIDENCE_STANCES = (
    "evidence_first", "hypothesis_first", "skeptical", "contrarian",
    "conservative", "novelty_seeking",
)

MUTATION_OPERATORS = (
    "add_node", "remove_node", "replace_node", "wrap_node_as_subgraph",
    "expand_subgraph", "collapse_subgraph", "add_edge", "remove_edge",
    "redirect_edge", "add_branch", "add_loop", "add_barrier", "add_map_reduce",
    "swap_route", "change_order_constraint", "change_parameter",
    "change_hyperparameter", "change_feature_set", "change_validation",
    "change_objective", "change_model_family", "change_ensemble", "change_package",
    "change_runtime", "change_fidelity", "fork_graph", "cross_over_graphs",
    "ablate_component", "restore_ancestor",
)

PROPOSAL_KINDS = (
    "task_reframe", "graph", "subgraph", "node", "route", "mutation", "ablation",
    "package", "research", "feature", "validation", "model", "ensemble", "runtime",
)

FAMILY_PROMPTS = {
    "what_next": "What is the highest-value thing to try next?",
    "what_missing": "What important idea, check, or transformation has not been tried?",
    "what_excessive": "What are we doing that is unnecessary, redundant, or harmful?",
    "greatest_opportunity": "Where is the largest plausible improvement opportunity?",
    "greatest_weakness": "What is the weakest part of the current solution?",
    "top_concern": "What should worry us most about this design?",
    "bottom_concern": "Which apparent concern is probably least important?",
    "pros_cons": "What are the strongest arguments for and against the current approach?",
    "assumptions": "Which assumptions are hidden, fragile, or untested?",
    "failure_modes": "How is this likely to fail, and what experiment would expose that failure?",
    "leakage": "Where could target, temporal, group, fold, preprocessing, or metadata leakage exist?",
    "validation_mismatch": "How could local validation disagree with the hidden leaderboard?",
    "distribution_shift": "What train/test or temporal distribution shifts should be tested?",
    "feature_interactions": "Which interactions, ratios, groups, lags, frequencies, or latent factors may matter?",
    "data_quality": "Which data-quality defect could be suppressing performance?",
    "uncertainty": "How should predictive, data, and model uncertainty change the graph?",
    "calibration": "Would calibration, thresholding, ranking, or decision-layer tuning help?",
    "robustness": "Which perturbation or stress test could falsify the current winner?",
    "efficiency": "How can we obtain more information or score improvement per unit compute?",
    "cost": "Which expensive step has the weakest expected value?",
    "memory": "What memory layout, batching, caching, precision, or representation change helps?",
    "hardware": "How should CPU, GPU, accelerator, storage, and parallelism constraints alter the route?",
    "package_discovery": "Which mature PyPI/package implementation could replace bespoke code or unlock a new approach?",
    "analogy": "What successful solution from an analogous problem should be translated here?",
    "opposite_strategy": "What would the strongest opposite strategy do differently?",
    "minimal_solution": "What is the smallest high-signal graph that could outperform this graph?",
    "maximal_solution": "If compute were abundant, what additional route would be worth testing?",
    "symbolic_hybrid": "Can deterministic formulas, rules, optimization, or symbolic structure improve the learned model?",
    "supervised_unsupervised_hybrid": "Can clustering, embeddings, anomaly scores, decomposition, or self-supervision improve supervised learning?",
    "ensemble_diversity": "Which intentionally different error pattern would add the most ensemble value?",
    "research_transfer": "Which published method or open-source implementation should be tested here?",
    "competition_transfer": "Which prior competition pattern transfers, and what must be changed to avoid cargo-culting it?",
}


def _validate_choice(value: str, allowed: Sequence[str], path: str) -> list[str]:
    if value not in allowed:
        return [f"{path} must be one of {', '.join(allowed)}"]
    return []


@dataclass(frozen=True)
class ModelRoute:
    """A model endpoint/configuration used to diversify proposal generation."""

    id: str
    provider: str = "ollama"
    model: str = ""
    temperature: float = 0.2
    seed: int | None = 0
    context_window: int | None = None
    tags: tuple[str, ...] = ()

    def validate(self, path: str = "model_route") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.provider.strip() or not self.model.strip():
            problems.append(f"{path}.provider and model must not be empty")
        if not isfinite(self.temperature) or self.temperature < 0:
            problems.append(f"{path}.temperature must be finite and non-negative")
        if self.context_window is not None and self.context_window <= 0:
            problems.append(f"{path}.context_window must be positive or null")
        return problems


@dataclass(frozen=True)
class PromptSpec:
    """One reproducible LLM question before task/context material is injected."""

    target: str
    context_view: str
    intent: str
    family: str
    lens: str
    time_lens: str
    language_lens: str
    evidence_stance: str
    mutation_operator: str
    proposal_kind: str

    def validate(self, path: str = "prompt") -> list[str]:
        problems: list[str] = []
        for value, allowed, label in (
            (self.target, TARGETS, "target"),
            (self.context_view, CONTEXT_VIEWS, "context_view"),
            (self.intent, INTENTS, "intent"),
            (self.family, QUESTION_FAMILIES, "family"),
            (self.lens, LENSES, "lens"),
            (self.time_lens, TIME_LENSES, "time_lens"),
            (self.language_lens, LANGUAGE_LENSES, "language_lens"),
            (self.evidence_stance, EVIDENCE_STANCES, "evidence_stance"),
            (self.mutation_operator, MUTATION_OPERATORS, "mutation_operator"),
            (self.proposal_kind, PROPOSAL_KINDS, "proposal_kind"),
        ):
            problems.extend(_validate_choice(value, allowed, f"{path}.{label}"))
        return problems

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, str]:
        return {
            "target": self.target,
            "context_view": self.context_view,
            "intent": self.intent,
            "family": self.family,
            "lens": self.lens,
            "time_lens": self.time_lens,
            "language_lens": self.language_lens,
            "evidence_stance": self.evidence_stance,
            "mutation_operator": self.mutation_operator,
            "proposal_kind": self.proposal_kind,
        }

    def render(self) -> str:
        question = FAMILY_PROMPTS[self.family]
        return (
            f"Role/lens: {self.lens}; time lens: {self.time_lens}; reasoning mode: "
            f"{self.language_lens}; evidence stance: {self.evidence_stance}.\n"
            f"Visible context policy: {self.context_view}. Focus level: {self.target}.\n"
            f"Primary intent: {self.intent}. Candidate operation: {self.mutation_operator}. "
            f"Return a structured {self.proposal_kind} proposal.\n\n"
            f"{question}\n\n"
            "Do not assume the current graph is correct. Distinguish observations from "
            "hypotheses. State expected benefit, cost, risk, confidence, required evidence, "
            "and the smallest falsifiable experiment. Prefer relative dependencies and typed "
            "inputs/outputs over fixed step numbers or fragile positional ordering."
        )


@dataclass(frozen=True)
class QuestionSpace:
    """Lazy Cartesian product for proposal prompts."""

    targets: tuple[str, ...] = TARGETS
    context_views: tuple[str, ...] = CONTEXT_VIEWS
    intents: tuple[str, ...] = INTENTS
    families: tuple[str, ...] = QUESTION_FAMILIES
    lenses: tuple[str, ...] = LENSES
    time_lenses: tuple[str, ...] = TIME_LENSES
    language_lenses: tuple[str, ...] = LANGUAGE_LENSES
    evidence_stances: tuple[str, ...] = EVIDENCE_STANCES
    mutation_operators: tuple[str, ...] = MUTATION_OPERATORS
    proposal_kinds: tuple[str, ...] = PROPOSAL_KINDS

    @property
    def axes(self) -> tuple[tuple[str, ...], ...]:
        return (
            self.targets, self.context_views, self.intents, self.families, self.lenses,
            self.time_lenses, self.language_lenses, self.evidence_stances,
            self.mutation_operators, self.proposal_kinds,
        )

    @property
    def size(self) -> int:
        return prod(len(axis) for axis in self.axes)

    def validate(self) -> list[str]:
        problems: list[str] = []
        for index, axis in enumerate(self.axes):
            if not axis:
                problems.append(f"axes[{index}] must not be empty")
            elif len(axis) != len(set(axis)):
                problems.append(f"axes[{index}] must not contain duplicates")
        return problems

    def at(self, index: int) -> PromptSpec:
        if index < 0 or index >= self.size:
            raise IndexError(index)
        values: list[str] = []
        remainder = index
        for axis in reversed(self.axes):
            remainder, offset = divmod(remainder, len(axis))
            values.append(axis[offset])
        values.reverse()
        return PromptSpec(*values)

    def iter_all(self, limit: int | None = None) -> Iterator[PromptSpec]:
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or null")
        yielded = 0
        for values in product(*self.axes):
            if limit is not None and yielded >= limit:
                break
            yielded += 1
            yield PromptSpec(*values)

    def sample(self, count: int, seed: int = 0) -> tuple[PromptSpec, ...]:
        if count < 0:
            raise ValueError("count must be non-negative")
        count = min(count, self.size)
        rng = Random(seed)
        indices = rng.sample(range(self.size), count)
        return tuple(self.at(index) for index in indices)

    def stratified_sample(
        self,
        count: int,
        *,
        seed: int = 0,
        ensure_context_views: bool = True,
        ensure_families: bool = True,
        ensure_lenses: bool = True,
    ) -> tuple[PromptSpec, ...]:
        """Sample broadly before filling the remaining budget randomly."""

        if count < 0:
            raise ValueError("count must be non-negative")
        if count == 0:
            return ()
        rng = Random(seed)
        chosen: dict[str, PromptSpec] = {}

        def add(spec: PromptSpec) -> None:
            if len(chosen) < count:
                chosen.setdefault(spec.digest, spec)

        if ensure_context_views:
            for value in self.context_views:
                base = list(self.sample(1, rng.randrange(2**31))[0].to_dict().values())
                base[1] = value
                add(PromptSpec(*base))
        if ensure_families:
            for value in self.families:
                base = list(self.sample(1, rng.randrange(2**31))[0].to_dict().values())
                base[3] = value
                add(PromptSpec(*base))
        if ensure_lenses:
            for value in self.lenses:
                base = list(self.sample(1, rng.randrange(2**31))[0].to_dict().values())
                base[4] = value
                add(PromptSpec(*base))

        while len(chosen) < min(count, self.size):
            add(self.at(rng.randrange(self.size)))
        return tuple(chosen.values())


@dataclass(frozen=True)
class ContextEnvelope:
    """Named context fragments. Visibility policy is enforced outside the LLM."""

    task: str = ""
    schema: str = ""
    blueprint: str = ""
    graph: str = ""
    local_neighborhood: str = ""
    results: str = ""
    failures: str = ""
    research: str = ""
    history: str = ""

    def project(self, view: str) -> dict[str, str]:
        problems = _validate_choice(view, CONTEXT_VIEWS, "context_view")
        if problems:
            raise ValueError(problems[0])
        mapping = {
            "blind": (),
            "task_only": ("task",),
            "schema_only": ("task", "schema"),
            "blueprint": ("task", "schema", "blueprint"),
            "local_neighborhood": ("task", "schema", "local_neighborhood", "results"),
            "graph_only": ("task", "schema", "graph"),
            "results_only": ("task", "schema", "results"),
            "failures_only": ("task", "schema", "failures"),
            "research_only": ("task", "schema", "research"),
            "partial_history": ("task", "schema", "graph", "results"),
            "full_history": (
                "task", "schema", "blueprint", "graph", "local_neighborhood",
                "results", "failures", "research", "history",
            ),
            "counterfactual_history": ("task", "schema", "failures", "research"),
        }
        return {name: getattr(self, name) for name in mapping[view] if getattr(self, name)}


@dataclass(frozen=True)
class Proposal:
    """Provider-neutral structured proposal returned by an LLM route."""

    id: str
    kind: str
    summary: str
    hypothesis: str
    operations: tuple[str, ...]
    expected_gain: float | None = None
    confidence: float = 0.5
    novelty: float = 0.5
    risk: float = 0.5
    cost_units: float = 1.0
    evidence_needed: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    falsification_test: str = ""
    source_prompt_digest: str = ""
    proposer_route_id: str = ""
    parent_candidate_ids: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    def validate(self, path: str = "proposal") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        problems.extend(_validate_choice(self.kind, PROPOSAL_KINDS, f"{path}.kind"))
        if not self.summary.strip() or not self.hypothesis.strip():
            problems.append(f"{path}.summary and hypothesis must not be empty")
        if not self.operations:
            problems.append(f"{path}.operations must not be empty")
        for label, value in (("confidence", self.confidence), ("novelty", self.novelty), ("risk", self.risk)):
            if not isfinite(value) or value < 0 or value > 1:
                problems.append(f"{path}.{label} must be in [0, 1]")
        if self.expected_gain is not None and not isfinite(self.expected_gain):
            problems.append(f"{path}.expected_gain must be finite or null")
        if not isfinite(self.cost_units) or self.cost_units < 0:
            problems.append(f"{path}.cost_units must be finite and non-negative")
        if self.source_prompt_digest and not self.source_prompt_digest.startswith("sha256:"):
            problems.append(f"{path}.source_prompt_digest must be a sha256 digest or empty")
        if self.proposer_route_id and not ID_RE.fullmatch(self.proposer_route_id):
            problems.append(f"{path}.proposer_route_id must be a namespaced identifier or empty")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "summary": self.summary,
            "hypothesis": self.hypothesis,
            "operations": list(self.operations),
            "expected_gain": self.expected_gain,
            "confidence": self.confidence,
            "novelty": self.novelty,
            "risk": self.risk,
            "cost_units": self.cost_units,
            "evidence_needed": list(self.evidence_needed),
            "assumptions": list(self.assumptions),
            "falsification_test": self.falsification_test,
            "source_prompt_digest": self.source_prompt_digest,
            "proposer_route_id": self.proposer_route_id,
            "parent_candidate_ids": list(self.parent_candidate_ids),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProposalVote:
    """A model/critic vote; never a substitute for empirical evaluation."""

    proposal_id: str
    voter_route_id: str
    support: float
    confidence: float
    reason: str
    dimensions: tuple[tuple[str, float], ...] = ()

    def validate(self, path: str = "vote") -> list[str]:
        problems: list[str] = []
        for label, value in (("support", self.support), ("confidence", self.confidence)):
            if not isfinite(value) or value < 0 or value > 1:
                problems.append(f"{path}.{label} must be in [0, 1]")
        if not ID_RE.fullmatch(self.proposal_id) or not ID_RE.fullmatch(self.voter_route_id):
            problems.append(f"{path}.proposal_id and voter_route_id must be namespaced identifiers")
        if not self.reason.strip():
            problems.append(f"{path}.reason must not be empty")
        for name, value in self.dimensions:
            if not ID_RE.fullmatch(name) or not isfinite(value) or value < 0 or value > 1:
                problems.append(f"{path}.dimensions contains an invalid entry")
        return problems


@dataclass(frozen=True)
class VoteSummary:
    proposal_id: str
    weighted_support: float
    mean_confidence: float
    disagreement: float
    voter_count: int
    dimension_means: tuple[tuple[str, float], ...] = ()


def aggregate_votes(votes: Iterable[ProposalVote]) -> tuple[VoteSummary, ...]:
    grouped: dict[str, list[ProposalVote]] = {}
    for vote in votes:
        problems = vote.validate()
        if problems:
            raise ValueError("invalid proposal vote: " + "; ".join(problems))
        grouped.setdefault(vote.proposal_id, []).append(vote)

    summaries: list[VoteSummary] = []
    for proposal_id, items in sorted(grouped.items()):
        total_weight = sum(item.confidence for item in items)
        weighted = (
            sum(item.support * item.confidence for item in items) / total_weight
            if total_weight > 0
            else sum(item.support for item in items) / len(items)
        )
        mean_conf = sum(item.confidence for item in items) / len(items)
        mean_support = sum(item.support for item in items) / len(items)
        disagreement = sum(abs(item.support - mean_support) for item in items) / len(items)
        dims: dict[str, list[float]] = {}
        for item in items:
            for name, value in item.dimensions:
                dims.setdefault(name, []).append(value)
        dimension_means = tuple((name, sum(values) / len(values)) for name, values in sorted(dims.items()))
        summaries.append(VoteSummary(proposal_id, weighted, mean_conf, disagreement, len(items), dimension_means))
    return tuple(summaries)


@dataclass(frozen=True)
class SearchBudget:
    """Hard proposal-generation budget before empirical graph evaluation."""

    max_prompt_specs: int = 128
    max_model_calls: int = 32
    max_proposals: int = 64
    max_votes: int = 128
    max_cost_units: float | None = None
    seed: int = 0

    def validate(self) -> list[str]:
        problems: list[str] = []
        for name in ("max_prompt_specs", "max_model_calls", "max_proposals", "max_votes"):
            if getattr(self, name) < 0:
                problems.append(f"{name} must be non-negative")
        if self.max_cost_units is not None and (not isfinite(self.max_cost_units) or self.max_cost_units <= 0):
            problems.append("max_cost_units must be finite and positive or null")
        return problems


@dataclass(frozen=True)
class PromptAssignment:
    prompt: PromptSpec
    route: ModelRoute
    visible_context: tuple[tuple[str, str], ...]

    @property
    def digest(self) -> str:
        return sha256_digest({
            "prompt": self.prompt.to_dict(),
            "route": self.route.id,
            "visible_context": dict(self.visible_context),
        })

    def render(self) -> str:
        context = "\n\n".join(f"[{name}]\n{value}" for name, value in self.visible_context)
        return self.prompt.render() + (f"\n\nVISIBLE CONTEXT\n{context}" if context else "")


def build_prompt_assignments(
    *,
    space: QuestionSpace,
    context: ContextEnvelope,
    routes: Sequence[ModelRoute],
    budget: SearchBudget = SearchBudget(),
) -> tuple[PromptAssignment, ...]:
    """Create a diverse, deterministic set of model-call assignments."""

    problems = space.validate() + budget.validate()
    for index, route in enumerate(routes):
        problems.extend(route.validate(f"routes[{index}]"))
    if not routes:
        problems.append("routes must not be empty")
    if problems:
        raise ValueError("invalid LLM search configuration: " + "; ".join(problems))
    if budget.max_model_calls == 0 or budget.max_prompt_specs == 0:
        return ()

    prompt_count = min(budget.max_prompt_specs, budget.max_model_calls)
    prompts = space.stratified_sample(prompt_count, seed=budget.seed)
    assignments: list[PromptAssignment] = []
    for index, prompt in enumerate(prompts):
        route = routes[index % len(routes)]
        visible = tuple(context.project(prompt.context_view).items())
        assignments.append(PromptAssignment(prompt, route, visible))
    return tuple(assignments)


def proposal_priority(
    proposal: Proposal,
    vote: VoteSummary | None = None,
    *,
    novelty_weight: float = 0.15,
    confidence_weight: float = 0.25,
    risk_penalty: float = 0.20,
    cost_penalty: float = 0.05,
    vote_weight: float = 0.35,
) -> float:
    """Heuristic scheduling priority, not an empirical performance score."""

    problems = proposal.validate()
    if problems:
        raise ValueError("invalid proposal: " + "; ".join(problems))
    support = vote.weighted_support if vote else 0.5
    return (
        novelty_weight * proposal.novelty
        + confidence_weight * proposal.confidence
        + vote_weight * support
        - risk_penalty * proposal.risk
        - cost_penalty * min(proposal.cost_units, 10.0) / 10.0
    )


def deduplicate_proposals(proposals: Iterable[Proposal]) -> tuple[Proposal, ...]:
    """Stable semantic-ish dedupe over proposal kind, operations, and hypothesis."""

    seen: set[str] = set()
    output: list[Proposal] = []
    for proposal in proposals:
        problems = proposal.validate()
        if problems:
            raise ValueError("invalid proposal: " + "; ".join(problems))
        key = sha256_digest({
            "kind": proposal.kind,
            "operations": list(proposal.operations),
            "hypothesis": " ".join(proposal.hypothesis.lower().split()),
        })
        if key not in seen:
            seen.add(key)
            output.append(proposal)
    return tuple(output)


def describe_search_space(space: QuestionSpace | None = None) -> dict[str, Any]:
    space = space or QuestionSpace()
    return {
        "model_version": SEARCH_MODEL_VERSION,
        "size": space.size,
        "axes": {
            "targets": len(space.targets),
            "context_views": len(space.context_views),
            "intents": len(space.intents),
            "families": len(space.families),
            "lenses": len(space.lenses),
            "time_lenses": len(space.time_lenses),
            "language_lenses": len(space.language_lenses),
            "evidence_stances": len(space.evidence_stances),
            "mutation_operators": len(space.mutation_operators),
            "proposal_kinds": len(space.proposal_kinds),
        },
    }


__all__ = [
    "SEARCH_MODEL_VERSION", "CONTEXT_VIEWS", "EVIDENCE_STANCES", "INTENTS",
    "LANGUAGE_LENSES", "LENSES", "MUTATION_OPERATORS", "PROPOSAL_KINDS",
    "QUESTION_FAMILIES", "TARGETS", "TIME_LENSES", "ContextEnvelope", "ModelRoute",
    "PromptAssignment", "PromptSpec", "Proposal", "ProposalVote", "QuestionSpace",
    "SearchBudget", "VoteSummary", "aggregate_votes", "build_prompt_assignments",
    "deduplicate_proposals", "describe_search_space", "proposal_priority",
]
