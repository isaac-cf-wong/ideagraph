"""Build the front-end JSON payloads for stored graphs.

Reconstructs the in-memory :class:`~ideagraph.kg.graph.KnowledgeGraph` from an
ORM row and computes the node/edge shape the visualization expects, reusing the
research-profile coverage and validation. The front-end contract (statement /
evidence / activity node buckets, discourse edges, support summary) is preserved
so the existing vis-network front end is unchanged. Staleness (which needs the
referenced artefact files on disk) is not computed for the hosted store.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ideagraph.bib import format_citation
from ideagraph.kg.profiles import (
    CROSS_ARTICLE_TYPES,
    DISCOURSE_TYPES,
    STATEMENT_TYPES,
    coverage,
    validate_all,
)
from ideagraph.server.graphs.bridge import orm_to_graph

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from ideagraph.server.graphs.models import Graph

_STATEMENT_SET = frozenset(STATEMENT_TYPES)


def graph_payload(row: Graph) -> dict[str, Any]:
    """Compute the visualization payload for a stored graph.

    Args:
        row: The Graph ORM row to render.

    Returns:
        A dict with ``nodes``, ``edges``, ``summary`` (support coverage counts),
        and ``counts`` — the shape the graph view's JavaScript consumes.

    """
    graph = orm_to_graph(row)
    verdicts = validate_all(graph)
    cov = coverage(graph)

    nodes: list[dict[str, Any]] = []
    counts = {"statements": 0, "evidence": 0, "activities": 0}
    for node in graph.nodes.values():
        props = node.properties
        if node.type in _STATEMENT_SET:
            counts["statements"] += 1
            status = verdicts[node.id].status if node.id in verdicts else props.get("status")
            nodes.append(
                {
                    "id": node.id,
                    "type": "statement",
                    "stype": node.type,
                    "level": 0,
                    "label": node.id,
                    "order": props.get("order", 0),
                    "section": props.get("section"),
                    "status": status,
                    "support": cov[node.id].category if node.id in cov else None,
                    "source_digest": props.get("source_digest"),
                    "statement": node.text,
                    "tags": list(node.tags),
                    "metadata": props,
                }
            )
        elif node.type == "evidence":
            counts["evidence"] += 1
            is_lit = props.get("kind") == "literature"
            citation = format_citation(props.get("reference", ""), None) if is_lit else None
            nodes.append(
                {
                    "id": node.id,
                    "type": "evidence",
                    "level": 1,
                    "label": citation if is_lit else node.id,
                    "status": "literature" if is_lit else "evidence",
                    "kind": props.get("kind"),
                    "reference": props.get("reference"),
                    "citation": citation,
                    "digest": props.get("digest"),
                    "metadata": props,
                }
            )
        elif node.type == "activity":
            counts["activities"] += 1
            nodes.append(
                {
                    "id": node.id,
                    "type": "activity",
                    "level": 2,
                    "label": props.get("label") or node.text,
                    "status": "activity",
                    "kind": props.get("kind"),
                    "metadata": props,
                }
            )
        else:
            nodes.append(
                {
                    "id": node.id,
                    "type": node.type,
                    "level": 0,
                    "label": node.id,
                    "status": None,
                    "statement": node.text,
                    "metadata": props,
                }
            )

    edges = [
        {
            "source": edge.source,
            "target": edge.target,
            "predicate": edge.type,
            "discourse": edge.type in DISCOURSE_TYPES,
        }
        for edge in graph.edges.values()
    ]

    summary: dict[str, int] = {}
    for c in cov.values():
        summary[c.category] = summary.get(c.category, 0) + 1

    return {"nodes": nodes, "edges": edges, "summary": summary, "counts": counts}


def library_payload(graphs: QuerySet[Graph]) -> dict[str, Any]:
    """Aggregate several graphs into one cross-article idea-graph payload.

    Args:
        graphs: The graphs to aggregate (typically the viewer's visible graphs).

    Returns:
        A dict with ``articles``, ``nodes``, ``edges``, and ``counts``.

    """
    graphs = graphs.prefetch_related("nodes", "edges")
    articles: list[dict[str, str]] = []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for row in graphs:
        art = row.article_id or row.slug
        articles.append({"id": art, "title": row.title or row.slug})
        statement_ids = set()
        for node in row.nodes.all():
            if node.type not in _STATEMENT_SET:
                continue
            statement_ids.add(node.node_id)
            nodes.append(
                {
                    "id": f"{art}#{node.node_id}",
                    "article": art,
                    "node": node.node_id,
                    "stype": node.type,
                    "status": node.status,
                    "text": node.text,
                }
            )
        for edge in row.edges.all():
            if edge.type in DISCOURSE_TYPES and edge.source in statement_ids and edge.target in statement_ids:
                edges.append(
                    {
                        "source": f"{art}#{edge.source}",
                        "target": f"{art}#{edge.target}",
                        "predicate": edge.type,
                        "kind": "intra",
                        "dangling": False,
                    }
                )
            elif edge.type in CROSS_ARTICLE_TYPES:
                edges.append(
                    {
                        "source": f"{art}#{edge.source}",
                        "target": edge.target,
                        "predicate": edge.type,
                        "kind": "cross",
                        "dangling": False,
                    }
                )

    known = {n["id"] for n in nodes}
    for edge in edges:
        if edge["kind"] == "cross":
            edge["dangling"] = edge["target"] not in known

    return {
        "articles": articles,
        "nodes": nodes,
        "edges": edges,
        "counts": {
            "articles": len(articles),
            "statements": len(nodes),
            "cross_edges": sum(1 for e in edges if e["kind"] == "cross"),
        },
    }
