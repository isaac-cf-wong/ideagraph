"""Tests for the kg Markdown report renderer."""

from __future__ import annotations

from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.reporting import render_node_report, render_report


def _graph() -> KnowledgeGraph:
    """A graph with a claim, a finding, a result, and a non-assertion method.

    Returns:
        The graph.

    """
    g = KnowledgeGraph()
    g.add_node(Node(type="claim", id="c1", text="A claim.", properties={"status": "valid"}))
    g.add_node(Node(type="finding", id="f1", text="A finding.", properties={"status": "valid"}))
    g.add_node(Node(type="result", id="r1", text="A result.", properties={"status": "unresolved"}))
    g.add_node(Node(type="method", id="m1", text="A method."))
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "d.csv"}))
    g.add_edge(Edge(type="supported_by", source="f1", target="e1", id="s1"))
    return g


def test_report_covers_all_assertion_types():
    """The report includes claim, finding, and result — not just claim."""
    report = render_report(_graph())
    assert "3 assertion(s)." in report
    assert "## Claim `c1`" in report
    assert "## Finding `f1`" in report
    assert "## Result `r1`" in report
    # A non-assertion statement is not reported.
    assert "`m1`" not in report


def test_report_status_summary():
    """The status summary counts each assertion's stored status."""
    report = render_report(_graph())
    assert "Status summary: 1 unresolved, 2 valid." in report


def test_node_report_heading_reflects_type():
    """A single-node report titles the section by the node's type."""
    assert render_node_report(_graph(), "f1").startswith("## Finding `f1`")


def test_report_shows_supporting_evidence():
    """Supporting evidence appears under the finding it backs."""
    report = render_node_report(_graph(), "f1")
    assert "### Supporting evidence (1)" in report
    assert "d.csv" in report


def test_empty_graph_report():
    """An empty graph reports zero assertions."""
    assert "0 assertion(s)." in render_report(KnowledgeGraph())
