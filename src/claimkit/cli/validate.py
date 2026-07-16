# ruff: noqa: PLC0415
"""The ``claimkit validate`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def validate_command(
    path: Annotated[Path, typer.Argument(help="Path to a provenance graph JSON file.")],
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Write the resolved status back onto each claim in the file."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit results as JSON instead of human-readable lines."),
    ] = False,
) -> None:
    """Validate every claim in a provenance graph against its evidence.

    Args:
        path: Path to a graph JSON file produced by claimkit.
        apply: If set, persist the resolved statuses back to ``path``.
        as_json: If set, print results as a JSON object keyed by claim id.
    """
    import json
    from logging import getLogger

    from claimkit.core import apply_all, validate_all
    from claimkit.persistence import load_graph, save_graph

    logger = getLogger("claimkit")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)

    if apply:
        results = {result.claim_id: result for result in apply_all(graph)}
        save_graph(graph, path)
        logger.info("Applied validation to %d claim(s) in %s", len(results), path)
    else:
        results = validate_all(graph)

    if as_json:
        typer.echo(json.dumps({cid: r.to_dict() for cid, r in results.items()}, indent=2, ensure_ascii=False))
        return

    if not results:
        typer.echo("No claims in graph.")
        return

    for claim_id, result in results.items():
        typer.echo(f"{claim_id}: {result.status.value} — {result.reason}")
