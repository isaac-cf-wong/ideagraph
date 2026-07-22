"""Research-profile integrity diagnostics over a generic knowledge graph.

This reproduces, for the generic :class:`~ideagraph.kg.graph.KnowledgeGraph`, the
integrity checks the old provenance-only ``doctor`` performed: it reports
problems that would otherwise surface only as silent dangling edges. The generic
model has a single :class:`~ideagraph.kg.edge.Edge` type, so an edge is treated
as a *cross-article reference* when its target is a global ``article_id#node_id``
address (or its type is a cross-article predicate), and as an intra-article
*relation* otherwise.

Cross-article *resolution* — does the target ``article_id#node_id`` actually
exist? — needs every graph in view and is therefore a library-level concern.
Pass ``known_articles`` to enable the ``xref-unknown-article`` warning.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from ideagraph.core.identity import is_global_id, parse_global_id
from ideagraph.kg.profile import Diagnostic
from ideagraph.kg.profiles.research import CROSS_ARTICLE_TYPES, STATEMENT_TYPES

if TYPE_CHECKING:
    from ideagraph.kg.edge import Edge
    from ideagraph.kg.graph import KnowledgeGraph

#: Diagnostic levels, most severe first.
_LEVEL_ORDER = {"error": 0, "warning": 1, "info": 2}

_STATEMENT_SET = frozenset(STATEMENT_TYPES)


def _is_cross_reference(edge: Edge) -> bool:
    """Whether an edge points at another article rather than a local node.

    Args:
        edge: The edge to classify.

    Returns:
        ``True`` for a cross-article reference.

    """
    return is_global_id(edge.target) or edge.type in CROSS_ARTICLE_TYPES


def _is_statement(graph: KnowledgeGraph, node_id: str) -> bool:
    """Whether ``node_id`` names a statement node held by the graph.

    Args:
        graph: The graph to look in.
        node_id: The id to check.

    Returns:
        ``True`` if a statement node with that id exists.

    """
    node = graph.nodes.get(node_id)
    return node is not None and node.type in _STATEMENT_SET


def diagnose(graph: KnowledgeGraph, *, known_articles: Iterable[str] | None = None) -> list[Diagnostic]:
    """Report integrity problems in a graph, most severe first.

    Args:
        graph: The graph to check.
        known_articles: If given, the set of article ids the library holds;
            cross-references whose target article is outside this set are
            flagged ``xref-unknown-article``. Omit for a single-graph check.

    Returns:
        The diagnostics found, sorted error → warning → info.

    """
    known = set(known_articles) if known_articles is not None else None
    out: list[Diagnostic] = []

    cross = [e for e in graph.edges.values() if _is_cross_reference(e)]
    relations = [e for e in graph.edges.values() if not _is_cross_reference(e)]

    if cross and graph.article_id is None:
        out.append(
            Diagnostic(
                "warning",
                "no-article-id",
                "graph has cross-references but no article_id, so no other article can point back at it",
            )
        )

    for edge in cross:
        if not _is_statement(graph, edge.source):
            out.append(
                Diagnostic(
                    "error",
                    "xref-dangling-subject",
                    f"cross-reference subject {edge.source!r} is not a statement in this graph",
                    edge.id,
                )
            )
        if not is_global_id(edge.target):
            out.append(
                Diagnostic(
                    "error",
                    "xref-bad-target",
                    f"cross-reference target {edge.target!r} is not a valid 'article_id#node_id' address",
                    edge.id,
                )
            )
            continue
        target_article, target_node = parse_global_id(edge.target)
        if target_article == graph.article_id and target_node not in graph.nodes:
            out.append(
                Diagnostic(
                    "error",
                    "xref-self-dangling",
                    f"cross-reference target {edge.target!r} points into this article at a missing node",
                    edge.id,
                )
            )
        elif known is not None and target_article not in known:
            out.append(
                Diagnostic(
                    "warning",
                    "xref-unknown-article",
                    f"cross-reference target article {target_article!r} is not in the library",
                    edge.id,
                )
            )

    for edge in relations:
        if edge.source not in graph.nodes:
            out.append(
                Diagnostic(
                    "warning",
                    "relation-dangling-subject",
                    f"relation subject {edge.source!r} is not held by the graph",
                    edge.id,
                )
            )
        if edge.target not in graph.nodes:
            out.append(
                Diagnostic(
                    "warning",
                    "relation-dangling-object",
                    f"relation object {edge.target!r} is not held by the graph",
                    edge.id,
                )
            )

    out.sort(key=lambda d: _LEVEL_ORDER.get(d.level, 99))
    return out
