"""Activities that generate evidence and artefacts.

An :class:`Activity` records a process — a computation, a measurement, an
analysis, a review — that consumed some artefacts and produced others. It is the
claimkit analogue of a `PROV Activity
<https://www.w3.org/TR/prov-dm/#term-Activity>`_: it captures *what* happened,
*who or what* performed it, *when* it ran, and *which* artefacts it ``used`` and
``generated``.

Activities reference the artefacts and evidence they touch by identifier rather
than holding those objects, so the model stays decoupled and independently
serialisable. The generic, typed provenance edges that connect claims,
evidence, activities, and artefacts into a graph are defined elsewhere.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class ActivityKind(enum.StrEnum):
    """The type of process an activity represents.

    The value is a stable, machine-readable string token.

    Attributes:
        COMPUTATION: A computational run (simulation, model fit, data pipeline).
        MEASUREMENT: A physical measurement or instrument acquisition.
        ANALYSIS: A post-processing or statistical analysis step.
        REVIEW: A human or automated review or assessment.
        IMPORT: Ingestion of provenance or artefacts from an external system.
        OTHER: Anything not covered by the categories above.
    """

    COMPUTATION = "computation"
    MEASUREMENT = "measurement"
    ANALYSIS = "analysis"
    REVIEW = "review"
    IMPORT = "import"
    OTHER = "other"


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        The current moment in UTC.

    """
    return datetime.now(UTC)


@dataclass
class Activity:
    """A process that consumed and produced artefacts.

    Attributes:
        kind: The type of process.
        label: A short human-readable name for the activity.
        id: Stable unique identifier. Generated as a UUID4 hex string if not
            supplied.
        description: A longer human-readable description.
        agent: The person, tool, or autonomous agent that performed the
            activity, if known.
        started_at: When the real-world activity began (UTC), if known. This is
            distinct from :attr:`created_at`, which records when this activity
            record was created.
        ended_at: When the real-world activity finished (UTC), if known.
        used: Identifiers or references of artefacts the activity consumed.
        generated: Identifiers or references of artefacts and evidence the
            activity produced.
        created_at: Timezone-aware timestamp of when this record was created
            (UTC).
        metadata: Arbitrary structured metadata.
    """

    kind: ActivityKind
    label: str
    id: str = field(default_factory=lambda: uuid4().hex)
    description: str = ""
    agent: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    used: list[str] = field(default_factory=list)
    generated: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the activity to a JSON-compatible dictionary.

        The kind renders as its stable string token and timestamps as ISO 8601
        strings (or ``None``), giving a representation suitable for exchange
        with other tools and autonomous agents.

        Returns:
            A dictionary representation of the activity.

        """
        return {
            "id": self.id,
            "kind": self.kind.value,
            "label": self.label,
            "description": self.description,
            "agent": self.agent,
            "started_at": self.started_at.isoformat() if self.started_at is not None else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at is not None else None,
            "used": list(self.used),
            "generated": list(self.generated),
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Activity:
        """Reconstruct an activity from its dictionary representation.

        This is the inverse of :meth:`to_dict`. ``kind`` and ``label`` are
        required; any missing optional field falls back to its default.

        Args:
            data: A dictionary as produced by :meth:`to_dict`.

        Returns:
            The reconstructed activity.

        Raises:
            KeyError: If ``kind`` or ``label`` is missing.

        """
        kwargs: dict[str, Any] = {
            "kind": ActivityKind(data["kind"]),
            "label": data["label"],
        }
        if "id" in data:
            kwargs["id"] = data["id"]
        if data.get("description") is not None:
            kwargs["description"] = data["description"]
        if data.get("agent") is not None:
            kwargs["agent"] = data["agent"]
        if data.get("started_at") is not None:
            kwargs["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("ended_at") is not None:
            kwargs["ended_at"] = datetime.fromisoformat(data["ended_at"])
        if data.get("used") is not None:
            kwargs["used"] = list(data["used"])
        if data.get("generated") is not None:
            kwargs["generated"] = list(data["generated"])
        if data.get("created_at") is not None:
            kwargs["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("metadata") is not None:
            kwargs["metadata"] = dict(data["metadata"])
        return cls(**kwargs)
