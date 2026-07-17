# ruff: noqa: PLC0415
"""Flask app + status payload for the claimkit provenance web UI.

``build_payload`` is dependency-free (core claimkit only) so it can be tested
without the ``web`` extra; ``create_app`` imports Flask lazily.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from claimkit import (
    Claim,
    ClaimStatus,
    Evidence,
    ProvenanceGraph,
    find_stale_claims,
    hash_file,
    load_graph,
    validate_all,
)

#: Node-type label for the front end, keyed by which store it came from.
_CLAIM, _EVIDENCE, _ACTIVITY = "claim", "evidence", "activity"

#: Truncate long claim statements to this many characters for the node label.
_LABEL_MAX = 60


def _resolver(base: Path):
    """Return a DigestResolver that re-hashes each evidence's reference file."""

    def _resolve(evidence: Evidence) -> str | None:
        ref = (evidence.metadata or {}).get("artefact") or evidence.reference
        if not ref:
            return None
        p = base / ref
        return hash_file(p) if p.exists() else None

    return _resolve


def _claim_node(claim: Claim, status: ClaimStatus, stale: bool) -> dict[str, Any]:
    """Build the front-end node dict for a claim."""
    return {
        "id": claim.id,
        "type": _CLAIM,
        "label": claim.statement[:_LABEL_MAX] + ("…" if len(claim.statement) > _LABEL_MAX else ""),
        "status": "stale" if stale else status.value,
        "statement": claim.statement,
        "tags": list(claim.tags),
        "metadata": claim.metadata,
    }


def build_payload(graph_path: str | Path, base: str | Path | None = None) -> dict[str, Any]:
    """Load the graph and compute a front-end payload with live status.

    Args:
        graph_path: Path to the claimkit graph JSON file.
        base: Directory that relative evidence references resolve against, for
            staleness (defaults to the graph file's parent).

    Returns:
        A dict with ``nodes``, ``edges``, and a ``summary`` of status counts —
        recomputed from disk on every call so the view reflects current state.
    """
    graph_path = Path(graph_path)
    base = Path(base) if base is not None else graph_path.parent
    graph: ProvenanceGraph = load_graph(graph_path)

    verdicts = validate_all(graph)
    stale_ids = {c.id for c in find_stale_claims(graph, _resolver(base))}

    nodes: list[dict[str, Any]] = []
    for cid, claim in graph.claims.items():
        nodes.append(_claim_node(claim, verdicts[cid].status, cid in stale_ids))
    for eid, ev in graph.evidence.items():
        nodes.append(
            {
                "id": eid,
                "type": _EVIDENCE,
                "label": ev.reference,
                "status": "evidence",
                "kind": ev.kind.value,
                "reference": ev.reference,
                "digest": ev.digest,
                "metadata": ev.metadata,
            }
        )
    for aid, act in graph.activities.items():
        nodes.append(
            {
                "id": aid,
                "type": _ACTIVITY,
                "label": act.label,
                "status": "activity",
                "kind": act.kind.value,
                "metadata": act.metadata,
            }
        )

    edges = [
        {
            "source": rel.subject_id,
            "target": rel.object_id,
            "predicate": rel.predicate.value,
        }
        for rel in graph.relations.values()
    ]

    summary: dict[str, int] = {}
    for cid in graph.claims:
        key = "stale" if cid in stale_ids else verdicts[cid].status.value
        summary[key] = summary.get(key, 0) + 1

    return {
        "nodes": nodes,
        "edges": edges,
        "summary": summary,
        "counts": {
            "claims": len(graph.claims),
            "evidence": len(graph.evidence),
            "activities": len(graph.activities),
        },
    }


def create_app(graph_path: str | Path, base: str | Path | None = None):
    """Build the Flask app serving the provenance UI.

    Args:
        graph_path: Path to the claimkit graph JSON file.
        base: Directory relative evidence references resolve against.

    Returns:
        A configured :class:`flask.Flask` application.

    Raises:
        ModuleNotFoundError: If Flask is not installed (install ``claimkit[web]``).
    """
    try:
        from flask import Flask, Response, jsonify
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised via CLI guard
        raise ModuleNotFoundError("the web UI needs Flask; install it with `pip install claimkit[web]`") from exc

    app = Flask(__name__)

    @app.route("/api/graph")
    def api_graph():  # type: ignore[no-untyped-def]
        return jsonify(build_payload(graph_path, base))

    @app.route("/vendor/vis-network.min.js")
    def vendor_vis():  # type: ignore[no-untyped-def]
        from importlib.resources import files

        data = (files("claimkit.web") / "static" / "vis-network.min.js").read_bytes()
        return Response(data, mimetype="application/javascript")

    @app.route("/")
    def index():  # type: ignore[no-untyped-def]
        return Response(_INDEX_HTML, mimetype="text/html")

    return app


#: Self-contained page; loads the vendored vis-network (served at /vendor/, no
#: network needed). Fetches /api/graph and renders a status-coloured provenance
#: DAG with a click-through detail panel and a status summary bar.
_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>claimkit provenance</title>
<script src="/vendor/vis-network.min.js"></script>
<style>
  body { margin:0; font-family: system-ui, sans-serif; display:flex; flex-direction:column; height:100vh; }
  #bar { padding:8px 12px; background:#1f2933; color:#fff; font-size:14px; }
  #bar .chip { display:inline-block; padding:2px 8px; border-radius:10px; margin-right:6px; }
  #main { flex:1; display:flex; min-height:0; }
  #net { flex:1; }
  #panel { width:340px; overflow:auto; border-left:1px solid #ddd; padding:12px; font-size:13px; }
  #panel h3 { margin:.2em 0; } pre { white-space:pre-wrap; word-break:break-word; background:#f6f8fa; padding:8px; }
  .legend span { margin-right:10px; } .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:3px; }
</style>
</head>
<body>
<div id="bar">
  <b>claimkit provenance</b> &nbsp; <span id="summary"></span>
  <span class="legend" style="float:right">
    <span><i class="dot" style="background:#2e7d32"></i>valid</span>
    <span><i class="dot" style="background:#c62828"></i>invalid</span>
    <span><i class="dot" style="background:#f9a825"></i>stale</span>
    <span><i class="dot" style="background:#757575"></i>unresolved</span>
    <span><i class="dot" style="background:#1565c0"></i>evidence</span>
    <span><i class="dot" style="background:#6a1b9a"></i>activity</span>
  </span>
</div>
<div id="main">
  <div id="net"></div>
  <div id="panel">Click a node to inspect its provenance.</div>
</div>
<script>
const COLOR = { valid:"#2e7d32", invalid:"#c62828", stale:"#f9a825", needs_review:"#ef6c00",
  unresolved:"#757575", evidence:"#1565c0", activity:"#6a1b9a" };
const SHAPE = { claim:"box", evidence:"ellipse", activity:"diamond" };
let byId = {};
async function load() {
  const data = await (await fetch("/api/graph")).json();
  byId = Object.fromEntries(data.nodes.map(n => [n.id, n]));
  const nodes = data.nodes.map(n => ({ id:n.id, label:n.label, shape:SHAPE[n.type]||"dot",
    color:{ background:COLOR[n.status]||"#999", border:"#333" }, font:{color:n.type==="claim"?"#fff":"#000"} }));
  const edges = data.edges.map(e => ({ from:e.source, to:e.target, label:e.predicate, arrows:"to",
    font:{size:9, color:"#666"}, color:{color:"#bbb"} }));
  const sm = Object.entries(data.summary).map(([k,v]) =>
    `<span class="chip" style="background:${COLOR[k]||'#999'}">${k}: ${v}</span>`).join("");
  document.getElementById("summary").innerHTML = sm +
    ` &nbsp; ${data.counts.claims} claims · ${data.counts.evidence} evidence · ${data.counts.activities} activities`;
  const net = new vis.Network(document.getElementById("net"),
    { nodes:new vis.DataSet(nodes), edges:new vis.DataSet(edges) },
    { layout:{ hierarchical:{ direction:"LR", sortMethod:"directed", nodeSpacing:120 } },
      physics:false, interaction:{ hover:true } });
  net.on("click", p => {
    if (!p.nodes.length) return;
    const n = byId[p.nodes[0]];
    let h = `<h3>${n.type}: ${n.id}</h3><b>status:</b> ${n.status}<br/>`;
    if (n.statement) h += `<p>${n.statement}</p>`;
    if (n.reference) h += `<b>reference:</b> ${n.reference}<br/>`;
    if (n.digest) h += `<b>digest:</b> <code>${n.digest}</code><br/>`;
    if (n.kind) h += `<b>kind:</b> ${n.kind}<br/>`;
    if (n.metadata && Object.keys(n.metadata).length)
      h += `<b>metadata:</b><pre>${JSON.stringify(n.metadata, null, 2)}</pre>`;
    document.getElementById("panel").innerHTML = h;
  });
}
load();
</script>
</body>
</html>
"""
