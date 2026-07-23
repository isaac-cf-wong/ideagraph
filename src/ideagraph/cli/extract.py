# ruff: noqa: PLC0415
"""The ``ideagraph extract`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def extract_command(
    path: Annotated[Path, typer.Argument(help="Path to a graph JSON file to extract from.")],
    seeds: Annotated[list[str], typer.Argument(help="Seed node ids to extract the subgraph around.")],
    hops: Annotated[int, typer.Option("--hops", help="Edge hops to expand from the seeds.")] = 1,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write the extracted graph here instead of stdout."),
    ] = None,
    article_id: Annotated[
        str | None,
        typer.Option("--article-id", help="article_id for the extracted graph."),
    ] = None,
) -> None:
    """Extract the induced subgraph around SEEDS into a new graph.

    Copies every node within ``--hops`` edges of a seed, the edges among them,
    and the cross-article edges leaving them, stamping each node's origin so the
    result stays traceable to the source graph.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        seeds: Seed node ids to extract around.
        hops: Number of edge hops to expand from the seeds.
        output: If given, write the extracted graph here; otherwise print to stdout.
        article_id: If given, set as the extracted graph's ``article_id``.
    """
    from logging import getLogger

    from ideagraph.kg.extract import extract_subgraph
    from ideagraph.kg.persistence import dumps_graph, load_graph, save_graph

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)
    missing = [s for s in seeds if s not in graph.nodes]
    if missing:
        typer.echo(f"Seed id(s) not in graph: {', '.join(missing)}", err=True)
        raise typer.Exit(code=1)

    sub = extract_subgraph(graph, set(seeds), hops=hops, article_id=article_id)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        save_graph(sub, output)
        logger.info("Extracted %d node(s), %d edge(s) to %s", len(sub.nodes), len(sub.edges), output)
    else:
        typer.echo(dumps_graph(sub))
