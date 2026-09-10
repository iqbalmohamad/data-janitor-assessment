# Board pack -- handover note

YP, November 2024. Written before my last day; NS runs this now.

- The pack numbers come from `board_pack.sql` (kept next to this note).
  The job `board_pack_monthly` runs it for the closed month on the
  morning of the 2nd working day of the new month, so the draft pack is
  with management early in the week.
- Revenue in the pack is dashboard revenue less returns per Finance, so
  it matches what Finance books for returns. Agreed verbally with the
  Finance Controller (mid-2024). Never written up properly -- this note
  is what there is.
- The returns deduction takes `total_amount` off the credit notes so the
  figure ties to the credit note documents.
- Gross Margin is Revenue less the dashboard's standard cost column, and
  Gross Margin % comes off those two.
- Owner going forward: TBD. Ask FP&A.
- Do not change the SQL without telling FP&A -- the pack history in
  `management.board_kpi_monthly` has to stay comparable month to month.
