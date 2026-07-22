"""Tests for the single-graph provenance visualization view."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.server.graphs.bridge import graph_to_orm

User = get_user_model()


def _stored_graph(owner) -> None:
    """Store a small graph (claim supported by evidence) owned by ``owner``.

    Args:
        owner: The owning user.
    """
    g = KnowledgeGraph(article_id="art1", metadata={"title": "Demo"})
    g.add_node(Node(type="claim", id="c1", text="A claim."))
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "d.csv"}))
    g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="r1"))
    graph_to_orm(g, slug="demo", owner=owner)


@pytest.fixture
def owner(db):
    """Create and return an owner user with a stored graph.

    Args:
        db: pytest-django database fixture.

    Returns:
        The owner user.

    """
    user = User.objects.create_user("owner", password="x")
    _stored_graph(user)
    return user


def test_graph_data_payload(owner):
    """The data endpoint returns nodes/edges/summary/counts for the owner."""
    client = Client()
    client.force_login(owner)
    data = client.get(reverse("web:graph-data", args=["demo"])).json()
    assert data["counts"] == {"statements": 1, "evidence": 1, "activities": 0}
    ids = {n["id"] for n in data["nodes"]}
    assert ids == {"c1", "e1"}
    statement = next(n for n in data["nodes"] if n["id"] == "c1")
    assert statement["type"] == "statement"
    assert statement["stype"] == "claim"
    assert statement["support"] == "own"
    assert len(data["edges"]) == 1
    assert data["edges"][0]["predicate"] == "supported_by"


def test_graph_detail_renders(owner):
    """The detail page renders and references the data endpoint and assets."""
    client = Client()
    client.force_login(owner)
    body = client.get(reverse("web:graph-detail", args=["demo"])).content.decode()
    assert reverse("web:graph-data", args=["demo"]) in body
    assert "vis-network.min.js" in body
    assert "web/js/graph.js" in body


def test_graph_requires_login():
    """Anonymous access to the data endpoint redirects to login."""
    response = Client().get(reverse("web:graph-data", args=["demo"]))
    assert response.status_code == 302
    assert reverse("login") in response.headers["Location"]


def test_graph_forbidden_for_outsider(owner):
    """A logged-in non-collaborator gets 403 on someone else's graph."""
    outsider = User.objects.create_user("outsider", password="x")
    client = Client()
    client.force_login(outsider)
    assert client.get(reverse("web:graph-data", args=["demo"])).status_code == 403
    assert client.get(reverse("web:graph-detail", args=["demo"])).status_code == 403


def test_graph_unknown_slug_404(owner):
    """An unknown slug returns 404."""
    client = Client()
    client.force_login(owner)
    assert client.get(reverse("web:graph-detail", args=["nope"])).status_code == 404
