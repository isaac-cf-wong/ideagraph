"""Convert legacy provenance-graph JSON into a generic KnowledgeGraph.

The old core serialised a graph as five typed collections
(``statements`` / ``evidence`` / ``activities`` / ``relations`` /
``cross_references``). This module maps that shape onto the generic
research-profile knowledge graph so existing files keep loading after the
core rewrite:

* each statement -> a node whose ``type`` is its rhetorical type; its text is
  the statement text; status/order/section/source_digest move into properties;
* each evidence -> an ``evidence`` node (kind/reference/relation/digest in
  properties; description as text);
* each activity -> an ``activity`` node (label as text; kind/agent/times/
  used/generated in properties);
* each relation and cross reference -> an edge typed by its predicate.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ideagraph.kg.edge import Edge
from ideagraph.kg.graph import KnowledgeGraph
from ideagraph.kg.node import Node


def _dt(value: str | None) -> datetime | None:
    """Parse an ISO timestamp, or None.

    Args:
        value: An ISO 8601 string or None.

    Returns:
        The parsed datetime, or None.

    """
    return datetime.fromisoformat(value) if value else None


def _timestamps(item: dict[str, Any]) -> dict[str, datetime]:
    """Extract created/updated timestamps from a legacy item.

    Args:
        item: A legacy node dict.

    Returns:
        Keyword args (``created_at``/``updated_at``) for a Node, omitting any
        that are absent.

    """
    out: dict[str, datetime] = {}
    created = _dt(item.get("created_at"))
    updated = _dt(item.get("updated_at")) or created
    if created is not None:
        out["created_at"] = created
    if updated is not None:
        out["updated_at"] = updated
    return out


def _statement_node(item: dict[str, Any]) -> Node:
    """Map a legacy statement to a node."""
    properties = {
        "status": item.get("status", "unresolved"),
        "order": item.get("order", 0),
        "section": item.get("section"),
        "source_digest": item.get("source_digest"),
    }
    return Node(
        type=item.get("type", "claim"),
        text=item.get("statement", ""),
        id=item["id"],
        tags=list(item.get("tags", [])),
        properties=properties,
        **_timestamps(item),
    )


def _evidence_node(item: dict[str, Any]) -> Node:
    """Map a legacy evidence record to an evidence node."""
    properties = {
        "kind": item["kind"],
        "reference": item["reference"],
        "relation": item.get("relation", "supports"),
        "digest": item.get("digest"),
    }
    return Node(
        type="evidence",
        text=item.get("description", ""),
        id=item["id"],
        properties=properties,
        **_timestamps(item),
    )


def _activity_node(item: dict[str, Any]) -> Node:
    """Map a legacy activity record to an activity node."""
    properties = {
        "kind": item["kind"],
        "label": item["label"],
        "description": item.get("description", ""),
        "agent": item.get("agent"),
        "started_at": item.get("started_at"),
        "ended_at": item.get("ended_at"),
        "used": list(item.get("used", [])),
        "generated": list(item.get("generated", [])),
    }
    return Node(
        type="activity",
        text=item["label"],
        id=item["id"],
        properties=properties,
        **_timestamps(item),
    )


def _edge(item: dict[str, Any], source_key: str, target_key: str) -> Edge:
    """Map a legacy relation/cross-reference to an edge."""
    kwargs: dict[str, Any] = {
        "type": item["predicate"],
        "source": item[source_key],
        "target": item[target_key],
        "id": item["id"],
    }
    created = _dt(item.get("created_at"))
    if created is not None:
        kwargs["created_at"] = created
    return Edge(**kwargs)


def graph_from_legacy(data: dict[str, Any]) -> KnowledgeGraph:
    """Convert a legacy provenance-graph dict into a KnowledgeGraph.

    Args:
        data: A legacy ``ProvenanceGraph.to_dict()`` mapping (statements or the
            pre-v2 ``claims`` key, plus evidence/activities/relations/
            cross_references).

    Returns:
        The equivalent generic knowledge graph (research profile).

    """
    graph = KnowledgeGraph(article_id=data.get("article_id"))
    if data.get("metadata") is not None:
        graph.metadata = dict(data["metadata"])
    for item in data.get("statements", data.get("claims", [])):
        graph.add_node(_statement_node(item))
    for item in data.get("evidence", []):
        graph.add_node(_evidence_node(item))
    for item in data.get("activities", []):
        graph.add_node(_activity_node(item))
    for item in data.get("relations", []):
        graph.add_edge(_edge(item, "subject_id", "object_id"))
    for item in data.get("cross_references", []):
        graph.add_edge(_edge(item, "subject_id", "target"))
    return graph
