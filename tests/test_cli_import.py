"""Tests for the ``ideagraph import`` command."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.persistence import load_graph
from ideagraph.kg.prov import dumps_prov

runner = CliRunner()


def _prov_file(path):
    """Write a PROV-JSON file for a claim supported by one piece of evidence.

    Args:
        path: Destination PROV-JSON file path.

    Returns:
        The path written to.

    """
    g = KnowledgeGraph()
    g.add_node(Node(type="claim", text="A", id="c1", properties={"status": "unresolved"}))
    g.add_node(Node(type="evidence", id="e1", properties={"kind": "data", "reference": "r"}))
    g.add_edge(Edge(type="supported_by", source="c1", target="e1", id="s1"))
    path.write_text(dumps_prov(g), encoding="utf-8")
    return path


def test_import_writes_graph(tmp_path):
    """Import converts PROV-JSON into a loadable ideagraph graph.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    src = _prov_file(tmp_path / "prov.json")
    dest = tmp_path / "g.json"
    result = runner.invoke(app, ["import", str(src), str(dest)])
    assert result.exit_code == 0
    graph = load_graph(dest)
    assert graph.nodes["c1"].text == "A"
    assert graph.nodes["e1"].type == "evidence"
    assert graph.outgoing("c1")[0].type == "supported_by"


def test_import_missing_source(tmp_path):
    """A missing source file exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["import", str(tmp_path / "nope.json"), str(tmp_path / "g.json")])
    assert result.exit_code == 1
    assert "No such file" in result.stderr


def test_import_refuses_overwrite(tmp_path):
    """Import refuses to clobber an existing destination without --force.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    src = _prov_file(tmp_path / "prov.json")
    dest = tmp_path / "g.json"
    dest.write_text("sentinel", encoding="utf-8")
    result = runner.invoke(app, ["import", str(src), str(dest)])
    assert result.exit_code == 1
    assert "Refusing to overwrite" in result.stderr
    assert dest.read_text(encoding="utf-8") == "sentinel"


def test_import_force_overwrites(tmp_path):
    """Import --force overwrites an existing destination.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    src = _prov_file(tmp_path / "prov.json")
    dest = tmp_path / "g.json"
    dest.write_text("sentinel", encoding="utf-8")
    result = runner.invoke(app, ["import", str(src), str(dest), "--force"])
    assert result.exit_code == 0
    assert load_graph(dest).nodes["c1"].text == "A"


def test_export_then_import_round_trips_via_cli(tmp_path):
    """A graph exported then imported through the CLI keeps its structure.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    graph_path = tmp_path / "g.json"
    runner.invoke(app, ["init", str(graph_path)])
    runner.invoke(app, ["add-claim", str(graph_path), "A", "--id", "c1"])
    runner.invoke(app, ["add-evidence", str(graph_path), "c1", "--kind", "data", "--reference", "r"])
    prov_path = tmp_path / "prov.json"
    runner.invoke(app, ["export", str(graph_path), "-o", str(prov_path)])
    back_path = tmp_path / "back.json"
    result = runner.invoke(app, ["import", str(prov_path), str(back_path)])
    assert result.exit_code == 0
    back = load_graph(back_path)
    assert back.nodes["c1"].text == "A"
    assert len([n for n in back.nodes.values() if n.type == "evidence"]) == 1
    assert back.outgoing("c1")[0].type == "supported_by"
