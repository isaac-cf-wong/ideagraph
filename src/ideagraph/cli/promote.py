# ruff: noqa: PLC0415
"""The ``ideagraph promote`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def promote_command(
    path: Annotated[Path, typer.Argument(help="Path to a project graph JSON file.")],
    article_id: Annotated[
        str | None,
        typer.Option("--article-id", help="article_id for the promoted article graph."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write the promoted graph here instead of stdout."),
    ] = None,
    check: Annotated[
        bool,
        typer.Option("--check", help="Only report whether the project is concluded; do not promote."),
    ] = False,
) -> None:
    """Promote a concluded project's own knowledge into a new article graph.

    A project is concluded when a result/finding answers its question (backed by
    evidence) and every addressing hypothesis is resolved. Nodes imported from
    the cache are left behind; edges into them are rewired as cross-article
    references back to their origin.

    Args:
        path: Path to a project graph JSON file.
        article_id: article_id for the promoted graph (required unless ``--check``).
        output: If given, write the promoted graph here; otherwise print to stdout.
        check: Only report conclusion status and exit; do not promote.
    """
    from logging import getLogger

    from ideagraph.kg.persistence import dumps_graph, load_graph, save_graph
    from ideagraph.kg.profiles import conclusion_status, promote

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)
    status = conclusion_status(graph)

    if check:
        if status.concluded:
            typer.echo("Concluded.")
        else:
            typer.echo("Not concluded:")
            for reason in status.reasons:
                typer.echo(f"  - {reason}")
        raise typer.Exit(code=0 if status.concluded else 1)

    if not status.concluded:
        typer.echo("Project is not concluded:", err=True)
        for reason in status.reasons:
            typer.echo(f"  - {reason}", err=True)
        raise typer.Exit(code=1)

    if article_id is None:
        typer.echo("--article-id is required to promote.", err=True)
        raise typer.Exit(code=1)

    promoted = promote(graph, article_id=article_id)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        save_graph(promoted, output)
        logger.info("Promoted %d node(s), %d edge(s) to %s", len(promoted.nodes), len(promoted.edges), output)
    else:
        typer.echo(dumps_graph(promoted))
