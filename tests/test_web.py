"""Tests for the provenance web UI (``claimkit serve`` / claimkit.web)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from claimkit import Claim, Evidence, EvidenceKind, NodeType, ProvenanceGraph, ProvenancePredicate, ProvenanceRelation
from claimkit.cli.main import app
from claimkit.persistence import save_graph
from claimkit.web import build_payload

runner = CliRunner()


def _graph_file(tmp_path, artefact_digest=None, artefact_name="fig.npz"):
    """Write a graph with one claim supported by one evidence, return its path.

    Args:
        tmp_path: Pytest temporary directory fixture.
        artefact_digest: Digest to store on the evidence (for staleness tests).
        artefact_name: Reference filename for the evidence.

    Returns:
        The graph file path.

    """
    g = ProvenanceGraph()
    g.add_claim(Claim(statement="A finding worth checking", id="c1"))
    g.add_evidence(Evidence(claim_id="c1", kind=EvidenceKind.FIGURE, reference=artefact_name, digest=artefact_digest))
    ev_id = next(iter(g.evidence))
    g.add_relation(
        ProvenanceRelation(
            subject_type=NodeType.CLAIM,
            subject_id="c1",
            predicate=ProvenancePredicate.SUPPORTED_BY,
            object_type=NodeType.EVIDENCE,
            object_id=ev_id,
        )
    )
    path = tmp_path / "g.json"
    save_graph(g, path)
    return path


def test_build_payload_shapes_and_status(tmp_path):
    """build_payload reports nodes, edges, and a valid claim status.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _graph_file(tmp_path)
    payload = build_payload(path)
    assert payload["counts"] == {"claims": 1, "evidence": 1, "activities": 0}
    assert payload["summary"].get("valid") == 1
    types = {n["type"] for n in payload["nodes"]}
    assert types == {"claim", "evidence"}
    assert len(payload["edges"]) == 1


def test_build_payload_detects_stale(tmp_path):
    """A claim whose referenced artefact drifted is reported stale.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    artefact = tmp_path / "fig.npz"
    artefact.write_bytes(b"original")
    from claimkit import hash_file

    path = _graph_file(tmp_path, artefact_digest=hash_file(artefact), artefact_name="fig.npz")
    assert build_payload(path)["summary"].get("stale") is None  # matches on disk

    artefact.write_bytes(b"CHANGED")
    claim_node = next(n for n in build_payload(path)["nodes"] if n["type"] == "claim")
    assert claim_node["status"] == "stale"


def test_flask_app_serves_index_and_api(tmp_path):
    """The Flask app serves the HTML page and the graph API.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    pytest.importorskip("flask")
    from claimkit.web import create_app

    path = _graph_file(tmp_path)
    client = create_app(path).test_client()

    index = client.get("/")
    assert index.status_code == 200
    assert b"claimkit provenance" in index.data

    api = client.get("/api/graph")
    assert api.status_code == 200
    body = api.get_json()
    assert body["counts"]["claims"] == 1
    assert body["summary"].get("valid") == 1


def test_flask_app_serves_vendored_vis_network(tmp_path):
    """The vendored vis-network library is served locally (no CDN).

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    pytest.importorskip("flask")
    from claimkit.web import create_app

    client = create_app(_graph_file(tmp_path)).test_client()
    index = client.get("/")
    assert b"/vendor/vis-network.min.js" in index.data
    assert b"unpkg.com" not in index.data

    vis = client.get("/vendor/vis-network.min.js")
    assert vis.status_code == 200
    assert b"vis-network" in vis.data


def test_serve_missing_file(tmp_path):
    """Serve on a missing graph file exits non-zero.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    result = runner.invoke(app, ["serve", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
    assert "No such file" in result.stderr
