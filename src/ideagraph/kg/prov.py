"""Export a KnowledgeGraph to, and import it from, PROV-JSON.

`PROV-JSON <https://www.w3.org/submissions/prov-json/>`_ is a standard JSON
serialisation of the `W3C PROV data model <https://www.w3.org/TR/prov-dm/>`_.
The generic mapping is:

* a node of type ``activity`` -> ``prov:Activity``; type ``agent`` ->
  ``prov:Agent``; any other type -> ``prov:Entity``;
* a node's ``type`` becomes ``prov:type`` (as a ``ck:`` qualified name), its
  ``text`` and each property become ``ck:`` attributes;
* edges map to the matching PROV relation (``used`` / ``generated_by`` /
  ``derived_from`` / ``attributed_to``); every other edge type has no PROV
  equivalent and is exported as ``wasInfluencedBy`` carrying a ``ck:predicate``
  attribute so the original relationship is preserved.

Import is best-effort and lossy (node ids/types/text/properties survive, but
node timestamps are not carried by PROV); the stable invariant is that
re-exporting an imported graph reproduces the document.
"""

from __future__ import annotations

import json
from typing import Any

from ideagraph.core.identity import is_global_id
from ideagraph.kg.edge import Edge
from ideagraph.kg.graph import KnowledgeGraph
from ideagraph.kg.node import Node

CK_NAMESPACE = "https://ideagraph.dev/ns#"

_ACTIVITY, _AGENT = "activity", "agent"

# edge.type -> (prov relation container, subject role, object role)
_RELATION_ROLES = {
    "used": ("used", "prov:activity", "prov:entity"),
    "generated_by": ("wasGeneratedBy", "prov:entity", "prov:activity"),
    "derived_from": ("wasDerivedFrom", "prov:generatedEntity", "prov:usedEntity"),
    "attributed_to": ("wasAttributedTo", "prov:entity", "prov:agent"),
}
# reverse: prov relation -> (edge.type, subject role, object role)
_RELATION_ROLES_REV = {name: (etype, s, o) for etype, (name, s, o) in _RELATION_ROLES.items()}


def _qn(identifier: str) -> str:
    """Return the ``ck``-prefixed qualified name for an identifier.

    Args:
        identifier: A node or edge id.

    Returns:
        The qualified name.

    """
    return f"ck:{identifier}"


def _local(qualified_name: str) -> str:
    """Strip the ``ck:`` prefix from a qualified name.

    Args:
        qualified_name: A PROV-JSON qualified name.

    Returns:
        The bare local identifier.

    """
    return qualified_name[3:] if qualified_name.startswith("ck:") else qualified_name


def _node_attrs(node: Node) -> dict[str, Any]:
    """Build the PROV attribute dict for a node.

    Args:
        node: The node.

    Returns:
        The ``prov:`` / ``ck:`` attribute mapping.

    """
    attrs: dict[str, Any] = {"prov:type": _qn(node.type)}
    if node.text:
        attrs["ck:text"] = node.text
    if node.tags:
        attrs["ck:tags"] = list(node.tags)
    for key, value in node.properties.items():
        if value is not None:
            attrs[f"ck:{key}"] = value
    return attrs


def to_prov(graph: KnowledgeGraph) -> dict[str, Any]:
    """Convert a knowledge graph to a PROV-JSON document.

    Args:
        graph: The graph to export.

    Returns:
        A PROV-JSON document as a plain dictionary.

    """
    entity: dict[str, Any] = {}
    activity: dict[str, Any] = {}
    agent: dict[str, Any] = {}
    buckets = {_ACTIVITY: activity, _AGENT: agent}

    for node in graph.nodes.values():
        buckets.get(node.type, entity)[_qn(node.id)] = _node_attrs(node)

    def _ensure_entity(node_id: str) -> None:
        qn = _qn(node_id)
        if qn not in entity and qn not in activity and qn not in agent:
            entity[qn] = {"prov:type": "ck:external"} if is_global_id(node_id) else {"prov:type": "ck:node"}

    relations: dict[str, dict[str, Any]] = {
        name: {} for name in ("used", "wasGeneratedBy", "wasDerivedFrom", "wasAttributedTo", "wasInfluencedBy")
    }
    for edge in graph.edges.values():
        _ensure_entity(edge.source)
        _ensure_entity(edge.target)
        subject, obj = _qn(edge.source), _qn(edge.target)
        roles = _RELATION_ROLES.get(edge.type)
        if roles is not None:
            name, s_role, o_role = roles
            relations[name][_qn(edge.id)] = {s_role: subject, o_role: obj}
        else:
            relations["wasInfluencedBy"][_qn(edge.id)] = {
                "prov:influencee": subject,
                "prov:influencer": obj,
                "ck:predicate": edge.type,
            }

    document: dict[str, Any] = {"prefix": {"ck": CK_NAMESPACE}}
    for name, collection in (("entity", entity), ("activity", activity), ("agent", agent), *relations.items()):
        if collection:
            document[name] = collection
    return document


def dumps_prov(graph: KnowledgeGraph, *, indent: int = 2) -> str:
    """Serialise a knowledge graph to a PROV-JSON string.

    Args:
        graph: The graph to export.
        indent: Indentation passed to :func:`json.dumps`.

    Returns:
        The PROV-JSON document as a string.

    """
    return json.dumps(to_prov(graph), indent=indent, ensure_ascii=False)


def _node_from_attrs(qn: str, attrs: dict[str, Any]) -> Node:
    """Reconstruct a node from its PROV attribute dict.

    Args:
        qn: The node's qualified name.
        attrs: Its ``prov:`` / ``ck:`` attributes.

    Returns:
        The reconstructed node.

    """
    properties = {}
    tags: list[str] = []
    text = ""
    for key, value in attrs.items():
        if key == "ck:text":
            text = value
        elif key == "ck:tags":
            tags = list(value)
        elif key.startswith("ck:"):
            properties[key[3:]] = value
    node_type = _local(attrs.get("prov:type", "ck:node"))
    return Node(type=node_type, text=text, id=_local(qn), tags=tags, properties=properties)


def from_prov(document: dict[str, Any]) -> KnowledgeGraph:
    """Reconstruct a knowledge graph from a PROV-JSON document.

    Args:
        document: A PROV-JSON document as produced by :func:`to_prov`.

    Returns:
        The reconstructed graph. External endpoint stubs (global ids or the
        generic ``ck:external`` / ``ck:node`` placeholders) are not materialised
        as nodes.

    """
    graph = KnowledgeGraph()
    for bucket in ("entity", "activity", "agent"):
        for qn, attrs in document.get(bucket, {}).items():
            local = _local(qn)
            if is_global_id(local) or attrs.get("prov:type") in ("ck:external", "ck:node"):
                continue
            graph.add_node(_node_from_attrs(qn, attrs))

    for name, payload_map in document.items():
        if name in _RELATION_ROLES_REV:
            etype, s_role, o_role = _RELATION_ROLES_REV[name]
            for qn, payload in payload_map.items():
                graph.add_edge(
                    Edge(type=etype, source=_local(payload[s_role]), target=_local(payload[o_role]), id=_local(qn))
                )
        elif name == "wasInfluencedBy":
            for qn, payload in payload_map.items():
                graph.add_edge(
                    Edge(
                        type=payload["ck:predicate"],
                        source=_local(payload["prov:influencee"]),
                        target=_local(payload["prov:influencer"]),
                        id=_local(qn),
                    )
                )
    return graph


def loads_prov(text: str) -> KnowledgeGraph:
    """Deserialise a knowledge graph from a PROV-JSON string.

    Args:
        text: A PROV-JSON document as produced by :func:`dumps_prov`.

    Returns:
        The reconstructed graph.

    """
    return from_prov(json.loads(text))
