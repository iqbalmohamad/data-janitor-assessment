"""Contract-level M0 verification, using core rows rather than literal answers."""

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from benchmark.generate import (COMMENTS, ROOT, SURFACE_PARAMETERS, TABLES, bind, calendar, columns,
                                generate_core, instant, load_config, period, stamp, statements, surface_sql)
from benchmark.load_duckdb import load
from benchmark.scenario.reconcile import inspect_evidence, verify_scenario, manifest


def zero(conn, sql, params=None):
    assert conn.execute(sql, params).fetchone()[0] == 0, sql


def hashes(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob("*")) if p.is_file()}


def test_schema_and_configured_counts(dataset):
    conn, cfg, profile, data, _, truth, _ = dataset
    actual = set(conn.execute("SELECT table_schema,table_name FROM information_schema.tables WHERE table_schema IN ('core','finance','analytics','management')").fetchall())
    expected = {("core", t) for t in TABLES} | {
        ("finance", "monthly_pnl_extract"), ("analytics", "delivered_sales"),
        ("analytics", "sales_dashboard_monthly"), ("analytics", "etl_job_runs"),
        ("management", "board_kpi_monthly")}
    assert actual == expected
    for table, count in cfg["scale"][profile].items():
        assert conn.execute(f"SELECT COUNT(*) FROM core.{table}").fetchone()[0] == count
    for table in TABLES:
        assert (data / "core" / f"{table}.csv").exists()
        assert "created_at" in columns(table)


def test_horizon_and_core_causality(dataset):
    conn, cfg, *_ = dataset
    horizon = instant(cfg["scenario"]["observation_at"])
    fields = {"products": [], "product_cost_history": ["effective_from"], "customers": [],
              "orders": ["order_date", "requested_delivery_date", "delivery_date", "cancelled_date"],
              "order_items": [], "invoices": ["invoice_date"], "invoice_lines": [],
              "payments": ["payment_date"], "returns": ["received_date"], "return_items": [],
              "credit_notes": ["posting_date"]}
    for table, dates in fields.items():
        zero(conn, f"SELECT COUNT(*) FROM core.{table} WHERE created_at>%s OR created_at IS NULL", (horizon,))
        for field in dates:
            zero(conn, f"SELECT COUNT(*) FROM core.{table} WHERE {field}>%s", (horizon.date(),))
    for table, field in (("orders", "order_date"), ("invoices", "invoice_date"), ("payments", "payment_date"),
                         ("returns", "received_date"), ("credit_notes", "posting_date"), ("product_cost_history", "effective_from")):
        zero(conn, f"SELECT COUNT(*) FROM core.{table} WHERE CAST(created_at AS DATE)<{field}")
    for child, parent, key in (("order_items", "orders", "order_id"), ("invoice_lines", "invoices", "invoice_id"),
                               ("return_items", "returns", "return_id"), ("credit_notes", "returns", "return_id"),
                               ("product_cost_history", "products", "product_id")):
        zero(conn, f"SELECT COUNT(*) FROM core.{child} c JOIN core.{parent} p USING({key}) WHERE c.created_at<p.created_at")
    zero(conn, """SELECT COUNT(*) FROM core.orders WHERE status NOT IN ('open','cancelled','delivered')
      OR (status='delivered' AND (delivery_date IS NULL OR delivery_date<=order_date OR cancelled_date IS NOT NULL))
      OR (status='cancelled' AND (cancelled_date IS NULL OR delivery_date IS NOT NULL OR cancelled_date<order_date))
      OR (status='open' AND (delivery_date IS NOT NULL OR cancelled_date IS NOT NULL))
      OR requested_delivery_date<order_date""")
    zero(conn, """SELECT COUNT(*) FROM core.orders o LEFT JOIN core.invoices i USING(order_id)
      WHERE (o.status='delivered' AND i.invoice_id IS NULL) OR (o.status<>'delivered' AND i.invoice_id IS NOT NULL)
      OR i.customer_id<>o.customer_id OR i.invoice_date<o.delivery_date
      OR i.accounting_period<>SUBSTRING(CAST(i.invoice_date AS VARCHAR),1,7)""")
    rows = conn.execute("SELECT delivery_date,invoice_date FROM core.orders JOIN core.invoices USING(order_id)").fetchall()
    for delivered, invoiced in rows:
        assert delivered.weekday() < 6 and invoiced.weekday() < 5
        lag = sum((delivered + timedelta(days=i)).weekday() < 5 for i in range(1, (invoiced-delivered).days + 1))
        assert 0 <= lag <= 3
    assert conn.execute("SELECT COUNT(*) FROM core.orders WHERE status='open'").fetchone()[0] > 0
    zero(conn, """SELECT COUNT(*) FROM core.returns r JOIN core.invoices i USING(invoice_id)
      JOIN core.orders o USING(order_id) WHERE r.customer_id<>i.customer_id OR r.received_date<i.invoice_date
      OR r.received_date<=o.delivery_date OR r.received_date>o.delivery_date+INTERVAL '45 days'""")
    zero(conn, """SELECT COUNT(*) FROM core.return_items ri JOIN core.returns r USING(return_id)
      JOIN core.invoice_lines l USING(invoice_line_id) WHERE r.invoice_id<>l.invoice_id
      OR l.line_type<>'merchandise' OR ri.qty_returned<=0 OR ri.qty_returned>l.qty""")
    zero(conn, """SELECT COUNT(*) FROM core.returns r LEFT JOIN core.credit_notes n USING(return_id)
      WHERE (r.status='credited' AND n.credit_note_id IS NULL) OR (r.status='received' AND n.credit_note_id IS NOT NULL)
      OR n.invoice_id<>r.invoice_id OR n.customer_id<>r.customer_id OR n.posting_date<=r.received_date
      OR n.accounting_period<>SUBSTRING(CAST(r.received_date AS VARCHAR),1,7)""")
    zero(conn, """SELECT COUNT(*) FROM core.payments p JOIN core.invoices i USING(invoice_id)
      WHERE p.payment_date<i.invoice_date OR p.amount<=0""")
    zero(conn, """SELECT COUNT(*) FROM (SELECT p.invoice_id,SUM(p.amount) AS paid,MAX(i.total_amount) AS billed
      FROM core.payments p JOIN core.invoices i USING(invoice_id) GROUP BY p.invoice_id) x WHERE paid>billed""")


def test_amounts_and_cost_history(dataset):
    conn, cfg, *_ = dataset
    zero(conn, """SELECT COUNT(*) FROM core.order_items WHERE line_net_amount<>ROUND(qty*unit_price*(1-discount_pct))
      OR qty<=0 OR unit_price<=0 OR discount_pct<0 OR discount_pct>=1""")
    zero(conn, """SELECT COUNT(*) FROM core.invoice_lines l JOIN core.order_items oi USING(order_item_id)
      WHERE l.line_type<>'merchandise' OR l.product_id<>oi.product_id OR l.qty<>oi.qty
      OR l.net_amount<>oi.line_net_amount OR l.discount_amount<>oi.qty*oi.unit_price-oi.line_net_amount""")
    zero(conn, """SELECT COUNT(*) FROM core.invoice_lines WHERE (line_type='freight' AND
      (product_id IS NOT NULL OR order_item_id IS NOT NULL OR unit_cost_actual IS NOT NULL))
      OR vat_amount<>ROUND(net_amount*%s)""", (Decimal(str(cfg["scenario"]["vat_rate"])),))
    zero(conn, """SELECT COUNT(*) FROM core.invoices i JOIN (
      SELECT invoice_id,SUM(CASE WHEN line_type='merchandise' THEN net_amount ELSE 0 END) AS merch,
        SUM(CASE WHEN line_type='freight' THEN net_amount ELSE 0 END) AS freight,SUM(vat_amount) AS vat
      FROM core.invoice_lines GROUP BY invoice_id) l USING(invoice_id)
      WHERE i.merchandise_amount<>l.merch OR i.freight_amount<>l.freight OR i.vat_amount<>l.vat
      OR i.total_amount<>l.merch+l.freight+l.vat""")
    zero(conn, """SELECT COUNT(*) FROM core.credit_notes n JOIN (
      SELECT return_id,SUM(ri.qty_returned*CAST(l.net_amount AS NUMERIC)/l.qty) AS merch,
        SUM(ri.qty_returned*l.unit_cost_actual) AS cost
      FROM core.return_items ri JOIN core.invoice_lines l USING(invoice_line_id) GROUP BY return_id
      ) r USING(return_id) WHERE n.merchandise_amount<>r.merch OR n.cogs_reversal_amount<>r.cost
        OR n.vat_amount<>ROUND(r.merch*%s) OR n.total_amount<>n.merchandise_amount+n.vat_amount""",
         (Decimal(str(cfg["scenario"]["vat_rate"])),))
    zero(conn, """SELECT COUNT(*) FROM core.invoice_lines l JOIN core.invoices i USING(invoice_id)
      JOIN core.orders o USING(order_id) JOIN core.product_cost_history h ON h.product_id=l.product_id
      AND h.cost_type='actual' AND h.effective_from=(SELECT MAX(x.effective_from) FROM core.product_cost_history x
        WHERE x.product_id=l.product_id AND x.cost_type='actual' AND x.effective_from<=o.delivery_date)
      WHERE l.line_type='merchandise' AND l.unit_cost_actual<>h.unit_cost""")
    zero(conn, """SELECT COUNT(*) FROM core.products p JOIN core.product_cost_history h USING(product_id)
      WHERE h.cost_type='standard' AND h.effective_from=(SELECT MAX(x.effective_from) FROM core.product_cost_history x
      WHERE x.product_id=p.product_id AND x.cost_type='standard') AND p.standard_cost<>h.unit_cost""")
    p = cfg["scenario"]["audit_period"]
    total, changed = conn.execute("""WITH changes AS (
      SELECT product_id,effective_from,unit_cost,
        LAG(unit_cost) OVER (PARTITION BY product_id ORDER BY effective_from) AS previous_cost
      FROM core.product_cost_history WHERE cost_type='actual')
      SELECT COUNT(DISTINCT l.product_id),COUNT(DISTINCT h.product_id)
      FROM core.orders o JOIN core.order_items l USING(order_id)
      LEFT JOIN changes h ON h.product_id=l.product_id AND h.unit_cost<>h.previous_cost
        AND SUBSTRING(CAST(h.effective_from AS VARCHAR),1,7)=%s
      WHERE SUBSTRING(CAST(o.delivery_date AS VARCHAR),1,7)=%s""", (p, p)).fetchone()
    assert .15 <= changed/total <= .25
    zero(conn, "SELECT COUNT(*) FROM core.product_cost_history WHERE cost_type='standard' AND SUBSTRING(CAST(effective_from AS VARCHAR),6,5) NOT IN ('01-01','07-01')")
    zero(conn, """SELECT COUNT(*) FROM analytics.delivered_sales d JOIN core.product_cost_history h
      ON h.product_id=d.product_id AND h.cost_type='standard'
      AND h.effective_from=(SELECT MAX(x.effective_from) FROM core.product_cost_history x
        WHERE x.product_id=d.product_id AND x.cost_type='standard' AND x.effective_from<=d.delivery_date)
      WHERE d.std_unit_cost<>h.unit_cost OR d.std_cost_amount<>d.qty*h.unit_cost""")
    zero(conn, """SELECT COUNT(*) FROM core.invoice_lines l JOIN core.invoices i USING(invoice_id)
      JOIN core.orders o USING(order_id) JOIN analytics.delivered_sales d USING(order_item_id)
      WHERE l.line_type='merchandise' AND (ABS(1.0*l.unit_cost_actual/d.std_unit_cost-1)<0.019
        OR ABS(1.0*l.unit_cost_actual/d.std_unit_cost-1)>0.081)""")


def test_history_snapshot_and_jobs(dataset):
    conn, cfg, *_ = dataset
    horizon = instant(cfg["scenario"]["observation_at"])
    finance = conn.execute("SELECT * FROM finance.monthly_pnl_extract ORDER BY accounting_period").fetchall()
    historical = conn.execute("SELECT * FROM management.board_kpi_monthly ORDER BY period,kpi").fetchall()
    assert len(finance) == len(calendar(cfg)) and len(historical) == 3*len(finance)
    for index, (month, board, close) in enumerate(calendar(cfg)):
        p = period(month)
        # Every stored close row is one run of the committed Finance query at its close instant.
        assert conn.execute(bind("finance_revenue.sql"), {"period": p, "closed_at": close}).fetchall() == [finance[index]]
        # Latest complete state changes no closed Finance values (only the query's label timestamp differs).
        current = conn.execute(bind("finance_revenue.sql"), {"period": p, "closed_at": horizon}).fetchone()
        assert current[:10] == finance[index][:10]
        # Every stored pack is one run of the committed Board query at its snapshot; a horizon rerun differs.
        stored = historical[3*index:3*index+3]
        assert conn.execute(bind("board_pack.sql"), {"period": p, "generated_at": board}).fetchall() == stored
        rerun = conn.execute(bind("board_pack.sql"), {"period": p, "generated_at": horizon}).fetchall()
        for old, new in zip(stored, rerun):
            assert old[:2] == new[:2]
            assert old[2] != new[2], "Recurring monthly credit batches should change the rerun"
    zero(conn, "SELECT COUNT(*) FROM analytics.etl_job_runs WHERE status<>'success' OR started_at>completed_at")
    for month, board, close in calendar(cfg):
        p = period(month)
        runs = dict(conn.execute("SELECT job_name,completed_at FROM analytics.etl_job_runs WHERE run_for_period=%s AND job_name<>'refresh_delivered_sales'", (p,)).fetchall())
        assert runs == {"board_pack_monthly": board, "finance_close": close}
        zero(conn, "SELECT COUNT(*) FROM core.credit_notes WHERE accounting_period=%s AND created_at>%s", (p, close))
        assert conn.execute("SELECT COUNT(*) FROM core.credit_notes WHERE accounting_period=%s AND created_at>%s", (p, board)).fetchone()[0] > 0
    p = cfg["scenario"]["audit_period"]
    stable = instant(cfg["scenario"]["sales_complete_at"])
    zero(conn, "SELECT COUNT(*) FROM analytics.delivered_sales WHERE SUBSTRING(CAST(delivery_date AS VARCHAR),1,7)=%s AND loaded_at>%s", (p, stable))
    zero(conn, """SELECT COUNT(*) FROM analytics.delivered_sales d JOIN core.orders o USING(order_id)
      JOIN core.order_items l USING(order_item_id) WHERE o.status<>'delivered'
      OR d.net_amount<>l.line_net_amount OR d.qty<>l.qty OR d.delivery_date<>o.delivery_date
      OR d.loaded_at<>CAST(o.delivery_date AS TIMESTAMP)+INTERVAL '1 day'+INTERVAL '2 hours 10 minutes'""")
    received = conn.execute("""SELECT SUBSTRING(CAST(r.received_date AS VARCHAR),1,7),c.sales_region,
        SUM(ri.qty_returned*CAST(l.net_amount AS NUMERIC)/l.qty)
      FROM core.returns r JOIN core.return_items ri USING(return_id)
      JOIN core.invoice_lines l USING(invoice_line_id) JOIN core.customers c ON c.customer_id=r.customer_id
      GROUP BY 1,2 ORDER BY 1,2""").fetchall()
    dashboard = {(p, region): amount for p, region, amount in conn.execute(
        "SELECT period,sales_region,returned_value FROM analytics.sales_dashboard_monthly").fetchall()}
    for receipt_period, region, amount in received:
        assert dashboard[receipt_period, region] == amount
    with (dataset[3] / "evidence/august_board_pack.csv").open(encoding="utf-8") as handle:
        export = list(csv.DictReader(handle))
    assert len(export) == 3
    for row in export:
        expected = conn.execute("SELECT value,generated_at FROM management.board_kpi_monthly WHERE period=%s AND kpi=%s", (p,row["kpi"])).fetchone()
        assert Decimal(row["value"]) == expected[0] and row["generated_at"] == str(expected[1])


def test_operational_sql_single_run_equivalence(dataset):
    """The evidence SQL is genuine single-run operational SQL (SC-9, SC-12): one
    nightly refresh, one Finance close and one pack run each reproduce exactly the
    canonical rows they are responsible for, executed as committed."""
    conn, cfg, *_ = dataset
    s = cfg["scenario"]
    p = s["audit_period"]
    script = statements(bind("sales_dashboard.sql"))
    refresh = [text for keyword, text in script if keyword in ("DELETE", "INSERT")]
    insert = [text for keyword, text in script if keyword == "INSERT"]
    assert len(refresh) == 2 and len(insert) == 1
    dates = [row[0] for row in conn.execute("SELECT DISTINCT delivery_date FROM analytics.delivered_sales ORDER BY 1").fetchall()]
    august = [d for d in dates if period(d) == p]
    assert august
    total = conn.execute("SELECT COUNT(*) FROM analytics.delivered_sales").fetchone()[0]
    slice_sql = "SELECT * FROM analytics.delivered_sales WHERE delivery_date=%s ORDER BY order_item_id"
    for run_date in (dates[0], august[-1], dates[-1]):
        before = conn.execute(slice_sql, (run_date,)).fetchall()
        assert before
        loaded_at = before[0][12]
        assert loaded_at == stamp(run_date + timedelta(days=1), 2, 10)
        conn.execute("BEGIN")
        try:
            # Replaying the nightly refresh for a run date replaces its slice; nothing is duplicated.
            for statement in refresh:
                conn.execute(statement, {"run_date": run_date, "loaded_at": loaded_at})
            assert conn.execute(slice_sql, (run_date,)).fetchall() == before
            assert conn.execute("SELECT COUNT(*) FROM analytics.delivered_sales").fetchone()[0] == total
            # The insert alone rebuilds the slice from core rows once it is removed.
            conn.execute("DELETE FROM analytics.delivered_sales WHERE delivery_date=%s", (run_date,))
            assert conn.execute("SELECT COUNT(*) FROM analytics.delivered_sales").fetchone()[0] == total - len(before)
            conn.execute(insert[0], {"run_date": run_date, "loaded_at": loaded_at})
            assert conn.execute(slice_sql, (run_date,)).fetchall() == before
        finally:
            conn.execute("ROLLBACK")
    assert conn.execute("SELECT COUNT(*) FROM analytics.delivered_sales").fetchone()[0] == total
    # August is complete at the fixed T+1 completion on 1 September.
    latest = conn.execute("SELECT MAX(loaded_at) FROM analytics.delivered_sales WHERE SUBSTRING(CAST(delivery_date AS VARCHAR),1,7)=%s", (p,)).fetchone()[0]
    assert latest == instant(s["sales_complete_at"])
    # One Finance close for the audit period equals the stored extract row.
    stored_finance = conn.execute("SELECT * FROM finance.monthly_pnl_extract WHERE accounting_period=%s", (p,)).fetchall()
    assert len(stored_finance) == 1
    assert conn.execute(bind("finance_revenue.sql"), {"period": p, "closed_at": instant(s["finance_close_at"])}).fetchall() == stored_finance
    # One pack run at the historical snapshot equals the circulated rows; the horizon rerun differs.
    stored_board = conn.execute("SELECT * FROM management.board_kpi_monthly WHERE period=%s ORDER BY kpi", (p,)).fetchall()
    assert len(stored_board) == 3
    assert conn.execute(bind("board_pack.sql"), {"period": p, "generated_at": instant(s["board_snapshot_at"])}).fetchall() == stored_board
    rerun = {row[1]: row[2] for row in conn.execute(bind("board_pack.sql"), {"period": p, "generated_at": instant(s["observation_at"])}).fetchall()}
    stored = {row[1]: row[2] for row in stored_board}
    assert rerun["Revenue"] != stored["Revenue"] and rerun["Gross Margin"] != stored["Gross Margin"]


def test_operational_evidence_artifacts(dataset):
    """Evidence SQL is the committed operational query verbatim: single-run,
    parameterized, with no rendered replay calendar or historical scaffold."""
    _, _, _, data, *_ = dataset
    for name, parameters in SURFACE_PARAMETERS.items():
        text = (data / "evidence" / name).read_text(encoding="utf-8")
        assert text == surface_sql(name)
        for parameter in parameters:
            assert re.search(rf":{parameter}\b", text), (name, parameter)
        assert "{{" not in text and "VALUES" not in text.upper()
        assert "TIMESTAMP '" not in text and not re.search(r"\d{4}-\d{2}-\d{2}", text)
    assert [keyword for keyword, _ in statements(surface_sql("sales_dashboard.sql"))] == ["DELETE", "INSERT", "CREATE"]
    assert len(statements(surface_sql("finance_revenue.sql"))) == 1
    assert len(statements(surface_sql("board_pack.sql"))) == 1


def test_reconciliation_manifest_and_materiality(dataset):
    conn, cfg, profile, _, hidden, expected, _ = dataset
    recomputed = verify_scenario(conn, cfg)
    stored = json.loads((hidden / f"{profile}.json").read_text(encoding="utf-8"))
    for key in ("values", "bridges", "materiality"):
        assert stored[key] == recomputed[key] == expected[key]
    v, b = recomputed["values"], recomputed["bridges"]
    assert v["R_period"] == v["R_early"] + v["R_late"]
    assert v["C_period"] == v["C_early"] + v["C_late"]
    lines = {row["line"]: row for row in b["gross_margin_finance_to_board"]}
    assert lines["cost_on_visible_credits"] == {"line": "cost_on_visible_credits", "category": "defect", "amount": -v["R_early"]}
    assert lines["cost_on_credits_after_snapshot"] == {"line": "cost_on_credits_after_snapshot", "category": "timing", "amount": -v["R_late"]}
    assert b["gross_margin_finance_to_sales"][-1]["category"] == "definition"
    assert b["gross_margin_finance_to_sales"][-1]["amount"] == -v["R_period"]
    assert len(stored["supporting_findings"]) == 2
    assert "true_revenue" not in json.dumps(stored)
    # Every pairwise bridge is accounted for, including Sales → Board by subtraction.
    for metric, source, target in (("revenue", "DSV", "BR"), ("gross_margin", "CM", "BGM")):
        a = sum(x["amount"] for x in b[metric + "_finance_to_sales"])
        z = sum(x["amount"] for x in b[metric + "_finance_to_board"])
        assert z - a == v[target] - v[source]
    assert all(row["pass"] for row in recomputed["materiality"].values())


def test_independent_recheck_detects_surface_tampering(dataset):
    conn, cfg, *_ = dataset
    # Transaction rollback makes this a meaningful negative control, not a second answer constant.
    conn.execute("BEGIN")
    try:
        conn.execute("UPDATE management.board_kpi_monthly SET value=value+1 WHERE kpi='Revenue'")
        with pytest.raises(AssertionError):
            inspect_evidence(conn, cfg["scenario"]["audit_period"])
    finally:
        conn.execute("ROLLBACK")


def test_evidence_boundary_and_comments(dataset, monkeypatch):
    conn, cfg, _, data, hidden, _, backend = dataset
    expected = {"finance_revenue.sql", "sales_dashboard.sql", "board_pack.sql", "august_board_pack.csv",
                "finance_close_notes.md", "sales_dashboard_notes.md", "board_pack_handover.md"}
    assert {p.name for p in (data / "evidence").iterdir()} == expected
    forbidden = re.compile(r"is_wrong|expected_revenue|correct_definition|true_value|mechanism|planted|scenario|defect|ground_truth|bad_board|late_credit|metric_definitions|dataset_registry|kpi_catalog", re.I)
    for path in sorted((data / "evidence").iterdir()):
        assert not forbidden.search(path.name + path.read_text(encoding="utf-8")), path.name
    for path in sorted((data / "core").iterdir()):
        # Scan all generated operational values, not just column names.
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                assert not forbidden.search(line)
    metadata = conn.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema IN ('core','finance','analytics','management')").fetchall()
    assert not forbidden.search(str(metadata) + COMMENTS)
    if backend == "postgresql":
        table_comments = dict(conn.execute("""SELECT n.nspname||'.'||c.relname,obj_description(c.oid)
          FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname IN ('core','finance','analytics','management') AND c.relkind IN ('r','v')""").fetchall())
        present = {"core.orders", "core.invoices", "core.credit_notes", "core.product_cost_history",
                   "finance.monthly_pnl_extract", "analytics.delivered_sales"}
        assert {k for k,v in table_comments.items() if v} == present
        col_comments = conn.execute("""SELECT n.nspname||'.'||c.relname||'.'||a.attname,col_description(c.oid,a.attnum)
          FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname IN ('core','finance','analytics','management') AND a.attnum>0
            AND col_description(c.oid,a.attnum) IS NOT NULL""").fetchall()
        assert {r[0] for r in col_comments} == {"core.invoices.accounting_period", "core.credit_notes.accounting_period", "analytics.sales_dashboard_monthly.revenue"}
        assert "net of discounts and returns" in dict(col_comments)["analytics.sales_dashboard_monthly.revenue"]
        assert not forbidden.search(str(table_comments) + str(col_comments))
    original = Path.read_text

    def deny_hidden(path, *args, **kwargs):
        if hidden in path.parents or "ground_truth" in path.parts:
            raise AssertionError("Read-only reconciliation attempted to consume hidden truth")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", deny_hidden)
    inspect_evidence(conn, cfg["scenario"]["audit_period"])
    # Payments must have no reporting or reconciliation role.
    for name in ("finance_revenue.sql", "sales_dashboard.sql", "board_pack.sql", "reconcile.py"):
        assert "core.payments" not in (ROOT / "benchmark/scenario" / name).read_text(encoding="utf-8")


def test_deterministic_core(dataset, tmp_path):
    _, cfg, profile, data, *_ = dataset
    generate_core(cfg, profile, tmp_path / "core")
    assert hashes(data / "core") == hashes(tmp_path / "core")


def test_offline_end_to_end_determinism(tmp_path):
    cfg = load_config()
    results = []
    for number in (1, 2):
        folder = tmp_path / str(number)
        conn, counts = load(cfg, "smoke", folder)
        truth = manifest(conn, cfg, "smoke", counts, verify_scenario(conn, cfg))
        result = (hashes(folder), json.dumps(truth, sort_keys=True, indent=2, default=str))
        conn.connection.close()
        results.append(result)
    assert results[0] == results[1]


def test_config_rejects_invalid_timeline_and_counts(tmp_path):
    text = (ROOT / "benchmark/config/benchmark.toml").read_text(encoding="utf-8")
    path = tmp_path / "bad.toml"
    path.write_text(text.replace('2026-09-08T09:00:00+07:00', '2026-09-01T09:00:00+07:00'), encoding="utf-8")
    with pytest.raises(ValueError, match="timeline"):
        load_config(path)
    path.write_text(text.replace("order_items = 6000", "order_items = 1"), encoding="utf-8")
    with pytest.raises(ValueError, match="three merchandise lines"):
        load_config(path)


def test_postgresql_cli_and_second_generation(dataset, tmp_path):
    conn, cfg, profile, data, truth, expected, backend = dataset
    if backend != "postgresql" or profile != "smoke":
        pytest.skip("Full PostgreSQL CLI repeat is covered once on smoke; core repeat covers both scales")
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    admin_dsn = os.environ["NORTHSTAR_TEST_DATABASE_URL"]
    name = f"northstar_repeat_{os.getpid()}"
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        env = dict(os.environ)
        env[cfg["postgresql"]["dsn_env_var"]] = make_conninfo(admin_dsn, dbname=name)
        try:
            process = subprocess.run([sys.executable, "benchmark/generate.py", "--profile", "smoke",
                                      "--data-dir", str(tmp_path / "data"), "--truth-dir", str(tmp_path / "hidden")],
                                     cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
            assert process.returncode == 0, process.stderr
            assert json.loads(process.stdout)["values"] == expected["values"]
            assert hashes(data) == hashes(tmp_path / "data")
            assert hashes(truth) == hashes(tmp_path / "hidden")
            recheck = subprocess.run([sys.executable, "-m", "benchmark.scenario.reconcile", "--period", cfg["scenario"]["audit_period"]],
                                     cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
            assert recheck.returncode == 0, recheck.stderr
            assert json.loads(recheck.stdout)["values"] == expected["values"]
            with psycopg.connect(env[cfg["postgresql"]["dsn_env_var"]]) as second:
                constraints = second.execute("SELECT COUNT(*) FROM pg_constraint WHERE contype='f' AND connamespace='core'::regnamespace").fetchone()[0]
                assert constraints == 17
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
