"""Tests for the ``claimkit`` CLI commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from claimkit.cli.main import app
from claimkit.core import (
    Claim,
    Evidence,
    EvidenceKind,
    NodeType,
    ProvenanceGraph,
    ProvenancePredicate,
    ProvenanceRelation,
)
from claimkit.persistence import load_graph, save_graph

runner = CliRunner()


def _graph_file(path, *, supported: bool = True):
    """Write a graph with one claim and one linked piece of evidence.

    Args:
        path: Destination graph file path.
        supported: If True the evidence supports the claim; else it refutes it.

    Returns:
        The path written to.

    """
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1"))
    g.add_evidence(Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="r", id="e1"))
    g.add_relation(
        ProvenanceRelation(
            subject_type=NodeType.CLAIM,
            subject_id="c1",
            predicate=ProvenancePredicate.SUPPORTED_BY if supported else ProvenancePredicate.REFUTED_BY,
            object_type=NodeType.EVIDENCE,
            object_id="e1",
            id="edge-1",
        )
    )
    save_graph(g, path)
    return path


def test_validate_human_output(tmp_path):
    """Validate prints one status line per claim.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path / "g.json")
    result = runner.invoke(app, ["validate", str(path)])
    assert result.exit_code == 0
    assert "c1: valid — supported by 1 piece(s) of evidence" in result.stdout


def test_validate_json_output(tmp_path):
    """Validate --json emits a JSON object keyed by claim id.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path / "g.json", supported=False)
    result = runner.invoke(app, ["validate", str(path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["c1"]["status"] == "invalid"
    assert payload["c1"]["refuting"] == ["e1"]


def test_validate_does_not_mutate_without_apply(tmp_path):
    """Without --apply the stored claim status is untouched.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path / "g.json")
    runner.invoke(app, ["validate", str(path)])
    assert load_graph(path).claims["c1"].status.value == "unresolved"


def test_validate_apply_persists_status(tmp_path):
    """--apply writes resolved statuses back to the file.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path / "g.json")
    result = runner.invoke(app, ["validate", str(path), "--apply"])
    assert result.exit_code == 0
    assert load_graph(path).claims["c1"].status.value == "valid"


def test_validate_missing_file(tmp_path):
    """A missing input file exits non-zero with a message.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["validate", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
    assert "No such file" in result.stderr


def test_report_stdout(tmp_path):
    """Report prints Markdown to stdout.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path / "g.json")
    result = runner.invoke(app, ["report", str(path)])
    assert result.exit_code == 0
    assert "# Provenance report" in result.stdout
    assert "## Claim `c1`" in result.stdout


def test_report_to_file(tmp_path):
    """Report -o writes Markdown to a file.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path / "g.json")
    out = tmp_path / "out" / "report.md"
    result = runner.invoke(app, ["report", str(path), "-o", str(out)])
    assert result.exit_code == 0
    assert out.read_text(encoding="utf-8").startswith("# Provenance report")


def test_report_missing_file(tmp_path):
    """A missing input file exits non-zero with a message.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["report", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
    assert "No such file" in result.stderr
