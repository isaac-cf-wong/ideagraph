"""The built-in ``article`` profile: representing a paper as a graph.

Extends the ``research`` profile with the vocabulary the head-to-head design
test settled on for encoding a single article: a first-class ``article`` root
node, a ``summary_point`` layer whose links to detail are real edges (so the
summary is searchable, traversable, and extractable), and ``quantity`` / ``fact``
detail nodes alongside the research statement types.

The summary layer is wired ``article -contains-> summary_point`` and
``summary_point -summarizes-> detail``. Discourse and support edges are widened
so the new detail types can participate (a ``quantity`` may ``depends_on``
another, a ``summary_point`` may be ``supported_by`` evidence, etc.).
"""

from __future__ import annotations

from ideagraph.kg.profile import EdgeRule, NodeRule, Profile, register_profile
from ideagraph.kg.profiles.research import (
    CROSS_ARTICLE_TYPES,
    DISCOURSE_TYPES,
    RESEARCH,
    STATEMENT_TYPES,
)

#: The article root node type.
ARTICLE_NODE = "article"
#: A concise summary statement pointing at key detail nodes.
SUMMARY_POINT = "summary_point"
#: A measured or derived numeric value.
QUANTITY = "quantity"
#: A non-numeric observational fact.
FACT = "fact"

#: Node types added by this profile on top of ``research``.
ARTICLE_NODE_TYPES = (ARTICLE_NODE, SUMMARY_POINT, QUANTITY, FACT)

#: Detail node types that may take part in discourse / support / cross edges.
DETAIL_TYPES = frozenset(STATEMENT_TYPES) | {SUMMARY_POINT, QUANTITY, FACT}


def _build_profile() -> Profile:
    """Construct the article profile.

    Returns:
        The article profile.

    """
    node_types = dict(RESEARCH.node_types)
    for node_type in ARTICLE_NODE_TYPES:
        node_types[node_type] = NodeRule(node_type)

    edge_types = dict(RESEARCH.edge_types)
    edge_types["contains"] = EdgeRule(
        "contains", source_types=frozenset({ARTICLE_NODE}), target_types=frozenset({SUMMARY_POINT})
    )
    edge_types["summarizes"] = EdgeRule("summarizes", source_types=frozenset({SUMMARY_POINT}))
    _widen(edge_types, DETAIL_TYPES)
    return Profile(name="article", node_types=node_types, edge_types=edge_types)


def _widen(edge_types: dict[str, EdgeRule], details: frozenset[str]) -> None:
    """Broaden the inherited statement-level edge rules to cover ``details``.

    Args:
        edge_types: The edge-rule mapping to mutate in place.
        details: The set of node types allowed to participate as statements.

    """
    for edge_type in DISCOURSE_TYPES:
        edge_types[edge_type] = EdgeRule(edge_type, source_types=details, target_types=details)
    for edge_type in ("supported_by", "refuted_by"):
        base = RESEARCH.edge_types[edge_type]
        edge_types[edge_type] = EdgeRule(edge_type, source_types=details, target_types=base.target_types)
    for edge_type in CROSS_ARTICLE_TYPES:
        edge_types[edge_type] = EdgeRule(edge_type, source_types=details)


ARTICLE = register_profile(_build_profile())
