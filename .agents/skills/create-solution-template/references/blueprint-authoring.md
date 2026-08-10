# Linear template blueprint authoring

Use `examples/custom-template-blueprint.json` as the copyable example and
`solutiongraph/schemas/template-blueprint.schema.json` as the wire contract.

## Required top-level fields

- `blueprint_model_version`: currently `0.1`.
- `id`, `version`, `title`, `description`.
- `task`: reusable outcome statement, not a tool recipe.
- `success_contract`: independent final acceptance rule.
- `domains`, `tags`: lowercase identifiers used for exact catalog filtering.
- `stages`: non-empty ordered array.

Optional top-level fields are `allowed_effects`, `granted_permissions`,
`invariants`, and namespaced `extensions`.

## Stage and slot fields

Each stage requires `id`, `title`, `description`, and a non-empty `slots` array.
Stage IDs and slot IDs must be unique within the blueprint.

Each slot requires:

- `id`: stable semantic obligation identifier;
- `purpose`: what outcome this slot produces;
- `success_contract`: independently checkable completion rule;
- `required_capabilities`: semantic capabilities nodes must implement.

Optional slot fields are `allowed_effects` and `optional`. Optional means the
obligation may admit a genuine identity candidate; it does not delete the slot
or waive its contract.

## Deterministic workflow

```bash
cp examples/custom-template-blueprint.json /tmp/my-template.json
solutiongraph templates validate /tmp/my-template.json
solutiongraph templates create /tmp/my-template.json --output /tmp/my-template.compiled.json
```

The parser rejects unknown fields, malformed identifiers, duplicate stage or
slot IDs, missing capabilities, empty contracts, non-namespaced extensions,
and malformed JSON. The compiled template then passes the same program and
stage validation as code-authored templates.

The linear blueprint intentionally cannot express arbitrary topology. Switch to
the full `SolutionTemplate` model rather than encoding a branch inside opaque
state or a mega-slot.
