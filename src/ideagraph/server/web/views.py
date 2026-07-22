"""Views for the ideagraph web UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from ideagraph.server.graphs.models import Graph
from ideagraph.server.graphs.payload import graph_payload
from ideagraph.server.graphs.permissions import can_view, visible_graphs
from ideagraph.version import __version__

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


def _graph_for_view(request: HttpRequest, slug: str) -> Graph:
    """Fetch a graph by slug, enforcing view permission.

    Args:
        request: The incoming request.
        slug: The graph slug.

    Returns:
        The graph the user is allowed to view.

    Raises:
        Http404: If no graph has that slug.
        PermissionDenied: If the user may not view it.

    """
    graph = get_object_or_404(Graph, slug=slug)
    if not can_view(request.user, graph):
        raise PermissionDenied
    return graph


def index(request: HttpRequest) -> HttpResponse:
    """Render the landing page.

    Args:
        request: The incoming request.

    Returns:
        The rendered landing page.

    """
    return render(request, "web/index.html", {"page": "home", "version": __version__})


def _role_for(user: object, graph: object) -> str:
    """Return a display label for a user's role on a graph.

    Args:
        user: The requesting user.
        graph: The graph being listed.

    Returns:
        One of ``owner``, ``read``, ``write``, or ``admin`` (superuser).

    """
    if graph.owner_id == user.pk:
        return "owner"
    membership = graph.collaborators.filter(user=user).first()
    if membership is not None:
        return membership.role
    return "admin" if user.is_superuser else "—"


@login_required
def graphs_list(request: HttpRequest) -> HttpResponse:
    """List the graphs the signed-in user may view, with their role.

    Args:
        request: The incoming request.

    Returns:
        The rendered graph list.

    """
    graphs = visible_graphs(request.user).select_related("owner").prefetch_related("collaborators")
    rows = [{"graph": g, "role": _role_for(request.user, g)} for g in graphs]
    return render(request, "web/graphs_list.html", {"page": "graphs", "rows": rows})


@login_required
def graph_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """Render the provenance-graph visualization for one stored graph.

    Args:
        request: The incoming request.
        slug: The graph slug.

    Returns:
        The rendered graph page.

    """
    graph = _graph_for_view(request, slug)
    return render(request, "web/graph_detail.html", {"page": "graphs", "graph": graph})


@login_required
def graph_data(request: HttpRequest, slug: str) -> JsonResponse:
    """Return the visualization payload for one stored graph as JSON.

    Args:
        request: The incoming request.
        slug: The graph slug.

    Returns:
        The graph payload (nodes/edges/summary/counts).

    """
    graph = _graph_for_view(request, slug)
    return JsonResponse(graph_payload(graph))
