"""Tests for the DRF graph API."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.server.graphs.bridge import graph_to_orm
from ideagraph.server.graphs.models import Graph, GraphCollaborator

User = get_user_model()


def _sample() -> KnowledgeGraph:
    """Build a small graph (claim supported by evidence)."""
    g = KnowledgeGraph(article_id="a", metadata={"title": "Demo"})
    g.add_node(Node(type="claim", id="c1", text="A claim."))
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "d.csv"}))
    g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="r1"))
    return g


@pytest.fixture
def owner(db):
    """Create an owner user.

    Args:
        db: pytest-django database fixture.

    Returns:
        The owner user.

    """
    return User.objects.create_user("owner", password="x")


def test_requires_authentication():
    """Unauthenticated API access is rejected."""
    assert APIClient().get("/api/graphs/").status_code in (401, 403)


def test_list_shows_only_visible(owner):
    """The list is scoped to the user's visible graphs."""
    graph_to_orm(_sample(), slug="mine", owner=owner)
    other = User.objects.create_user("other", password="x")
    graph_to_orm(_sample(), slug="theirs", owner=other)
    client = APIClient()
    client.force_authenticate(owner)
    slugs = {g["slug"] for g in client.get("/api/graphs/").json()}
    assert slugs == {"mine"}


def test_create_graph_from_content(owner):
    """POSTing {slug, content} creates a graph owned by the requester."""
    client = APIClient()
    client.force_authenticate(owner)
    resp = client.post("/api/graphs/", {"slug": "new", "content": _sample().to_dict()}, format="json")
    assert resp.status_code == 201
    graph = Graph.objects.get(slug="new")
    assert graph.owner_id == owner.pk
    assert graph.nodes.count() == 2


def test_create_conflict(owner):
    """Creating a duplicate slug returns 409."""
    graph_to_orm(_sample(), slug="dup", owner=owner)
    client = APIClient()
    client.force_authenticate(owner)
    resp = client.post("/api/graphs/", {"slug": "dup", "content": _sample().to_dict()}, format="json")
    assert resp.status_code == 409


def test_content_export_roundtrips(owner):
    """The content action returns a graph that round-trips to the original."""
    graph_to_orm(_sample(), slug="mine", owner=owner)
    client = APIClient()
    client.force_authenticate(owner)
    data = client.get("/api/graphs/mine/content/").json()
    restored = KnowledgeGraph.from_dict(data)
    assert set(restored.nodes) == {"c1", "e1"}
    assert set(restored.edges) == {"r1"}


def test_payload_action(owner):
    """The payload action returns the visualization payload."""
    graph_to_orm(_sample(), slug="mine", owner=owner)
    client = APIClient()
    client.force_authenticate(owner)
    data = client.get("/api/graphs/mine/payload/").json()
    assert data["counts"] == {"statements": 1, "evidence": 1, "activities": 0}


def test_read_collaborator_cannot_write(owner):
    """A read collaborator may GET but not PUT or DELETE."""
    graph_to_orm(_sample(), slug="mine", owner=owner)
    reader = User.objects.create_user("reader", password="x")
    GraphCollaborator.objects.create(
        graph=Graph.objects.get(slug="mine"), user=reader, role=GraphCollaborator.Role.READ
    )
    client = APIClient()
    client.force_authenticate(reader)
    get_resp = client.get("/api/graphs/mine/")
    put_resp = client.put("/api/graphs/mine/", {"content": _sample().to_dict()}, format="json")
    delete_resp = client.delete("/api/graphs/mine/")
    assert get_resp.status_code == 200
    assert put_resp.status_code == 403
    assert delete_resp.status_code == 403


def test_write_collaborator_can_replace(owner):
    """A write collaborator may replace a graph's content."""
    graph_to_orm(_sample(), slug="mine", owner=owner)
    writer = User.objects.create_user("writer", password="x")
    GraphCollaborator.objects.create(
        graph=Graph.objects.get(slug="mine"), user=writer, role=GraphCollaborator.Role.WRITE
    )
    smaller = KnowledgeGraph(article_id="a")
    smaller.add_node(Node(type="claim", id="c1", text="Only one."))
    client = APIClient()
    client.force_authenticate(writer)
    resp = client.put("/api/graphs/mine/", {"content": smaller.to_dict()}, format="json")
    assert resp.status_code == 200
    assert Graph.objects.get(slug="mine").nodes.count() == 1


def test_token_auth(owner):
    """A token obtained from the auth endpoint authorises API calls."""
    token = Token.objects.create(user=owner)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    assert client.get("/api/graphs/").status_code == 200


def test_obtain_token_endpoint(owner):
    """The token endpoint issues a token for valid credentials."""
    resp = APIClient().post("/api/auth/token/", {"username": "owner", "password": "x"}, format="json")
    assert resp.status_code == 200
    assert "token" in resp.json()
