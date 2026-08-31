#!/usr/bin/env python3
"""Exercise a real SMTP -> IMAP -> extraction loop against the GreenMail compose sandbox."""

from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "http://127.0.0.1:8080"
COMPOSE = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.sandbox.yml"]


def http_json(path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_tcp(port: int, timeout_seconds: int = 120) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"Timed out waiting for TCP port {port}")


def wait_for_http(path: str, timeout_seconds: int = 180) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            http_json(path)
            return
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(2)
    raise TimeoutError(f"Timed out waiting for {path}: {last_error}")


def main() -> None:
    wait_for_tcp(3025)
    wait_for_tcp(3143)
    wait_for_http("/health/ready")

    case = http_json(
        "/api/v1/cases",
        method="POST",
        payload={
            "title": "Container SMTP and IMAP integration smoke test",
            "kind": "quote_intelligence",
            "pack": "facilities_quote",
            "objective": "Obtain one complete, non-binding budgetary quote through the live mail sandbox.",
            "requester_name": "SourceLoop Container Test",
            "requester_email": "sourceloop@sourceloop.local",
            "requirements": {
                "service": "commercial preventive maintenance",
                "minimum_quotes": 1,
            },
            "contacts": [
                {
                    "organization_name": "Sandbox Supplier One",
                    "role_title": "Estimating desk",
                    "endpoint": "supplier1@supplier.local",
                    "source": "container_integration_test",
                    "source_public": True,
                    "confidence": 1.0,
                    "geography": "Sandbox market",
                    "topics": ["facilities_quote"],
                }
            ],
        },
    )
    case_id = case["id"]
    case = http_json(f"/api/v1/cases/{case_id}/run", method="POST")
    assert case["status"] == "waiting_approval", case
    assert len(case["actions"]) == 1, case

    action_id = case["actions"][0]["id"]
    http_json(
        f"/api/v1/cases/{case_id}/actions/{action_id}/approve",
        method="POST",
        payload={"approver": "container-smoke", "note": "Approved test-only GreenMail delivery"},
    )
    case = http_json(f"/api/v1/cases/{case_id}/dispatch", method="POST")
    assert case["status"] == "waiting_external", case

    response_body = (
        "Budgetary pricing is $125 per visit. Payment terms are Net 30. "
        "Taxes are included. Scope is subject to final site review. "
        "Current availability is within 14 days. Valid through 2026-10-15."
    )
    subprocess.run(
        [
            *COMPOSE,
            "exec",
            "-T",
            "api",
            "sourceloop",
            "sandbox-reply",
            "--case-id",
            case_id,
            "--from-address",
            "supplier1@supplier.local",
            "--body",
            response_body,
        ],
        check=True,
    )

    deadline = time.monotonic() + 90
    latest = case
    while time.monotonic() < deadline:
        try:
            http_json("/api/v1/mailbox/sync", method="POST")
        except urllib.error.HTTPError as exc:
            if exc.code not in {409, 502}:
                raise
        latest = http_json(f"/api/v1/cases/{case_id}")
        if latest["quotes"] and latest["status"] == "completed":
            break
        time.sleep(2)

    assert latest["status"] == "completed", latest
    assert len(latest["quotes"]) == 1, latest
    assert latest["quotes"][0]["unresolved_fields"] == [], latest["quotes"][0]
    assert any(item["direction"] == "inbound" for item in latest["interactions"]), latest
    outbox = http_json("/api/v1/outbox")
    assert any(item["case_id"] == case_id and item["status"] == "sent" for item in outbox), outbox

    print(
        json.dumps(
            {
                "status": "passed",
                "case_id": case_id,
                "case_status": latest["status"],
                "quote_count": len(latest["quotes"]),
                "interaction_count": len(latest["interactions"]),
                "provider_message_id": next(
                    item["provider_message_id"] for item in outbox if item["case_id"] == case_id
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
