# SourceLoop security model

## Safe defaults

A new deployment cannot send external email or access a mailbox:

```env
SOURCELOOP_EMAIL_MODE=dry_run
SOURCELOOP_ALLOW_EXTERNAL_SEND=false
SOURCELOOP_MAILBOX_MODE=disabled
```

Changing only one outbound flag is insufficient. Live SMTP requires both `email_mode=smtp` and explicit external-send authorization, a configured host, an approved action, a valid non-suppressed endpoint, an automation disclosure, and a unique idempotency key.

## Identity and authorization

Messages must identify the real requester and disclose automation or AI assistance. The policy engine rejects instructions that request impersonation, fabricated identities, hidden requesters, or concealed automation.

The current application is intended for a trusted, single-organization operator environment. It does not yet contain end-user authentication. Do not expose port 8080 to an untrusted network without an authenticated ingress, VPN, identity-aware proxy, or equivalent access control.

## Secrets

Do not store credentials in Git or baked images. `SOURCELOOP_SMTP_PASSWORD_FILE` and `SOURCELOOP_IMAP_PASSWORD_FILE` support Docker/Kubernetes secret mounts. The secret file should be readable only by the application UID. Database credentials should likewise be supplied by a deployment secret manager in production.

Dedicated low-privilege mailboxes are strongly preferred. Do not connect an executive or personal inbox containing unrelated correspondence.

## Outbound side effects

All outbound email is represented by a typed `ActionProposal`. Deterministic controls enforce:

- Exact-message approval where required.
- Suppression status.
- Maximum counterparty count.
- Bounded follow-ups.
- Email syntax.
- Truthful requester identity.
- Automation disclosure.
- No deceptive identity instructions.
- Thread requirements for a follow-up.
- Idempotency.
- Live-delivery configuration.

An agent runtime cannot call SMTP directly through SourceLoop. Hermes and OpenClaw are invoked as internal reasoning workers without delivery authority.

## Mailbox ingestion

Inbound email is untrusted content. The worker treats message text as evidence, not as executable instructions. Correlation must be unambiguous. Duplicate messages are suppressed with a durable receipt. Opt-out language immediately creates a suppression record.

HTML is reduced to readable text for extraction. Remote images, JavaScript, macros, and attachment contents are not executed.

## Evidence and attachments

Raw `.eml` evidence is written once with mode `0600`. File names are sanitized, paths are constrained beneath the evidence root, payloads are hashed, and oversized attachments are rejected. Accepted attachments remain `stored_quarantined`; no API route serves them and no downstream parser should consume them before a malware and content-safety stage is added.

## Political and sensitive workflows

The civic pack restricts contact counts and follow-ups. SourceLoop must not be used to:

- Impersonate constituents or manufacture grassroots activity.
- Infer private political beliefs.
- Scrape private memberships or hidden personal contact details.
- Map residences or live movements of organizers or attendees.
- Conduct individualized political persuasion based on sensitive traits.
- Continue after a decline or opt-out.

## Commercial and quote workflows

Supplier-specific nonpublic quotes remain scoped to the requesting customer. Do not disclose one supplier's confidential price or terms to a competitor. Autonomous quote acceptance, purchasing, contract signing, or unbounded negotiation is prohibited in the supplied packs.

## Container controls

The supplied Compose deployment runs application processes as non-root, drops Linux capabilities, applies `no-new-privileges`, uses read-only filesystems and tmpfs, places PostgreSQL on an internal-only network, and publishes only the web gateway. These controls reduce impact but are not substitutes for authentication, patching, backups, TLS termination, network policy, and secret management.

## Vulnerability reporting

Report a suspected vulnerability privately to the repository owner. Include the affected version or commit, reproduction steps, and impact. Do not include real mailbox credentials or private correspondence in a public issue.
