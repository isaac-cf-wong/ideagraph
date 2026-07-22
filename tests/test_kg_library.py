"""Library indexing over native (v4) generic graph files."""

from __future__ import annotations

from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.persistence import save_graph
from ideagraph.library import Library


def _write(dirpath, slug: str, graph: KnowledgeGraph) -> None:
    """Save a generic graph file under a directory.

    Args:
        dirpath: The library root directory.
        slug: File stem.
        graph: The graph to save.
    """
    save_graph(graph, dirpath / f"{slug}.json")


def test_index_native_generic_graphs(tmp_path):
    """The library indexes v4 nodes/edges: statements, intra + cross edges.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    a = KnowledgeGraph(article_id="a", metadata={"title": "A"})
    a.add_node(Node(type="claim", id="s1", text="First.", properties={"status": "unresolved", "order": 0}))
    a.add_node(Node(type="finding", id="s2", text="Second.", properties={"status": "valid", "order": 1}))
    a.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "d.csv"}))
    a.add_edge(Edge(type="elaborates", source="s1", target="s2", id="r1"))
    a.add_edge(Edge(type="supported_by", source="s2", target="e1", id="r2"))
    a.add_edge(Edge(type="builds_on", source="s1", target="b#t1", id="x1"))
    b = KnowledgeGraph(article_id="b", metadata={"title": "B"})
    b.add_node(Node(type="claim", id="t1", text="Target."))
    _write(tmp_path, "a", a)
    _write(tmp_path, "b", b)

    with Library(tmp_path) as lib:
        lib.index()
        snap = lib.snapshot()
        # Statements only (evidence is not indexed as a statement node).
        assert {n["id"] for n in snap["nodes"]} == {"a#s1", "a#s2", "b#t1"}
        kinds = {(e["source"], e["target"]): e["kind"] for e in snap["edges"]}
        assert kinds[("a#s1", "a#s2")] == "intra"
        assert kinds[("a#s1", "b#t1")] == "cross"
        # supported_by (statement -> evidence) is not an idea-level edge.
        assert ("a#s2", "a#e1") not in kinds
        # The resolvable cross edge is not dangling.
        cross = next(e for e in snap["edges"] if e["kind"] == "cross")
        assert cross["dangling"] is False
        # Unresolved assertion is surfaced; the valid one is not.
        unresolved = {h.gid for h in lib.unsupported_assertions()}
        assert unresolved == {"a#s1"}


def test_index_native_dangling_cross_reference(tmp_path):
    """A cross edge to a missing target is reported dangling.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    a = KnowledgeGraph(article_id="a")
    a.add_node(Node(type="claim", id="s1", text="x"))
    a.add_edge(Edge(type="builds_on", source="s1", target="z#missing", id="x1"))
    _write(tmp_path, "a", a)
    with Library(tmp_path) as lib:
        lib.index()
        dangling = lib.dangling_cross_references()
        assert [e.dst_gid for e in dangling] == ["z#missing"]
