# `solutiongraph.nexting`

`nexting` is the control-plane package for one question:

> Given the present knowledge state and delegated goal, what bounded work should be proposed next?

It does not compile graphs, execute nodes, install packages, grade candidates, or promote champions.

## Package map

| File | Owns | Must not own |
|---|---|---|
| `contracts.py` | Knowledge, question, proposal, decision, result, and receipt wire contracts | Runtime clients, domain rules, mutable stores |
| `actions.py` | Optional typed payload helpers for reference answer families | Closed global ontology or action execution |
| `prompts.py` | Context-exposure manifests, prompt frames, personas, and lazy variation | Model clients or hidden knowledge retrieval |
| `strategies.py` | Replaceable ways to propose next actions | Compiler, evaluator, or promotion authority |
| `engine.py` | Strategy allocation, semantic clustering, ranking, conflict-aware selection, and Solver Cell loop | Domain-specific ML logic or graph mutation implementation |
| `learning.py` | Evidence-only allocation beliefs | Task meaning, hard validity, or holdout access |
| `adapters/` *(planned)* | Bridges to compiler, search, mutation, interrogation, research, Ollama, experiments, and package qualification | Redefinition of those systems' source contracts |

## Naming model

- **Solver Cell**: one recursive `knowledge → question → decision → action evidence → knowledge` loop.
- **Knowledge State**: immutable answer to “what is presently known?”
- **Next Strategy**: one method for proposing what could happen next.
- **Next Action Proposal**: typed, non-authoritative proposed work.
- **Action Executor**: adapter that delegates a selected proposal to an existing subsystem.
- **State Reducer**: produces a new immutable knowledge revision from action results.
- **Iteration**: a receipt/timeline ordinal only, never graph execution order.

## Extension rule

New domain behavior should normally be implemented as:

1. a namespaced action payload schema;
2. one or more `NextStrategy` implementations in a specialized pack;
3. an `ActionExecutor` adapter to an existing subsystem;
4. external evaluation evidence;
5. tests proving that proposal authority does not bypass compiler, runtime, policy, or evaluator boundaries.

Do not add a giant domain-aware `Agent`, `Employee`, or `Worker` subclass to this package. The Solver Cell remains domain-neutral; domain expertise is composed through facts, references, strategies, recipes, policies, and adapters.
