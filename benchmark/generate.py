"""Bounded Northstar M0 generator. PostgreSQL is the acceptance environment."""

import argparse
import bisect
import csv
import json
import os
import random
import re
import tomllib
from calendar import monthrange
from contextlib import ExitStack
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "benchmark/scenario"
CONFIG = ROOT / "benchmark/config/benchmark.toml"

# Column order also defines CSV serialization. Every core row has an insertion time.
TABLES = {
    "products": "product_id BIGINT PRIMARY KEY, sku TEXT, product_name TEXT, category TEXT, uom TEXT, list_price BIGINT, standard_cost BIGINT, is_active BOOLEAN, created_at TIMESTAMP",
    "product_cost_history": "product_id BIGINT REFERENCES core.products(product_id), cost_type TEXT, effective_from DATE, unit_cost BIGINT, source TEXT, created_at TIMESTAMP, PRIMARY KEY(product_id,cost_type,effective_from)",
    "customers": "customer_id BIGINT PRIMARY KEY, customer_code TEXT, company_name TEXT, segment TEXT, province TEXT, city TEXT, sales_region TEXT, credit_terms_days INTEGER, is_active BOOLEAN, created_at TIMESTAMP",
    "orders": "order_id BIGINT PRIMARY KEY, customer_id BIGINT REFERENCES core.customers(customer_id), order_date DATE, requested_delivery_date DATE, status TEXT, delivery_date DATE, cancelled_date DATE, created_at TIMESTAMP",
    "order_items": "order_item_id BIGINT PRIMARY KEY, order_id BIGINT REFERENCES core.orders(order_id), product_id BIGINT REFERENCES core.products(product_id), qty INTEGER, unit_price BIGINT, discount_pct NUMERIC(6,4), line_net_amount BIGINT, created_at TIMESTAMP",
    "invoices": "invoice_id BIGINT PRIMARY KEY, order_id BIGINT UNIQUE REFERENCES core.orders(order_id), customer_id BIGINT REFERENCES core.customers(customer_id), invoice_date DATE, accounting_period TEXT, merchandise_amount BIGINT, freight_amount BIGINT, vat_amount BIGINT, total_amount BIGINT, created_at TIMESTAMP",
    "invoice_lines": "invoice_line_id BIGINT PRIMARY KEY, invoice_id BIGINT REFERENCES core.invoices(invoice_id), line_no INTEGER, line_type TEXT, order_item_id BIGINT REFERENCES core.order_items(order_item_id), product_id BIGINT REFERENCES core.products(product_id), qty INTEGER, unit_price BIGINT, discount_amount BIGINT, net_amount BIGINT, vat_amount BIGINT, unit_cost_actual BIGINT, created_at TIMESTAMP",
    "payments": "payment_id BIGINT PRIMARY KEY, invoice_id BIGINT REFERENCES core.invoices(invoice_id), payment_date DATE, amount BIGINT, method TEXT, created_at TIMESTAMP",
    "returns": "return_id BIGINT PRIMARY KEY, invoice_id BIGINT REFERENCES core.invoices(invoice_id), customer_id BIGINT REFERENCES core.customers(customer_id), received_date DATE, reason_code TEXT, status TEXT, created_at TIMESTAMP",
    "return_items": "return_item_id BIGINT PRIMARY KEY, return_id BIGINT REFERENCES core.returns(return_id), invoice_line_id BIGINT REFERENCES core.invoice_lines(invoice_line_id), qty_returned INTEGER, created_at TIMESTAMP",
    "credit_notes": "credit_note_id BIGINT PRIMARY KEY, return_id BIGINT UNIQUE REFERENCES core.returns(return_id), invoice_id BIGINT REFERENCES core.invoices(invoice_id), customer_id BIGINT REFERENCES core.customers(customer_id), posting_date DATE, accounting_period TEXT, merchandise_amount BIGINT, vat_amount BIGINT, total_amount BIGINT, cogs_reversal_amount BIGINT, created_at TIMESTAMP",
}
CORE_ORDER = ("products", "product_cost_history", "customers", "orders", "order_items",
              "invoices", "invoice_lines", "payments", "returns", "return_items", "credit_notes")

SURFACE_DDL = """
CREATE TABLE analytics.delivered_sales (
 delivery_date DATE, order_id BIGINT, order_item_id BIGINT PRIMARY KEY,
 customer_id BIGINT, sales_region TEXT, product_id BIGINT, qty INTEGER,
 gross_amount BIGINT, discount_amount BIGINT, net_amount BIGINT,
 std_unit_cost BIGINT, std_cost_amount BIGINT, loaded_at TIMESTAMP);
CREATE TABLE finance.monthly_pnl_extract (
 accounting_period TEXT PRIMARY KEY, gross_invoiced_merchandise BIGINT,
 credit_notes_merchandise BIGINT, net_merchandise_revenue BIGINT, freight_income BIGINT,
 cogs_invoiced BIGINT, cogs_reversed BIGINT, recognized_cogs BIGINT,
 gross_margin BIGINT, gross_margin_pct NUMERIC(20,12), closed_at TIMESTAMP, prepared_by TEXT);
CREATE TABLE management.board_kpi_monthly (
 period TEXT, kpi TEXT, value NUMERIC(30,12), generated_at TIMESTAMP,
 source_job TEXT, PRIMARY KEY(period,kpi));
CREATE TABLE analytics.etl_job_runs (
 job_name TEXT, run_for_period TEXT, started_at TIMESTAMP, completed_at TIMESTAMP,
 status TEXT, rows_written BIGINT);
"""

COMMENTS = """
COMMENT ON TABLE core.orders IS 'Commercial orders and delivery confirmation.';
COMMENT ON TABLE core.invoices IS 'Posted customer invoices.';
COMMENT ON TABLE core.credit_notes IS 'Customer credit documents.';
COMMENT ON TABLE core.product_cost_history IS 'Pricing standards and purchase cost revisions.';
COMMENT ON COLUMN core.invoices.accounting_period IS 'Period of invoice posting; unbilled deliveries are not accrued.';
COMMENT ON COLUMN core.credit_notes.accounting_period IS 'Returns received by month end and credited by close are booked to the receipt period.';
COMMENT ON TABLE finance.monthly_pnl_extract IS 'Finance owns the monthly P&L close extract.';
COMMENT ON TABLE analytics.delivered_sales IS 'Nightly T+1 refresh, completed at 02:10 WIB.';
COMMENT ON COLUMN analytics.sales_dashboard_monthly.revenue IS 'Delivered merchandise net of discounts and returns.';
"""


def load_config(path=CONFIG, profile="smoke"):
    with Path(path).open("rb") as handle:
        cfg = tomllib.load(handle)
    for section in ("generation", "postgresql", "scale", "scenario", "materiality"):
        if section not in cfg:
            raise ValueError(f"Missing configuration section: {section}")
    s = cfg["scenario"]
    required = ("audit_period", "credit_batch_business_days", "board_business_day", "close_business_day",
                "vat_rate", "posting_lag_weights", "cancelled_rate", "freight_rate", "return_quantity_fraction",
                "backdated_return_share", "august_cost_change_share", "standard_cost_price_ratio",
                "actual_cost_ratios", "actual_change_ratio", "actual_change_step", "month_end_deliveries", "month_end_delivery_share")
    for key in required:
        if key not in s:
            raise ValueError(f"Missing scenario parameter: {key}")
    for key in ("vat_rate", "cancelled_rate", "freight_rate", "return_quantity_fraction",
                "backdated_return_share", "august_cost_change_share", "standard_cost_price_ratio",
                "actual_change_ratio", "actual_change_step", "month_end_delivery_share"):
        if not 0 < s[key] < 1:
            raise ValueError(f"Invalid scenario fraction: {key}")
    for key in ("credit_rnmr_min", "credit_rnmr_max", "late_credit_share_min", "period_leg_rnmr_min",
                "cost_difference_min", "pairwise_revenue_rnmr_min", "pairwise_margin_pct_min",
                "finance_margin_min", "finance_margin_max"):
        if key not in cfg["materiality"] or not 0 < cfg["materiality"][key] < 1:
            raise ValueError(f"Invalid materiality parameter: {key}")
    for key in ("board_snapshot_at", "finance_close_at", "observation_at", "sales_complete_at",
                "credit_batch_start_at", "credit_batch_end_at"):
        instant(s[key])
    anchor = date.fromisoformat(cfg["generation"]["as_of_date"])
    if anchor.day != 1 or s["audit_period"] != period(anchor - timedelta(days=1)):
        raise ValueError("The anchor must follow the audit period")
    if not (instant(s["sales_complete_at"]) < instant(s["board_snapshot_at"]) <
            instant(s["credit_batch_start_at"]) <= instant(s["credit_batch_end_at"]) <
            instant(s["finance_close_at"]) < instant(s["observation_at"])):
        raise ValueError("Invalid close timeline")
    n = cfg["scale"][profile]
    if set(n) != {"products", "customers", "orders", "order_items", "returns", "payments"}:
        raise ValueError("Scale must name exactly the six independently generated populations")
    if any(type(v) is not int or v <= 0 for v in n.values()):
        raise ValueError("Scale counts must be positive integers")
    if n["order_items"] != 3 * n["orders"]:
        raise ValueError("This bounded generator uses three merchandise lines per order")
    if not .05 <= n["returns"] / n["orders"] <= .095:
        raise ValueError("Return population must be within lifecycle range")
    if abs(sum(s["posting_lag_weights"]) - 1) > 1e-9:
        raise ValueError("Posting weights must sum to one")
    if len(s["posting_lag_weights"]) != 4 or any(x < 0 for x in s["posting_lag_weights"]):
        raise ValueError("Posting weights must cover lags zero through three")
    if len(s["actual_cost_ratios"]) != 5 or any(not .92 <= x <= 1.08 for x in s["actual_cost_ratios"]):
        raise ValueError("Expected five bounded actual-cost strata")
    if not all(1 <= x <= s["close_business_day"] for x in s["credit_batch_business_days"]):
        raise ValueError("Credit batches must finish by Finance close")
    if set(cfg["postgresql"]["schemas"]) != {"core", "finance", "analytics", "management"}:
        raise ValueError("Unexpected Northstar schemas")
    return cfg


def instant(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() != timedelta(hours=7):
        raise ValueError("Scenario instants must be WIB (+07:00)")
    return parsed.replace(tzinfo=None)


def period(day):
    return day.isoformat()[:7]


def month_add(day, count):
    y, m = divmod(day.year * 12 + day.month - 1 + count, 12)
    return date(y, m + 1, 1)


def business_add(day, count):
    if count == 0:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        return day
    while count:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count -= 1
    return day


def business_day(month, number):
    return business_add(business_add(month, 0), number - 1)


def stamp(day, hour=9, minute=0):
    return datetime.combine(day, time(hour, minute))


def money(value):
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def calendar(cfg):
    anchor = date.fromisoformat(cfg["generation"]["as_of_date"])
    s = cfg["scenario"]
    result = []
    for i in range(cfg["generation"]["history_years"] * 12):
        month = month_add(anchor, i - cfg["generation"]["history_years"] * 12)
        following = month_add(month, 1)
        board = stamp(business_day(following, s["board_business_day"]), 8, 15)
        close = stamp(business_day(following, s["close_business_day"]), 17, 30)
        if period(month) == s["audit_period"]:
            board, close = instant(s["board_snapshot_at"]), instant(s["finance_close_at"])
        result.append((month, board, close))
    return result


def columns(table):
    return [chunk.strip().split()[0] for chunk in TABLES[table].split(", ")
            if not chunk.startswith("PRIMARY KEY")]


def generate_core(cfg, profile, output):
    """Stream dependency-linked CSVs; memory is bounded by catalog/customer size."""
    output.mkdir(parents=True, exist_ok=True)
    n, s = cfg["scale"][profile], cfg["scenario"]
    seed = cfg["generation"]["seed"]
    rng = {t: random.Random(f"{seed}:{t}") for t in sorted(TABLES)}
    months = calendar(cfg)
    start = months[0][0]
    horizon = instant(s["observation_at"])
    anchor = date.fromisoformat(cfg["generation"]["as_of_date"])
    vat = Decimal(str(s["vat_rate"]))
    counts = {t: 0 for t in sorted(TABLES)}
    costs, prices, customers = {}, {}, {}
    payment_candidates = []
    changed_products = sorted(range(1, n["products"] + 1), key=lambda pid: ((pid - 2) % 5, pid))[:int(n["products"] * s["august_cost_change_share"])]
    changed_products = frozenset(changed_products)  # Membership only; never serialized/iterated.
    with ExitStack() as stack:
        writers = {}
        for table in sorted(TABLES):
            handle = stack.enter_context((output / f"{table}.csv").open("w", newline="", encoding="utf-8"))
            writers[table] = csv.writer(handle, lineterminator="\n")
            writers[table].writerow(columns(table))

        def emit(table, *values):
            counts[table] += 1
            writers[table].writerow(values)

        for pid in range(1, n["products"] + 1):
            price = (95 + int(rng["products"].random() * 11)) * 1000
            prices[pid] = price
            std = money(price * s["standard_cost_price_ratio"])
            emit("products", pid, f"NS-{pid:05d}", f"Luma Pack {pid:05d}",
                 ("household", "packaged_goods")[pid % 2], "case", price, std, True, stamp(date(start.year, 7, 1), 0))
        for pid in range(1, n["products"] + 1):
            std = money(prices[pid] * s["standard_cost_price_ratio"])
            entries = []
            for month, _, _ in months:
                if month == start or month.month in (1, 7):
                    # The baseline is effective before the history window; subsequent
                    # pricing revisions occur only in January and July.
                    effective = date(start.year, 7, 1) if month == start else month
                    actual = money(std * s["actual_cost_ratios"][(pid - 1) % 5])
                    entries.extend([(effective, "standard", std), (effective, "actual", actual)])
                if pid in changed_products:
                    effective = month.replace(day=15)
                    ratio = s["actual_change_ratio"] + (month.month % 2) * s["actual_change_step"]
                    entries.append((effective, "actual", money(std * ratio)))
            entries.sort(key=lambda row: (row[1], row[0]))
            costs[pid] = {kind: [(d, c) for d, k, c in entries if k == kind]
                          for kind in ("actual", "standard")}
            for effective, kind, cost in entries:
                emit("product_cost_history", pid, kind, effective, cost,
                     "pricing_file" if kind == "standard" else "purchase_average", stamp(effective, 0))
        for cid in range(1, n["customers"] + 1):
            region = ("Java Meridian", "Sumatra Aurora", "Eastern Pelangi")[cid % 3]
            terms = (14, 30, 45)[int(rng["customers"].random() * 3)]
            customers[cid] = terms
            emit("customers", cid, f"ORG-{cid:06d}", f"PT Arunika Niaga {cid:06d}",
                 ("modern_trade", "general_trade", "wholesale", "horeca")[cid % 4],
                 f"Provinsi {region}", f"Kota {region}", region, terms, True, stamp(start, 0))

        tail_count = max(12, n["orders"] // 150)
        historical = n["orders"] - tail_count
        oid = item_id = line_id = payment_id = return_id = ri_id = credit_id = 0
        # Allocate counts by cumulative integer apportionment, without random misses.
        for mi in range(len(months) + 1):
            tail = mi == len(months)
            month = anchor if tail else months[mi][0]
            count = tail_count if tail else historical * (mi + 1) // len(months) - historical * mi // len(months)
            ret_count = 1 if tail else (n["returns"] - 1) * (mi + 1) // len(months) - (n["returns"] - 1) * mi // len(months)
            end_count = max(s["month_end_deliveries"], int(count * s["month_end_delivery_share"]))
            cancel_count = max(1, money(count * s["cancelled_rate"]))
            if end_count + ret_count + cancel_count + 2 >= count:
                raise ValueError("Profile too small for the monthly lifecycle strata")
            for pos in range(count):
                oid += 1
                cid = 1 + int(rng["orders"].random() * n["customers"])
                if tail:
                    delivery = month.replace(day=1 + pos % 5)
                elif pos < end_count:
                    delivery = month.replace(day=monthrange(month.year, month.month)[1])
                    while delivery.weekday() >= 5:
                        delivery -= timedelta(days=1)
                elif pos < end_count + ret_count:
                    delivery = month.replace(day=5)
                else:
                    delivery = month.replace(day=4 + int(rng["orders"].random() * 21))
                if delivery.weekday() == 6:
                    delivery += timedelta(days=1)
                ordered = max(start, delivery - timedelta(days=1 + int(rng["orders"].random() * 7)))
                status = "delivered"
                if pos >= count - cancel_count:
                    status = "cancelled"
                if (tail and pos >= count // 2 and status != "cancelled") or (
                    not tail and mi == len(months) - 1 and pos == count - cancel_count - 1
                ):
                    status = "open"
                    ordered = month.replace(day=6 if tail else 28)
                cancelled = ordered + timedelta(days=1) if status == "cancelled" else None
                requested = ordered + timedelta(days=1) if status == "open" else delivery
                emit("orders", oid, cid, ordered, requested, status,
                     delivery if status == "delivered" else None, cancelled, stamp(ordered))
                lines = []
                for j in range(3):
                    item_id += 1
                    pid = 1 + ((oid - 1) * 3 + j) % n["products"]
                    qty, price = 20, prices[pid]
                    discount = Decimal("0.05")
                    net = money(qty * price * (1 - discount))
                    emit("order_items", item_id, oid, pid, qty, price, discount, net, stamp(ordered, 10))
                    lines.append((item_id, pid, qty, price, net))
                if status != "delivered":
                    continue
                draw, cumulative, lag = rng["invoices"].random(), 0, 0
                for k, weight in enumerate(s["posting_lag_weights"]):
                    cumulative += weight
                    if draw < cumulative:
                        lag = k
                        break
                if not tail and pos < end_count:
                    # Explicit month-end posting queue, still within the 0–3 day rule.
                    lag = 1
                    while period(business_add(delivery, lag)) == period(month) and lag < 3:
                        lag += 1
                inv_date = business_add(delivery, lag)
                if tail:
                    inv_date = business_add(delivery, 0)
                merchandise = sum(row[4] for row in lines)
                freight = 75000 if rng["invoices"].random() < s["freight_rate"] else 0
                tax = sum(money(row[4] * vat) for row in lines) + money(freight * vat)
                total = merchandise + freight + tax
                emit("invoices", oid, oid, cid, inv_date, period(inv_date), merchandise, freight,
                     tax, total, stamp(inv_date, 12))
                posted_lines = []
                for j, (iid, pid, qty, price, net) in enumerate(lines, 1):
                    line_id += 1
                    history = costs[pid]["actual"]
                    actual = history[bisect.bisect_right(history, (delivery, float("inf"))) - 1][1]
                    emit("invoice_lines", line_id, oid, j, "merchandise", iid, pid, qty, price,
                         qty * price - net, net, money(net * vat), actual, stamp(inv_date, 12))
                    posted_lines.append((line_id, qty, net, actual))
                if freight:
                    line_id += 1
                    emit("invoice_lines", line_id, oid, 4, "freight", None, None, 1, freight,
                         0, freight, money(freight * vat), None, stamp(inv_date, 12))
                paid = inv_date + timedelta(days=customers[cid])
                if paid < horizon.date() - timedelta(days=1):
                    payment_candidates.append((oid, paid, total))
                if not end_count <= pos < end_count + ret_count:
                    continue
                return_id += 1
                rp = pos - end_count
                late = rp >= int(ret_count * (1 - s["backdated_return_share"]))
                received = month.replace(day=monthrange(month.year, month.month)[1]) if late else month.replace(day=12)
                if tail:
                    received = month.replace(day=7)
                following = month_add(month, 1)
                post = business_day(following, s["credit_batch_business_days"][rp % 3]) if late else business_add(received, 3)
                if tail:
                    post = business_add(received, 3)
                credited = stamp(post, 14) <= horizon
                emit("returns", return_id, oid, cid, received,
                     ("damaged", "expired", "wrong_item", "overstock", "quality")[int(rng["returns"].random() * 5)],
                     "credited" if credited else "received", stamp(received, 13))
                credit_amount = reversal = 0
                for lid, qty, net, actual in posted_lines:
                    ri_id += 1
                    returned = money(qty * s["return_quantity_fraction"])
                    emit("return_items", ri_id, return_id, lid, returned, stamp(received, 13))
                    credit_amount += money(Decimal(net) * returned / qty)
                    reversal += returned * actual
                if credited:
                    credit_id += 1
                    cvat = money(credit_amount * vat)
                    emit("credit_notes", credit_id, return_id, oid, cid, post, period(received),
                         credit_amount, cvat, credit_amount + cvat, reversal, stamp(post, 14))
        if n["payments"] > 2 * len(payment_candidates):
            raise ValueError("Payment count exceeds available one/two-instalment settlements")
        for index, (invoice_id, paid, total) in enumerate(payment_candidates):
            pieces = n["payments"] * (index + 1) // len(payment_candidates) - n["payments"] * index // len(payment_candidates)
            settlement = total // 2 if rng["payments"].random() < .08 else total
            for part in range(pieces):
                payment_id += 1
                amount = settlement * (part + 1) // pieces - settlement * part // pieces
                day = paid + timedelta(days=part)
                emit("payments", payment_id, invoice_id, day, amount, "bank_transfer", stamp(day, 14))
    return counts


def schema_sql(defer_foreign_keys=False):
    return "\n".join(f"CREATE SCHEMA {s};" for s in ("core", "finance", "analytics", "management")) + "\n" + "\n".join(
        f"CREATE TABLE core.{table} (" +
        (re.sub(r" REFERENCES core\.\w+\(\w+\)", "", TABLES[table]) if defer_foreign_keys else TABLES[table]) + ");"
        for table in CORE_ORDER
    ) + SURFACE_DDL


def validate_foreign_keys(conn):
    # ALTER validates each relationship as a set after COPY, avoiding row-trigger
    # overhead during the load. The committed PostgreSQL schema retains every FK.
    for table in CORE_ORDER:
        for column in TABLES[table].split(", "):
            match = re.search(r"REFERENCES (core\.\w+)\((\w+)\)", column)
            if match:
                conn.execute(f"ALTER TABLE core.{table} ADD FOREIGN KEY ({column.split()[0]}) REFERENCES {match[1]}({match[2]})")


# Each assessment-visible query is a single-run operational artifact bound to
# exactly these parameters. The generator materializes history by executing
# that same committed text once per close, per pack run and per nightly load.
SURFACE_PARAMETERS = {
    "finance_revenue.sql": ("period", "closed_at"),
    "board_pack.sql": ("period", "generated_at"),
    "sales_dashboard.sql": ("run_date", "loaded_at"),
}


def surface_sql(name):
    """The committed operational query, byte for byte; it is also the evidence file."""
    return (SOURCE / name).read_text(encoding="utf-8")


def bind(name):
    """Executable form of the same text: each :parameter becomes a driver placeholder."""
    text = surface_sql(name).replace("%", "%%")
    for parameter in SURFACE_PARAMETERS[name]:
        pattern = rf":{parameter}\b"
        if not re.search(pattern, text):
            raise ValueError(f"{name} must bind :{parameter}")
        text = re.sub(pattern, f"%({parameter})s", text)
    return text


def statements(text):
    """(first keyword, statement) pairs of a script; comments stay attached."""
    result = []
    for chunk in text.split(";\n"):
        body = [line.strip() for line in chunk.strip().splitlines()
                if line.strip() and not line.strip().startswith("--")]
        if body:
            result.append((body[0].split()[0].upper(), chunk.strip()))
    return result


def materialize(conn, cfg):
    day = calendar(cfg)[0][0] + timedelta(days=1)
    horizon = instant(cfg["scenario"]["observation_at"])
    script = statements(bind("sales_dashboard.sql"))
    refresh = [text for keyword, text in script if keyword in ("DELETE", "INSERT")]
    view = [text for keyword, text in script if keyword == "CREATE"]
    if len(refresh) != 2 or len(view) != 1:
        raise ValueError("sales_dashboard.sql must hold the nightly refresh and the view")
    delivered = {row[0] for row in conn.execute("SELECT DISTINCT delivery_date FROM core.orders WHERE status='delivered'").fetchall()}
    # Historical replay of the nightly job: the committed refresh runs once per
    # calendar day for the previous day's deliveries, stamped with that run's
    # completion time. Days without deliveries would load nothing and are skipped.
    while stamp(day, 2, 10) <= horizon:
        run_date = day - timedelta(days=1)
        if run_date in delivered:
            for statement in refresh:
                conn.execute(statement, {"run_date": run_date, "loaded_at": stamp(day, 2, 10)})
        day += timedelta(days=1)
    conn.execute(view[0])
    for month, board, close in calendar(cfg):
        # One pack run per month at its snapshot instant; one close per period.
        conn.execute("INSERT INTO management.board_kpi_monthly " + bind("board_pack.sql"),
                     {"period": period(month), "generated_at": board})
        conn.execute("INSERT INTO finance.monthly_pnl_extract " + bind("finance_revenue.sql"),
                     {"period": period(month), "closed_at": close})
    conn.execute(COMMENTS)
    day = calendar(cfg)[0][0] + timedelta(days=1)
    # The append-only T+1 fact retains its original load timestamp.
    daily = dict(conn.execute("SELECT CAST(loaded_at AS DATE), COUNT(*) FROM analytics.delivered_sales GROUP BY 1").fetchall())
    jobs = []
    while stamp(day, 2, 10) <= horizon:
        jobs.append(("refresh_delivered_sales", period(day - timedelta(days=1)), stamp(day, 2), stamp(day, 2, 10), "success", daily.get(day, 0)))
        day += timedelta(days=1)
    for month, board, close in calendar(cfg):
        jobs.extend([("board_pack_monthly", period(month), board - timedelta(minutes=5), board, "success", 3),
                     ("finance_close", period(month), close - timedelta(minutes=10), close, "success", 1)])
    ordered_jobs = sorted(jobs, key=lambda r: (r[2], r[0]))
    # All text here is fixed job vocabulary or ISO dates from the calendar.
    job_values = [f"('{job}', '{p}', TIMESTAMP '{begin}', TIMESTAMP '{end}', 'success', {count})"
                  for job, p, begin, end, status, count in ordered_jobs]
    conn.execute("INSERT INTO analytics.etl_job_runs VALUES " + ",".join(job_values))


def write_evidence(conn, cfg, directory):
    directory.mkdir(parents=True, exist_ok=True)
    expected = {"finance_revenue.sql", "sales_dashboard.sql", "board_pack.sql", "august_board_pack.csv",
                "finance_close_notes.md", "sales_dashboard_notes.md", "board_pack_handover.md"}
    if set(p.name for p in directory.iterdir()) - expected:
        raise ValueError("Evidence directory contains files outside SC-12")
    for name in sorted(expected - {"august_board_pack.csv"}):
        # Evidence is the committed source verbatim; nothing is rendered into it.
        (directory / name).write_text((SOURCE / name).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    with (directory / "august_board_pack.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("period", "kpi", "value", "generated_at"))
        writer.writerows(conn.execute("SELECT period,kpi,value,generated_at FROM management.board_kpi_monthly WHERE period=%s ORDER BY kpi", (cfg["scenario"]["audit_period"],)).fetchall())


def generate(cfg, profile, data_dir=None, truth_dir=None):
    import psycopg
    from benchmark.scenario.reconcile import verify_scenario, manifest

    data_dir = Path(data_dir or ROOT / "benchmark/data")
    truth_dir = Path(truth_dir or ROOT / cfg["generation"]["ground_truth_dir"])
    if data_dir.resolve() in truth_dir.resolve().parents or truth_dir.resolve() in data_dir.resolve().parents or data_dir.resolve() == truth_dir.resolve():
        raise ValueError("Ground truth must be separate from assessment-visible output")
    dsn = os.environ.get(cfg["postgresql"]["dsn_env_var"])
    if not dsn:
        raise ValueError(f"Set {cfg['postgresql']['dsn_env_var']} to a disposable local PostgreSQL database")
    counts = generate_core(cfg, profile, data_dir / "core")
    with psycopg.connect(dsn) as conn:
        # Do not replace an existing Northstar or unrelated schema implicitly.
        existing = conn.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('core','finance','analytics','management')").fetchall()
        if existing:
            raise ValueError("Target must be clean: use a new disposable database (existing schemas preserved)")
        conn.execute("SET TIME ZONE 'Asia/Jakarta'")
        conn.execute(schema_sql(defer_foreign_keys=True))
        for table in CORE_ORDER:
            with conn.cursor().copy(f"COPY core.{table} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)") as copy:
                with (data_dir / "core" / f"{table}.csv").open("rb") as source:
                    while block := source.read(1024 * 1024):
                        copy.write(block)
        validate_foreign_keys(conn)
        conn.execute("CREATE INDEX ON core.credit_notes(accounting_period,created_at)")
        conn.execute("CREATE INDEX ON core.invoices(accounting_period)")
        conn.execute("CREATE INDEX ON core.orders(delivery_date)")
        conn.execute("ANALYZE")
        materialize(conn, cfg)
        write_evidence(conn, cfg, data_dir / "evidence")
        result = verify_scenario(conn, cfg)
        truth = manifest(conn, cfg, profile, counts, result)
        truth_dir.mkdir(parents=True, exist_ok=True)
        (truth_dir / f"{profile}.json").write_text(json.dumps(truth, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    return truth


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "demo"), default="demo")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--truth-dir", type=Path)
    args = parser.parse_args()
    result = generate(load_config(args.config, args.profile), args.profile, args.data_dir, args.truth_dir)
    print(json.dumps({"profile": args.profile, "values": result["values"], "materiality": result["materiality"]}, indent=2))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    main()
