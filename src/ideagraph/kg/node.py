"""The generic :class:`Node` of a knowledge graph.

A node carries one piece of information. Its ``type`` is a free string drawn from
the active profile's vocabulary (e.g. ``"claim"``, ``"evidence"``, ``"person"``,
``"concept"``), its ``text`` is the human-readable content, and everything
domain-specific lives in ``properties``. This replaces the fixed
Statement/Evidence/Activity trichotomy of the old provenance-only core.
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
class Node:
    """A single piece of information in a knowledge graph.

    Attributes:
        type: The node's type, from the active profile's vocabulary.
        text: The human-readable content of the node.
        id: Stable unique identifier (UUID4 hex if not supplied).
        tags: Free-form labels for grouping and discovery.
        properties: Arbitrary structured, domain-specific fields.
        created_at: Timezone-aware creation timestamp (UTC).
        updated_at: Timezone-aware timestamp of the last change (UTC).
    """

    type: str
    text: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    tags: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def touch(self) -> None:
        """Refresh :attr:`updated_at` to now."""
        self.updated_at = _utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Serialise the node to a JSON-compatible dictionary.

        Returns:
            A dictionary representation of the node.

        """
        return {
            "id": self.id,
            "type": self.type,
            "text": self.text,
            "tags": list(self.tags),
            "properties": dict(self.properties),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Node:
        """Reconstruct a node from its dictionary representation.

        Args:
            data: A dictionary as produced by :meth:`to_dict`.

        Returns:
            The reconstructed node.

        Raises:
            KeyError: If ``type`` is missing.

        """
        kwargs: dict[str, Any] = {"type": data["type"], "text": data.get("text", "")}
        if "id" in data:
            kwargs["id"] = data["id"]
        if data.get("tags") is not None:
            kwargs["tags"] = list(data["tags"])
        if data.get("properties") is not None:
            kwargs["properties"] = dict(data["properties"])
        if data.get("created_at") is not None:
            kwargs["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at") is not None:
            kwargs["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**kwargs)
