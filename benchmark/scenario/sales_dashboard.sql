-- RW; nightly refresh_delivered_sales, run after 02:00 for the previous
-- day's deliveries. Bind the delivery date being loaded and the completion
-- time stamped on the rows. Rerunning a date replaces that date's rows.
DELETE FROM analytics.delivered_sales WHERE delivery_date=CAST(:run_date AS DATE);

INSERT INTO analytics.delivered_sales
SELECT o.delivery_date, o.order_id, l.order_item_id, o.customer_id,
       c.sales_region, l.product_id, l.qty, l.qty*l.unit_price,
       l.qty*l.unit_price-l.line_net_amount, l.line_net_amount,
       h.unit_cost, l.qty*h.unit_cost, CAST(:loaded_at AS TIMESTAMP)
FROM core.orders o JOIN core.order_items l USING(order_id)
JOIN core.customers c USING(customer_id)
JOIN core.products p USING(product_id)
JOIN core.product_cost_history h ON h.product_id=l.product_id AND h.cost_type='standard'
 AND h.effective_from=(SELECT MAX(h2.effective_from) FROM core.product_cost_history h2
                      WHERE h2.product_id=l.product_id AND h2.cost_type='standard'
                        AND h2.effective_from<=o.delivery_date)
WHERE o.status='delivered' AND o.delivery_date=CAST(:run_date AS DATE)
ORDER BY l.order_item_id;

CREATE VIEW analytics.sales_dashboard_monthly AS
WITH deliveries AS (
 SELECT SUBSTRING(CAST(delivery_date AS VARCHAR),1,7) AS period, sales_region,
        SUM(net_amount) AS revenue, SUM(std_cost_amount) AS cogs_std,
        COUNT(DISTINCT order_id) AS order_count
 FROM analytics.delivered_sales GROUP BY 1,2
), received AS (
 SELECT SUBSTRING(CAST(r.received_date AS VARCHAR),1,7) AS period, c.sales_region,
        SUM(CAST(ri.qty_returned AS NUMERIC)*il.net_amount/il.qty) AS returned_value
 FROM core.returns r JOIN core.return_items ri USING(return_id)
 JOIN core.invoice_lines il USING(invoice_line_id)
 JOIN core.customers c ON c.customer_id=r.customer_id
 GROUP BY 1,2
)
SELECT d.period, d.sales_region, d.revenue, d.cogs_std, d.revenue-d.cogs_std AS margin,
       CAST(1.0*(d.revenue-d.cogs_std)/NULLIF(d.revenue,0) AS NUMERIC(20,12)) AS margin_pct,
       COALESCE(r.returned_value,0) AS returned_value, d.order_count
FROM deliveries d LEFT JOIN received r USING(period,sales_region);
