# ruff: noqa: PLC0415
"""The ``ideagraph add-edge`` command (profile-agnostic edge authoring)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def add_edge_command(
    path: Annotated[Path, typer.Argument(help="Path to a knowledge graph JSON file.")],
    source_id: Annotated[str, typer.Argument(help="Id of the source node.")],
    target_id: Annotated[str, typer.Argument(help="Id of the target node (local id or article_id#node_id).")],
    type_: Annotated[str, typer.Option("--type", help="Edge type, from the graph's profile vocabulary.")],
    prop: Annotated[
        list[str] | None,
        typer.Option("--prop", help="A KEY=VALUE property. Repeatable."),
    ] = None,
    prop_json: Annotated[
        list[str] | None,
        typer.Option("--prop-json", help="A KEY=JSON property (structured value). Repeatable."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Override the graph's profile for validation."),
    ] = None,
) -> None:
    """Add a typed edge between two nodes and print its id.

    The edge type and its endpoints are validated against the graph's profile
    (recorded by ``init --profile``, or overridden with ``--profile``). A target
    of the form ``article_id#node_id`` is treated as a cross-article reference
    and is not resolved locally.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        source_id: Id of the source node (must exist in the graph).
        target_id: Id of the target node, or a cross-article global id.
        type_: The edge type (must be allowed by the active profile).
        prop: Repeatable ``KEY=VALUE`` properties.
        prop_json: Repeatable ``KEY=JSON`` properties (structured values).
        profile: Override the graph's recorded profile for validation.
    """
    from logging import getLogger

    from ideagraph.cli._options import merged_metadata
    from ideagraph.cli._profile import resolve_profile
    from ideagraph.core.identity import is_global_id
    from ideagraph.kg import Edge
    from ideagraph.kg.persistence import load_graph, save_graph

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)
    active = resolve_profile(graph, profile)

    if not active.allows_edge_type(type_):
        allowed = ", ".join(sorted(active.edge_types))
        typer.echo(f"Unknown edge type {type_!r} for profile {active.name!r}. Allowed: {allowed}", err=True)
        raise typer.Exit(code=1)

    if source_id not in graph.nodes:
        typer.echo(f"No such source node: {source_id}", err=True)
        raise typer.Exit(code=1)
    cross_article = is_global_id(target_id)
    if not cross_article and target_id not in graph.nodes:
        typer.echo(f"No such target node: {target_id}", err=True)
        raise typer.Exit(code=1)

    rule = active.edge_types[type_]
    source_type = graph.nodes[source_id].type
    if rule.source_types and source_type not in rule.source_types:
        typer.echo(f"{type_!r} source may not be {source_type!r}", err=True)
        raise typer.Exit(code=1)
    if not cross_article and rule.target_types:
        target_type = graph.nodes[target_id].type
        if target_type not in rule.target_types:
            typer.echo(f"{type_!r} target may not be {target_type!r}", err=True)
            raise typer.Exit(code=1)

    properties = merged_metadata(prop, prop_json)
    missing = sorted(rule.required_properties - set(properties))
    if missing:
        typer.echo(f"edge type {type_!r} requires properties: {', '.join(missing)}", err=True)
        raise typer.Exit(code=1)

    edge = Edge(type=type_, source=source_id, target=target_id, properties=properties)
    graph.add_edge(edge)
    save_graph(graph, path)

    logger.info("Added edge %s: %s %s %s", edge.id, source_id, type_, target_id)
    typer.echo(edge.id)
