"""Pack-governed SourceLoop engine for active market investigations."""

from __future__ import annotations

from .domain import (
    ActionProposal,
    ActionStatus,
    CaseCreate,
    CaseKind,
    CaseRecord,
    CaseStatus,
    ContactRoute,
    Direction,
    FindingKind,
    FindingReviewRequest,
    FindingStatus,
    InboundEmail,
    Interaction,
    PractitionerStage,
    RegistryCheck,
    RegistryCheckCreate,
    Severity,
    utcnow,
    stable_key,
)
from .engine import SourceLoopEngine
from .investigation import (
    completion_count,
    compose_followup,
    compose_initial_message,
    critical_missing_fields,
    evaluate_findings,
    governance_snapshot,
    merge_findings,
    response_coverage,
    resolve_superseded_findings,
    validate_case_request,
    validate_contacts,
)
from .packs import VerticalPack
from .runtime import AgentRunStatus


class InvestigativeSourceLoopEngine(SourceLoopEngine):
    """Adds pack-defined swarms, risk gates, findings, and general follow-up loops."""

    def create_case(self, request: CaseCreate) -> CaseRecord:
        if request.kind is CaseKind.MARKET_INVESTIGATION and not request.pack:
            raise ValueError("Market investigation cases require an explicit governed pack.")
        pack = self.packs.get(request.pack) or self.packs.default_for(request.kind)
        if pack is None:
            raise ValueError(f"No SourceLoop pack is available for case kind {request.kind.value!r}")
        errors = validate_case_request(request, pack)
        if errors:
            raise ValueError("; ".join(errors))
        case = super().create_case(request)
        case.risk_tier = pack.risk_tier
        case.investigation_mode = request.investigation_mode or pack.investigation_mode
        case.governance = governance_snapshot(request, pack)
        self.repository.save_case(case)
        self.repository.append_event(
            case.id,
            "governance_applied",
            {
                "pack": pack.id,
                "risk_tier": pack.risk_tier.value,
                "investigation_mode": case.investigation_mode.value if case.investigation_mode else None,
                "acknowledgements": sorted(
                    key for key, value in request.governance_acknowledgements.items() if value
                ),
            },
        )
        return case

    def add_contacts(self, case_id: str, contacts: list[ContactRoute], *, replace: bool = False) -> CaseRecord:
        case = self.get_case(case_id)
        pack = self.packs.require(case.pack)
        errors = validate_contacts(contacts, pack)
        if errors:
            raise ValueError("; ".join(errors))
        existing = [] if replace else list(case.contacts)
        by_endpoint = {item.endpoint: item for item in existing}
        for contact in contacts:
            by_endpoint[contact.endpoint] = contact
        if len(by_endpoint) > case.max_contacts:
            raise ValueError(f"Case permits at most {case.max_contacts} unique contact route(s).")
        case.contacts = list(by_endpoint.values())
        if case.status is CaseStatus.WAITING_INPUT and case.stage is PractitionerStage.HOW and case.contacts:
            case.status = CaseStatus.ACTIVE
        self.repository.save_case(case)
        self.repository.append_event(
            case.id,
            "contacts_imported",
            {
                "replace": replace,
                "received": len(contacts),
                "stored": len(case.contacts),
                "endpoints": [contact.endpoint for contact in case.contacts],
            },
        )
        return self.run_until_blocked(case.id) if case.status is CaseStatus.ACTIVE else case

    def add_registry_check(self, case_id: str, request: RegistryCheckCreate) -> CaseRecord:
        case = self.get_case(case_id)
        check = RegistryCheck.model_validate(request.model_dump())
        case.registry_checks.append(check)
        normalized = check.status.strip().lower().replace(" ", "_")
        subject_id = check.subject_id or check.identifier or check.entity_name or check.query
        if normalized in {"matched", "verified", "active", "found"}:
            case.findings.append(
                self._registry_finding(
                    check,
                    subject_id,
                    FindingKind.POSITIVE_CONTROL,
                    Severity.INFO,
                    "Registry record matched",
                    "The supplied registry check reports a current matching record.",
                    requires_human_review=False,
                )
            )
            for finding in case.findings:
                if (
                    finding.subject_id == subject_id
                    and finding.kind is FindingKind.LICENSE_UNVERIFIED
                    and finding.status is FindingStatus.OPEN
                ):
                    finding.status = FindingStatus.RESOLVED
                    finding.review_notes = f"Resolved by registry check {check.id}."
        elif normalized in {"not_found", "no_match", "unverified", "inactive", "expired"}:
            case.findings.append(
                self._registry_finding(
                    check,
                    subject_id,
                    FindingKind.LICENSE_UNVERIFIED,
                    Severity.HIGH if normalized in {"inactive", "expired"} else Severity.MEDIUM,
                    "Registry check did not confirm the claimed record",
                    (
                        "The checked registry did not confirm the submitted identity or authorization. "
                        "This is a research finding, not a legal conclusion."
                    ),
                    requires_human_review=True,
                )
            )
        self.repository.save_case(case)
        self.repository.append_event(
            case.id,
            "registry_check_recorded",
            {
                "registry_check_id": check.id,
                "registry": check.registry,
                "status": check.status,
                "identifier": check.identifier,
                "subject_id": check.subject_id,
            },
        )
        return case

    def review_finding(self, case_id: str, finding_id: str, request: FindingReviewRequest) -> CaseRecord:
        case = self.get_case(case_id)
        finding = next((item for item in case.findings if item.id == finding_id), None)
        if finding is None:
            raise KeyError(finding_id)
        finding.status = request.status
        finding.reviewed_by = request.reviewer
        finding.reviewed_at = utcnow()
        finding.review_notes = request.notes
        self.repository.save_case(case)
        self.repository.append_event(
            case.id,
            "finding_reviewed",
            {
                "finding_id": finding.id,
                "status": finding.status.value,
                "reviewer": request.reviewer,
                "notes": request.notes,
            },
        )
        return case

    @staticmethod
    def _registry_finding(
        check: RegistryCheck,
        subject_id: str,
        kind: FindingKind,
        severity: Severity,
        title: str,
        summary: str,
        *,
        requires_human_review: bool,
    ):
        from .domain import InvestigationFinding

        return InvestigationFinding(
            rule_id=f"registry:{check.registry}:{check.status}",
            kind=kind,
            severity=severity,
            title=title,
            summary=summary,
            subject_id=subject_id,
            value={
                "registry": check.registry,
                "status": check.status,
                "identifier": check.identifier,
                "entity_name": check.entity_name,
                "jurisdiction": check.jurisdiction,
            },
            evidence_ids=check.evidence_ids,
            confidence=0.95 if kind is FindingKind.POSITIVE_CONTROL else 0.8,
            source_scope="registry_check",
            requires_human_review=requires_human_review,
        )

    def simulate_demo_replies(self, case_id: str) -> CaseRecord:
        case = self.get_case(case_id)
        if not case.demo:
            raise PermissionError("Synthetic replies are available only for demo cases")
        pack = self.packs.get(case.pack)
        if pack is None or not pack.demo_replies:
            return super().simulate_demo_replies(case_id)
        outbound = [item for item in case.interactions if item.direction is Direction.OUTBOUND]
        if not outbound:
            raise ValueError("Dispatch the dry-run messages before simulating replies")
        needed = max(1, case.completion_target - completion_count(case, pack))
        for index, interaction in enumerate(outbound[:needed]):
            reply = pack.demo_replies[index % len(pack.demo_replies)]
            case = self.record_inbound(
                InboundEmail(
                    case_id=case.id,
                    thread_id=interaction.thread_id,
                    sender=interaction.endpoint,
                    subject=reply.subject or f"Re: {interaction.subject}",
                    body=reply.body,
                    provider_message_id=f"<demo-{pack.id}-{index}-{case.id}@example.test>",
                    in_reply_to=interaction.provider_message_id,
                    references=[item for item in [interaction.provider_message_id] if item],
                )
            )
            if case.status is CaseStatus.COMPLETED:
                break
        return case

    def _run_agents(
        self,
        case: CaseRecord,
        roles: list[str],
        instruction: str,
        extra_payload: dict[str, object] | None = None,
    ) -> list:
        pack = self.packs.get(case.pack)
        selected_roles = pack.roles_for(case.stage.value, roles) if pack else roles
        return super()._run_agents(case, selected_roles, instruction, extra_payload)

    def _how(self, case: CaseRecord) -> None:
        pack = self.packs.get(case.pack)
        if case.demo and not case.contacts and pack and pack.demo_contacts:
            case.contacts = [contact.model_copy(deep=True) for contact in pack.demo_contacts]
        super()._how(case)

    def _act(self, case: CaseRecord) -> None:
        existing_ids = {action.id for action in case.actions}
        super()._act(case)
        pack = self.packs.get(case.pack)
        if pack is None:
            return
        for action in case.actions:
            if action.id in existing_ids or action.followup:
                continue
            contact = next((item for item in case.contacts if item.endpoint == action.recipient), None)
            if contact is None:
                continue
            action.subject, action.body = compose_initial_message(case, contact, pack)
            action.idempotency_key = stable_key(case.id, contact.id, action.subject, action.body, "initial")

    def _verify(self, case: CaseRecord) -> None:
        pending = [item for item in case.interactions if item.direction is Direction.INBOUND and not item.processed]
        if not pending:
            case.status = CaseStatus.WAITING_EXTERNAL
            return
        pack = self.packs.get(case.pack)
        if pack is None:
            super()._verify(case)
            return

        # Coverage is computed before the base extraction so the overridden completion
        # predicate can prevent a partial response from prematurely closing the case.
        for interaction in pending:
            coverage = response_coverage(pack, interaction.body)
            previously = set(case.response_coverage.get(interaction.endpoint, []))
            case.response_coverage[interaction.endpoint] = sorted(
                previously.union(field for field, present in coverage.items() if present)
            )

        super()._verify(case)

        followup_proposed = any(
            action.status in {ActionStatus.PENDING, ActionStatus.APPROVED}
            and action.followup
            and action.recipient in {item.endpoint for item in pending}
            for action in case.actions
        )
        for interaction in pending:
            merge_findings(case.findings, evaluate_findings(case, interaction, pack))
            resolve_superseded_findings(case, interaction, pack)
            quote = self._quote_for_endpoint(case, interaction.endpoint)
            missing = critical_missing_fields(
                pack,
                interaction.body,
                quote,
                previously_covered=case.response_coverage.get(interaction.endpoint, []),
            )
            if missing and self._propose_pack_followup(case, interaction, pack, missing):
                followup_proposed = True

        if followup_proposed:
            case.stage = PractitionerStage.ACT
            case.status = CaseStatus.WAITING_APPROVAL
        elif self._case_ready_to_complete(case):
            case.stage = PractitionerStage.INTEGRATE_COMMIT
            case.status = CaseStatus.ACTIVE
        elif case.status is CaseStatus.ACTIVE:
            case.status = CaseStatus.WAITING_EXTERNAL

    def _propose_pack_followup(
        self,
        case: CaseRecord,
        interaction: Interaction,
        pack: VerticalPack,
        missing: list[str],
    ) -> bool:
        if any(token in interaction.body.lower() for token in ("unsubscribe", "do not contact", "no further contact")):
            return False
        existing = [
            action
            for action in case.actions
            if action.followup and action.recipient == interaction.endpoint
        ]
        if len(existing) >= case.max_followups:
            return False
        if any(
            action.status in {ActionStatus.PENDING, ActionStatus.APPROVED}
            and action.followup
            and action.recipient == interaction.endpoint
            for action in case.actions
        ):
            return False
        if not interaction.provider_message_id:
            self.repository.append_event(
                case.id,
                "followup_not_proposed",
                {"interaction_id": interaction.id, "reason": "missing_provider_message_id", "missing": missing},
            )
            return False

        runs = self._run_agents(
            case,
            ["followup_planner", "message_composer", "policy_critic"],
            "Compose one narrow, evidence-aware clarification containing only unresolved critical fields.",
            extra_payload={"interaction": interaction.model_dump(mode="json"), "missing_fields": missing},
        )
        run_ids = [run.id for run in runs if run.status is AgentRunStatus.SUCCEEDED]
        references = list(
            dict.fromkeys(
                [
                    *interaction.references,
                    *([interaction.in_reply_to] if interaction.in_reply_to else []),
                    interaction.provider_message_id,
                ]
            )
        )
        action = ActionProposal(
            recipient=interaction.endpoint,
            organization_name=next(
                (
                    contact.organization_name
                    for contact in case.contacts
                    if contact.endpoint == interaction.endpoint
                ),
                "",
            ),
            subject=interaction.subject if interaction.subject.lower().startswith("re:") else f"Re: {interaction.subject}",
            body=compose_followup(case, pack, missing),
            followup=True,
            thread_id=interaction.thread_id,
            in_reply_to=interaction.provider_message_id,
            references=references,
            approval_required=pack.followup_approval_required,
            proposed_by_run_ids=run_ids,
        )
        action.idempotency_key = stable_key(
            case.id,
            interaction.thread_id,
            interaction.provider_message_id,
            *missing,
            "pack-followup",
        )
        case.actions.append(action)
        self.repository.append_event(
            case.id,
            "followup_proposed",
            {
                "action_id": action.id,
                "interaction_id": interaction.id,
                "pack": pack.id,
                "missing": missing,
            },
        )
        return True

    def _case_ready_to_complete(self, case: CaseRecord) -> bool:
        pack = self.packs.get(case.pack)
        if pack is None:
            return super()._case_ready_to_complete(case)
        if any(action.status in {ActionStatus.PENDING, ActionStatus.APPROVED} for action in case.actions):
            return False
        if case.kind is CaseKind.QUOTE_INTELLIGENCE:
            if not super()._case_ready_to_complete(case):
                return False
        if completion_count(case, pack) < case.completion_target:
            return False
        if not pack.response_fields:
            return True

        critical_ids = {field.id for field in pack.response_fields if field.critical}
        if not critical_ids:
            return True
        inbound_endpoints = {
            interaction.endpoint
            for interaction in case.interactions
            if interaction.direction is Direction.INBOUND and interaction.processed
        }
        qualifying = 0
        for endpoint in inbound_endpoints:
            covered = set(case.response_coverage.get(endpoint, []))
            if critical_ids.issubset(covered):
                qualifying += 1
                continue
            followups = sum(
                1
                for action in case.actions
                if action.followup
                and action.recipient == endpoint
                and action.status in {ActionStatus.DISPATCHED, ActionStatus.REJECTED, ActionStatus.BLOCKED}
            )
            if followups >= case.max_followups:
                qualifying += 1
        return qualifying >= case.completion_target
