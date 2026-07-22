# ruff: noqa: PLC0415
"""The ``ideagraph coverage`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def coverage_command(
    path: Annotated[Path, typer.Argument(help="Path to a provenance graph JSON file.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit results as JSON.")] = False,
    strict: Annotated[bool, typer.Option("--strict", help="Exit non-zero if any claim is unsupported.")] = False,
) -> None:
    """Report whether each claim is supported, and by what (own work / literature).

    Classifies every claim by its supporting evidence: ``own`` (first-hand
    data/figures/workflow), ``literature`` (a citation), ``both``, ``other``, or
    ``unsupported`` (no supporting evidence — the gaps). With ``--strict`` the
    command exits non-zero when any claim is unsupported, for use as a gate.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        as_json: Emit the per-claim classification as JSON.
        strict: Exit non-zero if any claim is unsupported.
    """
    import json as _json
    from logging import getLogger

    from ideagraph.kg.persistence import load_graph
    from ideagraph.kg.profiles import coverage as coverage_fn

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    cov = coverage_fn(load_graph(path))
    if as_json:
        typer.echo(_json.dumps({cid: c.to_dict() for cid, c in cov.items()}, indent=2))
    else:
        counts: dict[str, int] = {}
        for cid, c in cov.items():
            counts[c.category] = counts.get(c.category, 0) + 1
            kinds = f" [{', '.join(c.evidence_kinds)}]" if c.evidence_kinds else ""
            typer.echo(f"{cid}: {c.category}{kinds}")
        summary = ", ".join(f"{n} {k}" for k, n in sorted(counts.items()))
        typer.echo(f"\n{len(cov)} claim(s): {summary}")

    unsupported = [cid for cid, c in cov.items() if not c.supported]
    logger.info("coverage: %d/%d claim(s) unsupported", len(unsupported), len(cov))
    if strict and unsupported:
        typer.echo(f"\n{len(unsupported)} unsupported claim(s): {', '.join(unsupported)}", err=True)
        raise typer.Exit(code=1)
