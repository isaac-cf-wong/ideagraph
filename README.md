# ClaimKit

[![Python CI](https://github.com/isaac-cf-wong/claimkit/actions/workflows/ci.yml/badge.svg)](https://github.com/isaac-cf-wong/claimkit/actions/workflows/ci.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/isaac-cf-wong/claimkit/main.svg)](https://results.pre-commit.ci/latest/github/isaac-cf-wong/claimkit/main)
[![Documentation Status](https://github.com/isaac-cf-wong/claimkit/actions/workflows/documentation.yml/badge.svg)](https://isaac-cf-wong.github.io/claimkit/)
[![codecov](https://codecov.io/gh/isaac-cf-wong/claimkit/graph/badge.svg?token=COF8341N60)](https://codecov.io/gh/isaac-cf-wong/claimkit)
[![PyPI Version](https://img.shields.io/pypi/v/claimkit)](https://pypi.org/project/claimkit/)
[![Python Versions](https://img.shields.io/pypi/pyversions/claimkit)](https://pypi.org/project/claimkit/)
[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![DOI](https://zenodo.org/badge/924023559.svg)](https://doi.org/10.5281/zenodo.18017404)
[![SPEC 0 — Minimum Supported Dependencies](https://img.shields.io/badge/SPEC-0-green?labelColor=%23004811&color=%235CA038)](https://scientific-python.org/specs/spec-0000/)

**ClaimKit is a claim-level provenance framework for scientific research.**

It makes every scientific claim, numerical result, figure, and table traceable
to the evidence that supports it. A claim registered in ClaimKit has a
well-defined provenance, can be validated against its current evidence, and is
flagged as _stale_ when that evidence changes. ClaimKit is designed to be both
human- and agent-friendly, with stable machine-readable interfaces throughout.

ClaimKit does **not** replace workflow managers, experiment trackers, version
control, or manuscript tools — it links to and builds on them.

## Core concepts

- **Claim** — a scientific assertion with a stable id and a validation status.
- **Evidence** — a link from a claim to an artefact (code, data, a run,
  literature, …) that supports, refutes, or contextualises it.
- **Activity** — a process (computation, measurement, analysis, review) that
  consumed and produced artefacts.
- **ProvenanceRelation** — a typed, directed edge connecting claims, evidence,
  activities, artefacts, and agents into a graph.
- **ProvenanceGraph** — the container of nodes and edges; supports traversal,
  validation, staleness detection, and reporting.

A claim's status is one of `unresolved`, `valid`, `invalid`, `stale`, or
`needs_review`.

## Installation

```bash
pip install claimkit
```

Requires Python 3.12+.

## Command-line quickstart

Build a graph, link evidence, and check it — all from the terminal:

```bash
claimkit init graph.json
CLAIM=$(claimkit add-claim graph.json "Half-life measured at 5.2 days." --tag decay)
claimkit add-evidence graph.json "$CLAIM" \
    --kind workflow --reference run-42 --digest sha256:abc123

claimkit validate graph.json            # resolve status from evidence
claimkit stale graph.json               # flag claims whose artefacts changed
claimkit report graph.json              # human-readable Markdown report
claimkit export graph.json -o prov.json # export to W3C PROV-JSON
claimkit import prov.json restored.json # import PROV-JSON back into a graph
```

`validate` and `stale` accept `--json` for machine-readable output; `report` and
`export` accept `-o` to write to a file. Run `claimkit --help` for the full
command list.

## Python quickstart

```python
from claimkit import (
    Claim, Evidence, EvidenceKind, NodeType,
    ProvenanceGraph, ProvenancePredicate, ProvenanceRelation,
    validate_claim, render_report,
)

graph = ProvenanceGraph()
graph.add_claim(Claim(statement="Half-life measured at 5.2 days.", id="c1"))
graph.add_evidence(
    Evidence(claim_id="c1", kind=EvidenceKind.WORKFLOW, reference="run-42", id="e1")
)
graph.add_relation(
    ProvenanceRelation(
        subject_type=NodeType.CLAIM, subject_id="c1",
        predicate=ProvenancePredicate.SUPPORTED_BY,
        object_type=NodeType.EVIDENCE, object_id="e1",
    )
)

result = validate_claim(graph, "c1")
print(result.status, "—", result.reason)   # valid — supported by 1 piece(s) of evidence
print(render_report(graph))
```

## Interoperability

ClaimKit graphs serialise to a versioned JSON format for storage (`save_graph` /
`load_graph`) and export to / import from
[W3C PROV-JSON](https://www.w3.org/submissions/prov-json/) (`to_prov` /
`from_prov`) for interchange with the wider provenance ecosystem.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
