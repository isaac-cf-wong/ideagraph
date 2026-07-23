"""Carve a self-contained subgraph out of a :class:`KnowledgeGraph`.

Extraction is the seam between a large source graph (or an article in a cached
library) and a small working graph seeded for a specific task. Given a set of
seed node ids, it returns the induced subgraph within ``hops`` edges of those
seeds: the reachable nodes, the edges among them, and the cross-article edges
leaving them. Each copied node keeps a ``source_gid`` provenance stamp pointing
back at the node it came from, so the extracted graph is self-contained yet
still traceable to its origin.
"""

from __future__ import annotations

from ideagraph.core.identity import is_global_id
from ideagraph.kg.edge import Edge
from ideagraph.kg.graph import KnowledgeGraph
from ideagraph.kg.node import Node

#: Property key under which a copied node records its origin's global id.
SOURCE_GID_KEY = "source_gid"


def neighbourhood(graph: KnowledgeGraph, seeds: set[str], *, hops: int = 1) -> set[str]:
    """Return the ids of nodes within ``hops`` edges of any seed.

    Expansion follows edges in both directions and stays within the graph's own
    nodes (cross-article targets, which live elsewhere, are not traversed).

    Args:
        graph: The graph to expand within.
        seeds: Seed node ids (ids absent from the graph are ignored).
        hops: Number of edge hops to expand; ``0`` returns just the seeds.

    Returns:
        The reachable node-id set, including the seeds present in the graph.
    """
    seen = {s for s in seeds if s in graph.nodes}
    frontier = set(seen)
    for _ in range(max(hops, 0)):
        nxt: set[str] = set()
        for edge in graph.edges.values():
            if edge.source in frontier and edge.target in graph.nodes:
                nxt.add(edge.target)
            if edge.target in frontier and edge.source in graph.nodes:
                nxt.add(edge.source)
        nxt -= seen
        if not nxt:
            break
        seen |= nxt
        frontier = nxt
    return seen


def extract_subgraph(
    graph: KnowledgeGraph,
    seeds: set[str],
    *,
    hops: int = 1,
    article_id: str | None = None,
    stamp_provenance: bool = True,
) -> KnowledgeGraph:
    """Extract the induced subgraph around ``seeds`` into a new graph.

    The result contains every node within ``hops`` edges of a seed, every edge
    whose endpoints are both included, and every cross-article edge leaving an
    included node. Copies are deep enough to be independent of the source: the
    new graph can be mutated or saved without touching the original.

    Args:
        graph: The source graph to carve from.
        seeds: Seed node ids (ids absent from the source are ignored).
        hops: Number of edge hops to expand from the seeds.
        article_id: ``article_id`` for the new graph; defaults to ``None`` (the
            caller sets one before the subgraph can be referenced globally).
        stamp_provenance: If true and the source has an ``article_id``, record
            each copied node's origin under ``properties["source_gid"]`` (an
            existing stamp is preserved, so re-extraction keeps the first origin).

    Returns:
        A new :class:`KnowledgeGraph` holding the induced subgraph.
    """
    keep = neighbourhood(graph, seeds, hops=hops)
    out = KnowledgeGraph(article_id=article_id)
    can_stamp = stamp_provenance and graph.article_id is not None
    for nid in keep:
        src = graph.nodes[nid]
        properties = dict(src.properties)
        if can_stamp and SOURCE_GID_KEY not in properties:
            properties[SOURCE_GID_KEY] = graph.global_id(nid)
        out.add_node(
            Node(
                type=src.type,
                text=src.text,
                id=src.id,
                tags=list(src.tags),
                properties=properties,
                created_at=src.created_at,
                updated_at=src.updated_at,
            )
        )
    for edge in graph.edges.values():
        if edge.source not in keep:
            continue
        if edge.target in keep or is_global_id(edge.target):
            out.add_edge(
                Edge(
                    type=edge.type,
                    source=edge.source,
                    target=edge.target,
                    id=edge.id,
                    properties=dict(edge.properties),
                    created_at=edge.created_at,
                )
            )
    return out
