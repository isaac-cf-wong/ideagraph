"""Tests for the ``ideagraph promote`` CLI command."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.persistence import load_graph, save_graph

runner = CliRunner()


def _project_file(path, *, concluded: bool):
    """Write a project graph, either mid-flight or concluded.

    Args:
        path: Destination graph file path.
        concluded: If true, resolve the hypothesis and add an evidenced answer.

    Returns:
        The path written to.

    """
    g = KnowledgeGraph(article_id="proj")
    g.add_node(Node(type="question", id="q0", text="why?"))
    g.add_node(Node(type="hypothesis", id="h", text="because", properties={"status": "needs_review"}))
    g.add_edge(Edge(type="addresses", source="h", target="q0", id="e1"))
    if concluded:
        g.nodes["h"].properties["status"] = "valid"
        g.add_node(Node(type="evidence", id="ev", properties={"kind": "data", "reference": "x"}))
        g.add_node(Node(type="result", id="r", text="answer", properties={"status": "valid"}))
        g.add_edge(Edge(type="answers", source="r", target="q0", id="e2"))
        g.add_edge(Edge(type="supported_by", source="r", target="ev", id="e3"))
    save_graph(g, path)
    return path


def test_check_draft_exits_nonzero(tmp_path):
    """`--check` on a draft reports not-concluded and exits 1.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _project_file(tmp_path / "p.json", concluded=False)
    result = runner.invoke(app, ["promote", str(path), "--check"])
    assert result.exit_code == 1
    assert "Not concluded" in result.stdout


def test_check_concluded_exits_zero(tmp_path):
    """`--check` on a concluded project exits 0.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _project_file(tmp_path / "p.json", concluded=True)
    result = runner.invoke(app, ["promote", str(path), "--check"])
    assert result.exit_code == 0
    assert "Concluded" in result.stdout


def test_promote_draft_refused(tmp_path):
    """Promoting a draft (no --check) exits 1 with reasons on stderr.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _project_file(tmp_path / "p.json", concluded=False)
    result = runner.invoke(app, ["promote", str(path), "--article-id", "paper"])
    assert result.exit_code == 1
    assert "not concluded" in result.stderr


def test_promote_requires_article_id(tmp_path):
    """Promoting without --article-id exits 1.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _project_file(tmp_path / "p.json", concluded=True)
    result = runner.invoke(app, ["promote", str(path)])
    assert result.exit_code == 1
    assert "article-id" in result.stderr


def test_promote_to_file(tmp_path):
    """Promoting a concluded project writes the new article graph.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _project_file(tmp_path / "p.json", concluded=True)
    out = tmp_path / "out" / "paper.json"
    result = runner.invoke(app, ["promote", str(path), "--article-id", "paper2027", "-o", str(out)])
    assert result.exit_code == 0
    promoted = load_graph(out)
    assert promoted.article_id == "paper2027"
    assert "q0" in promoted.nodes


def test_promote_missing_file(tmp_path):
    """A missing input file exits non-zero with a message.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["promote", str(tmp_path / "nope.json"), "--check"])
    assert result.exit_code == 1
    assert "No such file" in result.stderr
