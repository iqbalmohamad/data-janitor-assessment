"""Canonical acceptance path: full generation into PostgreSQL (smoke
profile), with every reported figure independently recomputed in SQL
written by this test -- not by the generator -- so the disagreement is
proven to be a product of each surface's own logic, never a hardcoded
value (assignment section 10.2-10.5; SC-9/SC-10/SC-14).

Requires a disposable PostgreSQL instance: set NORTHSTAR_DATABASE_URL (the
canonical DSN environment variable) and these tests create and use a
scratch database named northstar_m0_test. Skipped when the variable is
unset. See README.md for the exact local setup.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

DSN_ENV = "NORTHSTAR_DATABASE_URL"
TEST_DB = "northstar_m0_test"
AUDIT = "2026-08"
SNAPSHOT = datetime.fromisoformat("2026-09-02T08:15:00+07:00")
CLOSE = datetime.fromisoformat("2026-09-07T17:30:00+07:00")
HORIZON = datetime.fromisoformat("2026-09-08T09:00:00+07:00")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DSN_ENV),
    reason=f"set {DSN_ENV} to run the PostgreSQL acceptance tests",
)


@pytest.fixture(scope="module")
def pg(gen, config, tmp_path_factory):
    import psycopg
    from psycopg import conninfo

    base_dsn = os.environ[DSN_ENV]
    with psycopg.connect(base_dsn, autocommit=True) as conn:
        conn.execute(f"drop database if exists {TEST_DB}")
        conn.execute(f"create database {TEST_DB}")
    # WIB session default, so ::date casts follow SC-5 and survive the
    # transaction rollbacks the error helpers issue
    dsn = conninfo.make_conninfo(
        base_dsn, dbname=TEST_DB, options="-c timezone=Asia/Jakarta"
    )
    out1 = tmp_path_factory.mktemp("northstar_run1")
    out2 = tmp_path_factory.mktemp("northstar_run2")
    summary1 = gen.run("smoke", dsn=dsn, out_root=out1, quiet=True)
    # regenerate from scratch into the same target: proves idempotent
    # loading and byte-identical outputs (assignment sections 9 / 10.5)
    summary2 = gen.run("smoke", dsn=dsn, out_root=out2, quiet=True)
    conn = psycopg.connect(dsn)
    yield SimpleNamespace(
        conn=conn, dsn=dsn, out1=out1, out2=out2,
        summary1=summary1, summary2=summary2, config=config,
    )
    conn.close()


def one(pg, sql, params=None):
    try:
        with pg.conn.cursor() as cur:
            cur.execute(sql, params or {})
            return cur.fetchone()
    except Exception:
        pg.conn.rollback()
        raise


def all_rows(pg, sql, params=None):
    try:
        with pg.conn.cursor() as cur:
            cur.execute(sql, params or {})
            return cur.fetchall()
    except Exception:
        pg.conn.rollback()
        raise


# ---------------------------------------------------------------------------
# Independent SQL recomputation of every reconciliation quantity
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def q(pg):
    """Audit-period quantities recomputed straight from core.* by this
    test's own SQL."""
    g_post, k_post, freight = one(pg, """
        select
          coalesce(sum(il.net_amount) filter (where il.line_type = 'merchandise'), 0),
          coalesce(sum(il.qty * il.unit_cost_actual) filter (where il.line_type = 'merchandise'), 0),
          coalesce(sum(il.net_amount) filter (where il.line_type = 'freight'), 0)
        from core.invoice_lines il
        join core.invoices i on i.invoice_id = il.invoice_id
        where i.accounting_period = %(p)s
    """, {"p": AUDIT})
    c = one(pg, """
        select
          coalesce(sum(merchandise_amount), 0),
          coalesce(sum(merchandise_amount) filter (where created_at <= %(snap)s), 0),
          coalesce(sum(merchandise_amount) filter (where created_at > %(snap)s), 0),
          coalesce(sum(vat_amount) filter (where created_at <= %(snap)s), 0),
          coalesce(sum(vat_amount) filter (where created_at > %(snap)s), 0),
          coalesce(sum(cogs_reversal_amount), 0),
          coalesce(sum(cogs_reversal_amount) filter (where created_at <= %(snap)s), 0),
          coalesce(sum(cogs_reversal_amount) filter (where created_at > %(snap)s), 0),
          coalesce(sum(total_amount), 0)
        from core.credit_notes
        where accounting_period = %(p)s
    """, {"p": AUDIT, "snap": SNAPSHOT})
    d1, k1 = one(pg, """
        select coalesce(sum(il.net_amount), 0), coalesce(sum(il.qty * il.unit_cost_actual), 0)
        from core.invoice_lines il
        join core.invoices i on i.invoice_id = il.invoice_id
        join core.orders o on o.order_id = i.order_id
        where il.line_type = 'merchandise'
          and to_char(o.delivery_date, 'YYYY-MM') = %(p)s
          and i.accounting_period <> %(p)s
    """, {"p": AUDIT})
    d2, k2 = one(pg, """
        select coalesce(sum(il.net_amount), 0), coalesce(sum(il.qty * il.unit_cost_actual), 0)
        from core.invoice_lines il
        join core.invoices i on i.invoice_id = il.invoice_id
        join core.orders o on o.order_id = i.order_id
        where il.line_type = 'merchandise'
          and to_char(o.delivery_date, 'YYYY-MM') = '2026-07'
          and i.accounting_period = %(p)s
    """, {"p": AUDIT})
    dsv, k_std = one(pg, """
        select
          coalesce(sum(oi.line_net_amount), 0),
          coalesce(sum(oi.qty * (
            select h.unit_cost from core.product_cost_history h
            where h.product_id = oi.product_id
              and h.cost_type = 'standard'
              and h.effective_from <= o.delivery_date
            order by h.effective_from desc limit 1
          )), 0)
        from core.orders o
        join core.order_items oi on oi.order_id = o.order_id
        where o.status = 'delivered'
          and to_char(o.delivery_date, 'YYYY-MM') = %(p)s
    """, {"p": AUDIT})
    ns = SimpleNamespace(
        g_post=int(g_post), k_post=int(k_post), freight=int(freight),
        c_period=int(c[0]), c_seen=int(c[1]), c_late=int(c[2]),
        vat_seen=int(c[3]), vat_late=int(c[4]),
        r_period=int(c[5]), r_early=int(c[6]), r_late=int(c[7]),
        c_total_amount=int(c[8]),
        d1=int(d1), k1=int(k1), d2=int(d2), k2=int(k2),
        dsv=int(dsv), k_std=int(k_std),
    )
    ns.rnmr = ns.g_post - ns.c_period
    ns.arc = ns.k_post - ns.r_period
    ns.fgm = ns.rnmr - ns.arc
    ns.cm = ns.dsv - ns.k_std
    ns.k_act = ns.k_post + ns.k1 - ns.k2
    ns.br = ns.dsv - (ns.c_seen + ns.vat_seen)
    ns.bgm = ns.br - ns.k_std
    return ns


# ---------------------------------------------------------------------------
# Schema and documentation pattern
# ---------------------------------------------------------------------------


def test_required_objects_exist(pg):
    tables = {
        (s, t)
        for s, t in all_rows(pg, """
            select table_schema, table_name from information_schema.tables
            where table_schema in ('core', 'finance', 'analytics', 'management')
        """)
    }
    required = {
        ("core", "customers"), ("core", "products"), ("core", "product_cost_history"),
        ("core", "orders"), ("core", "order_items"), ("core", "invoices"),
        ("core", "invoice_lines"), ("core", "payments"), ("core", "returns"),
        ("core", "return_items"), ("core", "credit_notes"),
        ("finance", "monthly_pnl_extract"),
        ("analytics", "delivered_sales"), ("analytics", "etl_job_runs"),
        ("analytics", "sales_dashboard_monthly"),
        ("management", "board_kpi_monthly"),
    }
    assert required <= tables
    # no registry-style objects stand in for organizational knowledge
    names = {t for _, t in tables}
    assert not names & {"metric_definitions", "dataset_registry", "kpi_catalog"}


def test_binding_columns_exist(pg):
    expected = {
        ("finance", "monthly_pnl_extract"): {
            "accounting_period", "gross_invoiced_merchandise",
            "credit_notes_merchandise", "net_merchandise_revenue",
            "freight_income", "cogs_invoiced", "cogs_reversed",
            "recognized_cogs", "gross_margin", "gross_margin_pct",
            "closed_at", "prepared_by",
        },
        ("management", "board_kpi_monthly"): {
            "period", "kpi", "value", "generated_at", "source_job",
        },
        ("analytics", "delivered_sales"): {
            "delivery_date", "order_id", "order_item_id", "customer_id",
            "sales_region", "product_id", "qty", "gross_amount",
            "discount_amount", "net_amount", "std_unit_cost",
            "std_cost_amount", "loaded_at",
        },
        ("analytics", "sales_dashboard_monthly"): {
            "month", "sales_region", "revenue", "cogs_std", "margin",
            "margin_pct", "returned_value", "order_count",
        },
        ("analytics", "etl_job_runs"): {
            "run_id", "job_name", "run_for_period", "started_at",
            "completed_at", "status", "rows_written",
        },
    }
    for (schema, table), cols in expected.items():
        present = {
            r[0] for r in all_rows(pg, """
                select column_name from information_schema.columns
                where table_schema = %s and table_name = %s
            """, (schema, table))
        }
        assert cols <= present, f"{schema}.{table} missing {cols - present}"


def test_comment_fragmentation_pattern(pg):
    """SC-12.1: comments exist exactly where the contract places them, and
    the dashboard revenue comment is the stale net-of-returns text."""
    def table_comment(schema, table):
        return one(pg, """
            select obj_description(format('%%I.%%I', %s::text, %s::text)::regclass)
        """, (schema, table))[0]

    def column_comment(schema, table, column):
        return one(pg, """
            select col_description(format('%%I.%%I', %s::text, %s::text)::regclass,
                (select ordinal_position::int from information_schema.columns
                 where table_schema = %s and table_name = %s and column_name = %s))
        """, (schema, table, schema, table, column))[0]

    for schema, table in [("core", "orders"), ("core", "invoices"),
                          ("core", "credit_notes"), ("core", "product_cost_history"),
                          ("finance", "monthly_pnl_extract"),
                          ("analytics", "delivered_sales")]:
        assert table_comment(schema, table), f"comment missing on {schema}.{table}"
    for schema, table in [("core", "returns"), ("core", "return_items"),
                          ("core", "payments"), ("management", "board_kpi_monthly")]:
        assert table_comment(schema, table) is None, f"unexpected comment on {schema}.{table}"
    assert "period of invoice_date" in column_comment("core", "invoices", "accounting_period")
    assert "credited by its close" in column_comment("core", "credit_notes", "accounting_period")
    stale = column_comment("analytics", "sales_dashboard_monthly", "revenue")
    assert "net of discounts and returns" in stale  # stale: the view is gross


# ---------------------------------------------------------------------------
# Surface reproduction (assignment section 10.3: the disagreement is real)
# ---------------------------------------------------------------------------


def test_finance_extract_reproducible_from_core(pg, q):
    row = one(pg, """
        select gross_invoiced_merchandise, credit_notes_merchandise,
               net_merchandise_revenue, freight_income, cogs_invoiced,
               cogs_reversed, recognized_cogs, gross_margin,
               gross_margin_pct, closed_at, prepared_by
        from finance.monthly_pnl_extract where accounting_period = %s
    """, (AUDIT,))
    assert row is not None
    assert row[0] == q.g_post
    assert row[1] == q.c_period
    assert row[2] == q.rnmr
    assert row[3] == q.freight
    assert row[4] == q.k_post
    assert row[5] == q.r_period
    assert row[6] == q.arc
    assert row[7] == q.fgm
    expected_pct = (Decimal(q.fgm) * 100 / Decimal(q.rnmr)).quantize(Decimal("0.01"))
    assert row[8] == expected_pct
    assert row[9] == CLOSE
    assert row[10] == "DA"


def test_finance_extract_reproducible_for_every_period(pg):
    """Finance logic is stable, so re-deriving every closed period from
    core reproduces the whole extract -- the recurring close pattern."""
    mismatches = all_rows(pg, """
        with derived as (
          select i.accounting_period as p,
                 sum(il.net_amount) filter (where il.line_type = 'merchandise') as gross,
                 sum(il.qty * il.unit_cost_actual)
                     filter (where il.line_type = 'merchandise') as cogs
          from core.invoice_lines il
          join core.invoices i on i.invoice_id = il.invoice_id
          group by 1
        ), credits as (
          select accounting_period as p,
                 sum(merchandise_amount) as merch,
                 sum(cogs_reversal_amount) as cogs_rev
          from core.credit_notes group by 1
        )
        select f.accounting_period
        from finance.monthly_pnl_extract f
        join derived d on d.p = f.accounting_period
        left join credits c on c.p = f.accounting_period
        where f.net_merchandise_revenue <> d.gross - coalesce(c.merch, 0)
           or f.recognized_cogs <> d.cogs - coalesce(c.cogs_rev, 0)
    """)
    assert mismatches == []
    n = one(pg, "select count(*) from finance.monthly_pnl_extract")[0]
    assert n == 36  # every closed period of the 36-month history


def test_sales_dashboard_reproducible_from_core(pg, q):
    revenue, cogs_std, margin = one(pg, """
        select coalesce(sum(revenue), 0), coalesce(sum(cogs_std), 0),
               coalesce(sum(margin), 0)
        from analytics.sales_dashboard_monthly where month = %s
    """, (date(2026, 8, 1),))
    assert revenue == q.dsv
    assert cogs_std == q.k_std
    assert margin == q.cm
    # returned_value is informational, received-month based, and never
    # netted from revenue
    returned = one(pg, """
        select coalesce(sum(returned_value), 0)
        from analytics.sales_dashboard_monthly where month = %s
    """, (date(2026, 8, 1),))[0]
    exp_returned = one(pg, """
        select coalesce(sum((ri.qty_returned * il.net_amount + il.qty / 2) / il.qty), 0)
        from core.returns r
        join core.return_items ri on ri.return_id = r.return_id
        join core.invoice_lines il on il.invoice_line_id = ri.invoice_line_id
        where to_char(r.received_date, 'YYYY-MM') = %s
    """, (AUDIT,))[0]
    assert returned == exp_returned
    assert returned > 0


def test_fact_matches_nightly_refresh_sql_for_audit_month(pg, gen):
    """Replaying the committed evidence refresh statement for every August
    delivery date reproduces the stored fact rows exactly."""
    refresh_statements, _ = gen.sales_dashboard_parts()
    delete_sql, insert_sql = refresh_statements
    insert_sql = insert_sql.replace(
        "insert into analytics.delivered_sales (",
        "insert into _replay_fact (",
    )
    days = [r[0] for r in all_rows(pg, """
        select distinct delivery_date from core.orders
        where status = 'delivered' and to_char(delivery_date, 'YYYY-MM') = %s
        order by 1
    """, (AUDIT,))]
    with pg.conn.cursor() as cur:
        cur.execute("""
            create temp table _replay_fact
            (like analytics.delivered_sales including defaults)
        """)
        for d in days:
            loaded_at = one(pg, """
                select loaded_at from analytics.delivered_sales
                where delivery_date = %s limit 1
            """, (d,))[0]
            cur.execute(insert_sql, {"run_date": d, "loaded_at": loaded_at})
        diff = cur.execute("""
            (table _replay_fact except
             (select * from analytics.delivered_sales
              where to_char(delivery_date, 'YYYY-MM') = %(p)s))
            union all
            ((select * from analytics.delivered_sales
              where to_char(delivery_date, 'YYYY-MM') = %(p)s)
             except table _replay_fact)
        """, {"p": AUDIT}).fetchall()
        cur.execute("drop table _replay_fact")
    pg.conn.rollback()
    assert diff == []
    assert "delete from analytics.delivered_sales" in delete_sql.lower()


def test_board_snapshot_reproducible_only_with_snapshot_restriction(pg, q):
    stored = {
        kpi: (value, generated_at)
        for kpi, value, generated_at in all_rows(pg, """
            select kpi, value, generated_at from management.board_kpi_monthly
            where period = %s
        """, (AUDIT,))
    }
    assert set(stored) == {"Revenue", "Gross Margin", "Gross Margin %"}
    assert stored["Revenue"][1] == SNAPSHOT
    # reproduction with the created_at <= generated_at restriction (SC-9.3)
    assert stored["Revenue"][0] == q.br
    assert stored["Gross Margin"][0] == q.bgm
    expected_pct = (Decimal(q.bgm) * 100 / Decimal(q.br)).quantize(Decimal("0.1"))
    assert stored["Gross Margin %"][0] == expected_pct
    # horizon-state rerun (no restriction) must NOT reproduce the snapshot:
    # that is the freshness finding
    horizon_rev = q.dsv - q.c_total_amount
    assert horizon_rev != stored["Revenue"][0]
    assert stored["Revenue"][0] - horizon_rev == q.c_late + q.vat_late


def test_board_snapshots_exist_for_every_period_as_recurring_pattern(pg):
    periods = all_rows(pg, """
        select period, count(*) from management.board_kpi_monthly
        group by 1 order by 1
    """)
    assert len(periods) == 36
    assert all(n == 3 for _, n in periods)
    # each snapshot precedes its Finance close: the recurring early pattern
    early = one(pg, """
        select count(*) from management.board_kpi_monthly b
        join finance.monthly_pnl_extract f on f.accounting_period = b.period
        where b.generated_at >= f.closed_at
    """)[0]
    assert early == 0


# ---------------------------------------------------------------------------
# Reconciliation, materiality, ground truth
# ---------------------------------------------------------------------------


def test_bridges_hold_exactly(pg, q):
    assert q.dsv == q.g_post + q.d1 - q.d2
    assert q.c_period == q.c_seen + q.c_late
    assert q.r_period == q.r_early + q.r_late
    assert q.rnmr + (q.d1 - q.d2) + q.c_period == q.dsv
    assert q.rnmr + (q.d1 - q.d2) + q.c_late - q.vat_seen == q.br
    assert (
        q.fgm + (q.dsv - q.rnmr) - (q.k1 - q.k2)
        - (q.k_std - q.k_act) - q.r_period == q.cm
    )
    assert (
        q.fgm + (q.br - q.rnmr) - (q.k1 - q.k2)
        - (q.k_std - q.k_act) - q.r_late - q.r_early == q.bgm
    )


def test_credit_split_is_one_shared_predicate(pg):
    """C_late/R_late and C_seen/R_early come from the same created_at <=
    generated_at split (SC-18.5), and it coincides with the posting-date
    description in SC-10.1."""
    bad = one(pg, """
        select count(*) from core.credit_notes
        where accounting_period = %(p)s
          and ((created_at <= %(snap)s and posting_date > '2026-09-01')
            or (created_at > %(snap)s
                and posting_date not between '2026-09-02' and '2026-09-04'))
    """, {"p": AUDIT, "snap": SNAPSHOT})[0]
    assert bad == 0


def test_materiality_sc14_from_database(pg, q, config):
    mat = config["scenario"]["materiality"]
    lo, hi = mat["c_period_pct_of_rnmr"]
    assert lo <= 100 * q.c_period / q.rnmr <= hi
    assert q.c_late / q.c_period >= mat["c_late_min_share_of_c_period"]
    assert 100 * q.d1 / q.rnmr >= mat["d1_min_pct_of_rnmr"]
    assert 100 * q.d2 / q.rnmr >= mat["d2_min_pct_of_rnmr"]
    assert 100 * abs(q.k_std - q.k_act) / q.k_act >= mat["cost_basis_min_pct_of_k_act"]
    min_rev = mat["revenue_pairwise_min_pct_of_rnmr"] / 100 * q.rnmr
    assert abs(q.rnmr - q.dsv) >= min_rev
    assert abs(q.rnmr - q.br) >= min_rev
    assert abs(q.dsv - q.br) >= min_rev
    assert len({q.rnmr, q.dsv, q.br}) == 3
    fgm_pct, cm_pct, bgm_pct = (
        100 * q.fgm / q.rnmr, 100 * q.cm / q.dsv, 100 * q.bgm / q.br,
    )
    min_pp = mat["margin_pairwise_min_pp"]
    assert abs(fgm_pct - cm_pct) >= min_pp
    assert abs(fgm_pct - bgm_pct) >= min_pp
    assert abs(cm_pct - bgm_pct) >= min_pp
    lo, hi = mat["fgm_pct_of_rnmr_band"]
    assert lo <= fgm_pct <= hi


def test_ground_truth_matches_independent_recomputation(pg, q, config):
    manifest = json.loads(
        (pg.out1 / config["generation"]["ground_truth_dir"]
         / "northstar-2026-08-revenue-margin.json").read_text()
    )
    assert manifest["profile"] == "smoke"
    assert manifest["audit_period"] == AUDIT
    s = manifest["surfaces"]
    assert s["finance"]["reported"]["revenue"] == q.rnmr
    assert s["finance"]["reported"]["gross_margin"] == q.fgm
    assert s["sales"]["reported"]["revenue"] == q.dsv
    assert s["sales"]["reported"]["gross_margin"] == q.cm
    assert s["board"]["reported"]["revenue"] == q.br
    assert s["board"]["reported"]["gross_margin"] == q.bgm
    i = manifest["intermediate"]
    assert i["g_post"] == q.g_post and i["c_period"] == q.c_period
    assert i["c_late"] == q.c_late and i["d1"] == q.d1 and i["d2"] == q.d2
    assert i["k_std"] == q.k_std and i["k_act"] == q.k_act
    assert i["r_period"] == q.r_period
    assert i["r_early"] == q.r_early and i["r_late"] == q.r_late
    for name, delta in [
        ("revenue_finance_to_sales", q.dsv - q.rnmr),
        ("revenue_finance_to_board", q.br - q.rnmr),
        ("gross_margin_finance_to_sales", q.cm - q.fgm),
        ("gross_margin_finance_to_board", q.bgm - q.fgm),
    ]:
        assert sum(x["amount"] for x in manifest["bridges"][name]) == delta
    # decision-context relativity: no universal true revenue anywhere
    text = json.dumps(manifest)
    assert "true_revenue" not in text
    assert manifest["recommended_basis"]["board_financial_performance_pnl"] == "finance"
    assert manifest["recommended_basis"]["sales_commercial_performance"] == "sales"
    assert len(manifest["supporting_findings"]) == 2


def test_no_leakage_in_database_or_evidence(pg, config):
    from test_scenario_sources import assert_clean

    names = all_rows(pg, """
        select table_schema || '.' || table_name || '.' || column_name
        from information_schema.columns
        where table_schema in ('core', 'finance', 'analytics', 'management')
    """)
    for (name,) in names:
        assert_clean(name, "object name")
    comments = all_rows(pg, """
        select coalesce(obj_description(c.oid), '') || ' ' ||
               coalesce(string_agg(d.description, ' '), '')
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        left join pg_description d on d.objoid = c.oid and d.objsubid > 0
        where n.nspname in ('core', 'finance', 'analytics', 'management')
        group by c.oid
    """)
    for (text,) in comments:
        assert_clean(text, "database comment")
    evidence_dir = pg.out1 / config["generation"]["data_dir"] / "evidence"
    files = sorted(p.name for p in evidence_dir.iterdir())
    assert files == [
        "august_board_pack.csv", "board_pack.sql", "board_pack_handover.md",
        "finance_close_notes.md", "finance_revenue.sql",
        "sales_dashboard.sql", "sales_dashboard_notes.md",
    ]  # exactly the seven SC-12.2 artifacts
    for p in evidence_dir.iterdir():
        assert_clean(p.name, "evidence file name")
        assert_clean(p.read_text(encoding="utf-8"), p.name)


def test_circulated_pack_csv_matches_board_surface(pg, config):
    evidence_dir = pg.out1 / config["generation"]["data_dir"] / "evidence"
    lines = (evidence_dir / "august_board_pack.csv").read_text().strip().split("\n")
    assert lines[0] == "period,kpi,value,generated_at"
    csv_values = {}
    for line in lines[1:]:
        p, kpi, value, generated_at = line.split(",")
        assert p == AUDIT
        assert generated_at == SNAPSHOT.isoformat()
        csv_values[kpi] = Decimal(value)
    stored = dict(all_rows(pg, """
        select kpi, value from management.board_kpi_monthly where period = %s
    """, (AUDIT,)))
    assert csv_values == {k: Decimal(v) for k, v in stored.items()}


def test_job_log_freshness_evidence(pg):
    assert one(pg, "select count(*) from analytics.etl_job_runs where status <> 'success'")[0] == 0
    # the fact's loaded_at is exactly the completion instant of the nightly
    # run that loaded that delivery date
    bad = one(pg, """
        select count(*) from analytics.delivered_sales ds
        where not exists (
          select 1 from analytics.etl_job_runs r
          where r.job_name = 'refresh_delivered_sales'
            and r.completed_at = ds.loaded_at
            and r.completed_at::date = ds.delivery_date + 1
        )
    """)[0]
    assert bad == 0
    # board job completion instants match the stored snapshots
    bad = one(pg, """
        select count(*) from management.board_kpi_monthly b
        where not exists (
          select 1 from analytics.etl_job_runs r
          where r.job_name = 'board_pack_monthly'
            and r.run_for_period = b.period
            and r.completed_at = b.generated_at
        )
    """)[0]
    assert bad == 0


def test_lifecycle_constraints_in_database(pg):
    checks = [
        # delivered orders have delivery dates; cancelled never do
        "select count(*) from core.orders where status = 'delivered' and delivery_date is null",
        "select count(*) from core.orders where status = 'cancelled' and (delivery_date is not null or cancelled_date is null)",
        "select count(*) from core.orders where status = 'open' and (delivery_date is not null or cancelled_date is not null)",
        # chronology
        "select count(*) from core.orders where delivery_date <= order_date",
        "select count(*) from core.invoices i join core.orders o on o.order_id = i.order_id where i.invoice_date < o.delivery_date",
        "select count(*) from core.returns r join core.invoices i on i.invoice_id = r.invoice_id join core.orders o on o.order_id = i.order_id where r.received_date <= o.delivery_date",
        "select count(*) from core.credit_notes cn join core.returns r on r.return_id = cn.return_id where cn.posting_date <= r.received_date",
        # accounting periods follow their dates
        "select count(*) from core.invoices where accounting_period <> to_char(invoice_date, 'YYYY-MM')",
        "select count(*) from core.credit_notes cn join core.returns r on r.return_id = cn.return_id where cn.accounting_period <> to_char(r.received_date, 'YYYY-MM')",
        # status coherence
        "select count(*) from core.returns r where status = 'credited' and not exists (select 1 from core.credit_notes cn where cn.return_id = r.return_id)",
        "select count(*) from core.returns r where status = 'received' and exists (select 1 from core.credit_notes cn where cn.return_id = r.return_id)",
        # returned quantity never exceeds the invoiced quantity
        "select count(*) from core.return_items ri join core.invoice_lines il on il.invoice_line_id = ri.invoice_line_id where ri.qty_returned > il.qty or ri.qty_returned < 1",
        # horizon: no event date or system timestamp after observation
        f"select count(*) from core.orders where created_at > '{HORIZON.isoformat()}' or order_date > '2026-09-08' or delivery_date > '2026-09-08'",
        f"select count(*) from core.credit_notes where created_at > '{HORIZON.isoformat()}'",
        f"select count(*) from analytics.etl_job_runs where completed_at > '{HORIZON.isoformat()}'",
    ]
    for sql in checks:
        assert one(pg, sql)[0] == 0, sql
    # an open-order tail exists at the horizon (SC-6)
    assert one(pg, "select count(*) from core.orders where status = 'open'")[0] > 0


def test_deterministic_regeneration_byte_identical(pg, config):
    assert pg.summary1["fingerprint"] == pg.summary2["fingerprint"]
    for rel in [config["generation"]["data_dir"] + "/evidence",
                config["generation"]["ground_truth_dir"]]:
        d1, d2 = pg.out1 / rel, pg.out2 / rel
        files1 = sorted(p.name for p in d1.iterdir())
        files2 = sorted(p.name for p in d2.iterdir())
        assert files1 == files2
        for name in files1:
            assert (d1 / name).read_bytes() == (d2 / name).read_bytes(), name
