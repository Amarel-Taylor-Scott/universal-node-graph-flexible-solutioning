# SourceLoop 0.2 architecture

## System boundaries

SourceLoop separates reasoning from authority. An agent may suggest whom to contact, what to ask, and how to interpret a reply. It may not bypass the action ledger, policy engine, approval state, suppression registry, or evidence commit path.

```text
React/Nginx operator console
             │
             ▼
FastAPI case and approval control plane
             │
    ┌────────┼─────────┐
    ▼        ▼         ▼
practitioner policy   graph projector
swarm        engine   NetworkX/GeoJSON/City2Graph
    │        │
    └────┬───┘
         ▼
PostgreSQL/PostGIS state + event/outbox/inbound ledgers
         │
  ┌──────┴───────────┐
  ▼                  ▼
SMTP gateway      IMAP worker
  │                  │
  └──── counterparty ┘
         conversation
         │
         ▼
immutable RFC 822 and quarantined attachment volume
```

## Services

### `web`

A production Vite build served by an unprivileged Nginx process. Nginx serves the single-page application and proxies `/api`, `/health`, `/docs`, and `/openapi.json` to the API over an internal Docker network.

### `api`

The authoritative synchronous control plane. It creates cases, advances the nine-stage practitioner, records approvals, dispatches allowed actions, receives normalized inbound messages, and exposes intelligence and graph projections.

### `worker`

A separately scalable long-running process. It polls an IMAP mailbox, parses MIME messages, correlates them to cases, stores raw evidence, records deduplication receipts, and resumes the relevant practitioner. It writes a heartbeat to the database for health monitoring.

### `db`

PostgreSQL/PostGIS. Version 0.2 stores typed case snapshots as JSON plus separate ordered event, outbox, inbound-receipt, suppression, and worker-heartbeat tables. The repository layer performs additive startup upgrades for the initial schema. A later multi-tenant release should move these upgrades into explicit migrations and normalized tenant-scoped tables.

### Evidence volume

Original email bytes and attachment bytes are stored outside model prompts and database JSON. Attachments receive hashes, safe names, size enforcement, and `stored_quarantined` state. No attachment is executed or publicly served.

## Outbound delivery transaction

The SMTP gateway follows this sequence:

1. Evaluate deterministic policy immediately before the side effect.
2. Check approval, suppression, contact ceilings, disclosure, follow-up limits, and configuration.
3. Generate a provider message ID and reserve an outbox row using the action idempotency key.
4. Construct an RFC-compliant message with case/thread headers and reply metadata.
5. Connect through SMTP SSL, STARTTLS, or plain SMTP according to configuration.
6. Update the outbox state to `sent` after the server accepts the message.
7. Mark ambiguous transport failures as `delivery_unknown` rather than automatically resending.

The final point avoids duplicating a message when the SMTP server accepted it but the network failed before SourceLoop received the response.

## Inbound correlation order

The mailbox worker uses the strongest available signal first:

1. `In-Reply-To` or `References` matched to a recorded outbound `Message-ID`.
2. Explicit `X-SourceLoop-Case-ID` and `X-SourceLoop-Thread-ID` headers.
3. The `[SL:XXXXXXXXXXXX]` subject token.
4. A unique open case containing the exact sender endpoint.

An ambiguous message is retained as an unmatched receipt and is not attached to an arbitrary case.

## Adaptive correspondence

After each inbound reply, two extraction workers produce schema-shaped interpretations. The deterministic reconciler creates or updates claims and a supplier quote. The vertical pack identifies critical quote fields. When those fields remain unresolved and the thread has not exhausted its follow-up allowance, SourceLoop proposes one reply containing only the missing questions.

The follow-up preserves:

- Thread ID.
- Original provider `Message-ID` in `In-Reply-To`.
- The complete `References` chain.
- Recipient endpoint.
- Automation disclosure.
- Human approval when required by the pack.
- A distinct idempotency key.

## Swarm topology

Long-lived roles own responsibility; short-lived workers perform narrow tasks.

```text
case supervisor
  ├── horizon and risk critic
  ├── requirement compiler
  ├── missing-information critic
  ├── market / GIS / relationship scouts
  ├── contact resolver
  ├── message composer
  ├── policy critic
  ├── extractor A
  ├── extractor B
  ├── adversarial quote auditor
  ├── graph curator
  └── completion judge
```

Only the conversation action created by the coordinator can reach the mail gateway. Internal workers have no external delivery capability.

## Persistence and concurrency

Case snapshots use optimistic version checks. An outdated process cannot silently overwrite a newer case version. Inbound receipts and outbound idempotency keys are unique database records. Ordered event insertion retries bounded sequence collisions. These controls support an API process and mailbox worker sharing one database without treating an LLM session as authoritative state.

## Container posture

The application images:

- Run as non-root UID/GID 10001 for Python and as the Nginx user for the web tier.
- Use multi-stage builds.
- Mount application filesystems read-only.
- Store only evidence and database state on named volumes.
- Drop Linux capabilities.
- Enable `no-new-privileges`.
- Use tmpfs for transient files.
- Provide liveness/readiness and worker-heartbeat checks.
- Expose only the Nginx port in the default Compose stack.

## Extension ports

The stable boundaries for further work are:

- `AgentRuntime` for Hermes, OpenClaw, OpenAI Agents SDK, local models, or other specialist workers.
- `MailGateway` for provider-native Gmail/Microsoft Graph transports.
- `MailboxClient` for push-webhook or provider-native inbound streams.
- `EvidenceStore` for S3-compatible immutable storage.
- `PackRegistry` for new vertical contracts.
- `GraphProjector` for City2Graph, graph databases, and model feature materialization.
- Discovery adapters for public registries, GIS, customer CRMs, and authorized search tools.
