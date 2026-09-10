-- sales dashboard -- RW, Sales Ops
-- 1) nightly fact refresh: job refresh_delivered_sales, runs at about
--    02:00 and loads the previous day's deliveries for :run_date
-- 2) monthly dashboard view over the fact

delete from analytics.delivered_sales
 where delivery_date = :run_date;

insert into analytics.delivered_sales (
    delivery_date, order_id, order_item_id, customer_id, sales_region,
    product_id, qty, gross_amount, discount_amount, net_amount,
    std_unit_cost, std_cost_amount, loaded_at
)
select
    o.delivery_date,
    o.order_id,
    oi.order_item_id,
    o.customer_id,
    c.sales_region,
    oi.product_id,
    oi.qty,
    oi.qty * oi.unit_price,
    oi.qty * oi.unit_price - oi.line_net_amount,
    oi.line_net_amount,
    p.standard_cost,
    oi.qty * p.standard_cost,
    now()
from core.orders o
join core.order_items oi on oi.order_id = o.order_id
join core.customers c on c.customer_id = o.customer_id
join core.products p on p.product_id = oi.product_id
where o.status = 'delivered'
  and o.delivery_date = :run_date;

create or replace view analytics.sales_dashboard_monthly as
with returned as (
    select date_trunc('month', r.received_date)::date as month,
           c.sales_region,
           sum((ri.qty_returned * il.net_amount + il.qty / 2) / il.qty) as returned_value
    from core.returns r
    join core.return_items ri on ri.return_id = r.return_id
    join core.invoice_lines il on il.invoice_line_id = ri.invoice_line_id
    join core.customers c on c.customer_id = r.customer_id
    group by 1, 2
),
delivered as (
    select date_trunc('month', ds.delivery_date)::date as month,
           ds.sales_region,
           sum(ds.net_amount) as revenue,
           sum(ds.std_cost_amount) as cogs_std,
           count(distinct ds.order_id) as order_count
    from analytics.delivered_sales ds
    group by 1, 2
)
select d.month,
       d.sales_region,
       d.revenue,
       d.cogs_std,
       d.revenue - d.cogs_std as margin,
       round(100.0 * (d.revenue - d.cogs_std) / nullif(d.revenue, 0), 1) as margin_pct,
       coalesce(r.returned_value, 0) as returned_value,
       d.order_count
from delivered d
left join returned r
       on r.month = d.month
      and r.sales_region = d.sales_region;
