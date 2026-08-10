# Reference catalogue

This directory is a checked-in projection generated from the canonical Python
contracts in `solutiongraph.reference_nodes` and `solutiongraph.template_library`.

- `index.json` lists every template and node pack with content digest and counts.
- `templates/` contains 18 reusable semantic templates and 317 atomic
  obligations, not fixed routes.
- `nodepacks/reference-core/` demonstrates node contracts, sparse descriptors,
  external connectors, registry capabilities, and a portable pack manifest.

Regenerate the JSON documents with:

```bash
solutiongraph catalog export --output catalog
python scripts/sync_catalog_explorer.py
```

The reference pack deliberately has no embeddings. Its capabilities advertise
exact, lexical, and enumeration modes, demonstrating graceful negotiation when
optional vector search is unavailable.
