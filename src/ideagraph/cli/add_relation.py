# ruff: noqa: PLC0415
"""The ``ideagraph add-relation`` command."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from ideagraph.core import NodeType, ProvenancePredicate

if TYPE_CHECKING:
    from ideagraph.kg import KnowledgeGraph

#: Node types ideagraph stores and can therefore verify an id against. ARTEFACT
#: and AGENT nodes are not held in the graph (they appear only as edge
#: endpoints), so an id of those types is accepted without an existence check.
_STORED_TYPES = (NodeType.CLAIM, NodeType.EVIDENCE, NodeType.ACTIVITY)


def _category(graph: KnowledgeGraph, node_id: str) -> NodeType | None:
    """Infer a stored node's :class:`NodeType` category from its id.

    Args:
        graph: The knowledge graph to search.
        node_id: The id to look up.

    Returns:
        ``NodeType.CLAIM`` for any statement node, ``EVIDENCE`` / ``ACTIVITY``
        for those node types, or None if no stored node has that id.
    """
    from ideagraph.kg.profiles import STATEMENT_TYPES

    node = graph.nodes.get(node_id)
    if node is None:
        return None
    if node.type in set(STATEMENT_TYPES):
        return NodeType.CLAIM
    if node.type == "evidence":
        return NodeType.EVIDENCE
    if node.type == "activity":
        return NodeType.ACTIVITY
    return None


def _resolve_type(graph: KnowledgeGraph, node_id: str, explicit: NodeType | None, role: str) -> None:
    """Validate an endpoint, resolving its type from a flag or by detection.

    Args:
        graph: The knowledge graph.
        node_id: The node id.
        explicit: A type passed on the command line, or None to auto-detect.
        role: ``"subject"`` or ``"object"``, for error messages.

    Raises:
        typer.Exit: If the type cannot be resolved or a stored node is absent.
    """
    node_type = explicit or _category(graph, node_id)
    if node_type is None:
        typer.echo(
            f"Cannot determine {role} type for {node_id!r}; pass --{role}-type "
            f"(no stored claim/evidence/activity has that id).",
            err=True,
        )
        raise typer.Exit(code=1)
    if node_type in _STORED_TYPES and _category(graph, node_id) != node_type:
        typer.echo(f"No such {node_type.value}: {node_id}", err=True)
        raise typer.Exit(code=1)


def add_relation_command(
    path: Annotated[Path, typer.Argument(help="Path to a knowledge graph JSON file.")],
    subject_id: Annotated[str, typer.Argument(help="Id of the subject (source) node.")],
    object_id: Annotated[str, typer.Argument(help="Id of the object (target) node.")],
    predicate: Annotated[
        ProvenancePredicate,
        typer.Option("--predicate", help="The typed relationship from subject to object."),
    ],
    subject_type: Annotated[
        NodeType | None,
        typer.Option("--subject-type", help="Subject node type (auto-detected if omitted)."),
    ] = None,
    object_type: Annotated[
        NodeType | None,
        typer.Option("--object-type", help="Object node type (auto-detected if omitted)."),
    ] = None,
) -> None:
    """Add a typed edge between two nodes and print its id.

    The subject/object types are auto-detected from their ids when the nodes are
    stored in the graph (statements, evidence, activities); pass
    ``--subject-type`` / ``--object-type`` for artefact or agent endpoints, which
    the graph does not store. Examples: link evidence to the activity that
    produced it (``--predicate generated_by``), or attach existing evidence to a
    second claim (``--predicate supported_by``).

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        subject_id: Id of the subject (source) node.
        object_id: Id of the object (target) node.
        predicate: The typed relationship from subject to object.
        subject_type: Explicit subject type, or None to auto-detect.
        object_type: Explicit object type, or None to auto-detect.
    """
    from logging import getLogger

    from ideagraph.kg import Edge
    from ideagraph.kg.persistence import load_graph, save_graph

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    graph = load_graph(path)
    _resolve_type(graph, subject_id, subject_type, "subject")
    _resolve_type(graph, object_id, object_type, "object")

    edge = Edge(type=predicate.value, source=subject_id, target=object_id)
    graph.add_edge(edge)
    save_graph(graph, path)

    logger.info("Added relation %s: %s %s %s", edge.id, subject_id, predicate.value, object_id)
    typer.echo(edge.id)
