"""Tests for :mod:`claimkit.reporting`."""

from __future__ import annotations

import pytest

from claimkit.core import (
    Claim,
    ClaimStatus,
    Evidence,
    EvidenceKind,
    NodeType,
    ProvenanceGraph,
    ProvenancePredicate,
    ProvenanceRelation,
)
from claimkit.reporting import render_claim_report, render_report


def _link(claim_id: str, evidence_id: str, predicate: ProvenancePredicate, edge_id: str) -> ProvenanceRelation:
    """Build a claim→evidence edge with the given predicate.

    Args:
        claim_id: Subject claim id.
        evidence_id: Object evidence id.
        predicate: The edge predicate.
        edge_id: The edge id.

    Returns:
        The edge.

    """
    return ProvenanceRelation(
        subject_type=NodeType.CLAIM,
        subject_id=claim_id,
        predicate=predicate,
        object_type=NodeType.EVIDENCE,
        object_id=evidence_id,
        id=edge_id,
    )


def _populated_graph() -> ProvenanceGraph:
    """Build a graph with one valid claim backed by two pieces of evidence.

    Returns:
        The graph.

    """
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="Water boils at 100C at sea level.", id="c1", status=ClaimStatus.VALID, tags=["phys"]))
    g.add_evidence(
        Evidence(
            claim_id="c1",
            kind=EvidenceKind.DATA,
            reference="dataset.csv",
            id="e1",
            description="measured",
            digest="sha256:abc",
        )
    )
    g.add_evidence(Evidence(claim_id="c1", kind=EvidenceKind.LITERATURE, reference="10.1/x", id="e2"))
    g.add_relation(_link("c1", "e1", ProvenancePredicate.SUPPORTED_BY, "edge-1"))
    g.add_relation(_link("c1", "e2", ProvenancePredicate.REFUTED_BY, "edge-2"))
    return g


def test_claim_report_contains_key_fields():
    """A claim report includes statement, status, tags, and evidence."""
    g = _populated_graph()
    report = render_claim_report(g, "c1")
    assert "## Claim `c1`" in report
    assert "> Water boils at 100C at sea level." in report
    assert "**Status:** valid" in report
    assert "**Tags:** phys" in report
    assert "dataset.csv" in report
    assert "`data`" in report
    assert "digest `sha256:abc`" in report
    assert "10.1/x" in report


def test_claim_report_groups_supporting_and_refuting():
    """Evidence is split into supporting and refuting sections."""
    g = _populated_graph()
    report = render_claim_report(g, "c1")
    assert "### Supporting evidence (1)" in report
    assert "### Refuting evidence (1)" in report
    # Conflicting evidence -> validation says NEEDS_REVIEW.
    assert "**Validation:** needs_review" in report


def test_claim_report_without_evidence_shows_none():
    """A claim with no evidence renders 'None' placeholders."""
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1"))
    report = render_claim_report(g, "c1")
    assert "### Supporting evidence (0)" in report
    assert "_None._" in report
    assert "**Validation:** unresolved" in report


def test_claim_report_omits_tags_line_when_empty():
    """The tags line is omitted for a claim with no tags."""
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1"))
    assert "**Tags:**" not in render_claim_report(g, "c1")


def test_claim_report_unknown_id_raises():
    """Reporting on a claim the graph does not hold raises KeyError."""
    g = ProvenanceGraph()
    with pytest.raises(KeyError):
        render_claim_report(g, "missing")


def test_full_report_has_title_and_summary():
    """The full report opens with a title and status summary."""
    g = _populated_graph()
    report = render_report(g)
    assert report.startswith("# Provenance report")
    assert "1 claim(s)." in report
    assert "Status summary: 1 valid." in report
    assert "## Claim `c1`" in report


def test_full_report_covers_all_claims():
    """Every claim appears in the full report."""
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1"))
    g.add_claim(Claim(statement="B", id="c2"))
    report = render_report(g)
    assert "## Claim `c1`" in report
    assert "## Claim `c2`" in report
    assert "2 claim(s)." in report


def test_full_report_empty_graph():
    """A report over an empty graph is well-formed."""
    report = render_report(ProvenanceGraph())
    assert report.startswith("# Provenance report")
    assert "0 claim(s)." in report
