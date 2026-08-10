# Universal DAG Arena

The Arena is the executable proving ground for the universal graph model. It
does not assume every problem is browsing, machine learning, or a linear data
pipeline. Each entry specifies a problem family, input/output contract,
semantic stage families, independent acceptance signals, a reusable template,
and an honest readiness level.

## Run it

```bash
python -m pip install -e .
solutiongraph doctor
solutiongraph arena list
solutiongraph arena list --readiness executable_fixture
solutiongraph arena show arena.organization-entity-graph
solutiongraph solve organization-entity-linking --profile balanced
solutiongraph arena run --profile quick
```

Use `--runtime subprocess` to exercise the bounded child-process adapter. Add
`--artifact-dir` and `--receipt-journal` to persist content-addressed outputs
and append every completed receipt immediately.

## Readiness means something

| Readiness | Meaning |
|---|---|
| `executable_fixture` | A deterministic local program compiles and runs through an independent fixture oracle. This proves the mechanism, not production accuracy. |
| `template` | The semantic decomposition is reusable, but this repository does not claim a complete local implementation. |
| `credentialed_connector` | A production implementation needs scoped authority, credentials, current external data, or a live provider. |

The address fixture demonstrates parsing, postal-form normalization, authority
identity, match codes, and typed verification output against an offline
directory. It is deliberately named `address-reference-verification`; it is
not an official USPS request. A production USPS node must publish its API
version, credentials/authority requirements, network effect, rate limits,
response provenance, retention policy, and stable failure taxonomy.

## Executable task families

| Arena task | Executable examples | Core candidate matrix |
|---|---|---|
| Golden customer table | `data-cleanup`, `golden-customer-table` | normalization × validation/deduplication × identity resolution × field merge |
| Address verification | `address-reference-verification` | parsing × normalization × reference match × emission |
| Verified product scrape | `browse-and-scrape`, `verified-product-dataset` | acquisition × extraction × money normalization × corroboration |
| Invoice schema | `document-to-schema` | text normalization × extraction × schema projection |
| Image assurance | `image-check-and-process` | decode × enhance/pass-through × inspection |
| Tabular prediction | `tabular-regression`, `tabular-classification` | split × model × evaluation |
| Calibrated forecast | `calibrated-time-series-forecast` | preparation × model × forecast × interval calibration |
| Organization entity graph | `organization-entity-linking` | normalization × blocking × linking × components |
| Repository repair | `tested-code-repair` | inspection × proposal × application × independent tests |
| Analytical dataset | `multi-feed-analytical-dataset` | decode × normalize × reconcile × validate/quarantine |

Together these map to 13 programs and 31 declared reference routes. The shared
registry contains 84 executable nodes. The declared routes are release-gate
fixtures; `UniversalSolver` searches additional combinations from the complete
compiler-admitted matrix.

## Other included DAG families

The catalog also contains reusable contracts for:

- contact and communication-endpoint verification;
- web change monitoring;
- transaction reconciliation;
- PII redaction and independent leakage checks;
- schema migration and shadow comparison;
- shipping-event normalization and notifications;
- incident/log/trace triage;
- dependency, license, advisory, and SBOM assurance;
- recommendation and policy-aware ranking;
- geospatial and authority enrichment;
- reproducible scientific experiments;
- structured numerical linear systems;
- deployment/canary/rollback workflows; and
- multi-system API business transactions with compensation.

Add an executable fixture only when it has real node functions, exact typed
ports, a full-registry admission result, frozen routes, an independent oracle,
and passing in-process and subprocess gates. Until then, preserve `template` or
`credentialed_connector` status.

## Solver profiles

| Profile | Allocation | Intended use |
|---|---|---|
| `quick` | fixed baseline plus highest-prior route | smoke test or first plausible solution |
| `balanced` | prior round, learned beliefs, bounded beam | normal local comparison |
| `broad` | prior, wider beam, seeded sprouts, two seeds | more coverage and interaction discovery |
| `exhaustive` | every compiler-feasible route, no hidden cap | small spaces or explicitly provisioned experiments |

Exhaustive mode refuses to run unless `--allow-exhaustive` is supplied. The
flag is acknowledgment, not a budget: the profile intentionally has no hidden
route limit. Inspect `route_count_upper_bound` first.

Every profile still performs full registry admission. Search limits how many
valid routes receive experiment resources; it never hides candidates from the
compiler. Each round reports the Cartesian upper bound, evaluated,
constraint-eliminated, heuristic-skipped, and unvisited routes.

## What the solver returns

`UniversalSolver.solve()` returns:

- the admitted-space digest and complete per-slot candidate matrix;
- every search round, budget, coverage report, and belief revision;
- every compiled plan and immutable run receipt;
- separate development and holdout receipt identities; holdouts run only on
  the development-selected champion/fallback shortlist and never train priors;
- acceptance rates, metric means/variances, hard-constraint state, and a
  transparent normalized weighted score;
- the Pareto set;
- an accepted champion, or `no-accepted-route`; and
- separately benchmarked fallback routes selected from evidence and route,
  implementation, and declared failure-mode diversity.

The solver does not create an untested fallback by combining pieces of several
routes. It does not place learned weights in frozen plans. It never converts a
failed verifier result into success.

## Extend with a coding harness

Use `@solve-universal-dag` for an end-to-end Arena implementation. Use
`@create-solution-template` when only the semantic decomposition is needed,
`@author-node-pack` for reusable implementations, and
`@design-autoresearch-campaign` when the harness will generate or mutate code.

The minimum sequence is:

1. Freeze task, authority, inputs, output schema, oracle, objectives, and budget.
2. Refine a template into atomic typed slots.
3. Discover or author nodes and snapshot the registry.
4. Admit every candidate against every slot.
5. Run a fixed baseline and suggested routes.
6. Learn observational priors and allocate bounded new routes.
7. Confirm finalists on untouched cases and the intended runtime boundary.
8. Publish the frozen champion, diverse fallback routes, receipts, unvisited
   space, and remaining production gates.

For a Kaggle competition, keep EDA, split design, leakage checks, missingness,
encoding, feature generation, feature selection, model family, calibration,
ensemble, and submission validation as separate slots or nested subgraphs. The
bundled regression/classification fixtures prove the API only; a competition
claim requires the real immutable dataset, competition metric, legal rules,
fixed validation boundary, repeated seeds, and a submission receipt.
