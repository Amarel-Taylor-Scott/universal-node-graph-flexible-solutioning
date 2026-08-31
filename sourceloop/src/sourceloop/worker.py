"""Long-running mailbox worker for container and process deployments."""

from __future__ import annotations

import logging
import signal
from datetime import UTC, datetime
from threading import Event

from .config import Settings
from .domain import MailboxSyncResult, WorkerHeartbeat, utcnow
from .evidence import EvidenceStore
from .extended_engine import InvestigativeSourceLoopEngine
from .mailbox import MailboxService
from .repository import Repository

LOGGER = logging.getLogger("sourceloop.worker")


class SourceLoopWorker:
    def __init__(self, settings: Settings, repository: Repository | None = None) -> None:
        self.settings = settings
        self.repository = repository or Repository(settings.database_url)
        self.engine = InvestigativeSourceLoopEngine(settings, repository=self.repository)
        self.evidence = EvidenceStore(settings.evidence_dir, settings.attachment_max_bytes)
        self.mailbox = MailboxService(settings, self.repository, self.engine, self.evidence)
        self.stop_event = Event()

    def install_signal_handlers(self) -> None:
        def stop(signum: int, _frame: object) -> None:
            LOGGER.info("received signal %s; stopping after current mailbox cycle", signum)
            self.stop_event.set()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

    def sync_once(self) -> MailboxSyncResult:
        started = utcnow()
        self._heartbeat("running", {"cycle_started_at": started.isoformat()})
        try:
            result = self.mailbox.sync_once()
            self._heartbeat("healthy", result.model_dump(mode="json"))
            LOGGER.info(
                "mailbox sync fetched=%s processed=%s duplicate=%s unmatched=%s failed=%s",
                result.fetched,
                result.processed,
                result.duplicates,
                result.unmatched,
                result.failed,
            )
            return result
        except Exception as exc:
            self._heartbeat("degraded", {"error": str(exc), "cycle_started_at": started.isoformat()})
            LOGGER.exception("mailbox synchronization failed")
            raise

    def run_forever(self) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s %(levelname)s %(name)s %(message)s",
            )
        self.install_signal_handlers()
        LOGGER.info(
            "starting worker id=%s mailbox_mode=%s poll_seconds=%s",
            self.settings.worker_id,
            self.settings.mailbox_mode,
            self.settings.imap_poll_seconds,
        )
        while not self.stop_event.is_set():
            try:
                self.sync_once()
            except Exception:  # noqa: BLE001 - heartbeat already records failure; next cycle retries
                pass
            remaining = self.settings.imap_poll_seconds
            while remaining > 0 and not self.stop_event.is_set():
                interval = min(self.settings.worker_heartbeat_seconds, remaining)
                self.stop_event.wait(interval)
                remaining -= interval
                if not self.stop_event.is_set():
                    self._heartbeat("healthy", {"state": "idle", "next_poll_seconds": remaining})
        self._heartbeat("stopped", {})

    def _heartbeat(self, status: str, details: dict[str, object]) -> None:
        self.repository.set_worker_heartbeat(
            WorkerHeartbeat(worker_id=self.settings.worker_id, status=status, details=details)
        )


def worker_is_healthy(repository: Repository, worker_id: str, max_age_seconds: int) -> tuple[bool, str]:
    heartbeat = repository.get_worker_heartbeat(worker_id)
    if heartbeat is None:
        return False, "worker heartbeat not found"
    now = datetime.now(UTC)
    updated = heartbeat.updated_at if heartbeat.updated_at.tzinfo else heartbeat.updated_at.replace(tzinfo=UTC)
    age = (now - updated).total_seconds()
    if age > max_age_seconds:
        return False, f"worker heartbeat is stale ({age:.1f}s)"
    if heartbeat.status not in {"running", "healthy"}:
        return False, f"worker status is {heartbeat.status}"
    return True, f"worker heartbeat age={age:.1f}s status={heartbeat.status}"
