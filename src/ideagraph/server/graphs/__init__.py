"""The graphs app: ORM persistence for ideagraph provenance graphs.

Stores each :class:`~ideagraph.kg.graph.KnowledgeGraph` as a ``Graph`` row
with its nodes and edges, keeping the serialised dataclass dict as the source of
truth plus denormalised columns for querying. The bridge in :mod:`.bridge`
converts between the ORM rows and the in-memory ``KnowledgeGraph``, reusing the
engine's existing ``to_dict`` / ``from_dict`` so the domain model is not
duplicated.
"""

from __future__ import annotations
