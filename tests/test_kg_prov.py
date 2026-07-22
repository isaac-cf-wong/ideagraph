"""Tests for PROV-JSON export/import over the generic knowledge graph."""

from __future__ import annotations

import json

from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.prov import CK_NAMESPACE, dumps_prov, from_prov, loads_prov, to_prov


def _graph() -> KnowledgeGraph:
    """Build a graph exercising every export path.

    Returns:
        The graph.

    """
    g = KnowledgeGraph(article_id="a")
    g.add_node(Node(type="claim", id="c1", text="A claim.", properties={"status": "valid"}))
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "d.csv"}))
    g.add_node(Node(type="activity", id="act1", text="run", properties={"label": "run"}))
    g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="s1"))
    g.add_edge(Edge(type="generated_by", source="e1", target="act1", id="g1"))
    g.add_edge(Edge(type="builds_on", source="c1", target="other#c9", id="b1"))
    return g


def test_prefix_declared():
    """The document declares the ck namespace."""
    assert to_prov(KnowledgeGraph())["prefix"] == {"ck": CK_NAMESPACE}


def test_node_buckets():
    """Nodes land in entity / activity by type."""
    doc = to_prov(_graph())
    assert doc["entity"]["ck:c1"]["prov:type"] == "ck:claim"
    assert doc["entity"]["ck:c1"]["ck:text"] == "A claim."
    assert doc["entity"]["ck:c1"]["ck:status"] == "valid"
    assert doc["entity"]["ck:e1"]["ck:reference"] == "d.csv"
    assert "ck:act1" in doc["activity"]


def test_edge_mappings():
    """generated_by maps to a PROV relation; other edges to wasInfluencedBy."""
    doc = to_prov(_graph())
    assert doc["wasGeneratedBy"]["ck:g1"] == {"prov:entity": "ck:e1", "prov:activity": "ck:act1"}
    assert doc["wasInfluencedBy"]["ck:s1"] == {
        "prov:influencee": "ck:c1",
        "prov:influencer": "ck:e1",
        "ck:predicate": "supported_by",
    }
    assert doc["wasInfluencedBy"]["ck:b1"]["ck:predicate"] == "builds_on"


def test_cross_article_target_is_external_stub():
    """A cross-article target becomes an external entity stub, not a node."""
    doc = to_prov(_graph())
    assert doc["entity"]["ck:other#c9"]["prov:type"] == "ck:external"
    restored = from_prov(doc)
    assert "other#c9" not in restored.nodes
    assert restored.edges["b1"].target == "other#c9"


def test_import_reconstructs_nodes_and_edges():
    """from_prov rebuilds node types/text/properties and edge types."""
    restored = from_prov(to_prov(_graph()))
    assert restored.nodes["c1"].type == "claim"
    assert restored.nodes["c1"].text == "A claim."
    assert restored.nodes["c1"].properties["status"] == "valid"
    assert restored.nodes["e1"].properties["reference"] == "d.csv"
    assert restored.edges["g1"].type == "generated_by"
    assert restored.edges["s1"].type == "supported_by"


def test_reexport_is_stable():
    """Export -> import -> export reproduces the document (lossy-stable)."""
    doc = to_prov(_graph())
    assert to_prov(from_prov(doc)) == doc


def test_dumps_loads_string():
    """dumps_prov/loads_prov round-trip via a string (compared by re-export)."""
    g = _graph()
    assert to_prov(loads_prov(dumps_prov(g))) == to_prov(g)
    assert json.loads(dumps_prov(g))["prefix"]["ck"] == CK_NAMESPACE
