"""FastAPI routes for contact import, registry checks, findings, and reports."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response

from .domain import ContactImportRequest, FindingReviewRequest, RegistryCheckCreate
from .extended_engine import InvestigativeSourceLoopEngine
from .reporting import build_case_report, case_report_csv
from .repository import ConcurrentUpdateError


def register_investigation_routes(app: FastAPI, engine: InvestigativeSourceLoopEngine) -> None:
    @app.post("/api/v1/cases/{case_id}/contacts")
    def import_contacts(case_id: str, request: ContactImportRequest) -> dict[str, object]:
        try:
            return engine.add_contacts(case_id, request.contacts, replace=request.replace).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except (ValueError, ConcurrentUpdateError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/cases/{case_id}/registry-checks", status_code=201)
    def record_registry_check(case_id: str, request: RegistryCheckCreate) -> dict[str, object]:
        try:
            return engine.add_registry_check(case_id, request).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except ConcurrentUpdateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/cases/{case_id}/findings")
    def list_findings(case_id: str) -> list[dict[str, object]]:
        try:
            case = engine.get_case(case_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        return [finding.model_dump(mode="json") for finding in case.findings]

    @app.post("/api/v1/cases/{case_id}/findings/{finding_id}/review")
    def review_finding(
        case_id: str,
        finding_id: str,
        request: FindingReviewRequest,
    ) -> dict[str, object]:
        try:
            return engine.review_finding(case_id, finding_id, request).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case or finding not found") from exc
        except ConcurrentUpdateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/cases/{case_id}/report")
    def get_case_report(case_id: str) -> dict[str, object]:
        try:
            case = engine.get_case(case_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        return build_case_report(case, engine.packs.get(case.pack))

    @app.get("/api/v1/cases/{case_id}/report.csv")
    def get_case_report_csv(case_id: str) -> Response:
        try:
            case = engine.get_case(case_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        content = case_report_csv(case, engine.packs.get(case.pack))
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{case.id}-report.csv"'},
        )
