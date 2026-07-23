"""Tests for project-profile semantics: conclusion gate and promotion."""

from __future__ import annotations

import pytest

from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.extract import SOURCE_GID_KEY
from ideagraph.kg.profiles import PROJECT, conclusion_status, promote


def _project(*, concluded: bool) -> KnowledgeGraph:
    """Build a project graph, either mid-flight or concluded.

    Args:
        concluded: If true, resolve the hypothesis and add an evidenced answer.

    Returns:
        The project graph.

    """
    g = KnowledgeGraph(article_id="proj")
    g.add_node(Node(type="question", id="q0", text="why?"))
    g.add_node(Node(type="hypothesis", id="h", text="because", properties={"status": "needs_review"}))
    g.add_node(Node(type="activity", id="a1", properties={"label": "test"}))
    # a node imported from the cache carries a provenance stamp
    g.add_node(Node(type="finding", id="lit", text="prior work", properties={SOURCE_GID_KEY: "dupletsa2025#dl_over"}))
    g.add_edge(Edge(type="addresses", source="h", target="q0", id="e1"))
    g.add_edge(Edge(type="tests", source="a1", target="h", id="e2"))
    if concluded:
        g.nodes["h"].properties["status"] = "valid"
        g.add_node(Node(type="evidence", id="ev", properties={"kind": "data", "reference": "x"}))
        g.add_node(Node(type="result", id="r", text="answer", properties={"status": "valid"}))
        g.add_edge(Edge(type="answers", source="r", target="q0", id="e3"))
        g.add_edge(Edge(type="supported_by", source="r", target="ev", id="e4"))
        g.add_edge(Edge(type="generated_by", source="r", target="a1", id="e5"))
        g.add_edge(Edge(type="derived_from", source="r", target="lit", id="e6"))
    return g


def test_draft_is_not_concluded():
    """A mid-flight project is not concluded and lists why."""
    status = conclusion_status(_project(concluded=False))
    assert not status.concluded
    joined = " ".join(status.reasons)
    assert "no answering" in joined
    assert "unresolved" in joined


def test_no_question_is_not_concluded():
    """A graph without a question node cannot be concluded."""
    status = conclusion_status(KnowledgeGraph(article_id="x"))
    assert not status.concluded
    assert any("no question" in r for r in status.reasons)


def test_answer_without_evidence_is_not_concluded():
    """An answer lacking supporting evidence blocks conclusion."""
    g = KnowledgeGraph(article_id="x")
    g.add_node(Node(type="question", id="q0"))
    g.add_node(Node(type="result", id="r", properties={"status": "valid"}))
    g.add_edge(Edge(type="answers", source="r", target="q0", id="e1"))
    status = conclusion_status(g)
    assert not status.concluded
    assert any("no supporting evidence" in r for r in status.reasons)


def test_concluded_project():
    """A resolved, evidenced, answered project is concluded."""
    assert conclusion_status(_project(concluded=True)).concluded


def test_promote_refuses_draft():
    """Promoting an unconcluded project raises."""
    with pytest.raises(ValueError, match="not concluded"):
        promote(_project(concluded=False), article_id="paper")


def test_promote_keeps_native_and_rewires_citations():
    """Promotion drops imported nodes and rewires edges into them as xrefs."""
    promoted = promote(_project(concluded=True), article_id="paper2027")
    # imported node is left behind
    assert all(SOURCE_GID_KEY not in n.properties for n in promoted.nodes.values())
    assert "lit" not in promoted.nodes
    # the edge into the imported node became a cross-article reference to its origin
    xrefs = [e for e in promoted.edges.values() if e.target == "dupletsa2025#dl_over"]
    assert len(xrefs) == 1
    assert xrefs[0].type == "derived_from"
    assert promoted.article_id == "paper2027"
    assert promoted.metadata["promoted_from"] == "proj"


def test_promoted_graph_validates():
    """The promoted graph is structurally valid under the project profile."""
    promoted = promote(_project(concluded=True), article_id="paper2027")
    assert PROJECT.validate(promoted) == []
