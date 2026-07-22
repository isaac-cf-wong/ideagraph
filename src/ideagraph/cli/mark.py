# ruff: noqa: PLC0415
"""The ``ideagraph mark`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ideagraph.core import ClaimStatus


def mark_command(
    path: Annotated[Path, typer.Argument(help="Path to a knowledge graph JSON file.")],
    claim_id: Annotated[str, typer.Argument(help="Id of the claim to mark.")],
    status: Annotated[ClaimStatus, typer.Argument(help="The status to set on the claim.")],
    note: Annotated[
        str | None,
        typer.Option("--note", help="Reviewer note recorded in the claim's metadata."),
    ] = None,
) -> None:
    """Manually set a claim's status, recording a human review decision.

    This is the human-assisted counterpart to automated ``validate``: it lets a
    reviewer resolve a ``needs_review`` claim, or override any status, and saves
    the change. A ``--note`` is stored under the claim's ``metadata`` so the
    rationale travels with the claim.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        claim_id: Id of the claim to mark.
        status: The status to set.
        note: An optional reviewer note stored in the claim's metadata.
    """
    from logging import getLogger

    from ideagraph.kg.persistence import load_graph, save_graph
    from ideagraph.kg.profiles import STATEMENT_TYPES

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)
    node = graph.nodes.get(claim_id)
    if node is None or node.type not in set(STATEMENT_TYPES):
        typer.echo(f"No such statement: {claim_id}", err=True)
        raise typer.Exit(code=1)

    node.properties["status"] = status.value
    if note is not None:
        metadata = node.properties.setdefault("metadata", {})
        metadata["review_note"] = note
    node.touch()
    save_graph(graph, path)

    logger.info("Marked claim %s as %s in %s", claim_id, status.value, path)
    typer.echo(f"{claim_id}: {status.value}")
