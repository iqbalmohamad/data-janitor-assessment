# Current Assignment — M0: Reproducible Broken Company

**Status:** Defined — ready for implementation
**Milestone:** M0
**Assignment owner:** Technical Lead
**Canonical seed:** `20260910`

---

## 1. Objective

Establish a fully synthetic, deterministic, inspectable benchmark environment
— the fictional B2B distributor **Northstar Distribution** — containing known,
intentionally injected data-health defects across all six Data Janitor
assessment dimensions, together with a machine-readable ground-truth manifest
of those defects.

## 2. Why M0 exists

The Data Janitor assessment engine (later milestones) must be tested against a
subject whose defects are *known in advance*. Without a stable, reproducible
"broken company," check results cannot be validated honestly and regressions
cannot be detected. M0 proves we have a stable test subject **before** any
assessment logic is built. The benchmark is the foundation every subsequent
milestone stands on.

## 3. Canonical references

1. `SPEC.md` — canonical product truth. **Currently absent from the
   repository; the Product Owner must add it.** When it lands, reconcile this
   assignment against it. On any conflict, `SPEC.md` wins.
2. `Current Assignment.md` (this document) — canonical bounded engineering
   assignment for M0.
3. `benchmark/README.md` — benchmark architecture: schemas, defect catalog,
   ground-truth format, determinism rules. Subordinate to this document.
4. `benchmark/config/benchmark.toml` — canonical generation configuration
   (seed, row counts, output locations).

## 4. Scope

M0 delivers, in this order:

1. **Generator** — `benchmark/generate.py`: a deterministic, config-driven
   Python 3.12+ program that produces all Northstar datasets and the
   ground-truth manifest from code + `benchmark/config/benchmark.toml` +
   the canonical seed.
2. **Datasets** — the ten required datasets plus two justified optional
   datasets (see §7): `customers`, `products`, `orders`, `order_items`,
   `payments`, `returns`, `customer_export`, `metric_definitions`,
   `pipeline_runs`, `dataset_registry`, `sales_summary`,
   `customer_master_legacy`.
3. **Injected defects** — the defect catalog in `benchmark/README.md` §4,
   covering all six dimensions.
4. **Ground truth** — a machine-readable manifest of every injected defect,
   written to `benchmark/ground_truth/`, separate from assessment inputs.
5. **DuckDB loadability** — a documented, scripted path from generated output
   into a local DuckDB database.
6. **Tests** — see §10.
7. **Documentation** — how to generate, where data and ground truth live, how
   to run tests.

## 5. Non-scope

Explicitly **not** part of M0:

- any of the 42 assessment checks;
- profiling, normalized findings, scoring, risk prioritization;
- AI readiness classification;
- report generation (executive or otherwise);
- remediation of any kind (the product is read-only over source data);
- LLM integration of any kind;
- SaaS infrastructure: authentication, accounts, multi-tenancy, billing, web
  dashboards, customer portals, scheduled monitoring, notification systems,
  SSO, cloud deployment;
- distributed processing technology;
- performance engineering beyond what the benchmark scale requires;
- speculative abstraction "for future milestones."

## 6. Expected repository changes

M0 implementation touches only:

```
benchmark/generate.py          # new — the generator (may add small modules
benchmark/…                    #        beside it if generate.py grows unwieldy)
benchmark/load_duckdb.py       # new — loads generated output into DuckDB
benchmark/config/benchmark.toml# may be tuned (row counts, defect params)
benchmark/README.md            # updated if implementation refines the design
tests/…                        # new tests per §10
README.md                      # generation/usage instructions
Current Assignment.md          # status updates only
```

`benchmark/data/` and `benchmark/ground_truth/` are **generated output** and
stay gitignored. Do not commit generated bulk data as source of truth. Small
committed fixtures for tests are acceptable only if clearly labeled and tiny.

## 7. Benchmark requirements

Full architecture: `benchmark/README.md`. Binding requirements:

- **Fictional company.** Northstar Distribution is entirely fictional. Do not
  model it on any real employer, client, or organization. Schema stays generic
  B2B distribution: customers, product catalog, orders, payments, returns,
  plus operational metadata (metric definitions, pipeline runs, dataset
  registry).
- **Required datasets:** `customers`, `products`, `orders`, `order_items`,
  `payments`, `returns`, `customer_export`, `metric_definitions`,
  `pipeline_runs`, `dataset_registry`.
- **Optional datasets, included with justification:**
  - `sales_summary` — required to realize reconciliation-mismatch and
    conflicting-Revenue defects (an aggregate that disagrees with the
    transactional data it claims to summarize);
  - `customer_master_legacy` — required to realize deprecated-dataset,
    unclear-source-of-truth, and obsolete-dataset-still-available defects.
  No further domains may be added in M0.
- **Synthetic PII only.** Emails, phone numbers, and addresses are generated
  from fictional patterns (e.g. reserved example domains, invalid/fictional
  phone ranges). No real personal information anywhere in the repository.
- **Defect coverage.** All six dimensions carry injected defects per the
  catalog in `benchmark/README.md` §4, which includes at minimum: duplicate
  customers, orphan relationships, duplicate transactions, missing critical
  values, invalid business values, reconciliation mismatches; missing table
  descriptions, incomplete column documentation, missing source traceability,
  stale/deprecated datasets without lifecycle status; conflicting definitions
  of Revenue, Active Customer, and Net Sales; unnecessary PII replication and
  a poorly governed export dataset; ownerless critical datasets, missing
  business ownership, unclear source of truth, obsolete-but-available
  datasets; stale datasets, failed pipelines, duplicate/reprocessed ingestion,
  irregular volume, missing freshness expectations.
- **Scale.** Row counts per `benchmark/config/benchmark.toml` (order of
  10⁴–10⁵ rows in the largest tables). Comfortably laptop-scale; no
  infrastructure beyond Python + DuckDB.
- **Formats.** CSV is the primary generated format (inspectable); loading
  into DuckDB is scripted; Parquet export must remain possible via DuckDB
  (no extra dependency for it).

## 8. Ground-truth requirements

- Written by the generator to `benchmark/ground_truth/ground_truth.json`.
- Machine-readable JSON conforming to the schema in `benchmark/README.md` §5:
  one entry per injected defect with stable ID (`GT-<DIM>-NNN`), dimension,
  defect type, human-readable description, affected datasets, evidence
  locators (the concrete keys/rows affected), and expected counts.
- Contains enough metadata for future QA to verify a check found *exactly*
  the injected defects (IDs and counts, not just categories).
- Kept **separate from assessment inputs**: it lives in
  `benchmark/ground_truth/`, never inside `benchmark/data/`.
- The future assessment engine must **never** read the ground-truth manifest
  during normal execution. It is test/QA input only. Tests enforce the
  directory separation; later milestones must preserve it.

## 9. Deterministic-generation requirement

- Canonical seed: **`20260910`**, stored once in
  `benchmark/config/benchmark.toml`, never hard-coded elsewhere.
- Same code + same configuration + same seed ⇒ **byte-identical** generated
  datasets and ground-truth manifest.
- No wall-clock reads in generated content: all dates/timestamps derive from
  the configured simulation anchor date (`as_of_date` in config).
- No iteration over unordered structures where order affects output; no
  reliance on hash randomization; per-table RNG streams derived
  deterministically from the canonical seed (see `benchmark/README.md` §6) so
  editing one table's generator does not perturb the others.
- Only the Python standard library RNG (`random.Random`) may be used for
  randomness; no dependency whose output can drift across versions without a
  pin.

## 10. QA expectations

Implemented under `tests/`, runnable with `pytest` locally on Python 3.12+.
Minimum coverage:

1. **Generator execution** — generation runs end-to-end from a clean state
   and exits successfully.
2. **Expected tables** — every dataset listed in §7 is produced.
3. **Approximate row counts** — each dataset's row count is within a
   tolerance band of the configured target (bands defined in tests, since
   defect injection perturbs exact counts).
4. **Representative injected defects** — for each of the six dimensions, at
   least one injected defect is verified to actually exist in the generated
   data (e.g. the duplicate customer pairs named in ground truth really are
   near-duplicates; a payment named as duplicated really appears twice).
5. **Deterministic generation** — generating twice with the canonical seed
   into two directories produces identical output (byte comparison or stable
   hash comparison).
6. **Ground-truth integrity** — manifest parses, every entry has the required
   fields, IDs are unique, every referenced dataset exists.
7. **DuckDB loadability** — generated output loads into DuckDB and the
   expected tables are queryable.

Tests must not require network access.

## 11. Definition of Done

M0 is done when all of the following hold and are verified:

1. Northstar benchmark generation runs locally on Python 3.12+.
2. Generation starts from code + config, not manually maintained bulk data.
3. Re-running with seed `20260910` reproduces identical output.
4. All required benchmark datasets exist (§7).
5. Synthetic data contains no real personal or employer information.
6. Known intentional defects cover all six assessment dimensions.
7. Ground truth documents the injected defects separately (§8).
8. Generated output can be loaded into DuckDB via the scripted path.
9. The tests in §10 exist and pass.
10. Documentation explains how to generate Northstar, where generated data
    lives, where ground truth lives, and how to run tests.
11. No assessment scoring engine has been implemented (beyond what §10
    minimally requires to validate the benchmark itself).
12. No report generator has been implemented.
13. No SaaS infrastructure has been introduced.

## 12. Explicit prohibitions

- **No employer/client material** — no code, schemas, datasets, queries,
  documentation, metrics, business processes, or client material from any
  employer. Northstar is fictional and independently designed.
- **No real PII** — anywhere, including test fixtures, examples, and docs.
- **No LLM dependency** — generation, ground truth, and tests run fully
  offline with no AI service.
- **No committed bulk data** — generated output stays out of git.
- **No new domains** beyond the datasets in §7.
- **No assessment engine, scoring, AI-readiness classification, or report
  generation** in this milestone.
- **No SaaS scaffolding**, including "empty for future use" directories.
- **No distributed processing** or infrastructure beyond Python + DuckDB.
- **Never wire ground truth into assessment inputs.**

## 13. Expected implementation handoff

An engineer implementing M0 starts from this baseline and should:

1. Read this document, then `benchmark/README.md` (architecture and defect
   catalog), then `benchmark/config/benchmark.toml`.
2. Implement `benchmark/generate.py` against that architecture: clean-slate
   generation of base data first, defect injection second, ground-truth
   manifest emission last (see `benchmark/README.md` §6 for pipeline order
   and determinism rules).
3. Implement `benchmark/load_duckdb.py`.
4. Implement the §10 test suite; the existing `tests/test_benchmark_config.py`
   already pins the canonical seed and dataset list.
5. Update `README.md` usage instructions to match reality.
6. Keep every change inside §6's file list; anything outside it needs a new
   assignment.
7. When `SPEC.md` lands, reconcile: if it contradicts this assignment,
   `SPEC.md` wins — raise the conflict, don't silently diverge.

Deliverable of the handoff: a branch/PR against `main` in which the §11
Definition of Done is demonstrably satisfied, with test output included in
the PR description.
