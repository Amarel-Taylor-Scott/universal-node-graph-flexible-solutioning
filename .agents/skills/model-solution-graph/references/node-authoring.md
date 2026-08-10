# Node authoring reference

Read `../../../../NODE_REPOSITORY_PROTOCOL.md` for the full protocol.

Before code, write the node's stable ID/version, actual implementation artifact
digest, runtime/entrypoint, named nominal ports, cardinalities, parameter schema,
capabilities, effects, permissions, determinism, idempotency, pre/postconditions,
invariants, failure taxonomy, resources, verifier, and source provenance.

Then:

1. Make the entrypoint importable and test it in isolation.
2. Add valid and invalid fixtures for every port/parameter contract.
3. Prove effects and permissions are neither missing nor broader than required.
4. Add a concrete `Candidate`; expand each finite meaningful choice visibly.
5. Add a sparse `NodeDescriptor` only from inspected facts.
6. Add embeddings only with exact model/revision/dimensions/distance identity and
   a source-text digest. It is valid to add none.
7. Run registry validation and admission against at least one compatible and one
   incompatible semantic slot.
8. Regenerate catalogue artifacts and assert deterministic output.

Never place empirical quality/cost/latency in `NodeSpec`, use a mutable tag as an
artifact identity, hide authority in deployment configuration, or let descriptor
text repair an incomplete ABI.
