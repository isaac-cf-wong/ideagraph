"""CLI tests for ``ideagraph index`` and ``doctor --library``."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from ideagraph.cli.main import app

runner = CliRunner()


def _make(root, article_id, node_id, text):
    """Create a one-statement article graph via the CLI.

    Args:
        root: Directory to write the graph into.
        article_id: The article id.
        node_id: The statement id.
        text: The statement text.

    """
    path = root / f"{article_id}.json"
    runner.invoke(app, ["init", str(path), "--article-id", article_id])
    runner.invoke(app, ["add-statement", str(path), text, "--id", node_id])
    return path


def test_index_reports_and_json(tmp_path):
    """Index prints a summary and --json lists indexed articles.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    _make(tmp_path, "paperA", "c1", "A finding.")
    r = runner.invoke(app, ["index", str(tmp_path), "--json"])
    assert r.exit_code == 0
    payload = json.loads(r.stdout)
    assert "paperA" in payload["indexed"]


def test_index_flags_dangling_cross_reference(tmp_path):
    """Index exits non-zero and lists a dangling cross-reference.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    a = _make(tmp_path, "paperA", "c1", "Cites something missing.")
    runner.invoke(app, ["add-xref", str(a), "c1", "cites", "paperB#ghost"])
    _make(tmp_path, "paperB", "f1", "A real finding.")  # paperB exists, f-node does not
    r = runner.invoke(app, ["index", str(tmp_path)])
    assert r.exit_code == 1
    assert "dangling xref" in r.stdout
    assert "paperB#ghost" in r.stdout


def test_doctor_library_resolves_targets(tmp_path):
    """Doctor --library flags a cross-reference whose target node is absent.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    a = _make(tmp_path, "paperA", "c1", "Cites a missing node.")
    runner.invoke(app, ["add-xref", str(a), "c1", "cites", "paperB#ghost"])
    _make(tmp_path, "paperB", "f1", "A real finding.")

    # Single-graph doctor can't see the missing target -> clean.
    assert runner.invoke(app, ["doctor", str(a)]).exit_code == 0

    # Library-aware doctor resolves it -> error.
    r = runner.invoke(app, ["doctor", str(a), "--library", str(tmp_path)])
    assert r.exit_code == 1
    assert "xref-dangling-target" in r.stdout
