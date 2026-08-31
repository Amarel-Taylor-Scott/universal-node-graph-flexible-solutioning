from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_compose_defines_full_application_stack() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert set(compose["services"]) == {"db", "api", "worker", "web"}
    assert compose["services"]["db"]["networks"] == ["backend"]
    assert compose["services"]["web"]["ports"] == ["${SOURCELOOP_WEB_PORT:-8080}:8080"]
    assert compose["services"]["api"]["read_only"] is True
    assert compose["services"]["worker"]["command"] == ["worker"]
    assert "sourceloop-evidence" in compose["volumes"]


def test_sandbox_adds_non_relaying_mail_service() -> None:
    sandbox = yaml.safe_load((ROOT / "docker-compose.sandbox.yml").read_text(encoding="utf-8"))
    mail = sandbox["services"]["mail"]
    assert mail["image"] == "greenmail/standalone:2.1.13"
    assert "-Dgreenmail.auth.disabled" in mail["environment"]["GREENMAIL_OPTS"]
    assert sandbox["services"]["api"]["environment"]["SOURCELOOP_EMAIL_MODE"] == "smtp"
    assert sandbox["services"]["worker"]["environment"]["SOURCELOOP_MAILBOX_MODE"] == "imap"


def test_images_run_as_non_root_and_frontend_proxies_api() -> None:
    backend = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    nginx = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert "USER 10001:10001" in backend
    assert "USER nginx" in frontend
    assert "proxy_pass http://sourceloop_api" in nginx
    assert "try_files $uri $uri/ /index.html" in nginx
