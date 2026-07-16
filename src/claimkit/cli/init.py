# ruff: noqa: PLC0415
"""The ``claimkit init`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def init_command(
    path: Annotated[Path, typer.Argument(help="Path of the graph JSON file to create.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the file if it already exists."),
    ] = False,
) -> None:
    """Create an empty provenance graph file.

    Args:
        path: Destination graph JSON file path.
        force: If set, overwrite an existing file instead of refusing.
    """
    from logging import getLogger

    from claimkit.core import ProvenanceGraph
    from claimkit.persistence import save_graph

    logger = getLogger("claimkit")

    if path.exists() and not force:
        typer.echo(f"Refusing to overwrite existing file: {path} (use --force)", err=True)
        raise typer.Exit(code=1)

    save_graph(ProvenanceGraph(), path)
    logger.info("Initialised empty provenance graph at %s", path)
