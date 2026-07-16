"""Exporting a provenance graph to `PROV-JSON <https://www.w3.org/submissions/prov-json/>`_.

PROV-JSON is a standard JSON serialisation of the `W3C PROV data model
<https://www.w3.org/TR/prov-dm/>`_. Exporting to it lets claimkit provenance be
consumed by the wider provenance ecosystem (validators, visualisers, stores).

The mapping is:

* :class:`~claimkit.core.claim.Claim` and
  :class:`~claimkit.core.evidence.Evidence` nodes -> ``prov:Entity``
* :class:`~claimkit.core.activity.Activity` nodes -> ``prov:Activity``
* edge endpoints typed :attr:`~claimkit.core.provenance.NodeType.ARTEFACT`
  -> ``prov:Entity`` stubs, and :attr:`~claimkit.core.provenance.NodeType.AGENT`
  -> ``prov:Agent`` stubs (they have no dedicated node model yet)
* edges map to the PROV relation that matches their predicate; the claimkit-only
  predicates (``SUPPORTED_BY``, ``REFUTED_BY``, ``REVIEWED_BY``, ``RELATES_TO``)
  have no PROV equivalent and are exported as ``wasInfluencedBy`` carrying a
  ``ck:predicate`` attribute so the original relationship is not lost.

All identifiers are emitted as qualified names in the ``ck`` namespace.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from claimkit.core.activity import Activity, ActivityKind
from claimkit.core.claim import Claim, ClaimStatus
from claimkit.core.evidence import Evidence, EvidenceKind, EvidenceRelation
from claimkit.core.graph import ProvenanceGraph
from claimkit.core.provenance import NodeType, ProvenancePredicate, ProvenanceRelation

#: Namespace prefix mapping emitted in the PROV-JSON document.
CK_NAMESPACE = "https://claimkit.dev/ns#"

#: Reverse of the supports/refutes/contextual -> predicate mapping, used to
#: recover an evidence's intrinsic relation from the edge that links it.
_PREDICATE_TO_RELATION = {
    ProvenancePredicate.SUPPORTED_BY: EvidenceRelation.SUPPORTS,
    ProvenancePredicate.REFUTED_BY: EvidenceRelation.REFUTES,
    ProvenancePredicate.RELATES_TO: EvidenceRelation.CONTEXTUAL,
}


def _qn(identifier: str) -> str:
    """Return the ``ck``-prefixed qualified name for an identifier.

    Args:
        identifier: A claimkit node or edge id.

    Returns:
        The qualified name, e.g. ``"ck:c1"``.

    """
    return f"ck:{identifier}"


def _relation_entry(subject: str, predicate: ProvenancePredicate, obj: str) -> tuple[str, dict[str, Any]]:
    """Map an edge to its PROV relation name and payload.

    Predicates with no PROV equivalent fall through to ``wasInfluencedBy``,
    which carries a ``ck:predicate`` attribute preserving the original relation.

    Args:
        subject: The ``ck``-qualified subject id.
        predicate: The edge predicate.
        obj: The ``ck``-qualified object id.

    Returns:
        A ``(relation_name, payload)`` pair for the PROV-JSON document.

    """
    if predicate is ProvenancePredicate.USED:
        return "used", {"prov:activity": subject, "prov:entity": obj}
    if predicate is ProvenancePredicate.GENERATED_BY:
        return "wasGeneratedBy", {"prov:entity": subject, "prov:activity": obj}
    if predicate is ProvenancePredicate.DERIVED_FROM:
        return "wasDerivedFrom", {"prov:generatedEntity": subject, "prov:usedEntity": obj}
    if predicate is ProvenancePredicate.ATTRIBUTED_TO:
        return "wasAttributedTo", {"prov:entity": subject, "prov:agent": obj}
    return "wasInfluencedBy", {
        "prov:influencee": subject,
        "prov:influencer": obj,
        "ck:predicate": predicate.value,
    }


def to_prov(graph: ProvenanceGraph) -> dict[str, Any]:
    """Convert a provenance graph to a PROV-JSON document.

    Args:
        graph: The graph to export.

    Returns:
        A PROV-JSON document as a plain dictionary.

    """
    entity: dict[str, Any] = {}
    activity: dict[str, Any] = {}
    agent: dict[str, Any] = {}

    for claim in graph.claims.values():
        entity[_qn(claim.id)] = {
            "prov:type": "ck:Claim",
            "ck:statement": claim.statement,
            "ck:status": claim.status.value,
        }
    for ev in graph.evidence.values():
        attrs = {
            "prov:type": "ck:Evidence",
            "ck:kind": ev.kind.value,
            "ck:reference": ev.reference,
        }
        if ev.digest is not None:
            attrs["ck:digest"] = ev.digest
        entity[_qn(ev.id)] = attrs
    for act in graph.activities.values():
        attrs = {"prov:type": "ck:Activity", "prov:label": act.label}
        if act.started_at is not None:
            attrs["prov:startTime"] = act.started_at.isoformat()
        if act.ended_at is not None:
            attrs["prov:endTime"] = act.ended_at.isoformat()
        activity[_qn(act.id)] = attrs

    # Collections keyed by NodeType so edge endpoints land in the right bucket.
    buckets = {
        NodeType.CLAIM: (entity, "ck:Claim"),
        NodeType.EVIDENCE: (entity, "ck:Evidence"),
        NodeType.ARTEFACT: (entity, "ck:Artefact"),
        NodeType.ACTIVITY: (activity, "ck:Activity"),
        NodeType.AGENT: (agent, "ck:Agent"),
    }

    def _ensure(node_type: NodeType, node_id: str) -> None:
        collection, prov_type = buckets[node_type]
        collection.setdefault(_qn(node_id), {"prov:type": prov_type})

    relations: dict[str, dict[str, Any]] = {
        "used": {},
        "wasGeneratedBy": {},
        "wasDerivedFrom": {},
        "wasAttributedTo": {},
        "wasInfluencedBy": {},
    }
    for edge in graph.relations.values():
        _ensure(edge.subject_type, edge.subject_id)
        _ensure(edge.object_type, edge.object_id)
        name, payload = _relation_entry(_qn(edge.subject_id), edge.predicate, _qn(edge.object_id))
        relations[name][_qn(edge.id)] = payload

    document: dict[str, Any] = {"prefix": {"ck": CK_NAMESPACE}}
    collections = [("entity", entity), ("activity", activity), ("agent", agent), *relations.items()]
    for name, collection in collections:
        if collection:
            document[name] = collection
    return document


def dumps_prov(graph: ProvenanceGraph, *, indent: int = 2) -> str:
    """Serialise a provenance graph to a PROV-JSON string.

    Args:
        graph: The graph to export.
        indent: Indentation passed to :func:`json.dumps`.

    Returns:
        The PROV-JSON document as a string.

    """
    return json.dumps(to_prov(graph), indent=indent, ensure_ascii=False)


def _local(qualified_name: str) -> str:
    """Strip the ``ck:`` prefix from a qualified name.

    Args:
        qualified_name: A PROV-JSON qualified name.

    Returns:
        The bare local identifier; names in other namespaces are returned
        unchanged.

    """
    return qualified_name[3:] if qualified_name.startswith("ck:") else qualified_name


# How each PROV relation container names its subject/object roles and which
# claimkit predicate it represents. ``wasInfluencedBy`` is handled separately
# because its predicate is carried in a ``ck:predicate`` attribute.
_RELATION_ROLES = {
    "used": ("prov:activity", "prov:entity", ProvenancePredicate.USED),
    "wasGeneratedBy": ("prov:entity", "prov:activity", ProvenancePredicate.GENERATED_BY),
    "wasDerivedFrom": ("prov:generatedEntity", "prov:usedEntity", ProvenancePredicate.DERIVED_FROM),
    "wasAttributedTo": ("prov:entity", "prov:agent", ProvenancePredicate.ATTRIBUTED_TO),
}


def _node_type_map(entities: dict[str, Any], activities: dict[str, Any], agents: dict[str, Any]) -> dict[str, NodeType]:
    """Map every qualified name in a document to its claimkit NodeType.

    Args:
        entities: The document's ``entity`` collection.
        activities: The document's ``activity`` collection.
        agents: The document's ``agent`` collection.

    Returns:
        A mapping from qualified name to :class:`NodeType`.

    """
    entity_types = {"ck:Claim": NodeType.CLAIM, "ck:Evidence": NodeType.EVIDENCE}
    node_types: dict[str, NodeType] = {
        qn: entity_types.get(attrs.get("prov:type"), NodeType.ARTEFACT) for qn, attrs in entities.items()
    }
    node_types.update(dict.fromkeys(activities, NodeType.ACTIVITY))
    node_types.update(dict.fromkeys(agents, NodeType.AGENT))
    return node_types


def _import_nodes(graph: ProvenanceGraph, entities: dict[str, Any], activities: dict[str, Any]) -> None:
    """Add claim, evidence, and activity nodes to a graph from PROV collections.

    Args:
        graph: The graph to populate.
        entities: The document's ``entity`` collection.
        activities: The document's ``activity`` collection.

    """
    for qn, attrs in entities.items():
        prov_type = attrs.get("prov:type")
        if prov_type == "ck:Claim":
            graph.add_claim(
                Claim(
                    statement=attrs.get("ck:statement", ""),
                    id=_local(qn),
                    status=ClaimStatus(attrs.get("ck:status", ClaimStatus.UNRESOLVED.value)),
                )
            )
        elif prov_type == "ck:Evidence":
            graph.add_evidence(
                Evidence(
                    claim_id="",
                    kind=EvidenceKind(attrs.get("ck:kind", EvidenceKind.OTHER.value)),
                    reference=attrs.get("ck:reference", ""),
                    id=_local(qn),
                    digest=attrs.get("ck:digest"),
                )
            )
    for qn, attrs in activities.items():
        activity = Activity(kind=ActivityKind.OTHER, label=attrs.get("prov:label", ""), id=_local(qn))
        if attrs.get("prov:startTime") is not None:
            activity.started_at = datetime.fromisoformat(attrs["prov:startTime"])
        if attrs.get("prov:endTime") is not None:
            activity.ended_at = datetime.fromisoformat(attrs["prov:endTime"])
        graph.add_activity(activity)


def _import_edges(graph: ProvenanceGraph, document: dict[str, Any], node_types: dict[str, NodeType]) -> None:
    """Add provenance edges to a graph from a document's relation collections.

    Args:
        graph: The graph to populate.
        document: The full PROV-JSON document.
        node_types: Mapping from qualified name to :class:`NodeType`.

    """

    def _add(subject_qn: str, predicate: ProvenancePredicate, object_qn: str, edge_qn: str) -> None:
        graph.add_relation(
            ProvenanceRelation(
                subject_type=node_types.get(subject_qn, NodeType.ARTEFACT),
                subject_id=_local(subject_qn),
                predicate=predicate,
                object_type=node_types.get(object_qn, NodeType.ARTEFACT),
                object_id=_local(object_qn),
                id=_local(edge_qn),
            )
        )

    for name, (subject_role, object_role, predicate) in _RELATION_ROLES.items():
        for edge_qn, payload in document.get(name, {}).items():
            _add(payload[subject_role], predicate, payload[object_role], edge_qn)
    for edge_qn, payload in document.get("wasInfluencedBy", {}).items():
        _add(
            payload["prov:influencee"],
            ProvenancePredicate(payload["ck:predicate"]),
            payload["prov:influencer"],
            edge_qn,
        )


def _backfill_evidence_links(graph: ProvenanceGraph) -> None:
    """Recover each evidence's claim_id and relation from its linking edge.

    Args:
        graph: The graph whose evidence nodes are updated in place.

    """
    for edge in graph.relations.values():
        if edge.object_type is not NodeType.EVIDENCE or edge.object_id not in graph.evidence:
            continue
        relation = _PREDICATE_TO_RELATION.get(edge.predicate)
        if relation is not None and edge.subject_type is NodeType.CLAIM:
            evidence = graph.evidence[edge.object_id]
            evidence.claim_id = edge.subject_id
            evidence.relation = relation


def from_prov(document: dict[str, Any]) -> ProvenanceGraph:
    """Reconstruct a provenance graph from a claimkit PROV-JSON document.

    This is the inbound counterpart to :func:`to_prov`. Because PROV-JSON is a
    narrower model than claimkit's, the reconstruction is best-effort: fields
    claimkit does not export (claim tags and timestamps, evidence timestamps,
    activity kind and used/generated lists, all metadata) fall back to their
    defaults. An evidence node's ``claim_id`` and intrinsic ``relation`` are
    recovered from the edge that links it to a claim where possible.

    Args:
        document: A PROV-JSON document as produced by :func:`to_prov`.

    Returns:
        The reconstructed graph.

    """
    entities = document.get("entity", {})
    activities = document.get("activity", {})
    agents = document.get("agent", {})

    graph = ProvenanceGraph()
    _import_nodes(graph, entities, activities)
    _import_edges(graph, document, _node_type_map(entities, activities, agents))
    _backfill_evidence_links(graph)
    return graph


def loads_prov(text: str) -> ProvenanceGraph:
    """Deserialise a provenance graph from a PROV-JSON string.

    Args:
        text: A PROV-JSON document as produced by :func:`dumps_prov`.

    Returns:
        The reconstructed graph.

    """
    return from_prov(json.loads(text))
