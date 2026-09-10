# Northstar Distribution — Benchmark Architecture

Design for the M0 synthetic benchmark. Governed by
[`../Current Assignment.md`](../Current%20Assignment.md); on conflict, that
document (and above it, `SPEC.md`) wins.

Northstar Distribution is a **fictional** B2B distributor. Every record is
synthetic. Nothing here models a real organization.

---

## 1. Components

```
benchmark/
├── generate.py        # deterministic generator (M0 implementation)
├── load_duckdb.py     # loads generated CSVs into a DuckDB database (M0)
├── config/
│   └── benchmark.toml # canonical seed, as-of date, row counts, output paths
├── data/              # generated output (gitignored): one CSV per dataset
└── ground_truth/      # generated output (gitignored): ground_truth.json
```

Execution contract:

```bash
python benchmark/generate.py                # uses benchmark/config/benchmark.toml
python benchmark/load_duckdb.py             # builds benchmark/data/northstar.duckdb
```

`generate.py` must be runnable from the repository root, read all tunables
from the config file, write datasets to `data/` and the manifest to
`ground_truth/`, and take no network access. Parquet export remains possible
via DuckDB (`COPY … TO … (FORMAT PARQUET)`); CSV is the primary format
because it is diffable and inspectable.

## 2. Simulated world

- **As-of date:** `as_of_date` in config (default `2026-09-01`). All
  generated dates derive from it; the generator never reads the wall clock.
- **History window:** ~24 months of orders ending at the as-of date.
- **Business shape:** B2B customers (companies with contact persons) buying
  from a catalog of distribution products (categories like packaging,
  fasteners, safety equipment, cleaning supplies — deliberately generic),
  paying invoices, occasionally returning goods.
- **Operational layer:** a metric glossary (`metric_definitions`), a pipeline
  run log (`pipeline_runs`), and a data catalog (`dataset_registry`) describe
  how Northstar *manages* its data — this is where most metadata, ownership,
  and reliability defects live.

## 3. Dataset schemas

Primary keys in **bold**. Types are DuckDB-friendly (INTEGER, DOUBLE, DATE,
TIMESTAMP, VARCHAR, BOOLEAN).

### customers
| column | notes |
|---|---|
| **customer_id** | `C` + zero-padded integer |
| company_name | fictional |
| contact_name | synthetic person name |
| contact_email | synthetic, `@example.com`/`.example` domains only |
| contact_phone | fictional pattern (e.g. `+1-555-…`) |
| billing_address / city / region / postal_code / country | synthetic |
| segment | e.g. wholesale / retail / online |
| status | active / inactive / (defect: inconsistent casing & stray values) |
| created_at | DATE |
| notes | free text (defect: occasionally contains PII) |

### products
**product_id**, sku, product_name, category, unit_cost, list_price,
introduced_at, discontinued_at (nullable), status.

### orders
**order_id**, customer_id → customers, order_date, status
(placed/shipped/delivered/cancelled), currency, subtotal_amount,
tax_amount, shipping_amount, total_amount, ship_address fields
(defect: PII replication), channel.

### order_items
**order_item_id**, order_id → orders, product_id → products, quantity,
unit_price, discount_pct, line_amount.

### payments
**payment_id**, invoice_number, order_id → orders, payment_date, amount,
method, status.

### returns
**return_id**, order_id → orders, order_item_id → order_items, return_date,
quantity, refund_amount, reason.

### customer_export
A flat "marketing export" snapshot: **export_row_id**, customer_id,
company_name, contact_name, contact_email, contact_phone, full_address,
lifetime_order_count, lifetime_revenue, exported_at. Deliberately
over-broad PII replication with no governance entry (see GT-PII/GT-OG).

### metric_definitions
**metric_id**, metric_name, definition_text, formula_text, owner_team
(nullable), source_dataset (nullable), effective_from, status. Contains the
conflicting Revenue / Active Customer / Net Sales definitions.

### pipeline_runs
**run_id**, pipeline_name, target_dataset, run_started_at, run_finished_at
(nullable), status (success/failed/running), rows_loaded (nullable),
triggered_by. ~24 months of run history for each pipeline.

### dataset_registry
**dataset_name**, description (nullable), owner_team (nullable),
business_owner (nullable), steward (nullable), source_system (nullable),
is_source_of_truth (nullable/conflicting), lifecycle_status (nullable),
freshness_sla_hours (nullable), last_documented_at (nullable),
column_docs_pct. One row per Northstar dataset (including the deprecated
ones). This is the main carrier of metadata/ownership defects.

### sales_summary *(optional, justified)*
**summary_id**, month, category, gross_revenue, net_revenue, order_count.
A monthly aggregate that does **not** reconcile with recomputation from
orders/order_items/returns (GT-DQ-006) and embodies a third, conflicting
Revenue formula.

### customer_master_legacy *(optional, justified)*
Same shape as `customers` minus `notes`, ~80% overlapping IDs with drifted
values, no lifecycle status in the registry, still listed as available.
Carrier of deprecated-dataset / unclear source-of-truth defects.

## 4. Defect catalog

Every defect below is injected deliberately, is deterministic under the
canonical seed, and gets a ground-truth entry. IDs are stable; do not renumber.

### Data Quality (DQ)
| ID | Defect | Mechanism |
|---|---|---|
| GT-DQ-001 | Duplicate customers | ~2% of companies re-inserted with new `customer_id`, name/email variants (casing, punctuation, domain typo) |
| GT-DQ-002 | Orphan relationships | Small sets of `orders.customer_id`, `order_items.product_id`, `returns.order_id` pointing at deleted/nonexistent keys |
| GT-DQ-003 | Duplicate transactions | A set of payments duplicated with same `invoice_number`/amount, new `payment_id`; a few orders double-inserted |
| GT-DQ-004 | Missing critical values | NULL `contact_email` on a slice of customers, NULL `order_date` on a slice of orders, NULL `amount` on a few payments |
| GT-DQ-005 | Invalid business values | Negative quantities, order dates after `as_of_date`, `total_amount` = 0 on delivered orders, undefined status codes |
| GT-DQ-006 | Reconciliation mismatches | `orders.total_amount` ≠ sum of line amounts + tax + shipping on a slice; `sales_summary` months that disagree with recomputation |

### Metadata & Documentation (MD)
| ID | Defect | Mechanism |
|---|---|---|
| GT-MD-001 | Missing table descriptions | NULL `description` in registry for several critical datasets |
| GT-MD-002 | Incomplete column documentation | `column_docs_pct` well under 100 for most datasets, 0 for some |
| GT-MD-003 | Missing source traceability | NULL `source_system` for datasets that clearly derive from others |
| GT-MD-004 | Deprecated dataset without lifecycle status | `customer_master_legacy` registered, actively loadable, `lifecycle_status` NULL |

### Metric Consistency (MC)
| ID | Defect | Mechanism |
|---|---|---|
| GT-MC-001 | Conflicting **Revenue** | ≥2 registry definitions (gross incl. shipping vs excl. tax/shipping) + a third formula implicit in `sales_summary` |
| GT-MC-002 | Conflicting **Active Customer** | One definition: order in last 90 days; another: order in last 12 months; different teams as owners |
| GT-MC-003 | Conflicting **Net Sales** | Definitions differ on excluding returns vs returns+discounts vs cancelled orders |

### Privacy & PII Hygiene (PII) — all PII synthetic
| ID | Defect | Mechanism |
|---|---|---|
| GT-PII-001 | Unnecessary PII replication | Contact/address PII copied into `orders` ship fields and `customer_export` beyond need |
| GT-PII-002 | Poorly governed export dataset | `customer_export` carries full PII, has no registry owner, no purpose, no lifecycle |
| GT-PII-003 | PII in free text | Synthetic emails/phone numbers embedded in `customers.notes` for a small slice |

### Ownership & Governance (OG)
| ID | Defect | Mechanism |
|---|---|---|
| GT-OG-001 | Critical datasets without owners | NULL `owner_team` for `orders`, `payments` in registry |
| GT-OG-002 | Missing business ownership | Technical owner set, `business_owner` NULL for several datasets |
| GT-OG-003 | Unclear source of truth | Both `customers` and `customer_master_legacy` flagged (or neither flagged) as source of truth |
| GT-OG-004 | Obsolete dataset still available | `customer_master_legacy` present, loaded by a still-running pipeline |

### Reliability & Freshness (RF)
| ID | Defect | Mechanism |
|---|---|---|
| GT-RF-001 | Stale datasets | Last successful run for some pipelines months before `as_of_date` |
| GT-RF-002 | Failed pipelines | Failure streaks in `pipeline_runs` (including currently failing) |
| GT-RF-003 | Duplicate/reprocessed ingestion | Same pipeline/day run twice with rows loaded both times (ties into GT-DQ-003) |
| GT-RF-004 | Irregular data volume | `rows_loaded` spikes/drops far outside the pipeline's normal band |
| GT-RF-005 | Missing freshness expectations | NULL `freshness_sla_hours` for most datasets in the registry |

## 5. Ground-truth manifest

`benchmark/ground_truth/ground_truth.json`, written by the generator, never
read by the future assessment engine during normal execution.

```json
{
  "manifest_version": 1,
  "benchmark": "northstar-distribution",
  "seed": 20260910,
  "as_of_date": "2026-09-01",
  "expected_issues": [
    {
      "id": "GT-DQ-001",
      "dimension": "data_quality",
      "type": "duplicate_customers",
      "description": "Near-duplicate customer records inserted with variant names/emails.",
      "datasets": ["customers"],
      "evidence": {"duplicate_pairs": [["C000123", "C004876"]]},
      "expected_count": 96
    }
  ]
}
```

Rules:
- `id` unique and stable, `GT-<DIM>-NNN` per the catalog above;
- `dimension` ∈ {`data_quality`, `metadata_documentation`,
  `metric_consistency`, `privacy_pii`, `ownership_governance`,
  `reliability_freshness`};
- `evidence` holds concrete locators (the affected keys/rows), shaped per
  defect type — enough for QA to assert a check found exactly these;
- `expected_count` is the number of affected records/instances;
- no timestamps of generation time (would break byte-determinism).

## 6. Generation pipeline & determinism

Order of operations in `generate.py`:

1. Load config; fail fast on missing/invalid keys.
2. Build clean base world in dependency order: products → customers → orders
   → order_items → payments → returns → derived datasets (`customer_export`,
   `sales_summary`, `customer_master_legacy`) → operational layer
   (`metric_definitions`, `pipeline_runs`, `dataset_registry`).
3. Inject defects per the §4 catalog, recording every affected key.
4. Write datasets as CSV (fixed column order, `\n` line endings, UTF-8,
   deterministic float formatting).
5. Write `ground_truth.json` (sorted keys, fixed separators).

Determinism rules (binding):
- one `random.Random(f"{seed}:{table_name}")` stream per table — isolates
  tables so a change to one generator leaves the others byte-identical;
- defect injection uses its own derived streams
  (`f"{seed}:defect:{gt_id}"`);
- never iterate a `set`/`dict` where order reaches the output without
  sorting first;
- all dates computed relative to `as_of_date`; no `datetime.now()`,
  no `time.time()`, no `os.urandom`, no `uuid4`;
- stdlib only for randomness; runtime dependency is `duckdb` (loading), and
  the generator itself should need nothing beyond the standard library.

Synthetic-data safety rules (binding):
- names/companies assembled from fictional word lists written for this
  project — not sampled from any real directory, customer list, or employer
  material;
- emails only under `example.com` / `example.org` / `northstar.example`;
- phone numbers only in fictional ranges (e.g. NANP `555-01xx` style);
- addresses synthetic (fictional street names, real-looking but generic
  city/region names are acceptable, no real person association).

## 7. DuckDB loading

`load_duckdb.py` creates `benchmark/data/northstar.duckdb` and one table per
CSV via `read_csv` with explicit column types (schemas in §3 — explicit, so
type defects survive loading rather than being "fixed" by inference). The
database file is disposable derived output; CSVs remain the canonical
generated form.
