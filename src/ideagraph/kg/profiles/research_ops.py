"""Research-profile semantics over a generic knowledge graph.

The structural rules (allowed types, endpoints, required properties) live in the
``research`` :class:`~ideagraph.kg.profile.Profile`. This module adds the richer,
domain-specific logic that used to be hard-wired into the provenance-only core:
support coverage, claim validation, and staleness — now expressed over generic
:class:`~ideagraph.kg.node.Node` / :class:`~ideagraph.kg.edge.Edge` objects,
reading domain fields from ``node.properties``.

Conventions for research-profile nodes:

* assertion nodes (``claim`` / ``finding`` / ``result``) carry a
  ``properties["status"]`` in the validation-status vocabulary;
* ``evidence`` nodes carry ``properties["kind"]`` and, optionally,
  ``properties["digest"]``;
* support is expressed by ``supported_by`` / ``refuted_by`` edges to evidence.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ideagraph.kg.profiles.research import ASSERTION_TYPES

if TYPE_CHECKING:
    from ideagraph.kg.graph import KnowledgeGraph
    from ideagraph.kg.node import Node

#: Validation-status tokens (stored in an assertion node's ``status`` property).
UNRESOLVED, VALID, STALE, INVALID, NEEDS_REVIEW = "unresolved", "valid", "stale", "invalid", "needs_review"

#: Evidence kinds that count as first-hand (own) support.
_OWN_KINDS = frozenset({"code", "data", "workflow", "figure", "table", "instrument"})

_EVIDENCE = "evidence"

#: A resolver returning the current digest of an evidence node's artefact.
DigestResolver = Callable[["Node"], str | None]


# -- coverage --------------------------------------------------------------


@dataclass(frozen=True)
class Coverage:
    """How one assertion node is supported by evidence.

    Attributes:
        node_id: The assertion node's id.
        has_own: Whether any first-hand evidence supports it.
        has_literature: Whether any literature evidence supports it.
        has_other: Whether any other-kind evidence supports it.
        evidence_kinds: The kinds of all supporting evidence, in edge order.
    """

    node_id: str
    has_own: bool
    has_literature: bool
    has_other: bool
    evidence_kinds: list[str] = field(default_factory=list)

    @property
    def supported(self) -> bool:
        """Whether the assertion has any supporting evidence."""
        return self.has_own or self.has_literature or self.has_other

    @property
    def category(self) -> str:
        """The support category: unsupported / own / literature / both / other."""
        if self.has_own and self.has_literature:
            return "both"
        if self.has_own:
            return "own"
        if self.has_literature:
            return "literature"
        if self.has_other:
            return "other"
        return "unsupported"

    def to_dict(self) -> dict[str, Any]:
        """Serialise the coverage record.

        Returns:
            A dictionary representation.

        """
        return {
            "node_id": self.node_id,
            "category": self.category,
            "supported": self.supported,
            "evidence_kinds": list(self.evidence_kinds),
        }


def coverage(graph: KnowledgeGraph) -> dict[str, Coverage]:
    """Classify support origin for every assertion node in a graph.

    Args:
        graph: The graph to analyse.

    Returns:
        A mapping from assertion node id to its coverage.

    """
    result: dict[str, Coverage] = {}
    for node in graph.nodes.values():
        if node.type not in ASSERTION_TYPES:
            continue
        own = literature = other = False
        kinds: list[str] = []
        for edge in graph.outgoing(node.id, "supported_by"):
            evidence = graph.nodes.get(edge.target)
            if evidence is None or evidence.type != _EVIDENCE:
                continue
            kind = str(evidence.properties.get("kind", "other"))
            kinds.append(kind)
            if kind == "literature":
                literature = True
            elif kind in _OWN_KINDS:
                own = True
            else:
                other = True
        result[node.id] = Coverage(node.id, own, literature, other, kinds)
    return result


# -- validation ------------------------------------------------------------


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of validating one assertion node against its evidence.

    Attributes:
        node_id: The validated node's id.
        status: The resolved status token.
        supporting: Ids of evidence linked by ``supported_by``.
        refuting: Ids of evidence linked by ``refuted_by``.
        reason: A human-readable explanation.
    """

    node_id: str
    status: str
    supporting: list[str] = field(default_factory=list)
    refuting: list[str] = field(default_factory=list)
    reason: str = ""


def _linked_evidence(graph: KnowledgeGraph, node_id: str, edge_type: str) -> list[str]:
    """Return ids of evidence nodes linked from a node by an edge type.

    Args:
        graph: The graph.
        node_id: The source node id.
        edge_type: The edge type to follow.

    Returns:
        Held evidence node ids, in edge order.

    """
    out = []
    for edge in graph.outgoing(node_id, edge_type):
        target = graph.nodes.get(edge.target)
        if target is not None and target.type == _EVIDENCE:
            out.append(edge.target)
    return out


def validate_node(graph: KnowledgeGraph, node_id: str) -> ValidationResult:
    """Resolve an assertion node's status from its supporting/refuting evidence.

    Args:
        graph: The graph holding the node and its evidence.
        node_id: The id of the node to validate.

    Returns:
        The validation result.

    Raises:
        KeyError: If the node is not held by the graph.

    """
    if node_id not in graph.nodes:
        raise KeyError(node_id)
    supporting = _linked_evidence(graph, node_id, "supported_by")
    refuting = _linked_evidence(graph, node_id, "refuted_by")
    if not supporting and not refuting:
        return ValidationResult(node_id, UNRESOLVED, supporting, refuting, "no supporting or refuting evidence linked")
    if supporting and refuting:
        reason = f"conflicting evidence: {len(supporting)} supporting, {len(refuting)} refuting"
        return ValidationResult(node_id, NEEDS_REVIEW, supporting, refuting, reason)
    if refuting:
        return ValidationResult(node_id, INVALID, supporting, refuting, f"refuted by {len(refuting)} piece(s)")
    return ValidationResult(node_id, VALID, supporting, refuting, f"supported by {len(supporting)} piece(s)")


def validate_all(graph: KnowledgeGraph) -> dict[str, ValidationResult]:
    """Validate every assertion node without mutating the graph.

    Args:
        graph: The graph to validate.

    Returns:
        A mapping from node id to validation result.

    """
    return {n.id: validate_node(graph, n.id) for n in graph.nodes.values() if n.type in ASSERTION_TYPES}


def apply_validation(graph: KnowledgeGraph, node_id: str) -> ValidationResult:
    """Validate a node and write the resolved status into its properties.

    Args:
        graph: The graph.
        node_id: The node to validate and update.

    Returns:
        The validation result whose status was applied.

    """
    result = validate_node(graph, node_id)
    node = graph.nodes[node_id]
    node.properties["status"] = result.status
    node.touch()
    return result


def apply_all(graph: KnowledgeGraph) -> list[ValidationResult]:
    """Validate every assertion node and write each status back.

    Args:
        graph: The graph to validate and update in place.

    Returns:
        The results, one per assertion node.

    """
    return [apply_validation(graph, nid) for nid in list(graph.nodes) if graph.nodes[nid].type in ASSERTION_TYPES]


# -- staleness -------------------------------------------------------------


def evidence_changed(node: Node, current_digest: str | None) -> bool:
    """Report whether an evidence node's artefact has drifted.

    Args:
        node: The evidence node holding a baseline ``digest`` property.
        current_digest: The artefact's current digest, or None if unknown.

    Returns:
        ``True`` if both digests are present and differ.

    """
    baseline = node.properties.get("digest")
    if not baseline or current_digest is None:
        return False
    return baseline != current_digest


def find_stale_evidence(graph: KnowledgeGraph, resolver: DigestResolver) -> list[Node]:
    """Return evidence nodes whose artefact has changed.

    Args:
        graph: The graph to sweep.
        resolver: Resolves an evidence node's current digest (or None).

    Returns:
        The changed evidence nodes.

    """
    return [n for n in graph.nodes.values() if n.type == _EVIDENCE and evidence_changed(n, resolver(n))]


def find_stale_assertions(graph: KnowledgeGraph, resolver: DigestResolver) -> list[Node]:
    """Return assertion nodes with at least one changed supporting evidence.

    Args:
        graph: The graph to sweep.
        resolver: Resolves an evidence node's current digest (or None).

    Returns:
        The affected assertion nodes, in insertion order.

    """
    out: list[Node] = []
    for node in graph.nodes.values():
        if node.type not in ASSERTION_TYPES:
            continue
        for eid in _linked_evidence(graph, node.id, "supported_by"):
            if evidence_changed(graph.nodes[eid], resolver(graph.nodes[eid])):
                out.append(node)
                break
    return out


def mark_stale(graph: KnowledgeGraph, resolver: DigestResolver) -> list[Node]:
    """Flip affected ``valid`` assertion nodes to ``stale`` and return them.

    Args:
        graph: The graph to update in place.
        resolver: Resolves an evidence node's current digest (or None).

    Returns:
        The assertion nodes whose status changed to ``stale``.

    """
    changed: list[Node] = []
    for node in find_stale_assertions(graph, resolver):
        if node.properties.get("status") == VALID:
            node.properties["status"] = STALE
            node.touch()
            changed.append(node)
    return changed
