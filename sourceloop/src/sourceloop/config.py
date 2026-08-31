"""Environment-backed SourceLoop settings with Docker secret support."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _raw(name: str, default: str = "") -> str:
    """Read an environment value, preferring the Docker-style ``*_FILE`` secret."""

    secret_path = os.getenv(f"{name}_FILE", "").strip()
    if secret_path:
        try:
            return Path(secret_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"Could not read {name}_FILE={secret_path!r}") from exc
    return os.getenv(name, default)


def _bool(name: str, default: bool) -> bool:
    raw = _raw(name, "")
    if not raw:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _int(name: str, default: int, minimum: int | None = None) -> int:
    raw = _raw(name, "")
    value = default if not raw else int(raw)
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration loaded once per application or worker process."""

    database_url: str = "sqlite:///./sourceloop.db"
    agent_runtime: str = "mock"
    hermes_profile: str = "sourceloop-research"
    openclaw_agent: str = "sourceloop-practitioner"
    agent_timeout_seconds: int = 180
    max_internal_workers: int = 6

    email_mode: str = "dry_run"
    allow_external_send: bool = False
    sender_name: str = "SourceLoop Research Assistant"
    sender_email: str = "research@example.invalid"
    reply_to_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: int = 30

    mailbox_mode: str = "disabled"
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    imap_ssl: bool = True
    imap_starttls: bool = False
    imap_poll_seconds: int = 30
    imap_mark_seen: bool = True
    imap_search_criterion: str = "UNSEEN"
    imap_max_messages: int = 50

    evidence_dir: str = "./.sourceloop/evidence"
    attachment_max_bytes: int = 10 * 1024 * 1024
    worker_id: str = "mailbox-worker"
    worker_heartbeat_seconds: int = 15
    environment: str = "development"
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://localhost:8080")

    @property
    def mailbox_enabled(self) -> bool:
        return self.mailbox_mode == "imap"

    @property
    def effective_reply_to(self) -> str:
        return self.reply_to_email.strip() or self.sender_email.strip()

    @classmethod
    def from_env(cls) -> Settings:
        origins = tuple(
            origin.strip()
            for origin in _raw(
                "SOURCELOOP_CORS_ORIGINS",
                "http://localhost:5173,http://localhost:8080",
            ).split(",")
            if origin.strip()
        )
        settings = cls(
            database_url=_raw("SOURCELOOP_DATABASE_URL", "sqlite:///./sourceloop.db").strip(),
            agent_runtime=_raw("SOURCELOOP_AGENT_RUNTIME", "mock").strip().lower(),
            hermes_profile=_raw("SOURCELOOP_HERMES_PROFILE", "sourceloop-research").strip(),
            openclaw_agent=_raw("SOURCELOOP_OPENCLAW_AGENT", "sourceloop-practitioner").strip(),
            agent_timeout_seconds=_int("SOURCELOOP_AGENT_TIMEOUT_SECONDS", 180, 1),
            max_internal_workers=_int("SOURCELOOP_MAX_INTERNAL_WORKERS", 6, 1),
            email_mode=_raw("SOURCELOOP_EMAIL_MODE", "dry_run").strip().lower(),
            allow_external_send=_bool("SOURCELOOP_ALLOW_EXTERNAL_SEND", False),
            sender_name=_raw("SOURCELOOP_SENDER_NAME", "SourceLoop Research Assistant").strip(),
            sender_email=_raw("SOURCELOOP_SENDER_EMAIL", "research@example.invalid").strip().lower(),
            reply_to_email=_raw("SOURCELOOP_REPLY_TO_EMAIL", "").strip().lower(),
            smtp_host=_raw("SOURCELOOP_SMTP_HOST", "").strip(),
            smtp_port=_int("SOURCELOOP_SMTP_PORT", 587, 1),
            smtp_username=_raw("SOURCELOOP_SMTP_USERNAME", "").strip(),
            smtp_password=_raw("SOURCELOOP_SMTP_PASSWORD", ""),
            smtp_starttls=_bool("SOURCELOOP_SMTP_STARTTLS", True),
            smtp_ssl=_bool("SOURCELOOP_SMTP_SSL", False),
            smtp_timeout_seconds=_int("SOURCELOOP_SMTP_TIMEOUT_SECONDS", 30, 1),
            mailbox_mode=_raw("SOURCELOOP_MAILBOX_MODE", "disabled").strip().lower(),
            imap_host=_raw("SOURCELOOP_IMAP_HOST", "").strip(),
            imap_port=_int("SOURCELOOP_IMAP_PORT", 993, 1),
            imap_username=_raw("SOURCELOOP_IMAP_USERNAME", "").strip(),
            imap_password=_raw("SOURCELOOP_IMAP_PASSWORD", ""),
            imap_folder=_raw("SOURCELOOP_IMAP_FOLDER", "INBOX").strip(),
            imap_ssl=_bool("SOURCELOOP_IMAP_SSL", True),
            imap_starttls=_bool("SOURCELOOP_IMAP_STARTTLS", False),
            imap_poll_seconds=_int("SOURCELOOP_IMAP_POLL_SECONDS", 30, 1),
            imap_mark_seen=_bool("SOURCELOOP_IMAP_MARK_SEEN", True),
            imap_search_criterion=_raw("SOURCELOOP_IMAP_SEARCH_CRITERION", "UNSEEN").strip(),
            imap_max_messages=_int("SOURCELOOP_IMAP_MAX_MESSAGES", 50, 1),
            evidence_dir=_raw("SOURCELOOP_EVIDENCE_DIR", "./.sourceloop/evidence").strip(),
            attachment_max_bytes=_int("SOURCELOOP_ATTACHMENT_MAX_BYTES", 10 * 1024 * 1024, 0),
            worker_id=_raw("SOURCELOOP_WORKER_ID", "mailbox-worker").strip(),
            worker_heartbeat_seconds=_int("SOURCELOOP_WORKER_HEARTBEAT_SECONDS", 15, 1),
            environment=_raw("SOURCELOOP_ENVIRONMENT", "development").strip().lower(),
            cors_origins=origins,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.email_mode not in {"dry_run", "smtp"}:
            raise ValueError("SOURCELOOP_EMAIL_MODE must be dry_run or smtp")
        if self.mailbox_mode not in {"disabled", "imap"}:
            raise ValueError("SOURCELOOP_MAILBOX_MODE must be disabled or imap")
        if self.smtp_ssl and self.smtp_starttls:
            raise ValueError("SMTP SSL and STARTTLS cannot both be enabled")
        if self.imap_ssl and self.imap_starttls:
            raise ValueError("IMAP SSL and STARTTLS cannot both be enabled")
        if self.email_mode == "smtp" and not self.smtp_host:
            raise ValueError("SOURCELOOP_SMTP_HOST is required in smtp mode")
        if self.mailbox_enabled and not self.imap_host:
            raise ValueError("SOURCELOOP_IMAP_HOST is required in imap mode")
        if not self.sender_email or "@" not in self.sender_email:
            raise ValueError("SOURCELOOP_SENDER_EMAIL must be a valid-looking address")
