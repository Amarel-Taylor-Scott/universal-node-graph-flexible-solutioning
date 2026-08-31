"""FastAPI application for SourceLoop operators and embedded clients."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from .config import Settings
from .domain import ApprovalRequest, CaseCreate, InboundEmail
from .engine import SourceLoopEngine
from .graph import GraphProjector
from .repository import Repository


class SuppressionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str
    reason: str = "Operator suppression"


def create_app(settings: Settings | None = None, repository: Repository | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    engine = SourceLoopEngine(resolved_settings, repository=repository)
    projector = GraphProjector()

    application = FastAPI(
        title="SourceLoop API",
        version="0.1.0",
        description="Approval-gated direct-source intelligence and request-to-quote practitioner runtime.",
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
        return {
            "name": "SourceLoop",
            "version": "0.1.0",
            "docs": "/docs",
            "email_mode": resolved_settings.email_mode,
            "external_send_enabled": resolved_settings.allow_external_send,
            "agent_runtime": resolved_settings.agent_runtime,
        }

    @application.get("/")
    def root() -> dict[str, object]:
        return runtime_info()

    @application.get("/api/v1/runtime")
    def get_runtime_info() -> dict[str, object]:
        return runtime_info()

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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

    @application.post("/api/v1/cases/{case_id}/actions/{action_id}/approve")
    def approve_action(case_id: str, action_id: str, request: ApprovalRequest) -> dict[str, object]:
        try:
            return engine.approve_action(case_id, action_id, request).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case or action not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post("/api/v1/cases/{case_id}/dispatch")
    def dispatch(case_id: str) -> dict[str, object]:
        try:
            return engine.dispatch_approved(case_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except (ValueError, PermissionError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post("/api/v1/inbound/email")
    def inbound_email(inbound: InboundEmail) -> dict[str, object]:
        try:
            return engine.record_inbound(inbound).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post("/api/v1/demo/{case_id}/replies")
    def demo_replies(case_id: str) -> dict[str, object]:
        try:
            return engine.simulate_demo_replies(case_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except (PermissionError, ValueError) as exc:
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
