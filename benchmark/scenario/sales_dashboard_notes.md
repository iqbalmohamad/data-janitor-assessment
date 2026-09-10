# Sales dashboard -- how the numbers are put together

RW, Sales Ops. Updated February 2025.

- The dashboard reads `analytics.sales_dashboard_monthly`, which sits on
  `analytics.delivered_sales`. The fact is loaded by the nightly
  `refresh_delivered_sales` job (about 02:00 WIB, loads the previous
  day's deliveries), so a month is complete from the morning of the 1st.
- Revenue is what we delivered in the calendar month: the delivered
  order lines at net price (after line discount). Ex VAT, ex freight.
  Cancelled orders never enter the fact.
- Since the February 2025 change the month is shown gross of returns.
  Sales asked for this after the January review: a closed month kept
  shrinking as returns trickled in weeks later, and the team is measured
  on what it delivered. Returns now sit in their own column
  (`returned_value`, by the month the goods came back to the warehouse)
  so nobody loses sight of them, but they no longer reduce a delivered
  month.
- Margin is revenue less standard cost, per the pricing team's file
  (standard costs are revised each January and July). Actual costs are
  Finance's business, not the dashboard's.
- Region grouping follows `customers.sales_region`.
