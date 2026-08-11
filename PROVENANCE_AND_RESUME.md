# Provenance and Resume

Status: local reference protocol 0.1
Implementations: `solutiongraph.durable`, `solutiongraph.provenance`

Resume and provenance solve different problems. A checkpoint says which exact
prefix may continue. Provenance says what exact execution and artifacts were
observed. Neither changes the semantic program or legalizes a plan.

## Exact checkpoint identity

`ExecutionCheckpoint` binds:

- plan, program, registry, and admitted-space digests;
- graph-input and environment digests;
- task-case ID and seed;
- status and failure class;
- an exact topological prefix of completed slots;
- every selected candidate, node receipt, output name, codec, and stored
  artifact identity.

`resume=True` succeeds only if every identity matches the current execution.
The executor rehydrates each output from the supplied `ArtifactStore` and
preserves the original node receipt. A missing artifact, reordered/non-prefix
slot, changed environment, changed input, or different plan fails closed.

`MemoryCheckpointStore` is for tests. `FileArtifactStore` verifies content on
read and uses an atomic, file- and directory-`fsync` write; `FileCheckpointStore`
uses the same durable replace discipline. Successful and verifier-rejected completions
clear the checkpoint by default; failed runs retain it. Set
`clear_checkpoint_on_success=False` only when a harness has a defined archival
policy.

Inspect a checkpoint without executing it:

```bash
solutiongraph checkpoint inspect checkpoint.json
solutiongraph checkpoint inspect checkpoint.json --json
```

## Provenance projections

Every projection is derived from an immutable `RunReceipt`:

- W3C PROV JSON maps the graph run and node attempts to activities and binds
  input/output artifacts as entities;
- OpenLineage emits a standard UUID run identity and a `COMPLETE` run event with
  SolutionGraph receipt identity, assignments, metrics, and artifact facets;
- in-toto/SLSA emits a Statement with SLSA provenance v1 predicate data.

Export a receipt JSON or one entry from a verified JSONL journal:

```bash
solutiongraph provenance export receipt.json --format bundle --output provenance.json
solutiongraph provenance export receipts.jsonl --receipt-id run.example \
  --format openlineage --output openlineage.json
```

The bundle retains the receipt ID and digest. These mappings support ecosystem
integration; they do not assert that an external service ingested the event,
that a signer attested it, or that the runtime was isolated. A production
system should sign receipts, bind dependency/environment digests, publish to an
authenticated lineage store, and enforce retention independently.

## Distributed systems boundary

Local exact-prefix resume is not distributed exactly-once processing. A
distributed adapter still needs leases, fencing tokens, ownership transfer,
heartbeats, idempotency records, transactional or deduplicating sinks, remote
durable state, garbage collection, and recovery testing under worker and
coordinator failure.
