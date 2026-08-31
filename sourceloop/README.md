# SourceLoop — Direct-Source Intelligence OS

SourceLoop is a working Phase-1 implementation of a **question-to-knowledge and request-to-quote operating system**. It turns an uncertain business or civic question into a governed practitioner workflow that can research, discover contacts, prepare transparent outreach, wait for asynchronous replies, extract claims or quotes, and update a source-backed graph.

The implementation deliberately separates four concerns:

1. **The practitioner loop** owns the nine-stage case lifecycle.
2. **Agent runtimes** reason, research, compose, and extract, but do not directly authorize side effects.
3. **Deterministic policy and approval services** control email, suppression, idempotency, and graph commits.
4. **The evidence ledger** stores the original interaction beside every structured claim or quote.

## What is implemented

- Nine-stage practitioner runtime: `ORIENT → RECONCILE_HORIZON → ASSESS_PREPARE → DECIDE_NEXT → HOW → ACT → VERIFY → INTEGRATE_COMMIT → ROUTE`.
- Durable case, event, outbox, approval, and suppression records in SQLite or PostgreSQL.
- Internal specialist swarms with persistent run receipts.
- Default deterministic `MockRuntime` plus optional Hermes and OpenClaw CLI adapters.
- Approval-gated outbound email. External SMTP is disabled unless two explicit safety settings are enabled.
- One coherent external thread per counterparty; internal workers never contact recipients independently.
- Dual extraction, deterministic reconciliation, quote normalization, and unresolved-field reporting.
- NetworkX projection, GeoJSON output, and an optional City2Graph bridge to NetworkX/rustworkx/PyG.
- Three vertical packs: civic intelligence, commercial-facilities quoting, and BPO quoting.
- FastAPI API, React + TypeScript operator console, CLI demo, Docker Compose, and automated tests.

## Quick start

```bash
cd sourceloop
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Starts the API on http://localhost:8000
sourceloop serve
```

In another terminal:

```bash
cd sourceloop/frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The frontend proxies `/api` to the backend.

### Run the deterministic end-to-end demo

```bash
sourceloop demo --kind facilities_quote
```

The demo creates a case, runs the practitioner until an approval gate, approves and **dry-runs** the outbound requests, injects sample supplier replies, normalizes the quotes, and completes the graph update. No external email is sent.

### Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

The stack includes PostgreSQL/PostGIS, the API, and the React console. The email gateway remains `dry_run` unless explicitly changed.

## Core API

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/cases` | Create a direct-source intelligence case |
| `GET` | `/api/v1/cases` | List cases |
| `GET` | `/api/v1/cases/{case_id}` | Read full case state |
| `POST` | `/api/v1/cases/{case_id}/run` | Run until input, approval, or external reply is required |
| `POST` | `/api/v1/cases/{case_id}/actions/{action_id}/approve` | Approve one proposed side effect |
| `POST` | `/api/v1/cases/{case_id}/dispatch` | Dispatch approved actions through the configured gateway |
| `POST` | `/api/v1/inbound/email` | Record a reply and resume the case |
| `POST` | `/api/v1/demo/{case_id}/replies` | Inject deterministic demonstration replies |
| `GET` | `/api/v1/cases/{case_id}/events` | Read the immutable event timeline |
| `GET` | `/api/v1/outbox` | Inspect dry-run or sent messages |
| `GET` | `/api/v1/graph` | NetworkX node-link projection |
| `GET` | `/api/v1/map/features` | GeoJSON feature collection |

Interactive API documentation is available at `/docs`.

## Agent runtimes

The default runtime is deterministic so the repository can be tested without credentials.

```bash
SOURCELOOP_AGENT_RUNTIME=mock
```

Hermes adapter:

```bash
SOURCELOOP_AGENT_RUNTIME=hermes
SOURCELOOP_HERMES_PROFILE=sourceloop-research
```

OpenClaw adapter:

```bash
SOURCELOOP_AGENT_RUNTIME=openclaw
SOURCELOOP_OPENCLAW_AGENT=sourceloop-practitioner
```

The adapters run one internal reasoning turn and request JSON. They do **not** use `--deliver` and cannot bypass the SourceLoop action ledger. The exact installed CLI version remains an external dependency; see `ARCHITECTURE.md` for the adapter contract.

## Outbound safety

The default configuration is intentionally non-delivering:

```bash
SOURCELOOP_EMAIL_MODE=dry_run
SOURCELOOP_ALLOW_EXTERNAL_SEND=false
```

Actual SMTP requires both:

```bash
SOURCELOOP_EMAIL_MODE=smtp
SOURCELOOP_ALLOW_EXTERNAL_SEND=true
```

It also requires an approved action, a non-suppressed endpoint, a disclosed automated-assistance sentence, a configured sender identity, and an idempotency key that has not previously been dispatched.

SourceLoop does not autonomously accept quotes, sign agreements, make political representations, infer private political beliefs, or contact private individuals merely because they appear in a dataset. Political/civic cases receive the strictest contact and follow-up limits.

## Vertical packs

A pack defines vocabulary, required fields, specialist roles, completion rules, outreach limits, and reusable question templates. Packs are data, not hard-coded prompt strings:

```text
packs/civic_intelligence.yaml
packs/facilities_quote.yaml
packs/bpo_quote.yaml
```

The next production step is to connect pack loading to the larger Universal Loop Engine catalog and let its compiler materialize these workflows as reusable loop-node profiles.

## Status

This branch is a functional Phase-1 MVP and architecture proving ground. It is not represented as a finished production communications platform. Before real deployment, add organization-specific identity, OAuth-based email connectors, tenant isolation, encrypted secrets, production migrations, legal/compliance review for each vertical, observability, rate limits, and an evaluated human-approval operating process.
