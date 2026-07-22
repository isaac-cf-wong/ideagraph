"""The generic :class:`KnowledgeGraph` container.

Holds typed :class:`~ideagraph.kg.node.Node` objects and the directed
:class:`~ideagraph.kg.edge.Edge` objects between them, indexed by endpoint for
constant-time traversal. This is the generic successor to the old
provenance-specific ``ProvenanceGraph``; it serialises to a flat
``{nodes, edges}`` shape rather than the fixed statement/evidence/activity
collections.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ideagraph.core.identity import global_id as _global_id
from ideagraph.kg.edge import Edge
from ideagraph.kg.node import Node


@dataclass
class KnowledgeGraph:
    """An in-memory collection of typed nodes and the edges between them.

    Attributes:
        nodes: Nodes held by the graph, keyed by id.
        edges: Edges held by the graph, keyed by id.
        article_id: This graph's stable article id. Nodes are addressed globally
            as ``article_id#node_id``; required before another graph can
            reference this one.
        metadata: Arbitrary graph-level metadata (e.g. ``title``).
    """

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)
    article_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    _out: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list), repr=False, compare=False)
    _in: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list), repr=False, compare=False)

    def add_node(self, node: Node) -> Node:
        """Add or replace a node.

        Args:
            node: The node to store.

        Returns:
            The stored node.

        """
        self.nodes[node.id] = node
        return node

    def add_edge(self, edge: Edge) -> Edge:
        """Add or replace an edge and update the traversal index.

        Args:
            edge: The edge to store.

        Returns:
            The stored edge.

        """
        if edge.id in self.edges:
            self._deindex(self.edges[edge.id])
        self.edges[edge.id] = edge
        self._out[edge.source].append(edge.id)
        self._in[edge.target].append(edge.id)
        return edge

    def _deindex(self, edge: Edge) -> None:
        """Remove an edge from the traversal index.

        Args:
            edge: The edge to remove from the index.

        """
        out_ids = self._out.get(edge.source)
        if out_ids and edge.id in out_ids:
            out_ids.remove(edge.id)
        in_ids = self._in.get(edge.target)
        if in_ids and edge.id in in_ids:
            in_ids.remove(edge.id)

    def outgoing(self, node_id: str, edge_type: str | None = None) -> list[Edge]:
        """Return edges whose source is ``node_id``.

        Args:
            node_id: The id of the source node.
            edge_type: If given, only edges of this type are returned.

        Returns:
            The matching edges, in insertion order.

        """
        edges = [self.edges[eid] for eid in self._out.get(node_id, [])]
        if edge_type is not None:
            edges = [e for e in edges if e.type == edge_type]
        return edges

    def incoming(self, node_id: str, edge_type: str | None = None) -> list[Edge]:
        """Return edges whose target is ``node_id``.

        Args:
            node_id: The id of the target node.
            edge_type: If given, only edges of this type are returned.

        Returns:
            The matching edges, in insertion order.

        """
        edges = [self.edges[eid] for eid in self._in.get(node_id, [])]
        if edge_type is not None:
            edges = [e for e in edges if e.type == edge_type]
        return edges

    def nodes_of_type(self, node_type: str) -> list[Node]:
        """Return all nodes of a given type, in insertion order.

        Args:
            node_type: The node type to filter by.

        Returns:
            The matching nodes.

        """
        return [n for n in self.nodes.values() if n.type == node_type]

    def global_id(self, node_id: str) -> str:
        """Return the global address ``article_id#node_id`` for a local node.

        Args:
            node_id: A local node id.

        Returns:
            The global address.

        Raises:
            ValueError: If this graph has no ``article_id`` set.

        """
        if self.article_id is None:
            raise ValueError("graph has no article_id; set one before building global ids")
        return _global_id(self.article_id, node_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the whole graph to a JSON-compatible dictionary.

        Returns:
            A dictionary with ``article_id``, ``metadata``, ``nodes``, and
            ``edges``.

        """
        return {
            "article_id": self.article_id,
            "metadata": dict(self.metadata),
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeGraph:
        """Reconstruct a graph from its dictionary representation.

        Args:
            data: A dictionary as produced by :meth:`to_dict`.

        Returns:
            The reconstructed graph, with its traversal index rebuilt.

        """
        graph = cls()
        graph.article_id = data.get("article_id")
        if data.get("metadata") is not None:
            graph.metadata = dict(data["metadata"])
        for n in data.get("nodes", []):
            graph.add_node(Node.from_dict(n))
        for e in data.get("edges", []):
            graph.add_edge(Edge.from_dict(e))
        return graph
