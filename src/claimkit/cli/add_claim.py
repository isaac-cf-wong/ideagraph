# ruff: noqa: PLC0415
"""The ``claimkit add-claim`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def add_claim_command(
    path: Annotated[Path, typer.Argument(help="Path to a provenance graph JSON file.")],
    statement: Annotated[str, typer.Argument(help="The claim statement.")],
    claim_id: Annotated[
        str | None,
        typer.Option("--id", help="Explicit claim id. A UUID is generated if omitted."),
    ] = None,
    tags: Annotated[
        list[str] | None,
        typer.Option("--tag", help="A tag for the claim. Repeatable."),
    ] = None,
) -> None:
    """Add a claim to a provenance graph and print its id.

    Args:
        path: Path to a graph JSON file produced by claimkit.
        statement: The human-readable claim statement.
        claim_id: An explicit id for the claim, or None to generate one.
        tags: Tags to attach to the claim.
    """
    from logging import getLogger

    from claimkit.core import Claim
    from claimkit.persistence import load_graph, save_graph

    logger = getLogger("claimkit")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)

    if claim_id is not None and claim_id in graph.claims:
        typer.echo(f"A claim with id {claim_id} already exists", err=True)
        raise typer.Exit(code=1)

    claim_tags = list(tags) if tags else []
    claim = (
        Claim(statement=statement, tags=claim_tags)
        if claim_id is None
        else Claim(statement=statement, id=claim_id, tags=claim_tags)
    )
    graph.add_claim(claim)
    save_graph(graph, path)

    logger.info("Added claim %s to %s", claim.id, path)
    typer.echo(claim.id)
