# Data Janitor Assessment

A productized **data-health assessment** with a lightweight local execution
harness. Its intellectual framework spans six dimensions:

1. Data Quality
2. Metadata & Documentation
3. Metric Consistency
4. Privacy & PII Hygiene
5. Ownership & Governance
6. Reliability & Freshness

with a documented catalog of 42 checks. **That full framework is not the
current commercial or engineering target** — see below.

## Project status

Per `SPEC.md` **Amendment 001** (2026-09-10, "Post-Feasibility Product
Reorientation"), the six-dimension framework and 42-check catalog are
retained as an internal methodology library, but the commercial and
engineering focus has narrowed to a single validated wedge:

> An independent, evidence-backed reconciliation of management numbers
> (starting with Revenue and Margin) that materially disagree across
> reporting surfaces.

**Current milestone: M0 — Reporting Reliability Demo Environment**
(definition phase; supersedes the prior "Reproducible Broken Company"
milestone). M0 builds one realistic synthetic scenario — the fictional B2B
distributor **Northstar Distribution**, now positioned as a *demo dataset*
rather than an industry benchmark, with a Revenue/Margin dispute
reproducible across at least three reporting surfaces — and uses it to
produce one presentable sample **Reporting Reliability Audit**. See
[`Current Assignment.md`](Current%20Assignment.md) for the full assignment.

Engineering is capped at that deliverable: per Amendment §AA, further
engineering pauses once M0's Definition of Done is met, pending commercial
buyer validation. The full 42-check engine, composite scoring, AI
Readiness, and SaaS infrastructure remain explicitly out of scope until the
Product Owner reauthorizes them.

## Document hierarchy

| Document | Role |
|---|---|
| `SPEC.md` (incl. Amendment 001) | Canonical product specification (product truth). **Owned by the Product Owner.** Amendment 001 overrides any conflicting original section. |
| `Current Assignment.md` | Canonical engineering assignment for the active milestone (M0, revised). |

If the two conflict, `SPEC.md` wins.

## Repository layout

```
data-janitor-assessment/
├── README.md                 # this file — repository orientation
├── SPEC.md                   # canonical product spec + Amendment 001, owned by the PO
├── Current Assignment.md     # active milestone assignment (M0, revised)
├── pyproject.toml            # Python project configuration
├── benchmark/                # Northstar Distribution demo environment
│   ├── README.md             # demo-environment architecture & reconciliation scenario
│   ├── generate.py           # deterministic generator → PostgreSQL + evidence + ground truth
│   ├── load_duckdb.py        # optional internal DuckDB mirror (dev/test only)
│   ├── config/               # generation configuration (seed, scale profiles, scenario params)
│   ├── scenario/             # committed surface SQL and note sources (the evidence)
│   ├── data/                 # generated dev/test output (gitignored — regenerate)
│   └── ground_truth/         # generated hidden ground truth (gitignored)
├── report/
│   └── samples/               # the one committed sample Reporting Reliability Audit
└── tests/                    # test suite
```

Directories for later milestones (`assessment/`, `runner/`, `methodology/`,
`public/`) are intentionally absent until a milestone needs them.

## Core constraints (summary)

- **Independent IP** — everything here is independently created; all data is
  fictional and synthetic. No employer or client material of any kind.
- **Local-first** — runs locally on Python 3.12+. **PostgreSQL is the
  canonical Northstar environment**; DuckDB is an internal test/dev
  convenience only, never the canonical platform. No mandatory cloud,
  commercial API, or external AI service.
- **LLM-independent** — deterministic evidence and reconciliation never
  require an LLM.
- **Read-only** — the product analyzes data; it never modifies source data.
- **No SaaS infrastructure** — no auth, accounts, billing, dashboards,
  portals, scheduling, or notifications in v0.1.
- **Demo, not benchmark** — Northstar is described as a demo dataset /
  synthetic demonstration environment, never as an industry benchmark.

## Getting started

Requires Python 3.12+.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Most tests run offline with no database. The tests that exercise the
canonical PostgreSQL acceptance path (`tests/test_postgres_end_to_end.py`,
`tests/test_duckdb_mirror.py`) are **skipped** unless
`NORTHSTAR_DATABASE_URL` points at a PostgreSQL instance you control; they
create and drop their own scratch databases on that server.

## Generating the Northstar demo environment

**PostgreSQL is the canonical Northstar environment.** Point
`NORTHSTAR_DATABASE_URL` at a database and generate:

```bash
export NORTHSTAR_DATABASE_URL="postgresql://user@host:5432/northstar"
python benchmark/generate.py --profile smoke   # small, fast (seconds)
python benchmark/generate.py --profile demo    # credible mid-market scale (~90s)
```

`generate.py` creates the `core`, `finance`, `analytics`, and `management`
schemas from scratch, loads the operational lifecycle, materializes the
three reporting surfaces via their own SQL, attaches the fragmented
evidence, writes the evidence directory to `benchmark/data/evidence/`, and
writes the hidden ground-truth manifest to `benchmark/ground_truth/`. It
self-verifies every reported figure against an independent recomputation and
refuses to emit output that misses a materiality target. Both generated
directories are gitignored — regenerate rather than commit them.

Optional internal DuckDB mirror (dev/test convenience only, never the
canonical environment):

```bash
python benchmark/load_duckdb.py   # mirrors the generated PostgreSQL data into benchmark/data/northstar_dev.duckdb
```

### Local disposable PostgreSQL (for the acceptance tests)

Any local PostgreSQL 14+ works. One disposable-instance recipe:

```bash
initdb -D /tmp/northstar-pg -U northstar --auth=trust
pg_ctl -D /tmp/northstar-pg -o "-p 55432" -l /tmp/northstar-pg/log start
createdb -h 127.0.0.1 -p 55432 -U northstar northstar
export NORTHSTAR_DATABASE_URL="postgresql://northstar@127.0.0.1:55432/northstar"
pytest        # now runs the PostgreSQL + DuckDB acceptance tests too
```

The demo environment, the sample report, the reconciliation scenario, and
the ground-truth format are all specified in
[`benchmark/README.md`](benchmark/README.md) (the binding Scenario
Contract). The one committed sample audit produced from this environment is
[`report/samples/northstar-reporting-reliability-audit.md`](report/samples/northstar-reporting-reliability-audit.md).
