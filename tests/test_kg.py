"""Tests for the generic knowledge-graph core (ideagraph.kg)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ideagraph.kg import Edge, KnowledgeGraph, Node, get_profile
from ideagraph.kg.profile import EdgeRule, NodeRule, Profile


def test_node_roundtrip():
    """Node.from_dict inverts Node.to_dict."""
    node = Node(
        type="claim",
        text="A claim.",
        id="n1",
        tags=["x"],
        properties={"status": "valid"},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    assert Node.from_dict(node.to_dict()) == node


def test_node_requires_type():
    """Node.from_dict raises without a type."""
    with pytest.raises(KeyError):
        Node.from_dict({"text": "x"})


def test_edge_roundtrip():
    """Edge.from_dict inverts Edge.to_dict."""
    edge = Edge(type="supported_by", source="n1", target="n2", id="e1", properties={"k": "v"})
    assert Edge.from_dict(edge.to_dict()) == edge


def test_graph_add_and_traverse():
    """Edges are indexed by both endpoints."""
    g = KnowledgeGraph(article_id="a")
    g.add_node(Node(type="claim", id="c1"))
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "r"}))
    edge = g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="x1"))
    assert g.outgoing("c1") == [edge]
    assert g.incoming("e1") == [edge]
    assert g.outgoing("c1", edge_type="refuted_by") == []
    assert g.nodes_of_type("claim") == [g.nodes["c1"]]


def test_graph_roundtrip():
    """KnowledgeGraph.from_dict inverts to_dict and rebuilds the index."""
    g = KnowledgeGraph(article_id="a", metadata={"title": "T"})
    g.add_node(Node(type="claim", id="c1", text="A"))
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "r"}))
    g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="x1"))
    restored = KnowledgeGraph.from_dict(g.to_dict())
    assert restored == g
    assert [e.id for e in restored.outgoing("c1")] == ["x1"]


def test_graph_serialisation_shape():
    """The graph serialises to a flat nodes/edges shape."""
    g = KnowledgeGraph(article_id="a")
    g.add_node(Node(type="claim", id="c1"))
    data = g.to_dict()
    assert set(data) == {"article_id", "metadata", "nodes", "edges"}
    assert data["nodes"][0]["type"] == "claim"


def test_add_edge_replace_reindexes():
    """Re-adding an edge id updates the index rather than duplicating it."""
    g = KnowledgeGraph()
    g.add_node(Node(type="claim", id="c1"))
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "r"}))
    g.add_node(Node(type="evidence", id="e2", properties={"kind": "data", "reference": "r"}))
    g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="x1"))
    g.add_edge(Edge(type="supported_by", source="c1", target="e2", id="x1"))
    assert len(g.outgoing("c1")) == 1
    assert g.incoming("e1") == []
    assert len(g.incoming("e2")) == 1


# -- profile validation ----------------------------------------------------


def _research_graph() -> KnowledgeGraph:
    """A conforming research-profile graph.

    Returns:
        The graph.

    """
    g = KnowledgeGraph(article_id="a")
    g.add_node(Node(type="claim", id="c1", text="A"))
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "r"}))
    g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="x1"))
    return g


def test_research_profile_registered():
    """The research profile is available by name with the expected vocabulary."""
    profile = get_profile("research")
    assert profile.allows_node_type("claim")
    assert profile.allows_node_type("evidence")
    assert profile.allows_edge_type("supported_by")
    assert not profile.allows_node_type("person")


def test_valid_graph_has_no_diagnostics():
    """A conforming graph validates clean."""
    assert get_profile("research").validate(_research_graph()) == []


def test_unknown_node_type_flagged():
    """A node of an unknown type is an error."""
    g = _research_graph()
    g.add_node(Node(type="person", id="p1"))
    codes = {d.code for d in get_profile("research").validate(g)}
    assert "unknown-node-type" in codes


def test_missing_required_property_flagged():
    """Evidence without kind/reference is flagged."""
    g = KnowledgeGraph()
    g.add_node(Node(type="evidence", id="e1"))
    codes = {d.code for d in get_profile("research").validate(g)}
    assert "missing-property" in codes


def test_bad_endpoint_type_flagged():
    """supported_by must point at evidence, not another claim."""
    g = KnowledgeGraph()
    g.add_node(Node(type="claim", id="c1"))
    g.add_node(Node(type="claim", id="c2"))
    g.add_edge(Edge(type="supported_by", source="c1", target="c2", id="x1"))
    codes = {d.code for d in get_profile("research").validate(g)}
    assert "edge-bad-target-type" in codes


def test_dangling_edge_source_flagged():
    """An edge whose source node is absent is flagged."""
    g = KnowledgeGraph()
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "r"}))
    g.add_edge(Edge(type="supported_by", source="missing", target="e1", id="x1"))
    codes = {d.code for d in get_profile("research").validate(g)}
    assert "edge-dangling-source" in codes


def test_cross_article_target_not_resolved_locally():
    """A cross-article edge to a global id is not treated as dangling."""
    g = KnowledgeGraph(article_id="a")
    g.add_node(Node(type="claim", id="c1"))
    g.add_edge(Edge(type="builds_on", source="c1", target="other#c9", id="x1"))
    codes = {d.code for d in get_profile("research").validate(g)}
    assert "edge-dangling-target" not in codes


def test_custom_profile():
    """A custom profile validates its own vocabulary."""
    profile = Profile(
        name="people",
        node_types={"person": NodeRule("person"), "org": NodeRule("org")},
        edge_types={
            "works_at": EdgeRule("works_at", source_types=frozenset({"person"}), target_types=frozenset({"org"}))
        },
    )
    g = KnowledgeGraph()
    g.add_node(Node(type="person", id="p1"))
    g.add_node(Node(type="org", id="o1"))
    g.add_edge(Edge(type="works_at", source="p1", target="o1", id="w1"))
    assert profile.validate(g) == []
