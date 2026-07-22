# ruff: noqa: PLC0415
"""The ``ideagraph add-statement`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ideagraph.core import StatementStatus, StatementType


def add_statement_command(
    path: Annotated[Path, typer.Argument(help="Path to a knowledge graph JSON file.")],
    statement: Annotated[str, typer.Argument(help="The statement text (a block of one or more sentences).")],
    type_: Annotated[
        StatementType,
        typer.Option("--type", help="The statement's rhetorical type."),
    ] = StatementType.CLAIM,
    statement_id: Annotated[
        str | None,
        typer.Option("--id", help="Explicit statement id. A UUID is generated if omitted."),
    ] = None,
    status: Annotated[
        StatementStatus,
        typer.Option("--status", help="Initial status."),
    ] = StatementStatus.UNRESOLVED,
    order: Annotated[int, typer.Option("--order", help="Reading-order index within the article.")] = 0,
    section: Annotated[str | None, typer.Option("--section", help="Section label.")] = None,
    source_digest: Annotated[
        str | None,
        typer.Option("--source-digest", help="sha256 of the draft span this text came from (drift detection)."),
    ] = None,
    tags: Annotated[list[str] | None, typer.Option("--tag", help="A tag. Repeatable.")] = None,
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
    """Add a statement to a graph and print its id.

    A statement is a typed block of the article (claim, background, method, …).
    ``add-claim`` is a shorthand for ``add-statement --type claim``.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        statement: The statement text.
        type_: The statement's :class:`StatementType`.
        statement_id: An explicit id, or None to generate one.
        status: The initial status.
        order: Reading-order index within the article.
        section: Optional section label.
        source_digest: Optional sha256 of the source span, for drift detection.
        tags: Repeatable tags.
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

    if statement_id is not None and statement_id in graph.nodes:
        typer.echo(f"A statement with id {statement_id} already exists", err=True)
        raise typer.Exit(code=1)

    node = Node(
        type=type_.value,
        text=statement,
        tags=list(tags) if tags else [],
        properties={
            "status": status.value,
            "order": order,
            "section": section,
            "source_digest": source_digest,
            "metadata": merged_metadata(meta, meta_json),
        },
    )
    if statement_id is not None:
        node.id = statement_id
    created = parse_datetime(created_at, "--created-at")
    if created is not None:
        node.created_at = created
    graph.add_node(node)
    save_graph(graph, path)

    logger.info("Added %s statement %s to %s", type_.value, node.id, path)
    typer.echo(node.id)
