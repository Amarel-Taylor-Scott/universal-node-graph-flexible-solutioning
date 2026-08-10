# Search and experiment reference

Search starts after compiler admission.

- Prior: fastest deterministic starting route; no optimality claim.
- Beam: bounded exploitation; disclose width and skipped/unvisited routes.
- Sprout: seeded unique sampling around full/partial anchors; disclose evaluation,
  attempt, and mutation budgets plus duplicates and invalid samples.
- Successive halving: compare one resource rung, reject failed/incomplete plans,
  and promote a deterministic accepted fraction.
- Exhaustive: stream every feasible route with no hidden cap; a supplied budget
  makes the result incomplete by definition.

Always preserve the belief revision, query/snapshot identities, route assignments,
seed, resources, verifier, and receipts. Use fixed baseline, representative cases,
holdouts, repeated stochastic seeds, best-so-far versus budget, Pareto objectives,
and failure-diverse fallbacks. Treat receipt-derived node effects as observational
unless controlled assignment supports a causal claim.

Never use an optimizer score to grant authority, promote an unaccepted plan,
compare trials at different resource rungs as if equal, hide early stopping, or
call an incomplete search globally optimal.
