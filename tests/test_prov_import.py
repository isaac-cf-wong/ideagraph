"""Tests for PROV-JSON import (:func:`claimkit.prov.from_prov`)."""

from __future__ import annotations

from datetime import UTC, datetime

from claimkit.core import (
    Activity,
    ActivityKind,
    Claim,
    ClaimStatus,
    Evidence,
    EvidenceKind,
    EvidenceRelation,
    NodeType,
    ProvenanceGraph,
    ProvenancePredicate,
    ProvenanceRelation,
)
from claimkit.prov import dumps_prov, from_prov, loads_prov, to_prov


def _link(claim_id, evidence_id, predicate, edge_id):
    """Build a claim→evidence edge.

    Args:
        claim_id: Subject claim id.
        evidence_id: Object evidence id.
        predicate: Edge predicate.
        edge_id: Edge id.

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


def test_import_claim_status_and_statement():
    """Claims round-trip their id, statement, and status."""
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1", status=ClaimStatus.VALID))
    restored = from_prov(to_prov(g))
    claim = restored.claims["c1"]
    assert claim.statement == "A"
    assert claim.status is ClaimStatus.VALID


def test_import_evidence_fields():
    """Evidence round-trips kind, reference, and digest."""
    g = ProvenanceGraph()
    g.add_evidence(Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="r", id="e1", digest="sha256:aa"))
    ev = from_prov(to_prov(g)).evidence["e1"]
    assert ev.kind is EvidenceKind.DATA
    assert ev.reference == "r"
    assert ev.digest == "sha256:aa"


def test_import_recovers_claim_id_and_relation_from_edge():
    """Evidence claim_id and relation are recovered from the linking edge."""
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1"))
    g.add_evidence(Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="r", id="e1"))
    g.add_relation(_link("c1", "e1", ProvenancePredicate.REFUTED_BY, "edge-1"))
    ev = from_prov(to_prov(g)).evidence["e1"]
    assert ev.claim_id == "c1"
    assert ev.relation is EvidenceRelation.REFUTES


def test_import_activity_times():
    """Activities recover their label and time interval (kind defaults)."""
    g = ProvenanceGraph()
    g.add_activity(
        Activity(
            kind=ActivityKind.COMPUTATION,
            label="run",
            id="a1",
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            ended_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    act = from_prov(to_prov(g)).activities["a1"]
    assert act.label == "run"
    assert act.started_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert act.ended_at == datetime(2026, 1, 2, tzinfo=UTC)
    # Kind is not carried by PROV; it defaults.
    assert act.kind is ActivityKind.OTHER


def test_import_rebuilds_all_edge_types():
    """Every PROV relation container maps back to the right predicate."""
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1"))
    g.add_evidence(Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="r", id="e1"))
    g.add_activity(Activity(kind=ActivityKind.COMPUTATION, label="run", id="a1"))
    edges = [
        _link("c1", "e1", ProvenancePredicate.SUPPORTED_BY, "s1"),
        ProvenanceRelation(
            subject_type=NodeType.EVIDENCE,
            subject_id="e1",
            predicate=ProvenancePredicate.GENERATED_BY,
            object_type=NodeType.ACTIVITY,
            object_id="a1",
            id="g1",
        ),
        ProvenanceRelation(
            subject_type=NodeType.ACTIVITY,
            subject_id="a1",
            predicate=ProvenancePredicate.USED,
            object_type=NodeType.ARTEFACT,
            object_id="data-1",
            id="u1",
        ),
        ProvenanceRelation(
            subject_type=NodeType.CLAIM,
            subject_id="c1",
            predicate=ProvenancePredicate.ATTRIBUTED_TO,
            object_type=NodeType.AGENT,
            object_id="alice",
            id="at1",
        ),
        ProvenanceRelation(
            subject_type=NodeType.ARTEFACT,
            subject_id="data-1",
            predicate=ProvenancePredicate.DERIVED_FROM,
            object_type=NodeType.ARTEFACT,
            object_id="raw-1",
            id="d1",
        ),
    ]
    for edge in edges:
        g.add_relation(edge)

    restored = from_prov(to_prov(g))
    got = {eid: (e.subject_id, e.predicate, e.object_id) for eid, e in restored.relations.items()}
    assert got == {
        "s1": ("c1", ProvenancePredicate.SUPPORTED_BY, "e1"),
        "g1": ("e1", ProvenancePredicate.GENERATED_BY, "a1"),
        "u1": ("a1", ProvenancePredicate.USED, "data-1"),
        "at1": ("c1", ProvenancePredicate.ATTRIBUTED_TO, "alice"),
        "d1": ("data-1", ProvenancePredicate.DERIVED_FROM, "raw-1"),
    }


def test_import_endpoint_types_are_recovered():
    """Edge endpoint NodeTypes are inferred from the PROV collections."""
    g = ProvenanceGraph()
    g.add_activity(Activity(kind=ActivityKind.COMPUTATION, label="run", id="a1"))
    g.add_relation(
        ProvenanceRelation(
            subject_type=NodeType.ACTIVITY,
            subject_id="a1",
            predicate=ProvenancePredicate.USED,
            object_type=NodeType.ARTEFACT,
            object_id="data-1",
            id="u1",
        )
    )
    edge = from_prov(to_prov(g)).relations["u1"]
    assert edge.subject_type is NodeType.ACTIVITY
    assert edge.object_type is NodeType.ARTEFACT


def test_loads_prov_matches_from_prov():
    """loads_prov and from_prov agree, compared via their PROV projection."""
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1"))
    assert to_prov(loads_prov(dumps_prov(g))) == to_prov(from_prov(to_prov(g)))


def test_import_empty_document():
    """An empty PROV document yields an empty graph."""
    assert from_prov({"prefix": {}}) == ProvenanceGraph()


def test_reexport_is_stable():
    """Export -> import -> export reproduces the PROV document (lossy-stable)."""
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1", status=ClaimStatus.VALID))
    g.add_evidence(
        Evidence(
            claim_id="c1",
            kind=EvidenceKind.DATA,
            reference="r",
            id="e1",
            digest="sha256:aa",
            relation=EvidenceRelation.SUPPORTS,
        )
    )
    g.add_relation(_link("c1", "e1", ProvenancePredicate.SUPPORTED_BY, "s1"))
    doc = to_prov(g)
    assert to_prov(from_prov(doc)) == doc


def test_import_preserves_representable_fields():
    """Representable claim/evidence fields survive an import."""
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A", id="c1", status=ClaimStatus.VALID))
    g.add_evidence(Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="r", id="e1", digest="sha256:aa"))
    g.add_relation(_link("c1", "e1", ProvenancePredicate.SUPPORTED_BY, "s1"))
    restored = from_prov(to_prov(g))
    assert restored.claims["c1"].statement == "A"
    assert restored.claims["c1"].status is ClaimStatus.VALID
    assert restored.evidence["e1"].kind is EvidenceKind.DATA
    assert restored.evidence["e1"].claim_id == "c1"
