# ruff: noqa: PLC0415
"""The ``ideagraph init`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def init_command(
    path: Annotated[Path, typer.Argument(help="Path of the graph JSON file to create.")],
    article_id: Annotated[
        str | None,
        typer.Option("--article-id", help="Stable article id (nodes are addressed as article_id#node_id)."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Profile recorded in the graph (e.g. research, article, project)."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the file if it already exists."),
    ] = False,
) -> None:
    """Create an empty knowledge graph file.

    Args:
        path: Destination graph JSON file path.
        article_id: Optional stable article id for this graph.
        profile: Optional profile name to record in the graph's metadata, so
            authoring and ``doctor`` validate against it by default.
        force: If set, overwrite an existing file instead of refusing.
    """
    from logging import getLogger

    from ideagraph.core.identity import SEP
    from ideagraph.kg import KnowledgeGraph
    from ideagraph.kg.persistence import save_graph
    from ideagraph.kg.profile import get_profile

    logger = getLogger("ideagraph")

    if path.exists() and not force:
        typer.echo(f"Refusing to overwrite existing file: {path} (use --force)", err=True)
        raise typer.Exit(code=1)

    if article_id is not None and (not article_id or SEP in article_id):
        typer.echo(f"Invalid --article-id {article_id!r}: must be non-empty and not contain {SEP!r}", err=True)
        raise typer.Exit(code=1)

    metadata: dict[str, str] = {}
    if profile is not None:
        try:
            get_profile(profile)
        except KeyError:
            typer.echo(f"Unknown profile: {profile}", err=True)
            raise typer.Exit(code=1) from None
        metadata["profile"] = profile

    save_graph(KnowledgeGraph(article_id=article_id, metadata=metadata), path)
    logger.info("Initialised empty knowledge graph at %s", path)
