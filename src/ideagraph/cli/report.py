# ruff: noqa: PLC0415
"""The ``ideagraph report`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def report_command(
    path: Annotated[Path, typer.Argument(help="Path to a provenance graph JSON file.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write the report to this file instead of stdout."),
    ] = None,
) -> None:
    """Render a human-readable Markdown provenance report for a graph.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        output: If given, write the report here; otherwise print to stdout.
    """
    from logging import getLogger

    from ideagraph.kg.persistence import load_graph
    from ideagraph.kg.reporting import render_report

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    report = render_report(load_graph(path))

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        logger.info("Wrote report to %s", output)
    else:
        typer.echo(report)
