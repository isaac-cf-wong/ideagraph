"""Shared helpers for parsing CLI options."""

from __future__ import annotations

import typer


def parse_meta(items: list[str] | None) -> dict[str, str]:
    """Parse repeatable ``KEY=VALUE`` options into a dict.

    Args:
        items: The raw ``KEY=VALUE`` strings, or None.

    Returns:
        A mapping of key to value (empty if ``items`` is falsy).

    Raises:
        typer.BadParameter: If an item is not of the form ``KEY=VALUE``.
    """
    meta: dict[str, str] = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise typer.BadParameter(f"expected KEY=VALUE, got {item!r}")
        meta[key] = value
    return meta
