"""Adaptive, inspectable question and proposal contracts for graph solutioning.

Question variants are generated lazily from versioned axes rather than stored as
an unmaintainable list.  An LLM response is always a proposal artifact.  It does
not compile a graph, admit a node, execute code, access a hidden evaluator, or
approve its own promotion.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from math import gcd, isfinite, prod, sqrt
from random import Random
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE, canonical_json, sha256_digest

PROPOSAL_SPACE_MODEL_VERSION = "0.1"


class ProposalKind(str, Enum):
    TASK_REFRAME = "proposal.task-reframe"
    RESEARCH = "proposal.research"
    GRAPH = "proposal.graph"
    SUBGRAPH = "proposal.subgraph"
    NODE = "proposal.node"
    ROUTE = "proposal.route"
    MUTATION = "proposal.mutation"
    REPLACEMENT = "proposal.replacement"
    PACKAGE = "proposal.package"
    PARAMETER_SPACE = "proposal.parameter-space"
    FEATURE = "proposal.feature"
    VALIDATION = "proposal.validation"
    ENSEMBLE = "proposal.ensemble"
    RESOURCE = "proposal.resource"
    DIAGNOSTIC = "proposal.diagnostic"
    STOP = "proposal.stop"


class ContextExposure(str, Enum):
    NONE = "context.none"
    TASK_ONLY = "context.task-only"
    SCHEMA_ONLY = "context.schema-only"
    DATA_PROFILE = "context.data-profile"
    BLUEPRINT = "context.blueprint"
    GRAPH_SUMMARY = "context.graph-summary"
    GRAPH_FULL = "context.graph-full"
    EVIDENCE_SUMMARY = "context.evidence-summary"
    FAILURES_ONLY = "context.failures-only"
    CHAMPION_ONLY = "context.champion-only"
    ALTERNATIVES_ONLY = "context.alternatives-only"
    RESEARCH_SUMMARY = "context.research-summary"
    HYBRID = "context.hybrid"
    FULL = "context.full"


class ResponseMode(str, Enum):
    YES_NO = "response.yes-no"
    SCALE_1_5 = "response.scale-1-5"
    SCALE_1_10 = "response.scale-1-10"
    SCALE_0_100 = "response.scale-0-100"
    RANKED_LIST = "response.ranked-list"
    PROS_CONS = "response.pros-cons"
    SINGLE_ACTION = "response.single-action"
    EXHAUSTIVE = "response.exhaustive"
    COUNTEREXAMPLE = "response.counterexample"
    HYPOTHESIS = "response.hypothesis"
    MINIMAL_PATCH = "response.minimal-patch"
    STRUCTURED_PROPOSAL = "response.structured-proposal"


class Polarity(str, Enum):
    POSITIVE = "polarity.positive"
    NEGATIVE = "polarity.negative"
    INVERSE = "polarity.inverse"
    NULL = "polarity.null"
    COUNTERFACTUAL = "polarity.counterfactual"
    ADVERSARIAL = "polarity.adversarial"
    OMISSION = "polarity.omission"
    EXCESS = "polarity.excess"
    ANTI_PATTERN = "polarity.anti-pattern"
    ROBUSTNESS = "polarity.robustness"


_RESPONSE_INSTRUCTIONS = {
    ResponseMode.YES_NO: "Return yes or no, one reason, and one next action.",
    ResponseMode.SCALE_1_5: "Score 1 to 5, define anchors, and justify the score.",
    ResponseMode.SCALE_1_10: "Score 1 to 10, define anchors, and justify the score.",
    ResponseMode.SCALE_0_100: "Score 0 to 100, state uncertainty, and justify it.",
    ResponseMode.RANKED_LIST: "Return a ranked list with explicit criteria and ties.",
    ResponseMode.PROS_CONS: "Return pros, cons, failure modes, and a conditional recommendation.",
    ResponseMode.SINGLE_ACTION: "Return exactly one next action and its acceptance test.",
    ResponseMode.EXHAUSTIVE: "Enumerate distinct feasible alternatives and mark speculation.",
    ResponseMode.COUNTEREXAMPLE: "Try to falsify the design with concrete counterexamples.",
    ResponseMode.HYPOTHESIS: "Return a testable hypothesis, experiment, and stopping rule.",
    ResponseMode.MINIMAL_PATCH: "Return the smallest semantic patch that tests the uncertainty.",
    ResponseMode.STRUCTURED_PROPOSAL: "Return one JSON object matching the response schema.",
}


@dataclass(frozen=True)
class QuestionAxes:
    proposal_kinds: tuple[ProposalKind, ...]
    intents: tuple[str, ...]
    focuses: tuple[str, ...]
    scales: tuple[str, ...]
    response_modes: tuple[ResponseMode, ...]
    polarities: tuple[Polarity, ...]
    persona_roles: tuple[str, ...]
    persona_stances: tuple[str, ...]
    theory_lenses: tuple[str, ...]
    language_lenses: tuple[str, ...]
    context_exposures: tuple[ContextExposure, ...]
    salts: tuple[str, ...]

    @property
    def values(self) -> tuple[tuple[Any, ...], ...]:
        return (
            self.proposal_kinds,
            self.intents,
            self.focuses,
            self.scales,
            self.response_modes,
            self.polarities,
            self.persona_roles,
            self.persona_stances,
            self.theory_lenses,
            self.language_lenses,
            self.context_exposures,
            self.salts,
        )

    @property
    def combination_count(self) -> int:
        return prod(len(items) for items in self.values)

    def validate(self, path: str = "question_axes") -> list[str]:
        problems: list[str] = []
        for index, items in enumerate(self.values):
            if not items:
                problems.append(f"{path}[{index}] must not be empty")
            if len(items) != len(set(items)):
                problems.append(f"{path}[{index}] must be unique")
        return problems

    def to_dict(self) -> dict[str, Any]:
        names = (
            "proposal_kinds", "intents", "focuses", "scales", "response_modes",
            "polarities", "persona_roles", "persona_stances", "theory_lenses",
            "language_lenses", "context_exposures", "salts",
        )
        result: dict[str, Any] = {}
        for name, items in zip(names, self.values, strict=True):
            result[name] = [item.value if isinstance(item, Enum) else item for item in items]
        return result


@dataclass(frozen=True)
class QuestionVariant:
    id: str
    proposal_kind: ProposalKind
    intent: str
    focus: str
    scale: str
    response_mode: ResponseMode
    polarity: Polarity
    persona_role: str
    persona_stance: str
    theory_lens: str
    language_lens: str
    context_exposure: ContextExposure
    salt: str
    question: str
    system_directive: str
    response_instruction: str
    seed: int

    @property
    def factors(self) -> tuple[tuple[str, str], ...]:
        return (
            ("proposal_kind", self.proposal_kind.value),
            ("intent", self.intent),
            ("focus", self.focus),
            ("scale", self.scale),
            ("response_mode", self.response_mode.value),
            ("polarity", self.polarity.value),
            ("persona_role", self.persona_role),
            ("persona_stance", self.persona_stance),
            ("theory_lens", self.theory_lens),
            ("language_lens", self.language_lens),
            ("context_exposure", self.context_exposure.value),
            ("salt", self.salt),
        )

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def with_exposure(self, exposure: ContextExposure) -> QuestionVariant:
        payload = {**self.to_dict(), "context_exposure": exposure.value}
        suffix = sha256_digest(payload).removeprefix("sha256:")[:24]
        return QuestionVariant(
            id=f"question.variant.{suffix}", proposal_kind=self.proposal_kind,
            intent=self.intent, focus=self.focus, scale=self.scale,
            response_mode=self.response_mode, polarity=self.polarity,
            persona_role=self.persona_role, persona_stance=self.persona_stance,
            theory_lens=self.theory_lens, language_lens=self.language_lens,
            context_exposure=exposure, salt=self.salt, question=self.question,
            system_directive=self.system_directive,
            response_instruction=self.response_instruction, seed=self.seed,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_space_model_version": PROPOSAL_SPACE_MODEL_VERSION,
            "id": self.id,
            **dict(self.factors),
            "question": self.question,
            "system_directive": self.system_directive,
            "response_instruction": self.response_instruction,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class QuestionSpace:
    id: str
    version: str
    axes: QuestionAxes

    @property
    def count(self) -> int:
        return self.axes.combination_count

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems = self.axes.validate()
        if not ID_RE.fullmatch(self.id) or not self.version.strip():
            problems.append("question-space id and version are required")
        return problems

    def variant_at(self, index: int, *, seed: int = 0) -> QuestionVariant:
        if index < 0 or index >= self.count:
            raise IndexError(index)
        coordinates: list[int] = []
        remaining = index
        for items in reversed(self.axes.values):
            coordinates.append(remaining % len(items))
            remaining //= len(items)
        values = [items[i] for items, i in zip(self.axes.values, reversed(coordinates), strict=True)]
        (
            kind, intent, focus, scale, response_mode, polarity, role, stance,
            theory, language, exposure, salt,
        ) = values
        question = (
            f"Act as a {stance} {role}. Use {theory}, the {language} framing lens, and "
            f"the controlled cue '{salt}'. Examine {focus} at {scale}. The requested "
            f"artifact is {kind.value}; the intent is {intent}; use a {polarity.value} "
            "examination. What concrete proposal, test, omission, reduction, analogy, or "
            "next move should be considered? Preserve the task oracle, rules, data boundary, "
            "and hard resource constraints."
        )
        system = (
            "You generate proposals only. You are not the compiler, executor, evaluator, or "
            "promotion authority. Separate facts, assumptions, and speculation. Do not reveal "
            "private chain-of-thought. Return concise rationale, risks, dependencies, and an "
            "acceptance test. Final output must be in English."
        )
        raw = {
            "space": self.digest, "index": index, "seed": seed,
            "kind": kind.value, "intent": intent, "focus": focus, "scale": scale,
            "response": response_mode.value, "polarity": polarity.value,
            "role": role, "stance": stance, "theory": theory, "language": language,
            "exposure": exposure.value, "salt": salt,
        }
        suffix = sha256_digest(raw).removeprefix("sha256:")[:24]
        return QuestionVariant(
            id=f"question.variant.{suffix}", proposal_kind=kind, intent=intent,
            focus=focus, scale=scale, response_mode=response_mode, polarity=polarity,
            persona_role=role, persona_stance=stance, theory_lens=theory,
            language_lens=language, context_exposure=exposure, salt=salt,
            question=question, system_directive=system,
            response_instruction=_RESPONSE_INSTRUCTIONS[response_mode], seed=seed,
        )

    def iter_variants(
        self, *, limit: int | None = None, seed: int = 0, start: int = 0,
        stride: int | None = None,
    ) -> Iterator[QuestionVariant]:
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or null")
        if not 0 <= start < self.count:
            raise ValueError("start must be inside the question space")
        if stride is None:
            random = Random(seed)
            stride = random.randrange(1, self.count + 1)
            while gcd(stride, self.count) != 1:
                stride = random.randrange(1, self.count + 1)
        if stride <= 0 or gcd(stride, self.count) != 1:
            raise ValueError("stride must be positive and coprime to the space size")
        visits = self.count if limit is None else min(limit, self.count)
        for offset in range(visits):
            yield self.variant_at((start + offset * stride) % self.count, seed=seed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_space_model_version": PROPOSAL_SPACE_MODEL_VERSION,
            "id": self.id, "version": self.version, "axes": self.axes.to_dict(),
            "count": self.count,
        }


_STANDARD_CONTEXT = (
    "task", "rules", "schema", "data_profile", "column_profile", "blueprint",
    "graph_summary", "graph_full", "route_summary", "evidence_summary", "failures",
    "champion", "alternatives", "package_catalog", "research_summary", "code_summary",
    "constraints",
)

_EXPOSURE = {
    ContextExposure.NONE: (),
    ContextExposure.TASK_ONLY: ("task",),
    ContextExposure.SCHEMA_ONLY: ("task", "schema", "column_profile"),
    ContextExposure.DATA_PROFILE: ("task", "schema", "data_profile", "column_profile"),
    ContextExposure.BLUEPRINT: ("task", "rules", "blueprint", "constraints"),
    ContextExposure.GRAPH_SUMMARY: ("task", "graph_summary", "constraints"),
    ContextExposure.GRAPH_FULL: ("task", "graph_full", "constraints"),
    ContextExposure.EVIDENCE_SUMMARY: ("task", "graph_summary", "evidence_summary"),
    ContextExposure.FAILURES_ONLY: ("task", "failures", "constraints"),
    ContextExposure.CHAMPION_ONLY: ("task", "champion", "evidence_summary"),
    ContextExposure.ALTERNATIVES_ONLY: ("task", "alternatives", "evidence_summary"),
    ContextExposure.RESEARCH_SUMMARY: ("task", "research_summary", "constraints"),
    ContextExposure.HYBRID: (
        "task", "rules", "schema", "data_profile", "graph_summary",
        "evidence_summary", "failures", "constraints",
    ),
    ContextExposure.FULL: _STANDARD_CONTEXT,
}


@dataclass(frozen=True)
class ContextProjection:
    exposure: ContextExposure
    included_sections: tuple[str, ...]
    omitted_sections: tuple[str, ...]
    text: str

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "exposure": self.exposure.value,
            "included_sections": list(self.included_sections),
            "omitted_sections": list(self.omitted_sections), "text": self.text,
        }


@dataclass(frozen=True)
class ContextBundle:
    id: str
    sections: tuple[tuple[str, str], ...]
    hidden_sections: tuple[tuple[str, str], ...] = ()
    source_digests: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("context id must be namespaced")
        visible = [key for key, _ in self.sections]
        hidden = [key for key, _ in self.hidden_sections]
        if len(visible) != len(set(visible)) or len(hidden) != len(set(hidden)):
            problems.append("context section names must be unique")
        if set(visible) & set(hidden):
            problems.append("visible and hidden context must be disjoint")
        if any(not DIGEST_RE.fullmatch(item) for item in self.source_digests):
            problems.append("context source digests must be sha256 digests")
        return problems

    def project(self, exposure: ContextExposure) -> ContextProjection:
        values = dict(self.sections)
        requested = tuple(values) if exposure == ContextExposure.FULL else _EXPOSURE[exposure]
        included = tuple(key for key in requested if values.get(key, "").strip())
        omitted = tuple(key for key, value in self.sections if key not in included and value.strip())
        text = "\n\n".join(
            f"## {key.replace('_', ' ').title()}\n{values[key]}" for key in included
        )
        return ContextProjection(exposure, included, omitted, text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_space_model_version": PROPOSAL_SPACE_MODEL_VERSION,
            "id": self.id, "sections": dict(self.sections),
            "source_digests": list(self.source_digests),
        }


@dataclass(frozen=True)
class ProposalContract:
    kind: ProposalKind
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()

    def validate(self, payload: Mapping[str, Any]) -> list[str]:
        missing = sorted(set(self.required) - set(payload))
        unknown = sorted(set(payload) - set(self.required) - set(self.optional))
        problems: list[str] = []
        if missing:
            problems.append("payload missing: " + ", ".join(missing))
        if unknown:
            problems.append("payload has unknown fields: " + ", ".join(unknown))
        try:
            canonical_json(dict(payload))
        except (TypeError, ValueError):
            problems.append("payload must be JSON serialisable")
        return problems


DEFAULT_PROPOSAL_CONTRACTS = (
    ProposalContract(ProposalKind.TASK_REFRAME, ("reframed_task", "preserved_constraints", "new_questions"), ("assumptions", "risks")),
    ProposalContract(ProposalKind.RESEARCH, ("questions", "sources_to_seek", "expected_decisions"), ("stop_conditions", "risks")),
    ProposalContract(ProposalKind.GRAPH, ("external_inputs", "external_outputs", "obligations", "bindings", "goals"), ("controllers", "constraints", "subgraphs")),
    ProposalContract(ProposalKind.SUBGRAPH, ("boundary_inputs", "boundary_outputs", "obligations", "bindings", "goal"), ("constraints",)),
    ProposalContract(ProposalKind.NODE, ("capability", "inputs", "outputs", "runtime", "effects", "permissions", "verifier"), ("parameters", "failure_modes", "resources", "fallbacks")),
    ProposalContract(ProposalKind.ROUTE, ("assignments", "expected_mechanism", "evaluation_plan"), ("fallbacks", "interactions", "risks")),
    ProposalContract(ProposalKind.MUTATION, ("operators", "target_selectors", "expected_effect", "acceptance_test"), ("rollback", "risks")),
    ProposalContract(ProposalKind.REPLACEMENT, ("replace_target", "replacement", "interface_preservation", "acceptance_test"), ("fallback", "risks")),
    ProposalContract(ProposalKind.PACKAGE, ("distribution_name", "import_name", "version_constraint", "source_repository", "license", "capabilities", "integration_plan", "tests", "fallback"), ("system_dependencies", "security_notes", "alternatives", "wheel_digest")),
    ProposalContract(ProposalKind.PARAMETER_SPACE, ("parameters", "constraints", "search_strategy", "budget", "evaluation_plan"), ("priors", "fidelity", "stopping_rule")),
    ProposalContract(ProposalKind.FEATURE, ("feature_definition", "data_requirements", "leakage_checks", "ablation"), ("implementation", "cost", "risks")),
    ProposalContract(ProposalKind.VALIDATION, ("validation_design", "failure_risks", "acceptance_criteria"), ("stress_tests", "holdout", "uncertainty")),
    ProposalContract(ProposalKind.ENSEMBLE, ("members", "combination_rule", "diversity_evidence", "evaluation_plan"), ("calibration", "fallback", "cost")),
    ProposalContract(ProposalKind.RESOURCE, ("bottleneck", "change", "expected_savings", "correctness_checks"), ("hardware", "fallback", "risks")),
    ProposalContract(ProposalKind.DIAGNOSTIC, ("findings", "evidence_needed", "priority_order"), ("counterarguments", "uncertainty")),
    ProposalContract(ProposalKind.STOP, ("decision", "reasons", "conditions_to_resume"), ("remaining_uncertainty", "safe_outputs")),
)


def _contracts(contracts: Sequence[ProposalContract]) -> dict[ProposalKind, ProposalContract]:
    result = {item.kind: item for item in contracts}
    if len(result) != len(contracts):
        raise ValueError("proposal contract kinds must be unique")
    return result


@dataclass(frozen=True)
class ProposalArtifact:
    id: str
    kind: ProposalKind
    title: str
    rationale: str
    hypothesis: str
    target_ref: str
    payload: Mapping[str, Any]
    proposer_id: str
    question_variant_id: str
    model_id: str = ""
    confidence: float = 0.5
    uncertainty: float = 1.0
    evidence_refs: tuple[str, ...] = ()
    parent_proposal_ids: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()
    created_at: str = ""

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def semantic_fingerprint(self) -> str:
        return sha256_digest({"kind": self.kind.value, "target": self.target_ref, "payload": dict(self.payload)})

    def validate(self, contracts: Sequence[ProposalContract] = DEFAULT_PROPOSAL_CONTRACTS) -> list[str]:
        problems: list[str] = []
        for value in (self.id, self.proposer_id, self.question_variant_id):
            if not ID_RE.fullmatch(value):
                problems.append("proposal ids must be namespaced")
        if not self.title.strip() or not self.rationale.strip() or not self.hypothesis.strip():
            problems.append("proposal title, rationale, and hypothesis are required")
        if not self.target_ref.strip():
            problems.append("proposal target_ref is required")
        if not isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            problems.append("proposal confidence must be between zero and one")
        if not isfinite(self.uncertainty) or self.uncertainty < 0:
            problems.append("proposal uncertainty must be non-negative")
        contract = _contracts(contracts).get(self.kind)
        if contract is None:
            problems.append("proposal kind has no payload contract")
        else:
            problems.extend(contract.validate(self.payload))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_space_model_version": PROPOSAL_SPACE_MODEL_VERSION,
            "id": self.id, "kind": self.kind.value, "title": self.title,
            "rationale": self.rationale, "hypothesis": self.hypothesis,
            "target_ref": self.target_ref,
            "payload": json.loads(canonical_json(dict(self.payload))),
            "proposer_id": self.proposer_id,
            "question_variant_id": self.question_variant_id, "model_id": self.model_id,
            "confidence": self.confidence, "uncertainty": self.uncertainty,
            "evidence_refs": list(self.evidence_refs),
            "parent_proposal_ids": list(self.parent_proposal_ids),
            "risk_flags": list(self.risk_flags), "created_at": self.created_at,
        }


_JSON_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def parse_proposals(
    raw: str, *, proposer_id: str, question_variant_id: str,
    model_id: str = "", created_at: str = "",
    contracts: Sequence[ProposalContract] = DEFAULT_PROPOSAL_CONTRACTS,
) -> tuple[ProposalArtifact, ...]:
    text = raw.strip()
    match = _JSON_FENCE.fullmatch(text)
    if match:
        text = match.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"proposal response is not JSON: {exc}") from exc
    items = value.get("proposals") if isinstance(value, Mapping) and set(value) == {"proposals"} else [value]
    if not isinstance(items, list):
        raise ValueError("proposal envelope must contain a list")
    allowed = {
        "kind", "title", "rationale", "hypothesis", "target_ref", "payload",
        "confidence", "uncertainty", "evidence_refs", "parent_proposal_ids", "risk_flags",
    }
    required = {"kind", "title", "rationale", "hypothesis", "target_ref", "payload"}
    proposals: list[ProposalArtifact] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"proposal[{index}] must be an object")
        if required - set(item) or set(item) - allowed:
            raise ValueError(f"proposal[{index}] has missing or unknown fields")
        if not isinstance(item["payload"], Mapping):
            raise ValueError(f"proposal[{index}].payload must be an object")
        suffix = sha256_digest({"proposer": proposer_id, "question": question_variant_id, "model": model_id, "index": index, "item": item}).removeprefix("sha256:")[:24]
        proposal = ProposalArtifact(
            id=f"proposal.{suffix}", kind=ProposalKind(item["kind"]),
            title=str(item["title"]), rationale=str(item["rationale"]),
            hypothesis=str(item["hypothesis"]), target_ref=str(item["target_ref"]),
            payload=dict(item["payload"]), proposer_id=proposer_id,
            question_variant_id=question_variant_id, model_id=model_id,
            confidence=float(item.get("confidence", 0.5)),
            uncertainty=float(item.get("uncertainty", 1.0)),
            evidence_refs=tuple(item.get("evidence_refs", ())),
            parent_proposal_ids=tuple(item.get("parent_proposal_ids", ())),
            risk_flags=tuple(item.get("risk_flags", ())), created_at=created_at,
        )
        problems = proposal.validate(contracts)
        if problems:
            raise ValueError("invalid proposal: " + "; ".join(problems))
        proposals.append(proposal)
    return tuple(proposals)


def deduplicate_proposals(proposals: Sequence[ProposalArtifact]) -> tuple[tuple[ProposalArtifact, ...], tuple[tuple[str, str], ...]]:
    retained: list[ProposalArtifact] = []
    duplicates: list[tuple[str, str]] = []
    by_fingerprint: dict[str, str] = {}
    for proposal in proposals:
        previous = by_fingerprint.get(proposal.semantic_fingerprint)
        if previous is None:
            by_fingerprint[proposal.semantic_fingerprint] = proposal.id
            retained.append(proposal)
        else:
            duplicates.append((proposal.id, previous))
    return tuple(retained), tuple(duplicates)


@dataclass(frozen=True)
class FactorStat:
    factor: str
    count: int = 0
    mean_reward: float = 0.0
    m2: float = 0.0

    def update(self, reward: float) -> FactorStat:
        if not isfinite(reward):
            raise ValueError("reward must be finite")
        count = self.count + 1
        delta = reward - self.mean_reward
        mean = self.mean_reward + delta / count
        return FactorStat(self.factor, count, mean, self.m2 + delta * (reward - mean))


@dataclass(frozen=True)
class QuestionValueModel:
    revision: str = "untrained"
    observations: int = 0
    factors: tuple[FactorStat, ...] = ()

    @property
    def factor_map(self) -> dict[str, FactorStat]:
        return {item.factor: item for item in self.factors}

    def update(self, question: QuestionVariant, model_endpoint_id: str, reward: float) -> QuestionValueModel:
        mapping = self.factor_map
        names = tuple(f"{key}={value}" for key, value in question.factors) + (f"model_endpoint={model_endpoint_id}",)
        for name in names:
            mapping[name] = mapping.get(name, FactorStat(name)).update(reward)
        revision = "question-belief." + sha256_digest({"parent": self.revision, "question": question.id, "model": model_endpoint_id, "reward": reward}).removeprefix("sha256:")[:24]
        return QuestionValueModel(revision, self.observations + 1, tuple(mapping[key] for key in sorted(mapping)))

    def score(self, question: QuestionVariant, *, model_endpoint_id: str = "", exploration: float = 1.0) -> float:
        names = [f"{key}={value}" for key, value in question.factors]
        if model_endpoint_id:
            names.append(f"model_endpoint={model_endpoint_id}")
        mapping = self.factor_map
        total = max(self.observations, 1)
        values = []
        for name in names:
            stat = mapping.get(name, FactorStat(name))
            values.append(stat.mean_reward + exploration * sqrt(math.log(total + 2) / (stat.count + 1)))
        return sum(values) / max(len(values), 1)


@dataclass(frozen=True)
class AdaptiveQuestionSampler:
    exploration: float = 1.0
    random_fraction: float = 0.20
    candidate_pool_size: int = 4096

    def sample(self, space: QuestionSpace, model: QuestionValueModel, *, limit: int, seed: int, model_endpoint_id: str = "") -> tuple[QuestionVariant, ...]:
        if limit <= 0 or self.candidate_pool_size <= 0:
            raise ValueError("limits must be positive")
        if not 0 <= self.random_fraction <= 1:
            raise ValueError("random_fraction must be between zero and one")
        pool = tuple(space.iter_variants(limit=min(space.count, max(limit, self.candidate_pool_size)), seed=seed, start=seed % space.count))
        random_count = min(limit, round(limit * self.random_fraction))
        guided_count = limit - random_count
        ranked = sorted(pool, key=lambda item: (-model.score(item, model_endpoint_id=model_endpoint_id, exploration=self.exploration), item.id))
        selected = list(ranked[:guided_count])
        used = {item.id for item in selected}
        remainder = [item for item in pool if item.id not in used]
        Random(seed ^ 0xA5A5A5A5).shuffle(remainder)
        selected.extend(remainder[:random_count])
        return tuple(selected[:limit])


PROPOSAL_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["kind", "title", "rationale", "hypothesis", "target_ref", "payload", "confidence", "uncertainty", "evidence_refs", "parent_proposal_ids", "risk_flags"],
    "properties": {
        "kind": {"type": "string", "enum": [item.value for item in ProposalKind]},
        "title": {"type": "string", "minLength": 1},
        "rationale": {"type": "string", "minLength": 1},
        "hypothesis": {"type": "string", "minLength": 1},
        "target_ref": {"type": "string", "minLength": 1},
        "payload": {"type": "object"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertainty": {"type": "number", "minimum": 0},
        "evidence_refs": {"type": "array", "items": {"type": "string"}},
        "parent_proposal_ids": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
    },
}


def default_kaggle_question_space() -> QuestionSpace:
    focuses = (
        "task framing", "metric", "competition rules", "public/private leaderboard risk",
        "cross-validation", "time split", "group split", "adversarial validation",
        "leakage", "train-test drift", "schema", "columns", "target semantics",
        "missingness", "imputation", "outliers", "duplicates", "label noise",
        "cleaning", "smoothing", "scaling", "transformations", "categorical encoding",
        "text representation", "image representation", "time-series representation",
        "feature engineering", "interactions", "aggregations", "lags", "target encoding",
        "feature selection", "dimensionality reduction", "unsupervised features",
        "pretraining", "transfer learning", "model family", "boosting", "neural networks",
        "probabilistic models", "symbolic models", "hybrid symbolic-ML",
        "semi-supervised learning", "pseudo-labeling", "loss", "class imbalance",
        "sample weighting", "hyperparameters", "early stopping", "calibration",
        "uncertainty", "ensembling", "stacking", "post-processing", "submission",
        "runtime", "memory", "CPU", "GPU", "hardware", "packages", "reproducibility",
        "failure analysis", "route topology", "node replacement", "subgraph replacement",
        "graph simplification", "graph expansion", "research retrieval",
    )
    roles = (
        "Kaggle grandmaster", "statistician", "Bayesian researcher", "causal researcher",
        "information theorist", "optimization researcher", "numerical analyst",
        "graph theorist", "control theorist", "experimental-design specialist",
        "robust-statistics specialist", "time-series scientist", "vision researcher",
        "NLP researcher", "tabular specialist", "feature engineer", "data-quality engineer",
        "MLOps engineer", "compiler engineer", "distributed-systems engineer",
        "GPU engineer", "privacy engineer", "security reviewer", "red-team evaluator",
        "reproducibility auditor", "package maintainer", "minimalist architect",
        "maximalist experimenter", "future maintainer", "cost accountant",
        "theoretical computer scientist", "physics-inspired modeler",
        "symbolic reasoning researcher", "blind external reviewer", "leakage hunter",
        "ensemble specialist", "calibration specialist", "benchmark designer",
        "operations researcher", "meta-learning researcher", "AutoML researcher",
    )
    theories = (
        "information theory", "decision theory", "Bayesian inference", "causal inference",
        "experimental design", "robust statistics", "graph theory", "control theory",
        "game theory", "convex optimization", "multi-objective optimization",
        "algorithmic complexity", "minimum description length", "bias-variance analysis",
        "ensemble diversity", "calibration theory", "uncertainty quantification",
        "numerical linear algebra", "signal processing", "dynamical systems",
        "symbolic computation", "program synthesis", "compiler optimization",
        "database optimization", "active learning", "meta-learning", "transfer learning",
        "optimal transport", "kernel methods", "Gaussian processes",
        "information bottleneck", "change-point detection", "scientific falsification",
    )
    salts = (
        "invariants", "bottleneck", "orthogonality", "counterexample", "boundary case",
        "symmetry", "duality", "compression", "causal mechanism", "identifiability",
        "sufficiency", "error decomposition", "ablation", "negative control", "stress test",
        "sensitivity", "calibration", "tail risk", "regime change", "adversarial split",
        "Pareto frontier", "failure certificate", "proof obligation", "mutation operator",
        "compiler gate", "holdout firewall", "semantic drift", "data lineage",
        "hidden dependency", "interaction effect", "champion challenger", "quorum",
        "fallback diversity", "information gain", "opportunity cost", "replayability",
        "counterfactual", "null model", "upper bound", "approximation error",
        "estimation error", "leakage path", "distribution shift", "runtime variance",
        "memory locality", "hardware utilization", "package provenance",
    )
    axes = QuestionAxes(
        proposal_kinds=tuple(ProposalKind),
        intents=("construct", "extend", "what-next", "complete", "reduce", "criticize", "verify", "compare", "prioritize", "analogize", "invert", "challenge", "diagnose", "optimize", "simplify", "diversify", "research", "find-missing", "find-excess", "stop"),
        focuses=focuses,
        scales=("micro", "parameter", "node", "slot", "subgraph", "route", "graph", "system", "portfolio"),
        response_modes=tuple(ResponseMode), polarities=tuple(Polarity),
        persona_roles=roles,
        persona_stances=("optimistic", "skeptical", "conservative", "aggressively experimental", "cost-first", "latency-first", "accuracy-first", "robustness-first", "simplicity-first", "novelty-seeking", "evidence-first", "failure-first"),
        theory_lenses=theories,
        language_lenses=("English", "Tagalog", "Spanish", "French", "German", "Portuguese", "Japanese", "Mandarin Chinese", "Arabic", "Hindi", "formal mathematics", "plain-language teaching"),
        context_exposures=tuple(ContextExposure), salts=salts,
    )
    space = QuestionSpace("question-space.kaggle-universal", "1.0.0", axes)
    problems = space.validate()
    if problems:
        raise ValueError("invalid default question space: " + "; ".join(problems))
    return space


__all__ = [
    "PROPOSAL_SPACE_MODEL_VERSION", "PROPOSAL_RESPONSE_SCHEMA",
    "AdaptiveQuestionSampler", "ContextBundle", "ContextExposure", "ContextProjection",
    "DEFAULT_PROPOSAL_CONTRACTS", "FactorStat", "Polarity", "ProposalArtifact",
    "ProposalContract", "ProposalKind", "QuestionAxes", "QuestionSpace",
    "QuestionValueModel", "QuestionVariant", "ResponseMode", "deduplicate_proposals",
    "default_kaggle_question_space", "parse_proposals",
]
