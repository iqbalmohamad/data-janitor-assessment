"""Optional dev/test mirror of the Northstar PostgreSQL environment into DuckDB.

Internal convenience only (SPEC.md Amendment section O): DuckDB is never
Northstar's canonical environment, and this mirror is never an alternate
implementation path. It copies the PostgreSQL-materialized data verbatim --
including the reporting surfaces, with the dashboard view flattened into a
table -- so it cannot drift from the canonical environment's logic.

Usage:
    NORTHSTAR_DATABASE_URL=postgresql://... python benchmark/load_duckdb.py
"""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "benchmark" / "config" / "benchmark.toml"

# (qualified name, ORDER BY for a stable copy). The dashboard view is
# materialized as a table of its output rows.
MIRROR_OBJECTS = [
    ("core.customers", "1"),
    ("core.products", "1"),
    ("core.product_cost_history", "1"),
    ("core.orders", "1"),
    ("core.order_items", "1"),
    ("core.invoices", "1"),
    ("core.invoice_lines", "1"),
    ("core.payments", "1"),
    ("core.returns", "1"),
    ("core.return_items", "1"),
    ("core.credit_notes", "1"),
    ("finance.monthly_pnl_extract", "1"),
    ("analytics.delivered_sales", "3"),
    ("analytics.etl_job_runs", "1"),
    ("analytics.sales_dashboard_monthly", "1, 2"),
    ("management.board_kpi_monthly", "1, 2"),
]

# PostgreSQL type OID -> DuckDB column type
OID_TYPES = {
    16: "BOOLEAN",
    20: "BIGINT",
    21: "SMALLINT",
    23: "INTEGER",
    25: "VARCHAR",
    1082: "DATE",
    1114: "TIMESTAMP",
    1184: "TIMESTAMPTZ",
    1700: "DECIMAL(20,4)",
}


def main() -> int:
    import tempfile

    import duckdb
    import psycopg

    with CONFIG_PATH.open("rb") as f:
        config = tomllib.load(f)
    dsn = os.environ.get(config["postgresql"]["dsn_env_var"])
    if not dsn:
        print(
            f"error: set {config['postgresql']['dsn_env_var']} to the PostgreSQL "
            "DSN of a generated Northstar environment",
            file=sys.stderr,
        )
        return 1
    mirror_path = REPO_ROOT / config["duckdb"]["dev_mirror_path"]
    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    if mirror_path.exists():
        mirror_path.unlink()

    duck = duckdb.connect(str(mirror_path))
    with psycopg.connect(dsn) as conn:
        for schema in ("core", "finance", "analytics", "management"):
            duck.execute(f"create schema if not exists {schema}")
        for name, order_by in MIRROR_OBJECTS:
            # Stream the object out of PostgreSQL as CSV and bulk-load it
            # into DuckDB via read_csv -- far faster than per-row inserts,
            # and it keeps the mirror a verbatim copy that cannot drift.
            with conn.cursor() as cur:
                cur.execute(f"select * from {name} order by {order_by} limit 0")
                columns = [
                    f'"{d.name}" {OID_TYPES.get(d.type_code, "VARCHAR")}'
                    for d in cur.description
                ]
                col_names = [d.name for d in cur.description]
            duck.execute(f"create table {name} ({', '.join(columns)})")
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".csv", delete=False
            ) as tmp:
                header = ",".join(f'"{c}"' for c in col_names) + "\n"
                tmp.write(header.encode("utf-8"))
                copy_sql = (
                    f"copy (select * from {name} order by {order_by}) "
                    "to stdout with (format csv)"
                )
                # write PostgreSQL's raw CSV bytes straight through
                with conn.cursor().copy(copy_sql) as copy:
                    for data in copy:
                        tmp.write(data)
                tmp_path = tmp.name
            duck.execute(
                f"insert into {name} select * from "
                f"read_csv(?, header=true, nullstr='', all_varchar=false, "
                f"columns={_duck_columns(columns)})",
                [tmp_path],
            )
            os.unlink(tmp_path)
            count = duck.execute(f"select count(*) from {name}").fetchone()[0]
            print(f"[load_duckdb] {name}: {count} rows")
    duck.close()
    print(f"[load_duckdb] mirror written to {mirror_path}")
    return 0


def _duck_columns(column_defs: list[str]) -> str:
    """Render a read_csv columns={...} struct literal from `"name" TYPE` defs."""
    parts = []
    for col in column_defs:
        name, _, ctype = col.partition(" ")
        parts.append(f"{name}: '{ctype}'")
    return "{" + ", ".join(parts) + "}"


if __name__ == "__main__":
    raise SystemExit(main())
