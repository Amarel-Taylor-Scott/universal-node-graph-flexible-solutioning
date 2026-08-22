"""Bounded multi-model proposal swarms with explicit context and evidence boundaries.

The reference engine calls language-model adapters and returns immutable proposal
artifacts and receipts.  It never edits a graph, executes a proposed package,
reads a hidden evaluator, or promotes a candidate.  Compiler, runtime, evaluator,
and campaign authorities remain separate.
"""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Protocol, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite, sqrt
from statistics import fmean
from time import monotonic
from typing import Any

from solutiongraph.model import ID_RE, canonical_json, sha256_digest
from solutiongraph.proposal_space import (
    PROPOSAL_RESPONSE_SCHEMA,
    AdaptiveQuestionSampler,
    ContextBundle,
    ContextExposure,
    ProposalArtifact,
    ProposalKind,
    QuestionSpace,
    QuestionValueModel,
    QuestionVariant,
    deduplicate_proposals,
    parse_proposals,
)

PROPOSAL_SWARM_MODEL_VERSION = "0.1"


class SwarmPattern(str, Enum):
    INDEPENDENT = "swarm.independent"
    CROSS_MODEL = "swarm.cross-model"
    BLIND_FULL_HYBRID = "swarm.blind-full-hybrid"
    PAIRED_OPPOSITION = "swarm.paired-opposition"
    FOCUS_SWEEP = "swarm.focus-sweep"
    RANDOM_NEIGHBORHOOD = "swarm.random-neighborhood"
    JUDGE_PANEL = "swarm.judge-panel"
    DELPHI = "swarm.delphi"


class LaneRole(str, Enum):
    PROPOSER = "lane.proposer"
    CRITIC = "lane.critic"
    SYNTHESIZER = "lane.synthesizer"
    JUDGE = "lane.judge"
    BLIND_PROPOSER = "lane.blind-proposer"
    INFORMED_PROPOSER = "lane.informed-proposer"


@dataclass(frozen=True)
class ModelEndpoint:
    id: str
    adapter_id: str
    model: str
    system_prefix: str = ""
    temperature: float = 0.2
    seed: int | None = None
    max_tokens: int = 2048
    cost_units_per_request: float = 1.0
    tags: tuple[str, ...] = ()

    def validate(self, path: str = "model_endpoint") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.adapter_id):
            problems.append(f"{path} ids must be namespaced")
        if not self.model.strip():
            problems.append(f"{path}.model must not be empty")
        if not isfinite(self.temperature) or self.temperature < 0:
            problems.append(f"{path}.temperature must be finite and non-negative")
        if self.max_tokens <= 0:
            problems.append(f"{path}.max_tokens must be positive")
        if not isfinite(self.cost_units_per_request) or self.cost_units_per_request < 0:
            problems.append(f"{path}.cost_units_per_request must be non-negative")
        if len(self.tags) != len(set(self.tags)):
            problems.append(f"{path}.tags must be unique")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "adapter_id": self.adapter_id, "model": self.model,
            "system_prefix": self.system_prefix, "temperature": self.temperature,
            "seed": self.seed, "max_tokens": self.max_tokens,
            "cost_units_per_request": self.cost_units_per_request,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class LLMRequest:
    id: str
    endpoint: ModelEndpoint
    system_prompt: str
    user_prompt: str
    response_schema: Mapping[str, Any]
    metadata: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_swarm_model_version": PROPOSAL_SWARM_MODEL_VERSION,
            "id": self.id, "endpoint": self.endpoint.to_dict(),
            "system_prompt": self.system_prompt, "user_prompt": self.user_prompt,
            "response_schema": json.loads(canonical_json(dict(self.response_schema))),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LLMResponse:
    request_id: str
    adapter_id: str
    model: str
    raw_text: str
    duration_seconds: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    provider_metadata: tuple[tuple[str, Any], ...] = ()
    error: str = ""

    @property
    def successful(self) -> bool:
        return not self.error

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "llm_response") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.request_id) or not ID_RE.fullmatch(self.adapter_id):
            problems.append(f"{path} ids must be namespaced")
        if not self.model.strip():
            problems.append(f"{path}.model must not be empty")
        if not isfinite(self.duration_seconds) or self.duration_seconds < 0:
            problems.append(f"{path}.duration_seconds must be non-negative")
        for value in (self.prompt_tokens, self.completion_tokens):
            if value is not None and value < 0:
                problems.append(f"{path} token counts must be non-negative or null")
        if not self.error and not self.raw_text.strip():
            problems.append(f"{path}.raw_text is required for a successful response")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id, "adapter_id": self.adapter_id,
            "model": self.model, "raw_text": self.raw_text,
            "duration_seconds": self.duration_seconds,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "provider_metadata": dict(self.provider_metadata), "error": self.error,
        }


class LanguageModelAdapter(Protocol):
    adapter_id: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...


@dataclass
class RecordedLanguageModelAdapter:
    """Deterministic adapter for tests, replay, and offline fixtures."""

    adapter_id: str
    responses: Mapping[str, str]
    default_response: str = ""
    requests: list[LLMRequest] = field(default_factory=list)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        raw = self.responses.get(request.id, self.responses.get(request.digest, self.default_response))
        if not raw:
            return LLMResponse(
                request.id, self.adapter_id, request.endpoint.model, "",
                error="recorded response not found",
            )
        return LLMResponse(request.id, self.adapter_id, request.endpoint.model, raw)


@dataclass(frozen=True)
class SwarmLane:
    id: str
    endpoint_id: str
    question: QuestionVariant
    role: LaneRole = LaneRole.PROPOSER
    phase: int = 0
    required: bool = False
    parent_lane_ids: tuple[str, ...] = ()
    blind_group: str = ""

    def validate(self, path: str = "swarm_lane") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.endpoint_id):
            problems.append(f"{path} ids must be namespaced")
        if self.phase < 0:
            problems.append(f"{path}.phase must be non-negative")
        if len(self.parent_lane_ids) != len(set(self.parent_lane_ids)):
            problems.append(f"{path}.parent_lane_ids must be unique")
        return problems

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "endpoint_id": self.endpoint_id,
            "question": self.question.to_dict(), "role": self.role.value,
            "phase": self.phase, "required": self.required,
            "parent_lane_ids": list(self.parent_lane_ids), "blind_group": self.blind_group,
        }


@dataclass(frozen=True)
class SwarmBudget:
    max_requests: int
    max_parallel: int = 1
    max_failures: int = 0
    max_cost_units: float | None = None

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.max_requests <= 0 or self.max_parallel <= 0:
            problems.append("swarm request and parallel limits must be positive")
        if self.max_failures < 0:
            problems.append("swarm max_failures must be non-negative")
        if self.max_cost_units is not None and (
            not isfinite(self.max_cost_units) or self.max_cost_units <= 0
        ):
            problems.append("swarm max_cost_units must be positive or null")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_requests": self.max_requests, "max_parallel": self.max_parallel,
            "max_failures": self.max_failures, "max_cost_units": self.max_cost_units,
        }


@dataclass(frozen=True)
class SwarmPlan:
    id: str
    pattern: SwarmPattern
    endpoints: tuple[ModelEndpoint, ...]
    lanes: tuple[SwarmLane, ...]
    budget: SwarmBudget
    question_space_digest: str
    random_seed: int

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def endpoint_map(self) -> dict[str, ModelEndpoint]:
        return {item.id: item for item in self.endpoints}

    def validate(self) -> list[str]:
        problems = self.budget.validate()
        if not ID_RE.fullmatch(self.id):
            problems.append("swarm plan id must be namespaced")
        endpoint_ids = [item.id for item in self.endpoints]
        lane_ids = [item.id for item in self.lanes]
        if not self.endpoints or len(endpoint_ids) != len(set(endpoint_ids)):
            problems.append("swarm endpoints must be nonempty and unique")
        if not self.lanes or len(lane_ids) != len(set(lane_ids)):
            problems.append("swarm lanes must be nonempty and unique")
        if len(self.lanes) > self.budget.max_requests:
            problems.append("swarm lanes exceed max_requests")
        known = set(endpoint_ids)
        for index, endpoint in enumerate(self.endpoints):
            problems.extend(endpoint.validate(f"endpoints[{index}]"))
        for index, lane in enumerate(self.lanes):
            problems.extend(lane.validate(f"lanes[{index}]"))
            if lane.endpoint_id not in known:
                problems.append(f"lanes[{index}] references unknown endpoint")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_swarm_model_version": PROPOSAL_SWARM_MODEL_VERSION,
            "id": self.id, "pattern": self.pattern.value,
            "endpoints": [item.to_dict() for item in self.endpoints],
            "lanes": [item.to_dict() for item in self.lanes],
            "budget": self.budget.to_dict(),
            "question_space_digest": self.question_space_digest,
            "random_seed": self.random_seed,
        }


class SwarmPlanner:
    """Compile selected questions and model endpoints into explicit bounded lanes."""

    def plan(
        self, *, plan_id: str, pattern: SwarmPattern, endpoints: Sequence[ModelEndpoint],
        questions: Sequence[QuestionVariant], budget: SwarmBudget,
        question_space_digest: str, random_seed: int = 0,
    ) -> SwarmPlan:
        if not endpoints or not questions:
            raise ValueError("swarm planning requires endpoints and questions")
        lanes: list[SwarmLane] = []

        def add(endpoint: ModelEndpoint, question: QuestionVariant, role: LaneRole, suffix: str) -> None:
            raw = {
                "plan": plan_id, "endpoint": endpoint.id, "question": question.digest,
                "role": role.value, "suffix": suffix,
            }
            lane_id = "swarm.lane." + sha256_digest(raw).removeprefix("sha256:")[:24]
            lanes.append(SwarmLane(lane_id, endpoint.id, question, role, blind_group=suffix))

        if pattern == SwarmPattern.CROSS_MODEL:
            for question in questions:
                for endpoint in endpoints:
                    add(endpoint, question, LaneRole.PROPOSER, "cross-model")
        elif pattern == SwarmPattern.BLIND_FULL_HYBRID:
            exposures = (
                (ContextExposure.NONE, LaneRole.BLIND_PROPOSER, "blind"),
                (ContextExposure.HYBRID, LaneRole.INFORMED_PROPOSER, "hybrid"),
                (ContextExposure.FULL, LaneRole.INFORMED_PROPOSER, "full"),
            )
            for index, question in enumerate(questions):
                for offset, (exposure, role, label) in enumerate(exposures):
                    add(endpoints[(index + offset) % len(endpoints)], question.with_exposure(exposure), role, label)
        elif pattern == SwarmPattern.PAIRED_OPPOSITION:
            for index, question in enumerate(questions):
                endpoint = endpoints[index % len(endpoints)]
                add(endpoint, question, LaneRole.PROPOSER, "proposal")
                add(endpoints[(index + 1) % len(endpoints)], question, LaneRole.CRITIC, "opposition")
        else:
            for index, question in enumerate(questions):
                add(endpoints[index % len(endpoints)], question, LaneRole.PROPOSER, pattern.value)
        lanes = lanes[: budget.max_requests]
        plan = SwarmPlan(
            plan_id, pattern, tuple(endpoints), tuple(lanes), budget,
            question_space_digest, random_seed,
        )
        problems = plan.validate()
        if problems:
            raise ValueError("invalid swarm plan: " + "; ".join(problems))
        return plan


@dataclass(frozen=True)
class SwarmLaneReceipt:
    lane_id: str
    request_digest: str
    response_digest: str
    status: str
    proposal_ids: tuple[str, ...] = ()
    error: str = ""
    cost_units: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id, "request_digest": self.request_digest,
            "response_digest": self.response_digest, "status": self.status,
            "proposal_ids": list(self.proposal_ids), "error": self.error,
            "cost_units": self.cost_units,
        }


@dataclass(frozen=True)
class SwarmRunReceipt:
    id: str
    plan_digest: str
    context_digest: str
    lane_receipts: tuple[SwarmLaneReceipt, ...]
    proposals: tuple[ProposalArtifact, ...]
    duplicate_proposals: tuple[tuple[str, str], ...]
    attempted_requests: int
    failures: int
    cost_units: float

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_swarm_model_version": PROPOSAL_SWARM_MODEL_VERSION,
            "id": self.id, "plan_digest": self.plan_digest,
            "context_digest": self.context_digest,
            "lane_receipts": [item.to_dict() for item in self.lane_receipts],
            "proposals": [item.to_dict() for item in self.proposals],
            "duplicate_proposals": [
                {"duplicate": duplicate, "retained": retained}
                for duplicate, retained in self.duplicate_proposals
            ],
            "attempted_requests": self.attempted_requests,
            "failures": self.failures, "cost_units": self.cost_units,
        }


class ProposalSwarmEngine:
    """Execute bounded proposal lanes through registered model adapters."""

    @staticmethod
    def _request(lane: SwarmLane, endpoint: ModelEndpoint, context: ContextBundle) -> LLMRequest:
        projection = context.project(lane.question.context_exposure)
        role_addendum = {
            LaneRole.CRITIC: "Attack the proposal space; prefer falsification and omitted risks.",
            LaneRole.JUDGE: "Judge supplied proposals; do not generate a replacement unless asked.",
            LaneRole.SYNTHESIZER: "Synthesize only non-duplicate compatible ideas.",
        }.get(lane.role, "Generate one independently useful proposal.")
        contract = (
            "Return JSON with kind, title, rationale, hypothesis, target_ref, payload, "
            "confidence, uncertainty, evidence_refs, parent_proposal_ids, and risk_flags. "
            "Confidence is a self-assessment, not evidence or approval."
        )
        user_parts = [lane.question.question, lane.question.response_instruction, role_addendum, contract]
        if projection.text:
            user_parts.insert(0, projection.text)
        request_id = "llm.request." + sha256_digest(
            {"lane": lane.digest, "endpoint": endpoint.to_dict(), "context": projection.digest}
        ).removeprefix("sha256:")[:24]
        return LLMRequest(
            request_id, endpoint,
            "\n\n".join(item for item in (endpoint.system_prefix, lane.question.system_directive) if item),
            "\n\n".join(user_parts), PROPOSAL_RESPONSE_SCHEMA,
            metadata=(("lane_id", lane.id), ("context_projection_digest", projection.digest)),
        )

    def run(
        self, plan: SwarmPlan, context: ContextBundle,
        adapters: Mapping[str, LanguageModelAdapter],
    ) -> SwarmRunReceipt:
        problems = (*plan.validate(), *context.validate())
        if problems:
            raise ValueError("invalid swarm execution: " + "; ".join(problems))
        endpoint_map = plan.endpoint_map
        receipts: list[SwarmLaneReceipt] = []
        proposals: list[ProposalArtifact] = []
        failures = 0
        cost = 0.0
        attempted = 0
        lanes_by_phase: dict[int, list[SwarmLane]] = defaultdict(list)
        for lane in plan.lanes:
            lanes_by_phase[lane.phase].append(lane)

        def execute(lane: SwarmLane) -> tuple[SwarmLane, LLMRequest, LLMResponse]:
            endpoint = endpoint_map[lane.endpoint_id]
            request = self._request(lane, endpoint, context)
            adapter = adapters.get(endpoint.adapter_id)
            if adapter is None:
                return lane, request, LLMResponse(
                    request.id, endpoint.adapter_id, endpoint.model, "",
                    error="adapter not registered",
                )
            started = monotonic()
            try:
                response = adapter.complete(request)
            except Exception as exc:  # adapters are an external failure boundary
                response = LLMResponse(
                    request.id, endpoint.adapter_id, endpoint.model, "",
                    duration_seconds=monotonic() - started,
                    error=f"adapter exception: {type(exc).__name__}: {exc}",
                )
            return lane, request, response

        stop = False
        for phase in sorted(lanes_by_phase):
            phase_lanes = lanes_by_phase[phase]
            for start in range(0, len(phase_lanes), plan.budget.max_parallel):
                batch: list[SwarmLane] = []
                for lane in phase_lanes[start : start + plan.budget.max_parallel]:
                    endpoint = endpoint_map[lane.endpoint_id]
                    if attempted >= plan.budget.max_requests:
                        stop = True
                        break
                    if plan.budget.max_cost_units is not None and (
                        cost + endpoint.cost_units_per_request > plan.budget.max_cost_units
                    ):
                        stop = True
                        break
                    attempted += 1
                    cost += endpoint.cost_units_per_request
                    batch.append(lane)
                if not batch:
                    break
                with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                    futures = {pool.submit(execute, lane): lane for lane in batch}
                    results = [future.result() for future in as_completed(futures)]
                for lane, request, response in sorted(results, key=lambda item: item[0].id):
                    endpoint = endpoint_map[lane.endpoint_id]
                    status = "succeeded"
                    error = response.error
                    lane_proposals: tuple[ProposalArtifact, ...] = ()
                    response_problems = response.validate()
                    if response_problems:
                        error = "; ".join(response_problems)
                    if error:
                        status = "failed"
                    else:
                        try:
                            lane_proposals = parse_proposals(
                                response.raw_text, proposer_id=lane.id,
                                question_variant_id=lane.question.id,
                                model_id=endpoint.model,
                            )
                        except ValueError as exc:
                            status = "malformed"
                            error = str(exc)
                    if status != "succeeded":
                        failures += 1
                    proposals.extend(lane_proposals)
                    receipts.append(SwarmLaneReceipt(
                        lane.id, request.digest, response.digest, status,
                        tuple(item.id for item in lane_proposals), error,
                        endpoint.cost_units_per_request,
                    ))
                    if lane.required and status != "succeeded":
                        stop = True
                if failures > plan.budget.max_failures:
                    stop = True
                if stop:
                    break
            if stop:
                break
        retained, duplicates = deduplicate_proposals(proposals)
        run_id = "swarm.run." + sha256_digest(
            {"plan": plan.digest, "context": context.digest, "receipts": [item.to_dict() for item in receipts]}
        ).removeprefix("sha256:")[:24]
        return SwarmRunReceipt(
            run_id, plan.digest, context.digest, tuple(receipts), retained,
            duplicates, attempted, failures, cost,
        )


@dataclass(frozen=True)
class GateDecision:
    proposal_id: str
    gate_id: str
    admitted: bool
    reasons: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


class ProposalGate(Protocol):
    gate_id: str

    def evaluate(self, proposal: ProposalArtifact) -> GateDecision: ...


@dataclass(frozen=True)
class ProposalJudgment:
    id: str
    proposal_id: str
    judge_id: str
    scores: Mapping[str, float]
    verdict: str
    rationale: str
    confidence: float = 0.5
    independent_context: bool = True

    def validate(self) -> list[str]:
        problems: list[str] = []
        for value in (self.id, self.proposal_id, self.judge_id):
            if not ID_RE.fullmatch(value):
                problems.append("judgment ids must be namespaced")
        if self.verdict not in ("support", "oppose", "review", "abstain", "error"):
            problems.append("judgment verdict is unknown")
        if not self.rationale.strip():
            problems.append("judgment rationale is required")
        if not isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            problems.append("judgment confidence must be between zero and one")
        if any(not isfinite(value) or not 0 <= value <= 1 for value in self.scores.values()):
            problems.append("judgment scores must be between zero and one")
        return problems


@dataclass(frozen=True)
class ProposalPanelReport:
    proposal_id: str
    aggregate_scores: tuple[tuple[str, float], ...]
    disagreement: tuple[tuple[str, float], ...]
    support: int
    oppose: int
    review: int
    abstain: int
    independent_judges: int
    judgment_ids: tuple[str, ...]



def aggregate_judgments(judgments: Sequence[ProposalJudgment]) -> ProposalPanelReport:
    if not judgments:
        raise ValueError("panel requires judgments")
    proposal_ids = {item.proposal_id for item in judgments}
    if len(proposal_ids) != 1:
        raise ValueError("panel judgments must concern one proposal")
    problems = [problem for item in judgments for problem in item.validate()]
    if problems:
        raise ValueError("invalid panel: " + "; ".join(problems))
    values: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for judgment in judgments:
        # Model confidence is capped so confident rhetoric cannot dominate evidence.
        weight = min(0.75, max(0.10, judgment.confidence))
        for criterion, score in judgment.scores.items():
            values[criterion].append((score, weight))
    aggregates: list[tuple[str, float]] = []
    disagreements: list[tuple[str, float]] = []
    for criterion, observations in sorted(values.items()):
        weight_sum = sum(weight for _, weight in observations)
        mean = sum(score * weight for score, weight in observations) / weight_sum
        variance = sum(weight * (score - mean) ** 2 for score, weight in observations) / weight_sum
        aggregates.append((criterion, mean))
        disagreements.append((criterion, sqrt(variance)))
    counts = defaultdict(int)
    for judgment in judgments:
        counts[judgment.verdict] += 1
    return ProposalPanelReport(
        next(iter(proposal_ids)), tuple(aggregates), tuple(disagreements),
        counts["support"], counts["oppose"], counts["review"], counts["abstain"],
        len({item.judge_id for item in judgments if item.independent_context}),
        tuple(item.id for item in judgments),
    )



def pareto_proposal_ids(
    reports: Sequence[ProposalPanelReport], objectives: Mapping[str, str],
) -> tuple[str, ...]:
    if any(direction not in ("maximize", "minimize") for direction in objectives.values()):
        raise ValueError("objective directions must be maximize or minimize")
    scores = {report.proposal_id: dict(report.aggregate_scores) for report in reports}
    frontier: list[str] = []
    for candidate, candidate_scores in scores.items():
        dominated = False
        for other, other_scores in scores.items():
            if candidate == other:
                continue
            weakly_better = True
            strictly_better = False
            for metric, direction in objectives.items():
                left = candidate_scores.get(metric)
                right = other_scores.get(metric)
                if left is None or right is None:
                    weakly_better = False
                    break
                if direction == "maximize":
                    weakly_better &= right >= left
                    strictly_better |= right > left
                else:
                    weakly_better &= right <= left
                    strictly_better |= right < left
            if weakly_better and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return tuple(sorted(frontier))


@dataclass(frozen=True)
class ProposalCampaignPolicy:
    max_rounds: int
    questions_per_round: int
    novelty_patience: int = 2
    exploration: float = 1.0
    protected_random_fraction: float = 0.20

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.max_rounds <= 0 or self.questions_per_round <= 0:
            problems.append("campaign limits must be positive")
        if self.novelty_patience <= 0:
            problems.append("novelty_patience must be positive")
        if not isfinite(self.exploration) or self.exploration < 0:
            problems.append("exploration must be non-negative")
        if not 0 <= self.protected_random_fraction <= 1:
            problems.append("protected_random_fraction must be between zero and one")
        return problems


@dataclass(frozen=True)
class ProposalCampaignState:
    round_index: int = 0
    question_values: QuestionValueModel = field(default_factory=QuestionValueModel)
    proposal_ids: tuple[str, ...] = ()
    no_novel_rounds: int = 0

    def next_questions(
        self, space: QuestionSpace, policy: ProposalCampaignPolicy, *, seed: int,
        model_endpoint_id: str = "",
    ) -> tuple[QuestionVariant, ...]:
        sampler = AdaptiveQuestionSampler(
            exploration=policy.exploration,
            random_fraction=policy.protected_random_fraction,
        )
        return sampler.sample(
            space, self.question_values, limit=policy.questions_per_round,
            seed=seed + self.round_index, model_endpoint_id=model_endpoint_id,
        )

    def observe(
        self, question: QuestionVariant, model_endpoint_id: str, reward: float,
        new_proposal_ids: Sequence[str],
    ) -> ProposalCampaignState:
        known = set(self.proposal_ids)
        additions = tuple(item for item in new_proposal_ids if item not in known)
        merged = tuple(dict.fromkeys((*self.proposal_ids, *additions)))
        return ProposalCampaignState(
            round_index=self.round_index + 1,
            question_values=self.question_values.update(question, model_endpoint_id, reward),
            proposal_ids=merged,
            no_novel_rounds=0 if additions else self.no_novel_rounds + 1,
        )

    def should_stop(self, policy: ProposalCampaignPolicy) -> bool:
        return self.round_index >= policy.max_rounds or self.no_novel_rounds >= policy.novelty_patience


__all__ = [
    "PROPOSAL_SWARM_MODEL_VERSION", "GateDecision", "LLMRequest", "LLMResponse",
    "LaneRole", "LanguageModelAdapter", "ModelEndpoint", "ProposalCampaignPolicy",
    "ProposalCampaignState", "ProposalGate", "ProposalJudgment", "ProposalPanelReport",
    "ProposalSwarmEngine", "RecordedLanguageModelAdapter", "SwarmBudget", "SwarmLane",
    "SwarmLaneReceipt", "SwarmPattern", "SwarmPlan", "SwarmPlanner", "SwarmRunReceipt",
    "aggregate_judgments", "pareto_proposal_ids",
]
