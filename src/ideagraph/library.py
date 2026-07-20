"""The library: a SQLite index over a directory of article graphs.

Individual article graphs are the source of truth (one JSON file each). The
library is a *derived, disposable* index over a whole directory of them, so that
ideas can be discovered and navigated across articles at scale — the payoff of
the global ``article_id#node_id`` identity introduced in Phase B.

The index holds three things: the statements of every article (for full-text
search), the idea-level edges between them (discourse links within an article and
cross-article references), and a content hash per article so re-indexing only
touches files that changed. Nothing here is authoritative: delete the database
and :meth:`Library.index` rebuilds it from the JSON files.

Only graphs that declare an ``article_id`` are indexed — a statement needs a
global address to be a search hit or an edge endpoint. Files without one are
reported as skipped so the gap is visible rather than silent.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from ideagraph.core import ProvenanceGraph
from ideagraph.core.identity import global_id
from ideagraph.core.staleness import compute_digest
from ideagraph.persistence import load_graph

#: Default location of the index database, relative to the library root.
DEFAULT_DB_RELPATH = ".ideagraph/index.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    article_id   TEXT PRIMARY KEY,
    path         TEXT NOT NULL,
    title        TEXT,
    content_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS statements (
    gid        TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    node_id    TEXT NOT NULL,
    stype      TEXT,
    status     TEXT,
    section    TEXT,
    ord        INTEGER,
    text       TEXT,
    FOREIGN KEY (article_id) REFERENCES articles (article_id)
);
CREATE INDEX IF NOT EXISTS ix_statements_article ON statements (article_id);
CREATE TABLE IF NOT EXISTS edges (
    src_gid    TEXT NOT NULL,
    dst_gid    TEXT NOT NULL,
    predicate  TEXT NOT NULL,
    kind       TEXT NOT NULL,
    article_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_edges_src ON edges (src_gid);
CREATE INDEX IF NOT EXISTS ix_edges_dst ON edges (dst_gid);
CREATE INDEX IF NOT EXISTS ix_edges_article ON edges (article_id);
CREATE VIRTUAL TABLE IF NOT EXISTS statements_fts USING fts5 (
    gid UNINDEXED, article_id UNINDEXED, text
);
"""


@dataclass
class IndexResult:
    """Outcome of an :meth:`Library.index` run.

    Attributes:
        indexed: Article ids (re)indexed because their content changed.
        unchanged: Article ids skipped because their content hash matched.
        skipped_no_article: Paths skipped because the graph has no ``article_id``.
        removed: Article ids dropped because their file no longer exists.
    """

    indexed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped_no_article: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SearchHit:
    """A full-text search match.

    Attributes:
        gid: The statement's global id.
        article_id: The owning article.
        node_id: The statement's local id.
        stype: The statement's rhetorical type.
        text: The statement text.
    """

    gid: str
    article_id: str
    node_id: str
    stype: str
    text: str


@dataclass(frozen=True)
class Edge:
    """An idea-level edge in the index.

    Attributes:
        src_gid: Source statement global id.
        dst_gid: Target statement global id.
        predicate: The relationship token.
        kind: ``"intra"`` (within an article) or ``"cross"`` (between articles).
        article_id: The article that asserts the edge.
    """

    src_gid: str
    dst_gid: str
    predicate: str
    kind: str
    article_id: str


class Library:
    """A SQLite index over a directory tree of article graph JSON files."""

    def __init__(self, root: str | Path, db_path: str | Path | None = None) -> None:
        """Open (or create) a library rooted at a directory.

        Args:
            root: Directory tree to scan for ``*.json`` article graphs.
            db_path: Index database location. Defaults to
                ``<root>/.ideagraph/index.db``.
        """
        self.root = Path(root)
        self.db_path = Path(db_path) if db_path is not None else self.root / DEFAULT_DB_RELPATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    def __enter__(self) -> Library:
        """Enter a context manager, returning self."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the connection on context-manager exit."""
        self.close()

    # -- indexing ---------------------------------------------------------

    def _discover(self) -> list[Path]:
        """Return candidate graph files under the root (excluding the db dir)."""
        db_dir = self.db_path.parent.resolve()
        out = []
        for p in sorted(self.root.rglob("*.json")):
            if db_dir in p.resolve().parents or p.resolve().parent == db_dir:
                continue
            out.append(p)
        return out

    @staticmethod
    def _read_graph(path: Path) -> ProvenanceGraph | None:
        """Load a file as a graph, or return None if it is not one."""
        try:
            return load_graph(path)
        except (ValueError, KeyError, OSError, UnicodeDecodeError):
            return None

    def index(self, *, rebuild: bool = False) -> IndexResult:
        """Scan the root and (re)index changed article graphs.

        Only files whose content hash changed are re-indexed, unless ``rebuild``
        forces a full pass. Graphs without an ``article_id`` are skipped; article
        entries whose file has disappeared are removed.

        Args:
            rebuild: Re-index every article regardless of content hash.

        Returns:
            An :class:`IndexResult` summarising what changed.
        """
        result = IndexResult()
        existing = {row["article_id"]: row["content_hash"] for row in self._conn.execute("SELECT * FROM articles")}
        seen: set[str] = set()

        for path in self._discover():
            raw = path.read_bytes()
            content_hash = compute_digest(raw)
            graph = self._read_graph(path)
            if graph is None or graph.article_id is None:
                if graph is not None and graph.article_id is None:
                    result.skipped_no_article.append(str(path))
                continue
            article_id = graph.article_id
            seen.add(article_id)
            if not rebuild and existing.get(article_id) == content_hash:
                result.unchanged.append(article_id)
                continue
            self._reindex_article(article_id, path, graph, content_hash)
            result.indexed.append(article_id)

        for article_id in existing:
            if article_id not in seen:
                self._delete_article(article_id)
                result.removed.append(article_id)

        self._conn.commit()
        return result

    def _delete_article(self, article_id: str) -> None:
        """Remove all index rows belonging to an article."""
        self._conn.execute("DELETE FROM statements_fts WHERE article_id = ?", (article_id,))
        self._conn.execute("DELETE FROM statements WHERE article_id = ?", (article_id,))
        self._conn.execute("DELETE FROM edges WHERE article_id = ?", (article_id,))
        self._conn.execute("DELETE FROM articles WHERE article_id = ?", (article_id,))

    def _reindex_article(self, article_id: str, path: Path, graph: ProvenanceGraph, content_hash: str) -> None:
        """Replace an article's rows with a fresh index of its graph."""
        self._delete_article(article_id)
        self._conn.execute(
            "INSERT INTO articles (article_id, path, title, content_hash) VALUES (?, ?, ?, ?)",
            (article_id, str(path), graph.metadata.get("title"), content_hash),
        )
        for node_id, s in graph.statements.items():
            gid = global_id(article_id, node_id)
            self._conn.execute(
                "INSERT INTO statements (gid, article_id, node_id, stype, status, section, ord, text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (gid, article_id, node_id, s.type.value, s.status.value, s.section, s.order, s.statement),
            )
            self._conn.execute(
                "INSERT INTO statements_fts (gid, article_id, text) VALUES (?, ?, ?)",
                (gid, article_id, s.statement),
            )
        insert_edge = "INSERT INTO edges (src_gid, dst_gid, predicate, kind, article_id) VALUES (?, ?, ?, ?, ?)"
        # Idea-level intra edges: statement -> statement discourse links only.
        for rel in graph.relations.values():
            if rel.subject_id in graph.statements and rel.object_id in graph.statements:
                src = global_id(article_id, rel.subject_id)
                dst = global_id(article_id, rel.object_id)
                self._conn.execute(insert_edge, (src, dst, rel.predicate.value, "intra", article_id))
        for xref in graph.cross_references.values():
            if xref.subject_id in graph.statements:
                src = global_id(article_id, xref.subject_id)
                self._conn.execute(insert_edge, (src, xref.target, xref.predicate.value, "cross", article_id))

    # -- queries ----------------------------------------------------------

    def article_ids(self) -> set[str]:
        """Return the set of article ids currently held in the index."""
        return {row["article_id"] for row in self._conn.execute("SELECT article_id FROM articles")}

    def statement_gids(self) -> set[str]:
        """Return the set of statement global ids currently held in the index."""
        return {row["gid"] for row in self._conn.execute("SELECT gid FROM statements")}

    @staticmethod
    def _fts_query(query: str) -> str:
        """Turn free text into a safe FTS5 MATCH expression.

        Each whitespace-separated token is wrapped in double quotes (with internal
        quotes doubled), so punctuation such as ``-`` in ``time-slides`` is matched
        literally instead of being read as an FTS operator. Tokens combine with the
        default implicit AND.
        """
        tokens = query.split()
        return " ".join('"' + t.replace('"', '""') + '"' for t in tokens)

    def search(self, query: str, *, limit: int = 50) -> list[SearchHit]:
        """Full-text search statement text across the library.

        The query is treated as free text: each token is matched literally and
        tokens are combined with AND. Returns nothing for an empty query.

        Args:
            query: Free-text search terms.
            limit: Maximum number of hits to return.

        Returns:
            Matching statements, best-ranked first.
        """
        match = self._fts_query(query)
        if not match:
            return []
        rows = self._conn.execute(
            "SELECT s.gid, s.article_id, s.node_id, s.stype, s.text "
            "FROM statements_fts f JOIN statements s ON s.gid = f.gid "
            "WHERE statements_fts MATCH ? ORDER BY rank LIMIT ?",
            (match, limit),
        ).fetchall()
        return [SearchHit(r["gid"], r["article_id"], r["node_id"], r["stype"], r["text"]) for r in rows]

    def _edges(self, where: str, params: tuple) -> list[Edge]:
        """Run an edges query and map rows to :class:`Edge`.

        ``where`` is always an internal literal (never caller/user input); values
        are bound as parameters.
        """
        rows = self._conn.execute(
            f"SELECT src_gid, dst_gid, predicate, kind, article_id FROM edges WHERE {where}",  # noqa: S608 - literal
            params,
        ).fetchall()
        return [Edge(r["src_gid"], r["dst_gid"], r["predicate"], r["kind"], r["article_id"]) for r in rows]

    def neighbors(self, gid: str, *, direction: str = "both") -> list[Edge]:
        """Return edges touching a statement.

        Args:
            gid: The statement's global id.
            direction: ``"out"`` (edges from gid), ``"in"`` (edges to gid), or
                ``"both"``.

        Returns:
            The matching edges.
        """
        if direction == "out":
            return self._edges("src_gid = ?", (gid,))
        if direction == "in":
            return self._edges("dst_gid = ?", (gid,))
        return self._edges("src_gid = ? OR dst_gid = ?", (gid, gid))

    def backlinks(self, gid: str) -> list[Edge]:
        """Return edges pointing *at* a statement (incoming), across articles.

        Args:
            gid: The statement's global id.

        Returns:
            The incoming edges.
        """
        return self.neighbors(gid, direction="in")

    def dangling_cross_references(self) -> list[Edge]:
        """Return cross-article edges whose target statement is not in the index.

        These are the real dangling references — a link into another article at a
        node that does not (or no longer) exists. Resolvable only with the whole
        library in view, which is why single-graph ``doctor`` cannot find them.

        Returns:
            The dangling cross edges.
        """
        rows = self._conn.execute(
            "SELECT e.src_gid, e.dst_gid, e.predicate, e.kind, e.article_id FROM edges e "
            "WHERE e.kind = 'cross' AND NOT EXISTS (SELECT 1 FROM statements s WHERE s.gid = e.dst_gid)"
        ).fetchall()
        return [Edge(r["src_gid"], r["dst_gid"], r["predicate"], r["kind"], r["article_id"]) for r in rows]
