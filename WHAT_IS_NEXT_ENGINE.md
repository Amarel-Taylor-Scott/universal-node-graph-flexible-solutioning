# The Solver Cell and What-Is-Next Engine

Status: implementation preview 0.1  
Reference package: `solutiongraph.nexting`  
Primary principle: **what is presently known determines what may be useful next**

## Executive decision

The universal graph system should not be organized around a fixed sequence of
human-sounding stages such as:

```text
understand → plan → build → test → improve → finish
```

Those labels are useful as views, but they are not a sufficiently general
execution model. An expert rarely walks through one universal ordered list.
An expert repeatedly performs a much smaller loop:

```text
What do I presently know?
        ↓
What is next?
        ↓
Take or delegate one or more bounded actions
        ↓
Observe what happened
        ↓
Update what is presently known
        ↓
Ask again
```

The smallest reusable autonomous unit in Taedri/Kadri is therefore named a
**Solver Cell**.

A Solver Cell is not a giant agent class. It is an orchestration boundary that
contains five replaceable seams:

1. a durable `KnowledgeState`;
2. a `QuestionFactory` that asks a scoped What-Is-Next question;
3. a `WhatIsNextEngine` that invokes answer strategies and chooses a typed
   proposal or portfolio;
4. an `ActionExecutor` that delegates the selected work to the appropriate
   graph, tool, person, model, runtime, or service;
5. a `StateReducer` that converts action evidence into a new immutable
   `KnowledgeState`.

The loop is intentionally smaller than a graph solver, an optimizer, an LLM
harness, or a Kaggle pipeline. Those systems become possible action executors or
answer strategies rather than being merged into one fragile object.

The canonical loop is:

```text
KnowledgeState
    → NextQuestion
    → StrategyOutcome[]
    → ProposalCluster[]
    → NextDecision
    → ActionResult[]
    → KnowledgeState'
```

Every transition is content-addressed and receipted.

## The most important semantic boundary

The What-Is-Next Engine answers:

> What bounded work should be proposed next, given the current knowledge,
> delegated goal, policies, and budget?

It does **not** answer any of these questions by itself:

- Is a proposed graph compiler-valid?
- Does a node have permission to perform an effect?
- Did an implementation execute successfully?
- Did a model improve the competition metric?
- Is a package safe or licensed for the intended use?
- Should a candidate be promoted to champion?
- Did an LLM response tell the truth?

Those remain the responsibilities of existing compiler, runtime, verifier,
experiment, package, policy, and evidence boundaries.

This separation is non-negotiable:

```text
proposal authority       ≠ compiler authority
compiler validity        ≠ runtime success
runtime completion       ≠ evaluator acceptance
development acceptance   ≠ holdout confirmation
LLM confidence           ≠ empirical evidence
question popularity      ≠ independent support
```

The Next Engine may propose a graph change. The normal graph compiler must
still reject or admit it. It may propose a package. An isolated package
qualification process must still inspect and test it. It may propose a model or
feature. A declared experiment must still evaluate it.

## Vocabulary

### Solver Cell

The smallest recursive unit that repeatedly observes knowledge, asks What Is
Next, delegates work, records evidence, and updates knowledge.

A Solver Cell may be very small:

```text
Goal: determine whether validation leakage exists
```

or broad:

```text
Goal: produce the strongest competition solution within the campaign budget
```

Broad cells should normally delegate narrower goals to child cells rather than
carrying every concern in one context.

### Knowledge State

An immutable, content-addressed snapshot of what the cell presently knows. It
contains compact facts and references to larger artifacts. It is not equivalent
to an LLM context window.

### Knowledge Reference

A pointer to an artifact, folder, database query, graph revision, blueprint,
prior run, notebook, receipt set, source report, model output, package record,
or other content-addressed resource.

The actual bytes can remain outside prompt context.

### Knowledge Fact

A compact assertion that deterministic rules, learned policies, and prompt
assemblers may inspect without loading a larger artifact.

Examples:

```text
ml.validation-selected = grouped-cross-validation
ml.target-kind = continuous
resource.gpu-available = false
experiment.baseline-score = 0.8124
```

Facts must retain evidence references where meaningful.

### Unknown

An explicit unresolved question. An unknown can block a decision, nominate one
or more probe families, and carry importance.

Unknowns are first-class because an expert often answers What Is Next with:

> We do not yet know enough. Run these tests first.

### Next Question

One scoped invocation of the What-Is-Next problem. It freezes:

- the exact knowledge-state digest;
- scope and target;
- allowed answer families;
- context-exposure policy;
- active recipe, when any;
- parent question and recursion depth;
- optional extensions.

### Next Strategy

One way of proposing an answer. Strategies may be deterministic, heuristic,
similarity-based, learned, model-based, research-based, recipe-based, random,
or composite.

### Next Action Proposal

One typed proposed unit of work. A proposal may request context, a test,
research, a graph patch, an optimization, an experiment, a council, a child
cell, human review, pause, or stop.

A proposal is not execution.

### Proposal Cluster

A semantic grouping of proposals that request the same work despite different
wording, personas, models, or rationales. Ten paraphrases are not ten independent
ideas.

### Next Decision

A selected proposal or bounded portfolio with a disposition such as:

```text
one
ordered
parallel
ensemble
branch
defer
stop
```

### Action Result

Append-only evidence returned after the selected work has been delegated. It
may contain produced knowledge references, facts, resolved unknowns, metrics,
and failure information.

### Loop Iteration Receipt

Evidence for one observed Solver Cell iteration. Its ordinal is a timeline and
receipt field only. It has no semantic relationship to node position in a
solution graph.

## Why “What Is Next?” is more general than “Which node comes next?”

A common design error is to interpret What Is Next as:

> Which node should be appended to the graph?

That is only one answer family. The correct answer could instead be:

- inspect more context;
- summarize a folder or database region;
- retrieve analogous solved problems;
- instantiate one or more existing blueprints;
- run a cheap diagnostic;
- compare split strategies;
- profile a suspicious column;
- research current packages;
- research public solutions;
- ask several independent models;
- create a critic council;
- wait for a running experiment;
- simplify the current graph;
- remove a harmful node;
- extract a reusable subgraph;
- mutate a parameter space;
- launch low-fidelity trials;
- promote survivors to a higher fidelity;
- ensemble several completed solutions;
- request human approval;
- pause because a required external input is missing;
- stop because the delegated goal is satisfied.

A universal control plane must preserve all of these as typed alternatives.

## Answer-family taxonomy

The action vocabulary is open and namespaced. The reference package defines a
small initial family.

### Context and understanding

```text
next.gather-context
next.run-probe
next.research
```

These reduce uncertainty without changing the solution graph.

### Reuse and construction

```text
next.retrieve-blueprint
next.instantiate-graph
next.propose-graph
next.propose-subgraph
next.propose-node
next.propose-package
```

These nominate reusable or new solution structure.

### Improvement and search

```text
next.mutate-graph
next.replace-node
next.configure
next.optimize
next.evaluate
next.compare
next.ensemble
```

These explore or assess alternatives.

### Delegation and governance

```text
next.spawn-subloop
next.ask-council
next.request-human
next.continue-recipe
```

These delegate work or continue a declared policy.

### Lifecycle

```text
next.pause
next.stop
```

Plugins may define additional namespaced action families. Unknown semantic
extensions must be understood by the component that executes them; an unknown
action is never silently treated as a generic node insertion.

## Repository organization

The What-Is-Next implementation is isolated in one package:

```text
solutiongraph/nexting/
├── __init__.py      public facade
├── actions.py       typed optional payload shells for answer families
├── contracts.py     knowledge, question, proposal, decision, and receipt objects
├── prompts.py       context exposure, prompt frames, personas, lazy variants
├── strategies.py    pluggable answer strategies and strategy registry
├── engine.py        allocation, reconciliation, ranking, and Solver Cell loop
└── learning.py      evidence-only factor beliefs
```

The package is intentionally not named `agents`, `employees`, `workers`, or
`orchestration` because those terms are overloaded. `nexting` describes one
specific concern: deciding what work to propose next.

Domain code should not be added to this package. Kaggle-specific question
banks, insurance-specific rules, browser-specific actions, and health-specific
policies belong in specialized packs or adapters that register generic
strategies and action executors.

## Knowledge is not context

This distinction is central.

A Solver Cell can know about millions of artifacts without presenting them all
to an LLM. `KnowledgeState` contains references, not a giant concatenated
prompt.

```text
Knowledge State
├── task contract reference
├── dataset profile reference
├── feature inventory reference
├── graph revision reference
├── blueprint search results
├── 800 experiment receipts
├── package qualification records
├── failure clusters
└── external research archive
```

One strategy may see only:

```text
goal + task type + graph input/output contracts
```

Another may see:

```text
full graph summary + top failures + available node catalog
```

A blind critic may see:

```text
original task + output contract only
```

A package researcher may see:

```text
missing capability + runtime constraints + license policy
```

The exact exposure is recorded in a `ContextManifest`.

## Context-exposure modes

The reference implementation defines several policy modes.

### Blind

The strategy receives the delegated goal and question but no prior references,
facts, unknowns, progress, or attempt history.

Use cases:

- reduce anchoring;
- produce independent decompositions;
- test whether history is causing negative transfer;
- generate a fresh analogy;
- create a baseline proposal distribution.

Blind does not mean the strategy has no task. It means it is blind to selected
prior work.

### Minimal

The strategy receives task and goal framing, but no selected knowledge
references. Compact high-level fields may still be supplied.

### Selective

The context compiler filters references using IDs, tags, visibility, confidence,
and budget.

This should be the default for most model-assisted strategies.

### Summary

Only precomputed summaries are included. Raw artifacts remain external.

### Full

All references admitted by policy are available, still subject to the context
budget and artifact permissions.

“Full” means full admitted context, not unlimited access to every file, secret,
holdout, or evaluator.

## Prompt frame

An LLM prompt should be compiled from structured slots rather than handwritten
as one opaque string.

The reference `PromptFrame` contains:

```text
system instruction
persona
original task
simplified task
delegated goal
What-Is-Next question
presently known summary
important unknowns
current graph summary
active recipe summary
prior attempts
constraints
negative check
counterfactual check
additional instruction
response contract
```

Every slot may be varied independently and receipted.

This enables questions such as:

- Did blind task reframing outperform history-informed reframing?
- Did a numerical-analysis persona produce better optimization proposals for
  this task family?
- Did asking for the smallest sufficient graph reduce cost without reducing
  score?
- Did an adversarial negative prompt discover leakage more often?
- Did a non-English reasoning lane produce semantically novel proposals?
- Did full history cause proposal collapse?

## Prompt personas and lenses

A persona is a controlled diversification frame, not a claim that the model
literally becomes a famous person.

Useful dimensions include:

```text
role
stance
theory
analogy
language
era
objective
resource regime
additional instruction
```

Example roles:

```text
data scientist
statistician
causal inference reviewer
information theorist
numerical analyst
optimization researcher
systems engineer
GPU memory specialist
feature engineer
competition grandmaster
scientific programmer
MLOps engineer
skeptical auditor
minimalist
maximalist
future maintainer
```

Example stances:

```text
constructive
skeptical
adversarial
minimalist
maximalist
risk-first
cost-first
accuracy-first
information-gain-first
```

Example theory lenses:

```text
Bayesian inference
information theory
causal inference
robust statistics
statistical learning theory
optimization theory
numerical conditioning
control theory
graph theory
decision theory
experimental design
symbolic regression
physics-inspired modeling
```

Example question shapes:

```text
yes/no
1–5 rating
1–10 rating
0–100 score
ranked list
forced choice
small/medium/large
counterexample
failure scenario
minimal patch
complete graph proposal
one next action
all feasible next actions
```

The Cartesian product can be enormous. It should be represented by a lazy
`PromptVariantSpace`, sampled under explicit budgets, and never expanded into a
million nearly identical files.

## Strategies for answering What Is Next

### Deterministic rules

A rule inspects facts, references, unknowns, progress, and policy.

Examples:

```text
IF validation is unknown
THEN propose validation probes before model search

IF required graph input has no producer
THEN propose compiler repair

IF the last three full-fidelity trials failed for memory
THEN propose a lower-memory candidate family
```

Rules are transparent, cheap, and reliable for well-understood conditions.

### Relational recipes

A recipe is not a fixed numbered list. Each recipe instruction declares the
references or fact predicates it requires and the artifacts or facts it is
expected to produce.

```text
profile data
    requires: dataset reference
    produces: dataset profile

select validation
    requires: dataset profile + grouping assessment
    produces: validation contract

train baseline
    requires: validation contract + metric contract
    produces: baseline receipts
```

The recipe strategy finds every currently ready instruction. Tuple order is only
serialization order.

A recipe can therefore:

- branch;
- expose several ready actions;
- skip inapplicable instructions;
- re-enter an earlier functional concern after new evidence;
- hand control to open-ended strategies when its declared frontier is
  exhausted.

### Similarity and muscle memory

Similarity strategies retrieve:

- prior task fingerprints;
- blueprints;
- graph families;
- successful subgraphs;
- node configurations;
- failure clusters;
- package records;
- experiment histories.

Similarity can use exact metadata, embeddings, categories, dataset fingerprints,
or learned channels. Retrieval nominates candidates. Compiler admission and
new-task evaluation remain mandatory.

### Probe-first strategies

A probe strategy converts important unknowns into cheap information-gathering
actions.

Examples:

```text
compare random/group/time splits
measure target leakage
profile missingness by split
run a tiny baseline
estimate model memory
check whether categories appear only in test
measure feature drift
```

This prevents the system from pretending that every What-Is-Next question can
be answered from the current context.

### Research strategies

Research is itself a next action. The strategy produces a bounded research
request with source kinds, freshness requirements, output contract, and whether
the researcher should be blind to previous work.

Research may target:

- current package options;
- competition rules;
- public papers;
- known methods for analogous tasks;
- source-code implementations;
- hardware compatibility;
- license constraints;
- failure explanations.

Research results return as references and facts. They do not directly modify
the solution graph.

### LLM strategies

An LLM strategy receives a compiled prompt and a strict response schema. The
model output is parsed into `NextActionProposal` objects.

An LLM strategy must record:

```text
model identity
model digest when available
prompt digest
context manifest digest
seed/options
response digest
parse failures
cost and latency
```

The LLM cannot execute its proposal or grade itself.

### Councils

A council is a composite proposal strategy. Member strategies should normally
run independently before seeing one another’s answers.

Possible council structures:

```text
independent panel
paired advocate/skeptic
domain-specialist council
blind-versus-informed comparison
cross-model panel
cross-language panel
Delphi rounds
tournament
critic tree
judge panel
```

Council outputs preserve member lineage and correlation groups. Agreement among
five prompts sent to the same model with nearly identical context is not treated
as five independent sources.

### Protected random exploration

A bounded random lane samples an allowed answer family even when current beliefs
prefer other strategies. This helps detect premature convergence and negative
transfer.

Random exploration is:

- seeded;
- budgeted;
- typed;
- compiler-gated downstream;
- retained as evidence whether it succeeds or fails.

## Strategy selection

The Next Engine does not always run every registered strategy.

A `StrategySelectionPolicy` can specify:

- explicit include/exclude sets;
- required strategy families;
- maximum strategies per family;
- protected blind share;
- protected random share;
- belief-guided ordering;
- cost-aware ordering;
- total call budget;
- parallelism.

A useful portfolio might contain:

```text
1 deterministic safety/rule lane
1 recipe lane
2 historical retrieval lanes
2 probe/diagnostic lanes
3 local LLM lanes
1 blind local LLM lane
1 research lane
1 protected random lane
```

The portfolio varies by knowledge state. Early in a task, task reframing and
validation may dominate. Later, mutation, ablation, ensembling, and error
analysis may dominate.

## Proposal reconciliation

Strategies frequently produce semantically identical work with different
wording. The engine clusters proposals using a semantic identity derived from:

```text
action kind
target reference
portable payload
prerequisites
expected outputs
```

Rationales, persona names, and superficial formatting do not create new
candidates.

Each cluster retains:

- every member proposal ID;
- every proposing strategy;
- representative proposal;
- aggregate confidence;
- aggregate uncertainty;
- complete provenance.

## Decision policy

The reference decision policy ranks clusters using an explicit projection of:

```text
expected utility
expected information gain
aggregate confidence
priority
diversity
uncertainty
cost
```

Hard constraints are applied before ranking. They are not score penalties.

Where several high-ranked proposals are marked `parallel_safe` and their
conflict keys do not overlap, the engine may select a parallel portfolio.

Examples of conflict keys:

```text
unknown:validation-design
file:features.py
resource:gpu-0
entity:customer-123
field:directory.address
```

A proposal may be high-scoring but still unsuitable for parallel execution
because it writes the same graph region or consumes an exclusive resource.

## Nested Solver Cells

A `next.spawn-subloop` action delegates a narrower goal to a child Solver Cell.

Examples:

```text
parent: build strongest tabular solution
child: determine validation design
child: analyze categorical variables
child: research package options
child: optimize CatBoost family
child: design ensemble
```

A child request freezes:

- delegated goal;
- scope;
- allowed answer families;
- context policy;
- budget overrides;
- required return contract.

The child returns a content-addressed result reference. The parent does not need
the child’s entire event history in its prompt.

Recursion is bounded by depth, calls, cost, wall time, failures, and
no-progress ceilings.

## Parallel child cells and ensembles

A parent may delegate several distinct hypotheses:

```text
Cell A: gradient-boosted trees
Cell B: neural tabular representation
Cell C: symbolic/physics features
Cell D: semi-supervised approach
Cell E: leakage and validation audit
```

The parent can later ask What Is Next with the child receipts available. A valid
answer may be:

- promote one route;
- run more discriminating tests;
- combine complementary features;
- ensemble predictions;
- preserve several Pareto solutions;
- reject all and reframe the task.

Parallel cells are not assumed independent. Correlation and shared ancestry
must be recorded.

## State reduction

The reference `AppendOnlyStateReducer`:

- adds produced knowledge references;
- adds produced facts;
- removes only explicitly resolved unknowns;
- links the child state to the parent digest;
- never mutates the prior state.

Production reducers may additionally:

- invalidate stale facts;
- add supersession relationships;
- update frontier references;
- update progress signals;
- materialize graph summaries;
- apply domain-specific policy.

A reducer must not erase failed evidence or rewrite prior receipts.

## Evidence-only learning

`NextBeliefModel` learns which factors tend to produce useful externally
accepted work.

Reference factors include:

```text
strategy
answer/action family
context policy
model
prompt or task tag
```

Possible future factors include:

```text
persona
language
theory lens
blueprint family
graph region
mutation operator
competition archetype
dataset fingerprint
resource regime
```

A belief score may change strategy allocation. It cannot:

- make an invalid proposal valid;
- bypass the compiler;
- grant effects or permissions;
- access a hidden holdout;
- alter an evaluator;
- convert a public leaderboard observation into training evidence without an
  explicit policy.

Protected blind and random lanes remain available so the learned policy can be
challenged.

## Relationship to existing SolutionGraph components

The new control plane composes existing modules instead of replacing them.

### `solutiongraph.model`

Defines semantic obligations, implementation contracts, ports, graphs,
candidates, admitted spaces, and frozen plans.

The Next Engine may reference or propose these resources. It does not redefine
them.

### `solutiongraph.compiler`

Admits and freezes proposed graph structures and implementation routes.

A `next.propose-graph`, `next.propose-subgraph`, `next.propose-node`, or
`next.mutate-graph` action should delegate to a compiler adapter.

### `solutiongraph.search` and `solutiongraph.topology`

Become answer strategies or executors for route and topology exploration.

### `solutiongraph.mutations`

Provides deterministic typed graph rewrites. The Next Engine may choose a
mutation; the mutation engine and compiler remain the authorities.

### `solutiongraph.interrogation`

Supplies deterministic, external, LLM, and human questions. Findings and
unknowns become part of `KnowledgeState`; selected checks can be
`next.run-probe` actions.

### `solutiongraph.intelligence`

Supplies task fingerprints and historical retrieval. It is a natural
Similarity Strategy backend.

### `solutiongraph.campaign`

Retains proposal ancestry, budgets, decisions, and trust boundaries for larger
candidate campaigns.

### `solutiongraph.harnessing`

Supplies multi-graph councils, evaluation firewalls, and separated authorities.

### `solutiongraph.evidence`, `experiments`, and `ranking`

Supply empirical observations, independent verification, Pareto analysis, and
promotion inputs.

### `solutiongraph.artifacts`, `durable`, and `ledger`

Supply knowledge storage, checkpointing, and append-only evidence.

## Kaggle-oriented expert loop

A competition campaign can now be described as repeated knowledge-driven
questions rather than one enormous fixed graph.

### Initial knowledge

```text
task description
competition metric
train/test files
submission format
resource budget
competition rules
```

### First What-Is-Next portfolio

Possible answers:

```text
rephrase the prediction task
identify target horizon
profile target distribution
identify groups/time/entities
retrieve analogous task blueprints
build the cheapest valid baseline
research current package options
```

### After profiling

New knowledge may reveal:

```text
strong group structure
high-cardinality categories
non-random missingness
train/test drift
possible leakage
memory limits
```

The next portfolio changes:

```text
compare grouped and random CV
probe leakage candidates
build CatBoost baseline
test count/frequency encodings
research entity-aware validation
```

### After baseline receipts

The next questions become:

```text
Which errors dominate?
Which slices are weak?
Which features are unstable?
Did validation variance exceed expected lift?
What is the cheapest discriminating experiment?
Which node or subgraph has the highest expected improvement?
What should be removed?
What did we not try?
```

### Later campaign

Possible answers include:

```text
ablate fragile features
mutate model parameters
add adversarial validation
try semi-supervised features
extract a model-family subgraph
run successive halving
ensemble diverse OOF predictions
challenge public leaderboard transfer
stop because marginal information gain is too low
```

The campaign still uses exact CV, holdout, metric, submission, and leakage
firewalls. “Expert-like” does not mean “free-form model chooses everything.”

## Recipes and open-ended control

A Solver Cell may receive a recipe that covers a trusted early bootstrap:

```text
load task contract
verify submission schema
profile target
identify groups/time
establish baseline validation
run baseline
```

When the recipe frontier is exhausted, open-ended strategies continue.

Alternatively, open-ended strategies can interrupt the recipe when they find a
critical blocker:

```text
possible leakage
invalid metric implementation
missing group boundary
prohibited package
insufficient memory
```

Recipe compliance is therefore relational and policy-controlled, not blind
step following.

## “What Is Next?” question banks

Question banks should be built from composable semantic dimensions rather than
millions of static strings.

### Intent

```text
next action
missing information
largest weakness
largest opportunity
unnecessary complexity
failure explanation
minimal repair
complete redesign
analogy
counterexample
simplification
verification
```

### Scope

```text
problem
graph
subgraph
node
port
feature
column
split
model
ensemble
runtime
package
receipt
failure cluster
```

### Exposure

```text
blind
minimal
selective
summary
full
adversarially withheld
```

### Granularity

```text
one action
three actions
small/medium/large
atomic change
subgraph change
complete route
campaign strategy
```

### Response contract

```text
yes/no
ordinal scale
0–100 score
ranked list
JSON patch
node manifest
graph proposal
experiment design
research query
stop decision
```

The question genome, source template, selected axes, model, seed, context
manifest, and response digest must all be preserved.

## Anti-patterns

### One giant Agent class

A class that owns memory, prompts, tools, graph mutation, execution, evaluation,
and learning is not universal. It is an untestable authority collapse.

### Fixed universal stage numbers

`step_1`, `step_2`, and `step_3` should not determine meaning. Dependencies,
readiness, guards, and contracts should.

### Context stuffing

Loading every prior file into every model call increases cost, leakage, and
anchoring. Knowledge references and exposure manifests are required.

### LLM-generated hidden execution

An LLM response must not directly execute Python, install a package, alter a
graph, or update a champion.

### Self-grading proposals

A proposer cannot be the sole evaluator of its own proposal.

### Agreement inflation

Repeated paraphrases from correlated prompts or models must not be counted as
independent evidence.

### Unbounded recursion

Child cells and councils require explicit depth, call, cost, failure, and
no-progress ceilings.

### Silent no-progress loops

The Solver Cell records progress and terminates or escalates after a configured
no-progress ceiling.

### Destructive knowledge overwrite

New evidence creates facts, invalidations, and supersession records. Prior
history remains available.

## Implemented reference flow

The dependency-free example is:

```text
solutiongraph/examples/what_is_next_solver_cell.py
```

It demonstrates:

```text
Knowledge: validation design is unknown
        ↓
What Is Next?
        ↓
Deterministic strategy proposes a validation probe
        ↓
Executor records grouped-CV evidence
        ↓
Knowledge: validation design is now resolved
        ↓
What Is Next?
        ↓
Strategy proposes stop for the delegated cell
```

The example intentionally does not call a model, network, package manager, or
Kaggle service.

## Migration strategy

### Phase 1: introduce the control-plane contracts

Implemented in `solutiongraph.nexting`.

### Phase 2: adapters for existing capabilities

Add adapters that translate selected next actions into:

- compiler proposals;
- topology search;
- graph mutations;
- interrogation checks;
- historical retrieval;
- experiment bundles;
- package qualification;
- research graphs;
- LLM harness calls.

### Phase 3: persistent knowledge and receipts

Add an artifact-backed `KnowledgeStore` and event projections so Solver Cells
can resume across processes and machines.

### Phase 4: first Kaggle campaign cell

Build one narrow campaign around:

```text
profile → validation → baseline → error analysis → bounded mutation → ensemble
```

The control is a fixed expert-authored policy. Treatment arms add learned,
retrieval, and LLM Next Strategies.

### Phase 5: nested specialist cells

Add specialist child cells for:

```text
validation
feature engineering
model family
resource optimization
error analysis
ensemble design
package research
```

### Phase 6: council and context experiments

Measure blind versus informed, single versus council, local-model portfolios,
and prompt-persona variations using common task cases and sealed holdouts.

### Phase 7: population learning across competitions

Learn factorized strategy beliefs while preserving task-family uncertainty,
protected exploration, and negative-transfer checks.

## Near-term implementation backlog

1. `KnowledgeStore` protocol backed by the existing artifact store.
2. Adapter from `TaskFingerprint` to compact `KnowledgeFact` records.
3. Adapter from `HistoricalRetriever` to `SimilarityRetriever`.
4. Adapter from `QuestionPack` findings to `Unknown` and `ProbeRequest`.
5. Adapter from `GraphMutationEngine` to `GraphChangeRequest` execution.
6. Adapter from topology/route search to `OptimizationRequest` execution.
7. Adapter from experiment bundles to `ExperimentRequest` execution.
8. Ollama `ModelClient` using strict structured output and exact model digest.
9. Package-research child cell with read-only package metadata collection.
10. Artifact-backed Solver Cell checkpoints and event journal projection.
11. Semantic proposal deduplication beyond exact portable payload identity.
12. Correlation-aware council aggregation.
13. Child-cell budget inheritance and return contracts.
14. UI projections for knowledge, unknowns, proposals, decisions, and lineage.
15. Controlled Kaggle benchmark comparing fixed, retrieval, LLM, and hybrid
    Next Strategies.

## Normative rules

1. A Solver Cell MUST consume an immutable knowledge-state revision.
2. A Next Question MUST identify the exact state digest it interrogates.
3. Knowledge references MUST NOT be assumed to be present in model context.
4. Model context MUST have an explicit exposure policy and manifest.
5. A Next Strategy MUST return typed proposals or abstain.
6. A proposal MUST NOT acquire compiler, execution, evaluation, or promotion
   authority from its proposer.
7. Semantic duplicate proposals MUST be clustered before candidate counts are
   reported.
8. Hard constraints MUST be applied before ranking.
9. Parallel selections MUST be conflict checked.
10. Every delegated action MUST return an `ActionResult`, including failure or
    blockage.
11. State reduction MUST create a new revision rather than mutate the prior
    state.
12. Unknowns MUST be removed only through explicit resolution evidence or a
    policy-authorized invalidation.
13. Child Solver Cells MUST have explicit recursion and resource ceilings.
14. Loop iteration ordinals MUST NOT define semantic graph order.
15. Beliefs MAY alter proposal allocation but MUST NOT alter validity.
16. Blind and random challenge lanes SHOULD remain protected in learned
    campaigns.
17. Public leaderboard observations MUST NOT silently become proposal-training
    evidence.
18. A cell MUST terminate, pause, or escalate after its no-progress ceiling.
19. Receipts MUST retain skipped, failed, blocked, and rejected work.
20. Graph execution and independent verification remain outside the What-Is-Next
    Engine.

## Final architectural statement

The universal system should be understandable as a hierarchy of Solver Cells:

```text
A Solver Cell knows by reference,
asks What Is Next under an explicit context policy,
uses a portfolio of replaceable answer strategies,
selects typed bounded work,
delegates that work to ordinary graphs and tools,
learns only from external evidence,
and asks again.
```

This framing is flexible enough for deterministic workflows, embeddings, small
models, LLM councils, research, graph search, optimization, human review, and
future specialized mechanisms without forcing them into one fragile class,
one fixed stage ontology, or one universal numeric sequence.
