# SourceLoop architecture

## Purpose

SourceLoop acquires intelligence that does not already exist in a usable public record. An unknown becomes a typed question; the system identifies an appropriate source, prepares a transparent conversation, records the answer, separates fact from opinion or intention, and updates a temporal graph with provenance and an expiry policy.

```text
Unknown / requirement
        ↓
Nine-stage practitioner
        ↓
Internal specialist swarm
        ↓
Proposed external action
        ↓
Deterministic policy + human approval
        ↓
One counterparty conversation
        ↓
Dual extraction + validation
        ↓
Claim / quote / referral ledger
        ↓
NetworkX / rustworkx / PyG projection
```

## Authority boundaries

The system has four deliberately different authorities.

### 1. Case runtime

The practitioner state machine owns stage progression, waiting conditions, retry boundaries, stopping criteria, and event receipts. It is the authoritative source for what the system believes it is currently doing.

### 2. Agent runtime

Hermes, OpenClaw, future OpenAI agents, local models, or deterministic workers may propose interpretations and actions. Their output is untrusted until schema validation and policy checks succeed. An agent runtime cannot send mail, mutate suppression state, accept a quote, or commit a claim by itself.

### 3. Side-effect services

Mail, CRM, browser, calendar, and purchasing adapters are invoked only through typed action proposals. Every proposal carries approval status, idempotency key, recipient, case, purpose, and policy receipt.

### 4. Evidence and intelligence ledger

Original messages and attachments are immutable evidence. Claims and quotes are derived objects linked back to evidence. Narrative agent memory is never treated as a current quote or verified fact.

## Practitioner stages

| Stage | Primary purpose | Typical workers |
|---|---|---|
| `ORIENT` | Restate objective and requester authority | case supervisor |
| `RECONCILE_HORIZON` | Resolve deadline, geography, budget, quote type, and risk | horizon critic, risk classifier |
| `ASSESS_PREPARE` | Compile requirements and identify unknowns | requirement compiler, missing-information critic |
| `DECIDE_NEXT` | Decide whether direct-source acquisition is necessary | completion judge |
| `HOW` | Select sources, contact routes, channels, and evidence standards | web/GIS/registry/relationship scouts, contact resolver |
| `ACT` | Compose one coherent message and propose a side effect | conversation owner, policy critic |
| `VERIFY` | Interpret replies, reconcile extractors, and detect missing terms | extractor A/B, validator, adversarial auditor |
| `INTEGRATE_COMMIT` | Create approved claims, quotes, referrals, and graph edges | graph curator |
| `ROUTE` | Complete, seek more evidence, re-contact, or escalate | completion judge |

## Swarm topology

Persistent named practitioners own cases and relationships. Ephemeral workers receive bounded tasks and return structured results. External recipients never receive independent messages from the internal swarm.

```text
Case supervisor
  ├─ requirement compiler
  ├─ GIS scout
  ├─ registry scout
  ├─ relationship scout
  ├─ contact resolver
  ├─ message composer
  ├─ policy critic
  ├─ extractor A
  ├─ extractor B
  ├─ quote/claim auditor
  └─ graph curator
```

The current MVP executes workers concurrently inside a bounded thread pool. A production implementation can replace this coordinator with Temporal, LangGraph, Paperclip-managed employees, or the existing Universal Loop Engine without changing the `AgentRuntime` or case contracts.

## Runtime adapters

### Mock

The deterministic adapter powers tests and demos. It emits explicit role receipts and uses no external network or model.

### Hermes

The adapter invokes one profile-scoped Hermes chat turn:

```text
hermes -p <profile> chat -q <prompt>
```

The prompt includes the role, case snapshot, and required JSON output. SourceLoop parses the final JSON object and records stdout/stderr as a run receipt. The adapter has no mail tool in SourceLoop; external effects remain behind the action ledger.

### OpenClaw

The adapter invokes one named agent through the gateway:

```text
openclaw agent --agent <id> --message-file <file> --json
```

It intentionally omits `--deliver`. The command is used as an internal practitioner turn rather than an external messaging shortcut.

### Adapter contract

```python
class AgentRuntime(Protocol):
    def invoke(self, request: AgentRequest) -> AgentResult: ...
```

This prevents any one framework from becoming the domain model. New adapters can target local models, OpenAI Agents SDK, Microsoft Agent Framework, Paperclip-managed workers, Agent Zero, or browser operators.

## Persistence

The repository uses four core tables:

- `cases`: versioned JSON snapshots for fast recovery.
- `case_events`: immutable ordered receipts.
- `outbox`: idempotent outbound messages and delivery status.
- `suppressions`: permanent or expiring no-contact endpoints.

SQLite is suitable for tests and a single-user demo. Docker Compose uses PostgreSQL/PostGIS. Production should add migrations, encryption, tenant-scoped row-level access, attachment object storage, and a dedicated immutable audit sink.

## Graph projections

The authoritative store is not a model tensor. SourceLoop materializes projections:

- NetworkX `MultiDiGraph` for inspection and explainability.
- GeoJSON for the operator map.
- City2Graph-compatible GeoDataFrames for geospatial conversion.
- rustworkx for larger graph algorithms.
- PyTorch Geometric for embeddings, link prediction, recommendation, and anomaly detection.

Stable IDs map every projected node back to the source ledger. Full messages, permissions, and contractual text remain outside tensors.

## Vertical packs

A vertical pack supplies defaults rather than embedding industry knowledge into orchestration code. Each pack may define:

- required and optional requirement fields;
- specialist roles;
- discovery sources;
- contact and follow-up limits;
- question templates;
- claim or quote schemas;
- completion criteria;
- expiry policies;
- prohibited actions.

The MVP includes civic intelligence, commercial facilities quoting, and BPO quoting. The same contract can support healthcare access, insurance agency verification, manufacturing RFQs, construction projects, logistics capacity, government contracting, and supplier qualification.

## Production extension points

1. OAuth-based Gmail and Microsoft 365 gateways.
2. Inbound webhook signature verification and attachment malware scanning.
3. Per-tenant encryption and data-retention policies.
4. A human review queue with role-based authorization.
5. Durable timers and external-event subscriptions.
6. Search, GIS, registry, browser, and CRM connectors.
7. Historical evaluation and adversarial test harnesses.
8. Permissioned reusable-answer scopes and re-verification schedules.
9. City2Graph datasets built from authoritative PostGIS views.
10. Paperclip organization controls and Hermes/OpenClaw employee profiles.
