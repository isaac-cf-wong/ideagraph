---
title: API Reference
description: Reference for the ideagraph public API.
icon: material/api
---

This section documents the public API of ideagraph. Everything under
[Core](core.md) is also re-exported from the top-level `ideagraph` package.

## Sections

- **[Core](core.md)** – The generic knowledge graph: `Node`, `Edge`,
  `KnowledgeGraph`, and the `Profile` abstraction.
- **[Profiles](profiles.md)** – The built-in `research` profile vocabulary and
  its coverage / validation / staleness semantics.
- **[Persistence](persistence.md)** – Versioned JSON save/load for a graph.
- **[Extraction](extract.md)** – Carve a self-contained subgraph around seed
  nodes out of a larger graph.
- **[PROV-JSON](prov.md)** – Export to and import from W3C PROV-JSON.
- **[Reporting](reporting.md)** – Human-readable Markdown reports.
- **[Command line](../cli.md)** – The `ideagraph` CLI.
- **[Utility](utils/index.md)** – Logging and version helpers.
