from __future__ import annotations

from sourceloop.domain import WorkerHeartbeat
from sourceloop.worker import worker_is_healthy


def test_worker_heartbeat(repository) -> None:
    repository.set_worker_heartbeat(WorkerHeartbeat(worker_id="test-worker", status="healthy"))
    healthy, message = worker_is_healthy(repository, "test-worker", 60)
    assert healthy is True
    assert "healthy" in message
