-- DA; run at period close for the period being closed.
-- Bind the accounting period (YYYY-MM) and the close timestamp; the row is
-- loaded into finance.monthly_pnl_extract and kept with its components.
WITH close_run(accounting_period, closed_at) AS (
 SELECT CAST(:period AS TEXT), CAST(:closed_at AS TIMESTAMP)
), billed AS (
 SELECT i.accounting_period,
        SUM(CASE WHEN l.line_type='merchandise' THEN l.net_amount ELSE 0 END) AS merchandise,
        SUM(CASE WHEN l.line_type='freight' THEN l.net_amount ELSE 0 END) AS freight,
        SUM(CASE WHEN l.line_type='merchandise' THEN l.qty*l.unit_cost_actual ELSE 0 END) AS cost
 FROM core.invoices i JOIN core.invoice_lines l USING(invoice_id)
 JOIN close_run c ON c.accounting_period=i.accounting_period
 WHERE i.created_at<=c.closed_at AND l.created_at<=c.closed_at
 GROUP BY i.accounting_period
), credits AS (
 SELECT n.accounting_period, SUM(n.merchandise_amount) AS merchandise,
        SUM(n.cogs_reversal_amount) AS cost
 FROM core.credit_notes n JOIN close_run c ON c.accounting_period=n.accounting_period
 WHERE n.created_at<=c.closed_at
 GROUP BY n.accounting_period
), pnl AS (
 SELECT c.accounting_period, COALESCE(b.merchandise,0) AS gross_invoiced_merchandise,
        COALESCE(n.merchandise,0) AS credit_notes_merchandise,
        COALESCE(b.merchandise,0)-COALESCE(n.merchandise,0) AS net_merchandise_revenue,
        COALESCE(b.freight,0) AS freight_income, COALESCE(b.cost,0) AS cogs_invoiced,
        COALESCE(n.cost,0) AS cogs_reversed,
        COALESCE(b.cost,0)-COALESCE(n.cost,0) AS recognized_cogs, c.closed_at
 FROM close_run c LEFT JOIN billed b USING(accounting_period)
 LEFT JOIN credits n USING(accounting_period)
)
SELECT accounting_period, gross_invoiced_merchandise, credit_notes_merchandise,
       net_merchandise_revenue, freight_income, cogs_invoiced, cogs_reversed,
       recognized_cogs, net_merchandise_revenue-recognized_cogs AS gross_margin,
       CAST(1.0*(net_merchandise_revenue-recognized_cogs)/NULLIF(net_merchandise_revenue,0) AS NUMERIC(20,12)) AS gross_margin_pct,
       closed_at, 'DA' AS prepared_by
FROM pnl
