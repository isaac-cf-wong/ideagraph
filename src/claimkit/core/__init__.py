"""Core abstractions for claimkit.

This package holds the primary domain model. The first citizen is the
:class:`~claimkit.core.claim.Claim`, the central abstraction of the framework.
"""

from __future__ import annotations

from claimkit.core.activity import Activity, ActivityKind
from claimkit.core.claim import Claim, ClaimStatus
from claimkit.core.evidence import Evidence, EvidenceKind, EvidenceRelation
from claimkit.core.graph import ProvenanceGraph
from claimkit.core.provenance import NodeType, ProvenancePredicate, ProvenanceRelation
from claimkit.core.staleness import (
    DigestResolver,
    compute_digest,
    evidence_changed,
    find_stale_claims,
    find_stale_evidence,
    hash_file,
    mark_stale_claims,
)

__all__ = [
    "Activity",
    "ActivityKind",
    "Claim",
    "ClaimStatus",
    "DigestResolver",
    "Evidence",
    "EvidenceKind",
    "EvidenceRelation",
    "NodeType",
    "ProvenanceGraph",
    "ProvenancePredicate",
    "ProvenanceRelation",
    "compute_digest",
    "evidence_changed",
    "find_stale_claims",
    "find_stale_evidence",
    "hash_file",
    "mark_stale_claims",
]
