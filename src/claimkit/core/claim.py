"""The :class:`Claim`, claimkit's primary abstraction.

A claim is a scientific assertion registered independently of any manuscript.
It carries a stable identity, a human-readable statement, a validation status,
and structured metadata. Supporting evidence and provenance relationships are
attached by other parts of the framework; this module defines only the claim
itself and its serialisable representation so that both humans and autonomous
agents can inspect and exchange claims through a stable interface.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class ClaimStatus(enum.StrEnum):
    """Validation status of a claim.

    The status reflects the relationship between a claim and its current
    supporting evidence. It is a plain string enum so that it serialises to a
    stable, machine-readable token.

    Attributes:
        UNRESOLVED: The claim has not yet been validated against its evidence.
        VALID: The claim is supported by the current evidence.
        STALE: Supporting evidence has changed; the claim must be re-validated.
        INVALID: The current evidence contradicts the claim.
        NEEDS_REVIEW: Automated validation is inconclusive; a human must decide.
    """

    UNRESOLVED = "unresolved"
    VALID = "valid"
    STALE = "stale"
    INVALID = "invalid"
    NEEDS_REVIEW = "needs_review"


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        The current moment in UTC.

    """
    return datetime.now(UTC)


@dataclass
class Claim:
    """A registered scientific claim.

    A claim is the primary unit of provenance in claimkit. It is deliberately
    lightweight: it holds identity, the assertion itself, a validation status,
    timestamps, and free-form structured metadata. Links to evidence and
    provenance are modelled elsewhere and reference a claim by its ``id``.

    Attributes:
        statement: The human-readable assertion the claim makes.
        id: Stable unique identifier. Generated as a UUID4 hex string if not
            supplied.
        status: Current validation status. Defaults to
            :attr:`ClaimStatus.UNRESOLVED`.
        created_at: Timezone-aware creation timestamp (UTC).
        updated_at: Timezone-aware timestamp of the last status change (UTC).
        tags: Free-form labels for grouping and discovery.
        metadata: Arbitrary structured metadata. Prefer this over encoding
            information in the statement text.
    """

    statement: str
    id: str = field(default_factory=lambda: uuid4().hex)
    status: ClaimStatus = ClaimStatus.UNRESOLVED
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark(self, status: ClaimStatus) -> None:
        """Set the validation status and refresh :attr:`updated_at`.

        Args:
            status: The new validation status.

        """
        self.status = ClaimStatus(status)
        self.updated_at = _utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Serialise the claim to a JSON-compatible dictionary.

        Timestamps are rendered as ISO 8601 strings and the status as its
        stable string token, giving a representation suitable for exchange with
        other tools and autonomous agents.

        Returns:
            A dictionary representation of the claim.

        """
        return {
            "id": self.id,
            "statement": self.statement,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Claim:
        """Reconstruct a claim from its dictionary representation.

        This is the inverse of :meth:`to_dict`. Only ``statement`` is required;
        any missing optional field falls back to its default.

        Args:
            data: A dictionary as produced by :meth:`to_dict`.

        Returns:
            The reconstructed claim.

        Raises:
            KeyError: If ``statement`` is missing from ``data``.

        """
        kwargs: dict[str, Any] = {"statement": data["statement"]}
        if "id" in data:
            kwargs["id"] = data["id"]
        if data.get("status") is not None:
            kwargs["status"] = ClaimStatus(data["status"])
        if data.get("created_at") is not None:
            kwargs["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at") is not None:
            kwargs["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("tags") is not None:
            kwargs["tags"] = list(data["tags"])
        if data.get("metadata") is not None:
            kwargs["metadata"] = dict(data["metadata"])
        return cls(**kwargs)
