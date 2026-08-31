"""SQL-backed case snapshots and immutable event/outbox ledgers."""

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
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .domain import CaseEvent, CaseRecord, OutboxRecord, utcnow


class Repository:
    """Small persistence layer supporting SQLite and PostgreSQL URLs."""

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
            Column("provider_message_id", String(512), nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.suppressions = Table(
            "suppressions",
            self.metadata,
            Column("endpoint", String(512), primary_key=True),
            Column("reason", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("expires_at", DateTime(timezone=True), nullable=True),
        )
        self.metadata.create_all(self.engine)

    def save_case(self, case: CaseRecord) -> CaseRecord:
        now = utcnow()
        case.updated_at = now
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(self.cases.c.version, self.cases.c.created_at).where(self.cases.c.id == case.id)
            ).first()
            if existing:
                case.version = int(existing.version) + 1
                connection.execute(
                    update(self.cases)
                    .where(self.cases.c.id == case.id)
                    .values(
                        version=case.version,
                        state_json=case.model_dump_json(),
                        updated_at=now,
                    )
                )
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
        if row is None:
            return None
        return CaseRecord.model_validate_json(row.state_json)

    def list_cases(self) -> list[CaseRecord]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(self.cases.c.state_json).order_by(self.cases.c.updated_at.desc())).all()
        return [CaseRecord.model_validate_json(row.state_json) for row in rows]

    def append_event(self, case_id: str, event_type: str, payload: dict[str, Any] | None = None) -> CaseEvent:
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

    def list_events(self, case_id: str) -> list[CaseEvent]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(self.events).where(self.events.c.case_id == case_id).order_by(self.events.c.sequence)
            ).mappings()
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

    def record_outbox(self, record: OutboxRecord) -> OutboxRecord:
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
                        created_at=record.created_at,
                    )
                )
            return record
        except IntegrityError:
            existing = self.get_outbox_by_key(record.idempotency_key)
            if existing is None:
                raise
            return existing

    def get_outbox_by_key(self, idempotency_key: str) -> OutboxRecord | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(self.outbox).where(self.outbox.c.idempotency_key == idempotency_key)
            ).mappings().first()
        return _outbox_from_row(row) if row else None

    def list_outbox(self) -> list[OutboxRecord]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(self.outbox).order_by(self.outbox.c.created_at.desc())).mappings()
            return [_outbox_from_row(row) for row in rows]

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
            connection.execute(delete(self.suppressions))
            connection.execute(delete(self.cases))


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _outbox_from_row(row: Any) -> OutboxRecord:
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
        created_at=_aware(row["created_at"]),
    )
