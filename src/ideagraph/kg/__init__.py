"""The generic knowledge-graph core.

Typed :class:`~ideagraph.kg.node.Node` objects connected by directed
:class:`~ideagraph.kg.edge.Edge` objects in a :class:`~ideagraph.kg.graph.KnowledgeGraph`,
with a :class:`~ideagraph.kg.profile.Profile` supplying the vocabulary and rules
for a given domain. Importing this package registers the built-in profiles.
"""

from __future__ import annotations

from ideagraph.kg.edge import Edge
from ideagraph.kg.graph import KnowledgeGraph
from ideagraph.kg.node import Node
from ideagraph.kg.profile import (
    Diagnostic,
    EdgeRule,
    NodeRule,
    Profile,
    available_profiles,
    get_profile,
    register_profile,
)
from ideagraph.kg.profiles import RESEARCH

__all__ = [
    "RESEARCH",
    "Diagnostic",
    "Edge",
    "EdgeRule",
    "KnowledgeGraph",
    "Node",
    "NodeRule",
    "Profile",
    "available_profiles",
    "get_profile",
    "register_profile",
]
