# Security and responsible-use model

SourceLoop is designed for transparent direct-source research, verification, and request-for-quote workflows. It is not designed for covert persuasion, impersonation, surveillance, harassment, or unrestricted automated outreach.

## Non-negotiable controls

- External sending is disabled by default.
- Every initial external message requires a recorded approval.
- Every message has a deterministic idempotency key.
- Suppression and opt-out checks occur inside the mail service, not only in prompts.
- Political and civic cases use the lowest contact and follow-up ceilings.
- One visible sender identity and one thread are used per counterparty.
- Automation or assistance is disclosed in the default templates.
- The agent cannot accept a quote, sign a contract, make a purchase, or create a political representation.
- Original evidence is retained beside derived structured data.
- Fact, respondent report, estimate, opinion, forward-looking plan, referral, denial, and system inference are different claim classes.

## Prohibited implementations

Do not extend this system to:

- create fake residents, constituents, customers, journalists, or organizations;
- conceal the requester or fabricate a cover story;
- infer private political beliefs, religion, health, ethnicity, sexuality, or other sensitive traits;
- map private homes, device-level movement, closed-group membership, or event attendees;
- use facial recognition to identify attendees;
- evade rate limits, anti-bot systems, or no-contact requests;
- repeatedly pressure a recipient who declined or did not respond;
- pool identifiable nonpublic competitor pricing for seller-side coordination;
- publish confidential quotes or private replies outside their permitted scope;
- use an agent's remembered statement as a live price or verified fact.

## Threat model

### Prompt injection in replies and attachments

Inbound content is evidence, not an instruction channel. Extractors receive a fixed role and schema, and action services ignore instructions embedded in respondent content. Production deployments should parse attachments in isolated workers and malware-scan all files.

### Duplicate delivery

Mail dispatch is protected by a unique idempotency key in the database. Workflow retries return the existing outbox record instead of delivering again.

### Agent overreach

Agent outputs are `proposed_actions`. Deterministic policy checks and explicit approval precede any side effect. Runtimes receive no direct SMTP credential through the SourceLoop contract.

### Stale or misleading intelligence

Every claim records evidence, scope, assertion time, confidence, and optional expiry. Forward-looking plans and opinions are never silently promoted to facts.

### Cross-tenant leakage

The MVP is a single-tenant proving ground. A hosted product must add tenant IDs to every table, database row-level security, isolated object-store namespaces, per-tenant keys, and tests that prove queries cannot cross tenant boundaries.

### Secret exposure

Do not commit credentials. Use a secret manager in production. Hermes/OpenClaw profiles and browser workers should have separate narrowly scoped service accounts rather than a shared human super-account.

## Deployment checklist

Before enabling real external communication:

1. Complete legal and compliance review for the target jurisdiction and vertical.
2. Configure an authenticated organizational sender domain.
3. Replace shared passwords with OAuth or managed secrets.
4. Verify approval roles and escalation paths.
5. Test suppression, bounce, duplicate webhook, restart, and retry behavior.
6. Run a closed pilot with a small, known respondent panel.
7. Measure complaint, opt-out, wrong-recipient, and unresolved-question rates.
8. Establish deletion, correction, retention, and evidence-access procedures.
9. Review benchmark and pricing outputs for confidentiality and competition risk.
10. Keep purchasing, contract acceptance, and political persuasion outside autonomous authority.
