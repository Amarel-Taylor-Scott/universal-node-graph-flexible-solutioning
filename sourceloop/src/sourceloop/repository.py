"""SQL-backed case snapshots and immutable event, mail, and worker ledgers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    func,
    insert,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .domain import CaseEvent, CaseRecord, OutboxRecord, WorkerHeartbeat, case_token, utcnow


class ConcurrentUpdateError(RuntimeError):
    """Raised when API and worker processes attempt to update the same case snapshot."""


class Repository:
    """Persistence layer supporting SQLite and PostgreSQL/PostGIS URLs."""

    def __init__(self, database_url: str) -> None:
        connect_args: dict[str, Any] = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        self.engine: Engine = create_engine(
            database_url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        self.metadata = MetaData()
        self.cases = Table(
            "cases",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("version", Integer, nullable=False),
            Column("state_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.events = Table(
            "case_events",
            self.metadata,
            Column("case_id", String(64), primary_key=True),
            Column("sequence", Integer, primary_key=True),
            Column("event_id", String(64), nullable=False, unique=True),
            Column("event_type", String(128), nullable=False),
            Column("payload_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.outbox = Table(
            "outbox",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("case_id", String(64), nullable=False, index=True),
            Column("action_id", String(64), nullable=False, index=True),
            Column("idempotency_key", String(128), nullable=False, unique=True),
            Column("recipient", String(512), nullable=False),
            Column("sender", String(512), nullable=False),
            Column("subject", Text, nullable=False),
            Column("body", Text, nullable=False),
            Column("status", String(64), nullable=False),
            Column("provider_message_id", String(512), nullable=True, unique=True),
            Column("thread_id", String(128), nullable=True),
            Column("in_reply_to", String(512), nullable=True),
            Column("references_json", Text, nullable=True),
            Column("last_error", Text, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=True),
        )
        self.suppressions = Table(
            "suppressions",
            self.metadata,
            Column("endpoint", String(512), primary_key=True),
            Column("reason", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("expires_at", DateTime(timezone=True), nullable=True),
        )
        self.inbound_receipts = Table(
            "inbound_receipts",
            self.metadata,
            Column("receipt_key", String(128), primary_key=True),
            Column("provider_message_id", String(512), nullable=True, index=True),
            Column("mailbox_uid", String(128), nullable=True),
            Column("case_id", String(64), nullable=True, index=True),
            Column("status", String(64), nullable=False),
            Column("error", Text, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.worker_heartbeats = Table(
            "worker_heartbeats",
            self.metadata,
            Column("worker_id", String(128), primary_key=True),
            Column("status", String(64), nullable=False),
            Column("details_json", Text, nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.metadata.create_all(self.engine)
        self._upgrade_legacy_schema()

    def _upgrade_legacy_schema(self) -> None:
        """Add nullable mail columns for databases created by the Phase-1 MVP.

        This intentionally handles only additive, backward-compatible changes. A larger
        deployment should replace this helper with Alembic migrations.
        """

        inspector = inspect(self.engine)
        if "outbox" not in inspector.get_table_names():
            return
        existing = {column["name"] for column in inspector.get_columns("outbox")}
        additions = {
            "thread_id": "VARCHAR(128)",
            "in_reply_to": "VARCHAR(512)",
            "references_json": "TEXT",
            "last_error": "TEXT",
            "updated_at": "TIMESTAMP",
        }
        with self.engine.begin() as connection:
            for name, sql_type in additions.items():
                if name not in existing:
                    connection.exec_driver_sql(f"ALTER TABLE outbox ADD COLUMN {name} {sql_type}")

    def ping(self) -> bool:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def save_case(self, case: CaseRecord) -> CaseRecord:
        now = utcnow()
        case.updated_at = now
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(self.cases.c.version).where(self.cases.c.id == case.id)
            ).first()
            if existing:
                current_version = int(existing.version)
                if case.version not in {0, current_version}:
                    raise ConcurrentUpdateError(
                        f"Case {case.id} changed from version {case.version} to {current_version}"
                    )
                new_version = current_version + 1
                case.version = new_version
                result = connection.execute(
                    update(self.cases)
                    .where(self.cases.c.id == case.id, self.cases.c.version == current_version)
                    .values(version=new_version, state_json=case.model_dump_json(), updated_at=now)
                )
                if result.rowcount != 1:
                    raise ConcurrentUpdateError(f"Case {case.id} was updated concurrently")
            else:
                case.version = 1
                connection.execute(
                    insert(self.cases).values(
                        id=case.id,
                        version=case.version,
                        state_json=case.model_dump_json(),
                        created_at=case.created_at,
                        updated_at=now,
                    )
                )
        return case

    def get_case(self, case_id: str) -> CaseRecord | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(self.cases.c.state_json).where(self.cases.c.id == case_id)).first()
        return CaseRecord.model_validate_json(row.state_json) if row else None

    def get_case_by_token(self, token: str) -> CaseRecord | None:
        normalized = token.strip().upper()
        matches = [case for case in self.list_cases() if case_token(case.id) == normalized]
        return matches[0] if len(matches) == 1 else None

    def list_cases(self) -> list[CaseRecord]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(self.cases.c.state_json).order_by(self.cases.c.updated_at.desc())).all()
        return [CaseRecord.model_validate_json(row.state_json) for row in rows]

    def append_event(self, case_id: str, event_type: str, payload: dict[str, Any] | None = None) -> CaseEvent:
        for attempt in range(3):
            try:
                with self.engine.begin() as connection:
                    current = connection.execute(
                        select(func.max(self.events.c.sequence)).where(self.events.c.case_id == case_id)
                    ).scalar_one_or_none()
                    sequence = int(current or 0) + 1
                    event = CaseEvent(
                        case_id=case_id,
                        sequence=sequence,
                        event_type=event_type,
                        payload=payload or {},
                    )
                    connection.execute(
                        insert(self.events).values(
                            case_id=case_id,
                            sequence=sequence,
                            event_id=event.id,
                            event_type=event.event_type,
                            payload_json=json.dumps(event.payload, default=str, sort_keys=True),
                            created_at=event.created_at,
                        )
                    )
                return event
            except IntegrityError:
                if attempt == 2:
                    raise
        raise RuntimeError("unreachable")

    def list_events(self, case_id: str) -> list[CaseEvent]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(self.events).where(self.events.c.case_id == case_id).order_by(self.events.c.sequence)
            ).mappings().all()
        return [
            CaseEvent(
                id=row["event_id"],
                case_id=row["case_id"],
                sequence=row["sequence"],
                event_type=row["event_type"],
                payload=json.loads(row["payload_json"]),
                created_at=_aware(row["created_at"]),
            )
            for row in rows
        ]

    def reserve_outbox(self, record: OutboxRecord) -> tuple[OutboxRecord, bool]:
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    insert(self.outbox).values(
                        id=record.id,
                        case_id=record.case_id,
                        action_id=record.action_id,
                        idempotency_key=record.idempotency_key,
                        recipient=record.recipient,
                        sender=record.sender,
                        subject=record.subject,
                        body=record.body,
                        status=record.status,
                        provider_message_id=record.provider_message_id,
                        thread_id=record.thread_id or None,
                        in_reply_to=record.in_reply_to,
                        references_json=json.dumps(record.references),
                        last_error=record.last_error,
                        created_at=record.created_at,
                        updated_at=record.updated_at,
                    )
                )
            return record, True
        except IntegrityError:
            existing = self.get_outbox_by_key(record.idempotency_key)
            if existing is None:
                raise
            return existing, False

    def record_outbox(self, record: OutboxRecord) -> OutboxRecord:
        existing, _ = self.reserve_outbox(record)
        return existing

    def update_outbox_status(
        self,
        idempotency_key: str,
        status: str,
        *,
        provider_message_id: str | None = None,
        last_error: str | None = None,
    ) -> OutboxRecord:
        values: dict[str, Any] = {"status": status, "last_error": last_error, "updated_at": utcnow()}
        if provider_message_id is not None:
            values["provider_message_id"] = provider_message_id
        with self.engine.begin() as connection:
            result = connection.execute(
                update(self.outbox)
                .where(self.outbox.c.idempotency_key == idempotency_key)
                .values(**values)
            )
            if result.rowcount != 1:
                raise KeyError(idempotency_key)
        record = self.get_outbox_by_key(idempotency_key)
        if record is None:
            raise KeyError(idempotency_key)
        return record

    def get_outbox_by_key(self, idempotency_key: str) -> OutboxRecord | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(self.outbox).where(self.outbox.c.idempotency_key == idempotency_key)
            ).mappings().first()
        return _outbox_from_row(row) if row else None

    def get_outbox_by_provider_message_id(self, provider_message_id: str) -> OutboxRecord | None:
        normalized = provider_message_id.strip()
        if not normalized:
            return None
        with self.engine.connect() as connection:
            row = connection.execute(
                select(self.outbox).where(self.outbox.c.provider_message_id == normalized)
            ).mappings().first()
        return _outbox_from_row(row) if row else None

    def list_outbox(self) -> list[OutboxRecord]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(self.outbox).order_by(self.outbox.c.created_at.desc())).mappings().all()
        return [_outbox_from_row(row) for row in rows]

    def record_inbound_receipt(
        self,
        receipt_key: str,
        *,
        provider_message_id: str | None,
        mailbox_uid: str | None,
        status: str,
        case_id: str | None = None,
        error: str | None = None,
    ) -> bool:
        now = utcnow()
        values = {
            "receipt_key": receipt_key,
            "provider_message_id": provider_message_id,
            "mailbox_uid": mailbox_uid,
            "case_id": case_id,
            "status": status,
            "error": error,
            "created_at": now,
            "updated_at": now,
        }
        try:
            with self.engine.begin() as connection:
                connection.execute(insert(self.inbound_receipts).values(**values))
            return True
        except IntegrityError:
            with self.engine.begin() as connection:
                connection.execute(
                    update(self.inbound_receipts)
                    .where(self.inbound_receipts.c.receipt_key == receipt_key)
                    .values(
                        provider_message_id=provider_message_id,
                        mailbox_uid=mailbox_uid,
                        case_id=case_id,
                        status=status,
                        error=error,
                        updated_at=now,
                    )
                )
            return False

    def has_inbound_receipt(self, receipt_key: str) -> bool:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(self.inbound_receipts.c.receipt_key).where(
                    self.inbound_receipts.c.receipt_key == receipt_key,
                    self.inbound_receipts.c.status == "processed",
                )
            ).first()
        return row is not None

    def set_worker_heartbeat(self, heartbeat: WorkerHeartbeat) -> WorkerHeartbeat:
        values = {
            "worker_id": heartbeat.worker_id,
            "status": heartbeat.status,
            "details_json": json.dumps(heartbeat.details, default=str, sort_keys=True),
            "updated_at": heartbeat.updated_at,
        }
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(self.worker_heartbeats.c.worker_id).where(
                    self.worker_heartbeats.c.worker_id == heartbeat.worker_id
                )
            ).first()
            if existing:
                connection.execute(
                    update(self.worker_heartbeats)
                    .where(self.worker_heartbeats.c.worker_id == heartbeat.worker_id)
                    .values(**values)
                )
            else:
                connection.execute(insert(self.worker_heartbeats).values(**values))
        return heartbeat

    def get_worker_heartbeat(self, worker_id: str) -> WorkerHeartbeat | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(self.worker_heartbeats).where(self.worker_heartbeats.c.worker_id == worker_id)
            ).mappings().first()
        if not row:
            return None
        return WorkerHeartbeat(
            worker_id=row["worker_id"],
            status=row["status"],
            details=json.loads(row["details_json"]),
            updated_at=_aware(row["updated_at"]),
        )

    def add_suppression(
        self,
        endpoint: str,
        reason: str,
        expires_at: datetime | None = None,
    ) -> None:
        normalized = endpoint.strip().lower()
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(self.suppressions.c.endpoint).where(self.suppressions.c.endpoint == normalized)
            ).first()
            values = {
                "endpoint": normalized,
                "reason": reason,
                "created_at": utcnow(),
                "expires_at": expires_at,
            }
            if existing:
                connection.execute(
                    update(self.suppressions).where(self.suppressions.c.endpoint == normalized).values(**values)
                )
            else:
                connection.execute(insert(self.suppressions).values(**values))

    def is_suppressed(self, endpoint: str) -> bool:
        normalized = endpoint.strip().lower()
        with self.engine.connect() as connection:
            row = connection.execute(
                select(self.suppressions.c.expires_at).where(self.suppressions.c.endpoint == normalized)
            ).first()
        if row is None:
            return False
        expires_at = _aware(row.expires_at) if row.expires_at else None
        return expires_at is None or expires_at > utcnow()

    def clear(self) -> None:
        """Delete all data. Intended for tests and local demos only."""

        with self.engine.begin() as connection:
            connection.execute(delete(self.events))
            connection.execute(delete(self.outbox))
            connection.execute(delete(self.inbound_receipts))
            connection.execute(delete(self.worker_heartbeats))
            connection.execute(delete(self.suppressions))
            connection.execute(delete(self.cases))


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _outbox_from_row(row: Any) -> OutboxRecord:
    references_raw = row.get("references_json") if hasattr(row, "get") else None
    return OutboxRecord(
        id=row["id"],
        case_id=row["case_id"],
        action_id=row["action_id"],
        idempotency_key=row["idempotency_key"],
        recipient=row["recipient"],
        sender=row["sender"],
        subject=row["subject"],
        body=row["body"],
        status=row["status"],
        provider_message_id=row["provider_message_id"],
        thread_id=row.get("thread_id") or "",
        in_reply_to=row.get("in_reply_to"),
        references=json.loads(references_raw) if references_raw else [],
        last_error=row.get("last_error"),
        created_at=_aware(row["created_at"]),
        updated_at=_aware(row.get("updated_at") or row["created_at"]),
    )
