# Registry discovery reference

Read `../../../../NODE_REPOSITORY_PROTOCOL.md` before changing discovery behavior.

1. Exchange `HarnessCapabilities` and `RegistryCapabilities` first.
2. Require common protocol and required schema versions.
3. Enable vector queries only for exactly compatible `EmbeddingSpace` records.
4. Fall back explicitly to lexical, filters, exact lookup, or enumeration.
5. Record a content-addressed `DiscoveryQuery` and all requested filters/modes.
6. Follow continuation while the requested coverage requires it.
7. Emit a `DiscoveryReceipt` that states completeness or the exact coverage gap.
8. Freeze returned contracts as a `RegistrySnapshot` whose digest set exactly
   matches the receipt.
9. Run every snapshot candidate against every semantic slot.

Do not call a page-size limit candidate completeness, merge contracts merely
because IDs match, infer ABI compatibility from text/vector rank, or mutate an
old snapshot when a registry changes.
