"""Generic IMAP ingestion, MIME parsing, thread correlation, and case resumption."""

from __future__ import annotations

import hashlib
import imaplib
import re
import ssl
from dataclasses import dataclass, field
from email import policy
from email.header import decode_header
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr
from html.parser import HTMLParser
from typing import Protocol

from .config import Settings
from .domain import InboundEmail, MailboxSyncResult, new_id, stable_key
from .evidence import EvidenceStore
from .repository import Repository

_SUBJECT_TOKEN_RE = re.compile(r"\[SL:(?P<token>[A-F0-9]{12})\]", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class RawMailboxMessage:
    uid: str
    raw: bytes


@dataclass(frozen=True, slots=True)
class ParsedAttachment:
    filename: str
    content_type: str
    payload: bytes


@dataclass(frozen=True, slots=True)
class ParsedInboundMessage:
    message_id: str | None
    sender: str
    recipients: tuple[str, ...]
    subject: str
    body: str
    in_reply_to: str | None
    references: tuple[str, ...]
    headers: dict[str, str]
    attachments: tuple[ParsedAttachment, ...] = field(default_factory=tuple)


class MailboxClient(Protocol):
    def fetch_messages(self) -> list[RawMailboxMessage]: ...

    def mark_seen(self, uid: str) -> None: ...

    def close(self) -> None: ...


class ImapMailboxClient:
    """Small standards-based IMAP client suitable for Gmail app passwords and normal IMAP servers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: imaplib.IMAP4 | imaplib.IMAP4_SSL | None = None

    def _connect(self) -> imaplib.IMAP4 | imaplib.IMAP4_SSL:
        if self.client is not None:
            return self.client
        if self.settings.imap_ssl:
            client: imaplib.IMAP4 | imaplib.IMAP4_SSL = imaplib.IMAP4_SSL(
                self.settings.imap_host,
                self.settings.imap_port,
                ssl_context=ssl.create_default_context(),
            )
        else:
            client = imaplib.IMAP4(self.settings.imap_host, self.settings.imap_port)
            if self.settings.imap_starttls:
                client.starttls(ssl_context=ssl.create_default_context())
        if self.settings.imap_username:
            client.login(self.settings.imap_username, self.settings.imap_password)
        status, _ = client.select(self.settings.imap_folder)
        if status != "OK":
            client.logout()
            raise RuntimeError(f"Could not select IMAP folder {self.settings.imap_folder!r}")
        self.client = client
        return client

    def fetch_messages(self) -> list[RawMailboxMessage]:
        client = self._connect()
        status, data = client.uid("search", None, self.settings.imap_search_criterion)
        if status != "OK":
            raise RuntimeError(f"IMAP search failed with status {status}")
        raw_uids = data[0].split() if data and data[0] else []
        uids = raw_uids[-self.settings.imap_max_messages :]
        messages: list[RawMailboxMessage] = []
        for raw_uid in uids:
            uid = raw_uid.decode("ascii", errors="replace")
            status, parts = client.uid("fetch", raw_uid, "(BODY.PEEK[])")
            if status != "OK":
                raise RuntimeError(f"IMAP fetch failed for UID {uid} with status {status}")
            payload = next(
                (
                    part[1]
                    for part in parts
                    if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], bytes)
                ),
                None,
            )
            if payload is not None:
                messages.append(RawMailboxMessage(uid=uid, raw=payload))
        return messages

    def mark_seen(self, uid: str) -> None:
        client = self._connect()
        status, _ = client.uid("store", uid.encode("ascii"), "+FLAGS.SILENT", "(\\Seen)")
        if status != "OK":
            raise RuntimeError(f"Could not mark IMAP UID {uid} as seen")

    def close(self) -> None:
        client, self.client = self.client, None
        if client is None:
            return
        try:
            client.close()
        except (imaplib.IMAP4.error, OSError):
            pass
        try:
            client.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


class MailboxService:
    """Fetches replies, correlates them to outbound messages, and resumes cases."""

    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        engine: object,
        evidence: EvidenceStore,
        client_factory: type[MailboxClient] | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.engine = engine
        self.evidence = evidence
        self.client_factory = client_factory

    def sync_once(self, client: MailboxClient | None = None) -> MailboxSyncResult:
        result = MailboxSyncResult()
        if not self.settings.mailbox_enabled and client is None:
            return result
        owned_client = client is None
        mailbox = client or ImapMailboxClient(self.settings)
        try:
            messages = mailbox.fetch_messages()
            result.fetched = len(messages)
            for raw_message in messages:
                try:
                    state = self._process_one(raw_message)
                    if state == "processed":
                        result.processed += 1
                    elif state == "duplicate":
                        result.duplicates += 1
                    else:
                        result.unmatched += 1
                    if self.settings.imap_mark_seen:
                        mailbox.mark_seen(raw_message.uid)
                except Exception as exc:  # noqa: BLE001 - preserve per-message failures and continue
                    result.failed += 1
                    result.errors.append(f"UID {raw_message.uid}: {exc}")
            return result
        finally:
            if owned_client:
                mailbox.close()

    def _process_one(self, raw_message: RawMailboxMessage) -> str:
        parsed = parse_email(raw_message.raw)
        receipt_key = _receipt_key(parsed.message_id, raw_message.raw)
        if self.repository.has_inbound_receipt(receipt_key):
            return "duplicate"

        correlation = correlate_message(parsed, self.repository)
        if correlation is None:
            self.repository.record_inbound_receipt(
                receipt_key,
                provider_message_id=parsed.message_id,
                mailbox_uid=raw_message.uid,
                status="unmatched",
                error="No unambiguous SourceLoop case or outbound message matched this email.",
            )
            return "unmatched"

        case_id, thread_id = correlation
        evidence_id = new_id("evidence")
        raw_path = self.evidence.store_raw_email(case_id, evidence_id, raw_message.raw)
        attachments = [
            self.evidence.store_attachment(
                case_id,
                evidence_id,
                attachment.filename,
                attachment.content_type,
                attachment.payload,
            )
            for attachment in parsed.attachments
        ]
        inbound = InboundEmail(
            case_id=case_id,
            thread_id=thread_id,
            sender=parsed.sender,
            subject=parsed.subject,
            body=parsed.body,
            provider_message_id=parsed.message_id,
            in_reply_to=parsed.in_reply_to,
            references=list(parsed.references),
            headers=parsed.headers,
            evidence_id=evidence_id,
            raw_evidence_path=raw_path,
            attachments=attachments,
        )
        # The engine contract is deliberately duck-typed so mailbox parsing remains isolated.
        self.engine.record_inbound(inbound)  # type: ignore[attr-defined]
        self.repository.record_inbound_receipt(
            receipt_key,
            provider_message_id=parsed.message_id,
            mailbox_uid=raw_message.uid,
            case_id=case_id,
            status="processed",
        )
        return "processed"


def correlate_message(parsed: ParsedInboundMessage, repository: Repository) -> tuple[str, str] | None:
    """Resolve a reply using message references, explicit headers, subject token, then sender."""

    reference_ids = [identifier for identifier in [parsed.in_reply_to, *parsed.references] if identifier]
    for reference in reversed(reference_ids):
        outbound = repository.get_outbox_by_provider_message_id(reference)
        if outbound:
            return outbound.case_id, outbound.thread_id or stable_key(outbound.case_id, outbound.recipient)[:24]

    explicit_case = parsed.headers.get("x-sourceloop-case-id")
    explicit_thread = parsed.headers.get("x-sourceloop-thread-id")
    if explicit_case and repository.get_case(explicit_case):
        return explicit_case, explicit_thread or stable_key(explicit_case, parsed.sender)[:24]

    token_match = _SUBJECT_TOKEN_RE.search(parsed.subject)
    if token_match:
        case = repository.get_case_by_token(token_match.group("token"))
        if case:
            matching = next(
                (
                    interaction
                    for interaction in reversed(case.interactions)
                    if interaction.direction.value == "outbound" and interaction.endpoint == parsed.sender
                ),
                None,
            )
            return case.id, matching.thread_id if matching else f"thread_{stable_key(case.id, parsed.sender)[:20]}"

    candidates = []
    for case in repository.list_cases():
        if case.status.value not in {"waiting_external", "waiting_approval", "active"}:
            continue
        if any(contact.endpoint == parsed.sender for contact in case.contacts):
            candidates.append(case)
    if len(candidates) == 1:
        case = candidates[0]
        matching = next(
            (
                interaction
                for interaction in reversed(case.interactions)
                if interaction.direction.value == "outbound" and interaction.endpoint == parsed.sender
            ),
            None,
        )
        return case.id, matching.thread_id if matching else f"thread_{stable_key(case.id, parsed.sender)[:20]}"
    return None


def parse_email(raw_message: bytes) -> ParsedInboundMessage:
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    sender = parseaddr(_decode_header(message.get("From", "")))[1].strip().lower()
    if not sender:
        raise ValueError("Inbound message has no usable From address")
    recipients = tuple(
        address.lower()
        for _, address in getaddresses(
            [_decode_header(message.get(header, "")) for header in ("To", "Cc", "Delivered-To")]
        )
        if address
    )
    subject = _decode_header(message.get("Subject", ""))
    message_id = _normalize_message_id(message.get("Message-ID"))
    in_reply_to = _normalize_message_id(message.get("In-Reply-To"))
    references = tuple(
        identifier
        for identifier in (_normalize_message_id(value) for value in _split_references(message.get("References")))
        if identifier
    )
    body, attachments = _extract_body_and_attachments(message)
    relevant_headers = {
        header.lower(): _decode_header(message.get(header, ""))
        for header in (
            "Date",
            "From",
            "To",
            "Cc",
            "Message-ID",
            "In-Reply-To",
            "References",
            "X-SourceLoop-Case-ID",
            "X-SourceLoop-Thread-ID",
            "X-SourceLoop-Action-ID",
        )
        if message.get(header) is not None
    }
    return ParsedInboundMessage(
        message_id=message_id,
        sender=sender,
        recipients=recipients,
        subject=subject,
        body=_strip_reply_history(body).strip(),
        in_reply_to=in_reply_to,
        references=references,
        headers=relevant_headers,
        attachments=tuple(attachments),
    )


def _extract_body_and_attachments(message: Message) -> tuple[str, list[ParsedAttachment]]:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[ParsedAttachment] = []
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.is_multipart():
            continue
        disposition = part.get_content_disposition()
        filename = _decode_header(part.get_filename() or "")
        payload = part.get_payload(decode=True) or b""
        if disposition == "attachment" or filename:
            attachments.append(
                ParsedAttachment(
                    filename=filename or "attachment.bin",
                    content_type=part.get_content_type(),
                    payload=payload,
                )
            )
            continue
        content_type = part.get_content_type()
        charset = part.get_content_charset() or "utf-8"
        try:
            text_value = payload.decode(charset, errors="replace")
        except LookupError:
            text_value = payload.decode("utf-8", errors="replace")
        if content_type == "text/plain":
            plain_parts.append(text_value)
        elif content_type == "text/html":
            html_parts.append(_html_to_text(text_value))
    body = "\n\n".join(part.strip() for part in plain_parts if part.strip())
    if not body:
        body = "\n\n".join(part.strip() for part in html_parts if part.strip())
    return body, attachments


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    chunks: list[str] = []
    for chunk, encoding in decode_header(value):
        if isinstance(chunk, bytes):
            chunks.append(chunk.decode(encoding or "utf-8", errors="replace"))
        else:
            chunks.append(chunk)
    return "".join(chunks)


def _normalize_message_id(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _decode_header(value).strip()
    match = re.search(r"<[^>]+>", normalized)
    return match.group(0) if match else normalized or None


def _split_references(value: str | None) -> list[str]:
    if not value:
        return []
    decoded = _decode_header(value)
    identifiers = re.findall(r"<[^>]+>", decoded)
    return identifiers or decoded.split()


def _receipt_key(message_id: str | None, raw_message: bytes) -> str:
    if message_id:
        return stable_key("inbound-message-id", message_id)
    return hashlib.sha256(b"inbound-message\x00" + raw_message).hexdigest()


def _strip_reply_history(body: str) -> str:
    markers = (
        "\nOn ",
        "\nFrom:",
        "\n-----Original Message-----",
        "\n________________________________",
    )
    positions = [position for marker in markers if (position := body.find(marker)) >= 0]
    return body[: min(positions)] if positions else body


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.chunks.append(data.strip())


def _html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return "\n".join(parser.chunks)
