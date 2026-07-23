"""Tests for the ``ideagraph extract`` CLI command."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.persistence import load_graph, loads_graph, save_graph

runner = CliRunner()


def _graph_file(path):
    """Write an a->b->c chain graph with article_id ``src``.

    Args:
        path: Destination graph file path.

    Returns:
        The path written to.

    """
    g = KnowledgeGraph(article_id="src")
    for nid in ("a", "b", "c"):
        g.add_node(Node(type="claim", id=nid, text=nid.upper()))
    g.add_edge(Edge(type="depends_on", source="a", target="b", id="ab"))
    g.add_edge(Edge(type="depends_on", source="b", target="c", id="bc"))
    save_graph(g, path)
    return path


def test_extract_to_file(tmp_path):
    """Extract -o writes a subgraph file with provenance stamped.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path / "g.json")
    out = tmp_path / "out" / "sub.json"
    result = runner.invoke(app, ["extract", str(path), "a", "--hops", "1", "-o", str(out), "--article-id", "dest"])
    assert result.exit_code == 0
    sub = load_graph(out)
    assert set(sub.nodes) == {"a", "b"}
    assert sub.article_id == "dest"
    assert sub.nodes["a"].properties["source_gid"] == "src#a"


def test_extract_stdout(tmp_path):
    """Without -o the extracted graph is printed as JSON.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path / "g.json")
    result = runner.invoke(app, ["extract", str(path), "b", "--hops", "0"])
    assert result.exit_code == 0
    sub = loads_graph(result.stdout)
    assert set(sub.nodes) == {"b"}


def test_extract_missing_file(tmp_path):
    """A missing input file exits non-zero with a message.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["extract", str(tmp_path / "nope.json"), "a"])
    assert result.exit_code == 1
    assert "No such file" in result.stderr


def test_extract_unknown_seed(tmp_path):
    """An unknown seed id exits non-zero and names the offending id.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path / "g.json")
    result = runner.invoke(app, ["extract", str(path), "ghost"])
    assert result.exit_code == 1
    assert "ghost" in result.stderr
