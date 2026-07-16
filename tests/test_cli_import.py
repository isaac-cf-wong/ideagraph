"""Tests for the ``claimkit import`` command."""

from __future__ import annotations

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
from claimkit.persistence import load_graph
from claimkit.prov import dumps_prov

runner = CliRunner()


def _prov_file(path):
    """Write a PROV-JSON file for a claim supported by one piece of evidence.

    Args:
        path: Destination PROV-JSON file path.

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
            predicate=ProvenancePredicate.SUPPORTED_BY,
            object_type=NodeType.EVIDENCE,
            object_id="e1",
            id="s1",
        )
    )
    path.write_text(dumps_prov(g), encoding="utf-8")
    return path


def test_import_writes_graph(tmp_path):
    """Import converts PROV-JSON into a loadable claimkit graph.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    src = _prov_file(tmp_path / "prov.json")
    dest = tmp_path / "g.json"
    result = runner.invoke(app, ["import", str(src), str(dest)])
    assert result.exit_code == 0
    graph = load_graph(dest)
    assert graph.claims["c1"].statement == "A"
    assert graph.evidence["e1"].claim_id == "c1"
    assert graph.outgoing("c1")[0].predicate is ProvenancePredicate.SUPPORTED_BY


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
    assert load_graph(dest).claims["c1"].statement == "A"


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
    assert back.claims["c1"].statement == "A"
    assert len(back.evidence) == 1
    assert back.outgoing("c1")[0].predicate is ProvenancePredicate.SUPPORTED_BY
