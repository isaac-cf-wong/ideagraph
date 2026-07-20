"""Tests for semantic search (embeddings) over the library.

A deterministic fake embedder exercises the vector store and ranking without the
heavy ``[semantic]`` dependency; the real model path is only reached when that
extra is installed.
"""

from __future__ import annotations

import importlib.util

import pytest

from ideagraph import Library, ProvenanceGraph, Statement
from ideagraph.persistence import save_graph
from ideagraph.semantic import cosine, normalize


class FakeEmbedder:
    """Maps text to a tiny keyword-presence vector — deterministic, dep-free."""

    name = "fake-v1"

    def embed(self, texts):
        """Return a 3-d presence vector per text (noise / far / null themes)."""
        out = []
        for t in texts:
            tl = t.lower()
            out.append(
                [
                    float("noise" in tl or "glitch" in tl),
                    float("far" in tl or "false-alarm" in tl),
                    float("null" in tl or "self-slid" in tl),
                ]
            )
        return out


def test_normalize_and_cosine():
    """Normalize yields unit length; cosine ranks aligned vectors highest."""
    v = normalize([3.0, 4.0])
    assert abs(sum(x * x for x in v) - 1.0) < 1e-9
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine([], [1.0]) == 0.0


def _library(tmp_path):
    """Build a small library and return its root.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    g = ProvenanceGraph(article_id="paperA")
    g.add_statement(Statement(statement="Glitches inflate the noise background.", id="c1"))
    g.add_statement(Statement(statement="The null stream enables self-sliding.", id="c2"))
    g.add_statement(Statement(statement="Reported FAR values are untrustworthy.", id="c3"))
    save_graph(g, tmp_path / "A.json")
    return tmp_path


def test_embed_is_incremental(tmp_path):
    """Embed vectors missing statements once, then no-ops until text changes.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    root = _library(tmp_path)
    emb = FakeEmbedder()
    with Library(root) as lib:
        lib.index()
        assert lib.embed(emb) == 3  # all three embedded
        assert lib.embed(emb) == 0  # nothing changed

        # Edit one statement's text -> reindex -> exactly one re-embed.
        g = ProvenanceGraph(article_id="paperA")
        g.add_statement(Statement(statement="Glitches inflate the noise background.", id="c1"))
        g.add_statement(Statement(statement="The null stream enables self-sliding.", id="c2"))
        g.add_statement(Statement(statement="Reported FAR values are now revised.", id="c3"))
        save_graph(g, root / "A.json")
        lib.index()
        assert lib.embed(emb) == 1


def test_semantic_search_ranks_by_meaning(tmp_path):
    """semantic_search returns the closest statement first for a themed query.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    root = _library(tmp_path)
    emb = FakeEmbedder()
    with Library(root) as lib:
        lib.index()
        lib.embed(emb)
        hits = lib.semantic_search("background noise from glitches", emb, k=3)
        assert hits[0].gid == "paperA#c1"  # noise/glitch theme

        null_hits = lib.semantic_search("null-stream self-sliding method", emb, k=1)
        assert null_hits[0].gid == "paperA#c2"


def test_semantic_search_is_model_scoped(tmp_path):
    """Vectors from a different model name are not used for search.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    root = _library(tmp_path)
    with Library(root) as lib:
        lib.index()
        lib.embed(FakeEmbedder())

        class OtherModel(FakeEmbedder):
            name = "other-v9"

        assert lib.semantic_search("noise", OtherModel(), k=3) == []  # no vectors for this model yet


@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is not None,
    reason="the [semantic] extra is installed, so the missing-dependency path can't be exercised",
)
def test_find_semantic_without_extra_errors(tmp_path):
    """Find --semantic fails with a clear message when the extra is absent.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    from typer.testing import CliRunner

    from ideagraph.cli.main import app

    runner = CliRunner()
    root = _library(tmp_path)
    r = runner.invoke(app, ["find", str(root), "noise", "--semantic"])
    assert r.exit_code == 1
    assert "semantic" in r.stderr.lower()
