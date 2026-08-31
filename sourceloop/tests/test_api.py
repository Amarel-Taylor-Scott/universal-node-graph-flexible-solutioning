from __future__ import annotations

from fastapi.testclient import TestClient

from sourceloop.api import create_app


def test_health_and_runtime(settings, repository) -> None:
    client = TestClient(create_app(settings, repository))
    assert client.get("/health/live").json() == {"status": "ok"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    runtime = client.get("/api/v1/runtime").json()
    assert runtime["version"] == "0.2.0"
    assert runtime["mailbox_mode"] == "disabled"


def test_mailbox_sync_is_blocked_when_disabled(settings, repository) -> None:
    client = TestClient(create_app(settings, repository))
    response = client.post("/api/v1/mailbox/sync")
    assert response.status_code == 409
