"""Tests for the ``ideagraph mark`` command."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg.persistence import load_graph

runner = CliRunner()


def _graph_with_claim(path):
    """Create a graph file holding one unresolved claim ``c1``.

    Args:
        path: Destination graph file path.

    Returns:
        The path written to.

    """
    runner.invoke(app, ["init", str(path)])
    runner.invoke(app, ["add-claim", str(path), "A", "--id", "c1"])
    return path


def test_mark_sets_status(tmp_path):
    """Mark persists the chosen status onto the claim.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_claim(tmp_path / "g.json")
    result = runner.invoke(app, ["mark", str(path), "c1", "valid"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "c1: valid"
    assert load_graph(path).nodes["c1"].properties["status"] == "valid"


def test_mark_records_note_in_metadata(tmp_path):
    """--note is stored in the claim's metadata.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_claim(tmp_path / "g.json")
    runner.invoke(app, ["mark", str(path), "c1", "invalid", "--note", "reviewer disagrees"])
    node = load_graph(path).nodes["c1"]
    assert node.properties["status"] == "invalid"
    assert node.properties["metadata"]["review_note"] == "reviewer disagrees"


def test_mark_resolves_needs_review(tmp_path):
    """A needs_review claim can be resolved to valid by a human.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_claim(tmp_path / "g.json")
    runner.invoke(app, ["mark", str(path), "c1", "needs_review"])
    assert load_graph(path).nodes["c1"].properties["status"] == "needs_review"
    runner.invoke(app, ["mark", str(path), "c1", "valid"])
    assert load_graph(path).nodes["c1"].properties["status"] == "valid"


def test_mark_unknown_claim(tmp_path):
    """Marking a missing claim exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_claim(tmp_path / "g.json")
    result = runner.invoke(app, ["mark", str(path), "missing", "valid"])
    assert result.exit_code == 1
    assert "No such statement" in result.stderr


def test_mark_invalid_status_rejected(tmp_path):
    """An unrecognised status value is rejected by the CLI.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_with_claim(tmp_path / "g.json")
    result = runner.invoke(app, ["mark", str(path), "c1", "bogus"])
    assert result.exit_code != 0


def test_mark_missing_file(tmp_path):
    """Mark on a missing file exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["mark", str(tmp_path / "nope.json"), "c1", "valid"])
    assert result.exit_code == 1
    assert "No such file" in result.stderr
