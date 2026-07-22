// Render a single provenance graph with vis-network, reading its data from the
// endpoint named in the container's data-graph-url attribute.
;(function () {
    'use strict'

    var COLOR = {
        valid: '#1f9d55',
        invalid: '#e0245e',
        stale: '#f5a623',
        needs_review: '#ef6c00',
        unresolved: '#8895a7',
        own: '#1f9d55',
        literature: '#2f6df6',
        both: '#00897b',
        other: '#8895a7',
        unsupported: '#e0245e',
        evidence: '#2f6df6',
        activity: '#8e44c9',
        unknown: '#8895a7',
    }
    var STYPE = {
        claim: '#3949ab',
        finding: '#00897b',
        result: '#00acc1',
        background: '#8d6e63',
        method: '#6a4fa3',
        definition: '#546e7a',
        motivation: '#c2185b',
        other: '#8895a7',
    }

    function esc(s) {
        return String(s).replace(/[&<>]/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]
        })
    }

    var byId = {}

    function showNode(id) {
        var panel = document.getElementById('panel')
        var n = byId[id]
        if (!n) {
            panel.innerHTML =
                '<h3>' +
                esc(id) +
                '</h3><span class="badge" style="background:#e0245e">unknown reference</span>' +
                '<div class="stmt">This id is not in the graph — a dangling reference.</div>'
            return
        }
        var label =
            n.type === 'statement'
                ? n.stype
                : n.status === 'literature'
                  ? 'literature'
                  : n.type
        var bg =
            n.type === 'statement'
                ? STYPE[n.stype] || '#8895a7'
                : n.status === 'literature'
                  ? '#d98324'
                  : COLOR[n.status] || '#8895a7'
        var h =
            '<h3>' +
            esc(n.id) +
            '</h3><span class="badge" style="background:' +
            bg +
            '">' +
            esc(label) +
            '</span>'
        if (n.statement) h += '<div class="stmt">' + esc(n.statement) + '</div>'
        if (n.support)
            h += '<div class="kv"><b>support:</b> ' + esc(n.support) + '</div>'
        if (n.status)
            h += '<div class="kv"><b>status:</b> ' + esc(n.status) + '</div>'
        if (n.section)
            h += '<div class="kv"><b>section:</b> ' + esc(n.section) + '</div>'
        if (n.citation)
            h +=
                '<div class="kv"><b>citation:</b> ' + esc(n.citation) + '</div>'
        if (n.kind)
            h += '<div class="kv"><b>kind:</b> ' + esc(n.kind) + '</div>'
        if (n.reference)
            h +=
                '<div class="kv"><b>reference:</b> ' +
                esc(n.reference) +
                '</div>'
        if (n.digest)
            h +=
                '<div class="kv"><b>digest:</b> <code>' +
                esc(n.digest) +
                '</code></div>'
        if (n.source_digest)
            h +=
                '<div class="kv"><b>source digest:</b> <code>' +
                esc(n.source_digest) +
                '</code></div>'
        if (n.tags && n.tags.length)
            h +=
                '<div class="kv"><b>tags:</b> ' +
                esc(n.tags.join(', ')) +
                '</div>'
        if (n.metadata && Object.keys(n.metadata).length)
            h +=
                '<div class="kv"><b>metadata:</b></div><pre>' +
                esc(JSON.stringify(n.metadata, null, 2)) +
                '</pre>'
        panel.innerHTML = h
    }

    function renderLegend() {
        var legend = document.getElementById('legend')
        legend.innerHTML = Object.keys(STYPE)
            .map(function (k) {
                return (
                    '<span class="lg"><i style="background:' +
                    STYPE[k] +
                    '"></i>' +
                    k +
                    '</span>'
                )
            })
            .join('')
    }

    function render(data) {
        byId = {}
        data.nodes.forEach(function (n) {
            byId[n.id] = n
        })
        var nodes = data.nodes.map(function (n) {
            var bg, border
            if (n.type === 'statement') {
                bg = STYPE[n.stype] || '#8895a7'
                border =
                    n.support === 'unsupported'
                        ? '#e0245e'
                        : n.status === 'stale'
                          ? '#f5a623'
                          : bg
            } else {
                bg =
                    n.status === 'literature'
                        ? '#d98324'
                        : COLOR[n.status] || '#8895a7'
                border = bg
            }
            return {
                id: n.id,
                label: n.label,
                level: n.level,
                shape: 'box',
                color: {
                    background: bg,
                    border: border,
                    highlight: { background: bg, border: '#111' },
                },
                font: {
                    color: '#ffffff',
                    size: 18,
                    face: 'system-ui',
                    bold: n.type === 'statement',
                },
                margin: 12,
                widthConstraint: { maximum: 230 },
                shapeProperties: { borderRadius: 7 },
                borderWidth: border !== bg ? 4 : 2,
            }
        })
        var edges = data.edges.map(function (e) {
            return {
                from: e.source,
                to: e.target,
                arrows: { to: { scaleFactor: 0.6 } },
                dashes: e.discourse,
                label: e.discourse ? e.predicate : undefined,
                font: {
                    size: 11,
                    color: '#8d6e63',
                    strokeWidth: 3,
                    strokeColor: '#ffffff',
                },
                smooth: {
                    type: 'cubicBezier',
                    forceDirection: 'horizontal',
                    roundness: 0.55,
                },
                color: {
                    color: e.discourse ? '#8d6e63' : '#c3ccd8',
                    highlight: '#5b6b7f',
                },
                width: 1.5,
            }
        })
        document.getElementById('summary').innerHTML = Object.keys(data.summary)
            .map(function (k) {
                return (
                    '<span class="chip" style="background:' +
                    (COLOR[k] || '#8895a7') +
                    '">' +
                    data.summary[k] +
                    ' ' +
                    k +
                    '</span>'
                )
            })
            .join(' ')
        document.getElementById('counts').textContent =
            data.counts.statements +
            ' statements · ' +
            data.counts.evidence +
            ' evidence · ' +
            data.counts.activities +
            ' runs'
        var net = new vis.Network(
            document.getElementById('net'),
            { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) },
            {
                layout: {
                    hierarchical: {
                        enabled: true,
                        direction: 'LR',
                        sortMethod: 'directed',
                        levelSeparation: 430,
                        nodeSpacing: 120,
                        treeSpacing: 240,
                        blockShifting: true,
                        edgeMinimization: true,
                        parentCentralization: true,
                        shakeTowards: 'roots',
                    },
                },
                physics: false,
                interaction: { hover: true, tooltipDelay: 120 },
            }
        )
        net.once('afterDrawing', function () {
            net.fit({ animation: false })
        })
        net.on('click', function (p) {
            if (p.nodes.length) {
                showNode(p.nodes[0])
            } else {
                document.getElementById('panel').innerHTML =
                    '<span class="hint">Click a node to inspect it.</span>'
            }
        })
    }

    document.addEventListener('DOMContentLoaded', function () {
        var view = document.querySelector('.graph-view')
        if (!view) return
        renderLegend()
        fetch(view.dataset.graphUrl)
            .then(function (r) {
                return r.json()
            })
            .then(render)
            .catch(function () {
                document.getElementById('net').innerHTML =
                    '<p class="muted">Failed to load graph.</p>'
            })
    })
})()
