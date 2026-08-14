# Reference catalogue

This directory is a checked-in projection generated from the canonical Python
contracts in `solutiongraph.reference_nodes` and `solutiongraph.template_library`.

- `index.json` lists every template and node pack with content digest and counts.
- `templates/` contains 42 reusable semantic templates and 733 atomic
  obligations, not fixed routes.
- `nodepacks/` contains nine portable packs spanning the core, standard-library
  data nodes, executable domain fixtures, semantic interrogation, and the data-
  science design atlas. Each pack preserves exact node and registry identities.
- `specialized-packs/` contains 26 advisory domain/practice package definitions;
  these nominate recipes and assets but do not replace compiler admission.
- `arena/` contains 63 honestly labeled executable, template-only, or
  credentialed-connector task-family contracts.

Regenerate the JSON documents with:

```bash
solutiongraph catalog export --output catalog
python scripts/sync_catalog_explorer.py
```

The reference pack deliberately has no embeddings. Its capabilities advertise
exact, lexical, and enumeration modes, demonstrating graceful negotiation when
optional vector search is unavailable.
