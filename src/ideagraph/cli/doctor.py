# ruff: noqa: PLC0415
"""The ``ideagraph doctor`` command (graph integrity report)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from ideagraph.kg.graph import KnowledgeGraph
    from ideagraph.kg.profile import Diagnostic


def _library_context(library: Path) -> tuple[set[str], set[str], dict[str, object]]:
    """Index a library root and load its article graphs.

    Args:
        library: Library root directory.

    Returns:
        A tuple of (known article ids, known statement gids, article_id -> graph).
    """
    from ideagraph.kg.persistence import load_graph
    from ideagraph.library import Library

    with Library(library) as lib:
        lib.index()
        known_articles = lib.article_ids()
        library_gids = lib.statement_gids()
    origins: dict[str, object] = {}
    for candidate in library.rglob("*.json"):
        try:
            loaded = load_graph(candidate)
        except (ValueError, KeyError, OSError, UnicodeDecodeError):
            continue
        if loaded.article_id is not None:
            origins[loaded.article_id] = loaded
    return known_articles, library_gids, origins


def _library_diagnostics(
    graph: KnowledgeGraph, known_articles: set[str], library_gids: set[str], origins: dict[str, object]
) -> list[Diagnostic]:
    """Compute library-level diagnostics: dangling xref targets and stale imports.

    Args:
        graph: The graph under inspection.
        known_articles: Article ids present in the library.
        library_gids: Statement global ids present in the library.
        origins: Map of article_id to its current graph.

    Returns:
        The library-level diagnostics.
    """
    from ideagraph.core.identity import is_global_id, parse_global_id
    from ideagraph.kg.extract import find_stale_imports
    from ideagraph.kg.profile import Diagnostic

    out: list[Diagnostic] = []
    if graph.article_id is not None:
        for edge in graph.edges.values():
            if not is_global_id(edge.target):
                continue
            target_article, _ = parse_global_id(edge.target)
            if target_article in known_articles and edge.target not in library_gids:
                out.append(
                    Diagnostic(
                        "error",
                        "xref-dangling-target",
                        f"cross-reference target {edge.target!r} does not exist in the library",
                        edge.id,
                    )
                )
    for stale in find_stale_imports(graph, origins.get):
        out.append(
            Diagnostic(
                "warning",
                "stale-import",
                f"imported node {stale.node_id!r} is {stale.reason} vs its origin {stale.source_gid!r}",
                stale.node_id,
            )
        )
    return out


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
        str | None,
        typer.Option(
            "--profile", help="Profile to validate structure against; defaults to the graph's recorded profile."
        ),
    ] = None,
) -> None:
    """Check a graph's integrity and report problems.

    Runs the chosen profile's structural validation plus research-level checks:
    cross-references from missing statements, malformed global targets,
    self-references into missing local nodes, intra-article edges pointing at
    absent nodes, and outward links from a graph with no ``article_id``. Exits
    non-zero if any error is found (or any warning, with ``--strict``).

    With ``--library`` the whole library is indexed first, so cross-article
    targets are resolved and imported nodes whose cache origin has drifted since
    extraction are reported as ``stale-import`` warnings.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        library: Library root to resolve cross-article targets against.
        as_json: Emit the diagnostics as JSON.
        strict: Treat warnings as failures too.
        profile: Name of the profile to validate node/edge structure against.
    """
    import json as _json
    from logging import getLogger

    from ideagraph.cli._profile import resolve_profile
    from ideagraph.kg.persistence import load_graph
    from ideagraph.kg.profiles.research_diagnose import diagnose

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)
    active_profile = resolve_profile(graph, profile)
    known_articles: set[str] | None = None
    diagnostics = active_profile.validate(graph)

    if library is not None:
        known_articles, library_gids, origins = _library_context(library)
        diagnostics += diagnose(graph, known_articles=known_articles)
        diagnostics += _library_diagnostics(graph, known_articles, library_gids, origins)
    else:
        diagnostics += diagnose(graph, known_articles=known_articles)

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
