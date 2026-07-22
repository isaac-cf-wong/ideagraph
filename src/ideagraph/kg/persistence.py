"""Saving and loading a KnowledgeGraph as JSON, with legacy compatibility.

Documents are wrapped in a versioned envelope ``{schema_version, graph}``.
Schema version 4 is the generic ``{nodes, edges}`` shape; versions 1-3 are the
legacy five-collection provenance shape, which is transparently converted on
load via :func:`~ideagraph.kg.profiles.research_compat.graph_from_legacy`, so
files written by the old core still open.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ideagraph.kg.graph import KnowledgeGraph
from ideagraph.kg.profiles.research_compat import graph_from_legacy

#: Current on-disk schema version (generic nodes/edges shape).
SCHEMA_VERSION = 4

#: Highest legacy version that used the five-collection provenance shape.
_LEGACY_MAX = 3


def graph_to_document(graph: KnowledgeGraph) -> dict[str, Any]:
    """Wrap a graph's serialised form in a versioned envelope.

    Args:
        graph: The graph to wrap.

    Returns:
        A dictionary with ``schema_version`` and ``graph`` keys.

    """
    return {"schema_version": SCHEMA_VERSION, "graph": graph.to_dict()}


def graph_from_document(document: dict[str, Any]) -> KnowledgeGraph:
    """Reconstruct a graph from a versioned envelope (any supported version).

    Args:
        document: A dictionary with ``schema_version`` and ``graph``.

    Returns:
        The reconstructed generic graph.

    Raises:
        KeyError: If the envelope is missing required keys.
        ValueError: If the ``schema_version`` is newer than supported.

    """
    version = document["schema_version"]
    graph = document["graph"]
    if version > SCHEMA_VERSION:
        raise ValueError(
            f"document schema_version {version} is newer than supported version {SCHEMA_VERSION}; upgrade ideagraph"
        )
    if version <= _LEGACY_MAX:
        return graph_from_legacy(graph)
    return KnowledgeGraph.from_dict(graph)


def dumps_graph(graph: KnowledgeGraph, *, indent: int = 2) -> str:
    """Serialise a graph to a JSON string.

    Args:
        graph: The graph to serialise.
        indent: Indentation passed to :func:`json.dumps`.

    Returns:
        The JSON document.

    """
    return json.dumps(graph_to_document(graph), indent=indent, ensure_ascii=False)


def loads_graph(text: str) -> KnowledgeGraph:
    """Deserialise a graph from a JSON string.

    Args:
        text: A JSON document as produced by :func:`dumps_graph` (or a legacy
            document from the old core).

    Returns:
        The reconstructed graph.

    """
    return graph_from_document(json.loads(text))


def save_graph(graph: KnowledgeGraph, path: str | Path, *, indent: int = 2) -> None:
    """Write a graph to a JSON file, creating parent directories as needed.

    Args:
        graph: The graph to save.
        path: Destination file path.
        indent: Indentation passed to :func:`json.dumps`.

    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dumps_graph(graph, indent=indent) + "\n", encoding="utf-8")


def load_graph(path: str | Path) -> KnowledgeGraph:
    """Read a graph from a JSON file (generic or legacy).

    Args:
        path: Source file path.

    Returns:
        The reconstructed graph.

    """
    return loads_graph(Path(path).read_text(encoding="utf-8"))
