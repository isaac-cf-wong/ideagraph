"""Detecting when claims go stale because their evidence has changed.

Every piece of :class:`~claimkit.core.evidence.Evidence` may carry a ``digest``:
a content hash of the artefact captured at the time the evidence was recorded. A
claim is *stale* when the current content of a supporting artefact no longer
matches that recorded digest — the evidence the claim rests on has moved out
from under it.

This module provides the primitives for that check: helpers to compute a
digest, a comparison against the recorded value, and functions that sweep a
:class:`~claimkit.core.graph.ProvenanceGraph` to report — and optionally mark —
the claims whose evidence has drifted. The current content of an artefact is
obtained through a caller-supplied resolver, so this module stays independent of
where artefacts actually live (filesystem, object store, database, ...).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from claimkit.core.claim import Claim, ClaimStatus
from claimkit.core.evidence import Evidence
from claimkit.core.graph import ProvenanceGraph

#: A callable that returns the current digest of an artefact backing a piece of
#: evidence, or ``None`` if the artefact cannot be resolved. The returned string
#: is compared verbatim against :attr:`~claimkit.core.evidence.Evidence.digest`.
DigestResolver = Callable[[Evidence], str | None]


def compute_digest(data: bytes, *, algorithm: str = "sha256") -> str:
    """Compute a prefixed content digest of ``data``.

    Args:
        data: The bytes to hash.
        algorithm: A hash algorithm name understood by :mod:`hashlib`.

    Returns:
        The digest as ``"<algorithm>:<hexdigest>"``, e.g. ``"sha256:ab12..."``.
        The prefix keeps the algorithm attached to the value so a later
        comparison cannot silently mix algorithms.

    """
    digest = hashlib.new(algorithm, data).hexdigest()
    return f"{algorithm}:{digest}"


def hash_file(path: str | Path, *, algorithm: str = "sha256") -> str:
    """Compute the prefixed content digest of a file.

    Args:
        path: Path to the file to hash.
        algorithm: A hash algorithm name understood by :mod:`hashlib`.

    Returns:
        The digest as ``"<algorithm>:<hexdigest>"``.

    """
    return compute_digest(Path(path).read_bytes(), algorithm=algorithm)


def evidence_changed(evidence: Evidence, current_digest: str | None) -> bool:
    """Report whether an artefact has changed since the evidence was recorded.

    A change can only be detected when the evidence carries a baseline digest
    and the current digest is known. If either is absent there is no baseline to
    compare against, so the artefact is *not* reported as changed.

    Args:
        evidence: The evidence holding the recorded (baseline) digest.
        current_digest: The artefact's current digest, or ``None`` if unknown.

    Returns:
        ``True`` if both digests are present and differ; ``False`` otherwise.

    """
    if evidence.digest is None or current_digest is None:
        return False
    return evidence.digest != current_digest


def find_stale_evidence(graph: ProvenanceGraph, resolver: DigestResolver) -> list[Evidence]:
    """Return the evidence in ``graph`` whose artefact has changed.

    Args:
        graph: The provenance graph to sweep.
        resolver: Resolves the current digest of an artefact backing a piece of
            evidence (or ``None`` if it cannot be resolved).

    Returns:
        The evidence whose current digest differs from its recorded digest.

    """
    return [ev for ev in graph.evidence.values() if evidence_changed(ev, resolver(ev))]


def find_stale_claims(graph: ProvenanceGraph, resolver: DigestResolver) -> list[Claim]:
    """Return the claims in ``graph`` with at least one changed piece of evidence.

    A claim is considered affected when any evidence linked to it by a
    supports/refutes edge (and held by the graph) has a changed artefact.

    Args:
        graph: The provenance graph to sweep.
        resolver: Resolves the current digest of an artefact backing a piece of
            evidence (or ``None`` if it cannot be resolved).

    Returns:
        The affected claims, in the graph's claim insertion order.

    """
    return [
        claim
        for claim in graph.claims.values()
        if any(evidence_changed(ev, resolver(ev)) for ev in graph.evidence_for(claim.id))
    ]


def mark_stale_claims(graph: ProvenanceGraph, resolver: DigestResolver) -> list[Claim]:
    """Flip affected ``VALID`` claims to ``STALE`` and return those changed.

    Only claims currently marked :attr:`~claimkit.core.claim.ClaimStatus.VALID`
    are transitioned; claims in other states are left untouched, since staleness
    speaks only to previously-validated claims whose evidence has since drifted.

    Args:
        graph: The provenance graph to update in place.
        resolver: Resolves the current digest of an artefact backing a piece of
            evidence (or ``None`` if it cannot be resolved).

    Returns:
        The claims whose status was changed to
        :attr:`~claimkit.core.claim.ClaimStatus.STALE`.

    """
    changed: list[Claim] = []
    for claim in find_stale_claims(graph, resolver):
        if claim.status is ClaimStatus.VALID:
            claim.mark(ClaimStatus.STALE)
            changed.append(claim)
    return changed
