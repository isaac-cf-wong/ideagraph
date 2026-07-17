# ruff: noqa: PLC0415
"""The ``claimkit add-evidence`` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from claimkit.core import EvidenceKind, EvidenceRelation, ProvenancePredicate

#: How an evidence relation maps to the provenance edge predicate that links the
#: claim to the evidence.
_RELATION_TO_PREDICATE = {
    EvidenceRelation.SUPPORTS: ProvenancePredicate.SUPPORTED_BY,
    EvidenceRelation.REFUTES: ProvenancePredicate.REFUTED_BY,
    EvidenceRelation.CONTEXTUAL: ProvenancePredicate.RELATES_TO,
}


def add_evidence_command(
    path: Annotated[Path, typer.Argument(help="Path to a provenance graph JSON file.")],
    claim_id: Annotated[str, typer.Argument(help="Id of the claim this evidence bears on.")],
    kind: Annotated[EvidenceKind, typer.Option("--kind", help="The kind of artefact.")],
    reference: Annotated[str, typer.Option("--reference", help="Pointer to the artefact (path/URL/DOI/commit).")],
    relation: Annotated[
        EvidenceRelation,
        typer.Option("--relation", help="How the evidence bears on the claim."),
    ] = EvidenceRelation.SUPPORTS,
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
) -> None:
    """Add a piece of evidence to a claim and link it, printing the evidence id.

    A supporting/refuting/contextual relation is recorded both on the evidence
    and as the matching provenance edge from the claim to the evidence.

    Args:
        path: Path to a graph JSON file produced by claimkit.
        claim_id: Id of the claim the evidence bears on.
        kind: The kind of artefact referenced.
        reference: A pointer to the artefact.
        relation: How the evidence bears on the claim.
        evidence_id: An explicit id for the evidence, or None to generate one.
        digest: An optional content digest of the artefact.
        auto_digest: Compute the digest by hashing the reference as a file path.
        description: An optional human-readable note.
        meta: Repeatable ``KEY=VALUE`` metadata entries.
    """
    from logging import getLogger

    from claimkit.cli._options import parse_meta
    from claimkit.core import Evidence, NodeType, ProvenanceRelation, hash_file
    from claimkit.persistence import load_graph, save_graph

    logger = getLogger("claimkit")

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

    if claim_id not in graph.claims:
        typer.echo(f"No such claim: {claim_id}", err=True)
        raise typer.Exit(code=1)
    if evidence_id is not None and evidence_id in graph.evidence:
        typer.echo(f"Evidence with id {evidence_id} already exists", err=True)
        raise typer.Exit(code=1)

    evidence = Evidence(
        claim_id=claim_id,
        kind=kind,
        reference=reference,
        relation=relation,
        description=description,
        digest=digest,
        metadata=parse_meta(meta),
    )
    if evidence_id is not None:
        evidence.id = evidence_id
    graph.add_evidence(evidence)
    graph.add_relation(
        ProvenanceRelation(
            subject_type=NodeType.CLAIM,
            subject_id=claim_id,
            predicate=_RELATION_TO_PREDICATE[relation],
            object_type=NodeType.EVIDENCE,
            object_id=evidence.id,
        )
    )
    save_graph(graph, path)

    logger.info("Added evidence %s (%s) to claim %s", evidence.id, relation.value, claim_id)
    typer.echo(evidence.id)
