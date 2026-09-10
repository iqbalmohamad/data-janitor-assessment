"""DuckDB mirror is a faithful, internal-only copy (SPEC.md Amendment O).

Verifies that benchmark/load_duckdb.py reproduces the PostgreSQL surfaces
verbatim -- so the mirror can be used for fast local inspection without
becoming a second implementation path. Requires the same disposable
PostgreSQL instance as the end-to-end tests (uses a scratch database) and
is skipped when NORTHSTAR_DATABASE_URL is unset.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DSN_ENV = "NORTHSTAR_DATABASE_URL"
TEST_DB = "northstar_m0_duckdb_test"

pytestmark = pytest.mark.skipif(
    not os.environ.get(DSN_ENV),
    reason=f"set {DSN_ENV} to run the DuckDB mirror test",
)


@pytest.fixture(scope="module")
def mirror(gen, config, tmp_path_factory):
    import duckdb
    import psycopg
    from _pytest.monkeypatch import MonkeyPatch
    from psycopg import conninfo

    base_dsn = os.environ[DSN_ENV]
    with psycopg.connect(base_dsn, autocommit=True) as conn:
        conn.execute(f"drop database if exists {TEST_DB}")
        conn.execute(f"create database {TEST_DB}")
    dsn = conninfo.make_conninfo(base_dsn, dbname=TEST_DB, options="-c timezone=Asia/Jakarta")
    out = tmp_path_factory.mktemp("duckdb_mirror")
    gen.run("smoke", dsn=dsn, out_root=out, quiet=True)

    spec = importlib.util.spec_from_file_location(
        "northstar_load_duckdb", REPO_ROOT / "benchmark" / "load_duckdb.py"
    )
    loader = importlib.util.module_from_spec(spec)
    sys.modules["northstar_load_duckdb"] = loader
    spec.loader.exec_module(loader)

    # the loader resolves dev_mirror_path relative to its REPO_ROOT; point it
    # at the scratch tree and the scratch database
    mp = MonkeyPatch()
    mp.setenv(DSN_ENV, dsn)
    mp.setattr(loader, "REPO_ROOT", out)
    mirror_file = out / config["duckdb"]["dev_mirror_path"]

    assert loader.main() == 0
    yield {"duck": duckdb.connect(str(mirror_file), read_only=True), "dsn": dsn}
    mp.undo()


def test_mirror_reproduces_surfaces(mirror):
    import psycopg

    duck = mirror["duck"]
    with psycopg.connect(mirror["dsn"]) as conn, conn.cursor() as cur:
        cur.execute(
            "select net_merchandise_revenue, gross_margin "
            "from finance.monthly_pnl_extract where accounting_period = '2026-08'"
        )
        pg_fin = cur.fetchone()
        cur.execute(
            "select sum(revenue), sum(margin) "
            "from analytics.sales_dashboard_monthly where month = '2026-08-01'"
        )
        pg_sales = cur.fetchone()
        cur.execute(
            "select value from management.board_kpi_monthly "
            "where period = '2026-08' and kpi = 'Revenue'"
        )
        pg_board = cur.fetchone()[0]

    duck_fin = duck.execute(
        "select net_merchandise_revenue, gross_margin "
        "from finance.monthly_pnl_extract where accounting_period = '2026-08'"
    ).fetchone()
    duck_sales = duck.execute(
        "select sum(revenue), sum(margin) "
        "from analytics.sales_dashboard_monthly where month = '2026-08-01'"
    ).fetchone()
    duck_board = duck.execute(
        "select value from management.board_kpi_monthly "
        "where period = '2026-08' and kpi = 'Revenue'"
    ).fetchone()[0]

    assert int(duck_fin[0]) == pg_fin[0]
    assert int(duck_fin[1]) == pg_fin[1]
    assert int(duck_sales[0]) == pg_sales[0]
    assert int(duck_sales[1]) == pg_sales[1]
    assert int(duck_board) == int(pg_board)


def test_mirror_row_counts_match(mirror):
    import psycopg

    duck = mirror["duck"]
    with psycopg.connect(mirror["dsn"]) as conn, conn.cursor() as cur:
        for table in ("core.orders", "core.invoice_lines", "core.credit_notes",
                      "analytics.delivered_sales"):
            cur.execute(f"select count(*) from {table}")
            pg_n = cur.fetchone()[0]
            duck_n = duck.execute(f"select count(*) from {table}").fetchone()[0]
            assert duck_n == pg_n, f"{table}: duckdb {duck_n} != postgres {pg_n}"
