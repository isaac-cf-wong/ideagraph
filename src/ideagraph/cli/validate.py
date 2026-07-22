# ruff: noqa: PLC0415
"""The ``ideagraph validate`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def validate_command(
    path: Annotated[Path, typer.Argument(help="Path to a knowledge graph JSON file.")],
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Write the resolved status back onto each claim in the file."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit results as JSON instead of human-readable lines."),
    ] = False,
) -> None:
    """Validate every assertion in a knowledge graph against its evidence.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        apply: If set, persist the resolved statuses back to ``path``.
        as_json: If set, print results as a JSON object keyed by node id.
    """
    import json
    from logging import getLogger

    from ideagraph.kg.persistence import load_graph, save_graph
    from ideagraph.kg.profiles import apply_all, validate_all

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)

    if apply:
        results = {result.node_id: result for result in apply_all(graph)}
        save_graph(graph, path)
        logger.info("Applied validation to %d claim(s) in %s", len(results), path)
    else:
        results = validate_all(graph)

    if as_json:
        payload = {
            node_id: {
                "node_id": r.node_id,
                "status": r.status,
                "supporting": list(r.supporting),
                "refuting": list(r.refuting),
                "reason": r.reason,
            }
            for node_id, r in results.items()
        }
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if not results:
        typer.echo("No claims in graph.")
        return

    for node_id, result in results.items():
        typer.echo(f"{node_id}: {result.status} — {result.reason}")
