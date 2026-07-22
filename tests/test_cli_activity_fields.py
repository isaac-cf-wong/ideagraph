"""Tests for add-activity timing and used/generated options."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg.persistence import load_graph

runner = CliRunner()


def _graph(path):
    """Create an empty graph file.

    Args:
        path: Destination graph file path.

    Returns:
        The path written to.

    """
    runner.invoke(app, ["init", str(path)])
    return path


def test_add_activity_timing_and_artefacts(tmp_path):
    """Timestamps and used/generated lists are stored.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    result = runner.invoke(
        app,
        [
            "add-activity",
            str(path),
            "reach run",
            "--kind",
            "computation",
            "--id",
            "a1",
            "--started-at",
            "2026-06-13T12:00:00",
            "--ended-at",
            "2026-06-13T15:06:00",
            "--used",
            "config.yaml",
            "--generated",
            "far.npz",
            "--generated",
            "table.csv",
        ],
    )
    assert result.exit_code == 0, result.stderr
    act = load_graph(path).nodes["a1"]
    assert act.properties["started_at"] == "2026-06-13T12:00:00"
    assert act.properties["ended_at"] == "2026-06-13T15:06:00"
    assert act.properties["used"] == ["config.yaml"]
    assert act.properties["generated"] == ["far.npz", "table.csv"]


def test_add_activity_timing_optional(tmp_path):
    """Without timing flags the timestamps stay None and lists empty.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    runner.invoke(app, ["add-activity", str(path), "x", "--kind", "other", "--id", "a1"])
    act = load_graph(path).nodes["a1"]
    assert act.properties["started_at"] is None
    assert act.properties["ended_at"] is None
    assert act.properties["used"] == []
    assert act.properties["generated"] == []


def test_add_activity_bad_timestamp(tmp_path):
    """A non-ISO timestamp exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    result = runner.invoke(
        app,
        ["add-activity", str(path), "x", "--kind", "other", "--started-at", "yesterday"],
    )
    assert result.exit_code != 0
