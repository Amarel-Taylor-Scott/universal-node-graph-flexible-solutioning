"""Kaggle-specific proposal portfolios, context, and evidence policies.

This module does not scrape competition data or submit predictions.  It binds a
Kaggle task description, rules, validation assumptions, resource constraints,
and scarce submission budget to the generic proposal-swarm layer.  Public
leaderboard observations are never the default optimization oracle.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE, sha256_digest
from solutiongraph.proposal_space import (
    AdaptiveQuestionSampler,
    ContextBundle,
    ContextExposure,
    ProposalKind,
    QuestionSpace,
    QuestionValueModel,
    QuestionVariant,
    default_kaggle_question_space,
)
from solutiongraph.proposal_swarm import (
    ModelEndpoint,
    SwarmBudget,
    SwarmPattern,
    SwarmPlan,
    SwarmPlanner,
)

KAGGLE_SWARM_MODEL_VERSION = "0.1"


class CompetitionFormat(str, Enum):
    CLASSIC = "kaggle.format.classic"
    CODE = "kaggle.format.code"
    TWO_STAGE = "kaggle.format.two-stage"
    SIMULATION = "kaggle.format.simulation"
    HACKATHON = "kaggle.format.hackathon"
    UNKNOWN = "kaggle.format.unknown"


class MetricDirection(str, Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


@dataclass(frozen=True)
class KaggleCompetitionProfile:
    id: str
    competition_slug: str
    task_statement: str
    metric_name: str
    metric_direction: MetricDirection
    competition_format: CompetitionFormat = CompetitionFormat.UNKNOWN
    target_columns: tuple[str, ...] = ()
    id_columns: tuple[str, ...] = ()
    group_columns: tuple[str, ...] = ()
    time_columns: tuple[str, ...] = ()
    code_competition: bool = False
    internet_allowed: bool | None = None
    external_data_allowed: bool | None = None
    maximum_submissions_per_day: int | None = None
    runtime_limit_seconds: float | None = None
    cpu_limit: str = ""
    gpu_limit: str = ""
    memory_limit: str = ""
    rules_digest: str = ""
    train_digest: str = ""
    test_digest: str = ""
    sample_submission_digest: str = ""
    tags: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "kaggle_profile") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be namespaced")
        if not self.competition_slug.strip() or not self.task_statement.strip():
            problems.append(f"{path} requires competition_slug and task_statement")
        if not self.metric_name.strip():
            problems.append(f"{path}.metric_name must not be empty")
        for label in ("target_columns", "id_columns", "group_columns", "time_columns", "tags"):
            values = getattr(self, label)
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
        if self.maximum_submissions_per_day is not None and self.maximum_submissions_per_day <= 0:
            problems.append(f"{path}.maximum_submissions_per_day must be positive or null")
        if self.runtime_limit_seconds is not None and (
            not isfinite(self.runtime_limit_seconds) or self.runtime_limit_seconds <= 0
        ):
            problems.append(f"{path}.runtime_limit_seconds must be positive or null")
        for label in (
            "rules_digest", "train_digest", "test_digest", "sample_submission_digest"
        ):
            value = getattr(self, label)
            if value and not DIGEST_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be empty or a sha256 digest")
        if self.code_competition and self.competition_format not in (
            CompetitionFormat.CODE, CompetitionFormat.TWO_STAGE, CompetitionFormat.UNKNOWN
        ):
            problems.append(f"{path}.code_competition conflicts with competition_format")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "kaggle_swarm_model_version": KAGGLE_SWARM_MODEL_VERSION,
            "id": self.id, "competition_slug": self.competition_slug,
            "task_statement": self.task_statement, "metric_name": self.metric_name,
            "metric_direction": self.metric_direction.value,
            "competition_format": self.competition_format.value,
            "target_columns": list(self.target_columns), "id_columns": list(self.id_columns),
            "group_columns": list(self.group_columns), "time_columns": list(self.time_columns),
            "code_competition": self.code_competition,
            "internet_allowed": self.internet_allowed,
            "external_data_allowed": self.external_data_allowed,
            "maximum_submissions_per_day": self.maximum_submissions_per_day,
            "runtime_limit_seconds": self.runtime_limit_seconds,
            "cpu_limit": self.cpu_limit, "gpu_limit": self.gpu_limit,
            "memory_limit": self.memory_limit, "rules_digest": self.rules_digest,
            "train_digest": self.train_digest, "test_digest": self.test_digest,
            "sample_submission_digest": self.sample_submission_digest,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class KaggleExperimentPolicy:
    require_local_cross_validation: bool = True
    require_out_of_fold_predictions: bool = True
    require_reproducible_seed: bool = True
    require_private_holdout: bool = True
    forbid_test_target_access: bool = True
    public_leaderboard_weight: float = 0.0
    maximum_public_leaderboard_weight: float = 0.10
    maximum_submission_budget: int = 20
    minimum_repetitions_for_noisy_routes: int = 2
    maximum_llm_package_nominations_per_round: int = 8

    def validate(self, path: str = "kaggle_policy") -> list[str]:
        problems: list[str] = []
        if not isfinite(self.public_leaderboard_weight) or self.public_leaderboard_weight < 0:
            problems.append(f"{path}.public_leaderboard_weight must be non-negative")
        if not isfinite(self.maximum_public_leaderboard_weight) or not (
            0 <= self.maximum_public_leaderboard_weight <= 0.10
        ):
            problems.append(f"{path}.maximum_public_leaderboard_weight must be between 0 and 0.10")
        if self.public_leaderboard_weight > self.maximum_public_leaderboard_weight:
            problems.append(f"{path}.public_leaderboard_weight exceeds the permitted cap")
        if self.maximum_submission_budget <= 0:
            problems.append(f"{path}.maximum_submission_budget must be positive")
        if self.minimum_repetitions_for_noisy_routes <= 0:
            problems.append(f"{path}.minimum_repetitions_for_noisy_routes must be positive")
        if self.maximum_llm_package_nominations_per_round < 0:
            problems.append(f"{path}.maximum_llm_package_nominations_per_round must be non-negative")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "require_local_cross_validation": self.require_local_cross_validation,
            "require_out_of_fold_predictions": self.require_out_of_fold_predictions,
            "require_reproducible_seed": self.require_reproducible_seed,
            "require_private_holdout": self.require_private_holdout,
            "forbid_test_target_access": self.forbid_test_target_access,
            "public_leaderboard_weight": self.public_leaderboard_weight,
            "maximum_public_leaderboard_weight": self.maximum_public_leaderboard_weight,
            "maximum_submission_budget": self.maximum_submission_budget,
            "minimum_repetitions_for_noisy_routes": self.minimum_repetitions_for_noisy_routes,
            "maximum_llm_package_nominations_per_round": self.maximum_llm_package_nominations_per_round,
        }


@dataclass(frozen=True)
class SubmissionBudget:
    maximum_total: int
    used: int = 0
    reserved: int = 0

    @property
    def remaining(self) -> int:
        return self.maximum_total - self.used - self.reserved

    def reserve(self, count: int = 1) -> SubmissionBudget:
        if count <= 0 or count > self.remaining:
            raise ValueError("submission reservation exceeds remaining budget")
        return SubmissionBudget(self.maximum_total, self.used, self.reserved + count)

    def consume(self, count: int = 1) -> SubmissionBudget:
        if count <= 0 or count > self.reserved:
            raise ValueError("submission consumption exceeds reserved budget")
        return SubmissionBudget(self.maximum_total, self.used + count, self.reserved - count)

    def release(self, count: int = 1) -> SubmissionBudget:
        if count <= 0 or count > self.reserved:
            raise ValueError("submission release exceeds reserved budget")
        return SubmissionBudget(self.maximum_total, self.used, self.reserved - count)


@dataclass(frozen=True)
class KaggleExperimentObservation:
    proposal_id: str
    question_variant_id: str
    model_endpoint_id: str
    compiler_valid: bool
    executable: bool
    accepted_by_local_oracle: bool
    normalized_local_cv_lift: float = 0.0
    normalized_holdout_lift: float | None = None
    normalized_public_leaderboard_lift: float | None = None
    robustness_score: float = 0.0
    novelty_score: float = 0.0
    runtime_cost_ratio: float = 1.0
    monetary_cost_units: float = 0.0
    failure_rate: float = 0.0
    evidence_refs: tuple[str, ...] = ()

    def validate(self, path: str = "kaggle_observation") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("proposal_id", self.proposal_id),
            ("question_variant_id", self.question_variant_id),
            ("model_endpoint_id", self.model_endpoint_id),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be namespaced")
        numeric = (
            self.normalized_local_cv_lift,
            self.robustness_score,
            self.novelty_score,
            self.runtime_cost_ratio,
            self.monetary_cost_units,
            self.failure_rate,
        )
        if any(not isfinite(value) for value in numeric):
            problems.append(f"{path} numeric observations must be finite")
        for value in (self.normalized_holdout_lift, self.normalized_public_leaderboard_lift):
            if value is not None and not isfinite(value):
                problems.append(f"{path} optional lifts must be finite or null")
        if not 0 <= self.robustness_score <= 1 or not 0 <= self.novelty_score <= 1:
            problems.append(f"{path} robustness and novelty must be between zero and one")
        if self.runtime_cost_ratio < 0 or self.monetary_cost_units < 0:
            problems.append(f"{path} cost values must be non-negative")
        if not 0 <= self.failure_rate <= 1:
            problems.append(f"{path}.failure_rate must be between zero and one")
        return problems


@dataclass(frozen=True)
class KaggleRewardPolicy:
    compiler_valid_reward: float = 0.10
    executable_reward: float = 0.10
    local_cv_weight: float = 0.35
    holdout_weight: float = 0.30
    robustness_weight: float = 0.10
    novelty_weight: float = 0.05
    public_leaderboard_weight: float = 0.0
    runtime_penalty_weight: float = 0.05
    failure_penalty_weight: float = 0.20
    cost_penalty_weight: float = 0.01

    def validate(self, policy: KaggleExperimentPolicy | None = None) -> list[str]:
        problems: list[str] = []
        values = tuple(self.__dict__.values())
        if any(not isfinite(value) or value < 0 for value in values):
            problems.append("Kaggle reward weights must be finite and non-negative")
        if policy is not None and self.public_leaderboard_weight > policy.maximum_public_leaderboard_weight:
            problems.append("reward public-leaderboard weight exceeds policy cap")
        return problems

    def reward(
        self, observation: KaggleExperimentObservation,
        policy: KaggleExperimentPolicy | None = None,
    ) -> float:
        problems = (*observation.validate(), *self.validate(policy))
        if problems:
            raise ValueError("invalid Kaggle reward input: " + "; ".join(problems))
        holdout = observation.normalized_holdout_lift
        if holdout is None:
            holdout = 0.0
        public = observation.normalized_public_leaderboard_lift
        if public is None:
            public = 0.0
        reward = (
            self.compiler_valid_reward * float(observation.compiler_valid)
            + self.executable_reward * float(observation.executable)
            + self.local_cv_weight * observation.normalized_local_cv_lift
            + self.holdout_weight * holdout
            + self.robustness_weight * observation.robustness_score
            + self.novelty_weight * observation.novelty_score
            + self.public_leaderboard_weight * public
            - self.runtime_penalty_weight * max(0.0, observation.runtime_cost_ratio - 1.0)
            - self.failure_penalty_weight * observation.failure_rate
            - self.cost_penalty_weight * observation.monetary_cost_units
        )
        if not observation.accepted_by_local_oracle:
            reward -= 0.25
        return reward


@dataclass(frozen=True)
class KaggleSwarmPreset:
    id: str
    pattern: SwarmPattern
    proposal_kinds: tuple[ProposalKind, ...]
    focus_terms: tuple[str, ...]
    question_count: int
    max_requests: int
    max_parallel: int = 1
    max_failures: int = 0
    description: str = ""

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("Kaggle preset id must be namespaced")
        if not self.proposal_kinds or not self.focus_terms:
            problems.append("Kaggle preset requires proposal kinds and focus terms")
        if self.question_count <= 0 or self.max_requests <= 0 or self.max_parallel <= 0:
            problems.append("Kaggle preset limits must be positive")
        if self.max_failures < 0:
            problems.append("Kaggle preset max_failures must be non-negative")
        return problems


KAGGLE_SWARM_PRESETS: tuple[KaggleSwarmPreset, ...] = (
    KaggleSwarmPreset(
        "kaggle-preset.task-reframe", SwarmPattern.BLIND_FULL_HYBRID,
        (ProposalKind.TASK_REFRAME, ProposalKind.GRAPH, ProposalKind.DIAGNOSTIC),
        ("task framing", "metric", "competition rules"), 8, 24, 4, 4,
        "Blind, partially informed, and full-context task reframing.",
    ),
    KaggleSwarmPreset(
        "kaggle-preset.data-audit", SwarmPattern.CROSS_MODEL,
        (ProposalKind.DIAGNOSTIC, ProposalKind.FEATURE, ProposalKind.VALIDATION),
        ("schema", "columns", "missingness", "outliers", "duplicates", "cleaning"),
        12, 48, 4, 6, "Column, data-quality, and representation audit.",
    ),
    KaggleSwarmPreset(
        "kaggle-preset.validation-red-team", SwarmPattern.PAIRED_OPPOSITION,
        (ProposalKind.VALIDATION, ProposalKind.DIAGNOSTIC, ProposalKind.STOP),
        ("cross-validation", "leakage", "train-test drift", "public/private leaderboard risk"),
        10, 20, 4, 4, "Adversarial review of validation and leakage assumptions.",
    ),
    KaggleSwarmPreset(
        "kaggle-preset.feature-factory", SwarmPattern.CROSS_MODEL,
        (ProposalKind.FEATURE, ProposalKind.SUBGRAPH, ProposalKind.MUTATION),
        ("feature engineering", "interactions", "aggregations", "unsupervised features"),
        16, 64, 4, 8, "Diverse feature and representation hypotheses with ablations.",
    ),
    KaggleSwarmPreset(
        "kaggle-preset.route-search", SwarmPattern.CROSS_MODEL,
        (ProposalKind.ROUTE, ProposalKind.NODE, ProposalKind.REPLACEMENT, ProposalKind.PARAMETER_SPACE),
        ("model family", "route topology", "node replacement", "hyperparameters"),
        16, 64, 4, 8, "Model, route, node, and parameter-space proposals.",
    ),
    KaggleSwarmPreset(
        "kaggle-preset.ensemble", SwarmPattern.PAIRED_OPPOSITION,
        (ProposalKind.ENSEMBLE, ProposalKind.VALIDATION, ProposalKind.DIAGNOSTIC),
        ("ensembling", "stacking", "calibration", "uncertainty"),
        10, 20, 4, 4, "Diversity-aware ensemble and calibration proposals.",
    ),
    KaggleSwarmPreset(
        "kaggle-preset.package-scout", SwarmPattern.INDEPENDENT,
        (ProposalKind.PACKAGE, ProposalKind.NODE, ProposalKind.RESEARCH),
        ("packages", "model family", "feature engineering", "runtime"),
        8, 8, 2, 2, "Package nominations with provenance, tests, alternatives, and fallback.",
    ),
    KaggleSwarmPreset(
        "kaggle-preset.efficiency", SwarmPattern.PAIRED_OPPOSITION,
        (ProposalKind.RESOURCE, ProposalKind.REPLACEMENT, ProposalKind.STOP),
        ("runtime", "memory", "CPU", "GPU", "hardware"),
        8, 16, 4, 3, "Cost, memory, latency, and hardware optimization.",
    ),
    KaggleSwarmPreset(
        "kaggle-preset.minimalist", SwarmPattern.BLIND_FULL_HYBRID,
        (ProposalKind.STOP, ProposalKind.REPLACEMENT, ProposalKind.DIAGNOSTIC),
        ("graph simplification", "failure analysis", "reproducibility"),
        6, 18, 3, 3, "Find deletions and simpler falsifiable alternatives.",
    ),
)


def get_kaggle_preset(preset_id: str) -> KaggleSwarmPreset:
    try:
        return next(item for item in KAGGLE_SWARM_PRESETS if item.id == preset_id)
    except StopIteration as exc:
        raise ValueError(f"unknown Kaggle swarm preset {preset_id!r}") from exc


@dataclass(frozen=True)
class KaggleExperimentPortfolio:
    id: str
    competition_profile_digest: str
    experiment_policy: KaggleExperimentPolicy
    deterministic_route_trials: int
    deterministic_mutation_trials: int
    llm_swarm_plan: SwarmPlan
    submission_budget: SubmissionBudget
    protected_blind_fraction: float = 0.20

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems = self.experiment_policy.validate()
        if not ID_RE.fullmatch(self.id):
            problems.append("Kaggle portfolio id must be namespaced")
        if not DIGEST_RE.fullmatch(self.competition_profile_digest):
            problems.append("Kaggle portfolio profile digest must be sha256")
        if self.deterministic_route_trials < 0 or self.deterministic_mutation_trials < 0:
            problems.append("Kaggle deterministic trial counts must be non-negative")
        if not 0 <= self.protected_blind_fraction <= 1:
            problems.append("Kaggle protected_blind_fraction must be between zero and one")
        problems.extend(self.llm_swarm_plan.validate())
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "kaggle_swarm_model_version": KAGGLE_SWARM_MODEL_VERSION,
            "id": self.id, "competition_profile_digest": self.competition_profile_digest,
            "experiment_policy": self.experiment_policy.to_dict(),
            "deterministic_route_trials": self.deterministic_route_trials,
            "deterministic_mutation_trials": self.deterministic_mutation_trials,
            "llm_swarm_plan_digest": self.llm_swarm_plan.digest,
            "submission_budget": {
                "maximum_total": self.submission_budget.maximum_total,
                "used": self.submission_budget.used,
                "reserved": self.submission_budget.reserved,
            },
            "protected_blind_fraction": self.protected_blind_fraction,
        }


class KaggleCampaignPlanner:
    """Build mixed deterministic and LLM proposal portfolios for one competition."""

    def __init__(self, swarm_planner: SwarmPlanner | None = None) -> None:
        self.swarm_planner = swarm_planner or SwarmPlanner()

    @staticmethod
    def context(
        profile: KaggleCompetitionProfile, *, rules: str = "", schema: str = "",
        data_profile: str = "", column_profile: str = "", blueprint: str = "",
        graph_summary: str = "", graph_full: str = "", route_summary: str = "",
        evidence_summary: str = "", failures: str = "", champion: str = "",
        alternatives: str = "", package_catalog: str = "", research_summary: str = "",
        code_summary: str = "", constraints: str = "", hidden_holdout: str = "",
    ) -> ContextBundle:
        task = (
            f"Competition: {profile.competition_slug}\n"
            f"Task: {profile.task_statement}\n"
            f"Metric: {profile.metric_name} ({profile.metric_direction.value})\n"
            f"Format: {profile.competition_format.value}"
        )
        resource_constraints = (
            f"code_competition={profile.code_competition}; "
            f"internet_allowed={profile.internet_allowed}; "
            f"external_data_allowed={profile.external_data_allowed}; "
            f"runtime_limit_seconds={profile.runtime_limit_seconds}; "
            f"cpu={profile.cpu_limit}; gpu={profile.gpu_limit}; memory={profile.memory_limit}"
        )
        merged_constraints = "\n".join(item for item in (resource_constraints, constraints) if item)
        sections = tuple(
            (key, value)
            for key, value in (
                ("task", task), ("rules", rules), ("schema", schema),
                ("data_profile", data_profile), ("column_profile", column_profile),
                ("blueprint", blueprint), ("graph_summary", graph_summary),
                ("graph_full", graph_full), ("route_summary", route_summary),
                ("evidence_summary", evidence_summary), ("failures", failures),
                ("champion", champion), ("alternatives", alternatives),
                ("package_catalog", package_catalog), ("research_summary", research_summary),
                ("code_summary", code_summary), ("constraints", merged_constraints),
            )
            if value
        )
        source_digests = tuple(
            value for value in (
                profile.rules_digest, profile.train_digest, profile.test_digest,
                profile.sample_submission_digest,
            ) if value
        )
        return ContextBundle(
            id=f"context.kaggle.{profile.competition_slug}",
            sections=sections,
            hidden_sections=(("private_holdout", hidden_holdout),) if hidden_holdout else (),
            source_digests=source_digests,
        )

    @staticmethod
    def select_questions(
        space: QuestionSpace, preset: KaggleSwarmPreset, *, seed: int,
        question_values: QuestionValueModel | None = None,
    ) -> tuple[QuestionVariant, ...]:
        problems = preset.validate()
        if problems:
            raise ValueError("invalid Kaggle preset: " + "; ".join(problems))
        values = question_values or QuestionValueModel()
        pool_size = max(4096, preset.question_count * 256)
        sampler = AdaptiveQuestionSampler(candidate_pool_size=pool_size, random_fraction=0.25)
        candidates = sampler.sample(
            space, values, limit=min(pool_size, space.count), seed=seed,
        )
        kind_set = set(preset.proposal_kinds)
        focus_terms = tuple(term.lower() for term in preset.focus_terms)
        matching = [
            item for item in candidates
            if item.proposal_kind in kind_set
            and any(term in item.focus.lower() for term in focus_terms)
        ]
        if len(matching) < preset.question_count:
            matching.extend(item for item in candidates if item.proposal_kind in kind_set and item not in matching)
        if len(matching) < preset.question_count:
            matching.extend(item for item in candidates if item not in matching)
        return tuple(matching[: preset.question_count])

    def build_portfolio(
        self, profile: KaggleCompetitionProfile, endpoints: Sequence[ModelEndpoint], *,
        preset_id: str = "kaggle-preset.task-reframe", random_seed: int = 0,
        question_space: QuestionSpace | None = None,
        question_values: QuestionValueModel | None = None,
        experiment_policy: KaggleExperimentPolicy | None = None,
        deterministic_route_trials: int = 32,
        deterministic_mutation_trials: int = 16,
    ) -> KaggleExperimentPortfolio:
        profile_problems = profile.validate()
        policy = experiment_policy or KaggleExperimentPolicy()
        problems = (*profile_problems, *policy.validate())
        if problems:
            raise ValueError("invalid Kaggle portfolio input: " + "; ".join(problems))
        preset = get_kaggle_preset(preset_id)
        space = question_space or default_kaggle_question_space()
        questions = self.select_questions(
            space, preset, seed=random_seed, question_values=question_values,
        )
        swarm = self.swarm_planner.plan(
            plan_id=f"swarm-plan.kaggle.{profile.competition_slug}.{preset_id.split('.')[-1]}",
            pattern=preset.pattern, endpoints=endpoints, questions=questions,
            budget=SwarmBudget(
                max_requests=preset.max_requests,
                max_parallel=preset.max_parallel,
                max_failures=preset.max_failures,
            ),
            question_space_digest=space.digest, random_seed=random_seed,
        )
        portfolio = KaggleExperimentPortfolio(
            id=f"kaggle-portfolio.{profile.competition_slug}.{preset_id.split('.')[-1]}",
            competition_profile_digest=profile.digest,
            experiment_policy=policy,
            deterministic_route_trials=deterministic_route_trials,
            deterministic_mutation_trials=deterministic_mutation_trials,
            llm_swarm_plan=swarm,
            submission_budget=SubmissionBudget(policy.maximum_submission_budget),
        )
        portfolio_problems = portfolio.validate()
        if portfolio_problems:
            raise ValueError("invalid Kaggle portfolio: " + "; ".join(portfolio_problems))
        return portfolio


__all__ = [
    "KAGGLE_SWARM_MODEL_VERSION", "KAGGLE_SWARM_PRESETS", "CompetitionFormat",
    "KaggleCampaignPlanner", "KaggleCompetitionProfile", "KaggleExperimentObservation",
    "KaggleExperimentPolicy", "KaggleExperimentPortfolio", "KaggleRewardPolicy",
    "KaggleSwarmPreset", "MetricDirection", "SubmissionBudget", "get_kaggle_preset",
]
