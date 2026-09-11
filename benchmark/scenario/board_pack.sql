-- YP, 2024; do not change without telling FP&A.
-- Run on the second business day for the month just ended. Bind the period
-- (YYYY-MM) and the run timestamp stamped on the three pack rows.
WITH pack_run(period, generated_at) AS (
 SELECT CAST(:period AS TEXT), CAST(:generated_at AS TIMESTAMP)
), sales AS (
 SELECT c.period, SUM(d.net_amount) AS revenue, SUM(d.std_cost_amount) AS cost
 FROM pack_run c JOIN analytics.delivered_sales d
   ON SUBSTRING(CAST(d.delivery_date AS VARCHAR),1,7)=c.period
 WHERE d.loaded_at<=c.generated_at
 GROUP BY c.period
), adjustments AS (
 SELECT c.period, SUM(n.total_amount) AS amount
 FROM pack_run c JOIN core.credit_notes n ON n.accounting_period=c.period
 WHERE n.created_at<=c.generated_at
 GROUP BY c.period
), monthly AS (
 SELECT c.period, COALESCE(s.revenue,0)-COALESCE(a.amount,0) AS revenue,
        COALESCE(s.cost,0) AS cost, c.generated_at
 FROM pack_run c LEFT JOIN sales s USING(period)
 LEFT JOIN adjustments a USING(period)
)
SELECT period, 'Revenue' AS kpi, CAST(revenue AS NUMERIC(30,12)) AS value,
       generated_at, 'board_pack_monthly' AS source_job FROM monthly
UNION ALL
SELECT period, 'Gross Margin', CAST(revenue-cost AS NUMERIC(30,12)),
       generated_at, 'board_pack_monthly' FROM monthly
UNION ALL
SELECT period, 'Gross Margin %', CAST(1.0*(revenue-cost)/NULLIF(revenue,0) AS NUMERIC(30,12)),
       generated_at, 'board_pack_monthly' FROM monthly
ORDER BY period,kpi
