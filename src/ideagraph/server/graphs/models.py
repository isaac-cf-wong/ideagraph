"""ORM models persisting knowledge graphs.

Each node/edge keeps its serialised dict (``data``) as the source of truth,
alongside a few denormalised, indexed columns for querying and display. The
models are generic: a node's ``type`` and an edge's ``type`` are free strings
from the active profile's vocabulary. Conversion to/from the in-memory
:class:`~ideagraph.kg.graph.KnowledgeGraph` lives in :mod:`.bridge`.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Graph(models.Model):
    """A stored knowledge graph (one article's nodes and edges)."""

    slug = models.SlugField(unique=True, max_length=200)
    article_id = models.CharField(max_length=200, blank=True, default="")
    title = models.CharField(max_length=500, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_graphs",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self) -> str:
        """Return the graph's title or slug."""
        return self.title or self.slug


class GraphCollaborator(models.Model):
    """A user granted read or write access to a graph they do not own."""

    class Role(models.TextChoices):
        READ = "read", "Read"
        WRITE = "write", "Write"

    graph = models.ForeignKey(Graph, on_delete=models.CASCADE, related_name="collaborators")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="graph_memberships",
    )
    role = models.CharField(max_length=8, choices=Role.choices, default=Role.READ)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["graph", "user"]
        constraints = [
            models.UniqueConstraint(fields=["graph", "user"], name="uniq_collaborator_per_graph"),
        ]

    def __str__(self) -> str:
        """Return a short label for the collaborator grant."""
        return f"{self.user} ({self.role}) on {self.graph}"


class Node(models.Model):
    """A typed node within a graph."""

    graph = models.ForeignKey(Graph, on_delete=models.CASCADE, related_name="nodes")
    node_id = models.CharField(max_length=200)
    type = models.CharField(max_length=64)
    # Denormalised for querying/display; the authoritative copy is `data`.
    status = models.CharField(max_length=32, blank=True, default="")
    text = models.TextField(blank=True, default="")
    data = models.JSONField()

    class Meta:
        ordering = ["graph", "type", "node_id"]
        constraints = [
            models.UniqueConstraint(fields=["graph", "node_id"], name="uniq_node_per_graph"),
        ]
        indexes = [
            models.Index(fields=["graph", "type"]),
            models.Index(fields=["graph", "status"]),
        ]

    def __str__(self) -> str:
        """Return a short label for the node."""
        return f"{self.type}:{self.node_id}"


class Edge(models.Model):
    """A typed, directed edge within a graph."""

    graph = models.ForeignKey(Graph, on_delete=models.CASCADE, related_name="edges")
    edge_id = models.CharField(max_length=200)
    type = models.CharField(max_length=64)
    source = models.CharField(max_length=200)
    # A local node id, or a global article_id#node_id address (cross-article).
    target = models.CharField(max_length=400)
    data = models.JSONField()

    class Meta:
        ordering = ["graph", "type", "edge_id"]
        constraints = [
            models.UniqueConstraint(fields=["graph", "edge_id"], name="uniq_edge_per_graph"),
        ]
        indexes = [
            models.Index(fields=["graph", "source"]),
            models.Index(fields=["graph", "target"]),
        ]

    def __str__(self) -> str:
        """Return a short label for the edge."""
        return f"{self.source} -{self.type}-> {self.target}"
