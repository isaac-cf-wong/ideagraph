"""Tests for the ``ideagraph digest`` command and ``add-evidence --auto-digest``."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.core.staleness import hash_file
from ideagraph.kg.persistence import load_graph

runner = CliRunner()


def test_digest_prints_hash(tmp_path):
    """Digest prints the sha256 of a file.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    f = tmp_path / "artefact.bin"
    f.write_bytes(b"hello provenance")
    result = runner.invoke(app, ["digest", str(f)])
    assert result.exit_code == 0
    assert result.stdout.strip() == hash_file(f)


def test_digest_missing_file(tmp_path):
    """Digest on a missing file exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["digest", str(tmp_path / "nope.bin")])
    assert result.exit_code == 1
    assert "No such file" in result.stderr


def test_add_evidence_auto_digest(tmp_path):
    """--auto-digest hashes the reference path and stores it on the evidence.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    artefact = tmp_path / "fig.npz"
    artefact.write_bytes(b"data")
    graph_path = tmp_path / "g.json"
    runner.invoke(app, ["init", str(graph_path)])
    runner.invoke(app, ["add-claim", str(graph_path), "A", "--id", "c1"])
    result = runner.invoke(
        app,
        [
            "add-evidence",
            str(graph_path),
            "c1",
            "--kind",
            "figure",
            "--reference",
            str(artefact),
            "--id",
            "e1",
            "--auto-digest",
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert load_graph(graph_path).nodes["e1"].properties["digest"] == hash_file(artefact)


def test_auto_digest_conflicts_with_digest(tmp_path):
    """Passing both --digest and --auto-digest exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    artefact = tmp_path / "fig.npz"
    artefact.write_bytes(b"data")
    graph_path = tmp_path / "g.json"
    runner.invoke(app, ["init", str(graph_path)])
    runner.invoke(app, ["add-claim", str(graph_path), "A", "--id", "c1"])
    result = runner.invoke(
        app,
        [
            "add-evidence",
            str(graph_path),
            "c1",
            "--kind",
            "figure",
            "--reference",
            str(artefact),
            "--digest",
            "sha256:aa",
            "--auto-digest",
        ],
    )
    assert result.exit_code == 1
    assert "not both" in result.stderr


def test_auto_digest_missing_reference_file(tmp_path):
    """--auto-digest with a non-file reference exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    graph_path = tmp_path / "g.json"
    runner.invoke(app, ["init", str(graph_path)])
    runner.invoke(app, ["add-claim", str(graph_path), "A", "--id", "c1"])
    result = runner.invoke(
        app,
        [
            "add-evidence",
            str(graph_path),
            "c1",
            "--kind",
            "data",
            "--reference",
            "run-42",
            "--auto-digest",
        ],
    )
    assert result.exit_code == 1
    assert "no such file" in result.stderr.lower()
