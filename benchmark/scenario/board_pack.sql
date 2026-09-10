-- board pack kpis -- YP, 2024. do not change without telling FP&A.
-- run for the closed month on the 2nd working day of the following month
-- (job board_pack_monthly); writes the pack rows for :period into
-- management.board_kpi_monthly.

insert into management.board_kpi_monthly (period, kpi, value, generated_at, source_job)
with sales as (
    select coalesce(sum(net_amount), 0) as revenue,
           coalesce(sum(std_cost_amount), 0) as cost
      from analytics.delivered_sales
     where to_char(delivery_date, 'YYYY-MM') = :period
),
credits as (
    select coalesce(sum(total_amount), 0) as credit_total
      from core.credit_notes
     where accounting_period = :period
)
select :period,
       'Revenue',
       s.revenue - c.credit_total,
       now(),
       'board_pack_monthly'
  from sales s, credits c
union all
select :period,
       'Gross Margin',
       (s.revenue - c.credit_total) - s.cost,
       now(),
       'board_pack_monthly'
  from sales s, credits c
union all
select :period,
       'Gross Margin %',
       round(100.0 * ((s.revenue - c.credit_total) - s.cost)
             / nullif(s.revenue - c.credit_total, 0), 1),
       now(),
       'board_pack_monthly'
  from sales s, credits c;
