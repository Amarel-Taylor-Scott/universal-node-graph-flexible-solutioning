# Template instantiation reference

Read `../../../../SOLUTION_TEMPLATE_PROTOCOL.md` and inspect `catalog/templates/`.

1. Choose every possibly relevant template; do not silently take the first hit.
2. Restate the concrete task, inputs, outputs, hard constraints, and oracle.
3. Compare each template slot to the task. Explain additions and removals.
4. Split mega-slots until candidates are genuine substitutes and intermediate
   contracts are independently testable.
5. Refine schematic state envelopes into domain types, schemas, units, and
   cardinalities.
6. Preserve stages as visible submatrices only; they are not nodes.
7. Represent task loops/branches as structured slots. Keep optimizer refinement
   policies in the control plane with an explicit stop/resource budget.
8. Treat pass-through as an explicit identity candidate and admit it only for
   identical types and genuinely optional semantics.
9. Validate the program before searching a node registry.

Reject tool/provider-named semantic steps, implicit rewiring, optimizer steps,
opaque unversioned state, and templates retained without task justification.
