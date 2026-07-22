# ruff: noqa: PLC0415
"""The ``ideagraph add-evidence`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ideagraph.core import EvidenceKind, EvidenceRelation

#: How an evidence relation maps to the edge type that links the claim to the
#: evidence.
_RELATION_TO_EDGE_TYPE = {
    EvidenceRelation.SUPPORTS: "supported_by",
    EvidenceRelation.REFUTES: "refuted_by",
    EvidenceRelation.CONTEXTUAL: "relates_to",
}


def add_evidence_command(
    path: Annotated[Path, typer.Argument(help="Path to a knowledge graph JSON file.")],
    claim_id: Annotated[
        str | None,
        typer.Argument(help="Id of a claim this evidence bears on (omit to register standalone)."),
    ] = None,
    kind: Annotated[EvidenceKind, typer.Option("--kind", help="The kind of artefact.")] = EvidenceKind.OTHER,
    reference: Annotated[str, typer.Option("--reference", help="Pointer to the artefact (path/URL/DOI/commit).")] = "",
    relation: Annotated[
        EvidenceRelation,
        typer.Option("--relation", help="How the evidence bears on the claim(s)."),
    ] = EvidenceRelation.SUPPORTS,
    to_claim: Annotated[
        list[str] | None,
        typer.Option("--to-claim", help="Id of a further claim to link the same evidence to. Repeatable."),
    ] = None,
    evidence_id: Annotated[
        str | None,
        typer.Option("--id", help="Explicit evidence id. A UUID is generated if omitted."),
    ] = None,
    digest: Annotated[
        str | None,
        typer.Option("--digest", help="Content digest of the artefact, for staleness detection."),
    ] = None,
    auto_digest: Annotated[
        bool,
        typer.Option("--auto-digest", help="Compute the digest by hashing the reference as a file path."),
    ] = False,
    description: Annotated[
        str,
        typer.Option("--description", help="Human-readable note about the evidence."),
    ] = "",
    meta: Annotated[
        list[str] | None,
        typer.Option("--meta", help="A KEY=VALUE metadata entry. Repeatable."),
    ] = None,
    meta_json: Annotated[
        list[str] | None,
        typer.Option("--meta-json", help="A KEY=JSON metadata entry (structured value). Repeatable."),
    ] = None,
    created_at: Annotated[
        str | None,
        typer.Option("--created-at", help="ISO-8601 creation timestamp (defaults to now)."),
    ] = None,
) -> None:
    """Add a piece of evidence and link it to zero or more claims, printing its id.

    The evidence can bear on the positional claim, on additional ``--to-claim``
    claims (so one artefact can support several claims), or on none at all (a
    standalone artefact to be linked later with ``add-relation``). Each linked
    claim gets a supporting/refuting/contextual edge matching ``--relation``.

    Args:
        path: Path to a graph JSON file produced by ideagraph.
        claim_id: Id of a claim the evidence bears on, or None for standalone.
        kind: The kind of artefact referenced.
        reference: A pointer to the artefact.
        relation: How the evidence bears on the claim(s).
        to_claim: Ids of further claims to link the same evidence to.
        evidence_id: An explicit id for the evidence, or None to generate one.
        digest: An optional content digest of the artefact.
        auto_digest: Compute the digest by hashing the reference as a file path.
        description: An optional human-readable note.
        meta: Repeatable ``KEY=VALUE`` metadata entries.
        meta_json: Repeatable ``KEY=JSON`` metadata entries (structured values).
        created_at: An explicit ISO-8601 creation timestamp, or None for now.
    """
    from logging import getLogger

    from ideagraph.cli._options import merged_metadata, parse_datetime
    from ideagraph.core.staleness import hash_file
    from ideagraph.kg import Edge, Node
    from ideagraph.kg.persistence import load_graph, save_graph
    from ideagraph.kg.profiles import STATEMENT_TYPES

    logger = getLogger("ideagraph")

    if not path.exists():
        typer.echo(f"No such file: {path}", err=True)
        raise typer.Exit(code=1)

    if auto_digest:
        if digest is not None:
            typer.echo("Pass either --digest or --auto-digest, not both", err=True)
            raise typer.Exit(code=1)
        ref_path = Path(reference)
        if not ref_path.exists():
            typer.echo(f"--auto-digest needs the reference to be a file path; no such file: {reference}", err=True)
            raise typer.Exit(code=1)
        digest = hash_file(ref_path)

    graph = load_graph(path)
    statement_types = set(STATEMENT_TYPES)

    # De-duplicated, order-preserving list of claims to link to (may be empty).
    targets = list(dict.fromkeys([c for c in [claim_id, *(to_claim or [])] if c]))
    for target in targets:
        node = graph.nodes.get(target)
        if node is None or node.type not in statement_types:
            typer.echo(f"No such statement: {target}", err=True)
            raise typer.Exit(code=1)
    if evidence_id is not None and evidence_id in graph.nodes:
        typer.echo(f"Evidence with id {evidence_id} already exists", err=True)
        raise typer.Exit(code=1)

    evidence = Node(
        type="evidence",
        text=description,
        properties={
            "kind": kind.value,
            "reference": reference,
            "relation": relation.value,
            "digest": digest,
            "metadata": merged_metadata(meta, meta_json),
        },
    )
    if evidence_id is not None:
        evidence.id = evidence_id
    created = parse_datetime(created_at, "--created-at")
    if created is not None:
        evidence.created_at = created
    graph.add_node(evidence)
    edge_type = _RELATION_TO_EDGE_TYPE[relation]
    for target in targets:
        graph.add_edge(Edge(type=edge_type, source=target, target=evidence.id))
    save_graph(graph, path)

    linked = ", ".join(targets) if targets else "(standalone)"
    logger.info("Added evidence %s (%s) -> %s", evidence.id, relation.value, linked)
    typer.echo(evidence.id)
