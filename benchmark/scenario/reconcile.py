"""Northstar-only read-only reconciliation from database evidence; no manifest input."""

from decimal import Decimal
import hashlib
import json
from itertools import combinations


def inspect_evidence(conn, p):
    """Read only supplied DB evidence and the period named in the management question."""
    snapshots = conn.execute("SELECT DISTINCT generated_at FROM management.board_kpi_monthly WHERE period=%s", (p,)).fetchall()
    assert len(snapshots) == 1, "The circulated period must identify one Board snapshot"
    snapshot = snapshots[0][0]
    values = {}
    # Independent of all three reporting queries and their materialized facts.
    rows = conn.execute("""
        SELECT i.accounting_period,
               SUBSTRING(CAST(o.delivery_date AS VARCHAR),1,7),
               SUM(l.net_amount), SUM(l.qty*l.unit_cost_actual), SUM(l.qty*h.unit_cost)
        FROM core.invoices i JOIN core.orders o USING(order_id)
        JOIN core.invoice_lines l USING(invoice_id)
        JOIN core.product_cost_history h ON h.product_id=l.product_id AND h.cost_type='standard'
          AND h.effective_from=(SELECT MAX(x.effective_from) FROM core.product_cost_history x
            WHERE x.product_id=l.product_id AND x.cost_type='standard' AND x.effective_from<=o.delivery_date)
        WHERE l.line_type='merchandise' AND
          (i.accounting_period=%s OR SUBSTRING(CAST(o.delivery_date AS VARCHAR),1,7)=%s)
        GROUP BY 1,2
    """, (p, p)).fetchall()
    for key in ("G_post", "K_post", "D1", "D2", "K1", "K2", "K_act", "K_std", "DSV"):
        values[key] = 0
    for posted, delivered, revenue, actual, standard in rows:
        revenue, actual, standard = int(revenue), int(actual), int(standard)
        if posted == p:
            values["G_post"] += revenue
            values["K_post"] += actual
        if delivered == p:
            values["DSV"] += revenue
            values["K_act"] += actual
            values["K_std"] += standard
            if posted != p:
                values["D1"] += revenue
                values["K1"] += actual
        elif posted == p:
            values["D2"] += revenue
            values["K2"] += actual

    # A single split drives both the merchandise and original-cost sides.
    credit_rows = conn.execute("""
        SELECT n.created_at<=%s AS visible,
               SUM(ri.qty_returned*CAST(l.net_amount AS NUMERIC)/l.qty),
               SUM(ri.qty_returned*l.unit_cost_actual)
        FROM core.credit_notes n JOIN core.return_items ri USING(return_id)
        JOIN core.invoice_lines l USING(invoice_line_id)
        WHERE n.accounting_period=%s GROUP BY 1
    """, (snapshot, p)).fetchall()
    split = {bool(visible): (int(merch), int(cost)) for visible, merch, cost in credit_rows}
    early, late = split.get(True, (0, 0)), split.get(False, (0, 0))
    values.update(C_early=early[0], C_late=late[0], C_period=early[0] + late[0],
                  R_early=early[1], R_late=late[1], R_period=early[1] + late[1])
    # VAT is independently reconstructed per document, matching integer-rupiah rounding.
    values["VAT_early"] = int(conn.execute("""
        SELECT COALESCE(SUM(ROUND(c.vat)),0) FROM (
          SELECT n.credit_note_id, SUM(ri.qty_returned*CAST(l.vat_amount AS NUMERIC)/l.qty) AS vat
          FROM core.credit_notes n JOIN core.return_items ri USING(return_id)
          JOIN core.invoice_lines l USING(invoice_line_id)
          WHERE n.accounting_period=%s AND n.created_at<=%s GROUP BY n.credit_note_id
        ) c
    """, (p, snapshot)).fetchone()[0])
    v = values
    v["RNMR"] = v["G_post"] - v["C_period"]
    v["ARC"] = v["K_post"] - v["R_period"]
    v["FGM"] = v["RNMR"] - v["ARC"]
    v["CM"] = v["DSV"] - v["K_std"]
    v["BR"] = v["DSV"] - v["C_early"] - v["VAT_early"]
    v["BGM"] = v["BR"] - v["K_std"]
    v["cost_difference"] = v["K_std"] - v["K_act"]
    for prefix, numerator, denominator in (("finance", "FGM", "RNMR"), ("sales", "CM", "DSV"), ("board", "BGM", "BR")):
        v[prefix + "_margin_pct"] = str((Decimal(v[numerator]) / v[denominator]).quantize(Decimal("0.000000000001")))

    def line(name, category, amount):
        return {"line": name, "category": category, "amount": amount}

    rs = [line("delivery_vs_posting", "definition", v["D1"] - v["D2"]),
          line("gross_of_returns", "definition", v["C_period"])]
    rb = [rs[0], line("credits_after_snapshot", "timing", v["C_late"]),
          line("vat_on_visible_credits", "defect", -v["VAT_early"])]
    cost = [line("cost_period_basis", "definition", -(v["K1"] - v["K2"])),
            line("standard_vs_actual", "cost_basis", -v["cost_difference"])]
    bridges = {
        "revenue_finance_to_sales": rs,
        "revenue_finance_to_board": rb,
        "gross_margin_finance_to_sales": rs + cost + [line("gross_of_returns_cost", "definition", -v["R_period"])],
        "gross_margin_finance_to_board": rb + cost + [line("cost_on_credits_after_snapshot", "timing", -v["R_late"]),
                                                      line("cost_on_visible_credits", "defect", -v["R_early"])],
    }
    for name, begin, end in (("revenue_finance_to_sales", "RNMR", "DSV"), ("revenue_finance_to_board", "RNMR", "BR"),
                             ("gross_margin_finance_to_sales", "FGM", "CM"), ("gross_margin_finance_to_board", "FGM", "BGM")):
        assert v[begin] + sum(row["amount"] for row in bridges[name]) == v[end], name
    assert v["R_period"] == v["R_early"] + v["R_late"]
    assert v["K_act"] == v["K_post"] + v["K1"] - v["K2"]
    f = conn.execute("SELECT net_merchandise_revenue,recognized_cogs,gross_margin,gross_margin_pct FROM finance.monthly_pnl_extract WHERE accounting_period=%s", (p,)).fetchone()
    assert tuple(map(int, f[:3])) == (v["RNMR"], v["ARC"], v["FGM"])
    assert abs(Decimal(str(f[3])) - Decimal(v["finance_margin_pct"])) < Decimal("0.000000000002")
    sales = conn.execute("SELECT SUM(revenue),SUM(cogs_std),SUM(margin) FROM analytics.sales_dashboard_monthly WHERE period=%s", (p,)).fetchone()
    assert tuple(map(int, sales)) == (v["DSV"], v["K_std"], v["CM"])
    board = dict(conn.execute("SELECT kpi,value FROM management.board_kpi_monthly WHERE period=%s", (p,)).fetchall())
    assert int(board["Revenue"]) == v["BR"] and int(board["Gross Margin"]) == v["BGM"]
    assert abs(Decimal(str(board["Gross Margin %"])) - Decimal(v["board_margin_pct"])) < Decimal("0.000000000002")
    return {"values": v, "bridges": bridges}


def verify_scenario(conn, cfg):
    """Generator QA adds contract thresholds; these are not assessor inputs."""
    result = inspect_evidence(conn, cfg["scenario"]["audit_period"])
    result["materiality"] = materiality(result["values"], cfg)
    return result


def materiality(v, cfg):
    t = cfg["materiality"]
    observed = {
        "credit_rnmr": v["C_period"] / v["RNMR"],
        "late_credit_share": v["C_late"] / v["C_period"],
        "D1_rnmr": v["D1"] / v["RNMR"], "D2_rnmr": v["D2"] / v["RNMR"],
        "cost_difference_share": abs(v["cost_difference"]) / v["K_act"],
        "finance_margin": v["FGM"] / v["RNMR"],
    }
    bounds = {"credit_rnmr": (t["credit_rnmr_min"], t["credit_rnmr_max"]),
              "late_credit_share": (t["late_credit_share_min"], 1),
              "D1_rnmr": (t["period_leg_rnmr_min"], 1), "D2_rnmr": (t["period_leg_rnmr_min"], 1),
              "cost_difference_share": (t["cost_difference_min"], 1),
              "finance_margin": (t["finance_margin_min"], t["finance_margin_max"])}
    for a, b in combinations(("RNMR", "DSV", "BR"), 2):
        key = f"revenue_{a}_{b}"
        observed[key] = abs(v[a] - v[b]) / v["RNMR"]
        bounds[key] = (t["pairwise_revenue_rnmr_min"], 1)
    for a, b in combinations(("finance", "sales", "board"), 2):
        key = f"margin_{a}_{b}"
        observed[key] = abs(float(v[a + "_margin_pct"]) - float(v[b + "_margin_pct"]))
        bounds[key] = (t["pairwise_margin_pct_min"], 1)
    for key, actual in observed.items():
        low, high = bounds[key]
        assert low <= actual <= high, f"SC-14 {key}: {actual:.6%} outside [{low:.6%}, {high:.6%}]"
    return {key: {"observed": str(round(observed[key], 12)), "minimum": bounds[key][0], "maximum": bounds[key][1], "pass": True}
            for key in sorted(observed)}


def manifest(conn, cfg, profile, counts, result):
    s = cfg["scenario"]
    v = result["values"]
    surfaces = {}
    for name, obj, concept, r, g, snapshot in (
        ("finance", "finance.monthly_pnl_extract", "RNMR / ARC / FGM", "RNMR", "FGM", s["finance_close_at"]),
        ("sales", "analytics.sales_dashboard_monthly", "DSV / standard cost / CM", "DSV", "CM", s["sales_complete_at"]),
        ("board", "management.board_kpi_monthly", "BR / BGM (hybrid)", "BR", "BGM", s["board_snapshot_at"]),
    ):
        surfaces[name] = {"object": obj, "concept": concept, "snapshot_at": snapshot,
                          "reported": {"revenue": v[r], "gross_margin": v[g], "margin_pct": v[name + "_margin_pct"]}}
    all_counts = dict(counts)
    for table in ("finance.monthly_pnl_extract", "analytics.delivered_sales", "analytics.sales_dashboard_monthly", "analytics.etl_job_runs", "management.board_kpi_monthly"):
        all_counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    scale = {"counts": all_counts}
    surface_hashes = {}
    for table, ordering in (("finance.monthly_pnl_extract", "accounting_period"),
                            ("analytics.delivered_sales", "order_item_id"),
                            ("analytics.sales_dashboard_monthly", "period,sales_region"),
                            ("analytics.etl_job_runs", "started_at,job_name"),
                            ("management.board_kpi_monthly", "period,kpi")):
        digest = hashlib.sha256()
        cursor = conn.execute(f"SELECT * FROM {table} ORDER BY {ordering}")
        while rows := cursor.fetchmany(10000):
            for row in rows:
                digest.update((json.dumps(row, default=str, separators=(",", ":")) + "\n").encode("utf-8"))
        surface_hashes[table] = digest.hexdigest()
    for name, query in {
        "august_deliveries": "SELECT COUNT(*) FROM core.orders WHERE SUBSTRING(CAST(delivery_date AS VARCHAR),1,7)=%s",
        "august_invoices": "SELECT COUNT(*) FROM core.invoices WHERE accounting_period=%s",
        "august_credits": "SELECT COUNT(*) FROM core.credit_notes WHERE accounting_period=%s",
        "backdated_credits": "SELECT COUNT(*) FROM core.credit_notes WHERE accounting_period=%s AND SUBSTRING(CAST(posting_date AS VARCHAR),1,7)<>accounting_period",
    }.items():
        scale[name] = conn.execute(query, (s["audit_period"],)).fetchone()[0]
    return {"manifest_version": 2, "scenario": cfg["generation"]["scenario"], "seed": cfg["generation"]["seed"],
            "profile": profile, "audit_period": s["audit_period"],
            "decision_context": "August Management/Board financial-performance P&L and separate Sales commercial performance",
            "timeline": {key: s[key] for key in sorted(s) if key.endswith("_at")},
            "surfaces": surfaces, **result,
            "board_defect": {"description": "VAT-inclusive credit totals deducted from ex-VAT delivery sales; no cost reversal on credits already netted.",
                             "vat_deduction": -v["VAT_early"], "missing_visible_cost_reversal": -v["R_early"]},
            "recommended_basis": {"board_financial_performance_pnl": "Finance RNMR and FGM", "sales_commercial_performance": "Sales DSV and CM",
                                  "board_pack_presentation": "Show Finance P&L and Sales commercial measures separately, clearly labelled, certified after Finance close; retire the hybrid."},
            "supporting_findings": [
                {"finding": "Board snapshot precedes Finance close", "evidence": ["management.board_kpi_monthly.generated_at", "analytics.etl_job_runs", "core.credit_notes", "finance.monthly_pnl_extract.closed_at"]},
                {"finding": "No agreed Board Revenue definition or accountable owner", "evidence": ["board_pack_handover.md", "finance_close_notes.md", "sales_dashboard_notes.md", "analytics.sales_dashboard_monthly.revenue comment", "management.board_kpi_monthly missing comments"]}],
            "scale": scale, "surface_hashes": surface_hashes}


if __name__ == "__main__":
    import argparse
    import os
    import psycopg
    from benchmark.generate import load_config

    parser = argparse.ArgumentParser(description="Read-only Northstar Revenue/Gross Margin reconciliation")
    parser.add_argument("--period", required=True, help="Period named in the management question, YYYY-MM")
    args = parser.parse_args()
    config = load_config()
    with psycopg.connect(os.environ[config["postgresql"]["dsn_env_var"]]) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        print(json.dumps(inspect_evidence(connection, args.period), indent=2, sort_keys=True))
