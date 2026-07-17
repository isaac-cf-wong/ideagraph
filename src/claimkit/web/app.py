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
    """Build the front-end node dict for a claim (column 0)."""
    return {
        "id": claim.id,
        "type": _CLAIM,
        "level": 0,
        "label": claim.id,
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
                "level": 1,
                "label": eid,
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
                "level": 2,
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
  :root { --bg:#0f1720; --panel:#f7f9fc; }
  * { box-sizing:border-box; }
  body { margin:0; font-family: system-ui, -apple-system, sans-serif; display:flex; flex-direction:column;
         height:100vh; color:#1a2330; }
  #bar { padding:10px 16px; background:var(--bg); color:#fff; display:flex; align-items:center; gap:14px;
         flex-wrap:wrap; }
  #bar b { font-size:15px; letter-spacing:.2px; }
  .chip { display:inline-flex; align-items:center; padding:3px 10px; border-radius:12px; font-size:12px;
          font-weight:600; color:#fff; }
  .counts { color:#9fb0c3; font-size:13px; }
  .legend { margin-left:auto; display:flex; gap:14px; font-size:12px; color:#c8d3df; }
  .legend span { display:inline-flex; align-items:center; gap:5px; }
  .sw { width:12px; height:12px; border-radius:3px; display:inline-block; }
  #cols { display:flex; padding:6px 0; background:#eef2f7; border-bottom:1px solid #dde3ec;
          font-size:12px; font-weight:700; color:#5b6b7f; text-transform:uppercase; letter-spacing:.5px; }
  #cols div { flex:1; text-align:center; }
  #main { flex:1; display:flex; min-height:0; }
  #net { flex:1; background:#fbfcfe; }
  #panel { width:360px; overflow:auto; border-left:1px solid #dde3ec; padding:16px; font-size:13px;
           background:var(--panel); }
  #panel h3 { margin:0 0 4px; font-size:15px; word-break:break-word; }
  #panel .badge { display:inline-block; padding:2px 9px; border-radius:10px; color:#fff; font-size:11px;
                  font-weight:700; margin-bottom:10px; }
  #panel .stmt { font-size:14px; line-height:1.45; margin:8px 0 12px; color:#243244; }
  #panel .kv { margin:3px 0; color:#42536a; } #panel .kv b { color:#1a2330; }
  #panel code { background:#e7edf5; padding:1px 5px; border-radius:4px; font-size:12px; word-break:break-all; }
  pre { white-space:pre-wrap; word-break:break-word; background:#e7edf5; padding:10px; border-radius:6px;
        font-size:12px; margin:6px 0 0; }
  .hint { color:#8494a8; }
</style>
</head>
<body>
<div id="bar">
  <b>claimkit provenance</b>
  <span id="summary"></span>
  <span class="counts" id="counts"></span>
  <span class="legend">
    <span><i class="sw" style="background:#1f9d55"></i>valid</span>
    <span><i class="sw" style="background:#e0245e"></i>invalid</span>
    <span><i class="sw" style="background:#f5a623"></i>stale</span>
    <span><i class="sw" style="background:#8895a7"></i>unresolved</span>
    <span><i class="sw" style="background:#2f6df6"></i>evidence</span>
    <span><i class="sw" style="background:#8e44c9"></i>run</span>
  </span>
</div>
<div id="cols"><div>Claims (findings)</div><div>Evidence (results)</div><div>Activities (runs)</div></div>
<div id="main">
  <div id="net"></div>
  <div id="panel"><span class="hint">Click a node to inspect its provenance.</span></div>
</div>
<script>
const COLOR = { valid:"#1f9d55", invalid:"#e0245e", stale:"#f5a623", needs_review:"#ef6c00",
  unresolved:"#8895a7", evidence:"#2f6df6", activity:"#8e44c9" };
const DARKTEXT = new Set(["stale","needs_review"]);  // light fills -> dark text
let byId = {};
function esc(s){ return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

async function load() {
  const data = await (await fetch("/api/graph")).json();
  byId = Object.fromEntries(data.nodes.map(n => [n.id, n]));
  const nodes = data.nodes.map(n => {
    const bg = COLOR[n.status] || "#8895a7";
    const fg = DARKTEXT.has(n.status) ? "#1a2330" : "#ffffff";
    return { id:n.id, label:n.label, level:n.level, shape:"box",
      color:{ background:bg, border:bg, highlight:{background:bg, border:"#111"} },
      font:{ color:fg, size:15, face:"system-ui", bold: n.type==="claim" },
      margin:10, widthConstraint:{ maximum:210 }, shapeProperties:{ borderRadius:7 }, borderWidth:2 };
  });
  const edges = data.edges.map(e => ({ from:e.source, to:e.target, arrows:{to:{scaleFactor:.6}},
    smooth:{ type:"cubicBezier", forceDirection:"horizontal", roundness:.55 },
    color:{ color:"#c3ccd8", highlight:"#5b6b7f" }, width:1.5 }));
  const sm = Object.entries(data.summary).map(([k,v]) =>
    `<span class="chip" style="background:${COLOR[k]||'#8895a7'}">${v} ${k}</span>`).join(" ");
  document.getElementById("summary").innerHTML = sm;
  document.getElementById("counts").textContent =
    `${data.counts.claims} claims · ${data.counts.evidence} evidence · ${data.counts.activities} runs`;
  const net = new vis.Network(document.getElementById("net"),
    { nodes:new vis.DataSet(nodes), edges:new vis.DataSet(edges) },
    { layout:{ hierarchical:{ enabled:true, direction:"LR", sortMethod:"directed",
        levelSeparation:430, nodeSpacing:120, treeSpacing:240, blockShifting:true,
        edgeMinimization:true, parentCentralization:true, shakeTowards:"roots" } },
      physics:false, interaction:{ hover:true, tooltipDelay:120 } });
  net.once("afterDrawing", () => net.fit({ animation:false }));
  net.on("click", p => {
    const panel = document.getElementById("panel");
    if (!p.nodes.length) { panel.innerHTML = '<span class="hint">Click a node to inspect its provenance.</span>'; return; }
    const n = byId[p.nodes[0]];
    const bg = COLOR[n.status] || "#8895a7";
    let h = `<h3>${esc(n.id)}</h3><span class="badge" style="background:${bg}">${esc(n.type)} · ${esc(n.status)}</span>`;
    if (n.statement) h += `<div class="stmt">${esc(n.statement)}</div>`;
    if (n.kind) h += `<div class="kv"><b>kind:</b> ${esc(n.kind)}</div>`;
    if (n.reference) h += `<div class="kv"><b>reference:</b> ${esc(n.reference)}</div>`;
    if (n.digest) h += `<div class="kv"><b>digest:</b> <code>${esc(n.digest)}</code></div>`;
    if (n.tags && n.tags.length) h += `<div class="kv"><b>tags:</b> ${esc(n.tags.join(", "))}</div>`;
    if (n.metadata && Object.keys(n.metadata).length)
      h += `<div class="kv"><b>metadata:</b></div><pre>${esc(JSON.stringify(n.metadata, null, 2))}</pre>`;
    panel.innerHTML = h;
  });
}
load();
</script>
</body>
</html>
"""
