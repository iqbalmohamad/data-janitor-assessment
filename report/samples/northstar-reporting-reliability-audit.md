# Reporting Reliability Audit — August 2026 Board Financial-Performance Pack

**Northstar Distribution** (PT Northstar Distribusi Nusantara)
Prepared for: Chief Financial Officer · Independent reconciliation
Audit period: **August 2026** · Reporting currency: Indonesian rupiah (IDR)

> **Synthetic demonstration — not a real client engagement.** Northstar
> Distribution is a fictional company. All customers, products, figures,
> notes, and reporting logic are synthetic and were generated
> deterministically for this demonstration (seed `20260910`, `demo`
> profile). No real organization, person, or data is depicted. This
> document shows how a Reporting Reliability / Metric Consistency audit
> reads from evidence to an executive conclusion.

---

## 1. Management question

The September board meeting is being prepared. Three numbers labelled
"Revenue" — and three labelled "Gross Margin" — exist for August 2026, and
none of them agree:

| Surface | "Revenue" | "Gross Margin" | Margin % |
|---|---:|---:|---:|
| Finance monthly P&L extract | **Rp 183,996,376,369** | Rp 32,042,248,469 | 17.41% |
| Sales dashboard | **Rp 197,029,537,707** | Rp 39,076,214,107 | 19.83% |
| Board pack (circulated 2 Sep) | **Rp 193,511,839,728** | Rp 35,558,516,128 | 18.38% |

The board reads this pack to judge August **financial performance** (how
much revenue and gross margin Northstar earned), and the August result also
feeds the second-half revenue forecast and the sales-incentive accrual. The
CFO must decide **which number goes to the board, and whether the pack must
be reissued.**

The spread is not small: Rp 13.0 billion separates the highest and lowest
"Revenue" (7.1% of the Finance figure), and the margin rate ranges across
2.4 percentage points. A few percent on this pack moves the forecast and
the incentive accrual materially.

## 2. Executive verdict

**Both metrics are `CONFLICTING` as reported, and both reconcile in full.**
The three surfaces are not three attempts at one number — they measure
three different things, two of them legitimately.

- **Finance** is measuring recognized P&L revenue on the accounting basis.
  It is the **appropriate basis for the board's financial-performance
  decision.**
- **Sales** is measuring commercial delivery performance. It is a
  **legitimate operational measure** — but it is labelled "Revenue" and
  "Margin", which is not what it is.
- **The Board pack is the defective surface.** Its "Revenue" is a hybrid of
  incompatible definitions and snapshots, and it contains a genuine
  mechanical error. It is appropriate for **no** decision context.

Critically, the Board number is neither the highest nor the lowest of the
three — which is exactly why the disagreement was not caught by eye. It
looks like a reasonable middle number. It is not.

**Recommendation for the board pack:** present the **Finance P&L figures**
(revenue Rp 184.0 bn, gross margin 17.4%) as August financial performance,
present the **Sales commercial figures** separately and clearly labelled as
delivered commercial performance, generate/certify the pack **after** the
Finance close, and **retire the hybrid "Revenue" line.**

This is not "Finance is right and Sales is wrong." Finance and Sales are
each right for their own question. The pack is wrong because it blends them
and miscomputes the blend.

## 3. Evidence coverage

| Evidence class | Inspected | Notes |
|---|---|---|
| Reporting surfaces | 3 of 3 | Finance extract, Sales dashboard view, Board KPI snapshot |
| Core operational tables | 11 of 11 | Orders → invoices → returns → credit notes, plus cost history |
| Supporting artifacts | 7 of 7 | Three query files, the circulated pack CSV, three note files |
| Job / freshness log | 1 of 1 | `analytics.etl_job_runs` — every run successful |
| Reconciliation lines | **all reproduced from source** | 0 unverifiable; 0 assumed |

Every figure in this report is recomputed from Northstar's own operational
data using each surface's own logic. Nothing is asserted from a summary
table. Confidence is **HIGH**: the disagreement is deterministic and fully
decomposed.

## 4. What each number actually measures

| Concept | Surface | Precise definition |
|---|---|---|
| **RNMR** — Recognized Net Merchandise Revenue | Finance | Merchandise on invoices **posted** in August (accounting-period basis), net of line discounts and of credit notes recognized in August; excludes VAT and freight. |
| **FGM** — Finance Gross Margin | Finance | RNMR − actual recognized COGS (actual purchase cost, net of COGS reversals on recognized credit notes). |
| **DSV** — Delivered Sales Value | Sales | Merchandise **delivered** in the calendar month (delivery-date basis), net of line discounts, **gross of returns**; excludes VAT and freight; cancelled orders excluded. |
| **CM** — Commercial Margin | Sales | DSV − **standard** cost of the delivered goods. |
| **Board "Revenue" (BR)** | Board | Delivered sales (as the dashboard shows) **minus** credit-note totals as of the pack run — but VAT-inclusive, and only the credits that existed on 2 September. A hybrid. |
| **Board "Gross Margin" (BGM)** | Board | BR − standard cost of deliveries, with **no** cost reversal for the returns it already subtracted from revenue. |

The two Finance concepts and the two Sales concepts are each internally
coherent. The two Board concepts are not.

## 5. Reconciliation

All amounts in rupiah. Each line is tagged with one root-cause category:
**definition** (legitimate — different coherent concepts), **timing**
(legitimate as a fact, a freshness issue as a practice), **cost basis**
(legitimate — standard vs actual cost), or **defect** (incoherent under any
definition — must be corrected).

### 5.1 Revenue: Finance → Board

| Line | Category | Amount |
|---|---|---:|
| Finance RNMR (starting basis) | — | 183,996,376,369 |
| Period basis: delivery-dated vs posting-dated | definition | +7,053,688,490 |
| Back-dated credit notes posted after the 2 Sep snapshot | timing | +2,810,375,595 |
| VAT-inclusive credit total deducted from an ex-VAT figure | **defect** | −348,600,726 |
| **Board "Revenue" (BR)** | | **193,511,839,728** |

The board pack's revenue is **Rp 9.5 billion (5.2%) above** the Finance P&L
basis. Of that gap, Rp 7.05 bn is a legitimate definition difference and Rp
2.81 bn is a timing/freshness difference — but **Rp 0.35 bn is a genuine
error** (see §6).

### 5.2 Revenue: Finance → Sales (for completeness)

| Line | Category | Amount |
|---|---|---:|
| Finance RNMR | — | 183,996,376,369 |
| Period basis: delivery-dated vs posting-dated | definition | +7,053,688,490 |
| Sales is gross of returns; Finance nets recognized credits | definition | +5,979,472,848 |
| **Sales DSV** | | **197,029,537,707** |

The Finance ↔ Sales revenue gap (Rp 13.0 bn) is **entirely definitional** —
two legitimate concepts, zero defect. This is the key point about Sales: it
is not broken, it is differently (and correctly) defined.

### 5.3 Gross Margin: Finance → Board

| Line | Category | Amount |
|---|---|---:|
| Finance FGM (starting basis) | — | 32,042,248,469 |
| Revenue bridge above, carried in | (by line) | +9,515,463,359 |
| Period basis on cost | definition | −5,822,047,700 |
| Standard vs actual cost | cost basis | +4,745,752,400 |
| COGS reversal on late credits (not yet posted at snapshot) | timing | −2,324,460,400 |
| COGS **not reversed** on credits the board already subtracted | **defect** | −2,598,440,000 |
| **Board "Gross Margin" (BGM)** | | **35,558,516,128** |

### 5.4 The teaching point: the same amount, two categories

Look at the credit-note cost reversals. On the **Sales** bridge, "no COGS
reversal" is a **legitimate definition** difference — Sales is gross of
returns, so leaving the cost in is internally consistent. On the **Board**
bridge, the same money splits in two: the portion for credits the board
**could see** (`R_early`, Rp 2.60 bn) is a **defect** — the board subtracted
those credits from revenue but never reversed their cost — while the portion
for credits that **did not yet exist** at the snapshot (`R_late`, Rp 2.32
bn) is **timing**.

Correctness is about internal consistency with a surface's own definition
and snapshot — not about the number itself.

## 6. The actual Board defect

Two mechanical errors, both in `board_pack.sql` (the inherited query), both
affecting only the credits that existed when the pack ran on 2 September:

1. **VAT-inclusive deduction from an ex-VAT figure.** The pack subtracts the
   credit notes' `total_amount` (which includes 11% VAT) from a
   delivered-sales figure that excludes VAT. Effect on revenue:
   **−Rp 348,600,726.**
2. **Revenue netted, cost not reversed.** The pack subtracts those credit
   notes from Revenue but never reverses their standard cost in the Gross
   Margin line. Effect on gross margin: **−Rp 2,598,440,000.**

Combined, the defect understates the board's gross margin by **Rp 2.95
billion** relative to what its own hybrid logic should produce. (The board's
reported margin still comes out *higher* than Finance's because the
legitimate cost-basis and definition effects are larger — which is precisely
why the error hid in plain sight.)

Everything else in the board pack is a legitimate definition, timing, or
cost-basis difference — not an error, but also not the right basis for the
board's P&L decision.

## 7. Business materiality

For the **August board financial-performance (P&L) decision**, the
appropriate basis is Finance:

- **Revenue: Rp 184.0 bn** (not the Rp 193.5 bn on the circulated pack).
  The pack overstates the P&L revenue basis by **Rp 9.5 bn (5.2%)**.
- **Gross margin: 17.4%** (not the 18.4% on the pack). The pack overstates
  the P&L margin rate by **~1.0 percentage point.**

Decisions affected:

- **Board judgement of August performance** — the pack currently shows a
  materially stronger revenue and margin picture than the closed P&L
  supports.
- **Second-half revenue forecast** — if extrapolated from the pack's
  delivery-blended revenue, the forecast inherits the 5.2% overstatement.
- **Sales-incentive accrual** — if accrued on the pack's 18.4% margin rather
  than the P&L 17.4%, the accrual is overstated.

This is **measured** impact (reproduced from source), not inferred. The
rupiah amount of the pure error is bounded and known: Rp 0.35 bn on revenue,
Rp 2.95 bn on gross margin.

## 8. What should be used, and how Sales should be presented

**For the August board P&L decision:** use **Finance RNMR (Rp 184.0 bn)**
and **Finance Gross Margin (17.4%)**. This is the recognized accounting
basis and the appropriate answer to "what did August earn?"

**For sales-team commercial performance:** **DSV (Rp 197.0 bn)** and
**Commercial Margin (19.8%)** remain legitimate and useful — but they must
be **labelled as commercial delivery measures, not "Revenue" and "Margin".**
The sales organization is correctly measured on what it delivered; the fault
is only in the generic naming, which invites the numbers to be read as P&L.

**For the board pack itself:** show the Finance P&L figures and the Sales
commercial figures **side by side, each clearly labelled**, generated after
the Finance close. **Do not** combine incompatible concepts into one hybrid
"Revenue" / "Gross Margin" pair. Retire the inherited hybrid line.

## 9. Ownership and accountability gap

The reconciliation surfaced a second, structural finding:

- **Finance** owns and documents its definition (`finance_close_notes.md`;
  a table comment names Finance as owner).
- **Sales** owns and documents its definition
  (`sales_dashboard_notes.md`).
- **The Board pack's "Revenue" definition is owned by no one.** It exists
  only inside an inherited query and a **stale November 2024 handover note**
  that records the logic was "agreed verbally… never written up" and names
  the future owner as **"TBD".** The management KPI table carries no
  documentation at all.

A supporting documentation issue reinforces this: the dashboard's `revenue`
column comment still describes the metric as **net of returns**, which was
true before a February 2025 change but contradicts the current view. Stale
metadata like this is how a hybrid definition survives unquestioned.

## 10. Freshness / snapshot finding

The board pack for August was generated on **2 September at 08:15**, on the
second business day of the month — **before** Finance posted its period-end
back-dated credit-note batches (2–4 September) and **before** the Finance
close on **7 September at 17:30**. The pack therefore missed Rp 2.81 bn of
August credits (the `timing` line in §5.1) that existed by the time the CFO
compared the numbers.

This is a **recurring pattern, not a one-month accident**: the job log
(`analytics.etl_job_runs`) shows the board job running early on the second
business day **every month**, and historical credit-note posting dates show
the same period-end batching every month. The Finance close is the only
complete snapshot of any period.

## 11. Remediation sequence

| # | Action | Owner | Horizon |
|---|---|---|---|
| 1 | Reissue the August board pack using Finance RNMR / FGM for financial performance; present Sales DSV / CM separately and labelled as commercial measures. | CFO / FP&A | Immediate |
| 2 | Assign a named owner for the board-pack metric definitions (the "TBD" in the 2024 handover). | CFO | 0–30 days |
| 3 | Correct `board_pack.sql`: deduct **ex-VAT** credit merchandise, and reverse standard cost on credited returns — **or** retire the hybrid entirely in favour of the two labelled Finance/Sales blocks (preferred). | FP&A | 0–30 days |
| 4 | Schedule the board pack to generate **after** the Finance close, not on the second business day. | FP&A / Data | 0–30 days |
| 5 | Fix the stale `sales_dashboard_monthly.revenue` column comment to match the current gross-of-returns definition. | Sales Ops | 30–60 days |
| 6 | Adopt a one-line labelling convention: internal surfaces name the concept (Recognized Revenue, Delivered Sales Value) rather than a generic "Revenue". | Finance + Sales | 30–60 days |

## 12. Re-check / verification path

After the next month's close, a competent reviewer can reproduce this entire
audit from source:

1. Recompute each surface from `core.*` using its own SQL
   (`finance_revenue.sql`, `sales_dashboard.sql`, `board_pack.sql`).
2. Reproduce the historical board snapshot with the
   `created_at <= generated_at` restriction; confirm a fresh run without it
   does **not** match the circulated number (that gap is the freshness
   finding).
3. Re-run the four reconciliation bridges in §5 and confirm each line ties
   to source and carries one root-cause category.
4. Confirm the corrected pack shows Finance P&L and Sales commercial figures
   separately and that the `board_pack.sql` mechanical errors are gone.

Every number in this report was produced this way.

---

*Prepared as an independent reconciliation by a CDMP-certified practitioner.
Synthetic demonstration environment; figures are reproducible from the
Northstar generator at seed 20260910, `demo` profile.*
