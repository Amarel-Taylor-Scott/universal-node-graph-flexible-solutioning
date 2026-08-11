"""Bounded reference semantics for event-time streams, windows, and late data.

The engine is deliberately single-process and finite.  It is a conformance
adapter for testing node contracts and watermark behavior, not a replacement
for a distributed streaming runtime such as Beam or Flink.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from math import floor, isfinite
from typing import Any

from solutiongraph.model import ID_RE, canonical_json, sha256_digest

STREAM_MODEL_VERSION = "0.1"


@dataclass(frozen=True)
class StreamEvent:
    id: str
    key: str
    event_time: float
    value: Any
    source: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)

    def validate(self, path: str = "event") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be namespaced")
        if not isinstance(self.key, str) or not self.key:
            problems.append(f"{path}.key must not be empty")
        if not isfinite(self.event_time):
            problems.append(f"{path}.event_time must be finite")
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.headers.items()):
            problems.append(f"{path}.headers must map strings to strings")
        try:
            canonical_json(self.value)
        except (TypeError, ValueError):
            problems.append(f"{path}.value must be JSON-compatible")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "event_time": self.event_time,
            "value": self.value,
            "source": self.source,
            "headers": dict(self.headers),
        }


@dataclass(frozen=True)
class WindowPolicy:
    id: str
    size: float
    slide: float
    watermark_delay: float = 0.0
    allowed_lateness: float = 0.0
    early_trigger_count: int | None = None
    accumulation: str = "accumulating"

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("window policy id must be namespaced")
        for label, value in (("size", self.size), ("slide", self.slide)):
            if not isfinite(value) or value <= 0:
                problems.append(f"window {label} must be finite and positive")
        for label, value in (
            ("watermark_delay", self.watermark_delay),
            ("allowed_lateness", self.allowed_lateness),
        ):
            if not isfinite(value) or value < 0:
                problems.append(f"window {label} must be finite and non-negative")
        if self.early_trigger_count is not None and self.early_trigger_count <= 0:
            problems.append("early_trigger_count must be positive or null")
        if self.accumulation not in ("accumulating", "discarding"):
            problems.append("accumulation must be accumulating or discarding")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "stream_model_version": STREAM_MODEL_VERSION,
            "id": self.id,
            "size": self.size,
            "slide": self.slide,
            "watermark_delay": self.watermark_delay,
            "allowed_lateness": self.allowed_lateness,
            "early_trigger_count": self.early_trigger_count,
            "accumulation": self.accumulation,
        }


@dataclass(frozen=True)
class StreamEmission:
    id: str
    key: str
    window_start: float
    window_end: float
    revision: int
    reason: str
    value: Any
    event_ids: tuple[str, ...]
    watermark: float
    retracts: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "revision": self.revision,
            "reason": self.reason,
            "value": self.value,
            "event_ids": list(self.event_ids),
            "watermark": self.watermark,
            "retracts": self.retracts,
        }


@dataclass(frozen=True)
class StreamRunReceipt:
    id: str
    policy_digest: str
    processor_digest: str
    input_event_count: int
    accepted_event_count: int
    late_accepted_count: int
    too_late_count: int
    emission_count: int
    final_watermark: float | str
    dropped_event_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stream_model_version": STREAM_MODEL_VERSION,
            "id": self.id,
            "policy_digest": self.policy_digest,
            "processor_digest": self.processor_digest,
            "input_event_count": self.input_event_count,
            "accepted_event_count": self.accepted_event_count,
            "late_accepted_count": self.late_accepted_count,
            "too_late_count": self.too_late_count,
            "emission_count": self.emission_count,
            "final_watermark": self.final_watermark,
            "dropped_event_ids": list(self.dropped_event_ids),
        }


@dataclass(frozen=True)
class StreamResult:
    emissions: tuple[StreamEmission, ...]
    receipt: StreamRunReceipt

    def to_dict(self) -> dict[str, Any]:
        return {
            "emissions": [item.to_dict() for item in self.emissions],
            "receipt": self.receipt.to_dict(),
        }


@dataclass
class _WindowState:
    events: list[StreamEvent] = field(default_factory=list)
    revision: int = 0
    last_emission_id: str = ""
    emitted_event_count: int = 0
    on_time_emitted: bool = False


class ReferenceStreamEngine:
    """Evaluate finite arrival-order events with explicit event-time semantics."""

    @staticmethod
    def _processor_digest(processor: Callable[[tuple[Any, ...]], Any]) -> str:
        try:
            source = inspect.getsource(processor)
        except (OSError, TypeError):
            source = f"{processor.__module__}:{processor.__qualname__}"
        return sha256_digest(source)

    @staticmethod
    def _windows(event_time: float, policy: WindowPolicy) -> tuple[tuple[float, float], ...]:
        latest = floor(event_time / policy.slide) * policy.slide
        count = max(1, int(policy.size / policy.slide) + 1)
        windows = []
        for offset in range(count):
            start = latest - offset * policy.slide
            end = start + policy.size
            if start <= event_time < end:
                windows.append((start, end))
        return tuple(sorted(set(windows)))

    def run(
        self,
        events: tuple[StreamEvent, ...],
        policy: WindowPolicy,
        processor: Callable[[tuple[Any, ...]], Any],
        *,
        run_id: str = "stream.reference-run",
    ) -> StreamResult:
        problems = policy.validate()
        if not ID_RE.fullmatch(run_id):
            problems.append("stream run_id must be namespaced")
        ids = [event.id for event in events]
        if len(ids) != len(set(ids)):
            problems.append("stream event ids must be unique")
        for index, event in enumerate(events):
            problems.extend(event.validate(f"events[{index}]"))
        if problems:
            raise ValueError("invalid stream run: " + "; ".join(problems))

        states: dict[tuple[str, float, float], _WindowState] = {}
        emissions: list[StreamEmission] = []
        dropped: list[str] = []
        max_event_time = float("-inf")
        watermark = float("-inf")
        accepted = 0
        late_accepted = 0

        def emit(
            key: tuple[str, float, float],
            state: _WindowState,
            reason: str,
            current_watermark: float,
        ) -> None:
            source_events = (
                state.events
                if policy.accumulation == "accumulating"
                else state.events[state.emitted_event_count:]
            )
            if not source_events:
                return
            state.revision += 1
            emission_id = (
                f"emission.{run_id.replace(':', '-')}."
                f"{sha256_digest({'key': key, 'revision': state.revision})[7:23]}"
            )
            value = processor(tuple(event.value for event in source_events))
            canonical_json(value)
            emissions.append(StreamEmission(
                id=emission_id,
                key=key[0],
                window_start=key[1],
                window_end=key[2],
                revision=state.revision,
                reason=reason,
                value=value,
                event_ids=tuple(event.id for event in source_events),
                watermark=current_watermark,
                retracts=(
                    state.last_emission_id
                    if state.last_emission_id and policy.accumulation == "accumulating"
                    else ""
                ),
            ))
            state.last_emission_id = emission_id
            state.emitted_event_count = len(state.events)

        def advance(current_watermark: float, *, final: bool = False) -> None:
            for key in sorted(states):
                state = states[key]
                if key[2] <= current_watermark and not state.on_time_emitted:
                    emit(key, state, "final" if final else "on-time", current_watermark)
                    state.on_time_emitted = True
                elif final and len(state.events) > state.emitted_event_count:
                    emit(key, state, "final", current_watermark)

        for event in events:
            previous_watermark = watermark
            max_event_time = max(max_event_time, event.event_time)
            watermark = max_event_time - policy.watermark_delay
            if event.event_time < previous_watermark - policy.allowed_lateness:
                dropped.append(event.id)
                advance(watermark)
                continue
            is_late = event.event_time < previous_watermark
            accepted += 1
            late_accepted += int(is_late)
            for start, end in self._windows(event.event_time, policy):
                key = (event.key, start, end)
                state = states.setdefault(key, _WindowState())
                state.events.append(event)
                if state.on_time_emitted:
                    emit(key, state, "late", watermark)
                elif (
                    policy.early_trigger_count is not None
                    and len(state.events) - state.emitted_event_count
                    >= policy.early_trigger_count
                ):
                    emit(key, state, "early", watermark)
            advance(watermark)

        final_watermark = (
            max_event_time + policy.size + policy.allowed_lateness
            if events
            else 0.0
        )
        advance(final_watermark, final=True)
        processor_digest = self._processor_digest(processor)
        receipt = StreamRunReceipt(
            id=run_id,
            policy_digest=policy.digest,
            processor_digest=processor_digest,
            input_event_count=len(events),
            accepted_event_count=accepted,
            late_accepted_count=late_accepted,
            too_late_count=len(dropped),
            emission_count=len(emissions),
            final_watermark=final_watermark,
            dropped_event_ids=tuple(dropped),
        )
        return StreamResult(tuple(emissions), receipt)


__all__ = [
    "ReferenceStreamEngine",
    "STREAM_MODEL_VERSION",
    "StreamEmission",
    "StreamEvent",
    "StreamResult",
    "StreamRunReceipt",
    "WindowPolicy",
]
