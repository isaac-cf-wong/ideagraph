# ruff: noqa: PLC0415
"""The ``claimkit import`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def import_command(
    source: Annotated[Path, typer.Argument(help="Path to a PROV-JSON file to import.")],
    destination: Annotated[Path, typer.Argument(help="Path of the claimkit graph JSON file to write.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the destination if it already exists."),
    ] = False,
) -> None:
    """Import a PROV-JSON document into a claimkit graph file.

    The import is best-effort: PROV-JSON is a narrower model than claimkit's, so
    fields it does not carry fall back to their defaults.

    Args:
        source: Path to a PROV-JSON file.
        destination: Path of the claimkit graph JSON file to create.
        force: If set, overwrite an existing destination instead of refusing.
    """
    from logging import getLogger

    from claimkit.persistence import save_graph
    from claimkit.prov import loads_prov

    logger = getLogger("claimkit")

    if not source.exists():
        typer.echo(f"No such file: {source}", err=True)
        raise typer.Exit(code=1)
    if destination.exists() and not force:
        typer.echo(f"Refusing to overwrite existing file: {destination} (use --force)", err=True)
        raise typer.Exit(code=1)

    graph = loads_prov(source.read_text(encoding="utf-8"))
    save_graph(graph, destination)

    logger.info(
        "Imported %d claim(s), %d evidence, %d activity(ies) into %s",
        len(graph.claims),
        len(graph.evidence),
        len(graph.activities),
        destination,
    )
    typer.echo(str(destination))
