# ruff: noqa: PLC0415
"""The ``claimkit digest`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def digest_command(
    file: Annotated[Path, typer.Argument(help="Path to the artefact to hash.")],
    algorithm: Annotated[
        str,
        typer.Option("--algorithm", help="Hash algorithm (any hashlib name)."),
    ] = "sha256",
) -> None:
    """Compute and print an artefact's content digest.

    The value can be passed to ``add-evidence --digest`` so staleness detection
    can later tell whether the artefact has changed.

    Args:
        file: Path to the artefact to hash.
        algorithm: The hash algorithm to use.
    """
    from claimkit.core import hash_file

    if not file.exists():
        typer.echo(f"No such file: {file}", err=True)
        raise typer.Exit(code=1)

    typer.echo(hash_file(file, algorithm=algorithm))
