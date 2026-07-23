# ruff: noqa: PLC0415
"""The ``ideagraph doctor`` command (graph integrity report)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def doctor_command(
    path: Annotated[Path, typer.Argument(help="Path to a knowledge graph JSON file.")],
    library: Annotated[
        Path | None,
        typer.Option(
            "--library",
            help="Library root: resolve cross-article targets against every graph under it.",
        ),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit diagnostics as JSON.")] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Exit non-zero on warnings too, not just errors."),
    ] = False,
    profile: Annotated[
        str,
        typer.Option("--profile", help="Profile to validate structure against (e.g. research, article, project)."),
    ] = "research",
) -> None:
    """Check a graph's integrity and report problems.

    Runs the ``research`` profile's structural validation plus research-level
    checks: cross-references from missing statements, malformed global targets,
    self-references into missing local nodes, intra-article edges pointing at
    absent nodes, and outward links from a graph with no ``article_id``. Exits
    non-zero if any error is found (or any warning, with ``--strict``).

    With ``--library`` the whole library is indexed first, so cross-article
    targets are resolved: a reference to another article that is not present, or
    to a node that does not exist there, is reported.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        library: Library root to resolve cross-article targets against.
        as_json: Emit the diagnostics as JSON.
        strict: Treat warnings as failures too.
        profile: Name of the profile to validate node/edge structure against.
    """
    import json as _json
    from logging import getLogger

    from ideagraph.core.identity import is_global_id, parse_global_id
    from ideagraph.kg.persistence import load_graph
    from ideagraph.kg.profile import Diagnostic, get_profile
    from ideagraph.kg.profiles.research_diagnose import diagnose

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)
    known_articles: set[str] | None = None
    library_gids: set[str] | None = None
    if library is not None:
        from ideagraph.library import Library

        with Library(library) as lib:
            lib.index()
            known_articles = lib.article_ids()
            library_gids = lib.statement_gids()

    try:
        active_profile = get_profile(profile)
    except KeyError:
        typer.echo(f"Unknown profile: {profile}", err=True)
        raise typer.Exit(code=1) from None

    diagnostics = active_profile.validate(graph)
    diagnostics += diagnose(graph, known_articles=known_articles)

    # Library-level: cross target article is known but the node itself is absent.
    if library_gids is not None and graph.article_id is not None:
        for edge in graph.edges.values():
            if not is_global_id(edge.target):
                continue
            target_article, _ = parse_global_id(edge.target)
            if target_article in (known_articles or set()) and edge.target not in library_gids:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "xref-dangling-target",
                        f"cross-reference target {edge.target!r} does not exist in the library",
                        edge.id,
                    )
                )

    errors = [d for d in diagnostics if d.level == "error"]
    warnings = [d for d in diagnostics if d.level == "warning"]

    if as_json:
        typer.echo(_json.dumps([d.to_dict() for d in diagnostics], indent=2))
    elif not diagnostics:
        typer.echo("No problems found.")
    else:
        for d in diagnostics:
            ref = f" [{d.ref}]" if d.ref else ""
            typer.echo(f"{d.level.upper()}: {d.code}: {d.message}{ref}")
        typer.echo(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")

    logger.info("doctor: %d error(s), %d warning(s) in %s", len(errors), len(warnings), path)
    if errors or (strict and warnings):
        raise typer.Exit(code=1)
