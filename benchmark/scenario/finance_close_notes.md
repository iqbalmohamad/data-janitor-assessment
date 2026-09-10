# Monthly close notes -- Finance

Working notes for the monthly close. DA. Last tidied March 2026.

Checklist each month (period P, all times WIB):

1. Confirm the billing run is complete: every order delivered through the
   last day of P has an invoice. Invoices post 0-3 working days after
   delivery; we never back-date an invoice and we do not accrue unbilled
   deliveries. Merchandise revenue sits in the period of the invoice date
   (`invoices.accounting_period`).
2. Credit notes for returns: goods received back at the warehouse on or
   before the last day of P must be credited into P. Whatever the
   warehouse has received by month end that we have not yet credited gets
   the period-end batch: credit notes raised on working days 2-4 of the
   following month, posting date as raised, `accounting_period = P`.
   Anything received after month end is next period's business.
3. Freight lines are not merchandise. They go to `freight_income` in the
   extract, never into revenue.
4. VAT stays out of everything: revenue, credits, cost, margin are all
   ex-VAT.
5. COGS is actual cost as posted on the invoice lines
   (`unit_cost_actual`, from the purchasing valuation at delivery), less
   the cost taken back on credit notes (`cogs_reversal_amount`, always at
   the original line's cost, never at the cost on the credit date).
6. Run `finance_revenue.sql` for P and tie the loaded row to the trial
   balance. Close on working day 5 of the following month; sign-off DA.

The extract (`finance.monthly_pnl_extract`) is the closed P&L view of
the month and is not restated afterwards; late corrections go into the
following period.
