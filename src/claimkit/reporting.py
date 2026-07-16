"""Human-readable provenance reports rendered as Markdown.

This module turns the machine-readable provenance graph into prose a researcher
can read: for a claim it shows the statement, its current status, and the
evidence that supports or refutes it, followed by a whole-graph summary. It is
pure presentation — it does not mutate the graph or re-derive validation logic.
The classification of evidence into supporting and refuting reuses
:func:`claimkit.core.validation.validate_claim`, so the report and the
validation engine can never disagree about which evidence backs a claim.
"""

from __future__ import annotations

from collections import Counter

from claimkit.core.claim import ClaimStatus
from claimkit.core.evidence import Evidence
from claimkit.core.graph import ProvenanceGraph
from claimkit.core.validation import validate_claim


def _format_evidence(evidence: Evidence) -> str:
    """Render one piece of evidence as a Markdown list item.

    Args:
        evidence: The evidence to render.

    Returns:
        A single-line Markdown bullet describing the evidence.

    """
    parts = [f"`{evidence.kind.value}`", evidence.reference]
    if evidence.description:
        parts.append(f"— {evidence.description}")
    if evidence.digest is not None:
        parts.append(f"(digest `{evidence.digest}`)")
    return "- " + " ".join(parts)


def render_claim_report(graph: ProvenanceGraph, claim_id: str) -> str:
    """Render a Markdown report for a single claim.

    The report shows the claim's statement and stored status, then lists the
    supporting and refuting evidence held by the graph, and closes with the
    validation engine's reason for the derived status.

    Args:
        graph: The provenance graph holding the claim and its evidence.
        claim_id: The id of the claim to report on.

    Returns:
        A Markdown string.

    Raises:
        KeyError: If ``claim_id`` is not held by the graph.

    """
    claim = graph.claims[claim_id]
    result = validate_claim(graph, claim_id)

    lines = [
        f"## Claim `{claim.id}`",
        "",
        f"> {claim.statement}",
        "",
        f"- **Status:** {claim.status.value}",
    ]
    if claim.tags:
        lines.append(f"- **Tags:** {', '.join(claim.tags)}")
    lines.append(f"- **Created:** {claim.created_at.isoformat()}")
    lines.append(f"- **Updated:** {claim.updated_at.isoformat()}")
    lines.append("")

    supporting = [graph.evidence[eid] for eid in result.supporting]
    refuting = [graph.evidence[eid] for eid in result.refuting]

    lines.append(f"### Supporting evidence ({len(supporting)})")
    lines.extend([_format_evidence(e) for e in supporting] if supporting else ["_None._"])
    lines.append("")
    lines.append(f"### Refuting evidence ({len(refuting)})")
    lines.extend([_format_evidence(e) for e in refuting] if refuting else ["_None._"])
    lines.append("")
    lines.append(f"**Validation:** {result.status.value} — {result.reason}")

    return "\n".join(lines)


def render_report(graph: ProvenanceGraph) -> str:
    """Render a Markdown report for every claim in the graph.

    The report opens with a status summary and follows with one section per
    claim, in claim insertion order.

    Args:
        graph: The provenance graph to report on.

    Returns:
        A Markdown string.

    """
    lines = ["# Provenance report", ""]

    counts = Counter(claim.status for claim in graph.claims.values())
    lines.append(f"{len(graph.claims)} claim(s).")
    if counts:
        summary = ", ".join(f"{counts[status]} {status.value}" for status in ClaimStatus if counts[status])
        lines.append("")
        lines.append(f"Status summary: {summary}.")
    lines.append("")

    for claim_id in graph.claims:
        lines.append(render_claim_report(graph, claim_id))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
