"""Tests for :mod:`claimkit.core.staleness`."""

from __future__ import annotations

import hashlib

from claimkit.core import (
    Claim,
    ClaimStatus,
    Evidence,
    EvidenceKind,
    NodeType,
    ProvenanceGraph,
    ProvenancePredicate,
    ProvenanceRelation,
    compute_digest,
    evidence_changed,
    find_stale_claims,
    find_stale_evidence,
    hash_file,
    mark_stale_claims,
)


def test_compute_digest_is_prefixed_and_correct():
    """compute_digest returns an algorithm-prefixed hex digest."""
    data = b"hello"
    expected = f"sha256:{hashlib.sha256(data).hexdigest()}"
    assert compute_digest(data) == expected


def test_compute_digest_honours_algorithm():
    """A non-default algorithm is reflected in both hash and prefix."""
    data = b"hello"
    result = compute_digest(data, algorithm="sha512")
    assert result == f"sha512:{hashlib.sha512(data).hexdigest()}"


def test_hash_file(tmp_path):
    """hash_file digests the file's bytes.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    p = tmp_path / "artefact.txt"
    p.write_bytes(b"payload")
    assert hash_file(p) == compute_digest(b"payload")


def test_evidence_changed_detects_difference():
    """A recorded digest differing from the current one is a change."""
    ev = Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="r", digest="sha256:aaa")
    assert evidence_changed(ev, "sha256:bbb") is True
    assert evidence_changed(ev, "sha256:aaa") is False


def test_evidence_changed_needs_both_digests():
    """Without a baseline or a current digest, nothing is reported changed."""
    no_baseline = Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="r")
    assert evidence_changed(no_baseline, "sha256:bbb") is False
    with_baseline = Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="r", digest="sha256:aaa")
    assert evidence_changed(with_baseline, None) is False


def _graph_with_supported_claim(digest: str | None):
    """Build a graph with one claim supported by one piece of evidence.

    Args:
        digest: Baseline digest to record on the evidence.

    Returns:
        A tuple of (graph, claim, evidence).

    """
    g = ProvenanceGraph()
    claim = g.add_claim(Claim(statement="A", id="c1", status=ClaimStatus.VALID))
    ev = g.add_evidence(Evidence(claim_id="c1", kind=EvidenceKind.DATA, reference="r", id="e1", digest=digest))
    g.add_relation(
        ProvenanceRelation(
            subject_type=NodeType.CLAIM,
            subject_id="c1",
            predicate=ProvenancePredicate.SUPPORTED_BY,
            object_type=NodeType.EVIDENCE,
            object_id="e1",
            id="edge-1",
        )
    )
    return g, claim, ev


def test_find_stale_evidence():
    """find_stale_evidence returns only the changed evidence."""
    g, _claim, ev = _graph_with_supported_claim("sha256:aaa")
    resolver = {ev.id: "sha256:zzz"}.get
    stale = find_stale_evidence(g, lambda e: resolver(e.id))
    assert stale == [ev]


def test_find_stale_claims_follows_evidence():
    """A claim with changed supporting evidence is reported affected."""
    g, claim, _ev = _graph_with_supported_claim("sha256:aaa")
    affected = find_stale_claims(g, lambda _e: "sha256:zzz")
    assert affected == [claim]


def test_find_stale_claims_unchanged_evidence():
    """A claim whose evidence is unchanged is not reported."""
    g, _claim, _ev = _graph_with_supported_claim("sha256:aaa")
    affected = find_stale_claims(g, lambda _e: "sha256:aaa")
    assert affected == []


def test_mark_stale_claims_flips_valid_to_stale():
    """A valid claim with drifted evidence is marked stale."""
    g, claim, _ev = _graph_with_supported_claim("sha256:aaa")
    changed = mark_stale_claims(g, lambda _e: "sha256:zzz")
    assert changed == [claim]
    assert claim.status is ClaimStatus.STALE


def test_mark_stale_claims_leaves_non_valid_claims():
    """Claims not currently valid are left untouched even if affected."""
    g, claim, _ev = _graph_with_supported_claim("sha256:aaa")
    claim.mark(ClaimStatus.UNRESOLVED)
    changed = mark_stale_claims(g, lambda _e: "sha256:zzz")
    assert changed == []
    assert claim.status is ClaimStatus.UNRESOLVED


def test_mark_stale_claims_noop_when_unchanged():
    """Nothing is marked when no evidence has drifted."""
    g, claim, _ev = _graph_with_supported_claim("sha256:aaa")
    changed = mark_stale_claims(g, lambda _e: "sha256:aaa")
    assert changed == []
    assert claim.status is ClaimStatus.VALID
