# ruff: noqa: PLC0415
"""Shared helper for resolving the profile a CLI command should validate against."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from ideagraph.kg.graph import KnowledgeGraph
    from ideagraph.kg.profile import Profile


def resolve_profile(graph: KnowledgeGraph, explicit: str | None) -> Profile:
    """Return the profile to validate ``graph`` against.

    Resolution order: an explicit ``--profile`` value, else the profile recorded
    in ``graph.metadata["profile"]`` (set by ``init --profile``), else
    ``"research"``.

    Args:
        graph: The graph whose recorded profile is the fallback.
        explicit: A profile name from the command line, or None.

    Returns:
        The resolved :class:`~ideagraph.kg.profile.Profile`.

    Raises:
        typer.Exit: If the resolved profile name is not registered.
    """
    from ideagraph.kg.profile import get_profile

    name = explicit or graph.metadata.get("profile") or "research"
    try:
        return get_profile(name)
    except KeyError:
        typer.echo(f"Unknown profile: {name}", err=True)
        raise typer.Exit(code=1) from None
