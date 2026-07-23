"""Project-profile semantics: the conclusion gate and promotion.

The structural rules for a project graph live in the ``project``
:class:`~ideagraph.kg.profile.Profile`. This module adds the two lifecycle
operations on top:

* :func:`conclusion_status` — is the project's question answered? A question is
  concluded when a ``result`` / ``finding`` ``answers`` it, that answer is backed
  by evidence, and every ``hypothesis`` that ``addresses`` the question has been
  resolved (its ``status`` is ``valid`` or ``invalid``).
* :func:`promote` — carve the project's own new knowledge into a fresh article
  graph for the shared cache. Gated on :func:`conclusion_status`. Nodes imported
  from the cache (those carrying a ``source_gid`` stamp) are left behind; edges
  from kept nodes into imported ones are rewired as cross-article references back
  to their origin, so the promoted article cites its sources instead of copying
  them.
"""

from __future__ import annotations

from dataclasses import dataclass

from ideagraph.kg.edge import Edge
from ideagraph.kg.extract import SOURCE_GID_KEY
from ideagraph.kg.graph import KnowledgeGraph
from ideagraph.kg.node import Node

#: Hypothesis-status tokens that count as resolved.
_RESOLVED = frozenset({"valid", "invalid"})

_QUESTION = "question"


@dataclass(frozen=True)
class ConclusionResult:
    """Whether a project graph's question is concluded.

    Attributes:
        concluded: True when nothing blocks the conclusion.
        reasons: Human-readable reasons the project is not concluded (empty when
            it is).
    """

    concluded: bool
    reasons: tuple[str, ...]


def conclusion_status(graph: KnowledgeGraph) -> ConclusionResult:
    """Report whether a project graph's question has been answered.

    Args:
        graph: The project graph.

    Returns:
        A :class:`ConclusionResult` with the blocking reasons, if any.
    """
    reasons: list[str] = []
    questions = graph.nodes_of_type(_QUESTION)
    if not questions:
        reasons.append("no question node in graph")
    for question in questions:
        answers = graph.incoming(question.id, "answers")
        if not answers:
            reasons.append(f"question {question.id!r} has no answering result/finding")
        for answer in answers:
            if not graph.outgoing(answer.source, "supported_by"):
                reasons.append(f"answer {answer.source!r} to {question.id!r} has no supporting evidence")
        for edge in graph.incoming(question.id, "addresses"):
            hypothesis = graph.nodes.get(edge.source)
            status = hypothesis.properties.get("status") if hypothesis else None
            if status not in _RESOLVED:
                reasons.append(f"hypothesis {edge.source!r} is unresolved (status={status!r})")
    return ConclusionResult(concluded=not reasons, reasons=tuple(reasons))


def promote(graph: KnowledgeGraph, *, article_id: str) -> KnowledgeGraph:
    """Promote a concluded project's own knowledge into a new article graph.

    Keeps every node the project produced itself (those without a
    ``source_gid`` stamp) and the edges among them; edges into imported nodes are
    rewired as cross-article references to the imported node's origin.

    Args:
        graph: The concluded project graph.
        article_id: ``article_id`` for the promoted article graph.

    Returns:
        A new :class:`KnowledgeGraph` holding the promoted knowledge.

    Raises:
        ValueError: If the project is not concluded.
    """
    result = conclusion_status(graph)
    if not result.concluded:
        raise ValueError("project is not concluded: " + "; ".join(result.reasons))

    keep = {nid for nid, node in graph.nodes.items() if SOURCE_GID_KEY not in node.properties}
    out = KnowledgeGraph(article_id=article_id, metadata={"promoted_from": graph.article_id})
    for nid in keep:
        node = graph.nodes[nid]
        out.add_node(
            Node(
                type=node.type,
                text=node.text,
                id=node.id,
                tags=list(node.tags),
                properties=dict(node.properties),
                created_at=node.created_at,
                updated_at=node.updated_at,
            )
        )
    for edge in graph.edges.values():
        if edge.source not in keep:
            continue
        if edge.target in keep:
            _copy_edge(out, edge, edge.target)
            continue
        target = graph.nodes.get(edge.target)
        origin = target.properties.get(SOURCE_GID_KEY) if target else None
        if origin is not None:
            _copy_edge(out, edge, origin)
    return out


def _copy_edge(out: KnowledgeGraph, edge: Edge, target: str) -> None:
    """Copy ``edge`` into ``out`` with a (possibly rewired) target.

    Args:
        out: The destination graph.
        edge: The source edge.
        target: The target id to use (local id or a cross-article global id).

    """
    out.add_edge(Edge(type=edge.type, source=edge.source, target=target, id=edge.id, properties=dict(edge.properties)))
