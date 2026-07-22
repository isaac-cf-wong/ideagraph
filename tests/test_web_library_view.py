"""Tests for the cross-article Library visualization view."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.server.graphs.bridge import graph_to_orm

User = get_user_model()


def _graph_a() -> KnowledgeGraph:
    """Graph A: two statements, one discourse edge, one resolvable + one dangling xref."""
    g = KnowledgeGraph(article_id="a", metadata={"title": "A"})
    g.add_node(Node(type="claim", id="s1", text="S1."))
    g.add_node(Node(type="finding", id="s2", text="S2."))
    g.add_edge(Edge(type="elaborates", source="s1", target="s2", id="r1"))
    g.add_edge(Edge(type="builds_on", source="s1", target="b#t1", id="x1"))
    g.add_edge(Edge(type="builds_on", source="s2", target="z#x", id="x2"))
    return g


def _graph_b() -> KnowledgeGraph:
    """Graph B: a single statement that Graph A references."""
    g = KnowledgeGraph(article_id="b", metadata={"title": "B"})
    g.add_node(Node(type="claim", id="t1", text="T1."))
    return g


@pytest.fixture
def owner(db):
    """Create an owner with graphs A and B stored.

    Args:
        db: pytest-django database fixture.

    Returns:
        The owner user.

    """
    user = User.objects.create_user("owner", password="x")
    graph_to_orm(_graph_a(), slug="a", owner=user)
    graph_to_orm(_graph_b(), slug="b", owner=user)
    return user


def test_library_aggregates_visible_graphs(owner):
    """The payload lists both articles and every statement node."""
    client = Client()
    client.force_login(owner)
    data = client.get(reverse("web:library-data")).json()
    assert {a["id"] for a in data["articles"]} == {"a", "b"}
    assert {n["id"] for n in data["nodes"]} == {"a#s1", "a#s2", "b#t1"}
    assert data["counts"] == {"articles": 2, "statements": 3, "cross_edges": 2}


def test_library_intra_and_cross_edges(owner):
    """Intra discourse edges and cross references are distinguished; dangling flagged."""
    client = Client()
    client.force_login(owner)
    data = client.get(reverse("web:library-data")).json()
    by_target = {e["target"]: e for e in data["edges"]}
    assert by_target["a#s2"]["kind"] == "intra"
    assert by_target["a#s2"]["predicate"] == "elaborates"
    assert by_target["b#t1"]["kind"] == "cross"
    assert by_target["b#t1"]["dangling"] is False
    assert by_target["z#x"]["kind"] == "cross"
    assert by_target["z#x"]["dangling"] is True


def test_library_excludes_other_users_graphs(owner):
    """A user's library shows only their visible graphs."""
    other = User.objects.create_user("other", password="x")
    graph_to_orm(_graph_b(), slug="secret", owner=other)
    client = Client()
    client.force_login(other)
    data = client.get(reverse("web:library-data")).json()
    assert {a["id"] for a in data["articles"]} == {"b"}
    assert {n["id"] for n in data["nodes"]} == {"b#t1"}


def test_library_requires_login():
    """Anonymous access to the library data endpoint redirects to login."""
    response = Client().get(reverse("web:library-data"))
    assert response.status_code == 302
    assert reverse("login") in response.headers["Location"]


def test_library_page_renders(owner):
    """The library page renders and references the data endpoint and assets."""
    client = Client()
    client.force_login(owner)
    body = client.get(reverse("web:library")).content.decode()
    assert reverse("web:library-data") in body
    assert "web/js/library.js" in body
