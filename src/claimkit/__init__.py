"""Top-level package for claimkit."""

from __future__ import annotations

from claimkit.core import (
    Activity,
    ActivityKind,
    Claim,
    ClaimStatus,
    Evidence,
    EvidenceKind,
    EvidenceRelation,
)
from claimkit.hello_world import goodbye_world, hello_goodbye, hello_world, say_goodbye, say_hello
from claimkit.version import __version__

__all__ = [
    "Activity",
    "ActivityKind",
    "Claim",
    "ClaimStatus",
    "Evidence",
    "EvidenceKind",
    "EvidenceRelation",
    "__version__",
    "goodbye_world",
    "hello_goodbye",
    "hello_world",
    "say_goodbye",
    "say_hello",
]
