"""Profiles: the schema that gives a knowledge graph its meaning.

A :class:`Profile` names the node and edge types a graph may use and the
structural rules over them (endpoint types, required properties). It is the
seam that lets one generic engine serve any domain: the built-in ``research``
profile reproduces the old scientific-provenance model, but other profiles can
describe entirely different kinds of knowledge.

Structural validation lives here; richer, domain-specific semantics (support
coverage, claim validation, staleness) are layered on per profile elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ideagraph.core.identity import is_global_id

if TYPE_CHECKING:
    from ideagraph.kg.graph import KnowledgeGraph


@dataclass(frozen=True)
class Diagnostic:
    """A single validation finding.

    Attributes:
        level: ``"error"``, ``"warning"``, or ``"info"``.
        code: A stable machine-readable code.
        message: A human-readable, self-correction-friendly description.
        ref: The id of the offending node or edge, if any.
    """

    level: str
    code: str
    message: str
    ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise the diagnostic.

        Returns:
            A dictionary representation.

        """
        return {"level": self.level, "code": self.code, "message": self.message, "ref": self.ref}


@dataclass(frozen=True)
class NodeRule:
    """Schema for a node type.

    Attributes:
        type: The node type name.
        required_properties: Property keys every node of this type must set.
    """

    type: str
    required_properties: frozenset[str] = frozenset()


@dataclass(frozen=True)
class EdgeRule:
    """Schema for an edge type.

    Attributes:
        type: The edge type name.
        source_types: Allowed source node types (empty = any).
        target_types: Allowed target node types (empty = any). Ignored for
            cross-article targets, whose node lives in another graph.
        required_properties: Property keys every edge of this type must set.
    """

    type: str
    source_types: frozenset[str] = frozenset()
    target_types: frozenset[str] = frozenset()
    required_properties: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Profile:
    """A named schema of node and edge types plus structural rules.

    Attributes:
        name: The profile's stable name.
        node_types: Mapping of node type name to its rule.
        edge_types: Mapping of edge type name to its rule.
    """

    name: str
    node_types: dict[str, NodeRule] = field(default_factory=dict)
    edge_types: dict[str, EdgeRule] = field(default_factory=dict)

    def allows_node_type(self, node_type: str) -> bool:
        """Report whether a node type is part of this profile.

        Args:
            node_type: The node type to check.

        Returns:
            ``True`` if the type is known.

        """
        return node_type in self.node_types

    def allows_edge_type(self, edge_type: str) -> bool:
        """Report whether an edge type is part of this profile.

        Args:
            edge_type: The edge type to check.

        Returns:
            ``True`` if the type is known.

        """
        return edge_type in self.edge_types

    def validate(self, graph: KnowledgeGraph) -> list[Diagnostic]:
        """Structurally validate a graph against this profile.

        Checks that every node/edge type is known, that required properties are
        present, that edges reference existing source nodes, and that endpoint
        types satisfy the edge rule. Cross-article targets (global ids) are not
        resolved here — that is a library-level concern.

        Args:
            graph: The graph to validate.

        Returns:
            A list of diagnostics (empty if the graph conforms).

        """
        out: list[Diagnostic] = []
        for node in graph.nodes.values():
            rule = self.node_types.get(node.type)
            if rule is None:
                out.append(Diagnostic("error", "unknown-node-type", f"unknown node type {node.type!r}", node.id))
                continue
            for prop in sorted(rule.required_properties - set(node.properties)):
                out.append(Diagnostic("error", "missing-property", f"node missing property {prop!r}", node.id))
        for edge in graph.edges.values():
            out.extend(self._validate_edge(graph, edge))
        return out

    def _validate_edge(self, graph: KnowledgeGraph, edge: Any) -> list[Diagnostic]:
        """Validate a single edge against its rule.

        Args:
            graph: The graph the edge belongs to.
            edge: The edge to validate.

        Returns:
            Diagnostics for this edge.

        """
        rule = self.edge_types.get(edge.type)
        if rule is None:
            return [Diagnostic("error", "unknown-edge-type", f"unknown edge type {edge.type!r}", edge.id)]
        out: list[Diagnostic] = []
        for prop in sorted(rule.required_properties - set(edge.properties)):
            out.append(Diagnostic("error", "missing-property", f"edge missing property {prop!r}", edge.id))
        source = graph.nodes.get(edge.source)
        if source is None:
            out.append(Diagnostic("error", "edge-dangling-source", f"edge source {edge.source!r} not found", edge.id))
        elif rule.source_types and source.type not in rule.source_types:
            out.append(
                Diagnostic("error", "edge-bad-source-type", f"{edge.type!r} source may not be {source.type!r}", edge.id)
            )
        if not is_global_id(edge.target):
            target = graph.nodes.get(edge.target)
            if target is None:
                out.append(
                    Diagnostic("error", "edge-dangling-target", f"edge target {edge.target!r} not found", edge.id)
                )
            elif rule.target_types and target.type not in rule.target_types:
                out.append(
                    Diagnostic(
                        "error", "edge-bad-target-type", f"{edge.type!r} target may not be {target.type!r}", edge.id
                    )
                )
        return out


_PROFILES: dict[str, Profile] = {}


def register_profile(profile: Profile) -> Profile:
    """Register a profile so it can be looked up by name.

    Args:
        profile: The profile to register.

    Returns:
        The registered profile.

    """
    _PROFILES[profile.name] = profile
    return profile


def get_profile(name: str) -> Profile:
    """Return a registered profile by name.

    Args:
        name: The profile name.

    Returns:
        The profile.

    Raises:
        KeyError: If no profile with that name is registered.

    """
    return _PROFILES[name]


def available_profiles() -> list[str]:
    """Return the names of all registered profiles.

    Returns:
        Registered profile names, sorted.

    """
    return sorted(_PROFILES)
