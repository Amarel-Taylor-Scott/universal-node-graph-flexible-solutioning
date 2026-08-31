from __future__ import annotations

from pathlib import Path

import pytest

from sourceloop.config import Settings
from sourceloop.engine import SourceLoopEngine
from sourceloop.repository import Repository


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'sourceloop-test.db'}",
        agent_runtime="mock",
        hermes_profile="test",
        openclaw_agent="test",
        agent_timeout_seconds=10,
        max_internal_workers=4,
        email_mode="dry_run",
        allow_external_send=False,
        sender_name="SourceLoop Test",
        sender_email="research@example.test",
        smtp_host="",
        smtp_port=587,
        smtp_username="",
        smtp_password="",
        smtp_starttls=True,
        cors_origins=("http://testserver",),
    )


@pytest.fixture
def repository(settings: Settings) -> Repository:
    return Repository(settings.database_url)


@pytest.fixture
def engine(settings: Settings, repository: Repository) -> SourceLoopEngine:
    return SourceLoopEngine(settings, repository=repository)
