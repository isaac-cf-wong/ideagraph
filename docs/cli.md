---
title: Command line
description: The ideagraph command-line interface.
---

ideagraph ships a `ideagraph` command for building and checking a provenance
graph stored as a JSON file. Run `ideagraph --help` (or
`ideagraph COMMAND --help`) for the authoritative, always-current option list.

## Authoring one graph

- **`init GRAPH.json`** – create an empty graph file. Options: `--article-id`,
  `--profile` (record the profile so later commands validate against it),
  `--force`.
- **`add-node GRAPH.json --type T`** – append a node of any type in the graph's
  profile and print its id. Options: `--text`, `--id`, `--prop KEY=VALUE`,
  `--prop-json KEY=JSON`, `--tag` (all repeatable), `--profile`.
- **`add-edge GRAPH.json SOURCE TARGET --type T`** – add a typed edge (endpoints
  and type validated against the profile; a `article_id#node_id` target is a
  cross-article reference). Options: `--prop`, `--prop-json`, `--profile`.
- **`add-claim`**, **`add-statement`**, **`add-evidence`**, **`add-activity`**,
  **`add-relation`**, **`add-xref`** – research-profile shorthands for the
  above.
- **`validate GRAPH.json`** – resolve each assertion's status from its evidence.
  Options: `--apply`, `--json`.
- **`mark`**, **`stale`**, **`report`**, **`export`**, **`import`** – status
  editing, staleness of on-disk artefacts, Markdown report, and PROV-JSON
  in/out.

## Working with a graph or library

- **`doctor GRAPH.json`** – structural + integrity check. Validates against the
  graph's recorded profile (override with `--profile`). With `--library ROOT`,
  resolves cross-article targets and flags `stale-import` warnings; `--strict`
  fails on warnings too.
- **`extract GRAPH.json SEED...`** – carve the induced subgraph around seed
  nodes into a new graph. Options: `--hops`, `--article-id`, `-o/--output`.
- **`promote GRAPH.json`** – promote a concluded project graph into a new
  article graph. Options: `--article-id`, `-o/--output`, `--check` (report
  conclusion status only).
- **`index ROOT`**, **`find ROOT QUERY [--semantic]`**, **`neighbors`**,
  **`backlinks`**, **`path`**, **`gaps`** – build and query a library (a
  directory of graphs).

## Example: author a paper graph

```bash
ideagraph init paper.json --article-id gw150914 --profile article
ideagraph add-node paper.json --type article --text "Observation of GW" --id article
ideagraph add-node paper.json --type quantity --text "Matched-filter SNR was 24." --id snr
ideagraph add-node paper.json --type claim --text "First direct detection of GW." \
    --id first --prop status=valid
ideagraph add-node paper.json --type summary_point \
    --text "First direct detection of gravitational waves, SNR 24." --id sp1 --prop-json order=0
ideagraph add-edge paper.json article sp1 --type contains
ideagraph add-edge paper.json sp1 first --type summarizes
ideagraph add-edge paper.json sp1 snr --type summarizes
ideagraph doctor paper.json            # profile read from metadata
```
