# Northstar Distribution
## August 2026 Reporting Reliability Audit

**Synthetic demonstration - not a real client engagement.**

PT Northstar Distribusi Nusantara is a fictional Indonesian-style B2B distributor.
Observation: 8 September 2026, 09:00 WIB. Generated population: **demo** profile.
All money is integer Indonesian rupiah (IDR). Percentages are rounded for display.

### Decision required

Which August Revenue and Gross Margin should the CFO present for Board financial
performance, and should the pack circulated on 2 September be reissued?

**Reissue the financial-performance pack using Finance's closed P&L.** Keep Sales'
commercial measures alongside it with explicit labels. Both Revenue and Gross
Margin are **CONFLICTING as reported; fully reconciled by the evidence**. The
Board hybrid has mechanical errors and is unsuitable for the decision. This does
not make Sales' commercial view wrong.

| Surface | Revenue concept and amount | Gross margin concept and amount | Margin % |
|---|---|---|---|
| Finance, closed 7 September | RNMR: Rp 59,257,637,000 <!-- number:RNMR --> | FGM: Rp 13,125,508,130 <!-- number:FGM --> | 22.1499% <!-- number:finance_margin_pct --> |
| Sales, August deliveries | DSV: Rp 61,000,982,000 <!-- number:DSV --> | CM: Rp 12,200,196,400 <!-- number:CM --> | 20.0000% <!-- number:sales_margin_pct --> |
| Board, circulated 2 September | BR: Rp 60,035,534,525 <!-- number:BR --> | BGM: Rp 11,234,748,925 <!-- number:BGM --> | 18.7135% <!-- number:board_margin_pct --> |

**Revenue verdict:** CONFLICTING under a common label. RNMR is the appropriate
August P&L basis. DSV remains a legitimate commercial delivery measure.

**Gross Margin verdict:** CONFLICTING under a common label. FGM is the appropriate
P&L basis; CM remains legitimate for commercial performance at standard cost.
Board Gross Margin mixes netted credits with unreversed delivery cost.

### Measured business materiality

Relative to the closed Finance P&L, the circulated Board pack overstates Revenue
by Rp 777,897,525 <!-- number:board_revenue_difference --> (1.3127% <!-- number:board_revenue_difference_pct -->). Its
Gross Margin difference is Rp -1,890,759,205 <!-- number:board_margin_difference -->, and its margin-rate
difference is -3.4364 pp <!-- number:board_margin_difference_pp -->.

These are measured reporting differences, **not cash losses**. The August result
feeds the second-half forecast and sales-incentive accrual; using an incompatible
basis can change those decisions. No forecast loss or incentive overpayment has
been quantified from the supplied evidence.

**Immediate action:** Finance Controller DA certifies the P&L values; the CFO
appoints an accountable Board-pack owner; FP&A reissues the pack after close.

<!-- pagebreak -->

## What the numbers actually mean

**Finance - Recognized Net Merchandise Revenue (RNMR).** Invoice accounting
period equals invoice posting month; no accrual for unbilled deliveries.
Merchandise is net of line discounts and recognized credit notes. VAT and freight
are excluded. Actual Recognized COGS (ARC) uses actual cost effective at delivery,
captured on invoice lines, less original-cost reversals on recognized credits.
Finance Gross Margin (FGM) is RNMR minus ARC. ARC is Rp 46,132,128,870 <!-- number:ARC -->.

**Sales - Delivered Sales Value (DSV).** Calendar month of delivery, net of line
discounts, excluding VAT, freight, cancellations and undelivered orders. Deliveries
remain gross of returns; received returns are displayed separately. Commercial
Margin (CM) subtracts standard cost effective at delivery, Rp 48,800,785,600 <!-- number:K_std -->.
The August population is complete from the 1 September T+1 refresh. Subsequent
returns do not revise historical delivered Revenue or Margin.

**Board - as reported.** Delivery-based sales minus credit-document totals using
Finance's accounting period, restricted to documents present at the earlier run.
Credit totals include VAT even though sales exclude it. Cost remains standard
cost of all delivered goods, with no reversal for credits already deducted.

## Revenue reconciliation

Each bridge starts with Finance RNMR and adds the following signed amounts.
The categories distinguish legitimate definitions from snapshot differences and
actual query errors; no unexplained residual remains. Each percentage is the
signed line amount divided by starting Finance RNMR.

### Finance RNMR to Sales DSV

| Bridge line | Category | Signed change | % of RNMR |
|---|---|---:|---:|
| Delivery rather than invoice posting period | definition | Rp 627,000 <!-- number:revenue_finance_to_sales.delivery_vs_posting --> | 0.0011% <!-- number:revenue_finance_to_sales.delivery_vs_posting.pct --> |
| Sales keeps deliveries gross of returns | definition | Rp 1,742,718,000 <!-- number:revenue_finance_to_sales.gross_of_returns --> | 2.9409% <!-- number:revenue_finance_to_sales.gross_of_returns.pct --> |

Endpoint: Sales DSV, Rp 61,000,982,000 <!-- number:DSV -->. Gross-of-returns reporting is intentional and
legitimate for Sales' commercial context.

### Finance RNMR to circulated Board Revenue

| Bridge line | Category | Signed change | % of RNMR |
|---|---|---:|---:|
| Delivery rather than invoice posting period | definition | Rp 627,000 <!-- number:revenue_finance_to_board.delivery_vs_posting --> | 0.0011% <!-- number:revenue_finance_to_board.delivery_vs_posting.pct --> |
| Credits posted after the Board snapshot | timing | Rp 872,945,500 <!-- number:revenue_finance_to_board.credits_after_snapshot --> | 1.4731% <!-- number:revenue_finance_to_board.credits_after_snapshot.pct --> |
| VAT deducted on credits visible to Board | defect | Rp -95,674,975 <!-- number:revenue_finance_to_board.vat_on_visible_credits --> | -0.1615% <!-- number:revenue_finance_to_board.vat_on_visible_credits.pct --> |

Endpoint: Board Revenue, Rp 60,035,534,525 <!-- number:BR -->. Re-running the inherited SQL on the later
horizon without the historical cutoff produces a different number; it does not
reproduce the circulated pack.

<!-- pagebreak -->

## Gross Margin reconciliation

Each bridge starts with Finance FGM. Revenue bridge lines are shown individually
so their categories remain visible on the margin bridge. Each percentage is the
signed line amount divided by starting Finance FGM.

### Finance FGM to Sales CM

| Bridge line | Category | Signed change | % of FGM |
|---|---|---:|---:|
| Delivery rather than invoice posting period | definition | Rp 627,000 <!-- number:gross_margin_finance_to_sales.delivery_vs_posting --> | 0.0048% <!-- number:gross_margin_finance_to_sales.delivery_vs_posting.pct --> |
| Sales keeps deliveries gross of returns | definition | Rp 1,742,718,000 <!-- number:gross_margin_finance_to_sales.gross_of_returns --> | 13.2773% <!-- number:gross_margin_finance_to_sales.gross_of_returns.pct --> |
| Actual cost: delivery rather than posting period | definition | Rp 3,397,160 <!-- number:gross_margin_finance_to_sales.cost_period_basis --> | 0.0259% <!-- number:gross_margin_finance_to_sales.cost_period_basis.pct --> |
| Standard rather than actual cost | cost basis | Rp -1,314,142,820 <!-- number:gross_margin_finance_to_sales.standard_vs_actual --> | -10.0121% <!-- number:gross_margin_finance_to_sales.standard_vs_actual.pct --> |
| No reversal, consistent with gross-of-returns Sales | definition | Rp -1,357,911,070 <!-- number:gross_margin_finance_to_sales.gross_of_returns_cost --> | -10.3456% <!-- number:gross_margin_finance_to_sales.gross_of_returns_cost.pct --> |

Endpoint: Sales CM, Rp 12,200,196,400 <!-- number:CM -->.

### Finance FGM to circulated Board Gross Margin

| Bridge line | Category | Signed change | % of FGM |
|---|---|---:|---:|
| Delivery rather than invoice posting period | definition | Rp 627,000 <!-- number:gross_margin_finance_to_board.delivery_vs_posting --> | 0.0048% <!-- number:gross_margin_finance_to_board.delivery_vs_posting.pct --> |
| Credits posted after the Board snapshot | timing | Rp 872,945,500 <!-- number:gross_margin_finance_to_board.credits_after_snapshot --> | 6.6508% <!-- number:gross_margin_finance_to_board.credits_after_snapshot.pct --> |
| VAT deducted on credits visible to Board | defect | Rp -95,674,975 <!-- number:gross_margin_finance_to_board.vat_on_visible_credits --> | -0.7289% <!-- number:gross_margin_finance_to_board.vat_on_visible_credits.pct --> |
| Actual cost: delivery rather than posting period | definition | Rp 3,397,160 <!-- number:gross_margin_finance_to_board.cost_period_basis --> | 0.0259% <!-- number:gross_margin_finance_to_board.cost_period_basis.pct --> |
| Standard rather than actual cost | cost basis | Rp -1,314,142,820 <!-- number:gross_margin_finance_to_board.standard_vs_actual --> | -10.0121% <!-- number:gross_margin_finance_to_board.standard_vs_actual.pct --> |
| Cost reversal on credits after the snapshot | timing | Rp -680,225,670 <!-- number:gross_margin_finance_to_board.cost_on_credits_after_snapshot --> | -5.1825% <!-- number:gross_margin_finance_to_board.cost_on_credits_after_snapshot.pct --> |
| Cost not reversed on credits already netted | defect | Rp -677,685,400 <!-- number:gross_margin_finance_to_board.cost_on_visible_credits --> | -5.1631% <!-- number:gross_margin_finance_to_board.cost_on_visible_credits.pct --> |

Endpoint: Board Gross Margin, Rp 11,234,748,925 <!-- number:BGM -->.

### Why the same cost amount receives different classifications

Total period COGS reversal R_period is Rp 1,357,911,070 <!-- number:R_period -->. It consists of R_early,
Rp 677,685,400 <!-- number:R_early -->, plus R_late, Rp 680,225,670 <!-- number:R_late -->. **R_period = R_early + R_late.**

For Sales, not reversing this cost is a **definition difference**: DSV also keeps
returns gross. For Board, the credits it already deducted require a corresponding
cost reversal; omitting R_early is a **defect**. The later credits and their
R_late reversals did not exist at the Board snapshot, so both are **timing**.
The same credit-note membership split drives the revenue and cost attributions.

The Sales-to-Board differences are obtained by subtracting the Finance-to-Sales
bridge from the Finance-to-Board bridge, category by category. The reconciliation
therefore accounts for every pair of surfaces without adding another cause.

<!-- pagebreak -->

## Evidence coverage and the two supporting findings

**Evidence Coverage: 23 of 23 supplied assets inspected** - the operational
tables, reporting objects and job history in PostgreSQL, plus all seven supplied
files. This is coverage of this bounded demonstration, not a general governance
score. Inspection of all supplied assets does not establish an approved Board
definition where no approval document exists.

| Evidence group | What it establishes |
|---|---|
| Core operational tables | Order/delivery/invoice chronology; original prices, discounts and costs; warehouse returns; credit posting and period allocation. Payments corroborate lifecycle realism only. |
| Finance extract and finance_revenue.sql | Closed P&L values and component breakdown; Finance's posting-period and actual-cost basis. |
| Delivered-sales fact, dashboard view and sales_dashboard.sql | T+1 delivery population, gross-of-returns rule, standard cost and separately displayed return receipts. |
| Board snapshot, board_pack.sql and august_board_pack.csv | The circulated values, exact inherited logic and historical generated_at timestamp. |
| Job runs, comments and the three notes | Recurring close cadence, successful runs, Finance/Sales responsibilities and the absent Board approval/owner. |

**Supporting finding - freshness.** Board ran on 2 September at 08:15. The
back-dated August credits arrived in the 2-4 September batches, before Finance
closed on 7 September at 17:30. Job history shows the same early-pack pattern
across the generated history. Every run succeeded; this is a snapshot/close
coordination problem, not a failed pipeline.

**Supporting finding - ownership and definition.** The November 2024 YP handover
records a verbal agreement, says it was never written up and leaves the future
owner as TBD. NS runs the pack, which does not establish accountable ownership.
The Board table has no comments. Finance's notes describe its own policy but do
not approve the pack. Sales' stale Revenue comment still says net of returns,
while RW's early-2025 note and current SQL describe gross deliveries. These
fragments establish ambiguity, not an agreed Board P&L definition.

## Remediation and re-check

| Sequence | Accountable action | Verification evidence |
|---|---|---|
| Before reissue | CFO chooses the Finance P&L basis and appoints the Board-pack accountable owner; DA certifies the closed values. | Written decision-context definitions and Finance sign-off. |
| Rebuild the pack | FP&A retires the hybrid pair. Present RNMR/FGM and DSV/CM separately with their explicit names, periods, cost bases and snapshots. | Reissued pack reconciles to Finance and Sales independently. |
| Before the next close | Assigned owner coordinates pack certification after Finance close; Sales Ops RW corrects the stale dashboard comment. | Agreed close-to-pack checklist and updated comment. |
| At the next re-check | Re-run surface queries and the bridges after close; preserve the previously circulated snapshot separately. | No unexplained residual; every new difference classified and signed off. |

These are recommendations. The demonstration executes no remediation against
source data and creates no recurring monitor.

<!-- pagebreak -->

## Technical verification register

The following components come from core rows, independently of the reporting
queries. Cross-period revenue legs are shown separately even though their net is
small. Amounts are ex-VAT merchandise unless explicitly labelled otherwise.

| Component | Generated amount |
|---|---:|
| Gross invoice merchandise posted in August (G_post) | Rp 61,000,355,000 <!-- number:G_post --> |
| August credit merchandise (C_period) | Rp 1,742,718,000 <!-- number:C_period --> |
| Credit merchandise visible at Board run (C_early) | Rp 869,772,500 <!-- number:C_early --> |
| Credit merchandise after Board run (C_late) | Rp 872,945,500 <!-- number:C_late --> |
| August deliveries invoiced in September (D1) | Rp 2,514,536,000 <!-- number:D1 --> |
| July deliveries invoiced in August (D2) | Rp 2,513,909,000 <!-- number:D2 --> |
| Actual invoice cost in August (K_post) | Rp 47,490,039,940 <!-- number:K_post --> |
| Actual cost on D1 (K1) | Rp 1,955,399,080 <!-- number:K1 --> |
| Actual cost on D2 (K2) | Rp 1,958,796,240 <!-- number:K2 --> |
| Actual cost of August deliveries (K_act) | Rp 47,486,642,780 <!-- number:K_act --> |
| Standard minus actual delivery cost | Rp 1,314,142,820 <!-- number:cost_difference --> |
| VAT on visible credits (deducted by Board) | Rp 95,674,975 <!-- number:VAT_early --> |

### Materiality checks on the generated demo

| Check | Observed | Contract threshold |
|---|---:|---|
| C_period / RNMR | 2.9409% <!-- number:materiality.credit_rnmr --> | 2.5%-4.0% |
| C_late / C_period | 50.0910% <!-- number:materiality.late_credit_share --> | At least 35% |
| D1 / RNMR | 4.2434% <!-- number:materiality.D1_rnmr --> | At least 0.8% |
| D2 / RNMR | 4.2423% <!-- number:materiality.D2_rnmr --> | At least 0.8% |
| Absolute standard/actual difference / K_act | 2.7674% <!-- number:materiality.cost_difference_share --> | At least 1% |
| Finance margin level | 22.1499% <!-- number:materiality.finance_margin --> | 15%-25% |
| Finance-Sales Revenue gap / RNMR | 2.9420% <!-- number:materiality.revenue_RNMR_DSV --> | At least 0.5% |
| Finance-Board Revenue gap / RNMR | 1.3127% <!-- number:materiality.revenue_RNMR_BR --> | At least 0.5% |
| Sales-Board Revenue gap / RNMR | 1.6292% <!-- number:materiality.revenue_DSV_BR --> | At least 0.5% |
| Finance-Sales margin-rate gap | 2.1499 pp <!-- number:materiality.margin_finance_sales --> | At least 0.5 pp |
| Finance-Board margin-rate gap | 3.4364 pp <!-- number:materiality.margin_finance_board --> | At least 0.5 pp |
| Sales-Board margin-rate gap | 1.2865 pp <!-- number:materiality.margin_sales_board --> | At least 0.5 pp |

These are demonstration-design materiality checks, not customer health scores.

<!-- pagebreak -->

## Reproduce this audit

Use the repository's documented PostgreSQL setup and generate the **demo** profile
from code and configuration into a clean local database. The committed sample
uses the configured canonical seed; generated data and hidden QA truth are not
committed. No service beyond local PostgreSQL is needed.

1. Compare the August Finance extract, Sales monthly totals across regions and
   Board CSV. Sum the Sales amounts before calculating its company-wide margin
   rate; do not average regional percentages.
2. Re-run finance_revenue.sql at the observation horizon. Its closed amounts
   reproduce unchanged. Re-run board_pack.sql with each historical run instant;
   credit_notes.created_at must be no later than generated_at. Using the horizon
   instead is a freshness experiment, not reproduction of the circulated pack.
3. Join invoices and merchandise lines to orders for D1/D2 and K1/K2. Recover
   standard and actual costs from their effective dates. Sum return quantities
   against the original invoice net unit price and captured actual cost.
4. Split August credit notes once at the Board generated_at timestamp. The
   visible set supplies C_early, its VAT and R_early; the complementary set
   supplies C_late and R_late. Rebuild the four bridges above.
5. Run the read-only Northstar re-check and repository tests. The re-check takes
   only database evidence and the requested period; it never reads the hidden
   manifest or uses generation targets to calculate the amounts.

```text
python -m benchmark.scenario.reconcile --period 2026-08
python -m pytest
```

Technical source: benchmark/scenario/reconcile.py implements this bounded,
read-only calculation. Surface queries and notes are supplied in
benchmark/data/evidence/. Database evidence is the core, finance, analytics and
management schemas. PostgreSQL is Northstar's canonical environment; the optional
DuckDB mirror exists only for internal development and offline tests.

### Complete supplied file inventory

finance_revenue.sql; sales_dashboard.sql; board_pack.sql; august_board_pack.csv;
finance_close_notes.md; sales_dashboard_notes.md; board_pack_handover.md.

### Boundaries and disclosure

This is one synthetic demonstration of Revenue and Gross Margin for a fictional
company. It uses independently invented organizations, products, locations and
role initials; no personal, employer or client records are used. The VAT rate is
a fictional internal setting, not tax guidance. Historical behavior and the
September tail support this specific management dispute.

There is no universal correct Revenue definition. Correctness depends on the
stated decision and consistency of the chosen basis. The practical recommendation
is to present Finance financial performance and Sales commercial performance
separately, certify after Finance close, and retire the Board hybrid.
