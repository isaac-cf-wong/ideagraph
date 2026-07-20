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

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from ideagraph.core import ProvenanceGraph
from ideagraph.core.identity import global_id
from ideagraph.core.staleness import compute_digest
from ideagraph.persistence import load_graph
from ideagraph.semantic import cosine, normalize, text_hash

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
CREATE TABLE IF NOT EXISTS embeddings (
    gid        TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    model      TEXT NOT NULL,
    text_hash  TEXT NOT NULL,
    vector     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_embeddings_article ON embeddings (article_id);
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
        # Embeddings are intentionally NOT dropped here: they survive a reindex so
        # unchanged statements keep their vectors (embed() re-embeds only changed
        # text and prunes orphans whose statement no longer exists).

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

    def get_statement(self, gid: str) -> SearchHit | None:
        """Return the indexed statement with this global id, or None.

        Args:
            gid: The statement's global id.

        Returns:
            The statement as a :class:`SearchHit`, or None if not indexed.
        """
        row = self._conn.execute(
            "SELECT gid, article_id, node_id, stype, text FROM statements WHERE gid = ?", (gid,)
        ).fetchone()
        if row is None:
            return None
        return SearchHit(row["gid"], row["article_id"], row["node_id"], row["stype"], row["text"])

    def unsupported_assertions(self) -> list[SearchHit]:
        """Return asserting statements (claim/finding/result) left unresolved.

        These are library-wide support gaps carried in each statement's status —
        an assertion that has not been resolved against evidence.

        Returns:
            The unresolved assertion statements.
        """
        rows = self._conn.execute(
            "SELECT gid, article_id, node_id, stype, text FROM statements "
            "WHERE stype IN ('claim', 'finding', 'result') AND status = 'unresolved' "
            "ORDER BY article_id, ord"
        ).fetchall()
        return [SearchHit(r["gid"], r["article_id"], r["node_id"], r["stype"], r["text"]) for r in rows]

    def path(self, src_gid: str, dst_gid: str, *, max_depth: int = 8) -> list[str] | None:
        """Find a shortest directed path of idea edges from src to dst.

        Follows edges in their asserted direction (subject -> object). Both
        intra-article and cross-article edges are traversable.

        Args:
            src_gid: Starting statement global id.
            dst_gid: Target statement global id.
            max_depth: Maximum path length to search.

        Returns:
            The sequence of global ids from src to dst (inclusive), or None if no
            path of length <= ``max_depth`` exists.
        """
        if src_gid == dst_gid:
            return [src_gid]
        frontier: list[list[str]] = [[src_gid]]
        seen = {src_gid}
        for _ in range(max_depth):
            nxt: list[list[str]] = []
            for trail in frontier:
                for edge in self.neighbors(trail[-1], direction="out"):
                    if edge.dst_gid == dst_gid:
                        return [*trail, dst_gid]
                    if edge.dst_gid not in seen:
                        seen.add(edge.dst_gid)
                        nxt.append([*trail, edge.dst_gid])
            if not nxt:
                break
            frontier = nxt
        return None

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

    def snapshot(self) -> dict:
        """Return the whole library as a front-end-ready node/edge payload.

        Nodes are every indexed statement (keyed by global id, grouped by
        article); edges are the idea-level intra- and cross-article links. Cross
        edges whose target is not indexed are still included (so dangling links
        are visible), flagged via ``dangling``.

        Returns:
            A dict with ``articles``, ``nodes``, ``edges``, and ``counts``.
        """
        articles = [
            {"id": r["article_id"], "title": r["title"]}
            for r in self._conn.execute("SELECT article_id, title FROM articles ORDER BY article_id")
        ]
        nodes = [
            {
                "id": r["gid"],
                "article": r["article_id"],
                "node": r["node_id"],
                "stype": r["stype"],
                "status": r["status"],
                "text": r["text"],
            }
            for r in self._conn.execute(
                "SELECT gid, article_id, node_id, stype, status, text FROM statements ORDER BY article_id, ord"
            )
        ]
        known = {n["id"] for n in nodes}
        edges = [
            {
                "source": r["src_gid"],
                "target": r["dst_gid"],
                "predicate": r["predicate"],
                "kind": r["kind"],
                "dangling": r["kind"] == "cross" and r["dst_gid"] not in known,
            }
            for r in self._conn.execute("SELECT src_gid, dst_gid, predicate, kind FROM edges")
        ]
        return {
            "articles": articles,
            "nodes": nodes,
            "edges": edges,
            "counts": {
                "articles": len(articles),
                "statements": len(nodes),
                "cross_edges": sum(1 for e in edges if e["kind"] == "cross"),
            },
        }

    # -- semantic search (optional) --------------------------------------

    def embed(self, embedder, *, rebuild: bool = False) -> int:  # type: ignore[no-untyped-def]
        """Embed statements that are missing a current vector for this model.

        Incremental: a statement is (re)embedded only when it has no vector for
        ``embedder.name``, or its text changed since it was last embedded (or
        ``rebuild`` is set). Vectors are stored normalised.

        Args:
            embedder: An object with ``name`` and ``embed(texts) -> vectors``.
            rebuild: Re-embed every statement regardless of existing vectors.

        Returns:
            The number of statements embedded in this call.
        """
        # Drop vectors whose statement no longer exists (removed article / node).
        self._conn.execute("DELETE FROM embeddings WHERE gid NOT IN (SELECT gid FROM statements)")
        existing = {
            row["gid"]: row["text_hash"]
            for row in self._conn.execute("SELECT gid, text_hash FROM embeddings WHERE model = ?", (embedder.name,))
        }
        todo = []
        for row in self._conn.execute("SELECT gid, article_id, text FROM statements"):
            th = text_hash(row["text"] or "")
            if rebuild or existing.get(row["gid"]) != th:
                todo.append((row["gid"], row["article_id"], row["text"] or "", th))
        if not todo:
            return 0
        vectors = embedder.embed([t[2] for t in todo])
        for (gid, article_id, _text, th), vec in zip(todo, vectors, strict=True):
            unit = normalize([float(x) for x in vec])
            self._conn.execute(
                "INSERT INTO embeddings (gid, article_id, model, text_hash, vector) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(gid) DO UPDATE SET model=excluded.model, text_hash=excluded.text_hash, "
                "vector=excluded.vector, article_id=excluded.article_id",
                (gid, article_id, embedder.name, th, json.dumps(unit)),
            )
        self._conn.commit()
        return len(todo)

    def semantic_search(self, query: str, embedder, *, k: int = 10) -> list[SearchHit]:  # type: ignore[no-untyped-def]
        """Rank statements by embedding similarity to a query.

        Only vectors produced by ``embedder.name`` are considered; call
        :meth:`embed` first so the index is populated. Similarity is cosine over
        the stored normalised vectors.

        Args:
            query: The free-text query.
            embedder: The embedder (its ``name`` selects which vectors to use).
            k: Maximum number of hits to return.

        Returns:
            The best-matching statements, most similar first.
        """
        qvec = normalize([float(x) for x in embedder.embed([query])[0]])
        scored: list[tuple[float, str]] = []
        for row in self._conn.execute("SELECT gid, vector FROM embeddings WHERE model = ?", (embedder.name,)):
            scored.append((cosine(qvec, json.loads(row["vector"])), row["gid"]))
        scored.sort(key=lambda s: s[0], reverse=True)
        hits = []
        for _score, gid in scored[:k]:
            hit = self.get_statement(gid)
            if hit is not None:
                hits.append(hit)
        return hits

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
