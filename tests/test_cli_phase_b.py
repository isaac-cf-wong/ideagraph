"""CLI tests for Phase B: article id, cross-references, and doctor."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from ideagraph.cli.main import app
from ideagraph.kg.persistence import load_graph

runner = CliRunner()


def _init(path, article_id=None):
    """Init a graph, optionally with an article id.

    Args:
        path: Graph file path.
        article_id: Optional article id.

    """
    args = ["init", str(path)]
    if article_id:
        args += ["--article-id", article_id]
    assert runner.invoke(app, args).exit_code == 0


def test_init_with_article_id(tmp_path):
    """Init --article-id records the id on the graph.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    _init(path, "paper1")
    assert load_graph(path).article_id == "paper1"


def test_set_article_get_and_set(tmp_path):
    """set-article prints the current id and sets a new one.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    _init(path)
    assert runner.invoke(app, ["set-article", str(path)]).stdout.strip() == ""

    r = runner.invoke(app, ["set-article", str(path), "paper1"])
    assert r.exit_code == 0
    assert load_graph(path).article_id == "paper1"
    assert runner.invoke(app, ["set-article", str(path)]).stdout.strip() == "paper1"


def test_set_article_rejects_bad_id(tmp_path):
    """set-article rejects an id containing the separator.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    _init(path)
    r = runner.invoke(app, ["set-article", str(path), "bad#id"])
    assert r.exit_code == 1
    assert "Invalid article id" in r.stderr


def test_add_xref_records_edge(tmp_path):
    """add-xref stores a cross-article edge and prints its id.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    _init(path, "paper1")
    runner.invoke(app, ["add-statement", str(path), "A claim.", "--id", "c1"])
    r = runner.invoke(app, ["add-xref", str(path), "c1", "cites", "goncharov2022#f3"])
    assert r.exit_code == 0, r.stderr
    x = next(iter(load_graph(path).edges.values()))
    assert x.source == "c1"
    assert x.target == "goncharov2022#f3"


def test_add_xref_rejects_missing_subject_and_bad_target(tmp_path):
    """add-xref validates the subject exists and the target is a global id.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    _init(path, "paper1")
    runner.invoke(app, ["add-statement", str(path), "A claim.", "--id", "c1"])

    assert runner.invoke(app, ["add-xref", str(path), "ghost", "cites", "o#n1"]).exit_code == 1
    bad = runner.invoke(app, ["add-xref", str(path), "c1", "cites", "no-sep"])
    assert bad.exit_code == 1
    assert "Invalid target" in bad.stderr


def test_doctor_clean_and_errors(tmp_path):
    """Doctor passes a clean graph and fails on a dangling cross-reference.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    _init(path, "paper1")
    runner.invoke(app, ["add-statement", str(path), "A claim.", "--id", "c1"])
    clean = runner.invoke(app, ["doctor", str(path)])
    assert clean.exit_code == 0
    assert "No problems" in clean.stdout

    # Add a cross-reference then delete its subject by re-initialising is awkward;
    # instead point at a missing local node to force an error.
    runner.invoke(app, ["add-xref", str(path), "c1", "same_as", "paper1#missing"])
    bad = runner.invoke(app, ["doctor", str(path)])
    assert bad.exit_code == 1
    assert "xref-self-dangling" in bad.stdout


def test_doctor_json_output(tmp_path):
    """Doctor --json emits a JSON list of diagnostics.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = tmp_path / "g.json"
    _init(path, "paper1")
    runner.invoke(app, ["add-statement", str(path), "A claim.", "--id", "c1"])
    # A well-formed target into this article at a missing node (add-xref allows
    # it; doctor flags it) — exercises JSON output on a real diagnostic.
    runner.invoke(app, ["add-xref", str(path), "c1", "same_as", "paper1#missing"])
    out = runner.invoke(app, ["doctor", str(path), "--json"])
    payload = json.loads(out.stdout)
    assert any(d["code"] == "xref-self-dangling" for d in payload)
