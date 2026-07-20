"""Tests for the SQLite library index over a directory of article graphs."""

from __future__ import annotations

from ideagraph import (
    CrossReference,
    Library,
    ProvenanceGraph,
    ProvenancePredicate,
    Statement,
)
from ideagraph.persistence import save_graph


def _article(root, article_id, statements, cross=None):
    """Write an article graph file under ``root`` and return its path.

    Args:
        root: Directory to write into.
        article_id: The article id.
        statements: Iterable of (node_id, text) pairs.
        cross: Optional iterable of (subject_id, predicate, target) triples.

    """
    g = ProvenanceGraph(article_id=article_id)
    for node_id, text in statements:
        g.add_statement(Statement(statement=text, id=node_id))
    for subject_id, predicate, target in cross or []:
        g.add_cross_reference(CrossReference(subject_id=subject_id, predicate=predicate, target=target))
    path = root / f"{article_id}.json"
    save_graph(g, path)
    return path


def test_index_and_search(tmp_path):
    """Indexing makes statements searchable and article ids visible.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    _article(tmp_path, "paperA", [("c1", "Time-slides fail in the signal-dominated regime.")])
    _article(tmp_path, "paperB", [("c1", "Glitches inflate the false-alarm rate.")])
    with Library(tmp_path) as lib:
        result = lib.index()
        assert set(result.indexed) == {"paperA", "paperB"}
        assert lib.article_ids() == {"paperA", "paperB"}
        hits = lib.search("time-slides")
        assert len(hits) == 1
        assert hits[0].gid == "paperA#c1"


def test_incremental_reindex(tmp_path):
    """A second index run skips unchanged files and re-indexes edited ones.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _article(tmp_path, "paperA", [("c1", "original wording")])
    with Library(tmp_path) as lib:
        assert lib.index().indexed == ["paperA"]
        again = lib.index()
        assert again.indexed == []
        assert again.unchanged == ["paperA"]

        _article(tmp_path, "paperA", [("c1", "changed wording")])  # overwrite same path
        third = lib.index()
        assert third.indexed == ["paperA"]
        assert lib.search("changed")[0].gid == "paperA#c1"
        assert lib.search("original") == []
    assert path.exists()


def test_removed_article_is_dropped(tmp_path):
    """Deleting a file removes its rows on the next index run.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    path = _article(tmp_path, "paperA", [("c1", "x")])
    with Library(tmp_path) as lib:
        lib.index()
        path.unlink()
        result = lib.index()
        assert result.removed == ["paperA"]
        assert lib.article_ids() == set()


def test_skips_graph_without_article_id(tmp_path):
    """A graph with no article_id is skipped and reported.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    g = ProvenanceGraph()  # no article_id
    g.add_statement(Statement(statement="orphan", id="c1"))
    save_graph(g, tmp_path / "orphan.json")
    with Library(tmp_path) as lib:
        result = lib.index()
        assert len(result.skipped_no_article) == 1
        assert lib.article_ids() == set()


def test_cross_edge_neighbors_backlinks_and_dangling(tmp_path):
    """Cross-article edges appear as neighbors/backlinks; missing targets dangle.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    _article(tmp_path, "paperB", [("f3", "A cited finding.")])
    _article(
        tmp_path,
        "paperA",
        [("c1", "Builds on prior work."), ("c2", "A missing target link.")],
        cross=[
            ("c1", ProvenancePredicate.BUILDS_ON, "paperB#f3"),
            ("c2", ProvenancePredicate.CITES, "paperB#ghost"),
        ],
    )
    with Library(tmp_path) as lib:
        lib.index()
        out = lib.neighbors("paperA#c1", direction="out")
        assert any(e.dst_gid == "paperB#f3" and e.kind == "cross" for e in out)
        assert any(e.src_gid == "paperA#c1" for e in lib.backlinks("paperB#f3"))

        dangling = lib.dangling_cross_references()
        assert len(dangling) == 1
        assert dangling[0].dst_gid == "paperB#ghost"


def test_rebuild_reindexes_everything(tmp_path):
    """--rebuild re-indexes even unchanged files.

    Args:
        tmp_path: Pytest temporary directory fixture.

    """
    _article(tmp_path, "paperA", [("c1", "x")])
    with Library(tmp_path) as lib:
        lib.index()
        assert lib.index(rebuild=True).indexed == ["paperA"]
