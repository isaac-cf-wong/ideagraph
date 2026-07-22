# ruff: noqa: PLC0415
"""The ``ideagraph add-claim`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ideagraph.core import ClaimStatus


def add_claim_command(
    path: Annotated[Path, typer.Argument(help="Path to a knowledge graph JSON file.")],
    statement: Annotated[str, typer.Argument(help="The claim statement.")],
    claim_id: Annotated[
        str | None,
        typer.Option("--id", help="Explicit claim id. A UUID is generated if omitted."),
    ] = None,
    tags: Annotated[
        list[str] | None,
        typer.Option("--tag", help="A tag for the claim. Repeatable."),
    ] = None,
    status: Annotated[
        ClaimStatus,
        typer.Option("--status", help="Initial claim status."),
    ] = ClaimStatus.UNRESOLVED,
    meta: Annotated[
        list[str] | None,
        typer.Option("--meta", help="A KEY=VALUE metadata entry. Repeatable."),
    ] = None,
    meta_json: Annotated[
        list[str] | None,
        typer.Option("--meta-json", help="A KEY=JSON metadata entry (structured value). Repeatable."),
    ] = None,
    created_at: Annotated[
        str | None,
        typer.Option("--created-at", help="ISO-8601 creation timestamp (defaults to now)."),
    ] = None,
) -> None:
    """Add a claim to a knowledge graph and print its id.

    A claim is a statement whose type is fixed to ``claim``; it is a convenience
    shorthand for ``add-statement --type claim``.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        statement: The human-readable claim statement.
        claim_id: An explicit id for the claim, or None to generate one.
        tags: Tags to attach to the claim.
        status: The initial status to set on the claim.
        meta: Repeatable ``KEY=VALUE`` metadata entries.
        meta_json: Repeatable ``KEY=JSON`` metadata entries (structured values).
        created_at: An explicit ISO-8601 creation timestamp, or None for now.
    """
    from logging import getLogger

    from ideagraph.cli._options import merged_metadata, parse_datetime
    from ideagraph.kg import Node
    from ideagraph.kg.persistence import load_graph, save_graph

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)

    if claim_id is not None and claim_id in graph.nodes:
        typer.echo(f"A statement with id {claim_id} already exists", err=True)
        raise typer.Exit(code=1)

    node = Node(
        type="claim",
        text=statement,
        tags=list(tags) if tags else [],
        properties={
            "status": status.value,
            "order": 0,
            "section": None,
            "source_digest": None,
            "metadata": merged_metadata(meta, meta_json),
        },
    )
    if claim_id is not None:
        node.id = claim_id
    created = parse_datetime(created_at, "--created-at")
    if created is not None:
        node.created_at = created
    graph.add_node(node)
    save_graph(graph, path)

    logger.info("Added claim %s to %s", node.id, path)
    typer.echo(node.id)
