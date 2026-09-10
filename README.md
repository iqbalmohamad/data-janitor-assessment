# Data Janitor Assessment

A productized **data-health assessment** with a lightweight local execution
harness. It evaluates a data estate across six dimensions:

1. Data Quality
2. Metadata & Documentation
3. Metric Consistency
4. Privacy & PII Hygiene
5. Ownership & Governance
6. Reliability & Freshness

The v0.1 catalog contains 42 checks. The assessment pipeline (future
milestones) is:

```
Input Data → Profiling → Automated + Manual/Hybrid Checks → Normalized Findings
           → Scoring → Risk Prioritization → AI Readiness → Assessment Report
```

## Project status

**Current milestone: M0 — Reproducible Broken Company** (definition phase).

M0 builds the benchmark, not the assessment engine: a fully synthetic,
deterministic, inspectable test subject — the fictional B2B distributor
**Northstar Distribution** — containing known, documented data-health defects
across all six dimensions. See [`Current Assignment.md`](Current%20Assignment.md)
for the full M0 assignment.

## Document hierarchy

| Document | Role |
|---|---|
| `SPEC.md` | Canonical product specification (product truth). **Owned by the Product Owner.** |
| `Current Assignment.md` | Canonical engineering assignment for the active milestone. |

If the two conflict, `SPEC.md` wins.

`SPEC.md` is present at the repository root and the M0 assignment has been
reconciled against it.

## Repository layout

```
data-janitor-assessment/
├── README.md                 # this file — repository orientation
├── SPEC.md                   # canonical product spec, owned by the PO
├── Current Assignment.md     # active milestone assignment (M0)
├── pyproject.toml            # Python project configuration
├── benchmark/                # Northstar Distribution synthetic benchmark
│   ├── README.md             # benchmark architecture & defect catalog design
│   ├── config/               # generation configuration (seed, row counts, …)
│   ├── data/                 # generated datasets (gitignored — regenerate)
│   └── ground_truth/         # generated ground-truth manifest (gitignored)
└── tests/                    # test suite
```

Directories for later milestones (`assessment/`, `runner/`, `report/`,
`methodology/`, `public/`) are intentionally absent until a milestone needs
them.

## Core constraints (summary)

- **Independent IP** — everything here is independently created; all data is
  fictional and synthetic. No employer or client material of any kind.
- **Local-first** — runs locally on Python 3.12+ with DuckDB. No mandatory
  cloud, commercial API, external database, or AI service.
- **LLM-independent** — deterministic checks, scoring, evidence, and AI
  readiness classification never require an LLM.
- **Read-only** — the product analyzes data; it never modifies source data.
- **No SaaS infrastructure** — no auth, accounts, billing, dashboards,
  portals, scheduling, or notifications in v0.1.

## Getting started

Requires Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Benchmark generation (`python benchmark/generate.py`) arrives with the M0
implementation; its contract is defined in
[`benchmark/README.md`](benchmark/README.md).
