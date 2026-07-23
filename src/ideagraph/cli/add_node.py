# ruff: noqa: PLC0415
"""The ``ideagraph add-node`` command (profile-agnostic node authoring)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def add_node_command(
    path: Annotated[Path, typer.Argument(help="Path to a knowledge graph JSON file.")],
    type_: Annotated[str, typer.Option("--type", help="Node type, from the graph's profile vocabulary.")],
    text: Annotated[str, typer.Option("--text", help="The node's text content.")] = "",
    node_id: Annotated[
        str | None,
        typer.Option("--id", help="Explicit node id. A UUID is generated if omitted."),
    ] = None,
    prop: Annotated[
        list[str] | None,
        typer.Option("--prop", help="A KEY=VALUE property. Repeatable."),
    ] = None,
    prop_json: Annotated[
        list[str] | None,
        typer.Option("--prop-json", help="A KEY=JSON property (structured value). Repeatable."),
    ] = None,
    tags: Annotated[list[str] | None, typer.Option("--tag", help="A tag. Repeatable.")] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Override the graph's profile for validation."),
    ] = None,
) -> None:
    """Add a node of any profile type to a graph and print its id.

    The node type is validated against the graph's profile (recorded by
    ``init --profile``, or overridden with ``--profile``); unknown types and
    missing required properties are rejected.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        type_: The node type (must be allowed by the active profile).
        text: The node's text content.
        node_id: An explicit id, or None to generate one.
        prop: Repeatable ``KEY=VALUE`` properties.
        prop_json: Repeatable ``KEY=JSON`` properties (structured values).
        tags: Repeatable tags.
        profile: Override the graph's recorded profile for validation.
    """
    from logging import getLogger

    from ideagraph.cli._options import merged_metadata
    from ideagraph.cli._profile import resolve_profile
    from ideagraph.kg import Node
    from ideagraph.kg.persistence import load_graph, save_graph

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)
    active = resolve_profile(graph, profile)

    if not active.allows_node_type(type_):
        allowed = ", ".join(sorted(active.node_types))
        typer.echo(f"Unknown node type {type_!r} for profile {active.name!r}. Allowed: {allowed}", err=True)
        raise typer.Exit(code=1)

    if node_id is not None and node_id in graph.nodes:
        typer.echo(f"A node with id {node_id} already exists", err=True)
        raise typer.Exit(code=1)

    properties = merged_metadata(prop, prop_json)
    missing = sorted(active.node_types[type_].required_properties - set(properties))
    if missing:
        typer.echo(f"node type {type_!r} requires properties: {', '.join(missing)}", err=True)
        raise typer.Exit(code=1)

    node = Node(type=type_, text=text, tags=list(tags) if tags else [], properties=properties)
    if node_id is not None:
        node.id = node_id
    graph.add_node(node)
    save_graph(graph, path)

    logger.info("Added %s node %s to %s", type_, node.id, path)
    typer.echo(node.id)
