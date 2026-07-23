"""Tests for the built-in ``article`` and ``project`` profiles."""

from __future__ import annotations

from ideagraph.kg import Edge, KnowledgeGraph, Node, get_profile
from ideagraph.kg.profiles import ARTICLE, PROJECT


def _codes(diagnostics):
    """Return the set of diagnostic codes.

    Args:
        diagnostics: Diagnostics from a profile validation.

    Returns:
        The set of their codes.

    """
    return {d.code for d in diagnostics}


def test_profiles_are_registered():
    """The article and project profiles resolve by name."""
    assert get_profile("article") is ARTICLE
    assert get_profile("project") is PROJECT


def test_article_accepts_the_paper_shape():
    """A summary-layered paper graph validates cleanly under ``article``."""
    g = KnowledgeGraph(article_id="a")
    g.add_node(Node(type="article", id="art", text="T"))
    g.add_node(Node(type="summary_point", id="sp", text="s"))
    g.add_node(Node(type="quantity", id="q", text="SNR 24"))
    g.add_node(Node(type="claim", id="c", text="x", properties={"status": "valid"}))
    g.add_node(Node(type="evidence", id="ev", properties={"kind": "data", "reference": "r"}))
    g.add_edge(Edge(type="contains", source="art", target="sp", id="e1"))
    g.add_edge(Edge(type="summarizes", source="sp", target="q", id="e2"))
    g.add_edge(Edge(type="depends_on", source="c", target="q", id="e3"))
    g.add_edge(Edge(type="supported_by", source="c", target="ev", id="e4"))
    assert ARTICLE.validate(g) == []


def test_article_types_unknown_to_research():
    """The article types are rejected by the stock research profile."""
    g = KnowledgeGraph(article_id="a")
    g.add_node(Node(type="summary_point", id="sp"))
    assert "unknown-node-type" in _codes(get_profile("research").validate(g))


def test_article_contains_endpoint_rule():
    """`contains` must go article -> summary_point."""
    g = KnowledgeGraph(article_id="a")
    g.add_node(Node(type="article", id="art"))
    g.add_node(Node(type="claim", id="c"))
    g.add_edge(Edge(type="contains", source="art", target="c", id="e1"))
    assert "edge-bad-target-type" in _codes(ARTICLE.validate(g))


def test_project_accepts_question_hypothesis_loop():
    """A question -> hypothesis -> test -> answer graph validates under ``project``."""
    p = KnowledgeGraph(article_id="p")
    p.add_node(Node(type="question", id="q0", text="why?"))
    p.add_node(Node(type="hypothesis", id="h", text="because", properties={"status": "needs_review"}))
    p.add_node(Node(type="activity", id="a1", properties={"label": "test"}))
    p.add_node(Node(type="result", id="r", text="res", properties={"status": "valid"}))
    p.add_node(Node(type="evidence", id="ev", properties={"kind": "data", "reference": "x"}))
    p.add_edge(Edge(type="addresses", source="h", target="q0", id="e1"))
    p.add_edge(Edge(type="tests", source="a1", target="h", id="e2"))
    p.add_edge(Edge(type="answers", source="r", target="q0", id="e3"))
    p.add_edge(Edge(type="supported_by", source="h", target="ev", id="e4"))
    p.add_edge(Edge(type="generated_by", source="r", target="a1", id="e5"))
    assert PROJECT.validate(p) == []


def test_project_addresses_rejects_non_hypothesis_source():
    """`addresses` may only originate from a hypothesis."""
    p = KnowledgeGraph(article_id="p")
    p.add_node(Node(type="question", id="q0"))
    p.add_node(Node(type="claim", id="c"))
    p.add_edge(Edge(type="addresses", source="c", target="q0", id="e1"))
    assert "edge-bad-source-type" in _codes(PROJECT.validate(p))


def test_project_extends_article():
    """The project profile inherits every article node type."""
    assert set(ARTICLE.node_types) <= set(PROJECT.node_types)
    assert {"question", "hypothesis"} <= set(PROJECT.node_types)
