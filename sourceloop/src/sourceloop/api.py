"""FastAPI application for SourceLoop operators and embedded clients."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from .config import Settings
from .domain import ApprovalRequest, CaseCreate, InboundEmail
from .engine import SourceLoopEngine
from .evidence import EvidenceStore
from .graph import GraphProjector
from .mailbox import MailboxService
from .repository import ConcurrentUpdateError, Repository


class SuppressionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str
    reason: str = "Operator suppression"


def create_app(settings: Settings | None = None, repository: Repository | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    engine = SourceLoopEngine(resolved_settings, repository=repository)
    projector = GraphProjector()
    evidence = EvidenceStore(resolved_settings.evidence_dir, resolved_settings.attachment_max_bytes)

    application = FastAPI(
        title="SourceLoop API",
        version="0.2.0",
        description="Container-ready, approval-gated direct-source intelligence and correspondence runtime.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.state.engine = engine

    def runtime_info() -> dict[str, object]:
        heartbeat = engine.repository.get_worker_heartbeat(resolved_settings.worker_id)
        return {
            "name": "SourceLoop",
            "version": "0.2.0",
            "environment": resolved_settings.environment,
            "docs": "/docs",
            "email_mode": resolved_settings.email_mode,
            "external_send_enabled": resolved_settings.allow_external_send,
            "mailbox_mode": resolved_settings.mailbox_mode,
            "mailbox_enabled": resolved_settings.mailbox_enabled,
            "agent_runtime": resolved_settings.agent_runtime,
            "worker": heartbeat.model_dump(mode="json") if heartbeat else None,
        }

    @application.get("/")
    def root() -> dict[str, object]:
        return runtime_info()

    @application.get("/api/v1/runtime")
    def get_runtime_info() -> dict[str, object]:
        return runtime_info()

    @application.get("/health")
    @application.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready")
    def health_ready() -> dict[str, object]:
        try:
            engine.repository.ping()
        except Exception as exc:  # noqa: BLE001 - readiness must report any database driver failure
            raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
        return {"status": "ready", "database": "ok", "timestamp": datetime.now(UTC).isoformat()}

    @application.get("/api/v1/packs")
    def list_packs() -> list[dict[str, object]]:
        return [pack.model_dump(mode="json") for pack in engine.packs.list()]

    @application.post("/api/v1/cases", status_code=201)
    def create_case(request: CaseCreate) -> dict[str, object]:
        return engine.create_case(request).model_dump(mode="json")

    @application.get("/api/v1/cases")
    def list_cases() -> list[dict[str, object]]:
        return [case.model_dump(mode="json") for case in engine.repository.list_cases()]

    @application.get("/api/v1/cases/{case_id}")
    def get_case(case_id: str) -> dict[str, object]:
        try:
            return engine.get_case(case_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc

    @application.post("/api/v1/cases/{case_id}/run")
    def run_case(case_id: str) -> dict[str, object]:
        try:
            return engine.run_until_blocked(case_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except ConcurrentUpdateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post("/api/v1/cases/{case_id}/actions/{action_id}/approve")
    def approve_action(case_id: str, action_id: str, request: ApprovalRequest) -> dict[str, object]:
        try:
            return engine.approve_action(case_id, action_id, request).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case or action not found") from exc
        except (ValueError, ConcurrentUpdateError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post("/api/v1/cases/{case_id}/actions/{action_id}/reject")
    def reject_action(case_id: str, action_id: str, request: ApprovalRequest) -> dict[str, object]:
        try:
            return engine.reject_action(case_id, action_id, request).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case or action not found") from exc
        except (ValueError, ConcurrentUpdateError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post("/api/v1/cases/{case_id}/dispatch")
    def dispatch(case_id: str) -> dict[str, object]:
        try:
            return engine.dispatch_approved(case_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except (ValueError, PermissionError, RuntimeError, ConcurrentUpdateError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post("/api/v1/inbound/email")
    def inbound_email(inbound: InboundEmail) -> dict[str, object]:
        try:
            return engine.record_inbound(inbound).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except (ValueError, ConcurrentUpdateError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.get("/api/v1/mailbox/status")
    def mailbox_status() -> dict[str, object]:
        heartbeat = engine.repository.get_worker_heartbeat(resolved_settings.worker_id)
        return {
            "mode": resolved_settings.mailbox_mode,
            "enabled": resolved_settings.mailbox_enabled,
            "host_configured": bool(resolved_settings.imap_host),
            "folder": resolved_settings.imap_folder,
            "poll_seconds": resolved_settings.imap_poll_seconds,
            "mark_seen": resolved_settings.imap_mark_seen,
            "worker": heartbeat.model_dump(mode="json") if heartbeat else None,
        }

    @application.post("/api/v1/mailbox/sync")
    def mailbox_sync() -> dict[str, object]:
        if not resolved_settings.mailbox_enabled:
            raise HTTPException(status_code=409, detail="Mailbox mode is disabled")
        service = MailboxService(resolved_settings, engine.repository, engine, evidence)
        try:
            return service.sync_once().model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - expose a bounded operator-facing sync failure
            raise HTTPException(status_code=502, detail=f"Mailbox synchronization failed: {exc}") from exc

    @application.post("/api/v1/demo/{case_id}/replies")
    def demo_replies(case_id: str) -> dict[str, object]:
        try:
            return engine.simulate_demo_replies(case_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except (PermissionError, ValueError, ConcurrentUpdateError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.get("/api/v1/cases/{case_id}/events")
    def list_events(case_id: str) -> list[dict[str, object]]:
        try:
            engine.get_case(case_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        return [event.model_dump(mode="json") for event in engine.repository.list_events(case_id)]

    @application.get("/api/v1/outbox")
    def list_outbox() -> list[dict[str, object]]:
        return [record.model_dump(mode="json") for record in engine.repository.list_outbox()]

    @application.post("/api/v1/suppressions", status_code=201)
    def create_suppression(request: SuppressionCreate) -> dict[str, str]:
        engine.repository.add_suppression(request.endpoint, request.reason)
        return {"endpoint": request.endpoint.strip().lower(), "status": "suppressed"}

    @application.get("/api/v1/graph")
    def graph() -> dict[str, object]:
        return projector.node_link(engine.repository.list_cases())

    @application.get("/api/v1/map/features")
    def map_features() -> dict[str, object]:
        return projector.geojson(engine.repository.list_cases())

    @application.get("/api/v1/graph/city2graph")
    def city2graph_status() -> dict[str, object]:
        return projector.city2graph_status(engine.repository.list_cases())

    return application


app = create_app()
