# Universal LLM-Guided Graph Search

## Goal

Make graph construction, graph criticism, graph mutation, and experiment selection first-class search problems. The LLM is a proposal engine and critic, not the evaluator. Every proposed graph or subgraph still has to compile, execute, and win against an independent metric/evaluation boundary.

The system must work across Kaggle-style tabular, time-series, NLP, vision, recommendation, multimodal, scientific, and unusual AI/ML tasks without assuming a fixed pipeline length or fixed node positions.

## Core rule

**Search over graph structure, routes, subgraphs, node implementations, parameters, hyperparameters, task interpretations, validation designs, feature spaces, packages, and resource allocations. Do not search only model hyperparameters.**

The existing campaign ledger remains the immutable ancestry/evidence record. The existing adaptive layer remains responsible for resource promotion and early stopping. `solutiongraph.llm_search` sits before compilation/evaluation and produces inspectable proposal candidates.

## Why the question bank is combinatorial instead of a giant text file

The default `QuestionSpace` has ten independent axes:

- 26 focus targets
- 12 context-visibility policies
- 22 intents
- 32 question families
- 26 expert/theory/persona lenses
- 6 time/resource lenses
- 5 reasoning-language modes
- 6 evidence stances
- 29 mutation operators
- 14 proposal kinds

That is **417,348,771,840 possible prompt specifications** before task-specific values, graph neighborhoods, model routes, temperatures, seeds, or research documents are included.

Taedri should never materialize that full space. It should sample it reproducibly, stratify for diversity, learn which question families work by task family, and spend model calls only where expected value is high.

## Context masking is a search dimension

A proposal can be generated with any of the following views:

- `blind`: no current solution context
- `task_only`: task statement only
- `schema_only`: task plus schema
- `blueprint`: task/schema/high-level blueprint
- `local_neighborhood`: only the node/subgraph neighborhood under review
- `graph_only`: current graph but not historical results
- `results_only`: metrics without the implementation
- `failures_only`: known failures and negative evidence
- `research_only`: external research without current graph history
- `partial_history`: graph plus selected results
- `full_history`: all available state
- `counterfactual_history`: failures/research while hiding the current winner

This is deliberate. Full context can create anchoring and imitation. Blind agents create independent hypotheses. Partial context agents can diagnose a layer without being biased by unrelated work. The champion loop should learn which visibility policy is useful for which task and mutation class.

## Question families

The initial families include the direct questions we want every graph to face repeatedly:

- What is next?
- What did we not do?
- What did we do too much of?
- What is the greatest improvement opportunity?
- What is the greatest weakness?
- What is the top concern?
- Which concern is probably least important?
- What are the strongest pros and cons?
- Which assumptions are fragile?
- How can this fail?
- Where can leakage occur?
- How can validation disagree with the leaderboard?
- What distribution shift exists?
- What feature interactions or latent factors matter?
- What data-quality defect matters?
- How should uncertainty change the route?
- Would calibration/threshold/ranking changes help?
- What robustness test could falsify the winner?
- What gives the most score/information per compute unit?
- Which expensive step is least valuable?
- What memory/hardware/runtime change helps?
- Which PyPI package should replace custom code or unlock a new route?
- What analogous problem has a transferable solution?
- What would the strongest opposite strategy do?
- What is the smallest graph that could win?
- What would we do with abundant compute?
- Can symbolic/deterministic methods combine with learned methods?
- Can unsupervised/self-supervised methods improve supervised learning?
- Which deliberately diverse model would improve the ensemble?
- Which research/open-source method should be tested?
- Which prior competition pattern transfers without cargo culting?

These are templates, not static prompts. They are crossed with target, context, lens, mutation, and proposal type.

## Lenses and deliberate cognitive diversity

The same question should be asked from different technical priors: Kaggle grandmaster, classical statistics, Bayesian statistics, information theory, optimization theory, computational complexity, numerical analysis, signal processing, control theory, physics, symbolic mathematics, deep learning, causal inference, MLOps, data engineering, adversarial review, resource-constrained engineering, outsider, and competition-postmortem perspectives.

Time/resource lenses deliberately ask for solutions as if the solver lived in a different constraint regime: pre-deep-learning, classical statistics, modern systems, future hardware, extreme compute, or extreme scarcity.

Reasoning-language modes include native response, translation-based reframing, formal mathematical framing, and pseudocode-first reasoning. These are hypothesis-diversity tools, not claims that one language or persona is intrinsically superior.

## Proposal contract

An LLM proposal must be structured. At minimum it records:

- kind
- summary
- falsifiable hypothesis
- graph/mutation operations
- expected gain if the proposer can estimate it
- proposer confidence
- novelty
- risk
- estimated cost units
- evidence required
- assumptions
- smallest falsification test
- source prompt digest
- model route
- parent candidates

The compiler, not the LLM, determines whether operations are legal. The evaluator, not the LLM, determines whether the proposal is good.

## Multiple Ollama models

`ModelRoute` is provider-neutral but defaults to Ollama. A campaign can round-robin or bandit-select among DeepSeek, Kimi, GLM, Qwen, coding-specialized models, small cheap models, and larger expensive models.

The same prompt may be sent to multiple models. Different prompts may be routed to different models based on learned historical utility. Model identity, temperature, seed, context budget, and tags are part of the experiment provenance.

## Voting is triage, not truth

LLM critics can vote on proposals using support and confidence, with optional dimensions such as novelty, leakage risk, expected value, implementation risk, or fit with known evidence.

Votes are only a scheduling heuristic. A high-consensus proposal can still fail. A contrarian low-consensus proposal can win. Empirical evaluation remains authoritative.

Disagreement is useful information and should itself influence exploration: high disagreement can justify a cheap falsification experiment instead of suppression.

## Mutation surface

The initial structural operators include:

- add/remove/replace node
- wrap a node as a subgraph
- expand/collapse subgraph
- add/remove/redirect edge
- add branch/loop/barrier/map-reduce
- swap route
- change relative ordering constraint
- change parameter/hyperparameter
- change feature set
- change validation
- change objective
- change model family
- change ensemble
- change package
- change runtime/fidelity
- fork graph
- cross over graphs
- ablate a component
- restore an ancestor

No operator should depend on numeric stage positions. Ordering should come from typed inputs/outputs and explicit dependency constraints.

## Recommended Kaggle champion loop

1. Ingest competition statement, files, metric, submission format, compute limits, and known external-data rules.
2. Rephrase the task with several independent LLM routes, including blind and research-informed variants.
3. Build several minimal seed graphs rather than one canonical pipeline.
4. Compile every seed. Reject invalid graphs before expensive work.
5. Run very cheap diagnostics to identify leakage, split strategy, baseline signal, obvious feature families, and runtime constraints.
6. Generate proposal batches from multiple context views and lenses.
7. Deduplicate semantically similar proposals.
8. Ask independent critic routes to vote and identify assumptions/failure modes.
9. Schedule a deliberately mixed portfolio: high-confidence exploitation, disagreement tests, novelty exploration, and ablations.
10. Compile every mutated graph/subgraph before execution.
11. Use multi-fidelity evaluation and early stopping to kill weak candidates cheaply.
12. Record candidate ancestry, receipts, resource use, split definitions, seeds, packages, and environment digests.
13. Promote empirically strong candidates.
14. Cross over compatible winners at graph/subgraph boundaries.
15. Ask postmortem agents what was learned and which beliefs should change.
16. Update priors for question families, lenses, mutation operators, model routes, and task families.
17. Repeat until budget, convergence, or competition deadline.
18. Preserve diverse finalists for leaderboard uncertainty rather than collapsing prematurely to one local-CV winner.

## Research-derived design alignment

Modern agent frameworks such as Strands distinguish deterministic workflows, graphs with conditional/cyclic execution, and autonomous swarms, and allow graphs or swarms to be nested as nodes. Taedri should retain that compositional flexibility but represent it as compiler-visible graph/subgraph contracts rather than opaque runtime orchestration.

Population-based training demonstrates a useful exploit/explore pattern: copy strong candidates, mutate them, and continue evaluation. Taedri should generalize that idea from hyperparameters to graph topology, node implementations, feature sets, validation designs, package choices, and LLM proposal routes.

Optuna's sampler/pruner split is another important separation: generation policy and termination policy should be independent. Taedri should support random, grid, Bayesian/TPE, evolutionary, novelty, bandit, LLM-proposed, and hybrid proposal policies while keeping pruning/promotion policies pluggable.

## Next implementation layers

The new module is intentionally provider-neutral and does not yet make network/model calls. The next layers should be implemented as separate adapters and nodes:

1. Ollama proposal adapter with structured JSON/schema validation and retry/repair.
2. Research proposal node that searches papers, package docs, GitHub/Kaggle solutions, then emits provenance-backed proposals.
3. Graph-operation compiler that translates approved proposal operations into semantic graph edits.
4. Learned proposal scheduler using campaign history to estimate expected value by question family × lens × context view × model route × task family.
5. Diversity/novelty archive so the search does not converge to hundreds of near-identical XGBoost/CatBoost graphs.
6. Cross-competition memory with strict leakage boundaries and transferable meta-features.
7. Kaggle adapter for competition metadata, dataset fingerprints, local CV, submission artifacts, and public/private leaderboard receipts where permitted.
8. PyPI/package discovery node with environment compatibility and license/security checks.
9. Automatic ablation generator for every optional node/subgraph.
10. Counterfactual and negative-result memory: record what failed, where, at what fidelity, and under which split.
11. Graph crossover at typed subgraph interfaces.
12. Multi-objective Pareto archive for score, runtime, memory, cost, robustness, variance, and complexity.
13. Meta-learning over hundreds of competitions to learn which mutation/operator/question families are useful under which dataset/task signatures.

## Non-negotiable safety against optimizer self-deception

- Hidden evaluation remains outside candidate control.
- LLM confidence cannot directly mark a graph as successful.
- Public leaderboard score is evidence, not the sole objective.
- Validation definitions are versioned and immutable within a comparable trial cohort.
- Every preprocessing step must respect fold boundaries.
- External-data and competition-rule permissions are explicit capabilities.
- Candidate code cannot rewrite the evaluator or its receipts.
- Failed and negative experiments are retained to reduce repeated dead ends.
- Search-budget exhaustion is a valid stop condition.

The target system is therefore not "an LLM that writes Kaggle code." It is a self-tuning experimental operating system where deterministic graph compilation, statistical evaluation, adaptive search, LLM proposal diversity, research transfer, and immutable experiment memory all reinforce one another.
