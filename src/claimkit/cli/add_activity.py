# ruff: noqa: PLC0415
"""The ``claimkit add-activity`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from claimkit.core import ActivityKind


def _parse_meta(items: list[str] | None) -> dict[str, str]:
    """Parse repeatable ``KEY=VALUE`` options into a dict.

    Args:
        items: The raw ``KEY=VALUE`` strings, or None.

    Returns:
        A mapping of key to value.

    Raises:
        typer.BadParameter: If an item is not ``KEY=VALUE``.
    """
    meta: dict[str, str] = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise typer.BadParameter(f"expected KEY=VALUE, got {item!r}")
        meta[key] = value
    return meta


def add_activity_command(
    path: Annotated[Path, typer.Argument(help="Path to a provenance graph JSON file.")],
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
) -> None:
    """Add an activity to a provenance graph and print its id.

    An activity records a process (a computation, measurement, analysis, or
    review) that produced or consumed artefacts. Link it to the evidence it
    generated with ``claimkit add-relation ... --predicate generated-by``.

    Args:
        path: Path to a graph JSON file produced by claimkit.
        label: A short human-readable name for the activity.
        kind: The kind of process the activity represents.
        activity_id: An explicit id for the activity, or None to generate one.
        description: An optional human-readable note.
        agent: The agent responsible for the activity, if any.
        meta: Repeatable ``KEY=VALUE`` metadata entries.
    """
    from logging import getLogger

    from claimkit.core import Activity
    from claimkit.persistence import load_graph, save_graph

    logger = getLogger("claimkit")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)

    if activity_id is not None and activity_id in graph.activities:
        typer.echo(f"An activity with id {activity_id} already exists", err=True)
        raise typer.Exit(code=1)

    activity = Activity(
        kind=kind,
        label=label,
        description=description,
        agent=agent,
        metadata=_parse_meta(meta),
    )
    if activity_id is not None:
        activity.id = activity_id
    graph.add_activity(activity)
    save_graph(graph, path)

    logger.info("Added activity %s (%s) to %s", activity.id, kind.value, path)
    typer.echo(activity.id)
