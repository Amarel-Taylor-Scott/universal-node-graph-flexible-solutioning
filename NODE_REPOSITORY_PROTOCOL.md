# Node Repository and Discovery Protocol

Status: research preview 0.1
Normative Python model: `solutiongraph.discovery`
Portable schemas: `solutiongraph/schemas/*discovery*`, `node-descriptor`,
`embedding-record`, `node-compatibility-profile`, `registry-capabilities`,
`registry-snapshot`, and `node-pack`

This protocol lets independently maintained repositories publish reusable node
contracts without forcing every publisher to use the same database, search
engine, embedding model, programming language, or deployment system.

The central rule is:

> Executable truth is strict and content-addressed. Discovery evidence is sparse,
> extensible, independently versioned, and never grants compatibility.

## 1. Five different objects

| Object | Purpose | Required for compilation? | May change independently? |
|---|---|---:|---:|
| `NodeSpec` | Exact executable ABI and authority contract | Yes | Only as a new digest/version |
| `NodeDescriptor` | Human and machine discovery metadata | No | Yes |
| `EmbeddingRecord` | One vector view in one exact space | No | Yes |
| `NodeCompatibilityProfile` | Optional operational/semantic constraints outside the stable ABI | No | Yes, when rebound to the exact node identity |
| `NodePackManifest` | Portable, content-addressed distribution unit | For distribution, not semantics | Yes |

A registry MUST NOT copy an inferred capability, port, effect, or permission
from a descriptor or embedding into a `NodeSpec`. Search can nominate a node;
only compiler admission can prove that it fits a slot.

## 2. Executable node identity

A node repository publishes the complete `NodeSpec` described in
`UNIVERSAL_NODE_GRAPH_SPEC.md`. Its identity has three layers:

1. stable node ID, such as `acme.image.decode-png`;
2. contract version, such as `2.1.0`;
3. digest of the complete node contract, which itself includes the executable
   implementation digest.

The implementation digest SHOULD identify actual executable bytes, source, or
an OCI artifact—not a mutable tag or package name. Runtime-specific lockfiles,
container manifests, model weights, prompts, and other dependencies SHOULD be
separate content-addressed artifacts so a receipt can say exactly what changed.

## 3. Sparse, unlimited discovery descriptions

`NodeDescriptor` is keyed by node ID, version, and exact `node_spec_digest`. All
other fields are optional or repeatable:

- title and summary;
- purposes: why a route might need this node;
- solutions: problem statements the node has helped satisfy;
- actions: verbs or operations it performs;
- domain and tag identifiers;
- aliases and vocabulary variants;
- per-port meanings and examples;
- zero or more `SearchDocument` views;
- namespaced extension fields.

A publisher MAY provide only the three identity fields. Another publisher MAY
attach hundreds of independently sourced search documents. The limit is a
storage/index concern, not an ABI limit.

Each `SearchDocument` declares its target, language, optional source digest,
and namespaced extensions. Examples of distinct views include:

- a one-sentence overview;
- an API-oriented explanation;
- a domain-expert description;
- input or output semantics;
- failure and recovery behavior;
- worked examples;
- migration notes;
- externally reviewed documentation.

Descriptions do not have to agree perfectly, but provenance SHOULD be retained
and misleading documents SHOULD be superseded rather than silently rewritten.

## 4. Embeddings are named sidecars, not universal coordinates

Every `EmbeddingRecord` identifies an exact `EmbeddingSpace`:

- stable space ID;
- embedding model ID and revision;
- optional model artifact digest;
- dense, sparse, or multivector representation;
- dimensions where applicable;
- distance function;
- normalization and scalar type;
- intended descriptor targets;
- namespaced extensions.

Two spaces are compatible only when all vector semantics match exactly. Equal
dimensions do not imply compatibility. A query vector from model revision A
MUST NOT be sent to an index built with revision B unless a separately declared
adapter transforms between those spaces.

Vectors may be inline or referenced as content-addressed artifacts. The source
text digest binds a vector back to the text that produced it. Missing vectors
are normal: a node remains enumerable and searchable through other negotiated
modes.

Registries may expose any number of spaces—for node summaries, purposes, input
meanings, output meanings, failure behavior, examples, code, or learned task
associations. None is privileged by the architecture.

## 5. Compatibility profiles are strict optional sidecars

`NodeCompatibilityProfile` binds the exact node ID, version, and implementation
digest and may describe dimensions that a minimal executable ABI does not need:

- per-port nullability, ordering, time domain, event-time field, and data
  classifications;
- state and cache modes;
- required secret classes and hardware features;
- permitted data-residency regions;
- compensation-node identity; and
- namespaced extension metadata.

Sparse metadata remains unknown rather than guessed. A harness may require a
complete profile for regulated, stateful, streaming, or effectful workloads;
another may safely run a pure local node without one. Compatibility metadata
MUST NOT contain empirical quality scores and MUST NOT override the node's
nominal type, effect, permission, or implementation identity.

`CompatibilityCatalog.edge_problems()` compares two exact ports and reports
ordering, time-domain, classification, and completeness conflicts before a
runtime is selected. Nominal compiler admission remains mandatory even when
the sidecars appear compatible.

## 6. Harness–registry handshake

Before discovery, both sides exchange explicit capabilities.

The registry declares:

- protocol and wire-schema versions;
- query modes and searchable fields;
- exact embedding spaces;
- descriptor fields;
- enumeration, snapshot, continuation, and explanation support;
- an operational page-size maximum;
- namespaced extensions.

The harness declares ordered preferences for the same features. Negotiation
computes the intersection and freezes it as a content-addressed
`RegistrySession`.

The recommended fallback order is contextual, but a robust harness commonly
offers:

1. exact ID or digest lookup;
2. compatible vector or hybrid search;
3. lexical search;
4. typed metadata filtering;
5. deterministic enumeration.

If no exact vector space matches, vector mode is disabled with a warning; the
session continues through a compatible mode. If no protocol, required schema,
or usable query mode matches, negotiation fails before a query is issued.

Operational `max_page_size` is not an architectural candidate cap. A client
uses continuation until it has the requested coverage or deliberately records
why it stopped.

## 7. Open-world discovery, closed-world compilation

“Every possible node” cannot mean every node that might ever be published on
the internet. The protocol therefore makes the universe boundary explicit:

```text
federated/open registries
  → negotiated session
  → replayable DiscoveryQuery
  → one or more pages
  → DiscoveryReceipt
  → immutable RegistrySnapshot
  → full compiler admission over that snapshot
```

`DiscoveryReceipt` records the query and session digests, source registry,
modes used, pages and records examined, returned node digests, completeness,
continuation state, known total, explanation availability, and coverage notes.

`RegistrySnapshot` is the closed-world compiler universe. Its node-digest set
must exactly equal the receipt result set. Within that snapshot the compiler
examines every candidate for every slot—there is no hidden top-k. A later query
creates a new receipt and snapshot; it never mutates the meaning of an earlier
compilation.

This separates three important claims:

- **global completeness:** generally unknowable in a federated ecosystem;
- **query completeness:** evidenced by the discovery receipt;
- **admission completeness:** exact and testable within the snapshot.

## 8. Node packs and repository layout

A node pack is a portable manifest containing node-contract digests, descriptor
digests, optional embedding-record digests, artifacts, dependencies, source,
license, and namespaced extensions. It can be stored in Git, an object store,
or a content-addressed registry.

Recommended repository projection:

```text
nodepacks/<pack>/
├── manifest.json
├── registry.json
├── registry-capabilities.json
├── nodes/
│   └── <node-id>.json
├── descriptors/
│   └── <node-id>.json
├── embeddings/
│   └── <space-id>/<record-id>.json   # optional
├── artifacts/                        # optional local projection
├── fixtures/
└── tests/
```

The checked-in `catalog/nodepacks/reference-core/` directory demonstrates a
small descriptor-rich pack. `catalog/nodepacks/real-world-examples/`
demonstrates a larger executable pack with deliberately sparse discovery
metadata; missing descriptors or embeddings do not affect its ABI. Regenerate
both with:

```bash
python scripts/export_solutiongraph_catalog.py --output catalog
```

OCI-compatible registries are a natural transport because manifests and blobs
are content-addressed and annotations are namespaced. Transport compatibility
does not make an OCI image a valid node; its `NodeSpec` and artifacts still
have to pass this protocol and compiler admission.

## 9. Query and ranking rules

Discovery ranking is a nomination mechanism. A query may combine:

- exact identity;
- required capabilities;
- exact input/output nominal types;
- domain/tag filters;
- lexical text;
- one or more exact embedding targets;
- registry-specific namespaced filters.

The query, modes, weights, index revisions, and result explanations SHOULD be
recorded. A score MUST NOT be described as compatibility probability unless it
was calibrated for that meaning. Search results MUST be passed through strict
node/slot admission.

Federated results SHOULD preserve source registry and pack identity. Duplicate
node contracts may be collapsed by digest; conflicting contracts sharing a
human-readable ID MUST remain distinct and produce a diagnostic.

## 10. Extension rules

Core records use `additionalProperties: false`. Extensibility occurs only in an
explicit `extensions` object whose keys contain a namespace, such as:

```json
{
  "extensions": {
    "com.example.maintainer": "data-platform",
    "org.example.search.taxonomy": ["entity-resolution", "postal"]
  }
}
```

An extension MUST NOT change the semantics of a core field. A broadly required
extension should be proposed as a versioned core field with migration and
conformance tests.

## 11. Conformance checklist

A node repository is conforming when it can demonstrate:

1. Every node contract and executable artifact has stable content identity.
2. Descriptors reference the exact node-contract digest.
3. Port descriptions reference only real ABI ports.
4. Each vector references one exact declared embedding space and source text.
5. Missing descriptors or embeddings do not make a node invalid.
6. The registry and harness negotiate before querying.
7. Fallback never treats incompatible embedding spaces as equivalent.
8. Every query produces a coverage receipt.
9. Every compiler run consumes an immutable registry snapshot.
10. Admission examines the entire snapshot and retains every rejection reason.
11. Effects, permissions, provenance, and license survive packaging.
12. Compatibility profiles bind exact nodes and never grant ABI validity.
13. Generated files reproduce deterministically from their canonical source.

## 12. Explicit non-goals

- One mandatory vector database or embedding model.
- A central authority deciding which nodes may exist.
- Treating natural-language similarity as type safety.
- Assuming a registry result is trustworthy executable code.
- Requiring all publishers to fill every search field.
- Claiming an open federated universe has been exhausted.
- Hiding an operational retrieval limit as “all candidates.”
