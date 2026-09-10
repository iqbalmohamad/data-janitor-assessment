# Current Assignment — M0: Reporting Reliability Demo Environment

**Status:** Scenario Design Gate PASSED — ready for M0 implementation
authorization (Scenario Contract in `benchmark/README.md`, Part II, is
approved and final; implementation not yet started)
**Milestone:** M0 (revised)
**Assignment owner:** Technical Lead
**Canonical seed:** `20260910`

> **Supersession notice.** This document replaces the prior M0 assignment
> ("M0 — Reproducible Broken Company," covering all six assessment
> dimensions), which is retired per `SPEC.md` **Amendment 001** (effective
> 2026-09-10, §AH). Nothing from the prior assignment survives except where
> this document explicitly says so. If you have the prior assignment open,
> discard it.

> **Process gate.** The M0 scenario is fixed by the Scenario Contract
> (`benchmark/README.md`, Part II, sections SC-1 to SC-18). The agreed
> sequence is: Scenario Contract → Scenario Design Gate → M0 implementation
> authorization. The Scenario Design Gate has **PASSED** (Product Manager /
> Technical Lead review, criteria A–H). M0 implementation work (generator,
> schema, surfaces, sample report) is authorized to begin on a fresh branch
> created from `main` after the Scenario Contract PR merges; it is not part
> of that PR.

---

## 1. Objective

Produce a realistic, deterministic synthetic environment for the fictional
company **Northstar Distribution** — now positioned as a **demo dataset**,
not an industry benchmark — containing one credible management reporting
dispute (Revenue and Margin disagreeing across reporting surfaces), and use
it to produce **one presentable sample Reporting Reliability / Metric
Consistency Audit**. A machine-readable hidden ground-truth manifest
documents the planted causes of the dispute, separate from assessment
inputs.

## 2. Why M0 exists (revised)

`SPEC.md` Amendment 001 changes the commercial thesis: Data Janitor's first
validated wedge is not a broad six-dimension Data Health Assessment but a
narrow, evidence-backed reconciliation of management numbers that disagree
across systems. Before spending on buyer validation, the founder needs a
credible, professional artifact that demonstrates the full commercial value
chain — management question → conflicting numbers → evidence → reconciliation
→ business impact → recommended definition → owner/remediation — end to end,
on one scenario. M0 exists to produce exactly that artifact and the minimal
environment needed to generate it. It is **not** a universal Data Janitor
benchmark and does not need to exercise every dimension of the intellectual
framework.

## 3. Canonical references

1. `SPEC.md`, including **Amendment 001** — canonical product truth.
   Amendment 001 overrides any conflicting original section; non-conflicting
   original sections remain valid. This assignment is reconciled against
   both (2026-09-10).
2. `Current Assignment.md` (this document) — canonical bounded engineering
   assignment for the revised M0.
3. `benchmark/README.md` — Northstar demo-environment architecture and
   the binding **Scenario Contract** (Part II): the August 2026
   Finance/Sales/Board scenario, lifecycle and timestamp model, reporting
   surfaces, required decomposition, evidence inventory, ground-truth
   format, sample-report implications. Subordinate to this document.
4. `benchmark/config/benchmark.toml` — canonical generation configuration.

## 4. Scope

M0 delivers, in this order:

1. **Demo environment** — a PostgreSQL schema for Northstar Distribution
   (canonical environment per Amendment §O), generated deterministically
   from code + config + the canonical seed, containing:
   - core operational data following the lifecycle model fixed in the
     Scenario Contract (customers, products, product cost history, orders,
     order_items, invoices, invoice_lines, payments, returns, return_items,
     credit_notes — `benchmark/README.md` §SC-7);
   - three reporting surfaces that compute Revenue/Margin differently from
     the same underlying activity (the Finance P&L extract, the Sales
     dashboard view, the Management/Board KPI snapshot — §SC-9);
   - fragmented, realistic evidentiary artifacts (table/column comments,
     a job/run log, an ad hoc CSV export, informal ownership notes) rather
     than one tidy metadata registry table — per Amendment §N.
2. **Reconciliation scenario** — the August 2026 Revenue + Gross Margin
   dispute fixed by the Scenario Contract: Finance and Sales are each
   defensible for their own decision context; the Board pack carries the
   actual hybrid defect; the differences decompose into definition, timing,
   cost-basis, and defect components (§SC-10) — not arbitrary wrong
   numbers.
3. **Hidden ground truth** — a machine-readable manifest of the intended
   underlying business truth, which surfaces differ and why, the specific
   planted mechanisms, and the expected reconciliation result. Lives in
   `benchmark/ground_truth/`, structurally separate from assessment inputs,
   never read by the future assessment workflow.
4. **Two supporting findings** outside metric consistency, both tied to
   the dispute (§SC-11): the freshness/snapshot gap between the Board pack
   and the Finance close, and the unowned, undocumented Board-pack
   definition of Revenue. **No PII scenario is included in M0.** These
   remain supporting evidence — they do not reopen the full six-dimension
   scope.
5. **One presentable sample Reporting Reliability Audit** — the primary M0
   output (Amendment §U). Demonstrates the complete value chain end to end,
   readable by a CFO/COO, with evidence a Head of Data could verify. This
   report is hand-assembled from the generated evidence for M0; it does not
   require a general-purpose report-generation engine.
6. **Tests** — see §9.
7. **Documentation** — how to generate Northstar, where the data and ground
   truth live, how to run tests, and how to read the sample report.

## 5. Non-scope

Explicitly **not** part of the revised M0 (Amendment §V, §AD):

- the full 42-check catalog, or any general-purpose check-execution engine;
- full six-dimension coverage as a design goal — the demo only needs what
  the Revenue/Margin scenario and its limited supporting findings require;
- a generic Data Health Score, composite scoring, or Evidence Coverage
  math beyond what's needed to state coverage for the one scenario in the
  sample report;
- AI Readiness classification of any kind;
- a general connector framework or multi-database support — PostgreSQL
  (canonical) and DuckDB (internal test/comparison use only) are the only
  environments;
- a reusable/templated report-generation engine — M0 produces one sample
  report, not a report generator product;
- remediation execution of any kind (the product is read-only over source
  data);
- LLM integration of any kind;
- SaaS infrastructure: authentication, accounts, multi-tenancy, billing, web
  dashboards, customer portals, scheduled monitoring, notification systems,
  SSO, cloud deployment, continuous monitoring;
- BigQuery/Snowflake connectors;
- landing-page implementation, marketing assets, or public proof-package
  polish (Amendment §W) — a one-page commercial offer sheet and a minimal
  security/data-handling pack are the only other v0.1 proof-package assets,
  and neither is part of this engineering assignment;
- distributed processing technology;
- speculative abstraction "for future milestones."

## 6. Expected repository changes

M0 implementation touches only:

```
benchmark/generate.py          # new — deterministic generator targeting PostgreSQL
benchmark/load_duckdb.py       # new — optional dev/test mirror into DuckDB (§O)
benchmark/config/benchmark.toml# may be tuned (row counts, scenario params)
benchmark/scenario/            # new — surface SQL and note/extract sources fixed by the Scenario Contract
benchmark/README.md            # updated if implementation refines the design (within the Scenario Contract)
benchmark/ground_truth/        # generated output (gitignored)
report/samples/                # new — the one sample Reporting Reliability Audit
tests/…                        # new tests per §9
README.md                      # generation/usage instructions
Current Assignment.md          # status updates only
```

`benchmark/data/` and `benchmark/ground_truth/` are **generated output** and
stay gitignored. The sample report under `report/samples/` is a committed
deliverable (it is the M0 proof artifact), not generated output to discard.

## 7. Benchmark requirements

Full architecture: `benchmark/README.md`. Binding requirements:

- **Environment.** PostgreSQL is the canonical Northstar environment
  (Amendment §O). DuckDB may be used internally for test utilities and local
  comparison only — never presented as Northstar's organizational platform.
- **Demo dataset, not benchmark.** Public and internal language calls
  Northstar a "demo dataset" or "synthetic demonstration environment," never
  an industry benchmark (Amendment §M).
- **Realistic fragmentation.** No single tidy metadata-registry table
  stands in for organizational knowledge. Ownership, documentation, and
  lineage evidence is deliberately scattered, partial, and sometimes stale —
  across table/column comments, informal notes, job logs, and ad hoc
  exports — the way it actually is at a mid-market company (Amendment §N).
- **The scenario is the point.** At least one Revenue+Margin dispute must
  be reproducible across ≥3 reporting surfaces, caused by a plausible,
  identifiable mechanism (see §4.2). No arbitrary corrupted values.
- **Scale.** Guided by Amendment §P — business-semantic realism and a
  believable reconciliation take priority over raw row count. A canonical
  "demo" scale profile (order of 10⁴ customers, 10⁵–10⁶ orders, low-millions
  order_items, ~3 years of history) may coexist with a smaller "smoke" scale
  profile used for fast tests. Exact counts are not a success criterion.
- **No PII scenario.** M0 plants no privacy finding and contains no
  natural-person data (§SC-16). The secondary regulatory hypothesis
  (Amendment §L) is tested commercially, not in this demonstration.

## 8. Ground-truth requirements

- Written by the generator to `benchmark/ground_truth/`, machine-readable,
  and structurally separate from assessment/report inputs (never read by
  the future assessment workflow — Amendment §S).
- Documents: the intended underlying business truth for the disputed
  metric(s); which reporting surfaces differ and by how much; the specific
  planted mechanism(s) causing each difference; and the expected
  reconciliation result a correct audit should reach.
- Does **not** need to cover all 42 checks or all six dimensions — only the
  scenario actually built.
- No answer flags may leak into assessment-visible data (table/column
  comments, exported files, or the demo schema itself).

## 9. Deterministic-generation requirement

- Canonical seed: **`20260910`**, stored once in
  `benchmark/config/benchmark.toml`, never hard-coded elsewhere.
- Same code + same configuration + same seed **on the same Python feature
  release** (e.g. CPython 3.12.x) ⇒ byte-identical generated SQL/data and
  ground-truth manifest. Across supported Python versions (≥3.12), output
  must remain materially identical — see the note on stable RNG primitives
  below.
- No wall-clock reads in generated content: all dates/timestamps derive from
  a configured simulation anchor date; no `datetime.now()`, `time.time()`,
  `os.urandom`, or `uuid4`.
- One `random.Random(f"{seed}:{table_name}")` stream per table/surface;
  defect/scenario injection uses its own derived streams. Prefer stable RNG
  primitives (`random()`, `getrandbits()`) over distribution helpers
  (`sample`, `choices`, `shuffle`) where practical, since only the former
  carry a cross-version stability guarantee.
- Loading into PostgreSQL must be idempotent against a clean target schema;
  regenerating from scratch must reproduce the same logical dataset.

## 10. QA expectations

Implemented under `tests/`, runnable with `pytest` locally on Python 3.12+,
without requiring a live PostgreSQL instance for the parts that don't need
one (a local PostgreSQL, e.g. via a disposable container, is acceptable for
the tests that do). Minimum coverage:

1. **Generator execution** — generation runs end-to-end from a clean state
   and exits successfully, using the "smoke" scale profile.
2. **Expected schema** — the core operational tables and all three
   reporting-surface artifacts exist.
3. **Reconciliation is real** — recomputing each reporting surface's
   Revenue/Margin figure from the underlying operational data reproduces
   that surface's reported number (i.e., the disagreement is a genuine
   product of differing logic, not a hardcoded mismatch).
4. **Ground-truth integrity** — the manifest parses, names the planted
   mechanism(s) and the expected reconciliation result, and is not
   reachable from assessment-visible data.
5. **Deterministic generation** — generating twice with the canonical seed
   produces identical output (byte or stable-hash comparison).
6. **Sample report consistency** — the numbers quoted in the sample report
   match the generated evidence and the ground truth's expected
   reconciliation result.

Tests must not require network access beyond a local/disposable PostgreSQL
instance under the tester's own control.

## 11. Definition of Done

The revised M0 is done when all of the following hold and are verified:

1. Northstar generation runs locally on Python 3.12+ against PostgreSQL.
2. Generation starts from code + config, not manually maintained bulk data.
3. Re-running with seed `20260910` reproduces byte-identical output on the
   same interpreter (per §9).
4. The operational tables and ≥3 reporting surfaces exist and are loadable.
5. Synthetic data contains no real personal or employer information.
6. The Revenue/Margin dispute is reproducible and traceable to a specific,
   documented mechanism — not an arbitrary corrupted value.
7. Ground truth documents the dispute separately from assessment inputs and
   is never read by the (not-yet-built) assessment workflow.
8. The tests in §10 exist and pass.
9. One presentable sample Reporting Reliability Audit exists under
   `report/samples/`, demonstrating the full value chain in §4.5 and
   readable by a non-technical executive while remaining verifiable by a
   technical reviewer.
10. Documentation explains how to generate Northstar, where generated data
    and ground truth live, how to run tests, and how to read the sample
    report.
11. No 42-check engine, composite scoring platform, or AI Readiness logic
    has been implemented.
12. No SaaS infrastructure, connector framework, or continuous-monitoring
    capability has been introduced.
13. Nothing claims Northstar is an industry benchmark.

## 12. Explicit prohibitions

- **No employer/client material** — no code, schemas, datasets, queries,
  documentation, metrics, business processes, or client material from any
  employer. Northstar is fictional and independently designed.
- **No real PII** anywhere, including test fixtures, examples, and docs.
- **No LLM dependency** — generation, ground truth, and the sample report
  run fully offline with no AI service.
- **No committed generated bulk data or ground truth** — both stay out of
  git; the sample report is the one committed deliverable artifact.
- **No full six-dimension buildout, no 42-check implementation, no
  composite scoring, no AI Readiness** — blocked per Amendment §AD until the
  Product Owner reauthorizes after commercial validation.
- **No SaaS scaffolding**, including "empty for future use" directories.
- **No BigQuery/Snowflake connector, no generic connector framework.**
- **No industry-benchmark framing** for Northstar.
- **No distributed processing** or infrastructure beyond
  Python + PostgreSQL (+ DuckDB for internal test use).
- **Never wire ground truth into assessment- or report-visible data.**
- **Do not proceed to further engineering once M0's Definition of Done is
  met** — Amendment §AA pauses engineering at that point pending commercial
  validation. Flag completion to the Product Owner rather than continuing
  into M1-shaped work.

## 13. Expected implementation handoff

An engineer implementing the revised M0 starts from this baseline and
should:

1. Read this document, then `benchmark/README.md`, then
   `benchmark/config/benchmark.toml`.
2. Do **not** redesign the reconciliation scenario: it is fixed by the
   Scenario Contract (§4.2, `benchmark/README.md` Part II) and approved at
   the Scenario Design Gate. Implement it as written; raise any needed
   change through the gate. The scenario is the point; the data volume is
   not.
3. Implement `benchmark/generate.py` against that design: operational data
   first, the three reporting-surface artifacts second (each computing its
   own figure from the operational data via its own logic — never a
   hardcoded number), fragmented metadata/documentation artifacts third,
   ground-truth manifest last.
4. Implement `benchmark/load_duckdb.py` only as a dev/test convenience, not
   as an alternate canonical path.
5. Implement the §10 test suite.
6. Hand-assemble the one sample Reporting Reliability Audit from the
   generated evidence, following the value chain in §4.5 and the
   customer-facing output shape in Amendment §I (per-metric verdict,
   evidence coverage, definition reconciliation, business impact,
   remediation sequence).
7. Update `README.md` usage instructions to match reality.
8. Keep every change inside §6's file list; anything outside it needs a new
   assignment.
9. Stop at the §11 Definition of Done and report completion to the Product
   Owner — do not continue into further engineering (§12, last bullet).
10. This assignment is reconciled against `SPEC.md` including Amendment 001
    as of 2026-09-10. If a later amendment contradicts it, `SPEC.md` wins —
    raise the conflict, don't silently diverge.

Deliverable of the handoff: a branch/PR against `main` in which the §11
Definition of Done is demonstrably satisfied, with test output and the
sample report included in the PR description.
