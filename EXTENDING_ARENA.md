# Extending the Universal DAG Arena

The Arena is a conformance and experimentation suite, not a gallery of claims.
An entry is useful only when its readiness label, task contract, node matrix,
execution evidence, and external boundaries agree.

## Choose the honest readiness level

| Level | Required evidence |
|---|---|
| `executable_fixture` | Typed local program, real callable nodes, at least one accepted route, useful negative control, independent fixture oracle, and release-gate execution |
| `template` | Reusable typed decomposition with explicitly missing implementation/evaluation work |
| `credentialed_connector` | Real solution requires scoped credentials, current external authority, or a production system unavailable to the fixture suite |

An offline address directory is a reference fixture, not USPS validation. A
mock browser response is not a verified product scrape. A tiny tabular fixture
is not a Kaggle leaderboard claim.

## Implementation sequence

1. Freeze task inputs, typed outputs, authority, hard constraints, objectives,
   budget, and independent acceptance oracle.
2. Choose fixed topology or author a versioned topology family. Split macro
   steps until each atomic slot has one substitutable purpose.
3. Use branch activation, explicit optional merges, child graphs, or bounded
   loops instead of hiding control flow in a mega-node.
4. Author at least two genuine candidates for important slots. Wrap each
   callable with an exact `NodeSpec`, implementation digest, failure/effect/
   permission contract, and candidate binding.
5. Add the program, registry, fixture case, objective set, runtime policy,
   verifier, and declared routes. Include a valid-but-poor route when it teaches
   the oracle what to reject.
6. Add or update the `ArenaTask` metadata, readiness, external requirements,
   template ID, example IDs, acceptance signals, and tags.
7. Regenerate `catalog/`; never hand-edit generated projections.
8. Run in-process and subprocess release verification plus installed-wheel
   conformance.

## Required gates

```bash
solutiongraph catalog export --output catalog
solutiongraph doctor
solutiongraph conformance
solutiongraph verify --catalog-root catalog --runtime in-process
solutiongraph verify --catalog-root catalog --runtime subprocess
pytest -q
ruff check browsergraph solutiongraph tests/test_solutiongraph*.py scripts
```

## Real-world confirmation pack

Before promoting a fixture toward production language, add a separately
versioned confirmation pack containing representative immutable cases, clean
holdouts, credential and authority setup, runtime/environment identity,
repeated seeds where needed, failure injection, latency/cost/resource measures,
and retained receipts. Keep candidate execution unable to redefine or inspect
hidden evaluator assets.

For Kaggle, freeze competition rules, data hashes, split/leakage policy, metric,
submission schema, and seed budget. For APIs and business workflows, test
idempotency, partial failure, compensation, rate limits, and provider
provenance. For streaming, test event-time disorder and restart recovery. For
numerical tasks, test conditioning, residuals, precision escalation, and
algorithm fallback rather than only a happy-path answer.
