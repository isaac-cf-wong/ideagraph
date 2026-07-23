"""Human-readable provenance reports over a generic knowledge graph.

This module turns a research-profile :class:`~ideagraph.kg.graph.KnowledgeGraph`
into prose a researcher can read: for a claim it shows the statement text, its
stored status, and the evidence that supports or refutes it, followed by a
whole-graph summary. It is pure presentation — it does not mutate the graph or
re-derive validation logic. The split of evidence into supporting and refuting
reuses :func:`ideagraph.kg.profiles.research_ops.validate_node`, so the report
and the validation engine can never disagree about which evidence backs a claim.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from ideagraph.kg.profiles.research import ASSERTION_TYPES
from ideagraph.kg.profiles.research_ops import (
    INVALID,
    NEEDS_REVIEW,
    STALE,
    UNRESOLVED,
    VALID,
    validate_node,
)

if TYPE_CHECKING:
    from ideagraph.kg.graph import KnowledgeGraph
    from ideagraph.kg.node import Node

#: Status tokens in the order they appear in the report's summary line.
_STATUS_ORDER = (UNRESOLVED, VALID, STALE, INVALID, NEEDS_REVIEW)


def _format_evidence(node: Node) -> str:
    """Render one evidence node as a Markdown list item.

    Args:
        node: The evidence node to render.

    Returns:
        A single-line Markdown bullet describing the evidence.

    """
    kind = str(node.properties.get("kind", "other"))
    reference = str(node.properties.get("reference", ""))
    parts = [f"`{kind}`", reference]
    if node.text:
        parts.append(f"— {node.text}")
    digest = node.properties.get("digest")
    if digest is not None:
        parts.append(f"(digest `{digest}`)")
    return "- " + " ".join(parts)


def render_node_report(graph: KnowledgeGraph, node_id: str) -> str:
    """Render a Markdown report for a single assertion node.

    Args:
        graph: The graph holding the node and its evidence.
        node_id: The id of the node to report on.

    Returns:
        A Markdown string.

    Raises:
        KeyError: If ``node_id`` is not held by the graph.

    """
    node = graph.nodes[node_id]
    result = validate_node(graph, node_id)
    status = str(node.properties.get("status", UNRESOLVED))

    lines = [
        f"## {node.type.title()} `{node.id}`",
        "",
        f"> {node.text}",
        "",
        f"- **Status:** {status}",
    ]
    if node.tags:
        lines.append(f"- **Tags:** {', '.join(node.tags)}")
    lines.append(f"- **Created:** {node.created_at.isoformat()}")
    lines.append(f"- **Updated:** {node.updated_at.isoformat()}")
    lines.append("")

    supporting = [graph.nodes[eid] for eid in result.supporting]
    refuting = [graph.nodes[eid] for eid in result.refuting]

    lines.append(f"### Supporting evidence ({len(supporting)})")
    lines.extend([_format_evidence(e) for e in supporting] if supporting else ["_None._"])
    lines.append("")
    lines.append(f"### Refuting evidence ({len(refuting)})")
    lines.extend([_format_evidence(e) for e in refuting] if refuting else ["_None._"])
    lines.append("")
    lines.append(f"**Validation:** {result.status} — {result.reason}")

    return "\n".join(lines)


def render_report(graph: KnowledgeGraph) -> str:
    """Render a Markdown report for every assertion in the graph.

    Assertions are the statement types that carry a validation status
    (claim / finding / result); background, methods, and the like are not
    reported here.

    Args:
        graph: The graph to report on.

    Returns:
        A Markdown string.

    """
    assertion_ids = [n.id for n in graph.nodes.values() if n.type in ASSERTION_TYPES]
    lines = ["# Provenance report", ""]

    counts = Counter(str(graph.nodes[aid].properties.get("status", UNRESOLVED)) for aid in assertion_ids)
    lines.append(f"{len(assertion_ids)} assertion(s).")
    if counts:
        summary = ", ".join(f"{counts[status]} {status}" for status in _STATUS_ORDER if counts[status])
        lines.append("")
        lines.append(f"Status summary: {summary}.")
    lines.append("")

    for assertion_id in assertion_ids:
        lines.append(render_node_report(graph, assertion_id))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
