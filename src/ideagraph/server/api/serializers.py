"""Serializers for the graph API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rest_framework import serializers

from ideagraph.server.graphs.models import Graph

if TYPE_CHECKING:
    from collections.abc import Mapping


class GraphSerializer(serializers.ModelSerializer):
    """Read representation of a stored graph's metadata and counts."""

    owner = serializers.SerializerMethodField()
    counts = serializers.SerializerMethodField()

    class Meta:
        model = Graph
        fields = ["slug", "title", "article_id", "owner", "counts", "created_at", "updated_at"]
        read_only_fields = fields

    def get_owner(self, obj: Graph) -> str | None:
        """Return the owner's username, or None if unowned.

        Args:
            obj: The graph.

        Returns:
            The owner username or None.

        """
        return obj.owner.get_username() if obj.owner_id else None

    def get_counts(self, obj: Graph) -> dict[str, int]:
        """Return node/edge counts for the graph.

        Args:
            obj: The graph.

        Returns:
            A mapping with ``nodes`` and ``edges`` counts.

        """
        return {"nodes": obj.nodes.count(), "edges": obj.edges.count()}


class GraphWriteSerializer(serializers.Serializer):
    """Write payload for creating or replacing a graph from a full graph dict."""

    slug = serializers.SlugField(max_length=200)
    content = serializers.JSONField()

    def validate_content(self, value: Any) -> Mapping[str, Any]:
        """Ensure the content is a JSON object (a serialised KnowledgeGraph).

        Args:
            value: The submitted content.

        Returns:
            The validated content.

        Raises:
            ValidationError: If content is not a JSON object.

        """
        if not isinstance(value, dict):
            raise serializers.ValidationError("content must be a JSON object (a serialised graph).")
        return value
