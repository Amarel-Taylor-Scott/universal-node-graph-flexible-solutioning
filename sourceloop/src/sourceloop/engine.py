"""Nine-stage SourceLoop practitioner and direct-source case lifecycle."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from .config import Settings
from .domain import (
    STAGE_ORDER,
    ActionProposal,
    ActionStatus,
    ApprovalRequest,
    CaseCreate,
    CaseKind,
    CaseRecord,
    CaseStatus,
    ContactRoute,
    Direction,
    GeoPoint,
    InboundEmail,
    Interaction,
    PractitionerStage,
    Quote,
    case_token,
    new_id,
    stable_key,
    utcnow,
)
from .extraction import reconcile_extractor_outputs
from .mail import MailGateway, build_mail_gateway
from .packs import PackRegistry
from .policy import PolicyEngine
from .repository import Repository
from .runtime import AgentRunStatus, SwarmCoordinator, build_runtime


class SourceLoopEngine:
    """Authoritative process coordinator; agents return proposals and interpretations only."""

    def __init__(
        self,
        settings: Settings,
        repository: Repository | None = None,
        packs: PackRegistry | None = None,
        mail_gateway: MailGateway | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository or Repository(settings.database_url)
        self.packs = packs or PackRegistry()
        self.policy = PolicyEngine(settings, self.repository)
        self.runtime = build_runtime(settings)
        self.swarm = SwarmCoordinator(self.runtime, max_workers=settings.max_internal_workers)
        self.mail_gateway = mail_gateway or build_mail_gateway(settings, self.repository, self.policy)
        self._handlers: dict[PractitionerStage, Callable[[CaseRecord], None]] = {
            PractitionerStage.ORIENT: self._orient,
            PractitionerStage.RECONCILE_HORIZON: self._reconcile_horizon,
            PractitionerStage.ASSESS_PREPARE: self._assess_prepare,
            PractitionerStage.DECIDE_NEXT: self._decide_next,
            PractitionerStage.HOW: self._how,
            PractitionerStage.ACT: self._act,
            PractitionerStage.VERIFY: self._verify,
            PractitionerStage.INTEGRATE_COMMIT: self._integrate_commit,
            PractitionerStage.ROUTE: self._route,
        }

    def create_case(self, request: CaseCreate) -> CaseRecord:
        pack = self.packs.get(request.pack) or self.packs.default_for(request.kind)
        max_contacts = pack.max_contacts if pack else (3 if request.kind is CaseKind.CIVIC_INTELLIGENCE else 5)
        max_followups = pack.max_followups if pack else 1
        completion_target = pack.completion_target if pack else (2 if request.kind is CaseKind.QUOTE_INTELLIGENCE else 1)
        if "minimum_quotes" in request.requirements and request.kind is CaseKind.QUOTE_INTELLIGENCE:
            completion_target = max(1, int(request.requirements["minimum_quotes"]))

        location = request.location
        if request.demo and location is None:
            location = GeoPoint(latitude=40.4406, longitude=-79.9959, label="Demonstration market")

        case = CaseRecord(
            title=request.title,
            kind=request.kind,
            objective=request.objective,
            requester_name=request.requester_name,
            requester_email=request.requester_email,
            pack=pack.id if pack else request.pack,
            demo=request.demo,
            location=location,
            requirements=request.requirements,
            contacts=request.contacts,
            max_contacts=max_contacts,
            max_followups=max_followups,
            completion_target=completion_target,
        )
        self.repository.save_case(case)
        self.repository.append_event(
            case.id,
            "case_created",
            {
                "kind": case.kind.value,
                "pack": case.pack,
                "demo": case.demo,
                "completion_target": case.completion_target,
                "case_token": case_token(case.id),
            },
        )
        return case

    def get_case(self, case_id: str) -> CaseRecord:
        case = self.repository.get_case(case_id)
        if case is None:
            raise KeyError(case_id)
        return case

    def run_until_blocked(self, case_id: str, max_steps: int = 20) -> CaseRecord:
        case = self.get_case(case_id)
        for _ in range(max_steps):
            if case.status is not CaseStatus.ACTIVE:
                break
            before = (case.stage, case.status, len(case.actions), len(case.claims), len(case.quotes))
            case = self.advance(case.id)
            after = (case.stage, case.status, len(case.actions), len(case.claims), len(case.quotes))
            if after == before:
                break
        return case

    def advance(self, case_id: str) -> CaseRecord:
        case = self.get_case(case_id)
        if case.status is not CaseStatus.ACTIVE:
            return case
        before_stage = case.stage
        before_status = case.status
        self._handlers[case.stage](case)
        self.repository.save_case(case)
        self.repository.append_event(
            case.id,
            "practitioner_step",
            {
                "from_stage": before_stage.value,
                "to_stage": case.stage.value,
                "from_status": before_status.value,
                "to_status": case.status.value,
            },
        )
        return case

    def approve_action(self, case_id: str, action_id: str, request: ApprovalRequest) -> CaseRecord:
        case = self.get_case(case_id)
        action = next((candidate for candidate in case.actions if candidate.id == action_id), None)
        if action is None:
            raise KeyError(action_id)
        if action.status is not ActionStatus.PENDING:
            raise ValueError(f"Action {action_id} is not pending")
        action.status = ActionStatus.APPROVED
        action.approved_by = request.approver
        action.approved_at = utcnow()
        self.repository.save_case(case)
        self.repository.append_event(
            case.id,
            "action_approved",
            {"action_id": action.id, "approver": request.approver, "note": request.note},
        )
        return case

    def reject_action(self, case_id: str, action_id: str, request: ApprovalRequest) -> CaseRecord:
        case = self.get_case(case_id)
        action = next((candidate for candidate in case.actions if candidate.id == action_id), None)
        if action is None:
            raise KeyError(action_id)
        if action.status not in {ActionStatus.PENDING, ActionStatus.APPROVED}:
            raise ValueError(f"Action {action_id} cannot be rejected from {action.status.value}")
        action.status = ActionStatus.REJECTED
        action.approved_by = request.approver
        action.approved_at = utcnow()
        if not any(item.status in {ActionStatus.PENDING, ActionStatus.APPROVED} for item in case.actions):
            case.stage = PractitionerStage.ROUTE
            case.status = CaseStatus.ACTIVE
        self.repository.save_case(case)
        self.repository.append_event(
            case.id,
            "action_rejected",
            {"action_id": action.id, "operator": request.approver, "note": request.note},
        )
        return self.run_until_blocked(case.id)

    def dispatch_approved(self, case_id: str) -> CaseRecord:
        case = self.get_case(case_id)
        approved = [action for action in case.actions if action.status is ActionStatus.APPROVED]
        if not approved:
            raise ValueError("No approved actions are ready for dispatch")

        failures: list[str] = []
        for action in approved:
            try:
                record = self.mail_gateway.send(case, action)
                action.status = ActionStatus.DISPATCHED
                action.dispatched_at = utcnow()
                action.thread_id = record.thread_id
                if not any(item.related_action_id == action.id for item in case.interactions):
                    case.interactions.append(
                        Interaction(
                            thread_id=record.thread_id,
                            direction=Direction.OUTBOUND,
                            endpoint=action.recipient,
                            subject=action.subject,
                            body=action.body,
                            evidence_id=record.id,
                            provider_message_id=record.provider_message_id,
                            in_reply_to=record.in_reply_to,
                            references=record.references,
                            related_action_id=action.id,
                        )
                    )
                self.repository.append_event(
                    case.id,
                    "action_dispatched",
                    {
                        "action_id": action.id,
                        "message_id": record.id,
                        "provider_message_id": record.provider_message_id,
                        "thread_id": record.thread_id,
                        "mode": self.settings.email_mode,
                        "status": record.status,
                        "followup": action.followup,
                    },
                )
            except Exception as exc:  # noqa: BLE001 - preserve per-action failure receipts
                action.status = ActionStatus.BLOCKED
                failures.append(f"{action.id}: {exc}")
                self.repository.append_event(case.id, "action_blocked", {"action_id": action.id, "reason": str(exc)})

        if any(action.status is ActionStatus.PENDING for action in case.actions):
            case.status = CaseStatus.WAITING_APPROVAL
        elif any(action.status is ActionStatus.DISPATCHED for action in approved):
            case.stage = PractitionerStage.VERIFY
            case.status = CaseStatus.WAITING_EXTERNAL
        else:
            case.status = CaseStatus.FAILED
            case.stage_outputs.setdefault("dispatch", {})["failures"] = failures
        self.repository.save_case(case)
        return case

    def record_inbound(self, inbound: InboundEmail) -> CaseRecord:
        case = self.get_case(inbound.case_id)
        if inbound.provider_message_id and any(
            item.provider_message_id == inbound.provider_message_id for item in case.interactions
        ):
            return case
        endpoint = inbound.sender.strip().lower()
        interaction = Interaction(
            thread_id=inbound.thread_id,
            direction=Direction.INBOUND,
            endpoint=endpoint,
            subject=inbound.subject,
            body=inbound.body,
            evidence_id=inbound.evidence_id or new_id("evidence"),
            raw_evidence_path=inbound.raw_evidence_path,
            provider_message_id=inbound.provider_message_id,
            in_reply_to=inbound.in_reply_to,
            references=inbound.references,
            headers=inbound.headers,
            attachments=inbound.attachments,
        )
        case.interactions.append(interaction)
        if any(token in inbound.body.lower() for token in ("unsubscribe", "do not contact", "no further contact")):
            self.repository.add_suppression(endpoint, "Direct recipient opt-out")
            self.repository.append_event(case.id, "endpoint_suppressed", {"endpoint": endpoint})
        case.stage = PractitionerStage.VERIFY
        case.status = CaseStatus.ACTIVE
        self.repository.save_case(case)
        self.repository.append_event(
            case.id,
            "inbound_recorded",
            {
                "interaction_id": interaction.id,
                "thread_id": interaction.thread_id,
                "endpoint": endpoint,
                "provider_message_id": interaction.provider_message_id,
                "attachment_count": len(interaction.attachments),
                "raw_evidence_path": interaction.raw_evidence_path,
            },
        )
        return self.run_until_blocked(case.id)

    def simulate_demo_replies(self, case_id: str) -> CaseRecord:
        case = self.get_case(case_id)
        if not case.demo:
            raise PermissionError("Synthetic replies are available only for demo cases")
        outbound = [item for item in case.interactions if item.direction is Direction.OUTBOUND]
        if not outbound:
            raise ValueError("Dispatch the dry-run messages before simulating replies")

        needed = max(
            1,
            case.completion_target
            - (len(case.quotes) if case.kind is CaseKind.QUOTE_INTELLIGENCE else len(case.claims)),
        )
        for index, interaction in enumerate(outbound[:needed]):
            if case.kind is CaseKind.QUOTE_INTELLIGENCE:
                replies = [
                    "Budgetary pricing: $125 per site visit. Monthly preventive service is $890 per month. "
                    "Setup is $250 one-time. Travel inside the listed service area is included. "
                    "Taxes and emergency call-outs are excluded. Payment terms are Net 30. "
                    "Scope is confirmed for the stated portfolio. Valid through 2026-10-15.",
                    "We can support the requested locations. The service rate is $118 per visit and the monthly "
                    "plan is $940 per month. Implementation is $175 one-time. Parts are not included; taxes are "
                    "excluded. Payment terms are Net 30. Scope is subject to final site review. "
                    "Valid through 2026-10-20.",
                    "Our non-binding estimate is $132 per visit with a $825 monthly minimum. After-hours labor and "
                    "taxes are excluded. Payment terms are Net 45. Scope is confirmed as submitted. "
                    "Valid through 2026-10-10.",
                ]
                body = replies[index % len(replies)]
            elif case.kind is CaseKind.CIVIC_INTELLIGENCE:
                body = (
                    "Our organization serves the full county, including the municipality in your request. "
                    "New public inquiries should use volunteer-coordinator@example.test. Public meeting details "
                    "are maintained on the official calendar. This information may be reused for this case."
                )
            else:
                body = "The listed organization and public contact route are active as of today."

            case = self.record_inbound(
                InboundEmail(
                    case_id=case.id,
                    thread_id=interaction.thread_id,
                    sender=interaction.endpoint,
                    subject=f"Re: {interaction.subject}",
                    body=body,
                    provider_message_id=f"<demo-reply-{index}-{case.id}@example.test>",
                    in_reply_to=interaction.provider_message_id,
                    references=[identifier for identifier in [interaction.provider_message_id] if identifier],
                )
            )
            if case.status is CaseStatus.COMPLETED:
                break
        return case

    def _orient(self, case: CaseRecord) -> None:
        self._run_agents(case, ["case_supervisor"], "Confirm the objective, requester identity, and authority scope.")
        if not case.objective.strip() or not case.requester_name.strip():
            case.status = CaseStatus.WAITING_INPUT
            case.stage_outputs[case.stage.value] = {"missing": ["objective", "requester_name"]}
            return
        self._move_next(case)

    def _reconcile_horizon(self, case: CaseRecord) -> None:
        self._run_agents(
            case,
            ["horizon_critic", "risk_classifier"],
            "Resolve time horizon, geography, quote type, risk, and side-effect boundaries.",
        )
        if case.kind is CaseKind.CIVIC_INTELLIGENCE:
            case.max_contacts = min(case.max_contacts, 3)
            case.max_followups = min(case.max_followups, 1)
        self._move_next(case)

    def _assess_prepare(self, case: CaseRecord) -> None:
        pack = self.packs.get(case.pack)
        required = pack.required_fields if pack else []
        case.unknowns = [field for field in required if _get_nested(case.requirements, field) in (None, "", [])]
        self._run_agents(
            case,
            ["requirement_compiler", "missing_information_critic"],
            "Normalize the request and identify fields that must be learned from direct sources.",
        )
        self._move_next(case)

    def _decide_next(self, case: CaseRecord) -> None:
        self._run_agents(case, ["completion_judge"], "Decide whether existing evidence resolves the objective.")
        if self._case_ready_to_complete(case):
            case.stage = PractitionerStage.INTEGRATE_COMMIT
        else:
            self._move_next(case)

    def _how(self, case: CaseRecord) -> None:
        if not case.contacts and case.demo:
            case.contacts = _demo_contacts(case)
        if not case.contacts:
            case.status = CaseStatus.WAITING_INPUT
            case.stage_outputs[case.stage.value] = {
                "missing": ["contact_routes_or_discovery_connector"],
                "message": "Provide seed contacts or connect a discovery adapter before external acquisition.",
            }
            return
        case.contacts = case.contacts[: case.max_contacts]
        self._run_agents(
            case,
            ["market_scout", "gis_scout", "relationship_scout", "contact_resolver"],
            "Rank the smallest relevant respondent panel and explain geographic and role fit.",
        )
        self._move_next(case)

    def _act(self, case: CaseRecord) -> None:
        existing = [action for action in case.actions if action.status in {ActionStatus.PENDING, ActionStatus.APPROVED}]
        if existing:
            case.status = CaseStatus.WAITING_APPROVAL
            return
        if any(action.status is ActionStatus.DISPATCHED for action in case.actions):
            case.stage = PractitionerStage.VERIFY
            case.status = CaseStatus.WAITING_EXTERNAL
            return

        runs = self._run_agents(
            case,
            ["message_composer", "policy_critic"],
            "Prepare one concise, transparent request per approved counterparty route.",
        )
        run_ids = [run.id for run in runs if run.status is AgentRunStatus.SUCCEEDED]
        for contact in case.contacts:
            thread_id = f"thread_{stable_key(case.id, contact.endpoint)[:20]}"
            subject, body = _compose_message(case, contact)
            action = ActionProposal(
                recipient=contact.endpoint,
                recipient_name=contact.role_title,
                organization_name=contact.organization_name,
                subject=subject,
                body=body,
                thread_id=thread_id,
                proposed_by_run_ids=run_ids,
            )
            action.idempotency_key = stable_key(case.id, contact.id, subject, body, "initial")
            case.actions.append(action)
        case.status = CaseStatus.WAITING_APPROVAL
        self.repository.append_event(
            case.id,
            "actions_proposed",
            {"action_ids": [action.id for action in case.actions], "recipient_count": len(case.actions)},
        )

    def _verify(self, case: CaseRecord) -> None:
        pending = [item for item in case.interactions if item.direction is Direction.INBOUND and not item.processed]
        if not pending:
            case.status = CaseStatus.WAITING_EXTERNAL
            return

        followup_proposed = False
        for interaction in pending:
            runs = self._run_agents(
                case,
                ["extractor_a", "extractor_b", "adversarial_auditor"],
                "Extract scoped claims, quotes, assumptions, exclusions, and uncertainty from this reply.",
                extra_payload={"interaction": interaction.model_dump(mode="json")},
            )
            outputs = [
                run.output
                for run in runs
                if run.role in {"extractor_a", "extractor_b"} and run.status is AgentRunStatus.SUCCEEDED
            ]
            claims, quote, disagreement = reconcile_extractor_outputs(case, interaction, outputs)
            case.claims.extend(claims)
            stored_quote = self._upsert_quote(case, quote) if quote else self._quote_for_endpoint(case, interaction.endpoint)
            if stored_quote:
                _resolve_quote_fields_from_reply(stored_quote, interaction.body)
            interaction.processed = True
            self.repository.append_event(
                case.id,
                "reply_extracted",
                {
                    "interaction_id": interaction.id,
                    "claim_ids": [claim.id for claim in claims],
                    "quote_id": stored_quote.id if stored_quote else None,
                    "extractor_disagreement": disagreement,
                },
            )
            missing = self._critical_missing(case, stored_quote)
            if missing and self._propose_followup(case, interaction, missing):
                followup_proposed = True

        if followup_proposed:
            case.stage = PractitionerStage.ACT
            case.status = CaseStatus.WAITING_APPROVAL
        elif self._case_ready_to_complete(case):
            self._move_next(case)
            case.status = CaseStatus.ACTIVE
        else:
            case.status = CaseStatus.WAITING_EXTERNAL

    def _integrate_commit(self, case: CaseRecord) -> None:
        self._run_agents(
            case,
            ["graph_curator"],
            "Prepare provenance-preserving entity, claim, quote, and relationship graph updates.",
        )
        case.graph_committed = True
        self.repository.append_event(
            case.id,
            "graph_projection_ready",
            {"claims": len(case.claims), "quotes": len(case.quotes), "contacts": len(case.contacts)},
        )
        self._move_next(case)

    def _route(self, case: CaseRecord) -> None:
        self._run_agents(case, ["completion_judge"], "Confirm completion or route to another evidence cycle.")
        if self._case_ready_to_complete(case):
            case.status = CaseStatus.COMPLETED
            obtained = len(case.quotes) if case.kind is CaseKind.QUOTE_INTELLIGENCE else len(case.claims)
            self.repository.append_event(
                case.id,
                "case_completed",
                {"obtained": obtained, "target": case.completion_target},
            )
        elif any(action.status is ActionStatus.PENDING for action in case.actions):
            case.stage = PractitionerStage.ACT
            case.status = CaseStatus.WAITING_APPROVAL
        else:
            case.stage = PractitionerStage.DECIDE_NEXT
            case.status = CaseStatus.ACTIVE

    def _upsert_quote(self, case: CaseRecord, incoming: Quote) -> Quote:
        existing = next(
            (
                quote
                for quote in case.quotes
                if incoming.contact_id and quote.contact_id == incoming.contact_id
            ),
            None,
        )
        if existing is None:
            case.quotes.append(incoming)
            return incoming
        seen = {(item.description, item.unit, item.unit_price) for item in existing.line_items}
        for line_item in incoming.line_items:
            key = (line_item.description, line_item.unit, line_item.unit_price)
            if key not in seen:
                existing.line_items.append(line_item)
                seen.add(key)
        existing.commercial_terms.update(incoming.commercial_terms)
        existing.operational_terms.update(incoming.operational_terms)
        existing.exclusions = sorted(set(existing.exclusions + incoming.exclusions))
        existing.assumptions = sorted(set(existing.assumptions + incoming.assumptions))
        existing.evidence_ids = list(dict.fromkeys(existing.evidence_ids + incoming.evidence_ids))
        existing.normalization_lineage = list(
            dict.fromkeys(existing.normalization_lineage + incoming.normalization_lineage)
        )
        existing.unresolved_fields = incoming.unresolved_fields
        existing.extraction_confidence = min(existing.extraction_confidence, incoming.extraction_confidence)
        if incoming.valid_until:
            existing.valid_until = incoming.valid_until
        return existing

    @staticmethod
    def _quote_for_endpoint(case: CaseRecord, endpoint: str) -> Quote | None:
        contact = next((item for item in case.contacts if item.endpoint == endpoint), None)
        if contact is None:
            return None
        return next((quote for quote in case.quotes if quote.contact_id == contact.id), None)

    def _critical_missing(self, case: CaseRecord, quote: Quote | None) -> list[str]:
        if case.kind is not CaseKind.QUOTE_INTELLIGENCE or quote is None:
            return []
        pack = self.packs.get(case.pack)
        critical = pack.critical_quote_fields if pack else ["payment_terms", "quote_validity"]
        return sorted(set(quote.unresolved_fields).intersection(critical))

    def _propose_followup(self, case: CaseRecord, interaction: Interaction, missing: list[str]) -> bool:
        if any(token in interaction.body.lower() for token in ("unsubscribe", "do not contact", "no further contact")):
            return False
        sent_or_pending = [
            action for action in case.actions if action.followup and action.recipient == interaction.endpoint
        ]
        if len(sent_or_pending) >= case.max_followups:
            return False
        if not interaction.provider_message_id:
            self.repository.append_event(
                case.id,
                "followup_not_proposed",
                {"interaction_id": interaction.id, "reason": "missing_provider_message_id", "missing": missing},
            )
            return False
        pack = self.packs.get(case.pack)
        runs = self._run_agents(
            case,
            ["message_composer", "policy_critic"],
            "Compose one thread-aware clarification containing only unresolved critical fields.",
            extra_payload={"interaction": interaction.model_dump(mode="json"), "missing_fields": missing},
        )
        run_ids = [run.id for run in runs if run.status is AgentRunStatus.SUCCEEDED]
        subject = interaction.subject if interaction.subject.lower().startswith("re:") else f"Re: {interaction.subject}"
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
            subject=subject,
            body=_compose_followup(case, missing),
            followup=True,
            thread_id=interaction.thread_id,
            in_reply_to=interaction.provider_message_id,
            references=references,
            approval_required=pack.followup_approval_required if pack else True,
            proposed_by_run_ids=run_ids,
        )
        action.idempotency_key = stable_key(
            case.id,
            interaction.thread_id,
            interaction.provider_message_id,
            *missing,
            "followup",
        )
        case.actions.append(action)
        self.repository.append_event(
            case.id,
            "followup_proposed",
            {"action_id": action.id, "interaction_id": interaction.id, "missing": missing},
        )
        return True

    def _case_ready_to_complete(self, case: CaseRecord) -> bool:
        if any(action.status in {ActionStatus.PENDING, ActionStatus.APPROVED} for action in case.actions):
            return False
        obtained = len(case.quotes) if case.kind is CaseKind.QUOTE_INTELLIGENCE else len(case.claims)
        if obtained < case.completion_target:
            return False
        if case.kind is CaseKind.QUOTE_INTELLIGENCE:
            qualifying = sum(1 for quote in case.quotes if not self._critical_missing(case, quote))
            return qualifying >= case.completion_target
        return True

    def _run_agents(
        self,
        case: CaseRecord,
        roles: list[str],
        instruction: str,
        extra_payload: dict[str, object] | None = None,
    ) -> list:
        runs = self.swarm.execute(case, case.stage, roles, instruction, extra_payload=extra_payload)
        case.agent_runs.extend(runs)
        stage_entry = case.stage_outputs.setdefault(case.stage.value, {"batches": []})
        stage_entry.setdefault("batches", []).append(
            {
                "roles": roles,
                "run_ids": [run.id for run in runs],
                "failed": [run.role for run in runs if run.status is AgentRunStatus.FAILED],
            }
        )
        return runs

    @staticmethod
    def _move_next(case: CaseRecord) -> None:
        index = STAGE_ORDER.index(case.stage)
        if index + 1 < len(STAGE_ORDER):
            case.stage = STAGE_ORDER[index + 1]


def _compose_message(case: CaseRecord, contact: ContactRoute) -> tuple[str, str]:
    token = case_token(case.id)
    if case.kind is CaseKind.QUOTE_INTELLIGENCE:
        subject = f"[SL:{token}] Budgetary quote request: {case.title}"
        requirement_lines = "\n".join(
            f"- {key.replace('_', ' ').title()}: {_render_value(value)}"
            for key, value in sorted(case.requirements.items())
        ) or "- Please confirm the scope required to prepare a comparable budgetary quote."
        questions = (
            "Please include current pricing and units, one-time fees, minimum commitments, capacity or "
            "availability, lead time, assumptions, exclusions, payment terms, tax treatment, and quote validity."
        )
    elif case.kind is CaseKind.CIVIC_INTELLIGENCE:
        subject = f"[SL:{token}] Public civic information request: {case.title}"
        requirement_lines = "\n".join(
            f"- {key.replace('_', ' ').title()}: {_render_value(value)}"
            for key, value in sorted(case.requirements.items())
        ) or "- Please confirm the public organization, service area, and appropriate inquiry route."
        questions = (
            "Could you confirm the geography your organization publicly serves, the appropriate public role for "
            "this inquiry, and any official public meeting or information resource? A referral is welcome if "
            "another organization is more appropriate."
        )
    else:
        subject = f"[SL:{token}] Information verification request: {case.title}"
        requirement_lines = "\n".join(
            f"- {key.replace('_', ' ').title()}: {_render_value(value)}"
            for key, value in sorted(case.requirements.items())
        ) or "- Please confirm whether the supplied public or business record remains current."
        questions = "Please correct any inaccurate field and identify the authoritative public or business route."

    greeting = contact.role_title or "team"
    body = (
        f"Hello {greeting},\n\n"
        f"I am an automated assistant acting with {case.requester_name}'s authorization on the following "
        f"information request:\n\n{case.objective}\n\n"
        f"Current scope:\n{requirement_lines}\n\n"
        f"{questions}\n\n"
        "This is a one-time, transparent research or quotation request. The information will be treated as "
        "request-scoped unless you explicitly permit broader reuse. Reply 'no further contact' to suppress "
        "future requests to this endpoint.\n\n"
        f"Thank you,\n{case.requester_name}\nAssisted by SourceLoop"
    )
    return subject, body


def _compose_followup(case: CaseRecord, missing_fields: list[str]) -> str:
    labels = {
        "payment_terms": "the applicable payment terms",
        "quote_validity": "the date through which the quote is valid",
        "taxes": "whether taxes are included or excluded",
        "final_scope_confirmation": "whether the stated scope is confirmed or subject to further review",
        "extractor_disagreement": "a concise restatement of the quoted price, unit, and scope",
    }
    questions = "\n".join(f"- Please confirm {labels.get(field, field.replace('_', ' '))}." for field in missing_fields)
    return (
        "Hello,\n\n"
        "Thank you for the response. I am an automated assistant continuing the same authorized SourceLoop "
        "request. To compare the response accurately, could you clarify only the following item(s)?\n\n"
        f"{questions}\n\n"
        "No further details are needed beyond those items. Reply 'no further contact' to suppress future requests "
        "to this endpoint.\n\n"
        f"Thank you,\n{case.requester_name}\nAssisted by SourceLoop"
    )


def _resolve_quote_fields_from_reply(quote: Quote, body: str) -> None:
    lower = body.lower()
    resolved: set[str] = set()
    if re.search(r"\bnet\s+(15|30|45|60|90)\b", lower):
        resolved.add("payment_terms")
    if "tax" in lower:
        resolved.add("taxes")
    if any(marker in lower for marker in ("scope confirmed", "scope is", "subject to", "upon review")):
        resolved.add("final_scope_confirmation")
    if re.search(r"valid\s+(?:through|until)\s+\d{4}-\d{2}-\d{2}", lower):
        resolved.add("quote_validity")
    quote.unresolved_fields = [field for field in quote.unresolved_fields if field not in resolved]


def _render_value(value: object) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _get_nested(payload: dict[str, object], dotted_path: str) -> object | None:
    current: object = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _demo_contacts(case: CaseRecord) -> list[ContactRoute]:
    if case.kind is CaseKind.QUOTE_INTELLIGENCE:
        names = [
            ("Northstar Facility Services", "Estimating desk", "quotes@northstar.example.test", 40.443, -79.985),
            (
                "Three Rivers Mechanical",
                "Commercial service team",
                "estimating@threerivers.example.test",
                40.455,
                -80.021,
            ),
            (
                "Allegheny Building Care",
                "Business development",
                "rfq@alleghenycare.example.test",
                40.421,
                -79.943,
            ),
        ]
    elif case.kind is CaseKind.CIVIC_INTELLIGENCE:
        names = [
            (
                "Demonstration County Civic Committee",
                "Public inquiry coordinator",
                "info@county-civic.example.test",
                41.336,
                -75.048,
            ),
            (
                "Demonstration Regional Volunteer Network",
                "Volunteer coordinator",
                "volunteer@regional.example.test",
                41.294,
                -75.139,
            ),
        ]
    else:
        names = [
            (
                "Demonstration Record Owner",
                "Public records contact",
                "records@owner.example.test",
                40.441,
                -79.996,
            ),
        ]
    return [
        ContactRoute(
            organization_name=name,
            role_title=role,
            endpoint=endpoint,
            source="demo_pack",
            confidence=0.9,
            geography=case.location.label if case.location else "Demonstration geography",
            location=GeoPoint(latitude=latitude, longitude=longitude, label=name, precision="public_office"),
            topics=[case.kind.value],
        )
        for name, role, endpoint, latitude, longitude in names
    ]
