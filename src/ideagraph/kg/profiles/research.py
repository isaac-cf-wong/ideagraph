"""The built-in ``research`` profile.

Reproduces the scientific-provenance vocabulary of the old typed core as a
knowledge-graph profile: statement node types (claim, finding, …) plus evidence
and activity nodes, and the provenance / discourse / cross-article edge types
with their endpoint constraints. This is what makes the generic engine behave
like the original ideagraph when the ``research`` profile is active.
"""

from __future__ import annotations

from ideagraph.kg.profile import EdgeRule, NodeRule, Profile, register_profile

#: Statement node types (rhetorical roles).
STATEMENT_TYPES = ("claim", "finding", "background", "method", "definition", "motivation", "result", "other")

#: Statement types that assert something and therefore require support.
ASSERTION_TYPES = frozenset({"claim", "finding", "result"})

#: Non-statement node types.
_EVIDENCE = "evidence"
_ACTIVITY = "activity"

#: Discourse edge types (statement -> statement rhetorical links).
DISCOURSE_TYPES = frozenset({"elaborates", "contrasts", "depends_on", "cites", "motivates"})

#: Cross-article edge types (this article -> another).
CROSS_ARTICLE_TYPES = frozenset({"builds_on", "extends", "contradicts", "same_as"})

_STATEMENT_SET = frozenset(STATEMENT_TYPES)


def _build_profile() -> Profile:
    """Construct the research profile.

    Returns:
        The research profile.

    """
    node_types = {t: NodeRule(t) for t in STATEMENT_TYPES}
    node_types[_EVIDENCE] = NodeRule(_EVIDENCE, required_properties=frozenset({"kind", "reference"}))
    node_types[_ACTIVITY] = NodeRule(_ACTIVITY, required_properties=frozenset({"label"}))

    edge_types: dict[str, EdgeRule] = {
        "supported_by": EdgeRule("supported_by", source_types=_STATEMENT_SET, target_types=frozenset({_EVIDENCE})),
        "refuted_by": EdgeRule("refuted_by", source_types=_STATEMENT_SET, target_types=frozenset({_EVIDENCE})),
        "generated_by": EdgeRule("generated_by", target_types=frozenset({_ACTIVITY})),
        "used": EdgeRule("used", source_types=frozenset({_ACTIVITY})),
        "derived_from": EdgeRule("derived_from"),
        "attributed_to": EdgeRule("attributed_to"),
        "reviewed_by": EdgeRule("reviewed_by"),
        "relates_to": EdgeRule("relates_to"),
    }
    for t in DISCOURSE_TYPES:
        edge_types[t] = EdgeRule(t, source_types=_STATEMENT_SET, target_types=_STATEMENT_SET)
    for t in CROSS_ARTICLE_TYPES:
        # Cross-article edges point at a global id in another graph; the target
        # type cannot be checked locally, so it is left unconstrained.
        edge_types[t] = EdgeRule(t, source_types=_STATEMENT_SET)
    return Profile(name="research", node_types=node_types, edge_types=edge_types)


RESEARCH = register_profile(_build_profile())
