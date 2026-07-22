"""Convert between stored ORM rows and the in-memory KnowledgeGraph.

The engine's :class:`~ideagraph.kg.graph.KnowledgeGraph` serialises node/edge
dicts; this bridge stores those dicts in the ORM (with denormalised columns for
querying) and reconstructs the graph from them, reusing the engine's
``to_dict``/``from_dict`` so the domain model is not duplicated.
"""

from __future__ import annotations

from django.db import transaction

from ideagraph.kg.graph import KnowledgeGraph
from ideagraph.server.graphs.models import Edge, Graph, Node


@transaction.atomic
def graph_to_orm(graph: KnowledgeGraph, *, slug: str, owner: object = None) -> Graph:
    """Persist a KnowledgeGraph as a Graph row (replacing any existing one).

    Args:
        graph: The in-memory graph to store.
        slug: The stable URL/slug identifier for the stored graph.
        owner: Optional user to record as the graph's owner.

    Returns:
        The saved Graph row.

    """
    Graph.objects.filter(slug=slug).delete()
    row = Graph.objects.create(
        slug=slug,
        article_id=graph.article_id or "",
        title=str(graph.metadata.get("title", "")) if graph.metadata else "",
        metadata=dict(graph.metadata),
        owner=owner,
    )
    Node.objects.bulk_create(
        Node(
            graph=row,
            node_id=node.id,
            type=node.type,
            status=str(node.properties.get("status", "")),
            text=node.text,
            data=node.to_dict(),
        )
        for node in graph.nodes.values()
    )
    Edge.objects.bulk_create(
        Edge(
            graph=row,
            edge_id=edge.id,
            type=edge.type,
            source=edge.source,
            target=edge.target,
            data=edge.to_dict(),
        )
        for edge in graph.edges.values()
    )
    return row


def orm_to_graph(row: Graph) -> KnowledgeGraph:
    """Reconstruct a KnowledgeGraph from a stored Graph row.

    Args:
        row: The Graph row to read.

    Returns:
        The reconstructed in-memory graph.

    """
    data = {
        "article_id": row.article_id or None,
        "metadata": dict(row.metadata),
        "nodes": [n.data for n in row.nodes.all()],
        "edges": [e.data for e in row.edges.all()],
    }
    return KnowledgeGraph.from_dict(data)
