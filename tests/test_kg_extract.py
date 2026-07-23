"""Tests for induced-subgraph extraction (ideagraph.kg.extract)."""

from __future__ import annotations

from ideagraph.kg import Edge, KnowledgeGraph, Node, extract_subgraph
from ideagraph.kg.extract import SOURCE_GID_KEY, neighbourhood


def _chain() -> KnowledgeGraph:
    """Return a->b->c->d chain plus a cross-article edge leaving a.

    Returns:
        A source graph with article_id ``src``.

    """
    g = KnowledgeGraph(article_id="src")
    for nid in ("a", "b", "c", "d"):
        g.add_node(Node(type="claim", id=nid, text=nid.upper()))
    g.add_edge(Edge(type="depends_on", source="a", target="b", id="ab"))
    g.add_edge(Edge(type="depends_on", source="b", target="c", id="bc"))
    g.add_edge(Edge(type="depends_on", source="c", target="d", id="cd"))
    g.add_edge(Edge(type="cites", source="a", target="other#x", id="ax"))
    return g


def test_neighbourhood_expands_both_directions():
    """Expansion follows edges either way and honours the hop budget."""
    g = _chain()
    assert neighbourhood(g, {"b"}, hops=0) == {"b"}
    assert neighbourhood(g, {"b"}, hops=1) == {"a", "b", "c"}
    assert neighbourhood(g, {"a"}, hops=2) == {"a", "b", "c"}


def test_neighbourhood_ignores_unknown_seeds():
    """Seed ids absent from the graph are dropped, not errored."""
    g = _chain()
    assert neighbourhood(g, {"a", "ghost"}, hops=0) == {"a"}


def test_extract_keeps_internal_and_cross_article_edges():
    """Internal edges among kept nodes and cross-article edges leaving them survive."""
    g = _chain()
    sub = extract_subgraph(g, {"a"}, hops=1)
    assert set(sub.nodes) == {"a", "b"}
    edge_ids = set(sub.edges)
    assert "ab" in edge_ids  # internal edge kept
    assert "ax" in edge_ids  # cross-article edge leaving a kept
    assert "bc" not in edge_ids  # c is out of the induced set


def test_extract_stamps_provenance():
    """Each copied node records its origin global id, once."""
    g = _chain()
    sub = extract_subgraph(g, {"a"}, hops=0)
    assert sub.nodes["a"].properties[SOURCE_GID_KEY] == "src#a"


def test_extract_preserves_existing_provenance():
    """Re-extraction keeps the first origin rather than overwriting it."""
    g = _chain()
    g.nodes["a"].properties[SOURCE_GID_KEY] = "original#a"
    sub = extract_subgraph(g, {"a"}, hops=0)
    assert sub.nodes["a"].properties[SOURCE_GID_KEY] == "original#a"


def test_extract_without_source_article_id_skips_stamp():
    """A source graph without an article_id cannot stamp provenance."""
    g = KnowledgeGraph()
    g.add_node(Node(type="claim", id="a"))
    sub = extract_subgraph(g, {"a"}, hops=0)
    assert SOURCE_GID_KEY not in sub.nodes["a"].properties


def test_extract_is_independent_of_source():
    """Mutating the extracted graph does not touch the source."""
    g = _chain()
    sub = extract_subgraph(g, {"a"}, hops=0, article_id="dest")
    sub.nodes["a"].properties["mutated"] = True
    sub.nodes["a"].tags.append("x")
    assert "mutated" not in g.nodes["a"].properties
    assert g.nodes["a"].tags == []
    assert sub.article_id == "dest"
