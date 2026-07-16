"""Tests for :mod:`claimkit.core.validation`."""

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
    ValidationResult,
    apply_all,
    apply_validation,
    validate_all,
    validate_claim,
)


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


def _graph_with_claim() -> ProvenanceGraph:
    """Build a graph holding a single unresolved claim ``c1``.

    Returns:
        The graph.

    """
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1"))
    return g


def _add_evidence(g: ProvenanceGraph, evidence_id: str) -> None:
    """Add a data evidence node with the given id.

    Args:
        g: The graph to add to.
        evidence_id: The evidence id.

    """
    g.add_evidence(Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="r", id=evidence_id))


def test_unresolved_without_evidence():
    """A claim with no linked evidence is unresolved."""
    g = _graph_with_claim()
    result = validate_claim(g, "c1")
    assert result.status is ClaimStatus.UNRESOLVED
    assert result.supporting == []
    assert result.refuting == []
    assert "no supporting or refuting" in result.reason


def test_valid_with_supporting_evidence():
    """Only supporting evidence yields VALID."""
    g = _graph_with_claim()
    _add_evidence(g, "e1")
    _add_evidence(g, "e2")
    g.add_relation(_link("c1", "e1", ProvenancePredicate.SUPPORTED_BY, "edge-1"))
    g.add_relation(_link("c1", "e2", ProvenancePredicate.SUPPORTED_BY, "edge-2"))
    result = validate_claim(g, "c1")
    assert result.status is ClaimStatus.VALID
    assert result.supporting == ["e1", "e2"]
    assert result.refuting == []


def test_invalid_with_refuting_evidence():
    """Only refuting evidence yields INVALID."""
    g = _graph_with_claim()
    _add_evidence(g, "e1")
    g.add_relation(_link("c1", "e1", ProvenancePredicate.REFUTED_BY, "edge-1"))
    result = validate_claim(g, "c1")
    assert result.status is ClaimStatus.INVALID
    assert result.refuting == ["e1"]


def test_needs_review_with_conflicting_evidence():
    """Both supporting and refuting evidence yields NEEDS_REVIEW."""
    g = _graph_with_claim()
    _add_evidence(g, "e1")
    _add_evidence(g, "e2")
    g.add_relation(_link("c1", "e1", ProvenancePredicate.SUPPORTED_BY, "edge-1"))
    g.add_relation(_link("c1", "e2", ProvenancePredicate.REFUTED_BY, "edge-2"))
    result = validate_claim(g, "c1")
    assert result.status is ClaimStatus.NEEDS_REVIEW
    assert result.supporting == ["e1"]
    assert result.refuting == ["e2"]
    assert "conflicting" in result.reason


def test_other_predicates_are_ignored():
    """Non supports/refutes edges do not affect validation."""
    g = _graph_with_claim()
    g.add_relation(
        ProvenanceRelation(
            subject_type=NodeType.CLAIM,
            subject_id="c1",
            predicate=ProvenancePredicate.REVIEWED_BY,
            object_type=NodeType.AGENT,
            object_id="agent-1",
            id="edge-1",
        )
    )
    assert validate_claim(g, "c1").status is ClaimStatus.UNRESOLVED


def test_dangling_evidence_is_ignored():
    """Edges pointing at evidence the graph does not hold are skipped."""
    g = _graph_with_claim()
    g.add_relation(_link("c1", "missing", ProvenancePredicate.SUPPORTED_BY, "edge-1"))
    assert validate_claim(g, "c1").status is ClaimStatus.UNRESOLVED


def test_validate_claim_does_not_mutate():
    """validate_claim leaves the claim's status untouched."""
    g = _graph_with_claim()
    _add_evidence(g, "e1")
    g.add_relation(_link("c1", "e1", ProvenancePredicate.SUPPORTED_BY, "edge-1"))
    validate_claim(g, "c1")
    assert g.claims["c1"].status is ClaimStatus.UNRESOLVED


def test_validate_claim_unknown_id_raises():
    """Validating a claim the graph does not hold raises KeyError."""
    g = ProvenanceGraph()
    with pytest.raises(KeyError):
        validate_claim(g, "missing")


def test_apply_validation_writes_status_back():
    """apply_validation marks the claim with the resolved status."""
    g = _graph_with_claim()
    _add_evidence(g, "e1")
    g.add_relation(_link("c1", "e1", ProvenancePredicate.SUPPORTED_BY, "edge-1"))
    result = apply_validation(g, "c1")
    assert result.status is ClaimStatus.VALID
    assert g.claims["c1"].status is ClaimStatus.VALID


def test_validate_all_covers_every_claim():
    """validate_all returns a result per claim without mutating."""
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1"))
    g.add_claim(Claim(statement="B", id="c2"))
    results = validate_all(g)
    assert set(results) == {"c1", "c2"}
    assert all(r.status is ClaimStatus.UNRESOLVED for r in results.values())
    assert g.claims["c1"].status is ClaimStatus.UNRESOLVED


def test_apply_all_marks_every_claim():
    """apply_all writes back the status of every claim."""
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1"))
    _add_evidence(g, "e1")
    g.add_relation(_link("c1", "e1", ProvenancePredicate.SUPPORTED_BY, "edge-1"))
    g.add_claim(Claim(statement="B", id="c2"))
    results = apply_all(g)
    assert len(results) == 2
    assert g.claims["c1"].status is ClaimStatus.VALID
    assert g.claims["c2"].status is ClaimStatus.UNRESOLVED


def test_result_to_dict():
    """ValidationResult serialises to stable tokens."""
    result = ValidationResult(
        claim_id="c1",
        status=ClaimStatus.VALID,
        supporting=["e1"],
        refuting=[],
        reason="supported by 1 piece(s) of evidence",
    )
    assert result.to_dict() == {
        "claim_id": "c1",
        "status": "valid",
        "supporting": ["e1"],
        "refuting": [],
        "reason": "supported by 1 piece(s) of evidence",
    }
