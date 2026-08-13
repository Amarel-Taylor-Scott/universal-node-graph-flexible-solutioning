"""End-to-end semantic interrogation, shadow repair, and feedback loop."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from solutiongraph.interrogation.execution import (
    STANDARD_CHECK_REGISTRY,
    CheckRegistry,
    QuestionExecutor,
)
from solutiongraph.interrogation.learning import (
    EMPTY_QUESTION_UTILITY_MEMORY,
    QuestionUtilityProvider,
)
from solutiongraph.interrogation.planning import QuestionPlanner, effort_budget
from solutiongraph.interrogation.profiling import map_semantic_fields, profile_records
from solutiongraph.interrogation.repair import RepairProposalEngine, apply_repair_shadow
from solutiongraph.interrogation.reporting import InterrogationRunReport
from solutiongraph.interrogation.verification import rebind_plan, verify_repair
from solutiongraph.model import sha256_digest
from solutiongraph.question_packs import REFERENCE_CONCEPTS, REFERENCE_QUESTION_PACKS


class InterrogationEngine:
    """Coordinate explicit layers without merging questions and executors."""

    id = "engine.semantic-interrogation"
    version = "1.0.0"

    def __init__(
        self,
        *,
        check_registry: CheckRegistry = STANDARD_CHECK_REGISTRY,
        planner: QuestionPlanner | None = None,
        executor: QuestionExecutor | None = None,
        repairer: RepairProposalEngine | None = None,
    ) -> None:
        problems = check_registry.validate()
        if problems:
            raise ValueError("invalid check registry: " + "; ".join(problems))
        self.check_registry = check_registry
        self.planner = planner or QuestionPlanner()
        self.executor = executor or QuestionExecutor()
        self.repairer = repairer or RepairProposalEngine()

    def run(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        effort: int | str = "E3",
        mapping_strategy: str = "conservative",
        planning_strategy: str = "risk-first",
        repair_strategy: str = "safe-only",
        sample_limit: int = 0,
        random_seed: int = 0,
        granted_permissions: tuple[str, ...] = (),
        context_tags: tuple[str, ...] = (),
        explicit_hints: Mapping[str, str] | None = None,
        history: QuestionUtilityProvider = EMPTY_QUESTION_UTILITY_MEMORY,
        include_review_operations: bool = False,
        strict_verification: bool = True,
        record_timing: bool = False,
        source_id: str = "source.inline-records",
    ) -> InterrogationRunReport:
        """Run the complete loop while retaining raw records only in memory."""
        portable = [dict(record) for record in records]
        profile = profile_records(
            portable,
            source_id=source_id,
            sample_limit=sample_limit,
        )
        field_map = map_semantic_fields(
            profile,
            REFERENCE_CONCEPTS,
            strategy=mapping_strategy,
            explicit_hints=explicit_hints,
        )
        budget = effort_budget(
            effort,
            granted_permissions=granted_permissions,
            random_seed=random_seed,
        )
        plan = self.planner.plan(
            profile,
            field_map,
            REFERENCE_QUESTION_PACKS,
            budget=budget,
            available_capabilities=self.check_registry.capabilities,
            history=history,
            context_tags=context_tags,
            strategy=planning_strategy,
        )
        questions = {
            question.id: question
            for pack in REFERENCE_QUESTION_PACKS
            for question in pack.questions
        }
        before_findings = self.executor.execute(
            portable,
            profile,
            field_map,
            plan,
            questions,
            self.check_registry,
            record_timing=record_timing,
        )
        proposal = self.repairer.propose(
            portable,
            before_findings,
            strategy=repair_strategy,
        )
        shadow, application = apply_repair_shadow(
            portable,
            proposal,
            include_review_operations=include_review_operations,
        )
        shadow_profile = profile_records(
            shadow,
            source_id="source.repair-shadow",
            sample_limit=sample_limit,
        )
        shadow_map = map_semantic_fields(
            shadow_profile,
            REFERENCE_CONCEPTS,
            strategy=mapping_strategy,
            explicit_hints=explicit_hints,
        )
        shadow_plan = rebind_plan(plan, shadow_profile, shadow_map)
        after_findings = self.executor.execute(
            shadow,
            shadow_profile,
            shadow_map,
            shadow_plan,
            questions,
            self.check_registry,
            record_timing=record_timing,
        )
        verification = verify_repair(
            portable,
            shadow,
            proposal,
            application,
            before_findings,
            after_findings,
            strict=strict_verification,
        )
        configuration = (
            ("config.effort-level", budget.effort_level),
            ("config.mapping-strategy", mapping_strategy),
            ("config.planning-strategy", planning_strategy),
            ("config.repair-strategy", repair_strategy),
            ("config.sample-limit", sample_limit),
            ("config.random-seed", random_seed),
            ("config.include-review-operations", include_review_operations),
            ("config.strict-verification", strict_verification),
            ("config.patch-values-redacted-in-report", True),
            ("config.check-registry-digest", self.check_registry.digest),
        )
        run_identity = sha256_digest(
            {
                "dataset_digest": profile.dataset_digest,
                "plan_digest": plan.digest,
                "application_digest": application.digest,
                "verification_digest": verification.digest,
                "configuration": dict(configuration),
            }
        ).removeprefix("sha256:")
        report = InterrogationRunReport(
            id="run.semantic-interrogation-" + run_identity[:24],
            version=self.version,
            source_profile=profile,
            semantic_field_map=field_map,
            question_plan=plan,
            before_findings=before_findings,
            repair_proposal=proposal,
            repair_application=application,
            shadow_profile=shadow_profile,
            shadow_field_map=shadow_map,
            shadow_plan=shadow_plan,
            after_findings=after_findings,
            verification=verification,
            configuration=configuration,
            claim_scope="dataset-specific-evidence",
        )
        problems = report.validate()
        if problems:
            raise ValueError("invalid interrogation report: " + "; ".join(problems))
        return report


__all__ = ["InterrogationEngine"]
