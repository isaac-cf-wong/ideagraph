"""Tests for ``--meta-json`` structured metadata on the add-* commands."""

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


def test_add_claim_meta_json_stores_structured_value(tmp_path):
    """--meta-json decodes JSON into the claim metadata.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    result = runner.invoke(
        app,
        [
            "add-claim",
            str(path),
            "R",
            "--id",
            "c1",
            "--meta-json",
            'value={"triangle": {"loud10": 0.0}, "twol": {"loud10": 70.0}}',
        ],
    )
    assert result.exit_code == 0, result.stderr
    node = load_graph(path).nodes["c1"]
    assert node.properties["metadata"]["value"] == {"triangle": {"loud10": 0.0}, "twol": {"loud10": 70.0}}


def test_meta_and_meta_json_merge(tmp_path):
    """--meta strings and --meta-json values combine in one metadata dict.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    runner.invoke(
        app,
        [
            "add-claim",
            str(path),
            "R",
            "--id",
            "c1",
            "--meta",
            "units=ratio",
            "--meta-json",
            "samples=[1, 2, 3]",
        ],
    )
    meta = load_graph(path).nodes["c1"].properties["metadata"]
    assert meta["units"] == "ratio"
    assert meta["samples"] == [1, 2, 3]


def test_add_evidence_and_activity_meta_json(tmp_path):
    """add-evidence and add-activity also accept --meta-json.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    runner.invoke(app, ["add-claim", str(path), "A", "--id", "c1"])
    runner.invoke(
        app,
        ["add-evidence", str(path), "c1", "--kind", "data", "--reference", "r", "--id", "e1", "--meta-json", "n=42"],
    )
    runner.invoke(
        app,
        ["add-activity", str(path), "run", "--kind", "computation", "--id", "a1", "--meta-json", "seeds=[42, 43]"],
    )
    g = load_graph(path)
    assert g.nodes["e1"].properties["metadata"]["n"] == 42
    assert g.nodes["a1"].properties["metadata"]["seeds"] == [42, 43]


def test_invalid_json_exits_nonzero(tmp_path):
    """A malformed --meta-json value exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph(tmp_path / "g.json")
    result = runner.invoke(app, ["add-claim", str(path), "A", "--meta-json", "value={not json}"])
    assert result.exit_code != 0
