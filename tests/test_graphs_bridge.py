"""Tests for the ORM<->KnowledgeGraph bridge and import/export commands."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.persistence import load_graph, save_graph
from ideagraph.server.graphs.bridge import graph_to_orm, orm_to_graph
from ideagraph.server.graphs.models import Edge as EdgeRow
from ideagraph.server.graphs.models import Graph
from ideagraph.server.graphs.models import Node as NodeRow


def _sample_graph() -> KnowledgeGraph:
    """Build a graph exercising node and edge types plus a cross reference.

    Returns:
        The graph.

    """
    g = KnowledgeGraph(article_id="art1", metadata={"title": "Demo"})
    g.add_node(Node(type="claim", id="c1", text="A claim.", properties={"status": "valid"}))
    g.add_node(
        Node(type="evidence", id="e1", properties={"kind": "data", "reference": "data.csv", "digest": "sha256:aa"})
    )
    g.add_node(Node(type="activity", id="a1", text="run", properties={"kind": "computation", "label": "run"}))
    g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="edge-1"))
    g.add_edge(Edge(type="builds_on", source="c1", target="art2#c9", id="x1"))
    return g


@pytest.mark.django_db
def test_bridge_roundtrip_preserves_graph():
    """orm_to_graph inverts graph_to_orm."""
    original = _sample_graph()
    row = graph_to_orm(original, slug="demo")
    assert orm_to_graph(row) == original


@pytest.mark.django_db
def test_denormalised_columns_populated():
    """Node/Edge denormalised columns are filled from the graph."""
    graph_to_orm(_sample_graph(), slug="demo")
    claim = NodeRow.objects.get(node_id="c1")
    assert claim.type == "claim"
    assert claim.status == "valid"
    assert claim.text == "A claim."
    evidence = NodeRow.objects.get(node_id="e1")
    assert evidence.type == "evidence"
    rel = EdgeRow.objects.get(edge_id="edge-1")
    assert (rel.type, rel.source, rel.target) == ("supported_by", "c1", "e1")
    xref = EdgeRow.objects.get(edge_id="x1")
    assert (xref.type, xref.source, xref.target) == ("builds_on", "c1", "art2#c9")


@pytest.mark.django_db
def test_graph_metadata_persisted():
    """Graph-level article_id/title/metadata are stored."""
    row = graph_to_orm(_sample_graph(), slug="demo")
    assert row.article_id == "art1"
    assert row.title == "Demo"
    assert row.metadata["title"] == "Demo"


@pytest.mark.django_db
def test_reimport_replaces_existing():
    """Importing the same slug replaces the previous rows."""
    graph_to_orm(_sample_graph(), slug="demo")
    smaller = KnowledgeGraph(article_id="art1")
    smaller.add_node(Node(type="claim", id="c1", text="Only one."))
    graph_to_orm(smaller, slug="demo")
    assert Graph.objects.filter(slug="demo").count() == 1
    assert NodeRow.objects.filter(graph__slug="demo").count() == 1
    assert EdgeRow.objects.filter(graph__slug="demo").count() == 0


@pytest.mark.django_db
def test_import_then_export_command_roundtrip(tmp_path):
    """import_graph then export_graph reproduces the graph on disk.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    src = tmp_path / "in.json"
    save_graph(_sample_graph(), src)
    call_command("import_graph", "demo", str(src))
    out = tmp_path / "out.json"
    call_command("export_graph", "demo", str(out))
    assert load_graph(out) == load_graph(src)
