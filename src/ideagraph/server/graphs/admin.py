"""Django admin registration for the graphs app."""

from __future__ import annotations

from django.contrib import admin

from ideagraph.server.graphs.models import Edge, Graph, GraphCollaborator, Node


class GraphCollaboratorInline(admin.TabularInline):
    """Inline editor for a graph's collaborators."""

    model = GraphCollaborator
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Graph)
class GraphAdmin(admin.ModelAdmin):
    """Admin for stored graphs."""

    list_display = ("slug", "title", "article_id", "owner", "updated_at")
    list_filter = ("owner",)
    search_fields = ("slug", "title", "article_id")
    autocomplete_fields = ("owner",)
    inlines = (GraphCollaboratorInline,)


@admin.register(GraphCollaborator)
class GraphCollaboratorAdmin(admin.ModelAdmin):
    """Admin for graph collaborator grants."""

    list_display = ("graph", "user", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("graph__slug", "user__username")


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    """Admin for graph nodes."""

    list_display = ("graph", "type", "node_id", "status")
    list_filter = ("type", "status")
    search_fields = ("node_id", "text")


@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    """Admin for graph edges."""

    list_display = ("graph", "type", "source", "target")
    list_filter = ("type",)
    search_fields = ("source", "target")
