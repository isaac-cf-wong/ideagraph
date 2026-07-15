"""Tests for the :class:`claimkit.core.activity.Activity` model."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from claimkit.core import Activity, ActivityKind


def test_defaults():
    """An activity built from the required fields gets sensible defaults."""
    act = Activity(kind=ActivityKind.COMPUTATION, label="run pipeline")
    assert act.kind is ActivityKind.COMPUTATION
    assert act.label == "run pipeline"
    assert act.description == ""
    assert act.agent is None
    assert act.started_at is None
    assert act.ended_at is None
    assert act.used == []
    assert act.generated == []
    assert act.metadata == {}
    assert act.created_at.tzinfo is not None
    assert len(act.id) == 32


def test_ids_are_unique():
    """Auto-generated identifiers differ between activities."""
    a = Activity(kind=ActivityKind.ANALYSIS, label="a")
    b = Activity(kind=ActivityKind.ANALYSIS, label="b")
    assert a.id != b.id


def test_used_and_generated_reference_by_id():
    """used/generated hold plain reference strings."""
    act = Activity(
        kind=ActivityKind.COMPUTATION,
        label="fit",
        used=["dataset-1", "config-2"],
        generated=["ev-1", "fig-1"],
    )
    assert act.used == ["dataset-1", "config-2"]
    assert act.generated == ["ev-1", "fig-1"]


def test_to_dict_is_json_compatible():
    """to_dict() renders the kind and timestamps as stable tokens."""
    act = Activity(
        kind=ActivityKind.MEASUREMENT,
        label="acquire",
        id="act-001",
        description="lab run",
        agent="instrument-x",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        ended_at=datetime(2026, 1, 2, tzinfo=UTC),
        used=["sample-1"],
        generated=["ev-1"],
        metadata={"k": "v"},
    )
    data = act.to_dict()
    assert data == {
        "id": "act-001",
        "kind": "measurement",
        "label": "acquire",
        "description": "lab run",
        "agent": "instrument-x",
        "started_at": "2026-01-01T00:00:00+00:00",
        "ended_at": "2026-01-02T00:00:00+00:00",
        "used": ["sample-1"],
        "generated": ["ev-1"],
        "created_at": act.created_at.isoformat(),
        "metadata": {"k": "v"},
    }


def test_to_dict_renders_absent_times_as_none():
    """Missing started/ended timestamps serialise as None."""
    act = Activity(kind=ActivityKind.OTHER, label="x")
    data = act.to_dict()
    assert data["started_at"] is None
    assert data["ended_at"] is None
    assert data["agent"] is None


def test_roundtrip_preserves_fields():
    """from_dict() inverts to_dict()."""
    original = Activity(
        kind=ActivityKind.REVIEW,
        label="peer review",
        id="act-001",
        description="d",
        agent="reviewer-1",
        started_at=datetime(2026, 3, 1, tzinfo=UTC),
        ended_at=datetime(2026, 3, 2, tzinfo=UTC),
        used=["a"],
        generated=["b"],
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
        metadata={"k": "v"},
    )
    restored = Activity.from_dict(original.to_dict())
    assert restored == original


def test_roundtrip_with_absent_optionals():
    """A minimal activity survives a serialisation round trip."""
    original = Activity(kind=ActivityKind.IMPORT, label="ingest")
    restored = Activity.from_dict(original.to_dict())
    assert restored.started_at is None
    assert restored.ended_at is None
    assert restored == original


@pytest.mark.parametrize("missing", ["kind", "label"])
def test_from_dict_requires_core_fields(missing):
    """from_dict() raises when a required field is absent.

    Args:
        missing: The required key to drop from the input dictionary.

    """
    data = {"kind": "computation", "label": "l"}
    del data[missing]
    with pytest.raises(KeyError):
        Activity.from_dict(data)


def test_from_dict_applies_defaults_for_missing_optionals():
    """Optional fields fall back to defaults when absent."""
    act = Activity.from_dict({"kind": "analysis", "label": "l"})
    assert act.description == ""
    assert act.agent is None
    assert act.used == []
    assert act.generated == []
    assert act.metadata == {}
    assert len(act.id) == 32


def test_to_dict_copies_mutable_fields():
    """Mutating the dict output does not mutate the activity."""
    act = Activity(
        kind=ActivityKind.COMPUTATION,
        label="l",
        used=["a"],
        generated=["b"],
        metadata={"k": "v"},
    )
    data = act.to_dict()
    data["used"].append("c")
    data["generated"].append("d")
    data["metadata"]["k2"] = "v2"
    assert act.used == ["a"]
    assert act.generated == ["b"]
    assert act.metadata == {"k": "v"}
