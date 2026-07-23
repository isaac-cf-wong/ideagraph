"""Tests for the ``ideagraph doctor --profile`` option."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.persistence import save_graph

runner = CliRunner()


def _project_graph(path):
    """Write a minimal question/hypothesis project graph.

    Args:
        path: Destination graph file path.

    Returns:
        The path written to.

    """
    g = KnowledgeGraph(article_id="p")
    g.add_node(Node(type="question", id="q0", text="why?"))
    g.add_node(Node(type="hypothesis", id="h", text="because"))
    g.add_edge(Edge(type="addresses", source="h", target="q0", id="e1"))
    save_graph(g, path)
    return path


def test_doctor_rejects_project_shape_under_research(tmp_path):
    """Under the default research profile, project types are unknown.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _project_graph(tmp_path / "p.json")
    result = runner.invoke(app, ["doctor", str(path)])
    assert result.exit_code == 1
    assert "unknown-node-type" in result.stdout


def test_doctor_accepts_project_shape_with_profile(tmp_path):
    """`--profile project` validates the question/hypothesis shape.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _project_graph(tmp_path / "p.json")
    result = runner.invoke(app, ["doctor", str(path), "--profile", "project"])
    assert result.exit_code == 0
    assert "No problems found" in result.stdout


def test_doctor_unknown_profile(tmp_path):
    """An unknown profile name exits non-zero with a message.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _project_graph(tmp_path / "p.json")
    result = runner.invoke(app, ["doctor", str(path), "--profile", "nope"])
    assert result.exit_code == 1
    assert "Unknown profile" in result.stderr
