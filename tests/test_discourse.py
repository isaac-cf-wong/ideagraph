"""Tests for discourse predicates and assertion-scoped coverage/validation."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph import (
    Evidence,
    EvidenceKind,
    NodeType,
    ProvenanceGraph,
    ProvenancePredicate,
    ProvenanceRelation,
    Statement,
    StatementType,
    coverage,
    validate_all,
)
from ideagraph.cli.main import app
from ideagraph.persistence import save_graph

runner = CliRunner()


def test_discourse_predicate_available():
    """The discourse predicates exist and carry stable tokens."""
    assert ProvenancePredicate.ELABORATES.value == "elaborates"
    assert {"contrasts", "depends_on", "cites", "motivates"} <= {p.value for p in ProvenancePredicate}


def test_add_relation_discourse_edge(tmp_path):
    """add-relation records a statement->statement discourse edge.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    runner.invoke(app, ["init", str(path)])
    runner.invoke(app, ["add-statement", str(path), "Background.", "--type", "background", "--id", "b1"])
    runner.invoke(app, ["add-claim", str(path), "Our claim.", "--id", "c1"])
    r = runner.invoke(app, ["add-relation", str(path), "c1", "b1", "--predicate", "elaborates"])
    assert r.exit_code == 0, r.stderr
    from ideagraph.kg.persistence import load_graph as kg_load_graph

    edge = kg_load_graph(path).outgoing("c1")[0]
    assert edge.type == "elaborates"


def _graph_mixed():
    """Claim (supported), finding (unsupported), background (unsupported, exempt)."""
    g = ProvenanceGraph()
    g.add_statement(Statement(statement="claim", id="c1", type=StatementType.CLAIM))
    g.add_statement(Statement(statement="finding", id="f1", type=StatementType.FINDING))
    g.add_statement(Statement(statement="background", id="b1", type=StatementType.BACKGROUND))
    ev = Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="run-1")
    g.add_evidence(ev)
    g.add_relation(
        ProvenanceRelation(
            subject_type=NodeType.CLAIM,
            subject_id="c1",
            predicate=ProvenancePredicate.SUPPORTED_BY,
            object_type=NodeType.EVIDENCE,
            object_id=ev.id,
        )
    )
    return g


def test_coverage_scopes_to_assertion_types():
    """Coverage covers claim + finding, but exempts background."""
    cov = coverage(_graph_mixed())
    assert set(cov) == {"c1", "f1"}  # background exempt
    assert cov["c1"].category == "own"
    assert cov["f1"].category == "unsupported"


def test_validate_scopes_to_assertion_types():
    """validate_all validates assertion statements, not background."""
    verdicts = validate_all(_graph_mixed())
    assert set(verdicts) == {"c1", "f1"}
    assert verdicts["c1"].status.value == "valid"


def test_coverage_cli_strict_flags_unsupported_finding(tmp_path):
    """Coverage --strict flags an unsupported finding.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    save_graph(_graph_mixed(), path)
    result = runner.invoke(app, ["coverage", str(path), "--strict"])
    assert result.exit_code == 1
    assert "f1" in result.stderr
