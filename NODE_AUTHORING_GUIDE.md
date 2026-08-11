# Node authoring guide

This guide is the shortest safe path from a Python function to a reusable,
searchable SolutionGraph node pack. `NODE_REPOSITORY_PROTOCOL.md` remains the
normative ecosystem contract.

## 1. Choose an atomic capability

A node implements one replaceable method for one semantic obligation. Name the
capability after the result, not the tool:

- good: `records.deduplicate`, `document.extract-text`, `image.detect-text`;
- poor: `use-pandas`, `call-gpt`, `run-chrome`.

Provider, model, package, binary, prompt, and configuration belong to the node
implementation or candidate binding. Split a capability when its alternatives
would not have equivalent typed inputs, outputs, effects, and success meaning.

## 2. Write an importable function

The reference Python runtime invokes named inputs and parameters as keyword
arguments. Use a top-level importable function—never a lambda, closure, nested
function, or bound method.

```python
from typing import Any


def trim_strings(
    records: list[dict[str, Any]], recursive: bool = False
) -> list[dict[str, Any]]:
    """Trim string values under an explicit recursion policy."""
    # implementation omitted here
    return records
```

## 3. Define and validate the executable contract

`define_python_node` inspects the callable signature, derives an importable
entrypoint, hashes the actual source, constructs the strict `NodeSpec`, and
fails immediately on ABI drift.

```python
from solutiongraph import ParameterSpec, Port, ValueType, define_python_node

records_type = ValueType("records.json", "1")

definition = define_python_node(
    node_id="example.records.trim-strings",
    function=trim_strings,
    inputs=(Port("records", records_type),),
    outputs=(Port("records", records_type),),
    capabilities=("records.trim-strings",),
    description="Trim string fields with an explicit shallow/recursive policy.",
    parameters=(
        ParameterSpec(
            "recursive", "boolean", default=False, choices=(False, True)
        ),
    ),
    preconditions=("records conform to records.json@1",),
    postconditions=("record order and non-string values are preserved",),
    verifier="example.verify.trim-strings@1",
)

assert definition.validate() == []
```

Declare exact failure modes, effects, permissions, determinism, idempotency,
resource claims, and invariants whenever they apply. The authoring helper reduces
boilerplate; it does not infer semantic truth.

## 4. Expand finite choices into visible candidates

Finite experimental parameters should become explicit candidates so the viewer,
compiler, search report, and receipt can identify every choice.

```python
candidates = definition.candidates(max_candidates=2)
```

`enumerate_candidates` computes the exact Cartesian size and refuses to exceed
an explicit `max_candidates`. It never silently truncates. Use
`definition.candidate({...})` for required or open-ended parameters.

Do not encode provider/model/library selection inside an opaque function body or
prompt. Bind it visibly or create distinct implementation nodes when it changes
runtime, authority, failure, or provenance.

## 5. Build a registry and pack

```python
from solutiongraph import build_python_registry

registry = build_python_registry(
    "registry.example-records",
    "1.0.0",
    (definition,),
    candidates=candidates,
)
assert registry.validate() == []
```

Then add:

- sparse `NodeDescriptor` sidecars for people and discovery;
- optional search documents and exact named embedding representations;
- a truthful `RegistryCapabilities` handshake;
- a `NodePackManifest` containing the exact node, descriptor, document,
  embedding-space, candidate, and artifact digests;
- fixtures, compiler-admission tests, and runtime tests.

Descriptors and embeddings can nominate a node. They cannot grant a capability,
repair a type mismatch, authorize an effect, or alter `NodeSpec`.

## 6. Use the standard library as a reference

`solutiongraph/stdlib_nodes.py` contains 19 dependency-free text/data
implementations. `solutiongraph/stdlib_pack.py` wraps them exclusively through
the authoring SDK into 19 strict node definitions, 32 exact candidate bindings,
search descriptors/documents, a portable node pack, and an executable seven-slot
data-quality program.

```python
from solutiongraph.stdlib_pack import (
    STANDARD_LIBRARY_DEFINITIONS,
    STANDARD_LIBRARY_NODE_PACK,
    STANDARD_LIBRARY_REGISTRY,
)

assert all(not item.validate() for item in STANDARD_LIBRARY_DEFINITIONS)
assert not STANDARD_LIBRARY_NODE_PACK.validate()
assert not STANDARD_LIBRARY_REGISTRY.validate()
```

The pack includes Unicode and whitespace normalization, control stripping,
strict JSON/JSONL/delimited parsing, key/value normalization, projection,
required-field validation, filtering, deduplication, sorting, profiling,
canonical hashing, and explicit identity behavior.

## 7. Identity candidates

A pass-through is a real implementation choice, not an empty UI placeholder. It
is admissible only when input and output types match, effects are unchanged, and
the slot contract says omission is legal. Give it a content digest, capability,
candidate ID, tests, and evidence like every other node.

## 8. External connectors

For APIs, databases, browsers, queues, models, files, humans, or devices,
declare:

- authority and credential scope;
- network/filesystem/device effects;
- idempotency and retry semantics;
- rate, quota, and monetary resource claims;
- current provider/API/model/version identity;
- privacy, residency, retention, and data-classification constraints;
- typed error taxonomy and compensation behavior;
- a fixture adapter distinct from the authoritative production connector.

A local lookup table may test an address-verification interface. It must not be
described as an official USPS validation result.

## 9. Required tests

At minimum, test:

- `PythonNodeDefinition.validate()` and `NodeSpec.validate()`;
- rejection of missing, extra, or positional-only callable arguments;
- implementation digest changes when executable source changes;
- candidate binding validation and stable IDs;
- expected admission to compatible slots and rejection from incompatible ones;
- success, declared failures, and boundary cases;
- pack manifest closure and catalog round-trip;
- subprocess execution for trusted code when portability matters.

Run:

```bash
solutiongraph doctor
solutiongraph catalog export --output catalog
solutiongraph verify --catalog-root catalog --runtime subprocess
pytest -q
ruff check browsergraph solutiongraph scripts
```

## 10. Publication checklist

Publish only when the pack has a license, source, versioning policy, exact
digests, changelog, compatibility range, examples, tests, and honest readiness.
Do not publish measured quality inside the immutable node ABI; ship benchmark
receipts or belief artifacts tied to task, case, environment, and time instead.
