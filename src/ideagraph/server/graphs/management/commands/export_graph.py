"""``manage.py export_graph`` — write a stored graph back to JSON."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand, CommandError

from ideagraph.kg.persistence import dumps_graph, save_graph
from ideagraph.server.graphs.bridge import orm_to_graph
from ideagraph.server.graphs.models import Graph

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    """Export a stored graph to a JSON file or stdout."""

    help = "Export a stored graph (by slug) to a JSON file, or to stdout if no path is given."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Register command arguments.

        Args:
            parser: The argument parser.
        """
        parser.add_argument("slug", help="Slug of the stored graph to export.")
        parser.add_argument("path", nargs="?", help="Destination JSON file (stdout if omitted).")

    def handle(self, *args: object, **options: object) -> None:
        """Run the export.

        Args:
            *args: Unused positional arguments.
            **options: Parsed command options (``slug``, optional ``path``).
        """
        slug = str(options["slug"])
        try:
            graph = Graph.objects.get(slug=slug)
        except Graph.DoesNotExist as exc:
            raise CommandError(f"No such graph: {slug}") from exc
        pg = orm_to_graph(graph)
        if options.get("path"):
            path = Path(str(options["path"]))
            save_graph(pg, path)
            self.stdout.write(self.style.SUCCESS(f"Exported '{slug}' to {path}."))
        else:
            self.stdout.write(dumps_graph(pg))
