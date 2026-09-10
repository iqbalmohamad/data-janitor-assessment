-- monthly P&L extract load -- DA
-- run at period close for the period being closed; loads that period's
-- row into finance.monthly_pnl_extract.

insert into finance.monthly_pnl_extract (
    accounting_period,
    gross_invoiced_merchandise,
    credit_notes_merchandise,
    net_merchandise_revenue,
    freight_income,
    cogs_invoiced,
    cogs_reversed,
    recognized_cogs,
    gross_margin,
    gross_margin_pct,
    closed_at,
    prepared_by
)
select
    :period,
    inv.gross_merch,
    cn.credit_merch,
    inv.gross_merch - cn.credit_merch,
    frt.freight_income,
    inv.cogs_invoiced,
    cn.cogs_reversed,
    inv.cogs_invoiced - cn.cogs_reversed,
    (inv.gross_merch - cn.credit_merch) - (inv.cogs_invoiced - cn.cogs_reversed),
    round(100.0 * ((inv.gross_merch - cn.credit_merch) - (inv.cogs_invoiced - cn.cogs_reversed))
          / nullif(inv.gross_merch - cn.credit_merch, 0), 2),
    now(),
    'DA'
from
    (select coalesce(sum(il.net_amount), 0) as gross_merch,
            coalesce(sum(il.qty * il.unit_cost_actual), 0) as cogs_invoiced
       from core.invoice_lines il
       join core.invoices i on i.invoice_id = il.invoice_id
      where il.line_type = 'merchandise'
        and i.accounting_period = :period) inv,
    (select coalesce(sum(il.net_amount), 0) as freight_income
       from core.invoice_lines il
       join core.invoices i on i.invoice_id = il.invoice_id
      where il.line_type = 'freight'
        and i.accounting_period = :period) frt,
    (select coalesce(sum(merchandise_amount), 0) as credit_merch,
            coalesce(sum(cogs_reversal_amount), 0) as cogs_reversed
       from core.credit_notes
      where accounting_period = :period) cn;
