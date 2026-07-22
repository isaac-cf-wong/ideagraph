"""Tests for the ``ideagraph export`` CLI command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.persistence import save_graph
from ideagraph.kg.prov import CK_NAMESPACE

runner = CliRunner()


def _graph_file(path):
    """Write a graph with one claim supported by one piece of evidence.

    Args:
        path: Destination graph file path.

    Returns:
        The path written to.

    """
    g = KnowledgeGraph()
    g.add_node(Node(type="claim", text="A", id="c1", properties={"status": "unresolved"}))
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "r"}))
    g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="s1"))
    save_graph(g, path)
    return path


def test_export_stdout_is_prov_json(tmp_path):
    """Export prints PROV-JSON to stdout.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path / "g.json")
    result = runner.invoke(app, ["export", str(path)])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["prefix"]["ck"] == CK_NAMESPACE
    assert doc["entity"]["ck:c1"]["prov:type"] == "ck:claim"
    assert "ck:s1" in doc["wasInfluencedBy"]


def test_export_to_file(tmp_path):
    """Export -o writes PROV-JSON to a file with a trailing newline.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path / "g.json")
    out = tmp_path / "out" / "prov.json"
    result = runner.invoke(app, ["export", str(path), "-o", str(out)])
    assert result.exit_code == 0
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text)["entity"]["ck:c1"]["prov:type"] == "ck:claim"


def test_export_missing_file(tmp_path):
    """A missing input file exits non-zero with a message.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["export", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
    assert "No such file" in result.stderr
