from __future__ import annotations

from fastapi.testclient import TestClient

from sourceloop.api import create_app
from sourceloop.config import Settings
from sourceloop.repository import Repository


def test_api_drives_demo_to_completion(settings: Settings, repository: Repository) -> None:
    client = TestClient(create_app(settings, repository=repository))
    created = client.post(
        "/api/v1/cases",
        json={
            "title": "API quote case",
            "kind": "quote_intelligence",
            "pack": "facilities_quote",
            "objective": "Obtain comparable non-binding quotes.",
            "requester_name": "API Test",
            "demo": True,
            "requirements": {"service": "commercial maintenance", "minimum_quotes": 2},
        },
    )
    assert created.status_code == 201
    case_id = created.json()["id"]

    run = client.post(f"/api/v1/cases/{case_id}/run")
    assert run.status_code == 200
    case = run.json()
    assert case["status"] == "waiting_approval"

    for action in case["actions"]:
        approved = client.post(
            f"/api/v1/cases/{case_id}/actions/{action['id']}/approve",
            json={"approver": "api-reviewer", "note": "test"},
        )
        assert approved.status_code == 200

    dispatched = client.post(f"/api/v1/cases/{case_id}/dispatch")
    assert dispatched.status_code == 200
    assert dispatched.json()["status"] == "waiting_external"

    completed = client.post(f"/api/v1/demo/{case_id}/replies")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert len(completed.json()["quotes"]) >= 2

    graph = client.get("/api/v1/graph")
    assert graph.status_code == 200
    assert graph.json()["nodes"]

    outbox = client.get("/api/v1/outbox")
    assert outbox.status_code == 200
    assert len(outbox.json()) == 3
