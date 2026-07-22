"""Tests for KnowledgeGraph persistence and legacy compatibility."""

from __future__ import annotations

import json

import pytest

from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.persistence import (
    SCHEMA_VERSION,
    dumps_graph,
    graph_from_document,
    load_graph,
    loads_graph,
    save_graph,
)


def _graph() -> KnowledgeGraph:
    """A small research-profile graph.

    Returns:
        The graph.

    """
    g = KnowledgeGraph(article_id="a", metadata={"title": "T"})
    g.add_node(Node(type="claim", id="c1", text="A claim."))
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "r"}))
    g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="x1"))
    return g


def test_v4_envelope_and_roundtrip():
    """dumps_graph writes a v4 envelope that loads back identically."""
    g = _graph()
    doc = json.loads(dumps_graph(g))
    assert doc["schema_version"] == SCHEMA_VERSION
    assert set(doc["graph"]) == {"article_id", "metadata", "nodes", "edges"}
    assert loads_graph(dumps_graph(g)) == g


def test_file_roundtrip(tmp_path):
    """save_graph then load_graph reconstructs the graph.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    g = _graph()
    path = tmp_path / "g.json"
    save_graph(g, path)
    assert load_graph(path) == g


def test_newer_schema_rejected():
    """A document from a newer schema version is refused."""
    with pytest.raises(ValueError, match="newer than supported"):
        graph_from_document({"schema_version": SCHEMA_VERSION + 1, "graph": _graph().to_dict()})


def test_legacy_v3_document_converts():
    """A legacy five-collection document converts to the generic graph."""
    legacy = {
        "schema_version": 3,
        "graph": {
            "article_id": "a",
            "metadata": {"title": "Legacy"},
            "statements": [
                {"id": "c1", "statement": "A claim.", "type": "claim", "status": "valid", "order": 0, "tags": ["x"]}
            ],
            "evidence": [{"id": "e1", "kind": "data", "reference": "d.csv", "relation": "supports"}],
            "activities": [{"id": "a1", "kind": "computation", "label": "run"}],
            "relations": [
                {
                    "id": "r1",
                    "subject_type": "claim",
                    "subject_id": "c1",
                    "predicate": "supported_by",
                    "object_type": "evidence",
                    "object_id": "e1",
                }
            ],
            "cross_references": [{"id": "x1", "subject_id": "c1", "predicate": "builds_on", "target": "other#c9"}],
        },
    }
    g = graph_from_document(legacy)
    assert g.article_id == "a"
    assert g.metadata["title"] == "Legacy"
    claim = g.nodes["c1"]
    assert claim.type == "claim"
    assert claim.text == "A claim."
    assert claim.properties["status"] == "valid"
    assert claim.tags == ["x"]
    evidence = g.nodes["e1"]
    assert evidence.type == "evidence"
    assert evidence.properties["kind"] == "data"
    assert evidence.properties["reference"] == "d.csv"
    assert g.nodes["a1"].type == "activity"
    assert g.nodes["a1"].properties["label"] == "run"
    rel = g.edges["r1"]
    assert (rel.type, rel.source, rel.target) == ("supported_by", "c1", "e1")
    xref = g.edges["x1"]
    assert (xref.type, xref.source, xref.target) == ("builds_on", "c1", "other#c9")


def test_legacy_file_from_old_core_loads(tmp_path):
    """A file written by the OLD core persistence loads via the new loader.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    from ideagraph.core import (
        Evidence,
        EvidenceKind,
        NodeType,
        ProvenanceGraph,
        ProvenancePredicate,
        ProvenanceRelation,
        Statement,
        StatementType,
    )
    from ideagraph.persistence import save_graph as old_save

    old = ProvenanceGraph(article_id="a")
    old.add_statement(Statement(statement="A claim.", id="c1", type=StatementType.CLAIM))
    old.add_evidence(Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="d.csv", id="e1"))
    old.add_relation(
        ProvenanceRelation(
            subject_type=NodeType.CLAIM,
            subject_id="c1",
            predicate=ProvenancePredicate.SUPPORTED_BY,
            object_type=NodeType.EVIDENCE,
            object_id="e1",
            id="r1",
        )
    )
    path = tmp_path / "legacy.json"
    old_save(old, path)

    g = load_graph(path)
    assert g.nodes["c1"].type == "claim"
    assert g.nodes["c1"].text == "A claim."
    assert g.nodes["e1"].properties["reference"] == "d.csv"
    assert g.edges["r1"].type == "supported_by"
