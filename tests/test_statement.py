"""Tests for the Statement model, claims-view compat, and migration."""

from __future__ import annotations

from typer.testing import CliRunner

from ideagraph import Claim, ClaimStatus, ProvenanceGraph, Statement, StatementStatus, StatementType
from ideagraph.cli.main import app

runner = CliRunner()


def test_statement_defaults_and_roundtrip():
    """A Statement defaults to a claim and round-trips through to_dict/from_dict."""
    s = Statement(statement="X", id="s1", type=StatementType.BACKGROUND, order=3, section="Intro")
    assert s.type is StatementType.BACKGROUND
    d = s.to_dict()
    assert d["type"] == "background"
    assert d["order"] == 3
    assert d["section"] == "Intro"
    back = Statement.from_dict(d)
    assert back == s


def test_claim_is_statement_alias():
    """Claim/ClaimStatus are aliases of Statement/StatementStatus."""
    assert Claim is Statement
    assert ClaimStatus is StatementStatus
    c = Claim(statement="A")
    assert c.type is StatementType.CLAIM  # a claim is the CLAIM-typed statement


def test_from_dict_missing_type_defaults_claim():
    """A pre-v-next dict without a type migrates to a claim."""
    s = Statement.from_dict({"statement": "old", "id": "c1", "status": "valid"})
    assert s.type is StatementType.CLAIM
    assert s.status is StatementStatus.VALID


def test_graph_statements_and_claims_view():
    """graph.statements holds all; graph.claims is the claim-typed view."""
    g = ProvenanceGraph()
    g.add_statement(Statement(statement="a claim", id="c1", type=StatementType.CLAIM))
    g.add_statement(Statement(statement="some context", id="b1", type=StatementType.BACKGROUND))
    assert set(g.statements) == {"c1", "b1"}
    assert set(g.claims) == {"c1"}  # background excluded from the claims view


def test_graph_migrates_old_claims_key():
    """from_dict reads a pre-v-next document that stored nodes under 'claims'."""
    g = ProvenanceGraph.from_dict({"claims": [{"statement": "old", "id": "c1"}]})
    assert set(g.statements) == {"c1"}
    assert g.statements["c1"].type is StatementType.CLAIM
    assert "statements" in g.to_dict()  # re-serialises under the new key


def test_add_statement_cli(tmp_path):
    """add-statement registers a typed statement; add-claim stays claim-typed.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    runner.invoke(app, ["init", str(path)])
    r = runner.invoke(
        app,
        ["add-statement", str(path), "Prior work established X.", "--type", "background", "--id", "b1", "--order", "2"],
    )
    assert r.exit_code == 0, r.stderr
    runner.invoke(app, ["add-claim", str(path), "We find Y.", "--id", "c1"])
    from ideagraph.kg.persistence import load_graph as kg_load_graph

    g = kg_load_graph(path)
    assert g.nodes["b1"].type == "background"
    assert g.nodes["b1"].properties["order"] == 2
    assert g.nodes["c1"].type == "claim"
    assert {n.id for n in g.nodes.values() if n.type == "claim"} == {"c1"}
