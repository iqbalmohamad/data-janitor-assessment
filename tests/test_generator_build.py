"""Pure-Python coverage of the generated dataset (no database required).

Covers assignment section 10.1 (generation completes from clean state),
lifecycle coherence (SC-6/SC-7), the SC-14 materiality targets recomputed
independently from the raw rows, R_period = R_early + R_late with the
correct category assignment, and byte-level determinism of the build.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

AUDIT = "2026-08"
SNAPSHOT = datetime.fromisoformat("2026-09-02T08:15:00+07:00")
CLOSE = datetime.fromisoformat("2026-09-07T17:30:00+07:00")
HORIZON = datetime.fromisoformat("2026-09-08T09:00:00+07:00")
LAST_BUSINESS_DATE = date(2026, 9, 7)


def period(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def rows(ds, name):
    return ds.tables[name]


def by_id(ds, name):
    return {r[0]: r for r in ds.tables[name]}


# ---------------------------------------------------------------------------
# Scale and generation completion
# ---------------------------------------------------------------------------


def test_smoke_generation_completes_with_configured_scale(smoke_dataset, config):
    scale = config["scale"]["smoke"]
    assert len(rows(smoke_dataset, "core.customers")) == scale["customers"]
    assert len(rows(smoke_dataset, "core.products")) == scale["products"]
    assert len(rows(smoke_dataset, "core.orders")) == scale["orders"]
    assert len(rows(smoke_dataset, "core.returns")) == scale["returns"]
    # derived-mean targets, not exact counts (SC-14: configuration, not a
    # success criterion)
    assert abs(len(rows(smoke_dataset, "core.order_items")) - scale["order_items"]) <= (
        scale["order_items"] * 0.10
    )
    assert abs(len(rows(smoke_dataset, "core.payments")) - scale["payments"]) <= (
        scale["payments"] * 0.15
    )


def test_determinism_same_seed_same_bytes(gen, config, smoke_dataset):
    again = gen.build_dataset(config, "smoke")
    assert gen.dataset_fingerprint(smoke_dataset) == gen.dataset_fingerprint(again)


# ---------------------------------------------------------------------------
# Lifecycle coherence (SC-6)
# ---------------------------------------------------------------------------


def test_order_lifecycle(smoke_dataset):
    customers = by_id(smoke_dataset, "core.customers")
    n_open = n_cancelled = n_delivered = 0
    for o in rows(smoke_dataset, "core.orders"):
        oid, cid, od, req, status, delivery, cancelled, created_at = o
        assert cid in customers
        assert customers[cid][9].date() <= od  # customer existed first
        assert req >= od
        assert created_at.date() == od
        assert created_at <= HORIZON
        if status == "cancelled":
            n_cancelled += 1
            assert delivery is None
            assert cancelled is not None and cancelled >= od
        elif status == "delivered":
            n_delivered += 1
            assert cancelled is None
            assert delivery is not None
            assert delivery > od
            assert delivery.weekday() != 6  # no Sunday deliveries
            assert delivery <= LAST_BUSINESS_DATE
        else:
            assert status == "open"
            n_open += 1
            assert delivery is None and cancelled is None
    total = n_open + n_cancelled + n_delivered
    assert total == len(rows(smoke_dataset, "core.orders"))
    assert 0.01 <= n_cancelled / total <= 0.05
    assert n_open > 0  # realistic open tail at the horizon


def test_invoices_one_per_delivered_order_with_posting_lag(smoke_dataset):
    orders = by_id(smoke_dataset, "core.orders")
    seen_orders = set()
    for inv in rows(smoke_dataset, "core.invoices"):
        invoice_id, oid, cid, inv_date, acc_period, merch, freight, vat, total, created = inv
        assert oid not in seen_orders  # exactly one invoice per order
        seen_orders.add(oid)
        o = orders[oid]
        assert o[4] == "delivered"
        assert o[1] == cid
        delivery = o[5]
        assert delivery <= inv_date <= delivery + timedelta(days=7)
        assert inv_date.weekday() < 5  # invoices post Mon-Fri
        assert acc_period == period(inv_date)
        assert total == merch + freight + vat
        assert created <= HORIZON
    # every delivered order is invoiced unless its posting window crosses
    # the horizon (recent deliveries may be unbilled at observation)
    for o in rows(smoke_dataset, "core.orders"):
        if o[4] == "delivered" and o[0] not in seen_orders:
            assert o[5] >= LAST_BUSINESS_DATE - timedelta(days=6)


def test_invoice_lines_mirror_order_items(smoke_dataset):
    items = by_id(smoke_dataset, "core.order_items")
    invoices = by_id(smoke_dataset, "core.invoices")
    merch_sums: dict[int, int] = {}
    freight_sums: dict[int, int] = {}
    vat_sums: dict[int, int] = {}
    for line in rows(smoke_dataset, "core.invoice_lines"):
        (line_id, invoice_id, line_no, line_type, order_item_id, product_id,
         qty, unit_price, discount, net, vat, cost) = line
        if line_type == "merchandise":
            item = items[order_item_id]
            assert item[2] == product_id
            assert item[3] == qty
            assert item[4] == unit_price
            assert item[6] == net  # net_amount = original line_net_amount
            assert discount == qty * unit_price - net
            assert cost is not None and cost > 0
            merch_sums[invoice_id] = merch_sums.get(invoice_id, 0) + net
        else:
            assert line_type == "freight"
            assert order_item_id is None and product_id is None and cost is None
            freight_sums[invoice_id] = freight_sums.get(invoice_id, 0) + net
        vat_sums[invoice_id] = vat_sums.get(invoice_id, 0) + vat
    for invoice_id, inv in invoices.items():
        assert inv[5] == merch_sums.get(invoice_id, 0)
        assert inv[6] == freight_sums.get(invoice_id, 0)
        assert inv[7] == vat_sums.get(invoice_id, 0)


def test_unit_cost_actual_matches_cost_history_at_delivery(smoke_dataset):
    orders = by_id(smoke_dataset, "core.orders")
    invoices = by_id(smoke_dataset, "core.invoices")
    history: dict[tuple[int, str], list] = {}
    for r in rows(smoke_dataset, "core.product_cost_history"):
        history.setdefault((r[1], r[2]), []).append((r[3], r[4]))
    for hist in history.values():
        hist.sort()

    def cost_at(pid, cost_type, day):
        value = None
        for eff, val in history[(pid, cost_type)]:
            if eff <= day:
                value = val
        return value

    for line in rows(smoke_dataset, "core.invoice_lines"):
        if line[3] != "merchandise":
            continue
        delivery = orders[invoices[line[1]][1]][5]
        assert line[11] == cost_at(line[5], "actual", delivery)


def test_standard_cost_changes_only_at_semiannual_revisions(smoke_dataset):
    products = by_id(smoke_dataset, "core.products")
    latest_std: dict[int, tuple] = {}
    for r in rows(smoke_dataset, "core.product_cost_history"):
        rid, pid, cost_type, eff, cost, source, created = r
        assert cost > 0
        assert created <= HORIZON
        if cost_type == "standard":
            assert source == "pricing_team"
            if pid not in latest_std or eff > latest_std[pid][0]:
                latest_std[pid] = (eff, cost)
            # revisions happen on 1 Jan / 1 Jul; the initial row may sit on
            # the product's creation date instead
            if not (eff.day == 1 and eff.month in (1, 7)):
                assert products[pid][8].date() == eff
            assert period(eff) != AUDIT  # no standard change inside August 2026
        else:
            assert cost_type == "actual"
            assert source == "purchasing"
    for pid, (eff, cost) in latest_std.items():
        assert products[pid][6] == cost  # products.standard_cost mirrors latest


def test_returns_and_credit_notes_lifecycle(smoke_dataset):
    orders = by_id(smoke_dataset, "core.orders")
    invoices = by_id(smoke_dataset, "core.invoices")
    lines = by_id(smoke_dataset, "core.invoice_lines")
    returns = by_id(smoke_dataset, "core.returns")
    items_by_return: dict[int, list] = {}
    for ri in rows(smoke_dataset, "core.return_items"):
        items_by_return.setdefault(ri[1], []).append(ri)

    credited = set()
    for cr in rows(smoke_dataset, "core.credit_notes"):
        (cn_id, return_id, invoice_id, cid, posting, acc_period, merch, vat,
         total, cogs, created) = cr
        assert return_id not in credited  # one credit note per return
        credited.add(return_id)
        ret = returns[return_id]
        assert ret[1] == invoice_id and ret[2] == cid
        received = ret[3]
        assert posting > received
        assert created.date() == posting
        assert total == merch + vat
        # amount semantics (SC-7): original net unit price and original cost
        exp_merch = exp_cogs = 0
        for ri in items_by_return[return_id]:
            line = lines[ri[2]]
            assert line[1] == invoice_id
            assert 1 <= ri[3] <= line[6]  # qty_returned <= original qty
            exp_merch += (ri[3] * line[9] + line[6] // 2) // line[6]
            exp_cogs += ri[3] * line[11]
        assert merch == exp_merch
        assert cogs == exp_cogs
        # period semantics (SC-5/SC-6): a return received on or before the
        # last day of P and credited by P's close carries period P
        assert acc_period == period(received)

    for ret in rows(smoke_dataset, "core.returns"):
        return_id, invoice_id, cid, received, reason, status, created = ret
        delivery = orders[invoices[invoice_id][1]][5]
        assert delivery < received <= delivery + timedelta(days=45)
        assert received.weekday() != 6
        assert status == ("credited" if return_id in credited else "received")
        assert return_id in items_by_return


def test_payments_settle_invoices_without_reconciliation_role(smoke_dataset):
    invoices = by_id(smoke_dataset, "core.invoices")
    paid: dict[int, int] = {}
    for p in rows(smoke_dataset, "core.payments"):
        payment_id, invoice_id, pay_date, amount, method, created = p
        inv = invoices[invoice_id]
        assert pay_date >= inv[3]
        assert pay_date <= LAST_BUSINESS_DATE
        assert amount > 0
        paid[invoice_id] = paid.get(invoice_id, 0) + amount
    for invoice_id, amount in paid.items():
        assert amount <= invoices[invoice_id][8]


def test_horizon_and_created_at_bounds(smoke_dataset, gen):
    for name, table_rows in sorted(smoke_dataset.tables.items()):
        skip = set()
        if name == "core.orders":
            skip = {gen.TABLE_COLUMNS[name].index("requested_delivery_date")}
        for row in table_rows:
            for col, value in enumerate(row):
                if col in skip:
                    continue
                if isinstance(value, datetime):
                    assert value <= HORIZON, f"{name}: {value}"
                elif isinstance(value, date):
                    assert value <= HORIZON.date(), f"{name}: {value}"


# ---------------------------------------------------------------------------
# Independent recomputation of the reconciliation (SC-10) and SC-14 targets
# ---------------------------------------------------------------------------


def recompute(ds):
    """Test-side recomputation of every audit-period quantity from raw rows;
    deliberately independent of generate.compute_expected."""
    orders = by_id(ds, "core.orders")
    invoices = by_id(ds, "core.invoices")

    std: dict[int, list] = {}
    for r in rows(ds, "core.product_cost_history"):
        if r[2] == "standard":
            std.setdefault(r[1], []).append((r[3], r[4]))
    for hist in std.values():
        hist.sort()

    def std_at(pid, day):
        value = None
        for eff, val in std[pid]:
            if eff <= day:
                value = val
        return value

    q = {k: 0 for k in ("g_post", "k_post", "d1", "d2", "k1", "k2", "dsv", "k_std")}
    for line in rows(ds, "core.invoice_lines"):
        if line[3] != "merchandise":
            continue
        inv = invoices[line[1]]
        delivery = orders[inv[1]][5]
        acc, dp = inv[4], period(delivery)
        value, cost = line[9], line[6] * line[11]
        if acc == AUDIT:
            q["g_post"] += value
            q["k_post"] += cost
            if dp == "2026-07":
                q["d2"] += value
                q["k2"] += cost
        if dp == AUDIT and acc != AUDIT:
            q["d1"] += value
            q["k1"] += cost

    items_by_order: dict[int, list] = {}
    for it in rows(ds, "core.order_items"):
        items_by_order.setdefault(it[1], []).append(it)
    for o in rows(ds, "core.orders"):
        if o[4] == "delivered" and period(o[5]) == AUDIT:
            for it in items_by_order.get(o[0], []):
                q["dsv"] += it[6]
                q["k_std"] += it[3] * std_at(it[2], o[5])

    c = {k: 0 for k in ("c_period", "c_late", "c_seen", "vat_seen", "vat_late",
                        "r_period", "r_early", "r_late")}
    for cr in rows(ds, "core.credit_notes"):
        if cr[5] != AUDIT:
            continue
        c["c_period"] += cr[6]
        c["r_period"] += cr[9]
        if cr[10] <= SNAPSHOT:
            c["c_seen"] += cr[6]
            c["vat_seen"] += cr[7]
            c["r_early"] += cr[9]
        else:
            c["c_late"] += cr[6]
            c["vat_late"] += cr[7]
            c["r_late"] += cr[9]

    out = q | c
    out["rnmr"] = out["g_post"] - out["c_period"]
    out["arc"] = out["k_post"] - out["r_period"]
    out["fgm"] = out["rnmr"] - out["arc"]
    out["cm"] = out["dsv"] - out["k_std"]
    out["k_act"] = out["k_post"] + out["k1"] - out["k2"]
    out["br"] = out["dsv"] - (out["c_seen"] + out["vat_seen"])
    out["bgm"] = out["br"] - out["k_std"]
    return out


def test_reconciliation_identities_and_bridges(smoke_dataset):
    q = recompute(smoke_dataset)
    # structural identities (SC-10.1)
    assert q["dsv"] == q["g_post"] + q["d1"] - q["d2"]
    assert q["c_period"] == q["c_seen"] + q["c_late"]
    assert q["r_period"] == q["r_early"] + q["r_late"]

    # revenue bridges (SC-10.2)
    assert q["rnmr"] + (q["d1"] - q["d2"]) + q["c_period"] == q["dsv"]
    assert (
        q["rnmr"] + (q["d1"] - q["d2"]) + q["c_late"] - q["vat_seen"] == q["br"]
    )
    # gross margin bridges (SC-10.2)
    assert (
        q["fgm"]
        + (q["dsv"] - q["rnmr"])
        - (q["k1"] - q["k2"])
        - (q["k_std"] - q["k_act"])
        - q["r_period"]
        == q["cm"]
    )
    assert (
        q["fgm"]
        + (q["br"] - q["rnmr"])
        - (q["k1"] - q["k2"])
        - (q["k_std"] - q["k_act"])
        - q["r_late"]
        - q["r_early"]
        == q["bgm"]
    )


def test_r_split_categories_follow_snapshot_and_board_bridge(gen, smoke_dataset):
    """R_early is defect, R_late is timing, and the split must be driven by
    the same snapshot predicate as the credit split (SC-10.2 / SC-18.5)."""
    q = recompute(smoke_dataset)
    manifest = gen.build_ground_truth(smoke_dataset)
    gm_board = {b["line"]: b for b in manifest["bridges"]["gross_margin_finance_to_board"]}
    assert gm_board["cogs_reversal_on_credits_after_snapshot"]["category"] == "timing"
    assert gm_board["cogs_reversal_on_credits_after_snapshot"]["amount"] == -q["r_late"]
    assert gm_board["cogs_not_reversed_on_credits_seen_by_board"]["category"] == "defect"
    assert gm_board["cogs_not_reversed_on_credits_seen_by_board"]["amount"] == -q["r_early"]
    # the same amount R_period is a legitimate definition difference on the
    # Sales bridge (SC-10.2 teaching point)
    gm_sales = {b["line"]: b for b in manifest["bridges"]["gross_margin_finance_to_sales"]}
    assert gm_sales["no_cogs_reversal_consistent_with_gross_revenue"]["category"] == "definition"
    assert gm_sales["no_cogs_reversal_consistent_with_gross_revenue"]["amount"] == -q["r_period"]
    # timing and defect attribution use one shared split
    rev_board = {b["line"]: b for b in manifest["bridges"]["revenue_finance_to_board"]}
    assert rev_board["back_dated_credit_notes_after_snapshot"]["amount"] == q["c_late"]
    assert rev_board["vat_inclusive_credit_deduction"]["amount"] == -q["vat_seen"]
    # every bridge line carries exactly one approved category
    for bridge in manifest["bridges"].values():
        total = 0
        for line in bridge:
            assert line["category"] in {"definition", "timing", "cost_basis", "defect", "by_line"}
            total += line["amount"]
        assert isinstance(total, int)


def test_bridge_sums_reproduce_surface_deltas(gen, smoke_dataset):
    q = recompute(smoke_dataset)
    manifest = gen.build_ground_truth(smoke_dataset)
    b = manifest["bridges"]
    assert sum(x["amount"] for x in b["revenue_finance_to_sales"]) == q["dsv"] - q["rnmr"]
    assert sum(x["amount"] for x in b["revenue_finance_to_board"]) == q["br"] - q["rnmr"]
    assert sum(x["amount"] for x in b["gross_margin_finance_to_sales"]) == q["cm"] - q["fgm"]
    assert sum(x["amount"] for x in b["gross_margin_finance_to_board"]) == q["bgm"] - q["fgm"]


def test_materiality_targets_sc14(smoke_dataset, config):
    mat = config["scenario"]["materiality"]
    q = recompute(smoke_dataset)
    rnmr = q["rnmr"]
    lo, hi = mat["c_period_pct_of_rnmr"]
    assert lo <= 100 * q["c_period"] / rnmr <= hi
    assert q["c_late"] / q["c_period"] >= mat["c_late_min_share_of_c_period"]
    assert 100 * q["d1"] / rnmr >= mat["d1_min_pct_of_rnmr"]
    assert 100 * q["d2"] / rnmr >= mat["d2_min_pct_of_rnmr"]
    assert 100 * abs(q["k_std"] - q["k_act"]) / q["k_act"] >= mat["cost_basis_min_pct_of_k_act"]
    min_rev = mat["revenue_pairwise_min_pct_of_rnmr"] / 100 * rnmr
    assert abs(q["rnmr"] - q["dsv"]) >= min_rev
    assert abs(q["rnmr"] - q["br"]) >= min_rev
    assert abs(q["dsv"] - q["br"]) >= min_rev
    assert len({q["rnmr"], q["dsv"], q["br"]}) == 3
    fgm_pct = 100 * q["fgm"] / q["rnmr"]
    cm_pct = 100 * q["cm"] / q["dsv"]
    bgm_pct = 100 * q["bgm"] / q["br"]
    min_pp = mat["margin_pairwise_min_pp"]
    assert abs(fgm_pct - cm_pct) >= min_pp
    assert abs(fgm_pct - bgm_pct) >= min_pp
    assert abs(cm_pct - bgm_pct) >= min_pp
    lo, hi = mat["fgm_pct_of_rnmr_band"]
    assert lo <= fgm_pct <= hi


def test_return_rate_and_audit_cost_change_share(smoke_dataset, config):
    delivered = sum(1 for o in rows(smoke_dataset, "core.orders") if o[4] == "delivered")
    share = 100 * len(rows(smoke_dataset, "core.returns")) / delivered
    assert 5.0 <= share <= 10.0  # SC-6

    aug_products = set()
    items_by_order: dict[int, list] = {}
    for it in rows(smoke_dataset, "core.order_items"):
        items_by_order.setdefault(it[1], []).append(it)
    for o in rows(smoke_dataset, "core.orders"):
        if o[4] == "delivered" and period(o[5]) == AUDIT:
            for it in items_by_order.get(o[0], []):
                aug_products.add(it[2])
    changed = {
        r[1]
        for r in rows(smoke_dataset, "core.product_cost_history")
        if r[2] == "actual" and period(r[3]) == AUDIT
    }
    share = 100 * len(changed & aug_products) / len(aug_products)
    lo, hi = config["scenario"]["materiality"]["aug_actual_cost_change_product_share_band_pct"]
    assert lo <= share <= hi  # SC-8


def test_credit_split_predicates_coincide(smoke_dataset):
    """SC-10.1: the credits the board saw are exactly those posted on or
    before the first business day after period end; the late ones are
    exactly the 2-4 September postings."""
    for cr in rows(smoke_dataset, "core.credit_notes"):
        if cr[5] != AUDIT:
            continue
        posting = cr[4]
        if cr[10] <= SNAPSHOT:
            assert posting <= date(2026, 9, 1)
        else:
            assert date(2026, 9, 2) <= posting <= date(2026, 9, 4)
        assert cr[10] <= CLOSE  # all period credits exist by the close


def test_job_log_lifecycle(smoke_dataset):
    nightly_dates = set()
    for run in rows(smoke_dataset, "analytics.etl_job_runs"):
        run_id, job, run_for, started, completed, status, rows_written = run
        assert status == "success"  # SC-11: no failed jobs
        assert completed > started
        assert rows_written >= 0
        if job == "refresh_delivered_sales":
            nightly_dates.add(started.date())
        else:
            assert job == "board_pack_monthly"
            assert completed.time().isoformat() == "08:15:00"
            assert rows_written == 3
    # the nightly job ran every single day of the history window
    d = date(2023, 9, 2)
    while d <= date(2026, 9, 8):
        assert d in nightly_dates, f"missing nightly run on {d}"
        d += timedelta(days=1)
