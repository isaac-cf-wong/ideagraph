# ruff: noqa PL0415
"""Main entry point for the ideagraph CLI application."""

from __future__ import annotations

import enum
from typing import Annotated

import typer


class LoggingLevel(str, enum.Enum):
    """Logging levels for the CLI."""

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Create the main Typer app
app = typer.Typer(
    name="ideagraph",
    help="Claim-level provenance framework for scientific research.",
    rich_markup_mode="rich",
)


def setup_logging(level: LoggingLevel = LoggingLevel.INFO) -> None:
    """Set up logging with Rich handler.

    Args:
        level: Logging level.
    """
    import logging

    from rich.console import Console
    from rich.logging import RichHandler

    logger = logging.getLogger("ideagraph")

    logger.setLevel(level.value)

    console = Console(stderr=True)

    # Remove any existing handlers to ensure RichHandler is used
    for h in logger.handlers[:]:  # Use slice copy to avoid modification during iteration
        logger.removeHandler(h)
    # Add the RichHandler

    handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=True,
        show_level=True,  # Keep level (e.g., DEBUG, INFO) for clarity
        markup=True,  # Enable Rich markup in messages for styling
        level=level.value,  # Ensure handler respects the level
        omit_repeated_times=False,
        log_time_format="%H:%M",
    )
    handler.setLevel(level.value)
    logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate output
    logger.propagate = False


@app.callback()
def main(
    verbose: Annotated[
        LoggingLevel,
        typer.Option("--verbose", "-v", help="Set verbosity level."),
    ] = LoggingLevel.INFO,
) -> None:
    """Main entry point for the CLI application.

    Args:
        verbose: Verbosity level for logging.
    """
    setup_logging(verbose)


def register_commands() -> None:
    """Register CLI commands."""
    from ideagraph.cli.add_activity import add_activity_command
    from ideagraph.cli.add_claim import add_claim_command
    from ideagraph.cli.add_evidence import add_evidence_command
    from ideagraph.cli.add_relation import add_relation_command
    from ideagraph.cli.add_statement import add_statement_command
    from ideagraph.cli.add_xref import add_xref_command
    from ideagraph.cli.backlinks import backlinks_command
    from ideagraph.cli.coverage import coverage_command
    from ideagraph.cli.digest import digest_command
    from ideagraph.cli.doctor import doctor_command
    from ideagraph.cli.export import export_command
    from ideagraph.cli.extract import extract_command
    from ideagraph.cli.find import find_command
    from ideagraph.cli.gaps import gaps_command
    from ideagraph.cli.import_prov import import_command
    from ideagraph.cli.index import index_command
    from ideagraph.cli.init import init_command
    from ideagraph.cli.mark import mark_command
    from ideagraph.cli.neighbors import neighbors_command
    from ideagraph.cli.path import path_command
    from ideagraph.cli.remote import remote_app
    from ideagraph.cli.report import report_command
    from ideagraph.cli.set_article import set_article_command
    from ideagraph.cli.stale import stale_command
    from ideagraph.cli.validate import validate_command

    app.command(name="init")(init_command)
    app.command(name="set-article")(set_article_command)
    app.command(name="add-statement")(add_statement_command)
    app.command(name="add-claim")(add_claim_command)
    app.command(name="add-evidence")(add_evidence_command)
    app.command(name="add-activity")(add_activity_command)
    app.command(name="add-relation")(add_relation_command)
    app.command(name="add-xref")(add_xref_command)
    app.command(name="coverage")(coverage_command)
    app.command(name="digest")(digest_command)
    app.command(name="doctor")(doctor_command)
    app.command(name="extract")(extract_command)
    app.command(name="index")(index_command)
    app.command(name="find")(find_command)
    app.command(name="neighbors")(neighbors_command)
    app.command(name="backlinks")(backlinks_command)
    app.command(name="path")(path_command)
    app.command(name="gaps")(gaps_command)
    app.command(name="validate")(validate_command)
    app.command(name="mark")(mark_command)
    app.command(name="stale")(stale_command)
    app.command(name="report")(report_command)
    app.command(name="export")(export_command)
    app.command(name="import")(import_command)
    app.add_typer(remote_app, name="remote")


register_commands()
