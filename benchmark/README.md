# Northstar Distribution — Demo Environment & M0 Scenario Contract

Design for the revised M0 synthetic demo environment, including the binding
**Scenario Contract** for the one reporting dispute M0 demonstrates. Governed
by [`../Current Assignment.md`](../Current%20Assignment.md); on conflict, that
document (and above it, `SPEC.md` including **Amendment 001**) wins.

Northstar Distribution is a **fictional** Indonesian-style mid-market B2B
distributor. Every company, customer, product, person, rule, schema,
transaction, and note is synthetic and independently invented for this
project. Northstar is a **demo dataset** — a synthetic demonstration
environment — not an industry benchmark, and it is never described as one.

---

## 0. Status and process gate

| Item | State |
|---|---|
| Scenario Contract (Part II of this document) | **DRAFTED — pending Scenario Design Gate** |
| M0 implementation (generator, PostgreSQL schema, surfaces, sample report) | **BLOCKED** until the gate passes |

The agreed process is:

```
Scenario Contract (this document, Part II)
        ↓
Scenario Design Gate — Product Manager / Technical Lead review
        ↓
M0 implementation authorization (status updated here and in Current Assignment.md)
```

An implementation engineer must not start `benchmark/generate.py` or any
other M0 implementation work while the status above reads "pending". The
contract exists so that implementation can proceed **without rediscovering
or redesigning the scenario**: everything below Part II is binding on the
implementation unless the gate review changes it.

This document is design documentation. It is **not** part of the
assessment-visible environment (see §SC-12) — it explains the planted
answer, and the future assessment workflow never reads it.

---

# Part I — Environment

## 1. What this environment is for

Northstar exists to make one thing demonstrable end to end: a realistic
management reporting dispute — Revenue and Gross Margin disagreeing across
three reporting surfaces while a board pack is being prepared — that can be
investigated with evidence, reconciled, decomposed into legitimate
differences and one actual reporting defect, and explained to an executive
together with the metric definition appropriate to the decision at hand.

It is not a general-purpose data-health benchmark and does not exercise the
six-dimension / 42-check methodology library (which remains documented in
`SPEC.md` as internal methodology, not an implementation target).

## 2. Components

```
benchmark/
├── generate.py        # deterministic generator targeting PostgreSQL (M0 implementation)
├── load_duckdb.py     # optional dev/test-only mirror into DuckDB (M0 implementation)
├── config/
│   └── benchmark.toml # canonical seed, scenario config, scale profiles, output paths
├── scenario/          # surface SQL and note/extract sources fixed by the Scenario Contract (M0 implementation)
├── data/              # generated output (gitignored): DuckDB dev mirror, evidence directory
└── ground_truth/      # generated output (gitignored): hidden reconciliation ground truth
```

The one sample Reporting Reliability Audit produced from this environment
lives under `report/samples/` (a committed deliverable — see
`Current Assignment.md` §11.9), not here.

Execution contract:

```bash
python benchmark/generate.py --profile demo    # loads into PostgreSQL, writes evidence dir + ground truth
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
environment: operational tables, analytical views, accumulated schemas,
and reporting logic expressed as SQL rather than as clean exports.

Northstar's database is organized as several schemas (`core`, `finance`,
`analytics`, `management` — see §SC-7 and §SC-9), because an organically
evolved company does not keep operations, Finance, analytics, and
management reporting in one namespace.

**DuckDB is internal-only** — a convenience for test utilities and local
comparison during development. It must never be presented as Northstar's
organizational data platform, and no product-facing material may describe
Northstar as DuckDB-based.

**BigQuery is deferred** — do not introduce it to look enterprise-grade;
only add it if a real engagement requires it (Amendment §O).

---

# Part II — Scenario Contract (binding)

Sections are numbered `SC-n` so that implementation, tests, ground truth,
and the sample report can cite them.

## SC-1. Company and organizational context

**Northstar Distribution** (fictional; long form *PT Northstar Distribusi
Nusantara*) distributes packaged consumer and household goods from a
national catalog to business customers — modern-trade chains, general-trade
retailers, wholesalers, and hotel/restaurant/catering accounts — across
fictional sales regions of Java, Sumatra, and eastern Indonesia. Currency is
Indonesian rupiah (IDR, no decimals). All timestamps are Asia/Jakarta (WIB).

Relevant organizational shape (all roles fictional; artifacts refer to
people by initials only):

| Function | Role in the scenario | Initials used in artifacts |
|---|---|---|
| Finance | Owns the monthly close and the Finance P&L extract. Finance Controller signs the close. | `DA` (Finance Controller) |
| Sales Operations | Owns the sales dashboard and its nightly refresh. | `RW` (Sales Ops analyst) |
| FP&A / management reporting | Assembles the monthly Management/Board pack from SQL inherited from a former analyst who left in late 2024. | `YP` (former analyst, author of the board SQL); `NS` (current FP&A staff who runs it) |
| Executive sponsor | CFO who noticed the numbers disagree and commissioned the audit. | not named in artifacts |

Northstar has the technical debt profile the ICP is expected to have:
transactional tables maintained by the operational system, PostgreSQL
analytical tables and views refreshed by scheduled jobs, reporting SQL that
evolved by copy-and-edit, partial table/column comments, and informal
Markdown notes standing in for documentation.

## SC-2. Decision context: the August 2026 Board pack

- **Audit period:** accounting period **2026-08** (1–31 August 2026).
- **Management event:** preparation of the **August 2026 Management / Board
  Financial-Performance Pack** for the September board meeting.
- **Decision context:** the board reads the pack to judge August
  *financial performance* (P&L: how much revenue and gross margin Northstar
  earned in August) and, separately, *commercial performance* (how much the
  sales organization delivered). The August result also feeds the
  second-half revenue forecast and the sales-incentive accrual, which is why
  a disagreement of a few percent is consequential.
- **The dispute:** on the morning of Tuesday 8 September 2026, three
  numbers labelled "Revenue" (and three labelled "Margin" / "Gross Margin")
  exist for August: Finance's closed P&L extract, the Sales dashboard, and
  the Board pack circulated on 2 September. None agree. The CFO must decide
  which number goes to the board and whether the pack must be reissued.

Metric appropriateness is judged **against this decision context**, not
against an abstract notion of "the true Revenue" (see §SC-4).

## SC-3. Metrics in scope and naming rule

Exactly two metrics are in scope:

1. **Revenue**
2. **Gross Margin**

No third metric is added to M0. (Amendment §R permits one; this contract
declines it to keep the demonstration bounded.)

Northstar's surfaces use the generic labels `Revenue` and `Margin` /
`Gross Margin` for concepts that are not the same. **That ambiguity is part
of the scenario** and is itself a finding. The contract therefore gives
each concept a precise name, which implementation, ground truth, and the
sample report must use when they mean that concept:

| Precise name | Abbreviation | Surface | What it measures |
|---|---|---|---|
| Recognized Net Merchandise Revenue | RNMR | Finance | Merchandise revenue recognized in the accounting period, net of line discounts and of credit notes recognized in the period; excludes VAT and freight. |
| Actual Recognized COGS | ARC | Finance | Cost of goods recognized in the period at actual unit cost, net of COGS reversals on recognized credit notes. |
| Finance Gross Margin | FGM | Finance | RNMR − ARC. |
| Delivered Sales Value | DSV | Sales | Merchandise value delivered in the calendar month, net of line discounts, gross of returns; excludes VAT and freight; cancelled orders excluded. |
| Commercial Margin | CM | Sales | DSV − standard cost of the delivered goods. |
| Board Revenue (as reported) | BR | Board pack | The pack's "Revenue" line as its SQL computes it (see §SC-9.3). Not a coherent concept. |
| Board Gross Margin (as reported) | BGM | Board pack | The pack's "Gross Margin" line as its SQL computes it. Not a coherent concept. |

The fictional surfaces themselves keep their ambiguous labels (`revenue`,
`margin`, "Revenue", "Gross Margin"); only the contract, ground truth, and
report use the precise names.

## SC-4. Core rule: a definition is correct relative to a decision context

The contract, the ground truth, and the sample report must all encode:

> A metric definition is correct **relative to a decision context**. There
> is no single globally correct Revenue formula for every purpose.

Required conclusions the scenario must support (and the ground truth must
state — §SC-13):

```
For August board financial performance (P&L):
    Finance's Recognized Net Merchandise Revenue and Finance Gross Margin
    are the appropriate basis.

For sales-team commercial performance:
    Delivered Sales Value and Commercial Margin remain legitimate
    operational measures — with those names, not "Revenue" and "Margin".

For the Board pack:
    present the Finance P&L figures and the Sales commercial figures
    separately, clearly labelled, generated after the Finance close;
    do not combine them into one hybrid "Revenue" line.

The Board pack's as-reported figures are appropriate for no decision
context: they are a hybrid of incompatible definitions and snapshots and
contain a mechanical error (§SC-9.3, §SC-10).
```

Consequently the ground truth must **not** contain a universal
`true_revenue` (or equivalent). It contains expected values **per
legitimate context** plus an explicit recommended basis for the stated
decision context.

## SC-5. Fixed timeline

All dates below are fixed. They are scenario parameters, not
implementation choices, and must be encoded in configuration (see §SC-18),
never derived from the wall clock.

| When (WIB) | Event | Role in the scenario |
|---|---|---|
| Tue 1 Sep 2023 | Start of generated history (36 full months before the audit period ends). | history window |
| Mon 31 Aug 2026 | Last day of accounting period 2026-08. Last August delivery date. | period end |
| Tue 1 Sep 2026 | `as_of_date` in `benchmark.toml`: the **period boundary anchor** — first day of period 2026-09. History is counted back from it; the post-period tail is counted forward from it. | anchor |
| Tue 1 Sep 2026 02:10 | Nightly `refresh_delivered_sales` job completes; `analytics.delivered_sales` now contains every August delivery (deliveries are never back-dated, so the August delivery set is complete from this run onward). | T+1 refresh |
| Wed 2 Sep 2026 08:15 | `board_pack_monthly` job runs for period 2026-08 and writes the snapshot rows into `management.board_kpi_monthly`; FP&A exports the pack (`august_board_pack.csv`) and circulates it. | **earlier snapshot** |
| Wed 2 Sep 14:00 – Fri 4 Sep 2026 17:00 | Finance posts the period-end credit-note batches: every return **received at the warehouse on or before 31 Aug** that was not yet credited gets a credit note with `posting_date` on 2, 3, or 4 Sep and `accounting_period = '2026-08'`. | back-dated adjustments |
| Mon 7 Sep 2026 17:30 | Finance closes period 2026-08. `finance_revenue.sql` runs; the 2026-08 row is loaded into `finance.monthly_pnl_extract`. | **later Finance close** |
| Tue 8 Sep 2026 09:00 | **Observation instant** (environment horizon). No record in the environment carries a business date or system timestamp after this instant. The audit "sees" the environment as of now. | horizon |

What changed between the earlier snapshot (2 Sep 08:15) and the Finance
close (7 Sep 17:30): only the back-dated August credit notes posted 2–4
September. Nothing else that any surface reads for August changed.
Ordinary September operations (orders, deliveries, invoices, payments,
returns dated 1–7 September) continue to accrue in `core.*` up to the
horizon; they belong to period 2026-09 and are read by no August figure.

The same close pattern applies to **every** month in the history (close on
approximately the fifth business day of the following month; back-dated
credit batches on business days 2–4; board snapshot on the second business
day). The August pattern is therefore observable as a recurring pattern in
the job log and in historical credit-note posting dates, which is how a
competent auditor recognizes it without being told.

## SC-6. Transaction lifecycle and timestamp model

The environment preserves these distinct events with distinct dates:

```
order placed          orders.order_date
    ↓
delivered             orders.delivery_date            (NULL until delivered; never back-dated)
    ↓
invoiced / posted     invoices.invoice_date           = posting date; invoices.accounting_period
    ↓
paid                  payments.payment_date           (no reconciliation role)
    ↓
return received       returns.received_date           (goods physically back at the warehouse)
    ↓
credit note posted    credit_notes.posting_date ; credit_notes.accounting_period
    ↓
period closed         finance.monthly_pnl_extract.closed_at
```

Roles of each timestamp, and which surface uses it:

| Timestamp | Meaning | Finance | Sales | Board |
|---|---|---|---|---|
| `orders.order_date` | Commercial commitment. | — | — | — |
| `orders.delivery_date` | Goods handed to the customer. Defines the *calendar month* of delivery. | — | period basis for DSV and CM | period basis for the sales component |
| `invoices.invoice_date` | Accounting posting date of the sales invoice. Lags delivery by 0–3 business days. | drives `accounting_period` | — | — |
| `invoices.accounting_period` | Period in which merchandise revenue is recognized. **Always** the period of `invoice_date` (Finance does not accrue unbilled deliveries and never back-dates invoices). | period basis for RNMR/ARC | — | — |
| `returns.received_date` | Return occurrence: goods received back. Determines whether a credit note is eligible for back-dating. | eligibility rule | period basis for the informational `returned_value` column | — |
| `credit_notes.posting_date` | When the credit note was created in the ledger. | — | — | — |
| `credit_notes.accounting_period` | Period in which the credit reduces revenue and reverses COGS. Equals the period of `posting_date`, **except** for back-dated period-end credits (§SC-5, §SC-9.1). | period basis for credits | — | period basis for credits (copied from Finance's convention) |
| `*.created_at` | System insertion timestamp on every `core` row. Never earlier than the business date it records. Enables "as of snapshot" recomputation. | — | — | snapshot reproduction (§SC-9.3) |
| `management.board_kpi_monthly.generated_at` | When the board snapshot was computed. | — | — | the snapshot instant |
| `finance.monthly_pnl_extract.closed_at` | When Finance closed the period. | the close instant | — | — |

Implementation must not collapse these into one order timestamp. Every
row in every `core` table carries `created_at`.

Lifecycle rules (binding, with implementation latitude on distributions):

- An order is `open`, `cancelled`, or `delivered`. Cancelled orders have a
  `cancelled_date` and no `delivery_date`. Roughly 3% of orders are
  cancelled. Deliveries occur Monday–Saturday, typically 1–7 days after
  `order_date`. At the horizon a realistic tail of `open` orders exists
  (placed in early September, plus a few August backorders).
- One delivered order produces exactly **one** invoice, posted 0–3
  business days (Mon–Fri) after delivery, with weights on the order of
  55 / 25 / 12 / 8 percent for lags 0 / 1 / 2 / 3. Consequently some late-
  July deliveries are posted in August and some late-August deliveries are
  posted on 1–3 September. This is the **period-basis definition
  difference** and must be material (§SC-14).
- Returns reference the original invoice; `received_date` falls 1–45 days
  after delivery, skewed early. Between 5% and 10% of delivered orders
  have a return; returns are usually partial, so returned value is roughly
  2.5–4% of delivered value.
- A return is credited by exactly one credit note, normally posted 1–10
  business days after `received_date`. Period-end back-dating rule
  (Finance policy, applied every month): a return received on or before
  the last day of period *P* and credited on or before *P*'s close date is
  assigned `accounting_period = P` even though `posting_date` is in *P+1*.
  Returns received on or before 31 August are therefore all credited by
  4 September and all carry period 2026-08. Returns received 1–7 September
  are either still `received` (uncredited) at the horizon or credited with
  period 2026-09.
- Payments settle invoices on customer terms; some are partial. They exist
  because an invoice lifecycle without settlement is implausible; **no
  surface reads them and implementation must not give them a
  reconciliation role.**

## SC-7. Operational data model

The smallest credible lifecycle model. Schema `core` holds operational
data; table and column names are binding (implementation may add
non-semantic columns such as audit fields, and may choose physical types).
All monetary columns are integer rupiah.

| Table | Purpose | Binding columns |
|---|---|---|
| `core.customers` | Business customers. **No natural-person fields** (no contact name, email, phone, or street address — §SC-16). | `customer_id`, `customer_code`, `company_name`, `segment` (`modern_trade` / `general_trade` / `wholesale` / `horeca`), `province`, `city`, `sales_region`, `credit_terms_days`, `is_active`, `created_at` |
| `core.products` | Catalog. `standard_cost` mirrors the latest `standard` row in cost history (a denormalized convenience the dashboard uses). | `product_id`, `sku`, `product_name`, `category`, `uom`, `list_price`, `standard_cost`, `is_active`, `created_at` |
| `core.product_cost_history` | Cost semantics (§SC-8). | `product_id`, `cost_type` (`standard` / `actual`), `effective_from`, `unit_cost`, `source`, `created_at` |
| `core.orders` | Commercial commitment and delivery event. | `order_id`, `customer_id`, `order_date`, `requested_delivery_date`, `status` (`open` / `cancelled` / `delivered`), `delivery_date` (NULL unless delivered), `cancelled_date`, `created_at` |
| `core.order_items` | Ordered lines with line-level discount. | `order_item_id`, `order_id`, `product_id`, `qty`, `unit_price`, `discount_pct`, `line_net_amount` (= qty × unit_price × (1 − discount_pct), rounded) |
| `core.invoices` | Accounting posting of a delivered order (exactly one per delivered order). | `invoice_id`, `order_id` (unique), `customer_id`, `invoice_date`, `accounting_period` (`'YYYY-MM'`), `merchandise_amount`, `freight_amount`, `vat_amount`, `total_amount`, `created_at` |
| `core.invoice_lines` | Merchandise lines (one per order item) plus, on roughly 40% of invoices, one freight line. | `invoice_line_id`, `invoice_id`, `line_no`, `line_type` (`merchandise` / `freight`), `order_item_id` (NULL for freight), `product_id` (NULL for freight), `qty`, `unit_price`, `discount_amount`, `net_amount`, `vat_amount`, `unit_cost_actual` (NULL for freight) |
| `core.payments` | Settlement. No reconciliation role. | `payment_id`, `invoice_id`, `payment_date`, `amount`, `method`, `created_at` |
| `core.returns` | Return occurrence (goods received back). | `return_id`, `invoice_id`, `customer_id`, `received_date`, `reason_code` (`damaged` / `expired` / `wrong_item` / `overstock` / `quality`), `status` (`received` / `credited`), `created_at` |
| `core.return_items` | Returned quantities against original invoice lines. | `return_item_id`, `return_id`, `invoice_line_id`, `qty_returned` (≤ original qty) |
| `core.credit_notes` | Accounting adjustment for a return (exactly one per credited return). | `credit_note_id`, `return_id` (unique), `invoice_id`, `customer_id`, `posting_date`, `accounting_period`, `merchandise_amount`, `vat_amount`, `total_amount`, `cogs_reversal_amount`, `created_at` |

Amount semantics (binding):

- `invoice_lines.net_amount` (merchandise) = original `line_net_amount`;
  `invoice_lines.vat_amount` = VAT rate × `net_amount`; freight lines carry
  their own `net_amount` and VAT. `invoices.merchandise_amount` = Σ
  merchandise `net_amount`; `freight_amount` = Σ freight `net_amount`;
  `vat_amount` = Σ line VAT; `total_amount` = merchandise + freight + VAT.
- The VAT rate is a single scenario constant (default 11%). It is a
  fictional internal setting, not a claim about tax law.
- `credit_notes.merchandise_amount` = Σ `qty_returned` × the original
  line's net unit price; `vat_amount` = VAT rate × merchandise;
  `total_amount` = merchandise + VAT (returns never credit freight);
  `cogs_reversal_amount` = Σ `qty_returned` × the original line's
  `unit_cost_actual`.

Objects deliberately **not** in the model:

- **No legacy customer table.** The earlier generic design used a superseded
  customer table joined by one surface as a divergence mechanism. The
  approved scenario does not use a customer-population difference; adding
  one would create a fifth, unapproved decomposition category (§SC-10).
- **No `metric_definitions`, `dataset_registry`, or similar registry**
  (§SC-12).
- **No separate deliveries/shipments table.** Delivery is an order-header
  event (`orders.delivery_date`); one order has at most one delivery.
- **No inventory ledger.** Cost semantics are limited to §SC-8.

## SC-8. Product cost model

Two cost concepts coexist, both in `core.product_cost_history`:

| `cost_type` | Meaning | Who uses it | Change pattern |
|---|---|---|---|
| `standard` | Planning cost set by the pricing team at the semi-annual revision (1 January and 1 July each year). Mirrored into `core.products.standard_cost`. | Sales (CM), Board (BGM) | Changes only on 1 Jan / 1 Jul. **No standard cost changes inside August 2026**, so "standard cost effective at delivery" and "current standard cost" agree for every August delivery — implementation may use either. |
| `actual` | Realized (moving-average purchase) unit cost effective from a date; the value Finance recognizes as COGS. | Finance (ARC) | Changes on arbitrary dates as supplier prices move. **Between 15% and 25% of products delivered in August 2026 have at least one `actual` change with `effective_from` inside August**; across the catalog, actual cost differs from standard by roughly ±2–8%. |

Binding derivations:

- `invoice_lines.unit_cost_actual` = the `actual` unit cost effective on
  the order's `delivery_date` (captured at posting, as an ERP would post
  COGS from inventory valuation). Finance's recognized COGS is read from
  invoice lines, so it is fully reproducible from cost history.
- Sales' standard cost per delivered line = `qty` × `standard` cost
  effective on `delivery_date` (equivalently `products.standard_cost` for
  August).
- A credit note reverses COGS at the **original line's** `unit_cost_actual`
  (`credit_notes.cogs_reversal_amount`), never at the cost current on the
  credit date.

This is the whole cost model. It is sufficient to demonstrate the
legitimate **cost-basis difference** (standard vs actual) separately from
the revenue differences, which is its only purpose. Do not extend it into
inventory accounting.

## SC-9. Reporting surfaces

Three conceptual surfaces, in three schemas, with different physical
shapes because their semantics differ. Every value on every surface must be
reproducible from `core.*` by that surface's own SQL — **no hardcoded
figures anywhere**, including the mismatch.

### SC-9.1 Finance — `finance.monthly_pnl_extract` (snapshot table, one row per closed period)

Loaded by Finance at each period close by `finance_revenue.sql`. Row for
2026-08 loaded at 7 Sep 2026 17:30. Because the Finance close is the latest
snapshot and Finance's period logic is stable, recomputing the SQL at the
horizon reproduces the row exactly.

Finance's fictional internal recognition policy (the extract implements
it; `finance_close_notes.md` states it informally):

1. Merchandise revenue is recognized in the `accounting_period` of the
   sales invoice (= period of `invoice_date`). Unbilled deliveries are not
   accrued; invoices are never back-dated.
2. Line discounts reduce merchandise revenue (they are already netted in
   `net_amount`).
3. Credit notes reduce merchandise revenue and reverse COGS in the credit
   note's `accounting_period`, including period-end back-dated credits
   (§SC-5, §SC-6).
4. VAT is excluded.
5. Freight/service charges are excluded from merchandise revenue (reported
   as a separate `freight_income` column, which no metric in scope uses).
6. COGS is actual: Σ `qty` × `unit_cost_actual` on recognized merchandise
   lines, less Σ `cogs_reversal_amount` on recognized credit notes.

Binding columns: `accounting_period`, `gross_invoiced_merchandise`,
`credit_notes_merchandise`, `net_merchandise_revenue` (RNMR),
`freight_income`, `cogs_invoiced`, `cogs_reversed`, `recognized_cogs`
(ARC), `gross_margin` (FGM), `gross_margin_pct`, `closed_at`,
`prepared_by`.

Definitions:

```
RNMR = Σ invoice_lines.net_amount  [line_type = 'merchandise', invoices.accounting_period = P]
     − Σ credit_notes.merchandise_amount               [credit_notes.accounting_period = P]

ARC  = Σ invoice_lines.qty × unit_cost_actual          [same invoice-line filter]
     − Σ credit_notes.cogs_reversal_amount              [credit_notes.accounting_period = P]

FGM  = RNMR − ARC
```

Finance is **defensible**: for the board's P&L question this is the
appropriate basis (§SC-4). Finance's only weakness in the scenario is that
its label in conversation is also just "Revenue".

### SC-9.2 Sales — `analytics.delivered_sales` (fact table, nightly T+1) and `analytics.sales_dashboard_monthly` (view)

`analytics.delivered_sales` is refreshed nightly by job
`refresh_delivered_sales` (§SC-11) from `core.orders` / `core.order_items`
/ `core.products` / `core.customers`: one row per delivered order item,
with `delivery_date`, `order_id`, `order_item_id`, `customer_id`,
`sales_region`, `product_id`, `qty`, `gross_amount`, `discount_amount`,
`net_amount`, `std_unit_cost`, `std_cost_amount`, `loaded_at`. Cancelled
and undelivered orders never enter it.

`analytics.sales_dashboard_monthly` is a **view** over the fact (and, for
one informational column, over `core.returns` / `core.return_items`),
grouped by calendar month of `delivery_date` and `sales_region`, exposing
the generic column names the dashboard shows:

| View column | Precise meaning | Notes |
|---|---|---|
| `revenue` | **Delivered Sales Value (DSV)**: Σ `net_amount` for deliveries in the month. Net of line discounts, ex-VAT, ex-freight, **gross of returns**, cancelled orders excluded. | The label is ambiguous; the concept is legitimate. |
| `cogs_std` | Σ `std_cost_amount`. | standard cost basis |
| `margin` | **Commercial Margin (CM)** = `revenue` − `cogs_std`. | |
| `margin_pct` | `margin` / `revenue`. | |
| `returned_value` | Σ returned merchandise value (at original net unit price) for returns with `received_date` in the month. | Informational. **No surface nets it.** Shown so the sales team sees returns beside deliveries. |
| `order_count` | Distinct delivered orders. | |

**Snapshot/cutoff rule (chosen, binding):** DSV for a month is *gross of
returns* and *delivery-dated*. Subsequent returns never reduce a historical
month's `revenue`; they appear only in `returned_value` by receipt month.
Because deliveries are never back-dated, the August `revenue` and `margin`
values are identical at every refresh from 1 September onward — the Sales
surface has **no timing component**. Rationale (stated in
`sales_dashboard_notes.md`): the sales organization is measured on what it
delivered; returns are handled as a separate commercial follow-up, and the
dashboard was changed in early 2025 — after the sales team disputed having
a closed month reduced by later returns — to show deliveries gross and
returns separately.

Sales is **defensible**: DSV and CM are legitimate commercial-performance
measures. Sales is **not** the broken surface. Its findings are limited to
labelling (`revenue`, `margin`) and a stale column comment (§SC-11).

### SC-9.3 Board — `management.board_kpi_monthly` (snapshot table, long format)

Written by job `board_pack_monthly` from `board_pack.sql` (inherited from
`YP`, 2024), on the second business day of the following month — for
2026-08 at **2 Sep 2026 08:15**. Rows: `period`, `kpi`, `value`,
`generated_at`, `source_job`. KPIs for each period: `Revenue`,
`Gross Margin`, `Gross Margin %`. Historical periods are present and were
produced the same way, so the defect is a recurring pattern, not a
one-month accident. `august_board_pack.csv` in the evidence directory is
the export of the 2026-08 rows that was circulated.

Board logic (binding semantic composition; `board_pack.sql` must implement
exactly this and read plausibly as SQL that evolved by copy-and-edit):

```
Revenue        = Σ analytics.delivered_sales.net_amount   [delivery month = P]        -- delivery basis, T+1 fact
               − Σ core.credit_notes.total_amount         [accounting_period = P]     -- Finance's period convention,
                                                                                      --   as of the run instant,
                                                                                      --   VAT-INCLUSIVE column
Gross Margin   = Revenue − Σ analytics.delivered_sales.std_cost_amount [delivery month = P]
                                                                                      -- standard cost; no COGS
                                                                                      --   reversal for returns
Gross Margin % = Gross Margin / Revenue
```

Why the historical SQL looks this way (plausible, and traceable through
the evidence): the pack's author wanted "sales as the dashboard shows it,
less returns the way Finance books them, less cost" — a verbal agreement
recorded only in a 2024 handover note (§SC-11). The credit-note deduction
picked `total_amount` from the credit-note table because it is the column
that "matches the credit note document"; the margin line reused the
dashboard's cost column without reversing cost for the credited returns;
and the job was scheduled early so the pack draft reaches management
quickly — before Finance's period-end batches exist.

The Board surface therefore genuinely mixes incompatible semantics **and**
snapshots:

| Component | Basis | Snapshot | Compatible with the other components? |
|---|---|---|---|
| Sales component | delivery-dated, gross of returns, ex-VAT | T+1 fact (complete for August) | — |
| Returns component | Finance `accounting_period` convention, **VAT-inclusive** | as of 2 Sep 08:15 — misses the 2–4 Sep back-dated credits | No: posting-period credits netted from delivery-basis sales; VAT-inclusive deduction from an ex-VAT figure; stale |
| Cost component | standard cost of deliveries, not reversed for returns | T+1 fact | No: revenue is net of returns but cost is not |

**Reproduction rule (binding, tested):** re-running `board_pack.sql` at the
horizon does **not** reproduce the 2 Sep figure (that is the freshness
finding). The generator and the tests reproduce the snapshot by evaluating
the same logic with the credit-note set restricted to
`core.credit_notes.created_at <= management.board_kpi_monthly.generated_at`.
The Board number is thus reproducible from underlying data and its own
logic — it is not a hardcoded wrong value.

### SC-9.4 Surface summary

| Property | Finance `finance.monthly_pnl_extract` | Sales `analytics.sales_dashboard_monthly` | Board `management.board_kpi_monthly` |
|---|---|---|---|
| Physical shape | snapshot table, per closed period | view over T+1 fact | snapshot table, long format |
| Period basis (sales side) | `invoices.accounting_period` (posting) | calendar month of `delivery_date` | calendar month of `delivery_date` |
| Discounts | net | net | net |
| VAT | excluded | excluded | excluded on sales, **included on the credit deduction** |
| Freight | excluded (separate column) | excluded | excluded |
| Returns / credit notes | credit notes by `accounting_period`, incl. back-dated | none (gross); `returned_value` informational by `received_date` | credit notes by `accounting_period` **as of 2 Sep 08:15** |
| Cost basis | actual (`unit_cost_actual`), reversed on credits | standard, no reversal (consistent with gross-of-returns) | standard, **no reversal although revenue is net of returns** |
| Snapshot instant for 2026-08 | 7 Sep 17:30 (close) | stable from 1 Sep 02:10 | 2 Sep 08:15 |
| Verdict in the decision context | appropriate P&L basis | appropriate commercial basis (relabel) | defective; not usable for any context |

## SC-10. Required root-cause decomposition

The M0 audit must decompose every pairwise difference into these four
categories, and the ground truth must carry each bridge line tagged with
exactly one of them. They must never be collapsed into a generic "metric
mismatch".

| Category | Meaning | Demonstrated by |
|---|---|---|
| **definition** (semantic) | The surfaces measure different, individually coherent concepts. Would persist even if all surfaces were computed at the same instant from complete data. Legitimate. | period basis (delivery-dated vs posting-dated); gross-of-returns vs net-of-credit-notes |
| **timing** (cutoff / snapshot) | The same concept computed from snapshots taken at different instants, with period-relevant transactions posted in between. Legitimate as a fact; a freshness finding as a practice. | the 2–4 Sep back-dated credit notes missing from the 2 Sep Board snapshot |
| **cost basis** | Margin computed on standard vs actual cost. Legitimate. | Σ (actual − standard) cost of August deliveries |
| **defect** | Logic that is incoherent under any definition. Must be corrected. | Board deducts VAT-inclusive credit totals from an ex-VAT figure; Board nets the credits it can see from revenue but never reverses their cost |

### SC-10.1 Bridge notation

For period P = 2026-08 (all amounts merchandise, ex-VAT unless stated):

```
G_post   gross invoiced merchandise, invoices.accounting_period = P
C_period credit-note merchandise, credit_notes.accounting_period = P (all, incl. back-dated)
C_late   the subset of C_period with posting_date in 2–4 Sep (created after the Board snapshot)
v        VAT rate (0.11)
D1       merchandise of August deliveries whose invoices posted in September   (in DSV, not in RNMR)
D2       merchandise of July deliveries whose invoices posted in August        (in RNMR, not in DSV)
K_post   actual COGS on invoice lines with accounting_period = P
R_period COGS reversal on credit notes with accounting_period = P (all, incl. back-dated)
R_early  the subset of R_period on credit notes already created at the Board snapshot
         (created_at <= 2 Sep 08:15) — the cost side of the credits the Board did net
R_late   the subset of R_period on credit notes created after the Board snapshot
         (the 2–4 Sep batches) — the cost side of C_late;   R_period = R_early + R_late
K1, K2   actual-cost analogues of D1, D2
K_act    actual cost of August deliveries (delivery basis) = K_post + K1 − K2
K_std    standard cost of August deliveries (delivery basis)

RNMR = G_post − C_period                      ARC = K_post − R_period         FGM = RNMR − ARC
DSV  = G_post + D1 − D2                       CM  = DSV − K_std
BR   = DSV − (C_period − C_late) × (1 + v)    BGM = BR − K_std
```

### SC-10.2 Required bridges

Revenue, Finance → Sales:

```
RNMR
  + (D1 − D2)      definition   period basis: delivery-dated vs posting-dated
  + C_period       definition   Sales is gross of returns; Finance nets recognized credits
= DSV
```

Revenue, Finance → Board:

```
RNMR
  + (D1 − D2)                  definition   period basis (Board's sales component is delivery-dated)
  + C_late                     timing       back-dated credits posted 2–4 Sep, absent from the 2 Sep snapshot
  − v × (C_period − C_late)    defect       VAT-inclusive credit totals deducted from an ex-VAT figure
= BR
```

Gross Margin, Finance → Sales:

```
FGM
  + (DSV − RNMR)               [the revenue bridge above, by category]
  − (K1 − K2)                  definition   period basis on cost
  − (K_std − K_act)            cost basis   standard vs actual
  − R_period                   definition   no COGS reversal is consistent with gross-of-returns revenue
= CM
```

Gross Margin, Finance → Board:

```
FGM
  + (BR − RNMR)                [the revenue bridge above, by category]
  − (K1 − K2)                  definition   period basis on cost
  − (K_std − K_act)            cost basis   standard vs actual
  − R_late                     timing       cost side of the 2–4 Sep credits: neither the credit nor its
                                            COGS reversal existed at the 2 Sep snapshot
  − R_early                    defect       Board Revenue already nets these credits, but Board Gross
                                            Margin never reverses their cost
= BGM
```

Two teaching points the sample report must make:

- The same amount `R_period` is **legitimate** in the Sales bridge (Sales
  is gross of returns, so not reversing cost is consistent) while in the
  Board bridge it splits into a **defect** (`R_early`) and a **timing**
  difference (`R_late`). Correctness is about internal consistency with the
  surface's own definition and snapshot, not about the number itself.
- The Board's timing and defect attributions must be consistent between
  the two metrics: the credits the Board *saw* (`C_period − C_late`) are
  the ones whose VAT is wrongly deducted **and** whose cost is wrongly not
  reversed; the credits it *did not see* (`C_late`, `R_late`) are timing
  on both lines. A decomposition that calls a cost line a defect for a
  credit the Board could not have known about is wrong.

### SC-10.3 Worked illustration (not ground truth)

Round figures in Rp million, only to show the arithmetic; the generator
produces the real values.

```
G_post = 100,000   C_period = 3,200 (C_late = 1,400)   v = 0.11
D1 = 2,600   D2 = 2,100
K_post = 81,000   R_period = 2,650 (R_early = 1,490, R_late = 1,160)
K1 = 2,130   K2 = 1,720   K_std = 80,600

RNMR = 96,800        ARC = 78,350        FGM = 18,450   (19.1%)
DSV  = 100,500       K_std = 80,600      CM  = 19,900   (19.8%)
BR   = 100,500 − 1,800 × 1.11 = 98,502   BGM = 17,902   (18.2%)

BR − RNMR = 1,702 = (D1 − D2) 500 + C_late 1,400 − v(C_period − C_late) 198
BGM − FGM = −548 = 1,702 − (K1 − K2) 410 − (K_std − K_act) (−810) − R_late 1,160 − R_early 1,490

Gross Margin, Finance → Board, totalled by category:
  definition   (D1 − D2) 500 − (K1 − K2) 410            =    +90
  timing       C_late 1,400 − R_late 1,160              =   +240
  cost basis   −(K_std − K_act) = +810                  =   +810
  defect       −198 − R_early 1,490                     = −1,688
  total                                                 =   −548  ✓
```

Three "Revenue" numbers (96,800 / 100,500 / 98,502) and three margin
percentages, every difference explained line by line, and the Board pack
neither the highest nor the lowest — which is why nobody caught it by eye.

## SC-11. Supporting issues (bounded)

Exactly two supporting issues exist. Both are tied directly to the
reconciliation. No others are planted.

**Freshness / snapshot.** The Board pack for 2026-08 was generated at
2 Sep 08:15 from a credit-note set that Finance's 2–4 Sep back-dated
batches later changed; the Finance close at 7 Sep 17:30 is the only
complete August snapshot. Evidence: `management.board_kpi_monthly.generated_at`;
`analytics.etl_job_runs` (rows for `refresh_delivered_sales` nightly and
`board_pack_monthly` on the second business day of each month — the same
early pattern every month); `core.credit_notes.posting_date` vs
`accounting_period` for the back-dated batches; `finance.monthly_pnl_extract.closed_at`.
This is the `timing` line of the Board bridge; it is not a separate
failed-pipeline story. No job failures are planted.

**Ownership / documentation.** Finance and Sales each have an
understandable internal definition of "Revenue", but Northstar has no
agreed decision-context definition or ownership for how the metric is
presented in the Board pack. Evidence:

- `board_pack_handover.md` (dated November 2024, stale): `YP` records that
  the pack's Revenue is "dashboard revenue less returns per Finance so it
  matches what Finance books", agreed verbally with the Finance Controller
  at the time, "never written up", and names the future owner as "TBD".
- `COMMENT ON COLUMN analytics.sales_dashboard_monthly.revenue` still reads
  as net of returns (true before the early-2025 change described in
  `sales_dashboard_notes.md`), contradicting the current view SQL.
- `management.board_kpi_monthly` has **no** table or column comments.
- `finance_close_notes.md` states Finance's policy but says nothing about
  the Board pack.

This is the whole governance finding. It is not a governance catalog and
does not reopen the six-dimension assessment.

## SC-12. Evidence inventory, fragmentation, and no-leak rules

**Assessment-visible** means: the contents of the PostgreSQL database
(schemas `core`, `finance`, `analytics`, `management`, including comments)
and the generated evidence directory `benchmark/data/evidence/`. Nothing
else — not this document, not the generator source, not the configuration,
not `benchmark/ground_truth/` — is available to the assessment workflow.

Evidence is deliberately fragmented. Every artifact below has a stated
purpose; **do not add artifacts for atmosphere.**

### SC-12.1 Database objects

| Object | Purpose in the story |
|---|---|
| `core.*` (§SC-7) | The underlying business events every figure must be reproducible from. Table comments present for `orders`, `invoices`, `credit_notes`, `product_cost_history`; **absent** for `returns`, `return_items`, `payments`; column comments present for `invoices.accounting_period` (states the posting-period convention) and `credit_notes.accounting_period` (states the period-end back-dating rule in one terse sentence), absent elsewhere. |
| `finance.monthly_pnl_extract` | Finance's number and its full component breakdown. Table comment names Finance as owner. |
| `analytics.delivered_sales` | The T+1 fact behind both the dashboard and the Board sales component. Comment: refresh cadence only. |
| `analytics.sales_dashboard_monthly` | Sales' number. Stale `revenue` column comment (§SC-11). |
| `analytics.etl_job_runs` | Job log: `job_name`, `run_for_period`, `started_at`, `completed_at`, `status`, `rows_written`. Freshness evidence. Every run succeeds. |
| `management.board_kpi_monthly` | The Board number with `generated_at`. No comments. |

### SC-12.2 Evidence directory (`benchmark/data/evidence/`, generated)

| File | Purpose |
|---|---|
| `finance_revenue.sql` | The close query (§SC-9.1). Header comment: owner initials, "run at period close", nothing else. |
| `sales_dashboard.sql` | View definition plus the fact-refresh statement (§SC-9.2). |
| `board_pack.sql` | The inherited Board query (§SC-9.3). Header: author initials and year, "do not change without telling FP&A". Reads plausibly; contains no hint that it is wrong. |
| `august_board_pack.csv` | The circulated 2026-08 pack rows (`period`, `kpi`, `value`, `generated_at`) — the number the CFO is holding. |
| `finance_close_notes.md` | Finance's close checklist and recognition policy in informal shorthand (posting period, back-dated credits for returns received by period end, VAT/freight out, actual cost). Silent about the Board pack. |
| `sales_dashboard_notes.md` | Sales Ops' description of the dashboard: delivered basis, gross of returns since the early-2025 change and why, standard cost "per the pricing team's file", returns shown separately. |
| `board_pack_handover.md` | The stale 2024 handover (§SC-11). |

Seven files; no more. If an implementation need arises for an eighth, it
requires a contract change at the gate, not an ad hoc addition.

### SC-12.3 No-leak rules (binding)

Assessment-visible artifacts must not contain:

- answer flags (`is_wrong`, `expected_revenue`, `correct_definition`,
  `true_value`, `mechanism`, `planted`, `scenario`, `defect`, `ground_truth`
  or similar) in any object, column, file, or comment name or content;
- comments or notes saying a query is broken, intentionally so, stale by
  design, or "the one Finance disagrees with";
- object or file names that reveal a cause (`bad_board_revenue`,
  `vat_inclusive_bug`, `late_credit_notes`, …);
- documentation that states which surface is defective or lays out the
  reconciliation;
- any registry-style object (`metric_definitions`, `dataset_registry`,
  `kpi_catalog`, …) presenting organizational truth.

The environment must contain enough evidence for a competent auditor to
reach §SC-10 unaided — the policy comment on `credit_notes.accounting_period`,
the recurring job-log pattern, the handover note, and the SQL itself are
that evidence — and must not hand over the answer.

## SC-13. Hidden ground truth

`benchmark/ground_truth/` — machine-readable, generated, gitignored,
structurally separate from assessment-visible data, **never** read by the
future assessment workflow (Amendment §S). It is **decision-context-aware**:
it does not encode a universal correct Revenue.

Required content:

- scenario id, seed, profile, audit period, decision context (prose);
- the fixed timeline instants (§SC-5);
- per surface: object name, snapshot instant, reported values (Revenue-
  labelled, Margin-labelled, margin %), and the precise concept name;
- expected values per legitimate context: Finance (RNMR, ARC, FGM), Sales
  (DSV, K_std, CM), Board as reported (BR, BGM);
- every bridge line of §SC-10.2 with amount and category
  (`definition` / `timing` / `cost_basis` / `defect`), and the intermediate
  quantities (`G_post`, `C_period`, `C_late`, `D1`, `D2`, `K_*`, `R_period`,
  `R_early`, `R_late`);
- the actual Board defect described in words, with the two mechanically
  quantifiable sub-lines;
- recommended basis per decision context (§SC-4), and the presentation
  recommendation for the Board pack;
- the two supporting findings (§SC-11) with the evidence objects that
  establish them;
- derived scale facts the QA reviewer needs (counts per table, August
  delivery/invoice/credit counts, number of back-dated credits).

Illustrative shape (not mandatory; keys sorted, fixed separators, no
generation timestamps):

```json
{
  "manifest_version": 2,
  "scenario": "northstar-2026-08-revenue-margin",
  "seed": 20260910,
  "profile": "demo",
  "audit_period": "2026-08",
  "decision_context": "August 2026 Management/Board Financial-Performance Pack: board P&L view and separate commercial-performance view",
  "timeline": {"board_snapshot_at": "2026-09-02T08:15:00+07:00", "finance_close_at": "2026-09-07T17:30:00+07:00", "observation_at": "2026-09-08T09:00:00+07:00"},
  "surfaces": {
    "finance": {"object": "finance.monthly_pnl_extract", "concept": {"revenue": "RNMR", "margin": "FGM"}, "reported": {"revenue": 96800000000, "gross_margin": 18450000000}},
    "sales":   {"object": "analytics.sales_dashboard_monthly", "concept": {"revenue": "DSV", "margin": "CM"}, "reported": {"revenue": 100500000000, "gross_margin": 19900000000}},
    "board":   {"object": "management.board_kpi_monthly", "concept": {"revenue": "BR (hybrid)", "margin": "BGM (hybrid)"}, "reported": {"revenue": 98502000000, "gross_margin": 17902000000}}
  },
  "bridges": {
    "revenue_finance_to_board": [
      {"line": "period_basis_delivery_vs_posting", "category": "definition", "amount": 500000000},
      {"line": "back_dated_credit_notes_after_snapshot", "category": "timing", "amount": 1400000000},
      {"line": "vat_inclusive_credit_deduction", "category": "defect", "amount": -198000000}
    ],
    "gross_margin_finance_to_board": [
      {"line": "revenue_bridge_carried", "category": "by_line", "amount": 1702000000},
      {"line": "period_basis_on_cost", "category": "definition", "amount": -410000000},
      {"line": "standard_vs_actual_cost", "category": "cost_basis", "amount": 810000000},
      {"line": "cogs_reversal_on_credits_after_snapshot", "category": "timing", "amount": -1160000000},
      {"line": "cogs_not_reversed_on_credits_seen_by_board", "category": "defect", "amount": -1490000000}
    ]
  },
  "recommended_basis": {
    "board_financial_performance_pnl": "finance",
    "sales_commercial_performance": "sales",
    "board_pack_presentation": "present finance P&L and sales commercial figures separately, labelled, regenerated after the Finance close; retire the hybrid"
  },
  "supporting_findings": ["board_pack_snapshot_precedes_finance_close", "no_agreed_board_pack_revenue_definition_or_owner"]
}
```

## SC-14. Scale profiles and materiality targets

Two profiles, **identical scenario semantics**, driven by the same
business logic; only counts differ. Both are configured in
`benchmark/config/benchmark.toml`.

- **`smoke`** — small enough for fast automated tests (seconds).
- **`demo`** — large enough to look and behave like a credible mid-market
  operating environment.

Design direction for `demo` (guidance, not immutable counts):

```
Customers        ~50,000
Products          ~5,000
Orders           ~750k–1M
Order items      ~3M–5M
Invoices         ~700k–900k
Returns          ~50k–100k
History          36 months
```

The current configured `demo` counts are below this direction. They are
configuration, not a success criterion, and may be raised during
implementation if generation and loading time allow; they are not changed
by this contract. Priority order remains:

```
business-semantic realism > credible reconciliation > coherent transaction
lifecycle > sufficient scale > raw row count
```

Only the independently generated tables carry configured counts
(`customers`, `products`, `orders`, `order_items`, `payments`, `returns`).
The remaining tables are **derived** and need no counts: one invoice per
delivered order; invoice lines = order items of delivered orders plus
freight lines; return items ≈ 1–3 per return; one credit note per credited
return; cost history ≈ products × (six semi-annual standard revisions plus
several actual changes) over 36 months.

Materiality targets for period 2026-08 in **both** profiles. The generator
meets them **by construction**, not by hoping random draws land — e.g. by
guaranteeing a minimum number of month-end deliveries with a posting lag,
of returns received in the last week of August, and of August actual-cost
changes — which is what lets the small `smoke` profile satisfy them too.
Tests assert them on both profiles:

| Quantity | Target |
|---|---|
| `C_period` (August-period credit merchandise) | 2.5%–4.0% of RNMR |
| `C_late` share of `C_period` | ≥ 35% (so the timing line is ≥ ~1% of RNMR) |
| `D1` and `D2` | each ≥ 0.8% of RNMR (the net may be small; each leg must be visible) |
| `K_std − K_act` | absolute value ≥ 1% of `K_act` |
| Pairwise revenue differences (RNMR, DSV, BR) | each ≥ 0.5% of RNMR; all three values distinct |
| Pairwise margin-% differences (FGM, CM, BGM) | each ≥ 0.5 percentage points |
| Gross margin level | FGM between 15% and 25% of RNMR |

`R_early` and `R_late` are derived by the same snapshot split as `C_late`
(credit-note `created_at` relative to the Board `generated_at`), so they
inherit the `C_late` share target and need no separate row; tests that
assert the Board margin bridge must assert both lines and their sum.

## SC-15. What the M0 audit must be able to prove

The sample report is **not** produced by this task, but the environment
must make the following provable from assessment-visible evidence alone,
in this flow:

```
management question          which August Revenue and Gross Margin go to the board?
↓
conflicting reported numbers  finance.monthly_pnl_extract / analytics.sales_dashboard_monthly / august_board_pack.csv
↓
evidence collected           §SC-12 objects and files, with Evidence Coverage stated
↓
reconciliation               the four bridges of §SC-10.2, each line reproduced from core.*
↓
root cause decomposition     definition / timing / cost basis / defect, per line
↓
business impact              rupiah and % per line; measured (reproduced) vs inferred; decision affected
↓
definition for the context   §SC-4 conclusions, per context
↓
ownership / remediation      §SC-11: assign Board-pack definition ownership; correct board_pack.sql
                             (ex-VAT credit merchandise; reverse standard cost on credited returns — or
                             retire the hybrid); schedule the pack after the Finance close
↓
re-check path                re-run the three surfaces after the next close and re-run the bridges
```

Customer-facing outputs prioritize, per Amendment §I: a **per-metric
verdict** (`RECONCILED` / `CONFLICTING` / `UNVERIFIABLE`) — in this
scenario both Revenue and Gross Margin are `CONFLICTING` as reported and
reconcilable in full; **Evidence Coverage**; the **reconciliation**;
**business impact**; the **recommended decision-context definition**; and a
**remediation sequence**. The internal Data Health Score is not central to
this scenario and no AI Readiness output is produced.

## SC-16. Explicit exclusions

- **No PII scenario in M0.** No natural-person data exists anywhere in
  Northstar: `core.customers` carries company-level fields only; artifacts
  refer to staff by initials. No privacy finding is planted, and the
  earlier "one limited synthetic-PII example" language is withdrawn for
  M0. The secondary PP 33 / PDP hypothesis (Amendment §L) remains outside
  this demonstration.
- **No third metric.**
- **No legacy customer table, no registry tables, no inventory ledger**
  (§SC-7).
- **No duplicate/missing-transaction finding, no pipeline failures**, and
  no other supporting findings beyond §SC-11.
- **No hardcoded surface values**, anywhere.
- **No universal `true_revenue`** in ground truth.

## SC-17. Contract self-check against the gate criteria

| Gate | Criterion | Where satisfied |
|---|---|---|
| A | Finance is defensible for the August Board P&L | §SC-9.1 policy is coherent and complete; §SC-4 names it the P&L basis |
| B | Sales is a legitimate commercial metric, not a broken query | §SC-9.2 DSV/CM with an explicit, defensible gross-of-returns rule; no timing component |
| C | Board genuinely has a defect, reproducible | §SC-9.3: hybrid composition plus two mechanical errors, reproduced via the `created_at ≤ generated_at` rule |
| D | Differences are decomposable into definition / timing / cost basis / defect | §SC-10.2 bridges; every line carries one category; §SC-10.3 arithmetic checks |
| E | No universal-metric fallacy | §SC-4; §SC-13 has per-context expectations and no `true_value` |
| F | No answer leakage | §SC-12.3 rules; evidence requires reading SQL, comments, the job log, and the handover note together |
| G | Realistic without theatre | Seven evidence files and five non-core database objects, each with a stated purpose; only two supporting issues; no failed jobs |
| H | Bounded | Two metrics, three surfaces, one period, one company, one engagement shape |

## SC-18. Notes for the implementation handoff (after the gate)

These are consequences of the contract that the implementation must
handle; they are listed so they are not rediscovered.

1. **Scenario parameters belong in configuration**, not in generator code:
   the §SC-5 instants (board snapshot, credit-batch days, close instant,
   observation instant), the VAT rate, posting-lag weights, return and
   back-dating rates, and the §SC-14 materiality targets. `Current
   Assignment.md` §6 already allows `benchmark.toml` to gain scenario
   parameters during implementation; add them then. `as_of_date` keeps its
   §SC-5 meaning (period boundary anchor).
2. **`tests/test_benchmark_config.py` predates this contract.** Its
   informational constants still list the generic surface names
   (`finance_monthly_report`, `mgmt_board_kpis`, `sales_dashboard_kpis`)
   and `customer_master_legacy`; only the transactional-table check is
   asserted, and it still holds. Reconcile those constants when the M0
   test suite is written (assignment §10). This contract does not change
   tests.
3. **Surface SQL and note sources** live under `benchmark/scenario/` as
   committed source; the generator copies/renders them into the evidence
   directory. Their file names follow §SC-12.2 and must also satisfy
   §SC-12.3.
4. **Historical months** must follow the same lifecycle and close pattern
   as August so the patterns are recognizable; only August needs to meet
   the §SC-14 targets exactly.
5. **Snapshot reproduction tests** (assignment §10.3) must reproduce the
   Board figure with the `created_at ≤ generated_at` restriction, the
   Finance row by re-running its SQL at the horizon, and the Sales view by
   definition. The same restriction is what splits `C_period` into
   `C_period − C_late` / `C_late` and `R_period` into `R_early` / `R_late`;
   the ground truth and the bridge tests must use one shared split.

---

# Part III — Implementation rules (binding once implementation is authorized)

## 13. Determinism & synthetic-data rules

Order of operations in `generate.py`:

1. Load config (including which scale profile); fail fast on missing/
   invalid keys.
2. Build the operational data in dependency order: products → cost
   history → customers → orders → order_items → invoices/invoice_lines →
   payments → returns/return_items → credit_notes, applying the §SC-5/§SC-6
   lifecycle and close pattern to every month of history.
3. Materialize the reporting surfaces (§SC-9), each via its own SQL:
   the T+1 fact and dashboard view; the Board snapshot rows for every
   period using the snapshot restriction; the Finance extract rows for
   every closed period.
4. Attach the fragmented evidence (§SC-12): comments (with the specified
   gaps and the one stale comment), the job log, the evidence directory.
5. Write the hidden ground-truth manifest (§SC-13) — sorted keys, fixed
   separators, no generation-time timestamps.

Determinism rules (binding):

- one `random.Random(f"{seed}:{table_name}")` stream per table/surface;
  scenario logic uses its own derived streams (never share a stream
  across independent generators);
- prefer `random()` / `getrandbits()` over `sample()` / `choices()` /
  `shuffle()` where practical — only the former are contracted stable
  across CPython versions;
- reproducibility contract: **byte-identical** output for the same
  code + config + seed on the same Python feature release; **materially
  identical** across supported Python ≥3.12;
- never iterate a `set`/`dict` where order reaches the output without
  sorting first;
- all dates computed relative to the configured `as_of_date` and the
  §SC-5 scenario instants; no `datetime.now()`, `time.time()`,
  `os.urandom`, or `uuid4`;
- stdlib only for randomness; runtime dependencies are `psycopg` (loading
  into PostgreSQL) and, for internal test/dev use only, `duckdb`.

Synthetic-data safety rules (binding):

- company, product, place, and person-initial values are assembled from
  fictional word lists written for this project — not sampled from any
  real directory, customer list, or employer material;
- no natural-person fields exist anywhere (§SC-16): no names, emails,
  phone numbers, or street addresses, in the schema, the evidence
  directory, tests, or documentation.

## 14. PostgreSQL loading notes

`generate.py` connects to a target PostgreSQL instance (connection string
via an environment variable, e.g. `NORTHSTAR_DATABASE_URL` — never
hard-coded) and creates the `core`, `finance`, `analytics`, and
`management` schemas from scratch; loading is idempotent against a clean
target. `load_duckdb.py` is a separate, optional dev/test convenience that
mirrors the same logical data into a local DuckDB file for fast local
inspection and for tests that don't need a live PostgreSQL instance; it is
never Northstar's canonical environment (see §3).
