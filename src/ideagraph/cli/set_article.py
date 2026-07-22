# ruff: noqa: PLC0415
"""The ``ideagraph set-article`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def set_article_command(
    path: Annotated[Path, typer.Argument(help="Path to a provenance graph JSON file.")],
    article_id: Annotated[
        str | None,
        typer.Argument(help="The article id to set. Omit to print the current one."),
    ] = None,
) -> None:
    """Get or set a graph's article id.

    With no ``article_id`` the current value is printed. Otherwise the graph's
    article id is set — the stable name other articles use to reference this
    one's statements as ``article_id#node_id``.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        article_id: The article id to set, or None to print the current one.
    """
    from logging import getLogger

    from ideagraph.core.identity import SEP
    from ideagraph.kg.persistence import load_graph, save_graph

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)

    if article_id is None:
        typer.echo(graph.article_id if graph.article_id is not None else "")
        return

    if not article_id or SEP in article_id:
        typer.echo(f"Invalid article id {article_id!r}: must be non-empty and not contain {SEP!r}", err=True)
        raise typer.Exit(code=1)

    graph.article_id = article_id
    save_graph(graph, path)
    logger.info("Set article_id to %s in %s", article_id, path)
    typer.echo(article_id)
