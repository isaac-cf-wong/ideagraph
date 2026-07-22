# ruff: noqa: PLC0415
"""The ``ideagraph add-xref`` command (cross-article edges)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ideagraph.core import ProvenancePredicate


def add_xref_command(
    path: Annotated[Path, typer.Argument(help="Path to a knowledge graph JSON file (the asserting article).")],
    subject_id: Annotated[str, typer.Argument(help="A local statement id this edge starts from.")],
    predicate: Annotated[
        ProvenancePredicate,
        typer.Argument(help="The relationship (e.g. cites, builds_on, extends, contradicts, same_as)."),
    ],
    target: Annotated[str, typer.Argument(help="Global address of the target: 'article_id#node_id'.")],
    xref_id: Annotated[
        str | None,
        typer.Option("--id", help="Explicit edge id. A UUID is generated if omitted."),
    ] = None,
    meta: Annotated[
        list[str] | None,
        typer.Option("--meta", help="A KEY=VALUE metadata entry. Repeatable."),
    ] = None,
    meta_json: Annotated[
        list[str] | None,
        typer.Option("--meta-json", help="A KEY=JSON metadata entry (structured value). Repeatable."),
    ] = None,
) -> None:
    """Record a cross-article edge from a local statement to one in another article.

    The edge is stored in this (the asserting) article's graph as
    ``subject_id -> predicate -> target``, where ``target`` is a global
    ``article_id#node_id`` address into the other article.

    Args:
        path: Path to the asserting article's graph JSON file.
        subject_id: The local statement id the edge starts from.
        predicate: The relationship the edge expresses.
        target: The global address of the target statement.
        xref_id: An explicit edge id, or None to generate one.
        meta: Repeatable ``KEY=VALUE`` metadata entries.
        meta_json: Repeatable ``KEY=JSON`` metadata entries.
    """
    from logging import getLogger

    from ideagraph.cli._options import merged_metadata
    from ideagraph.core.identity import is_global_id
    from ideagraph.kg import Edge
    from ideagraph.kg.persistence import load_graph, save_graph
    from ideagraph.kg.profiles import STATEMENT_TYPES

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)

    subject = graph.nodes.get(subject_id)
    if subject is None or subject.type not in set(STATEMENT_TYPES):
        typer.echo(f"No such statement: {subject_id}", err=True)
        raise typer.Exit(code=1)
    if not is_global_id(target):
        typer.echo(f"Invalid target {target!r}: expected a global 'article_id#node_id' address", err=True)
        raise typer.Exit(code=1)
    if xref_id is not None and xref_id in graph.edges:
        typer.echo(f"A cross-reference with id {xref_id} already exists", err=True)
        raise typer.Exit(code=1)

    edge = Edge(
        type=predicate.value,
        source=subject_id,
        target=target,
        properties={"metadata": merged_metadata(meta, meta_json)},
    )
    if xref_id is not None:
        edge.id = xref_id
    graph.add_edge(edge)
    save_graph(graph, path)

    logger.info("Added cross-reference %s: %s %s %s", edge.id, subject_id, predicate.value, target)
    typer.echo(edge.id)
