# ruff: noqa: PLC0415
"""The ``claimkit mark`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from claimkit.core import ClaimStatus


def mark_command(
    path: Annotated[Path, typer.Argument(help="Path to a provenance graph JSON file.")],
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
        path: Path to a graph JSON file produced by claimkit.
        claim_id: Id of the claim to mark.
        status: The status to set.
        note: An optional reviewer note stored in the claim's metadata.
    """
    from logging import getLogger

    from claimkit.persistence import load_graph, save_graph

    logger = getLogger("claimkit")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)
    if claim_id not in graph.claims:
        typer.echo(f"No such claim: {claim_id}", err=True)
        raise typer.Exit(code=1)

    claim = graph.claims[claim_id]
    claim.mark(status)
    if note is not None:
        claim.metadata["review_note"] = note
    save_graph(graph, path)

    logger.info("Marked claim %s as %s in %s", claim_id, status.value, path)
    typer.echo(f"{claim_id}: {status.value}")
