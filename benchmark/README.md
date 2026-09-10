# Northstar Distribution — Demo Environment Architecture

Design for the revised M0 synthetic demo environment. Governed by
[`../Current Assignment.md`](../Current%20Assignment.md); on conflict, that
document (and above it, `SPEC.md` including **Amendment 001**) wins.

Northstar Distribution is a **fictional** B2B distributor. Every record is
synthetic. Northstar is a **demo dataset** — a synthetic demonstration
environment — not an industry benchmark, and it is never described as one.

---

## 1. What this environment is for

Northstar exists to make one thing demonstrable end to end: a realistic
management reporting dispute — Revenue and Margin disagreeing across
reporting surfaces — that can be investigated with evidence, reconciled,
and explained to an executive. It is not a general-purpose data-health
benchmark and does not attempt to exercise the full six-dimension /
42-check methodology library (that library remains documented in `SPEC.md`
as internal methodology, not an implementation target for this milestone).

## 2. Components

```
benchmark/
├── generate.py        # deterministic generator targeting PostgreSQL (M0 implementation)
├── load_duckdb.py     # optional dev/test-only mirror into DuckDB (M0 implementation)
├── config/
│   └── benchmark.toml # canonical seed, scenario config, scale profiles, output paths
├── data/               # generated output (gitignored): DuckDB dev mirror, exports
└── ground_truth/       # generated output (gitignored): hidden reconciliation ground truth
```

The one sample Reporting Reliability Audit produced from this environment
lives under `report/samples/` (a committed deliverable — see
`Current Assignment.md` §11.9), not here.

Execution contract:

```bash
python benchmark/generate.py --profile demo    # loads into PostgreSQL
python benchmark/generate.py --profile smoke   # small profile for fast tests
python benchmark/load_duckdb.py                # optional: dev/test DuckDB mirror
```

`generate.py` reads all tunables from `benchmark/config/benchmark.toml`,
writes to the configured PostgreSQL target (connection details via
environment variable, never hard-coded credentials), and takes no network
access beyond that local/target database. It emits no wall-clock-dependent
content.

## 3. Environment choice: PostgreSQL is canonical

Per `SPEC.md` Amendment §O, **PostgreSQL is the canonical Northstar
environment.** It plausibly represents the initial ICP's actual
environment: operational tables, analytical views, legacy schemas,
accumulated technical debt, and reporting logic expressed as SQL rather than
as clean exports.

**DuckDB is internal-only** — a convenience for test utilities and local
comparison during development. It must never be presented as Northstar's
organizational data platform, and no product-facing material may describe
Northstar as DuckDB-based.

**BigQuery is deferred** — do not introduce it to look enterprise-grade;
only add it if a real engagement requires it (Amendment §O).

## 4. Simulated world

- **History window:** ~3 years of order activity ending at a configured
  as-of date.
- **Business shape:** B2B distribution — companies buying from a product
  catalog, paying invoices, occasionally returning goods. Generic enough
  that it implies no real employer.
- **Organizational realism:** Northstar's data environment should read like
  it evolved organically — accumulated tables, a legacy customer table
  that one report still joins against, informal notes, a partially
  documented schema — not like a curated answer key. Per Amendment §N,
  do **not** build a single tidy "metadata registry" or "metric
  definitions" table as the primary carrier of organizational knowledge.
  Where such evidence exists, prefer scattered, partial, sometimes-stale
  sources: PostgreSQL `COMMENT ON TABLE`/`COMMENT ON COLUMN` metadata
  (present for some objects, absent or stale for others), a handful of
  informal text notes, a job/run log, and one ad hoc analyst CSV export —
  never a single table that, if read, would hand an assessor the answers.

## 5. The reconciliation scenario

Northstar must contain **at least one realistic Revenue/Margin dispute**
(a third KPI may be added if it strengthens the story, per Amendment §R),
reproducible across **at least three reporting surfaces** that compute the
same underlying business activity differently:

| Surface | Role | Plausible formula |
|---|---|---|
| `finance_monthly_report` | Finance's monthly extract/snapshot | e.g. revenue recognized net of returns and tax, at invoice date |
| `mgmt_board_kpis` | Management/board reporting query | e.g. revenue at order date, including in-flight (unshipped) orders, joined against the legacy customer table |
| `sales_dashboard_kpis` | Sales dashboard / analytical view | e.g. gross order value including cancelled-but-not-yet-reversed orders, excluding returns processed after month-end |

The **specific** mechanism(s) chosen must be plausible and documented, drawn
from Amendment §R's list: order-status inclusion, invoice-vs-order date,
returns handling, discounts, tax, shipping, late-arriving transactions,
cancellation handling, reporting grain, or restatement timing. **Do not**
create the disagreement by inserting arbitrary wrong numbers — every
divergence must be explainable as "surface X's query does Y, surface Z's
query does not."

Each reporting surface must be **computed from the operational data by its
own real logic** (a SQL view or a deterministically-populated snapshot
table), not hardcoded — so that recomputing from operational data actually
reproduces each surface's figure (this is directly tested; see
`Current Assignment.md` §10.3).

## 6. Schema

### Operational data (PostgreSQL, canonical Northstar schema)

- **customers** — current canonical customer table.
- **customer_master_legacy** — a superseded customer table, still queried by
  at least one reporting surface (a plausible cause of divergence: different
  customer population/segmentation between surfaces).
- **products**
- **orders**
- **order_items**
- **payments**
- **returns**

Column-level detail is an implementation decision for `generate.py`, guided
by the reconciliation mechanism chosen (§5) — e.g. if invoice-vs-order date
is the chosen mechanism, `orders` needs both an `order_date` and an
`invoice_date`, and `payments`/`returns` need timestamps that can land in
different reporting months.

### Reporting-surface artifacts

- **finance_monthly_report**, **mgmt_board_kpis**, **sales_dashboard_kpis**
  — per §5. Implemented as SQL views or snapshot tables per what best fits
  the chosen mechanism (a view for a live query-shape difference; a
  snapshot table for a timing/restatement difference).

### Fragmented evidentiary artifacts (not a clean registry)

- `COMMENT ON TABLE` / `COMMENT ON COLUMN` metadata — present for some
  objects, missing or stale for others.
- A small **job/run log** table recording generation/refresh runs for the
  reporting surfaces (freshness evidence for a supporting finding, if used).
- One ad hoc **CSV export** representing an analyst's working extract
  (usable for the secondary regulatory/PII hypothesis in `SPEC.md`
  Amendment §L, if a limited synthetic-PII example is included — this
  export is the only place PII may appear, and only in clearly synthetic
  form).
- Informal **ownership/documentation notes** (free text, not a structured
  table) — incomplete and possibly out of date, standing in for the kind
  of tribal knowledge a real mid-market company actually has.

## 7. Scale

Per Amendment §P, priority order is business-semantic realism >
coherent transaction logic > realistic reporting disagreement > sufficient
volume > raw row count. Two profiles may coexist in
`benchmark/config/benchmark.toml`:

- **`demo`** — the canonical scale for the sample report: on the order of
  10⁴ customers, low thousands of products, 10⁵–10⁶ orders, low millions of
  order_items, ~3 years of history.
- **`smoke`** — a small profile (hundreds to low thousands of rows) used by
  the test suite for fast, deterministic runs.

Exact counts are configuration, not a success criterion, and may be tuned
without triggering a new assignment.

## 8. Supporting findings (optional, bounded)

The sample report may include a small number of findings outside metric
consistency if they materially improve realism (Amendment §T):

- a freshness issue affecting one reporting surface (tie to the job/run
  log);
- a duplicate or missing transaction affecting the reconciliation;
- undocumented reporting logic (tie to missing `COMMENT ON` metadata);
- unclear ownership of one of the disputed metrics;
- one limited synthetic-PII example, if used to demonstrate the secondary
  regulatory hypothesis.

These stay strictly supporting evidence for the one scenario. They must not
reopen full six-dimension coverage or grow into a general defect catalog.

## 9. Ground truth

`benchmark/ground_truth/` — machine-readable, generated output, structurally
separate from assessment- and report-visible data, **never** read by the
future assessment workflow. Per Amendment §S, it documents:

- the intended underlying business truth for the disputed metric(s);
- which reporting surfaces differ, and by how much;
- the specific planted mechanism(s) causing each surface's number to
  diverge;
- the expected reconciliation result a correct audit should reach;
- any planted supporting-finding issues from §8.

No 42-check or six-dimension coverage is required in the ground truth — only
what the built scenario actually needs, so a QA reviewer can verify that the
sample report's conclusion matches the intended answer.

Example shape (illustrative, not mandatory):

```json
{
  "manifest_version": 1,
  "scenario": "northstar-revenue-margin-reconciliation",
  "seed": 20260910,
  "underlying_truth": {
    "metric": "revenue",
    "period": "2026-08",
    "true_value": 4128500000
  },
  "surfaces": [
    {"name": "finance_monthly_report", "reported_value": 4128500000, "mechanism": null},
    {"name": "mgmt_board_kpis", "reported_value": 4356200000, "mechanism": "includes_unshipped_orders"},
    {"name": "sales_dashboard_kpis", "reported_value": 4402100000, "mechanism": "excludes_late_returns"}
  ],
  "expected_reconciliation": {
    "recommended_definition": "finance_monthly_report",
    "rationale": "Recognizes revenue only on shipped, invoiced orders net of returns processed through period end."
  }
}
```

## 10. The sample report

The primary M0 deliverable (Amendment §U) is one presentable **Reporting
Reliability Audit** built from this environment, committed under
`report/samples/`. It must walk the full value chain:

```
management question → conflicting numbers → source evidence → reconciliation
→ root cause → business impact → recommended definition → owner/remediation
→ re-check path
```

and, per Amendment §I, present:

- a **per-metric verdict** (`RECONCILED` / `CONFLICTING` / `UNVERIFIABLE`)
  for each assessed metric;
- **Evidence Coverage** for the scenario (how much of the relevant evidence
  was actually inspected);
- **definition reconciliation** — the observed definitions, where each is
  used, and the recommended canonical definition for the decision at hand;
- **business impact**, distinguishing measured from inferred impact;
- a **remediation sequence** (immediate correction, ownership decision,
  definition change, data/query correction, report correction, longer-term
  prevention).

It must be readable by a CFO/COO and independently verifiable by a
technically literate reviewer against the generated evidence. It is a
one-off hand-assembled artifact for this milestone — not the output of a
general report-generation engine (that remains out of scope; see
`Current Assignment.md` §5).

## 11. Determinism & synthetic-data rules

Order of operations in `generate.py`:

1. Load config (including which scale profile); fail fast on missing/
   invalid keys.
2. Build the operational data in dependency order: products → customers
   (+ `customer_master_legacy`) → orders → order_items → payments → returns.
3. Materialize the three reporting-surface artifacts, each via its own real
   logic per the chosen mechanism(s) — never hardcoded figures.
4. Attach fragmented evidentiary artifacts (§6): comments, job log, CSV
   export, ownership notes — including deliberate gaps and staleness.
5. Write the hidden ground-truth manifest (§9) — sorted keys, fixed
   separators, no generation-time timestamps.

Determinism rules (binding):

- one `random.Random(f"{seed}:{table_name}")` stream per table/surface;
  scenario injection uses its own derived streams (never share a stream
  across independent generators);
- prefer `random()` / `getrandbits()` over `sample()` / `choices()` /
  `shuffle()` where practical — only the former are contracted stable
  across CPython versions;
- reproducibility contract: **byte-identical** output for the same
  code + config + seed on the same Python feature release; **materially
  identical** across supported Python ≥3.12;
- never iterate a `set`/`dict` where order reaches the output without
  sorting first;
- all dates computed relative to the configured as-of date; no
  `datetime.now()`, `time.time()`, `os.urandom`, or `uuid4`;
- stdlib only for randomness; runtime dependencies are `psycopg` (loading
  into PostgreSQL) and, for internal test/dev use only, `duckdb`.

Synthetic-data safety rules (binding):

- names/companies assembled from fictional word lists written for this
  project — not sampled from any real directory, customer list, or employer
  material;
- if the optional synthetic-PII example (§8) is used: emails only under
  `example.com`/`example.org`/`northstar.example`, phone numbers only in
  fictional ranges, addresses synthetic — and limited to the single CSV
  export called for in §6, not spread across the schema.

## 12. PostgreSQL loading notes

`generate.py` connects to a target PostgreSQL instance (connection string
via an environment variable, e.g. `NORTHSTAR_DATABASE_URL` — never
hard-coded) and creates the schema from scratch. `load_duckdb.py` is a
separate, optional dev/test convenience that mirrors the same logical data
into a local DuckDB file for fast local inspection and for tests that don't
need a live PostgreSQL instance; it is never Northstar's canonical
environment (see §3).
