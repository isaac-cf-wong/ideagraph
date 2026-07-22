"""Tests for the ``ideagraph add-relation`` command."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg import Node
from ideagraph.kg.persistence import load_graph, save_graph

runner = CliRunner()


def _graph_with_nodes(path):
    """Create a graph holding claim ``c1``, evidence ``e1``, activity ``a1``.

    The activity is added through the core API so this command's tests do not
    depend on any other CLI command that registers activities.

    Args:
        path: Destination graph file path.

    Returns:
        The path written to.

    """
    runner.invoke(app, ["init", str(path)])
    runner.invoke(app, ["add-claim", str(path), "A", "--id", "c1"])
    runner.invoke(app, ["add-evidence", str(path), "c1", "--kind", "data", "--reference", "r", "--id", "e1"])
    graph = load_graph(path)
    graph.add_node(Node(type="activity", text="run", id="a1", properties={"kind": "computation", "label": "run"}))
    save_graph(graph, path)
    return path


def test_add_relation_autodetects_types(tmp_path):
    """Subject/object types are inferred from ids for stored nodes.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_nodes(tmp_path / "g.json")
    result = runner.invoke(app, ["add-relation", str(path), "e1", "a1", "--predicate", "generated_by"])
    assert result.exit_code == 0, result.stderr
    rel_id = result.stdout.strip()
    graph = load_graph(path)
    edge = graph.edges[rel_id]
    assert edge.source == "e1"
    assert edge.target == "a1"
    assert edge.type == "generated_by"
    assert graph.nodes["e1"].type == "evidence"
    assert graph.nodes["a1"].type == "activity"


def test_add_relation_links_existing_evidence_to_second_claim(tmp_path):
    """Existing evidence can support a second claim via an explicit edge.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_nodes(tmp_path / "g.json")
    runner.invoke(app, ["add-claim", str(path), "B", "--id", "c2"])
    result = runner.invoke(app, ["add-relation", str(path), "c2", "e1", "--predicate", "supported_by"])
    assert result.exit_code == 0, result.stderr
    edges = load_graph(path).outgoing("c2")
    assert [e.target for e in edges] == ["e1"]
    assert edges[0].type == "supported_by"


def test_add_relation_explicit_type_for_unstored_endpoint(tmp_path):
    """An artefact/agent endpoint is accepted when its type is given explicitly.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_nodes(tmp_path / "g.json")
    result = runner.invoke(
        app,
        ["add-relation", str(path), "c1", "orcid:0000", "--predicate", "attributed_to", "--object-type", "agent"],
    )
    assert result.exit_code == 0, result.stderr
    edge = load_graph(path).edges[result.stdout.strip()]
    assert edge.target == "orcid:0000"


def test_add_relation_undetectable_id_errors(tmp_path):
    """An unknown id with no explicit type exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_nodes(tmp_path / "g.json")
    result = runner.invoke(app, ["add-relation", str(path), "c1", "ghost", "--predicate", "relates_to"])
    assert result.exit_code == 1
    assert "Cannot determine object type" in result.stderr


def test_add_relation_missing_stored_node_errors(tmp_path):
    """An explicit stored type whose id is absent exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_nodes(tmp_path / "g.json")
    result = runner.invoke(
        app,
        ["add-relation", str(path), "c1", "missing", "--predicate", "supported_by", "--object-type", "evidence"],
    )
    assert result.exit_code == 1
    assert "No such evidence" in result.stderr


def test_add_relation_missing_file(tmp_path):
    """add-relation on a missing file exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["add-relation", str(tmp_path / "nope.json"), "c1", "e1", "--predicate", "relates_to"])
    assert result.exit_code == 1
    assert "No such file" in result.stderr
