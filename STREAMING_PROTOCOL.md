# Streaming Protocol

Status: finite reference semantics 0.1
Implementation: `solutiongraph.streaming`

The reference stream engine exists to make event-time contracts testable with
no external service. It is single-process, finite-input, and deterministic in
arrival order. It is not a replacement for Beam, Flink, Kafka Streams, or a
durable distributed state backend.

## Records and policy

`StreamEvent` carries a unique namespaced ID, key, finite event timestamp,
JSON-compatible value, optional source, and string headers. `WindowPolicy`
defines size, slide, watermark delay, allowed lateness, optional early trigger
count, and accumulating or discarding mode.

`size == slide` creates tumbling windows. `size > slide` creates sliding
windows, and one event may belong to multiple windows. Nonpositive windows,
negative lateness/delay, duplicate event IDs, and nonportable values fail before
processing.

## Watermark and lateness

For each arrival:

```text
watermark = max(event_time_seen) - watermark_delay
```

An event older than the previous watermark minus allowed lateness is dropped
and named in the receipt. An event behind the previous watermark but inside
the lateness allowance is accepted as late.

When the watermark passes a window end, the engine emits an on-time result. A
late accepted event emits a new revision. In accumulating mode that revision
references the previous emission through `retracts`; downstream consumers can
replace the earlier result. At finite-input completion, the engine advances a
finite final watermark far enough to close known windows and emits any pending
final revision.

## Evidence

Each `StreamEmission` records key, window bounds, revision, reason
(`early`, `on-time`, `late`, or `final`), contributing event IDs, observed
watermark, value, and optional retraction target. `StreamRunReceipt` binds the
policy and processor digests and counts inputs, accepted events, late accepted
events, too-late drops, emissions, final watermark, and dropped event IDs.

## Production adapter requirements

A production streaming runtime must additionally define:

- durable keyed state and checkpoint/savepoint identity;
- source offsets, replay, deduplication, and idempotent/exactly-once sink rules;
- watermark idleness, partition merging, backpressure, cancellation, and scale;
- schema evolution, state migration, retention, and compaction;
- processing-time triggers and timers where required;
- effect authority, secrets, tenancy, telemetry, and recovery objectives.

Those features belong behind a runtime adapter. They must not alter the semantic
ports, acceptance contract, or evidence identity of the graph.
