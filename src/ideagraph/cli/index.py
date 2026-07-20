# ruff: noqa: PLC0415
"""The ``ideagraph index`` command (build/refresh the library index)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def index_command(
    root: Annotated[Path, typer.Argument(help="Directory tree of article graph JSON files to index.")],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Index database path (default: <root>/.ideagraph/index.db)."),
    ] = None,
    rebuild: Annotated[
        bool, typer.Option("--rebuild", help="Re-index every article, ignoring content hashes.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit the index result as JSON.")] = False,
) -> None:
    """Build or refresh the SQLite library index over a directory of graphs.

    Only articles whose content changed are re-indexed (unless ``--rebuild``).
    Graphs without an ``article_id`` are skipped and reported. After indexing,
    cross-article references whose target no longer resolves are listed.

    Args:
        root: Directory tree of article graph JSON files.
        db: Index database path, or None for the default under ``root``.
        rebuild: Re-index every article regardless of content hash.
        as_json: Emit the result as JSON.
    """
    import json as _json
    from logging import getLogger

    from ideagraph.library import Library

    logger = getLogger("ideagraph")

    if not root.exists():
        typer.echo(f"No such directory: {root}", err=True)
        raise typer.Exit(code=1)

    with Library(root, db) as lib:
        result = lib.index(rebuild=rebuild)
        dangling = lib.dangling_cross_references()

    if as_json:
        typer.echo(
            _json.dumps(
                {
                    "indexed": result.indexed,
                    "unchanged": result.unchanged,
                    "skipped_no_article": result.skipped_no_article,
                    "removed": result.removed,
                    "dangling_cross_references": [{"src": e.src_gid, "target": e.dst_gid} for e in dangling],
                },
                indent=2,
            )
        )
    else:
        typer.echo(
            f"indexed {len(result.indexed)}, unchanged {len(result.unchanged)}, "
            f"skipped {len(result.skipped_no_article)}, removed {len(result.removed)}"
        )
        for path in result.skipped_no_article:
            typer.echo(f"  skipped (no article_id): {path}")
        for e in dangling:
            typer.echo(f"  dangling xref: {e.src_gid} -{e.predicate}-> {e.dst_gid}")

    logger.info("index: %d indexed, %d dangling xref(s)", len(result.indexed), len(dangling))
    if dangling:
        raise typer.Exit(code=1)
