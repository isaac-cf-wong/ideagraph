"""DRF viewset exposing stored graphs over the API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ideagraph.kg.graph import KnowledgeGraph
from ideagraph.server.api.permissions import GraphPermission
from ideagraph.server.api.serializers import GraphSerializer, GraphWriteSerializer
from ideagraph.server.graphs.bridge import graph_to_orm, orm_to_graph
from ideagraph.server.graphs.models import Graph
from ideagraph.server.graphs.payload import graph_payload
from ideagraph.server.graphs.permissions import can_edit, visible_graphs

if TYPE_CHECKING:
    from rest_framework.request import Request


class GraphViewSet(viewsets.ModelViewSet):
    """List, read, create, replace, and delete stored graphs.

    The queryset is scoped to the requesting user's visible graphs, so graphs
    the user may not see are invisible (404) rather than forbidden. Object-level
    writes additionally require edit permission.
    """

    serializer_class = GraphSerializer
    permission_classes = [GraphPermission]
    lookup_field = "slug"

    def get_queryset(self):
        """Return the graphs visible to the requesting user.

        Returns:
            The visible-graphs queryset.

        """
        return visible_graphs(self.request.user).select_related("owner")

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Create a graph from a full serialised-graph payload.

        Args:
            request: The incoming request (``{slug, content}``).
            *args: Unused.
            **kwargs: Unused.

        Returns:
            The created graph's metadata (201), or 409 if the slug is taken.

        """
        write = GraphWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        slug = write.validated_data["slug"]
        if Graph.objects.filter(slug=slug).exists():
            return Response({"detail": f"A graph with slug '{slug}' already exists."}, status=status.HTTP_409_CONFLICT)
        pg = KnowledgeGraph.from_dict(write.validated_data["content"])
        graph = graph_to_orm(pg, slug=slug, owner=request.user)
        return Response(GraphSerializer(graph).data, status=status.HTTP_201_CREATED)

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Replace a graph's content from a full serialised-graph payload.

        Args:
            request: The incoming request (``{content}``; slug from the URL).
            *args: Unused.
            **kwargs: Unused.

        Returns:
            The updated graph's metadata.

        """
        graph = self.get_object()  # runs object permission check (edit required)
        content = request.data.get("content")
        if not isinstance(content, dict):
            return Response({"detail": "content must be a JSON object."}, status=status.HTTP_400_BAD_REQUEST)
        pg = KnowledgeGraph.from_dict(content)
        graph_to_orm(pg, slug=graph.slug, owner=graph.owner)
        return Response(GraphSerializer(Graph.objects.get(slug=graph.slug)).data)

    @action(detail=True, methods=["get"])
    def content(self, request: Request, slug: str | None = None) -> Response:
        """Return the full serialised graph (export).

        Args:
            request: The incoming request.
            slug: The graph slug (from the URL).

        Returns:
            The graph as a KnowledgeGraph dict.

        """
        return Response(orm_to_graph(self.get_object()).to_dict())

    @action(detail=True, methods=["get"])
    def payload(self, request: Request, slug: str | None = None) -> Response:
        """Return the visualization payload (nodes/edges/summary/counts).

        Args:
            request: The incoming request.
            slug: The graph slug (from the URL).

        Returns:
            The visualization payload.

        """
        return Response(graph_payload(self.get_object()))

    def perform_destroy(self, instance: Graph) -> None:
        """Delete a graph (edit permission already enforced).

        Args:
            instance: The graph to delete.

        """
        # can_edit is enforced by GraphPermission.has_object_permission; the
        # explicit check documents intent and guards against future reordering.
        if not can_edit(self.request.user, instance):  # pragma: no cover - defensive
            self.permission_denied(self.request)
        instance.delete()
