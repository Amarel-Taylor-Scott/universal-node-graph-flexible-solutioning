# Readiness and support levels

Current release line: **0.5 Developer Preview / external alpha**.

SolutionGraph is ready for developers and researchers to model typed solution
spaces, author reusable node contracts, compile frozen routes, execute trusted
local experiments, preserve evidence, and integrate a coding harness. It is not
yet a turnkey production scheduler or a hostile-code execution service.

## Capability matrix

| Surface | Status | Supported use |
|---|---|---|
| Semantic model and 48 strict schemas | Alpha-supported | Typed task graphs, slots, nodes, candidates, registries, plans, receipts, topology families and search reports, checkpoints, streaming events/results, sagas, compatibility catalogs, multi-fidelity runs, OpenLineage facets, provenance, and conformance |
| Compiler and complete snapshot admission | Alpha-supported | Reject invalid types, authority, effects, topology, bindings, and constraints before execution |
| Conditional branches | Alpha-supported locally | Data-dependent activation, exactly receipted skips, and compiler rejection of unsafe conditional outputs without an explicit merge |
| Composite and bounded-loop lowering | Alpha-supported locally | Deterministic namespaced expansion into ordinary compiler-valid DAGs with a content-addressed lowering receipt |
| Alternative topology families | Alpha-supported locally | Search explicit compiler-valid graph shapes and node routes with separate topology/route budgets and complete accounting |
| Prior, beam, sprout, adaptive, exhaustive search | Alpha-supported | Explicitly budgeted proposal ordering over compiler-valid routes |
| Executed successive halving | Alpha-supported locally | Caller-supplied evaluation at explicit fidelity rungs with complete promotion and resource records |
| UniversalSolver | Alpha-supported locally | Full admission, multi-round search, frozen-plan experiments, learned observational priors, hard gates, ranking, champion, and benchmarked route-level fallbacks |
| Universal DAG Arena | Alpha-supported as a mechanism suite | 24 typed task contracts and 23 executable programs across 20 task families; four task families remain credentialed connectors |
| Templates and offline viewers | Alpha-supported | Explore 19 templates and every bundled slot/candidate projection |
| Trusted in-process Python runtime | Development only | Fast fixtures, tests, and notebooks using trusted code |
| Bounded subprocess Python runtime | Alpha-supported lifecycle isolation | Trusted code needing process separation, strict JSON/bytes ABI, timeout, and optional POSIX CPU/memory limits |
| Content-addressed artifacts | Alpha-supported locally | Reproducible fixture outputs and local checkpoints |
| Exact local checkpoint/resume | Alpha-supported locally | Completed-prefix rehydration only when plan/program/registry/admission/input/environment/case/seed identity matches exactly |
| JSONL receipt journal | Alpha-supported locally | Immediate fsync-backed append, duplicate rejection, complete hash-chain verification |
| Event-time stream reference | Experimental conformance adapter | Finite tumbling/sliding windows, watermarks, allowed lateness, early/on-time/late/final emissions, drops, and retraction links; not a distributed engine |
| Saga compensation reference | Experimental | Reverse-order compensation using ordinary effectful `NodeSpec` contracts and idempotency keys; not a transaction manager |
| Compatibility sidecars | Experimental | Optional ordering, time-domain, nullability, classification, state, secret, hardware, residency, and compensation metadata without polluting the node ABI |
| W3C PROV/OpenLineage/SLSA projections | Alpha-supported export | Machine-readable projections from immutable run receipts; external backends remain adapters |
| Installed-wheel conformance suite | Alpha-supported | Eight executable checks covering control, lowering, topology, recovery, streaming, compensation, multi-fidelity, and provenance |
| LLM-generated campaign contracts | Experimental | Freeze budgets, ancestry, proposal identity, and evaluator boundary before orchestration |
| BrowserGraph adapters | Experimental/optional | Browser and HTTP demonstrations when optional runtimes are installed |
| Hostile generated-code execution | Not provided | Requires an external microVM, Wasm, or remote trust boundary |
| Multi-tenant secrets/auth/retention | Not provided | Must be supplied by a production platform |
| Distributed crash replay, exactly-once semantics, and scheduling | Not provided | Local exact-prefix resume proves the protocol seam; a durable distributed scheduler remains external |
| Universal real-world performance claims | Not claimed | Bundled programs are mechanism fixtures, not domain benchmark superiority evidence |

## Safe uses today

- Clone the repository and follow `GETTING_STARTED.md`.
- Generate a starter workspace with `solutiongraph init` and give it to an LLM
  coding harness together with the concrete task.
- Define exact task contracts, templates, nodes, registries, and independent
  verifiers.
- Compare trusted local routes and persist all positive and negative receipts.
- Run `solutiongraph solve` or the executable Arena suite with explicit search
  coverage, accepted champion, and diverse fallback reporting.
- Build third-party runtime, registry, node-pack, optimizer, and artifact-store
  adapters against the documented protocols.

## Uses requiring an external enforcement layer

- Running untrusted or compromised node code.
- Keeping hidden evaluators confidential from candidates.
- Processing production secrets or regulated multi-tenant data.
- Enforcing network/filesystem/device policy against adversarial code.
- Making unattended high-impact deployment, financial, legal, medical, safety,
  or security decisions.

The subprocess runtime is not a sandbox. It inherits the current operating-system
user's authority unless an outer system removes it. Declared permissions and
effects remain admission evidence; they do not enforce operating-system policy.

## Distribution identity

The Python **distribution** remains named `browsergraph` for compatibility with
the original proof of concept. The primary domain-neutral **import and CLI** are
`solutiongraph`; `browsergraph` is one bundled adapter. A future distribution
rename, if any, will be announced before 1.0 with an explicit compatibility
window rather than performed silently.

No stable-API promise is made before 1.0. Wire-model or behavior changes follow
semantic release versions, changelog entries, schema versions, and migration
notes. Exact versions and digests should be frozen in plans and node packs.

## Release gates

Every publishable commit must pass:

```bash
ruff check browsergraph solutiongraph tests/test_solutiongraph*.py scripts
pytest -q
solutiongraph doctor
solutiongraph conformance
solutiongraph verify --catalog-root catalog --runtime in-process
solutiongraph verify --catalog-root catalog --runtime subprocess
python -m build
twine check dist/*
```

CI additionally installs the built wheel into a clean environment and repeats
both release-verification modes. Tags must exactly match the package version.
GitHub release artifacts receive checksums and build provenance. PyPI publishing
is disabled unless the repository variable `PUBLISH_TO_PYPI=true` is explicitly
configured.

## Gates before beta or production language

Beta requires at least one enforcing isolated runtime adapter, distributed
crash-resumable campaign execution, larger mature-library node packs, and
held-out multi-seed benchmarks on real external tasks. Version 0.5 demonstrates the complete local
task → graph → admission → search → execution → evidence → belief-update →
champion/fallback loop plus structured control and recovery, but only on small
trusted fixtures.

Production language additionally requires authentication, authorization,
tenancy, secret brokerage, encryption, retention, operational monitoring,
incident response, supply-chain policy, and independently audited isolation.
