"""Environment-backed SourceLoop settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration loaded once per application instance."""

    database_url: str
    agent_runtime: str
    hermes_profile: str
    openclaw_agent: str
    agent_timeout_seconds: int
    max_internal_workers: int
    email_mode: str
    allow_external_send: bool
    sender_name: str
    sender_email: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_starttls: bool
    cors_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Settings":
        origins = tuple(
            origin.strip()
            for origin in os.getenv("SOURCELOOP_CORS_ORIGINS", "http://localhost:5173").split(",")
            if origin.strip()
        )
        return cls(
            database_url=os.getenv("SOURCELOOP_DATABASE_URL", "sqlite:///./sourceloop.db"),
            agent_runtime=os.getenv("SOURCELOOP_AGENT_RUNTIME", "mock").strip().lower(),
            hermes_profile=os.getenv("SOURCELOOP_HERMES_PROFILE", "sourceloop-research"),
            openclaw_agent=os.getenv("SOURCELOOP_OPENCLAW_AGENT", "sourceloop-practitioner"),
            agent_timeout_seconds=_int("SOURCELOOP_AGENT_TIMEOUT_SECONDS", 180),
            max_internal_workers=max(1, _int("SOURCELOOP_MAX_INTERNAL_WORKERS", 6)),
            email_mode=os.getenv("SOURCELOOP_EMAIL_MODE", "dry_run").strip().lower(),
            allow_external_send=_bool("SOURCELOOP_ALLOW_EXTERNAL_SEND", False),
            sender_name=os.getenv("SOURCELOOP_SENDER_NAME", "SourceLoop Research Assistant"),
            sender_email=os.getenv("SOURCELOOP_SENDER_EMAIL", "research@example.invalid"),
            smtp_host=os.getenv("SOURCELOOP_SMTP_HOST", ""),
            smtp_port=_int("SOURCELOOP_SMTP_PORT", 587),
            smtp_username=os.getenv("SOURCELOOP_SMTP_USERNAME", ""),
            smtp_password=os.getenv("SOURCELOOP_SMTP_PASSWORD", ""),
            smtp_starttls=_bool("SOURCELOOP_SMTP_STARTTLS", True),
            cors_origins=origins,
        )
