"""Tests for ``--meta``/``--status`` on the add-claim and add-evidence commands."""

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


def test_add_claim_status_and_meta(tmp_path):
    """add-claim records an explicit status and KEY=VALUE metadata.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    result = runner.invoke(
        app,
        [
            "add-claim",
            str(path),
            "R = 14.8",
            "--id",
            "c1",
            "--status",
            "valid",
            "--meta",
            "value=14.8",
            "--meta",
            "units=ratio",
        ],
    )
    assert result.exit_code == 0, result.stderr
    node = load_graph(path).nodes["c1"]
    assert node.properties["status"] == "valid"
    assert node.properties["metadata"] == {"value": "14.8", "units": "ratio"}


def test_add_claim_defaults_unresolved_no_meta(tmp_path):
    """Without the flags, a claim is unresolved with empty metadata.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    runner.invoke(app, ["add-claim", str(path), "A", "--id", "c1"])
    node = load_graph(path).nodes["c1"]
    assert node.properties["status"] == "unresolved"
    assert node.properties["metadata"] == {}


def test_add_evidence_meta(tmp_path):
    """add-evidence records KEY=VALUE metadata on the evidence.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    runner.invoke(app, ["add-claim", str(path), "A", "--id", "c1"])
    result = runner.invoke(
        app,
        [
            "add-evidence",
            str(path),
            "c1",
            "--kind",
            "data",
            "--reference",
            "r",
            "--id",
            "e1",
            "--meta",
            "run=1159554",
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert load_graph(path).nodes["e1"].properties["metadata"] == {"run": "1159554"}


def test_bad_meta_exits_nonzero(tmp_path):
    """A malformed --meta entry exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    result = runner.invoke(app, ["add-claim", str(path), "A", "--meta", "novalue"])
    assert result.exit_code != 0
