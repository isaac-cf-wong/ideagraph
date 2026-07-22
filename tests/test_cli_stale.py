"""Tests for the ``ideagraph stale`` command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.core.staleness import compute_digest
from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.persistence import load_graph, save_graph

runner = CliRunner()


def _graph_with_file_evidence(graph_path, artefact_path, *, recorded: bytes, current: bytes):
    """Build a graph whose claim is supported by a file-backed evidence.

    Args:
        graph_path: Where to save the graph.
        artefact_path: The artefact file the evidence references.
        recorded: Bytes whose digest is stored on the evidence.
        current: Bytes actually written to the artefact file.

    Returns:
        The graph path.

    """
    artefact_path.write_bytes(current)
    g = KnowledgeGraph()
    g.add_node(Node(type="claim", text="A", id="c1", properties={"status": "valid"}))
    g.add_node(
        Node(
            type="evidence",
            id="e1",
            properties={"kind": "data", "reference": artefact_path.name, "digest": compute_digest(recorded)},
        )
    )
    g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="s1"))
    save_graph(g, graph_path)
    return graph_path


def test_stale_detects_changed_artefact(tmp_path):
    """A drifted artefact makes its claim show as stale.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    gp = _graph_with_file_evidence(tmp_path / "g.json", tmp_path / "a.txt", recorded=b"old", current=b"new")
    result = runner.invoke(app, ["stale", str(gp), "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert "c1: supporting evidence has changed" in result.stdout


def test_stale_clean_when_unchanged(tmp_path):
    """An unchanged artefact yields no stale claims.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    gp = _graph_with_file_evidence(tmp_path / "g.json", tmp_path / "a.txt", recorded=b"same", current=b"same")
    result = runner.invoke(app, ["stale", str(gp), "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert "No stale claims." in result.stdout


def test_stale_apply_marks_and_persists(tmp_path):
    """--apply flips the valid claim to stale and saves it.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    gp = _graph_with_file_evidence(tmp_path / "g.json", tmp_path / "a.txt", recorded=b"old", current=b"new")
    result = runner.invoke(app, ["stale", str(gp), "--base", str(tmp_path), "--apply"])
    assert result.exit_code == 0
    assert load_graph(gp).nodes["c1"].properties["status"] == "stale"


def test_stale_json_output(tmp_path):
    """--json reports stale (and marked, with --apply) claim ids.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    gp = _graph_with_file_evidence(tmp_path / "g.json", tmp_path / "a.txt", recorded=b"old", current=b"new")
    result = runner.invoke(app, ["stale", str(gp), "--base", str(tmp_path), "--apply", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["stale"] == ["c1"]
    assert payload["marked"] == ["c1"]


def test_stale_missing_artefact_is_not_stale(tmp_path):
    """Evidence whose file is absent is not reported changed.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    gp = _graph_with_file_evidence(tmp_path / "g.json", tmp_path / "a.txt", recorded=b"x", current=b"x")
    (tmp_path / "a.txt").unlink()
    result = runner.invoke(app, ["stale", str(gp), "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert "No stale claims." in result.stdout


def test_stale_missing_file(tmp_path):
    """A missing graph file exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["stale", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
    assert "No such file" in result.stderr
