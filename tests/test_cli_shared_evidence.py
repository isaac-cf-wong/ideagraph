"""Tests for standalone and multi-claim evidence on ``add-evidence``."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg.persistence import load_graph

runner = CliRunner()


def _graph_with_claims(path, *claim_ids):
    """Create a graph holding the given claims.

    Args:
        path: Destination graph file path.
        claim_ids: Ids of claims to create.

    Returns:
        The path written to.

    """
    runner.invoke(app, ["init", str(path)])
    for cid in claim_ids:
        runner.invoke(app, ["add-claim", str(path), cid.upper(), "--id", cid])
    return path


def test_standalone_evidence_no_claim(tmp_path):
    """Evidence can be registered with no claim and no edges.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_claims(tmp_path / "g.json")
    result = runner.invoke(
        app,
        ["add-evidence", str(path), "--kind", "data", "--reference", "r", "--id", "e1"],
    )
    assert result.exit_code == 0, result.stderr
    graph = load_graph(path)
    assert "e1" in graph.nodes
    assert graph.nodes["e1"].type == "evidence"
    assert all(e.target != "e1" for e in graph.edges.values())


def test_multi_claim_evidence(tmp_path):
    """One evidence links to the positional claim and every --to-claim.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_claims(tmp_path / "g.json", "c1", "c2", "c3")
    result = runner.invoke(
        app,
        [
            "add-evidence",
            str(path),
            "c1",
            "--kind",
            "figure",
            "--reference",
            "fig.npz",
            "--id",
            "e1",
            "--to-claim",
            "c2",
            "--to-claim",
            "c3",
        ],
    )
    assert result.exit_code == 0, result.stderr
    graph = load_graph(path)
    for cid in ("c1", "c2", "c3"):
        edges = [e for e in graph.outgoing(cid) if e.target == "e1"]
        assert len(edges) == 1
        assert edges[0].type == "supported_by"
    assert graph.nodes["e1"].type == "evidence"


def test_to_claim_only_without_positional(tmp_path):
    """--to-claim works without a positional claim id.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_claims(tmp_path / "g.json", "c1")
    result = runner.invoke(
        app,
        ["add-evidence", str(path), "--kind", "data", "--reference", "r", "--id", "e1", "--to-claim", "c1"],
    )
    assert result.exit_code == 0, result.stderr
    graph = load_graph(path)
    assert graph.nodes["e1"].type == "evidence"
    assert [e.target for e in graph.outgoing("c1")] == ["e1"]


def test_unknown_target_claim_errors(tmp_path):
    """A missing --to-claim target exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_claims(tmp_path / "g.json", "c1")
    result = runner.invoke(
        app,
        ["add-evidence", str(path), "c1", "--kind", "data", "--reference", "r", "--to-claim", "ghost"],
    )
    assert result.exit_code == 1
    assert "No such statement: ghost" in result.stderr
