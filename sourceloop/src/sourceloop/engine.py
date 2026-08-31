"""Nine-stage SourceLoop practitioner and direct-source case lifecycle."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

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
    FindingKind,
    FindingStatus,
    GeoPoint,
    InboundEmail,
    Interaction,
    InvestigationFinding,
    InvestigationMode,
    PractitionerStage,
    Quote,
    RiskTier,
    case_token,
    new_id,
    stable_key,
    utcnow,
)
from .extraction import reconcile_extractor_outputs
from .investigation import extract_investigation_findings
from .investigation_policy import evaluate_case_policy, missing_required_fields
from .mail import MailGateway, build_mail_gateway
from .packs import PackRegistry, VerticalPack
from .policy import PolicyEngine
from .repository import Repository
from .runtime import AgentRunStatus, SwarmCoordinator, build_runtime

_DEFAULT_STAGE_ROLES: dict[PractitionerStage, list[str]] = {
    PractitionerStage.ORIENT: ["case_supervisor"],
    PractitionerStage.RECONCILE_HORIZON: ["horizon_critic", "risk_classifier"],
    PractitionerStage.ASSESS_PREPARE: ["requirement_compiler", "missing_information_critic"],
    PractitionerStage.DECIDE_NEXT: ["completion_judge"],
    PractitionerStage.HOW: ["market_scout", "gis_scout", "relationship_scout", "contact_resolver"],
    PractitionerStage.ACT: ["message_composer", "policy_critic"],
    PractitionerStage.VERIFY: ["extractor_a", "extractor_b", "adversarial_auditor"],
    PractitionerStage.INTEGRATE_COMMIT: ["graph_curator"],
    PractitionerStage.ROUTE: ["completion_judge"],
}


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
        self.policy = PolicyEngine(settings, self.repository, self.packs)
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
        pack = self.packs.validate_case_selection(request.kind, request.pack)
        investigation_mode = request.investigation_mode or (pack.investigation_mode if pack else None)
        risk_tier = pack.risk_tier if pack else RiskTier.MODERATE
        max_contacts = pack.max_contacts if pack else (3 if request.kind is CaseKind.CIVIC_INTELLIGENCE else 5)
        max_followups = pack.max_followups if pack else 1
        completion_target = pack.completion_target if pack else self._default_completion_target(request.kind)
        for key in ("minimum_quotes", "minimum_results"):
            if key in request.requirements:
                completion_target = max(1, min(int(request.requirements[key]), max_contacts))
                break

        if request.kind is CaseKind.MARKET_INVESTIGATION and investigation_mode is None:
            raise ValueError("Market investigation cases require an investigation_mode or a pack that supplies one")
        if request.kind is not CaseKind.MARKET_INVESTIGATION and request.investigation_mode is not None:
            raise ValueError("investigation_mode is valid only for market_investigation cases")
        if risk_tier in {RiskTier.HIGH, RiskTier.RESTRICTED}:
            max_contacts = min(max_contacts, self.settings.max_restricted_contacts)
            max_followups = min(max_followups, 1)

        location = request.location
        if request.demo and location is None:
            location = GeoPoint(latitude=40.4406, longitude=-79.9959, label="Demonstration market")

        requirements = dict(request.requirements)
        if pack and pack.required_disclosures:
            configured = [str(item) for item in requirements.get("required_disclosures", [])]
            requirements["required_disclosures"] = list(dict.fromkeys([*configured, *pack.required_disclosures]))

        case = CaseRecord(
            title=request.title,
            kind=request.kind,
            objective=request.objective,
            requester_name=request.requester_name,
            requester_email=request.requester_email,
            pack=pack.id if pack else request.pack,
            investigation_mode=investigation_mode,
            risk_tier=risk_tier,
            demo=request.demo,
            location=location,
            requirements=requirements,
            contacts=request.contacts,
            max_contacts=max_contacts,
            max_followups=max_followups,
            completion_target=completion_target,
        )
        missing = missing_required_fields(case, pack)
        if missing:
            case.unknowns = missing
        decision = evaluate_case_policy(self.settings, case, pack)
        case.stage_outputs["case_policy"] = decision.model_dump(mode="json")
        if not decision.allowed:
            raise ValueError("; ".join(decision.reasons))

        self.repository.save_case(case)
        self.repository.append_event(
            case.id,
            "case_created",
            {
                "kind": case.kind.value,
                "pack": case.pack,
                "investigation_mode": case.investigation_mode.value if case.investigation_mode else None,
                "risk_tier": case.risk_tier.value,
                "demo": case.demo,
                "completion_target": case.completion_target,
                "case_token": case_token(case.id),
            },
        )
        return case

    @staticmethod
    def _default_completion_target(kind: CaseKind) -> int:
        if kind is CaseKind.QUOTE_INTELLIGENCE:
            return 2
        if kind is CaseKind.MARKET_INVESTIGATION:
            return 2
        return 1

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
            before = (
                case.stage,
                case.status,
                len(case.actions),
                len(case.claims),
                len(case.quotes),
                len(case.findings),
            )
            case = self.advance(case.id)
            after = (
                case.stage,
                case.status,
                len(case.actions),
                len(case.claims),
                len(case.quotes),
                len(case.findings),
            )
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

        needed = max(1, case.completion_target - self._obtained(case))
        for index, interaction in enumerate(outbound[:needed]):
            body = self._demo_reply(case, index)
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

    @staticmethod
    def _demo_reply(case: CaseRecord, index: int) -> str:
        if case.kind is CaseKind.QUOTE_INTELLIGENCE:
            replies = [
                "Budgetary pricing: $125 per site visit. Monthly preventive service is $890 per month. "
                "Setup is $250 one-time. Travel inside the listed service area is included. "
                "We are available to start within 14 days. Taxes and emergency call-outs are excluded. "
                "Payment terms are Net 30. Scope is confirmed for the stated portfolio. Valid through 2026-10-15.",
                "We can support the requested locations and start within 21 days. The service rate is $118 per "
                "visit and the monthly plan is $940 per month. Implementation is $175 one-time. Parts are not "
                "included; taxes are excluded. Payment terms are Net 30. Scope is subject to final site review. "
                "Valid through 2026-10-20.",
                "Our non-binding estimate is $132 per visit with a $825 monthly minimum. Capacity is available "
                "next month. After-hours labor and taxes are excluded. Payment terms are Net 45. Scope is "
                "confirmed as submitted. Valid through 2026-10-10.",
            ]
            return replies[index % len(replies)]
        if case.kind is CaseKind.MARKET_INVESTIGATION:
            if case.investigation_mode is InvestigationMode.QUOTE_PROBE:
                replies = [
                    "We currently serve the full county and are available next week. Weekly service is $45 per "
                    "visit; the first overgrown visit is $75 per visit. Edging is included and debris hauling is "
                    "excluded. Payment terms are due on receipt. Valid through 2026-10-15.",
                    "Our service area includes the requested municipality. We have limited availability in two "
                    "weeks. The standard price is $52 per visit with a $20 first-service fee. Payment terms are "
                    "Net 15. Valid through 2026-10-20.",
                    "We can start within 10 days and cover the requested ZIP codes. Pricing is $180 per month for "
                    "weekly service. Taxes are excluded. Payment terms are Net 30. Valid through 2026-10-30.",
                ]
                return replies[index % len(replies)]
            if case.investigation_mode is InvestigationMode.PRACTICE_AUDIT:
                return (
                    "The legal company name is Example Staffing LLC. Applicants do not pay a registration or "
                    "placement fee. Written terms are supplied by email. The advertised assignment is currently "
                    "available and payment terms for employer clients are Net 30."
                )
            if case.investigation_mode is InvestigationMode.COMPLIANCE_PROBE:
                return (
                    "Our legal company name is Example Financial LLC and license number is PA-12345. APR is 36%. "
                    "The application fee is $25, payment terms are monthly, and this information request does not "
                    "require a credit inquiry. Written terms are available before any application."
                )
            return (
                "We currently offer the listed service across the county, have availability within two weeks, "
                "and quote $60 per visit. The legal trade name is Example Local Services."
            )
        if case.kind is CaseKind.CIVIC_INTELLIGENCE:
            return (
                "Our organization serves the full county, including the municipality in your request. "
                "New public inquiries should use volunteer-coordinator@example.test. Public meeting details "
                "are maintained on the official calendar. This information may be reused for this case."
            )
        return "The listed organization and public contact route are active as of today."

    def _pack(self, case: CaseRecord) -> VerticalPack | None:
        return self.packs.get(case.pack)

    def _roles(self, case: CaseRecord, stage: PractitionerStage) -> list[str]:
        fallback = _DEFAULT_STAGE_ROLES[stage]
        pack = self._pack(case)
        return pack.roles_for(stage, fallback) if pack else fallback

    def _run_stage_agents(
        self,
        case: CaseRecord,
        instruction: str,
        extra_payload: dict[str, object] | None = None,
        roles: list[str] | None = None,
    ) -> list:
        return self._run_agents(case, roles or self._roles(case, case.stage), instruction, extra_payload)

    def _orient(self, case: CaseRecord) -> None:
        self._run_stage_agents(case, "Confirm the objective, requester identity, authority scope, and risk tier.")
        pack = self._pack(case)
        decision = evaluate_case_policy(self.settings, case, pack)
        case.stage_outputs["case_policy"] = decision.model_dump(mode="json")
        if not decision.allowed:
            case.status = CaseStatus.FAILED
            case.stage_outputs[case.stage.value] = {"policy_errors": decision.reasons}
            return
        if not case.objective.strip() or not case.requester_name.strip():
            case.status = CaseStatus.WAITING_INPUT
            case.stage_outputs[case.stage.value] = {"missing": ["objective", "requester_name"]}
            return
        self._move_next(case)

    def _reconcile_horizon(self, case: CaseRecord) -> None:
        self._run_stage_agents(
            case,
            "Resolve time horizon, geography, quote or investigation mode, risk, and side-effect boundaries.",
        )
        if case.kind is CaseKind.CIVIC_INTELLIGENCE:
            case.max_contacts = min(case.max_contacts, 3)
            case.max_followups = min(case.max_followups, 1)
        if case.risk_tier in {RiskTier.HIGH, RiskTier.RESTRICTED}:
            case.max_contacts = min(case.max_contacts, self.settings.max_restricted_contacts)
            case.max_followups = min(case.max_followups, 1)
        self._move_next(case)

    def _assess_prepare(self, case: CaseRecord) -> None:
        pack = self._pack(case)
        case.unknowns = missing_required_fields(case, pack)
        self._run_stage_agents(
            case,
            "Normalize the request, compile a truthful standardized scenario, and identify fields that must be learned from direct sources.",
        )
        if case.unknowns:
            case.status = CaseStatus.WAITING_INPUT
            case.stage_outputs[case.stage.value] = {
                "missing": case.unknowns,
                "message": "Complete the required pack fields before external acquisition.",
            }
            return
        self._move_next(case)

    def _decide_next(self, case: CaseRecord) -> None:
        self._run_stage_agents(case, "Decide whether existing evidence resolves the objective.")
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
                "message": "Provide public/business contact routes or connect an approved discovery adapter.",
            }
            return
        case.contacts = case.contacts[: case.max_contacts]
        self._run_stage_agents(
            case,
            "Rank the smallest relevant respondent panel and explain geographic, identity, registry, and role fit.",
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

        runs = self._run_stage_agents(
            case,
            "Prepare one concise, transparent, non-transactional request per approved counterparty route.",
        )
        run_ids = [run.id for run in runs if run.status is AgentRunStatus.SUCCEEDED]
        for contact in case.contacts:
            thread_id = f"thread_{stable_key(case.id, contact.endpoint)[:20]}"
            subject, body = self._compose_message(case, contact)
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
            decision = self.policy.evaluate(case, action.model_copy(update={"status": ActionStatus.APPROVED}))
            action.policy_receipt = decision.model_dump(mode="json")
            if not decision.allowed:
                action.status = ActionStatus.BLOCKED
            case.actions.append(action)
        if any(action.status is ActionStatus.PENDING for action in case.actions):
            case.status = CaseStatus.WAITING_APPROVAL
        else:
            case.status = CaseStatus.FAILED
        self.repository.append_event(
            case.id,
            "actions_proposed",
            {
                "action_ids": [action.id for action in case.actions],
                "recipient_count": len(case.actions),
                "blocked": [action.id for action in case.actions if action.status is ActionStatus.BLOCKED],
            },
        )

    def _compose_message(self, case: CaseRecord, contact: ContactRoute) -> tuple[str, str]:
        token = case_token(case.id)
        pack = self._pack(case)
        requirement_lines = "\n".join(
            f"- {key.replace('_', ' ').title()}: {_render_value(value)}"
            for key, value in sorted(case.requirements.items())
            if key not in {"registry_results", "expected_disclosures"}
        ) or "- Please confirm the scope needed to answer this request."

        if case.kind is CaseKind.QUOTE_INTELLIGENCE:
            subject = f"[SL:{token}] Budgetary quote request: {case.title}"
            questions = (
                "Please include current pricing and units, one-time fees, minimum commitments, capacity or "
                "availability, lead time, assumptions, exclusions, payment terms, tax treatment, and quote validity."
            )
        elif case.kind is CaseKind.CIVIC_INTELLIGENCE:
            subject = f"[SL:{token}] Public civic information request: {case.title}"
            questions = (
                "Could you confirm the geography your organization publicly serves, the appropriate public role "
                "for this inquiry, and any official public meeting or information resource? A referral is welcome "
                "if another organization is more appropriate."
            )
        elif case.kind is CaseKind.MARKET_INVESTIGATION:
            label = {
                InvestigationMode.QUOTE_PROBE: "Nonbinding market quote request",
                InvestigationMode.PRACTICE_AUDIT: "Public business-practice information request",
                InvestigationMode.COMPLIANCE_PROBE: "Public disclosure and registration information request",
                InvestigationMode.MARKET_CENSUS: "Public business service-area information request",
            }.get(case.investigation_mode, "Market information request")
            subject = f"[SL:{token}] {label}: {case.title}"
            prompts = pack.question_prompts if pack else []
            questions = "\n".join(f"- {prompt}" for prompt in prompts) or (
                "Please provide current, nonbinding, public-facing information for the supplied standardized scenario."
            )
        else:
            subject = f"[SL:{token}] Information verification request: {case.title}"
            questions = "Please correct any inaccurate field and identify the authoritative public or business route."

        greeting = contact.role_title or "team"
        purpose = _investigation_purpose_sentence(case)
        body = (
            f"Hello {greeting},\n\n"
            f"I am an automated assistant acting with {case.requester_name}'s authorization. {purpose}\n\n"
            f"Request objective:\n{case.objective}\n\n"
            f"Standardized scope:\n{requirement_lines}\n\n"
            f"Questions:\n{questions}\n\n"
            "This is an information or nonbinding quotation request only. It does not submit an application, "
            "authorize a credit inquiry, accept an offer, place an order, make a payment, or create a contract. "
            "The information will be treated as request-scoped unless you explicitly permit broader reuse. "
            "Reply 'no further contact' to suppress future requests to this endpoint.\n\n"
            f"Thank you,\n{case.requester_name}\nAssisted by SourceLoop"
        )
        return subject, body

    def _verify(self, case: CaseRecord) -> None:
        pending = [item for item in case.interactions if item.direction is Direction.INBOUND and not item.processed]
        if not pending:
            case.status = CaseStatus.WAITING_EXTERNAL
            return

        followup_proposed = False
        for interaction in pending:
            roles = self._roles(case, PractitionerStage.VERIFY)
            runs = self._run_agents(
                case,
                roles,
                "Extract scoped claims, quotes, findings, assumptions, exclusions, registry discrepancies, and uncertainty from this reply.",
                extra_payload={"interaction": interaction.model_dump(mode="json")},
            )
            outputs = [
                run.output
                for run in runs
                if run.role in {"extractor_a", "extractor_b"} and run.status is AgentRunStatus.SUCCEEDED
            ]
            claims, quote, disagreement = reconcile_extractor_outputs(case, interaction, outputs)
            case.claims.extend(_new_claims(case, claims))
            stored_quote = self._upsert_quote(case, quote) if quote else self._quote_for_endpoint(case, interaction.endpoint)
            if stored_quote:
                _resolve_quote_fields_from_reply(stored_quote, interaction.body)

            new_findings: list[InvestigationFinding] = []
            if case.kind is CaseKind.MARKET_INVESTIGATION:
                new_findings = _merge_findings(case, extract_investigation_findings(case, interaction))

            interaction.processed = True
            self.repository.append_event(
                case.id,
                "reply_extracted",
                {
                    "interaction_id": interaction.id,
                    "claim_ids": [claim.id for claim in claims],
                    "quote_id": stored_quote.id if stored_quote else None,
                    "finding_ids": [finding.id for finding in new_findings],
                    "extractor_disagreement": disagreement,
                },
            )
            missing = self._critical_missing(case, stored_quote, interaction.endpoint)
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
        self._run_stage_agents(
            case,
            "Prepare provenance-preserving entity, claim, quote, finding, referral, and relationship graph updates.",
        )
        case.graph_committed = True
        self.repository.append_event(
            case.id,
            "graph_projection_ready",
            {
                "claims": len(case.claims),
                "quotes": len(case.quotes),
                "findings": len(case.findings),
                "contacts": len(case.contacts),
            },
        )
        self._move_next(case)

    def _route(self, case: CaseRecord) -> None:
        self._run_stage_agents(case, "Confirm completion or route to another evidence cycle.")
        if self._case_ready_to_complete(case):
            case.status = CaseStatus.COMPLETED
            self.repository.append_event(
                case.id,
                "case_completed",
                {"obtained": self._obtained(case), "target": case.completion_target},
            )
        elif any(action.status is ActionStatus.PENDING for action in case.actions):
            case.stage = PractitionerStage.ACT
            case.status = CaseStatus.WAITING_APPROVAL
        else:
            case.stage = PractitionerStage.DECIDE_NEXT
            case.status = CaseStatus.ACTIVE

    def _upsert_quote(self, case: CaseRecord, incoming: Quote) -> Quote:
        existing = next(
            (quote for quote in case.quotes if incoming.contact_id and quote.contact_id == incoming.contact_id),
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
        existing.normalization_lineage = list(dict.fromkeys(existing.normalization_lineage + incoming.normalization_lineage))
        existing.unresolved_fields = sorted(set(existing.unresolved_fields).intersection(incoming.unresolved_fields))
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

    def _critical_missing(self, case: CaseRecord, quote: Quote | None, endpoint: str) -> list[str]:
        pack = self._pack(case)
        if case.kind is CaseKind.QUOTE_INTELLIGENCE:
            if quote is None:
                return []
            critical = pack.critical_quote_fields if pack else ["payment_terms", "quote_validity"]
            return sorted(set(quote.unresolved_fields).intersection(critical))
        if case.kind is CaseKind.MARKET_INVESTIGATION:
            critical = pack.critical_finding_fields if pack else []
            contact = next((item for item in case.contacts if item.endpoint == endpoint), None)
            subject_id = contact.id if contact else endpoint
            present = {
                finding.field
                for finding in case.findings
                if finding.subject_id == subject_id and finding.value not in (None, "", [], {})
            }
            return sorted(set(critical) - present)
        return []

    def _propose_followup(self, case: CaseRecord, interaction: Interaction, missing: list[str]) -> bool:
        if any(token in interaction.body.lower() for token in ("unsubscribe", "do not contact", "no further contact")):
            return False
        sent_or_pending = [action for action in case.actions if action.followup and action.recipient == interaction.endpoint]
        if len(sent_or_pending) >= case.max_followups:
            return False
        if not interaction.provider_message_id:
            self.repository.append_event(
                case.id,
                "followup_not_proposed",
                {"interaction_id": interaction.id, "reason": "missing_provider_message_id", "missing": missing},
            )
            return False
        pack = self._pack(case)
        runs = self._run_agents(
            case,
            self._roles(case, PractitionerStage.ACT),
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
        if case.risk_tier in {RiskTier.HIGH, RiskTier.RESTRICTED}:
            action.approval_required = True
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
        if case.kind is CaseKind.QUOTE_INTELLIGENCE:
            qualifying = sum(1 for quote in case.quotes if not self._critical_missing(case, quote, ""))
            return qualifying >= case.completion_target
        if case.kind is CaseKind.MARKET_INVESTIGATION:
            return self._investigation_subjects_complete(case) >= case.completion_target
        return len(case.claims) >= case.completion_target

    def _investigation_subjects_complete(self, case: CaseRecord) -> int:
        pack = self._pack(case)
        critical = set(pack.critical_finding_fields if pack else [])
        subjects: set[str] = set()
        for contact in case.contacts:
            findings = [finding for finding in case.findings if finding.subject_id == contact.id]
            if not findings:
                continue
            present = {
                finding.field
                for finding in findings
                if finding.value not in (None, "", [], {})
                and finding.status is not FindingStatus.CONTRADICTED
            }
            if not critical or critical.issubset(present):
                subjects.add(contact.id)
        return len(subjects)

    def _obtained(self, case: CaseRecord) -> int:
        if case.kind is CaseKind.QUOTE_INTELLIGENCE:
            return len(case.quotes)
        if case.kind is CaseKind.MARKET_INVESTIGATION:
            return self._investigation_subjects_complete(case)
        return len(case.claims)

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


def _new_claims(case: CaseRecord, candidates: list) -> list:
    existing = {(claim.subject_id, claim.predicate, repr(claim.value), tuple(claim.evidence_ids)) for claim in case.claims}
    result = []
    for claim in candidates:
        key = (claim.subject_id, claim.predicate, repr(claim.value), tuple(claim.evidence_ids))
        if key not in existing:
            existing.add(key)
            result.append(claim)
    return result


def _merge_findings(case: CaseRecord, candidates: list[InvestigationFinding]) -> list[InvestigationFinding]:
    existing = {(item.subject_id, item.field, repr(item.value), tuple(item.evidence_ids)) for item in case.findings}
    added: list[InvestigationFinding] = []
    for finding in candidates:
        key = (finding.subject_id, finding.field, repr(finding.value), tuple(finding.evidence_ids))
        if key not in existing:
            case.findings.append(finding)
            added.append(finding)
            existing.add(key)
    return added


def _investigation_purpose_sentence(case: CaseRecord) -> str:
    if case.kind is not CaseKind.MARKET_INVESTIGATION:
        return "I am helping obtain current information from an appropriate public or business source."
    labels = {
        InvestigationMode.QUOTE_PROBE: "I am obtaining a current nonbinding price and availability response for a standardized scenario.",
        InvestigationMode.PRACTICE_AUDIT: "I am documenting current public-facing business practices and disclosures for an authorized research case.",
        InvestigationMode.COMPLIANCE_PROBE: "I am collecting public-facing disclosure and registration information for an authorized comparison; I am not applying or transacting.",
        InvestigationMode.MARKET_CENSUS: "I am documenting current service coverage, availability, and public business routing for a geographic market map.",
    }
    return labels.get(case.investigation_mode, "I am conducting a transparent, authorized market-information request.")


def _compose_followup(case: CaseRecord, missing_fields: list[str]) -> str:
    labels = {
        "payment_terms": "the applicable payment terms",
        "quote_validity": "the date through which the quote is valid",
        "taxes": "whether taxes are included or excluded",
        "final_scope_confirmation": "whether the stated scope is confirmed or subject to further review",
        "extractor_disagreement": "a concise restatement of the quoted price, unit, and scope",
        "quoted_price": "the current nonbinding price and pricing unit for the supplied scenario",
        "availability": "current availability and expected start or lead time",
        "service_scope": "the geography and service components currently covered",
        "claimed_license_number": "the legal entity and public license or registration number, when applicable",
        "identity_or_legal_name": "the legal or trade name responsible for the response",
        "applicant_upfront_fee": "whether any applicant or candidate fee is charged, including registration, placement, training, equipment, or screening",
        "apr_percent": "the APR for the representative amount and term, without submitting an application or credit inquiry",
    }
    questions = "\n".join(f"- Please confirm {labels.get(field, field.replace('_', ' '))}." for field in missing_fields)
    return (
        "Hello,\n\n"
        "Thank you for the response. I am an automated assistant continuing the same authorized SourceLoop "
        "information request. To record the response accurately, could you clarify only the following item(s)?\n\n"
        f"{questions}\n\n"
        "This remains an information request only and does not submit an application, authorize a credit inquiry, "
        "accept an offer, place an order, make a payment, or create a contract. No further details are needed beyond "
        "the listed items. Reply 'no further contact' to suppress future requests to this endpoint.\n\n"
        f"Thank you,\n{case.requester_name}\nAssisted by SourceLoop"
    )


def _resolve_quote_fields_from_reply(quote: Quote, body: str) -> None:
    lower = body.lower()
    resolved: set[str] = set()
    payment = re.search(r"\bnet\s+(15|30|45|60|90)\b", lower)
    if payment:
        resolved.add("payment_terms")
        quote.commercial_terms["payment_terms"] = f"Net {payment.group(1)}"
    elif re.search(r"\bdue\s+(?:on\s+receipt|immediately)\b", lower):
        resolved.add("payment_terms")
        quote.commercial_terms["payment_terms"] = "Due on receipt"
    if "tax" in lower:
        resolved.add("taxes")
    if any(marker in lower for marker in ("scope confirmed", "scope is", "subject to", "upon review")):
        resolved.add("final_scope_confirmation")
    if re.search(r"valid\s+(?:through|until)\s+\d{4}-\d{2}-\d{2}", lower):
        resolved.add("quote_validity")
    if any(marker in lower for marker in ("available", "availability", "fully booked", "waitlist")):
        resolved.add("availability")
        quote.operational_terms.setdefault("availability", _sentence_with(body, "avail"))
    if any(marker in lower for marker in ("lead time", "start within", "ramp", "schedule within")):
        resolved.add("lead_time")
        quote.operational_terms.setdefault("lead_time", _sentence_with(body, "within"))
    quote.unresolved_fields = [field for field in quote.unresolved_fields if field not in resolved]


def _sentence_with(body: str, marker: str) -> str:
    for segment in re.split(r"(?<=[.!?;])\s+|\n+", body):
        if marker.lower() in segment.lower():
            return segment.strip()[:500]
    return ""


def _render_value(value: object) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _demo_contacts(case: CaseRecord) -> list[ContactRoute]:
    if case.kind is CaseKind.QUOTE_INTELLIGENCE:
        names = [
            ("Northstar Facility Services", "Estimating desk", "quotes@northstar.example.test", 40.443, -79.985),
            ("Three Rivers Mechanical", "Commercial service team", "estimating@threerivers.example.test", 40.455, -80.021),
            ("Allegheny Building Care", "Business development", "rfq@alleghenycare.example.test", 40.421, -79.943),
        ]
    elif case.kind is CaseKind.MARKET_INVESTIGATION:
        names = [
            ("Neighborhood Service One", "Public business contact", "info@service-one.example.test", 40.446, -79.973),
            ("Regional Service Two", "Public business contact", "quotes@service-two.example.test", 40.421, -80.012),
            ("County Service Three", "Public business contact", "contact@service-three.example.test", 40.468, -79.934),
            ("Market Operator Four", "Public business contact", "hello@operator-four.example.test", 40.402, -79.998),
        ]
    elif case.kind is CaseKind.CIVIC_INTELLIGENCE:
        names = [
            ("Demonstration County Civic Committee", "Public inquiry coordinator", "info@county-civic.example.test", 41.336, -75.048),
            ("Demonstration Regional Volunteer Network", "Volunteer coordinator", "volunteer@regional.example.test", 41.294, -75.139),
        ]
    else:
        names = [
            ("Demonstration Record Owner", "Public records contact", "records@owner.example.test", 40.441, -79.996),
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
        for name, role, endpoint, latitude, longitude in names[: case.max_contacts]
    ]
