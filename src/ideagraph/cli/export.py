# ruff: noqa: PLC0415
"""The ``ideagraph export`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def export_command(
    path: Annotated[Path, typer.Argument(help="Path to a provenance graph JSON file.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write the PROV-JSON here instead of stdout."),
    ] = None,
) -> None:
    """Export a provenance graph to W3C PROV-JSON.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        output: If given, write the PROV-JSON here; otherwise print to stdout.
    """
    from logging import getLogger

    from ideagraph.kg.persistence import load_graph
    from ideagraph.kg.prov import dumps_prov

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    prov_json = dumps_prov(load_graph(path))

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(prov_json + "\n", encoding="utf-8")
        logger.info("Wrote PROV-JSON to %s", output)
    else:
        typer.echo(prov_json)
