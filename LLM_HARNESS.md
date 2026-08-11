# Coding-agent and LLM harness integration

The repository intentionally uses progressive disclosure instead of copying one
large prompt into every vendor-specific file.

| File | Purpose | Loading behavior |
|---|---|---|
| `AGENTS.md` | Canonical repository rules and compact architecture guardrails | Codex, Copilot agents, Cursor, and Windsurf read it directly |
| `CLAUDE.md` | Claude Code adapter | Imports `AGENTS.md` using Claude's supported `@` syntax |
| `GEMINI.md` | Gemini CLI adapter | Imports `AGENTS.md` using Gemini's supported `@` syntax |
| `.github/copilot-instructions.md` | Broad Copilot IDE compatibility | Points at the canonical rules and specification |
| `.agents/skills/model-solution-graph/SKILL.md` | Detailed on-demand modeling procedure | Loaded only when a matching task activates the workspace skill |
| `.agents/skills/model-solution-graph/references/` | Node, discovery, template, and experiment checklists | Loaded selectively for the active operation |
| `.agents/skills/create-solution-template/SKILL.md` | Template decomposition and strict blueprint workflow | Loaded for reusable template authoring |
| `.agents/skills/author-node-pack/SKILL.md` | Node ABI, sidecar, manifest, and registry workflow | Loaded for reusable implementation packs |
| `.agents/skills/execute-solution-graph/SKILL.md` | Runtime, artifact, fallback, verification, and executable-domain workflow | Loaded for frozen-plan execution work |
| `.agents/skills/benchmark-solution-graph/SKILL.md` | Search-budget, receipt, holdout, and Pareto workflow | Loaded for route experiments |
| `.agents/skills/design-autoresearch-campaign/SKILL.md` | Population lineage, generated-code quarantine, evaluator isolation, and promotion workflow | Loaded for iterative LLM-generated improvement campaigns |
| `.agents/skills/design-topology-family/SKILL.md` | Alternative graph-shape contracts, budgets, lineage, and comparison workflow | Loaded when the harness may insert/remove/reorder semantic obligations |
| `.agents/skills/author-structured-workflow/SKILL.md` | Conditional, merge, composite, and bounded-loop authoring workflow | Loaded when the task needs data-dependent or iterative control |
| `UNIVERSAL_NODE_GRAPH_SPEC.md` | Normative architecture | Read for design or implementation work |
| `NODE_REPOSITORY_PROTOCOL.md` | Node packs, sparse metadata, embeddings, handshake, and snapshots | Read for catalogue or discovery work |
| `SOLUTION_TEMPLATE_PROTOCOL.md` | Cross-domain stages, atomic slots, pass-through, refinement | Read for decomposition/template work |
| `EXECUTION_PROTOCOL.md` | Frozen-plan execution, runtime adapters, artifacts, recovery, and receipts | Read for runtime or notebook work |
| `STRUCTURED_CONTROL_PROTOCOL.md` | Branch, merge, composite, loop, map, reduce, and barrier rules | Read before implementing control flow |
| `TOPOLOGY_SEARCH_PROTOCOL.md` | Explicit graph variants and full search accounting | Read before topology generation or selection |
| `STREAMING_PROTOCOL.md` | Event-time and production streaming boundaries | Read for stream graphs or adapters |
| `PROVENANCE_AND_RESUME.md` | Exact local resume and interoperable provenance | Read for durable or lineage integrations |
| `AGENT_PLAYBOOK.md` | Patterns, anti-patterns, and end-to-end delivery workflow | Read before implementing a new domain |
| `RESEARCH_FOUNDATIONS.md` | Primary-source rationale | Read when evaluating or changing a tradeoff |
| `AUTORESEARCH_REVIEW.md` | Verified AutoResearch/package lessons and numerical-node decomposition | Read for autonomous campaigns or solver packages |
| `llms.txt` | Machine-friendly documentation map | Entry point for crawlers and unfamiliar harnesses |

## Why not duplicate the full prompt?

Duplicated prompt files drift, consume context, and create precedence conflicts.
The thin-adapter pattern gives each harness its supported discovery filename
while preserving one reviewable source of behavioral instructions.

Instruction files guide agent behavior; they are not an enforcement boundary.
The Python compiler, JSON Schemas, diagnostics, tests, content digests, and CI
enforce architecture independently of whether a model followed a prompt.

## Recommended harness workflow

Bootstrap a task-specific workspace without copying the entire framework:

```bash
solutiongraph init <workspace> --template <template-id>
```

The command fails on an existing destination and records the exact selected
template digest. It never invents implementations, authority, or evidence.

1. Load the generated and repository root instruction files.
2. Activate the narrow template, node-pack, structured-control, topology,
   executor, benchmark, AutoResearch, or end-to-end skill for the requested operation.
3. Negotiate node discovery and freeze a receipt-backed registry snapshot.
4. If the task needs structured control, lower it deterministically. If graph
   shape is a variable, freeze a `TopologyFamily`. Then compile the semantic
   program and freeze a plan before implementing runtime adapters.
5. Reconstruct the plan at execution, use explicit runtime authority, and retain
   artifacts plus an independent verification receipt. Prefer the subprocess
   adapter for trusted local lifecycle separation, set
   `allow_in_process_python=False`, and append every result immediately to a
   receipt journal. Use a stronger external boundary for untrusted code.
6. Run `solutiongraph conformance` and universal tests before domain-specific
   integration tests.
7. Include discovery receipts, compiler diagnostics, search reports, frozen
   plan/admitted-space digests, execution receipts, rejected cases, and
   limitations in the review output; do not rely on prose assurance.
8. For generated-code campaigns, freeze the evaluation boundary before the
   first proposal, preserve a population DAG and negative evidence, and keep
   candidate code unable to redefine or inspect hidden evaluation assets.
