---
name: create-solution-template
description: Create, refine, validate, or contribute a reusable Universal Node Graph solution template. Use when an agent must turn a task class, workflow, application, DAG, ticket family, or domain into ordered stages with atomic typed obligations; author a strict linear-template blueprint; compare it with the reference catalog; or compile and export a portable SolutionTemplate without selecting implementation nodes.
---

# Create a reusable solution template

Read `../../../SOLUTION_TEMPLATE_PROTOCOL.md` before authoring. Read
`references/blueprint-authoring.md` when using the JSON blueprint workflow.

## Choose the representation

- Use a `LinearTemplateBlueprint` for a left-to-right series of stages whose
  slots each consume and produce the evolving task state.
- Use the full Python `SolutionTemplate` and `ProgramGraph` models for branches,
  joins, maps, barriers, composite subgraphs, or multiple typed values.
- Never flatten a real branch or merge merely to fit the convenience format.

## Author

1. State the reusable problem class independently of any implementation.
2. Define external input/output meaning and an independent success contract.
3. Inspect nearby templates with `solutiongraph templates list` and
   `solutiongraph templates show <id>`.
4. Decompose the problem into stages for navigation, then atomic obligations.
5. Give every slot one purpose, one independent success contract, and one or
   more required semantic capabilities.
6. Split a slot when candidates would need different types, effects, authority,
   success checks, or reusable intermediate values.
7. Declare allowed effects and granted permissions independently. Never infer
   authority from the likely implementation.
8. Keep optimization and discovery policies outside the executable slot order.

## Validate and export

```bash
solutiongraph templates validate path/to/blueprint.json
solutiongraph templates create path/to/blueprint.json \
  --output path/to/template.json
solutiongraph doctor
pytest tests/test_solutiongraph*.py -q
```

For a catalog contribution, regenerate with:

```bash
solutiongraph catalog export --output catalog
```

## Review gate

Reject the template if a stage is selectable, a slot names a vendor or package,
an oversized action hides independently replaceable work, a success contract
only restates the purpose, permissions are implied, a pass-through changes the
type, or a refinement loop has no explicit budget.

The template is a reusable starting hypothesis. A production instantiation
must refine schematic state values into versioned domain types and schemas.
