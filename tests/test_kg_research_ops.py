"""Tests for research-profile semantics over the generic knowledge graph."""

from __future__ import annotations

import pytest

from ideagraph.kg import Edge, KnowledgeGraph, Node
from ideagraph.kg.profiles import (
    Coverage,
    apply_all,
    apply_validation,
    coverage,
    evidence_changed,
    find_stale_assertions,
    mark_stale,
    validate_all,
    validate_node,
)


def _claim(cid: str, status: str | None = None) -> Node:
    """Build a claim node with an optional status property.

    Args:
        cid: Node id.
        status: Optional validation status.

    Returns:
        The node.

    """
    props = {"status": status} if status else {}
    return Node(type="claim", id=cid, text="c", properties=props)


def _evidence(eid: str, kind: str = "data", digest: str | None = None) -> Node:
    """Build an evidence node.

    Args:
        eid: Node id.
        kind: Evidence kind.
        digest: Optional baseline digest.

    Returns:
        The node.

    """
    props = {"kind": kind, "reference": "r"}
    if digest:
        props["digest"] = digest
    return Node(type="evidence", id=eid, properties=props)


def _support(cid: str, eid: str, edge_id: str, edge_type: str = "supported_by") -> Edge:
    """Build a claim->evidence edge.

    Args:
        cid: Claim id.
        eid: Evidence id.
        edge_id: Edge id.
        edge_type: Edge type.

    Returns:
        The edge.

    """
    return Edge(type=edge_type, source=cid, target=eid, id=edge_id)


# -- coverage --------------------------------------------------------------


def test_coverage_categories():
    """Coverage classifies own vs literature vs both vs unsupported."""
    g = KnowledgeGraph()
    g.add_node(_claim("c1"))
    g.add_node(_claim("c2"))
    g.add_node(_claim("c3"))
    g.add_node(_evidence("d1", kind="data"))
    g.add_node(_evidence("l1", kind="literature"))
    g.add_edge(_support("c1", "d1", "x1"))
    g.add_edge(_support("c2", "d1", "x2"))
    g.add_edge(_support("c2", "l1", "x3"))
    cov = coverage(g)
    assert cov["c1"].category == "own"
    assert cov["c2"].category == "both"
    assert cov["c3"].category == "unsupported"
    assert not cov["c3"].supported


def test_coverage_only_covers_assertions():
    """Non-assertion statement types are not covered."""
    g = KnowledgeGraph()
    g.add_node(Node(type="background", id="b1"))
    assert coverage(g) == {}


def test_coverage_to_dict():
    """Coverage serialises with its category."""
    c = Coverage("c1", has_own=True, has_literature=False, has_other=False, evidence_kinds=["data"])
    assert c.to_dict()["category"] == "own"


# -- validation ------------------------------------------------------------


def test_validate_unresolved_valid_invalid_needs_review():
    """The four status outcomes are derived from support/refute edges."""
    g = KnowledgeGraph()
    for cid in ("c1", "c2", "c3", "c4"):
        g.add_node(_claim(cid))
    g.add_node(_evidence("e1"))
    g.add_node(_evidence("e2"))
    g.add_edge(_support("c2", "e1", "s2"))
    g.add_edge(_support("c3", "e1", "r3", edge_type="refuted_by"))
    g.add_edge(_support("c4", "e1", "s4"))
    g.add_edge(_support("c4", "e2", "r4", edge_type="refuted_by"))
    assert validate_node(g, "c1").status == "unresolved"
    assert validate_node(g, "c2").status == "valid"
    assert validate_node(g, "c3").status == "invalid"
    assert validate_node(g, "c4").status == "needs_review"


def test_validate_all_and_apply():
    """validate_all is pure; apply writes status into properties."""
    g = KnowledgeGraph()
    g.add_node(_claim("c1"))
    g.add_node(_evidence("e1"))
    g.add_edge(_support("c1", "e1", "s1"))
    assert validate_all(g)["c1"].status == "valid"
    assert g.nodes["c1"].properties.get("status") is None  # pure
    apply_validation(g, "c1")
    assert g.nodes["c1"].properties["status"] == "valid"


def test_apply_all_only_assertions():
    """apply_all writes status onto assertion nodes only."""
    g = KnowledgeGraph()
    g.add_node(_claim("c1"))
    g.add_node(Node(type="background", id="b1"))
    g.add_node(_evidence("e1"))
    g.add_edge(_support("c1", "e1", "s1"))
    apply_all(g)
    assert g.nodes["c1"].properties["status"] == "valid"
    assert "status" not in g.nodes["b1"].properties


def test_validate_unknown_node_raises():
    """Validating an absent node raises KeyError."""
    with pytest.raises(KeyError):
        validate_node(KnowledgeGraph(), "missing")


# -- staleness -------------------------------------------------------------


def test_evidence_changed():
    """A drifted digest is detected; absent digests are never changed."""
    ev = _evidence("e1", digest="sha256:aaa")
    assert evidence_changed(ev, "sha256:bbb") is True
    assert evidence_changed(ev, "sha256:aaa") is False
    assert evidence_changed(_evidence("e2"), "sha256:bbb") is False


def test_find_and_mark_stale():
    """A valid claim whose supporting artefact drifts is marked stale."""
    g = KnowledgeGraph()
    g.add_node(_claim("c1", status="valid"))
    g.add_node(_evidence("e1", digest="sha256:aaa"))
    g.add_edge(_support("c1", "e1", "s1"))
    resolver = {"e1": "sha256:zzz"}.get

    def _resolve(node: Node) -> str | None:
        return resolver(node.id)

    assert [n.id for n in find_stale_assertions(g, _resolve)] == ["c1"]
    changed = mark_stale(g, _resolve)
    assert [n.id for n in changed] == ["c1"]
    assert g.nodes["c1"].properties["status"] == "stale"


def test_mark_stale_leaves_non_valid():
    """Only currently-valid claims are flipped to stale."""
    g = KnowledgeGraph()
    g.add_node(_claim("c1", status="unresolved"))
    g.add_node(_evidence("e1", digest="sha256:aaa"))
    g.add_edge(_support("c1", "e1", "s1"))

    def _resolve(node: Node) -> str | None:
        return "sha256:zzz"

    assert mark_stale(g, _resolve) == []
    assert g.nodes["c1"].properties["status"] == "unresolved"
