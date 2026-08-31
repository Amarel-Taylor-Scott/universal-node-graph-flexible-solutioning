# SourceLoop — Direct-Source Intelligence and Quote OS

SourceLoop converts an unknown business or civic question into a governed, evidence-producing workflow:

```text
requirement or knowledge gap
        ↓
scoped practitioner swarm
        ↓
small, relevant counterparty panel
        ↓
operator-approved email
        ↓
SMTP delivery + IMAP reply monitoring
        ↓
thread-aware clarification when critical fields are missing
        ↓
claim / quote extraction with source lineage
        ↓
GIS and relationship-graph projection
```

Version 0.2 is a **complete container-shaped application**, not just a library or a mock UI. The default Compose stack includes PostgreSQL/PostGIS, the FastAPI control plane, a long-lived mailbox worker, an immutable evidence volume, and a production-built React console behind an unprivileged Nginx reverse proxy.

Outbound delivery and mailbox access remain disabled by default. A local GreenMail override is included so the complete SMTP → IMAP → extraction loop can be tested without any possibility of relaying email to the public internet.

## What is implemented

### Practitioner and swarm runtime

- Nine-stage lifecycle: `ORIENT → RECONCILE_HORIZON → ASSESS_PREPARE → DECIDE_NEXT → HOW → ACT → VERIFY → INTEGRATE_COMMIT → ROUTE`.
- Bounded internal specialists for requirements, GIS, relationships, contact resolution, message composition, policy review, dual extraction, adversarial review, and graph curation.
- Framework-neutral runtime adapters for the deterministic test worker, Hermes CLI, and OpenClaw CLI.
- One visible conversation owner per counterparty even when many internal workers contribute.
- Persistent case snapshots, ordered event receipts, worker heartbeats, suppression records, inbound deduplication, and an outbox ledger.

### Real correspondence plumbing

- Approval-gated SMTP delivery with STARTTLS or implicit TLS.
- Durable outbox reservation before network transmission.
- Stable `Message-ID`, `Reply-To`, `In-Reply-To`, and `References` handling.
- SourceLoop case and thread correlation headers plus a short subject token fallback.
- Generic IMAP mailbox access with SSL or STARTTLS.
- Unseen-message polling, MIME parsing, plain-text and HTML fallback extraction, and configurable folder/search settings.
- Automatic correlation of replies to cases and threads.
- Idempotent inbound processing using provider message IDs or message digests.
- Direct opt-out recognition and permanent suppression.
- Bounded, thread-aware clarification proposals when a quote omits configured critical fields.

### Evidence and intelligence

- Raw RFC 822 messages stored immutably on an application-owned volume.
- Attachment size limits, content hashes, safe file names, and quarantine status.
- Direct-source claims classified as facts, respondent reports, estimates, opinions, plans, referrals, denials, uncertainty, refusals, or system inferences.
- Quote line items, units, payment terms, operational terms, exclusions, validity, unresolved fields, and normalization lineage.
- Dual extraction with explicit disagreement marking.
- NetworkX and GeoJSON projections, plus an optional City2Graph path to rustworkx and PyTorch Geometric.

### Container application

- Multi-stage, non-root Python image shared by API and worker.
- Multi-stage React build served by non-root Nginx.
- Same-origin proxy for the API, health checks, OpenAPI, and the operator console.
- PostgreSQL/PostGIS with a persistent volume and health-gated startup.
- Read-only application filesystems, dropped Linux capabilities, `no-new-privileges`, tmpfs, restart policies, and health checks.
- Docker-style `*_FILE` secret support for SMTP and IMAP passwords.
- GreenMail SMTP/IMAP sandbox and an executable end-to-end smoke test.

## Start the application

```bash
cd sourceloop
cp .env.example .env
docker compose up --build -d
```

Open:

- Operator console: `http://localhost:8080`
- Interactive API documentation: `http://localhost:8080/docs`
- Readiness: `http://localhost:8080/health/ready`

The default stack is safe to start immediately:

```env
SOURCELOOP_EMAIL_MODE=dry_run
SOURCELOOP_ALLOW_EXTERNAL_SEND=false
SOURCELOOP_MAILBOX_MODE=disabled
```

Messages can be drafted, approved, and captured in the outbox, but they do not leave the container.

Useful commands:

```bash
make up
make logs
make doctor
make down
```

## Prove the complete email loop locally

The sandbox starts a non-relaying GreenMail server with SMTP and IMAP accounts inside Docker:

```bash
make sandbox-smoke
```

That command builds the stack and proves this complete path:

1. Create a real non-demo quote case through the API.
2. Generate and approve one outbound action.
3. Send the email over SMTP to `supplier1@supplier.local`.
4. Send a correlated reply over SMTP.
5. Retrieve the reply from the SourceLoop mailbox over IMAP.
6. Match `In-Reply-To` to the correct outbox record and case.
7. Preserve the raw email as evidence.
8. Extract a complete quote.
9. Complete the case and verify the sent-message ledger.

The sandbox exposes GreenMail only on local development ports and does not forward email to external mail servers.

Stop and delete sandbox data:

```bash
make sandbox-down
```

## Connect a real generic mailbox

Use a dedicated organizational mailbox rather than a personal mailbox. Configure both outbound SMTP and inbound IMAP:

```env
SOURCELOOP_ENVIRONMENT=production

SOURCELOOP_EMAIL_MODE=smtp
SOURCELOOP_ALLOW_EXTERNAL_SEND=true
SOURCELOOP_SENDER_NAME=Acme Research Desk
SOURCELOOP_SENDER_EMAIL=research@example.com
SOURCELOOP_REPLY_TO_EMAIL=research@example.com
SOURCELOOP_SMTP_HOST=smtp.example.com
SOURCELOOP_SMTP_PORT=587
SOURCELOOP_SMTP_USERNAME=research@example.com
SOURCELOOP_SMTP_PASSWORD_FILE=/run/secrets/smtp_password
SOURCELOOP_SMTP_STARTTLS=true
SOURCELOOP_SMTP_SSL=false

SOURCELOOP_MAILBOX_MODE=imap
SOURCELOOP_IMAP_HOST=imap.example.com
SOURCELOOP_IMAP_PORT=993
SOURCELOOP_IMAP_USERNAME=research@example.com
SOURCELOOP_IMAP_PASSWORD_FILE=/run/secrets/imap_password
SOURCELOOP_IMAP_SSL=true
SOURCELOOP_IMAP_STARTTLS=false
SOURCELOOP_IMAP_FOLDER=INBOX
SOURCELOOP_IMAP_POLL_SECONDS=30
```

Mount the referenced secret files into both the `api` and `worker` containers. Do not commit passwords, OAuth refresh tokens, or app passwords to the repository.

Gmail and Microsoft 365 deployments can use their SMTP/IMAP interfaces when enabled for the account. Native OAuth connector flows are still an extension point; the current production transport is standards-based SMTP/IMAP.

## Operator workflow

The console supports:

- Creating demo or live cases.
- Supplying typed requirements and public/business contact routes.
- Running the practitioner until it reaches an input, approval, or external wait state.
- Inspecting the exact recipient, subject, and body before approval.
- Approving or rejecting individual messages.
- Dispatching approved messages through dry-run or SMTP mode.
- Viewing conversation and evidence receipts.
- Manually triggering mailbox synchronization.
- Inspecting extracted quotes, unresolved fields, claims, agent receipts, and GIS routes.

A live case without contacts deliberately stops at `HOW`. The current version does not invent addresses. Search, registry, CRM, and organization-directory discovery adapters remain separate tools to connect through the runtime contract.

## Core API

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/cases` | Create a case |
| `GET` | `/api/v1/cases` | List cases |
| `GET` | `/api/v1/cases/{case_id}` | Read complete case state |
| `POST` | `/api/v1/cases/{case_id}/run` | Run until the next blocking condition |
| `POST` | `/api/v1/cases/{case_id}/actions/{action_id}/approve` | Approve one exact action |
| `POST` | `/api/v1/cases/{case_id}/actions/{action_id}/reject` | Reject one action |
| `POST` | `/api/v1/cases/{case_id}/dispatch` | Dispatch approved actions |
| `POST` | `/api/v1/inbound/email` | Ingest a normalized inbound message |
| `GET` | `/api/v1/mailbox/status` | Read mailbox and worker status |
| `POST` | `/api/v1/mailbox/sync` | Run one immediate IMAP synchronization |
| `GET` | `/api/v1/outbox` | Inspect captured, pending, sent, or uncertain messages |
| `POST` | `/api/v1/suppressions` | Suppress an endpoint |
| `GET` | `/api/v1/graph` | Read the NetworkX node-link projection |
| `GET` | `/api/v1/map/features` | Read the GeoJSON projection |
| `GET` | `/api/v1/graph/city2graph` | Inspect optional City2Graph materialization |

## CLI

```bash
sourceloop serve
sourceloop worker
sourceloop worker --once
sourceloop mailbox-sync
sourceloop doctor
sourceloop worker-health --max-age 120
sourceloop demo --kind facilities_quote
```

`sandbox-reply` is restricted to development, test, and sandbox environments.

## Agent runtimes

The credential-free runtime is the default:

```env
SOURCELOOP_AGENT_RUNTIME=mock
```

Hermes:

```env
SOURCELOOP_AGENT_RUNTIME=hermes
SOURCELOOP_HERMES_PROFILE=sourceloop-research
```

OpenClaw:

```env
SOURCELOOP_AGENT_RUNTIME=openclaw
SOURCELOOP_OPENCLAW_AGENT=sourceloop-practitioner
```

These adapters are internal practitioners. They cannot send email directly. They return typed proposals to SourceLoop, where deterministic approval, suppression, idempotency, and delivery services control side effects.

## Development without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
sourceloop demo --kind facilities_quote
sourceloop serve
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

## Current production boundaries

This version is a deployable single-organization foundation. Before exposing it directly to an untrusted network, add organization-specific authentication or place it behind an authenticated reverse proxy. Further enterprise work includes tenant-level row security, provider-native OAuth setup screens, database migrations, malware scanning before attachments leave quarantine, object-storage evidence backends, search/registry discovery connectors, durable distributed scheduling, and formal compliance review for each vertical.

The system deliberately does not autonomously accept quotes, make purchases, sign contracts, conduct hidden political persuasion, infer private political beliefs, map residential locations, or continue after a recipient opts out.
