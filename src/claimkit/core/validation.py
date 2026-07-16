"""Resolving a claim's :class:`~claimkit.core.claim.ClaimStatus` from evidence.

Validation answers: *given the evidence currently linked to a claim, is the
claim supported?* It reads the ``SUPPORTED_BY`` and ``REFUTED_BY`` provenance
edges leaving the claim and derives a status from them:

* no supporting or refuting evidence -> ``UNRESOLVED``
* only supporting evidence -> ``VALID``
* only refuting evidence -> ``INVALID``
* both supporting and refuting evidence -> ``NEEDS_REVIEW`` (a human must
  adjudicate the conflict)

The **edge predicate** is the single source of truth for how a piece of evidence
bears on a claim. The :attr:`~claimkit.core.evidence.Evidence.relation` field is
the evidence's own intrinsic stance and is deliberately *not* consulted here, so
the two are never double-counted; a piece of evidence may support one claim and
be merely contextual to another, and only the edge records that per-claim
relationship.

Staleness (an artefact drifting out from under previously-validated evidence) is
orthogonal to this relation-based check and is handled in
:mod:`claimkit.core.staleness`; callers that want both decide the precedence.
Every result carries a machine-readable status plus the evidence ids and a
human-readable reason, so an agent can determine *why* a claim landed where it
did.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from claimkit.core.claim import ClaimStatus
from claimkit.core.graph import ProvenanceGraph
from claimkit.core.provenance import NodeType, ProvenancePredicate


@dataclass
class ValidationResult:
    """The outcome of validating a single claim against its evidence.

    Attributes:
        claim_id: The id of the validated claim.
        status: The resolved status.
        supporting: Ids of evidence linked by a ``SUPPORTED_BY`` edge.
        refuting: Ids of evidence linked by a ``REFUTED_BY`` edge.
        reason: A human-readable explanation of how the status was reached.
    """

    claim_id: str
    status: ClaimStatus
    supporting: list[str] = field(default_factory=list)
    refuting: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise the result to a JSON-compatible dictionary.

        Returns:
            A dictionary representation of the result.

        """
        return {
            "claim_id": self.claim_id,
            "status": self.status.value,
            "supporting": list(self.supporting),
            "refuting": list(self.refuting),
            "reason": self.reason,
        }


def validate_claim(graph: ProvenanceGraph, claim_id: str) -> ValidationResult:
    """Resolve a claim's status from its supporting and refuting evidence.

    Only evidence held by the graph is counted; edges pointing at evidence the
    graph does not hold are skipped. This function is pure: it does not mutate
    the claim.

    Args:
        graph: The provenance graph holding the claim and its evidence.
        claim_id: The id of the claim to validate.

    Returns:
        The validation result.

    Raises:
        KeyError: If ``claim_id`` is not held by the graph.

    """
    if claim_id not in graph.claims:
        raise KeyError(claim_id)

    supporting: list[str] = []
    refuting: list[str] = []
    for edge in graph.outgoing(claim_id):
        if edge.object_type is not NodeType.EVIDENCE or edge.object_id not in graph.evidence:
            continue
        if edge.predicate is ProvenancePredicate.SUPPORTED_BY:
            supporting.append(edge.object_id)
        elif edge.predicate is ProvenancePredicate.REFUTED_BY:
            refuting.append(edge.object_id)

    if not supporting and not refuting:
        status = ClaimStatus.UNRESOLVED
        reason = "no supporting or refuting evidence linked"
    elif supporting and refuting:
        status = ClaimStatus.NEEDS_REVIEW
        reason = f"conflicting evidence: {len(supporting)} supporting, {len(refuting)} refuting"
    elif refuting:
        status = ClaimStatus.INVALID
        reason = f"refuted by {len(refuting)} piece(s) of evidence"
    else:
        status = ClaimStatus.VALID
        reason = f"supported by {len(supporting)} piece(s) of evidence"

    return ValidationResult(
        claim_id=claim_id,
        status=status,
        supporting=supporting,
        refuting=refuting,
        reason=reason,
    )


def validate_all(graph: ProvenanceGraph) -> dict[str, ValidationResult]:
    """Validate every claim in the graph without mutating any of them.

    Args:
        graph: The provenance graph to validate.

    Returns:
        A mapping from claim id to its validation result.

    """
    return {claim_id: validate_claim(graph, claim_id) for claim_id in graph.claims}


def apply_validation(graph: ProvenanceGraph, claim_id: str) -> ValidationResult:
    """Validate a claim and write the resolved status back onto it.

    Args:
        graph: The provenance graph holding the claim.
        claim_id: The id of the claim to validate and update.

    Returns:
        The validation result whose status was applied.

    Raises:
        KeyError: If ``claim_id`` is not held by the graph.

    """
    result = validate_claim(graph, claim_id)
    graph.claims[claim_id].mark(result.status)
    return result


def apply_all(graph: ProvenanceGraph) -> list[ValidationResult]:
    """Validate every claim and write each resolved status back onto it.

    Args:
        graph: The provenance graph to validate and update in place.

    Returns:
        The validation results, one per claim, in claim insertion order.

    """
    results = []
    for claim_id in list(graph.claims):
        results.append(apply_validation(graph, claim_id))
    return results
