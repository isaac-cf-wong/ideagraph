"""Tests for the ``claimkit add-activity`` command."""

from __future__ import annotations

from typer.testing import CliRunner

from claimkit.cli.main import app
from claimkit.persistence import load_graph

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


def test_add_activity_stores_and_prints_id(tmp_path):
    """add-activity stores the activity and prints its id.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    result = runner.invoke(
        app,
        ["add-activity", str(path), "reach run", "--kind", "computation"],
    )
    assert result.exit_code == 0
    act_id = result.stdout.strip()
    graph = load_graph(path)
    act = graph.activities[act_id]
    assert act.label == "reach run"
    assert act.kind.value == "computation"


def test_add_activity_honours_id_description_agent_meta(tmp_path):
    """Explicit id, description, agent, and metadata are stored.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    result = runner.invoke(
        app,
        [
            "add-activity",
            str(path),
            "seed sweep",
            "--kind",
            "analysis",
            "--id",
            "a1",
            "--description",
            "five-seed robustness",
            "--agent",
            "cluster:lyra",
            "--meta",
            "job=1159554",
            "--meta",
            "cluster=lyra",
        ],
    )
    assert result.stdout.strip() == "a1"
    act = load_graph(path).activities["a1"]
    assert act.description == "five-seed robustness"
    assert act.agent == "cluster:lyra"
    assert act.metadata == {"job": "1159554", "cluster": "lyra"}


def test_add_activity_bad_meta(tmp_path):
    """A malformed --meta entry exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    result = runner.invoke(
        app,
        ["add-activity", str(path), "x", "--kind", "other", "--meta", "novalue"],
    )
    assert result.exit_code != 0


def test_add_activity_duplicate_id(tmp_path):
    """Reusing an activity id exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    args = ["add-activity", str(path), "x", "--kind", "other", "--id", "a1"]
    runner.invoke(app, args)
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert "already exists" in result.stderr


def test_add_activity_missing_file(tmp_path):
    """add-activity on a missing file exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(
        app,
        ["add-activity", str(tmp_path / "nope.json"), "x", "--kind", "other"],
    )
    assert result.exit_code == 1
    assert "No such file" in result.stderr
