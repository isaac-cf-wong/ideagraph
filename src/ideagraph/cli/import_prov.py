# ruff: noqa: PLC0415
"""The ``ideagraph import`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def import_command(
    source: Annotated[Path, typer.Argument(help="Path to a PROV-JSON file to import.")],
    destination: Annotated[Path, typer.Argument(help="Path of the ideagraph graph JSON file to write.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the destination if it already exists."),
    ] = False,
) -> None:
    """Import a PROV-JSON document into a ideagraph graph file.

    The import is best-effort: PROV-JSON is a narrower model than ideagraph's, so
    fields it does not carry fall back to their defaults.

    Args:
        source: Path to a PROV-JSON file.
        destination: Path of the ideagraph graph JSON file to create.
        force: If set, overwrite an existing destination instead of refusing.
    """
    from logging import getLogger

    from ideagraph.kg.persistence import save_graph
    from ideagraph.kg.prov import loads_prov

    logger = getLogger("ideagraph")

    if not source.exists():
        typer.echo(f"No such file: {source}", err=True)
        raise typer.Exit(code=1)
    if destination.exists() and not force:
        typer.echo(f"Refusing to overwrite existing file: {destination} (use --force)", err=True)
        raise typer.Exit(code=1)

    graph = loads_prov(source.read_text(encoding="utf-8"))
    save_graph(graph, destination)

    logger.info("Imported %d node(s), %d edge(s) into %s", len(graph.nodes), len(graph.edges), destination)
    typer.echo(str(destination))
