# ruff: noqa: PLC0415
"""The ``ideagraph add-activity`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ideagraph.core import ActivityKind


def add_activity_command(
    path: Annotated[Path, typer.Argument(help="Path to a knowledge graph JSON file.")],
    label: Annotated[str, typer.Argument(help="A short human-readable name for the activity.")],
    kind: Annotated[ActivityKind, typer.Option("--kind", help="The kind of process.")],
    activity_id: Annotated[
        str | None,
        typer.Option("--id", help="Explicit activity id. A UUID is generated if omitted."),
    ] = None,
    description: Annotated[
        str,
        typer.Option("--description", help="Human-readable note about the activity."),
    ] = "",
    agent: Annotated[
        str | None,
        typer.Option("--agent", help="The agent (person/tool) responsible for the activity."),
    ] = None,
    meta: Annotated[
        list[str] | None,
        typer.Option("--meta", help="A KEY=VALUE metadata entry. Repeatable."),
    ] = None,
    meta_json: Annotated[
        list[str] | None,
        typer.Option("--meta-json", help="A KEY=JSON metadata entry (structured value). Repeatable."),
    ] = None,
    started_at: Annotated[
        str | None,
        typer.Option("--started-at", help="ISO-8601 timestamp when the activity started."),
    ] = None,
    ended_at: Annotated[
        str | None,
        typer.Option("--ended-at", help="ISO-8601 timestamp when the activity ended."),
    ] = None,
    used: Annotated[
        list[str] | None,
        typer.Option("--used", help="Id/reference of an artefact the activity consumed. Repeatable."),
    ] = None,
    generated: Annotated[
        list[str] | None,
        typer.Option("--generated", help="Id/reference of an artefact the activity produced. Repeatable."),
    ] = None,
    created_at: Annotated[
        str | None,
        typer.Option("--created-at", help="ISO-8601 creation timestamp (defaults to now)."),
    ] = None,
) -> None:
    """Add an activity to a knowledge graph and print its id.

    An activity records a process (a computation, measurement, analysis, or
    review) that produced or consumed artefacts. Link it to the evidence it
    generated with ``ideagraph add-relation ... --predicate generated_by``.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        label: A short human-readable name for the activity.
        kind: The kind of process the activity represents.
        activity_id: An explicit id for the activity, or None to generate one.
        description: An optional human-readable note.
        agent: The agent responsible for the activity, if any.
        meta: Repeatable ``KEY=VALUE`` metadata entries.
        meta_json: Repeatable ``KEY=JSON`` metadata entries (structured values).
        started_at: ISO-8601 timestamp when the activity started, if known.
        ended_at: ISO-8601 timestamp when the activity ended, if known.
        used: Ids/references of artefacts the activity consumed.
        generated: Ids/references of artefacts the activity produced.
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

    # Validate the timing options up front; store the raw ISO strings.
    parse_datetime(started_at, "--started-at")
    parse_datetime(ended_at, "--ended-at")

    graph = load_graph(path)

    if activity_id is not None and activity_id in graph.nodes:
        typer.echo(f"An activity with id {activity_id} already exists", err=True)
        raise typer.Exit(code=1)

    activity = Node(
        type="activity",
        text=label,
        properties={
            "kind": kind.value,
            "label": label,
            "description": description,
            "agent": agent,
            "started_at": started_at,
            "ended_at": ended_at,
            "used": list(used) if used else [],
            "generated": list(generated) if generated else [],
            "metadata": merged_metadata(meta, meta_json),
        },
    )
    if activity_id is not None:
        activity.id = activity_id
    created = parse_datetime(created_at, "--created-at")
    if created is not None:
        activity.created_at = created
    graph.add_node(activity)
    save_graph(graph, path)

    logger.info("Added activity %s (%s) to %s", activity.id, kind.value, path)
    typer.echo(activity.id)
