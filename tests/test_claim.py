"""Tests for the :class:`claimkit.core.claim.Claim` model."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from claimkit.core import Claim, ClaimStatus


def test_defaults():
    """A claim built from only a statement gets sensible defaults."""
    claim = Claim(statement="The speed of light is constant.")
    assert claim.statement == "The speed of light is constant."
    assert claim.status is ClaimStatus.UNRESOLVED
    assert claim.tags == []
    assert claim.metadata == {}
    assert claim.created_at.tzinfo is not None
    assert claim.updated_at.tzinfo is not None


def test_ids_are_unique():
    """Auto-generated identifiers differ between claims."""
    a = Claim(statement="A")
    b = Claim(statement="B")
    assert a.id != b.id
    assert len(a.id) == 32


def test_explicit_id_is_preserved():
    """An explicitly supplied identifier is kept verbatim."""
    claim = Claim(statement="A", id="claim-001")
    assert claim.id == "claim-001"


def test_mark_updates_status_and_timestamp():
    """mark() sets the status and refreshes updated_at."""
    claim = Claim(statement="A")
    before = claim.updated_at
    claim.mark(ClaimStatus.VALID)
    assert claim.status is ClaimStatus.VALID
    assert claim.updated_at >= before


def test_mark_accepts_string_value():
    """mark() coerces a raw status token into the enum."""
    claim = Claim(statement="A")
    claim.mark(ClaimStatus("stale"))
    assert claim.status is ClaimStatus.STALE


def test_to_dict_is_json_compatible():
    """to_dict() renders timestamps and status as stable tokens."""
    claim = Claim(
        statement="A",
        id="claim-001",
        status=ClaimStatus.VALID,
        tags=["physics"],
        metadata={"source": "run-42"},
    )
    data = claim.to_dict()
    assert data == {
        "id": "claim-001",
        "statement": "A",
        "status": "valid",
        "created_at": claim.created_at.isoformat(),
        "updated_at": claim.updated_at.isoformat(),
        "tags": ["physics"],
        "metadata": {"source": "run-42"},
    }


def test_roundtrip_preserves_fields():
    """from_dict() inverts to_dict()."""
    original = Claim(
        statement="A",
        id="claim-001",
        status=ClaimStatus.STALE,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 2, 1, tzinfo=UTC),
        tags=["a", "b"],
        metadata={"k": "v"},
    )
    restored = Claim.from_dict(original.to_dict())
    assert restored == original


def test_from_dict_requires_statement():
    """from_dict() raises when the statement is missing."""
    with pytest.raises(KeyError):
        Claim.from_dict({"id": "x"})


def test_from_dict_applies_defaults_for_missing_optionals():
    """Optional fields fall back to defaults when absent."""
    claim = Claim.from_dict({"statement": "A"})
    assert claim.status is ClaimStatus.UNRESOLVED
    assert claim.tags == []
    assert claim.metadata == {}
    assert len(claim.id) == 32


def test_to_dict_copies_mutable_fields():
    """Mutating the dict output does not mutate the claim."""
    claim = Claim(statement="A", tags=["x"], metadata={"k": "v"})
    data = claim.to_dict()
    data["tags"].append("y")
    data["metadata"]["k2"] = "v2"
    assert claim.tags == ["x"]
    assert claim.metadata == {"k": "v"}
