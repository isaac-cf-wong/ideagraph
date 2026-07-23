---
title: Profiles
description:
    The research profile vocabulary and its coverage/validation/staleness
    semantics.
---

Three profiles ship built-in, each extending the previous one:

- **`research`** — the scientific-provenance vocabulary: statement types
  (`claim`, `finding`, `result`, …) plus `evidence` and `activity`.
- **`article`** — adds the shape for representing a paper as a graph: an
  `article` root, a `summary_point` layer (`contains` / `summarizes` edges), and
  `quantity` / `fact` detail nodes.
- **`project`** — adds `question` and `hypothesis` nodes and the `addresses` /
  `answers` / `tests` edges that wire a research project's question → hypothesis
  → test → answer loop.

Validate a graph against a chosen profile with `get_profile(name).validate(g)`
or `ideagraph doctor --profile <name>`.

A project graph closes its loop with two operations: `conclusion_status(g)`
reports whether the question is answered (a result answers it, backed by
evidence, with every addressing hypothesis resolved), and
`promote(g, article_id=...)` carves the project's own new knowledge into a fresh
article graph for the cache — gated on conclusion, with edges into imported
nodes rewired as cross-article citations. The CLI equivalent is
`ideagraph promote` (`--check` reports status without promoting).

<!-- prettier-ignore-start -->

::: ideagraph.kg.profiles
    options:
        show_root_heading: false
        heading_level: 2
        inherited_members: true
        show_if_no_docstring: false
        docstring_style: google
        show_source: true

<!-- prettier-ignore-end -->
