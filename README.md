# Data Janitor - Reporting Reliability demonstration

Data Janitor's current commercial hypothesis is a fixed-scope audit of important
management numbers that disagree. The governing decision remains **VALIDATE
BEFORE BUILDING FURTHER**. The six-dimension framework and 42-check catalog in
SPEC.md remain methodology references, not an implementation backlog.

The bounded M0 implementation demonstrates a fictional Northstar Distribution
August 2026 Revenue/Gross Margin dispute. Finance is a defensible P&L view;
Sales is a defensible commercial view; the circulated Board pack contains the
hybrid reporting defect. PostgreSQL is Northstar's canonical environment.

**IMPLEMENTATION COMPLETE - READY FOR PM / TECHNICAL LEAD REVIEW.**

Start with the [six-page sample audit](report/samples/northstar-august-2026-audit.pdf)
or its [traceable Markdown edition](report/samples/northstar-august-2026-audit.md).
Both are explicitly synthetic demonstrations, not client engagements.

## Authority and scope

1. [SPEC.md](SPEC.md), including Amendment 001 - Product Owner controlled.
2. [Current Assignment.md](Current%20Assignment.md) - bounded M0 assignment.
3. [Scenario Contract](benchmark/README.md), SC-1 through SC-18.
4. [Generation configuration](benchmark/config/benchmark.toml).

No scoring engine, AI Readiness, connector framework, SaaS, continuous monitoring,
remediation execution or generic report engine is implemented. PM / Technical
Lead review determines the M0 gate; engineering does not self-declare M0 PASS.

## Local installation

Python 3.12+; PostgreSQL for canonical generation and acceptance. No cloud service,
external API, LLM or additional framework is required. From this repository:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest
```

On Unix, use `python3 -m venv .venv` and `.venv/bin/python` instead. The optional
dev dependencies provide pytest and DuckDB for offline test support only.

## Generate Northstar in PostgreSQL

Supply your disposable database's connection string in **NORTHSTAR_DATABASE_URL**,
the environment-variable name configured in benchmark.toml. Do not save credentials
in repository files. The generator creates the core, finance, analytics and
management schemas in one transaction. **The target must be clean**: it refuses
to replace an existing schema. Create another empty database when regenerating;
there is no implicit destructive reset.

```powershell
# Set NORTHSTAR_DATABASE_URL in your shell to your local disposable database.
.\.venv\Scripts\python.exe benchmark/generate.py --profile smoke

# Point the same environment variable at a second clean database for demo.
.\.venv\Scripts\python.exe benchmark/generate.py --profile demo
.\.venv\Scripts\python.exe -m benchmark.scenario.reconcile --period 2026-08
```

The last command starts a read-only transaction. Its monetary reconciliation
uses only database evidence and the requested period: snapshot time comes from
the circulated Board rows; credit VAT and original cost come from invoice/return
lines. Generation targets and hidden ground truth do not supply its answers.

Output defaults:

- `benchmark/data/core/`: deterministic operational CSVs used for bulk loading.
- `benchmark/data/evidence/`: exactly the seven SC-12 files.
- `benchmark/ground_truth/smoke.json` or `demo.json`: hidden QA manifest, including
  each classified bridge, context-specific values and hashes of all reporting
  objects and job history. Never an assessment input.
- `report/samples/northstar-august-2026-audit.md` and `.pdf`: the committed audit,
  assembled from the demo's PostgreSQL evidence. Generation does not overwrite it.

The data and ground-truth directories stay gitignored. `--data-dir`, `--truth-dir`
and `--config` allow isolated QA runs; the visible/hidden output roots must remain
separate. Same code/config/seed on the same interpreter reproduces byte-identical
CSVs, evidence and manifest. All scenario timestamps are fixed WIB local times;
no generator output uses a wall clock. The configured seed is read from TOML.

Each monthly population includes a small posting queue crossing month-end,
partial returns split between ordinary credit posting and close batches, and
actual-cost revisions. Counts are apportioned deterministically across history
so the smoke profile keeps the same materiality and semantics as demo. Monetary
arithmetic uses integer rupiah and Decimal rounding. The deliberately bounded
model uses three merchandise lines per order; the configured order-item total
must equal three times the order count. Some invoices settle in instalments and
some remain partially paid. The starting catalog has a July standard-cost
baseline before the September history begins.

PostgreSQL COPY loads operational data before validating the foreign keys in
bulk. All 17 relationships are present and validated in the resulting canonical
schema. The three query files under `benchmark/scenario/` are the operational
SQL the fictional teams run - one nightly fact refresh for a single run date,
one Finance close for a single period, one Board pack run for a single period
at its run instant - and they are copied verbatim into the evidence directory.
The generator materializes the 36-month history by executing that same
committed text once per nightly load, close and pack run (a bounded
deterministic replay; nothing is rendered into the evidence files). Wrong Board
values are never inserted as chosen literals. Tests replay one run of each query
and require it to reproduce the stored rows exactly; nightly/monthly job runs
are all recorded as successful.

## Acceptance tests

Ordinary pytest runs the service-free smoke checks. PostgreSQL tests are skipped
unless **NORTHSTAR_TEST_DATABASE_URL** names a local PostgreSQL connection with
CREATE DATABASE permission. The tests create uniquely named disposable databases
and drop only the databases they created. Add **NORTHSTAR_QA_DEMO=1** to exercise
both scales, including the committed report's demo numbers.

```powershell
# Set NORTHSTAR_TEST_DATABASE_URL to the local QA administration database.
$env:NORTHSTAR_QA_DEMO = '1'
.\.venv\Scripts\python.exe -m pytest --durations=10 --tb=short
git diff --check
```

The suite independently checks lifecycle chronology and amounts, actual cost
changes, all three surfaces, historical versus horizon Board reruns, all bridge
lines, materiality on both scales, metadata gaps, evidence leakage, ground-truth
separation, determinism and every generated amount/rate in the sample report.
A negative control changes a Board value inside a rolled-back test transaction
and requires the independent reconciliation to reject it. A second PostgreSQL
CLI smoke generation compares all generated files byte-for-byte, including
hidden hashes covering all historical reporting rows.

The committed PDF contains uncompressed deterministic text streams so its numeric
content can be checked without adding a PDF library to the project dependencies.
It was visually inspected after rendering all pages. PDF authoring is a one-off
artifact operation; no report-generation framework is part of this repository.

## Exact local QA setup used

Executed acceptance results: full smoke/demo + PostgreSQL/offline suite,
**49 passed, 5 intentional skips**; service-free run, **22 passed, 12 skips**;
final report presentation re-check against a fresh PostgreSQL demo, **2 passed**.
The full run includes materiality, lifecycle, historical reproduction,
same-interpreter repeat generation, no-leak checks and report consistency.
Smoke core CSVs were also byte-identical between CPython 3.12 and 3.14.
Runtime versions used: CPython 3.12.10, psycopg 3.3.5, DuckDB 1.5.5 and pytest 9.1.1.

Windows, CPython 3.12, PostgreSQL **17.2** binaries installed under
`C:\Program Files\PostgreSQL\17\bin`. A separate cluster was initialized at
`benchmark/data/qa/pg17`, bound only to `127.0.0.1:55432`, with local disposable
role `northstar`, UTF-8 encoding and C locale. It does not use an existing company
or application database. The cluster uses trust authentication solely for this
loopback-only disposable synthetic QA environment.

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\initdb.exe' -D "$PWD\benchmark\data\qa\pg17" -U northstar -A trust --encoding=UTF8 --locale=C
& 'C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe' -D "$PWD\benchmark\data\qa\pg17" -l "$PWD\benchmark\data\qa\pg17.log" -o '-p 55432 -h 127.0.0.1' start
& 'C:\Program Files\PostgreSQL\17\bin\createdb.exe' -h 127.0.0.1 -p 55432 -U northstar northstar_smoke
& 'C:\Program Files\PostgreSQL\17\bin\createdb.exe' -h 127.0.0.1 -p 55432 -U northstar northstar_demo_final
```

Generation DSNs were supplied externally for those databases; the QA DSN used
the same host, port and role with the `postgres` administration database. To stop
this exact disposable cluster after use:

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe' -D "$PWD\benchmark\data\qa\pg17" stop -m fast
```

An internal DuckDB mirror can be generated without PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -m benchmark.load_duckdb --profile smoke --output benchmark/data/offline
```

Use a fresh output location if its mirror database already exists. This command
is a development convenience and does not substitute for PostgreSQL acceptance.
