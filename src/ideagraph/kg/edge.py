"""The generic :class:`Edge` of a knowledge graph.

An edge is a directed, typed connection between two nodes: ``source
--type--> target``. Its ``type`` is a free string from the active profile's
edge vocabulary. This single model subsumes both the old intra-article
provenance relations and cross-article references — a cross-article edge is
simply one whose ``target`` is a global ``article_id#node_id`` address rather
than a local node id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        The current moment in UTC.

    """
    return datetime.now(UTC)


@dataclass
class Edge:
    """A directed, typed connection between two nodes.

    Attributes:
        type: The edge's type, from the active profile's edge vocabulary.
        source: The id of the source node.
        target: The id of the target node (a local id, or a global
            ``article_id#node_id`` address for a cross-article edge).
        id: Stable unique identifier (UUID4 hex if not supplied).
        properties: Arbitrary structured metadata about the connection.
        created_at: Timezone-aware creation timestamp (UTC).
    """

    type: str
    source: str
    target: str
    id: str = field(default_factory=lambda: uuid4().hex)
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the edge to a JSON-compatible dictionary.

        Returns:
            A dictionary representation of the edge.

        """
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "target": self.target,
            "properties": dict(self.properties),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Edge:
        """Reconstruct an edge from its dictionary representation.

        Args:
            data: A dictionary as produced by :meth:`to_dict`.

        Returns:
            The reconstructed edge.

        Raises:
            KeyError: If ``type``, ``source``, or ``target`` is missing.

        """
        kwargs: dict[str, Any] = {
            "type": data["type"],
            "source": data["source"],
            "target": data["target"],
        }
        if "id" in data:
            kwargs["id"] = data["id"]
        if data.get("properties") is not None:
            kwargs["properties"] = dict(data["properties"])
        if data.get("created_at") is not None:
            kwargs["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**kwargs)
