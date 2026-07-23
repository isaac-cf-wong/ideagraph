"""Built-in knowledge-graph profiles and their semantics.

Importing this package registers the bundled profiles (currently ``research``)
so they are available via :func:`ideagraph.kg.profile.get_profile`. The
research-profile semantics (coverage, validation, staleness) are re-exported
here for convenience.
"""

from __future__ import annotations

from ideagraph.kg.profiles.article import ARTICLE
from ideagraph.kg.profiles.project import PROJECT
from ideagraph.kg.profiles.research import (
    ASSERTION_TYPES,
    CROSS_ARTICLE_TYPES,
    DISCOURSE_TYPES,
    RESEARCH,
    STATEMENT_TYPES,
    ActivityKind,
    ClaimStatus,
    EvidenceKind,
    EvidenceRelation,
    NodeType,
    ProvenancePredicate,
    StatementStatus,
    StatementType,
)
from ideagraph.kg.profiles.research_compat import graph_from_legacy
from ideagraph.kg.profiles.research_ops import (
    Coverage,
    DigestResolver,
    ValidationResult,
    apply_all,
    apply_validation,
    coverage,
    evidence_changed,
    find_stale_assertions,
    find_stale_evidence,
    mark_stale,
    validate_all,
    validate_node,
)

__all__ = [
    "ARTICLE",
    "ASSERTION_TYPES",
    "CROSS_ARTICLE_TYPES",
    "DISCOURSE_TYPES",
    "PROJECT",
    "RESEARCH",
    "STATEMENT_TYPES",
    "ActivityKind",
    "ClaimStatus",
    "Coverage",
    "DigestResolver",
    "EvidenceKind",
    "EvidenceRelation",
    "NodeType",
    "ProvenancePredicate",
    "StatementStatus",
    "StatementType",
    "ValidationResult",
    "apply_all",
    "apply_validation",
    "coverage",
    "evidence_changed",
    "find_stale_assertions",
    "find_stale_evidence",
    "graph_from_legacy",
    "mark_stale",
    "validate_all",
    "validate_node",
]
