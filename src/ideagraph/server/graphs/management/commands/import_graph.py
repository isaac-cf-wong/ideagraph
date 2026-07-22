"""``manage.py import_graph`` — load a graph JSON file into the database."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from ideagraph.kg.persistence import load_graph
from ideagraph.server.graphs.bridge import graph_to_orm

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    """Import a provenance graph JSON file into the shared store."""

    help = "Import a provenance graph JSON file into the database under a slug."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Register command arguments.

        Args:
            parser: The argument parser.
        """
        parser.add_argument("slug", help="Slug to store the graph under (replaces any existing).")
        parser.add_argument("path", help="Path to a graph JSON file produced by ideagraph.")
        parser.add_argument("--owner", help="Username to record as the graph's owner.")

    def handle(self, *args: object, **options: object) -> None:
        """Run the import.

        Args:
            *args: Unused positional arguments.
            **options: Parsed command options (``slug``, ``path``, ``owner``).
        """
        path = Path(str(options["path"]))
        if not path.exists():
            raise CommandError(f"No such file: {path}")
        owner = None
        if options.get("owner"):
            user_model = get_user_model()
            try:
                owner = user_model.objects.get(username=options["owner"])
            except user_model.DoesNotExist as exc:
                raise CommandError(f"No such user: {options['owner']}") from exc
        graph = graph_to_orm(load_graph(path), slug=str(options["slug"]), owner=owner)
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {graph.nodes.count()} node(s) and {graph.edges.count()} edge(s) into '{graph.slug}'."
            )
        )
