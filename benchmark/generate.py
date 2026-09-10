"""Deterministic generator for the Northstar Distribution demo environment.

M0 implementation (see ``Current Assignment.md`` and the binding Scenario
Contract in ``benchmark/README.md``, Part II). Generates the ``core``
operational lifecycle in dependency order, loads it into the canonical
PostgreSQL target, materializes the three reporting surfaces via their own
SQL (``benchmark/scenario/*.sql``), attaches the fragmented evidence, and
writes the hidden ground-truth manifest last.

Every figure on every surface is a product of core data plus that
surface's SQL plus the appropriate snapshot -- nothing is hardcoded,
including the disagreement. The generator independently recomputes every
reconciliation quantity from the in-memory data and refuses to emit output
when the PostgreSQL-materialized surfaces or the SC-14 materiality targets
do not match.

Determinism: all randomness comes from per-purpose ``random.Random``
streams seeded from the canonical seed in ``benchmark/config/benchmark.toml``
(never hardcoded here); all instants derive from configured scenario
parameters; no wall-clock reads.

Usage:
    NORTHSTAR_DATABASE_URL=postgresql://... python benchmark/generate.py --profile smoke
"""

from __future__ import annotations

import argparse
import hashlib
import math
import json
import os
import random
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "benchmark" / "config" / "benchmark.toml"
SCENARIO_DIR = REPO_ROOT / "benchmark" / "scenario"

ONE_DAY = timedelta(days=1)

# Evidence inventory fixed by SC-12.2: exactly these seven files, no more.
EVIDENCE_SOURCE_FILES = [
    "finance_revenue.sql",
    "sales_dashboard.sql",
    "board_pack.sql",
    "finance_close_notes.md",
    "sales_dashboard_notes.md",
    "board_pack_handover.md",
]
EVIDENCE_GENERATED_FILES = ["august_board_pack.csv"]


class GenerationError(RuntimeError):
    """Raised when configuration is invalid or generated output would
    violate a Scenario Contract invariant (materiality, coherence,
    surface reproduction)."""


# ---------------------------------------------------------------------------
# Configuration / scenario timeline
# ---------------------------------------------------------------------------


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> dict:
    path = Path(path)
    with path.open("rb") as f:
        config = tomllib.load(f)
    for section in ("generation", "scenario", "postgresql", "scale"):
        if section not in config:
            raise GenerationError(f"benchmark.toml is missing [{section}]")
    for key in ("seed", "as_of_date", "history_years", "ground_truth_dir", "data_dir"):
        if key not in config["generation"]:
            raise GenerationError(f"benchmark.toml [generation] is missing '{key}'")
    scenario_keys = (
        "audit_period",
        "observation_at",
        "utc_offset_hours",
        "vat_rate_pct",
        "board_snapshot_business_day",
        "board_snapshot_time",
        "credit_batch_business_days",
        "close_business_day",
        "close_time",
        "invoice_lag_weights",
        "cancelled_order_rate_pct",
        "return_received_lag_days_max",
        "credit_lag_business_days_max",
        "materiality",
    )
    for key in scenario_keys:
        if key not in config["scenario"]:
            raise GenerationError(f"benchmark.toml [scenario] is missing '{key}'")
    return config


def is_business_day(d: date) -> bool:
    return d.weekday() < 5  # Mon-Fri


def add_business_days(d: date, n: int) -> date:
    """Day 0 is `d` itself when it is a business day, else the next one."""
    while not is_business_day(d):
        d += ONE_DAY
    for _ in range(n):
        d += ONE_DAY
        while not is_business_day(d):
            d += ONE_DAY
    return d


def business_days_of_month(year: int, month: int) -> list[date]:
    d = date(year, month, 1)
    days = []
    while d.month == month:
        if is_business_day(d):
            days.append(d)
        d += ONE_DAY
    return days


def period_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_first(period: str) -> date:
    year, month = int(period[:4]), int(period[5:7])
    return date(year, month, 1)


def next_month_first(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def prev_period(period: str) -> str:
    d = month_first(period)
    last = d - ONE_DAY
    return period_of(last)


def next_period(period: str) -> str:
    return period_of(next_month_first(month_first(period)))


@dataclass(frozen=True)
class PeriodClose:
    period: str
    bd1: date
    snapshot_at: datetime
    batch_days: tuple[date, ...]
    close_at: datetime


@dataclass
class Scenario:
    seed: int
    as_of: date
    history_start: date
    periods: list[str]  # closed periods, oldest first
    open_period: str
    audit_period: str
    observation_at: datetime
    tz: timezone
    vat_pct: int
    invoice_lag_weights: list[int]
    cancelled_rate_pct: int
    return_lag_max: int
    credit_lag_max: int
    materiality: dict
    closes: dict[str, PeriodClose] = field(default_factory=dict)

    def close_for(self, period: str) -> PeriodClose:
        return self.closes[period]


def build_scenario(config: dict) -> Scenario:
    gen, sc = config["generation"], config["scenario"]
    tz = timezone(timedelta(hours=int(sc["utc_offset_hours"])))
    as_of = date.fromisoformat(gen["as_of_date"])
    months = int(gen["history_years"]) * 12
    history_start = as_of
    for _ in range(months):
        last_of_prev = history_start - ONE_DAY
        history_start = date(last_of_prev.year, last_of_prev.month, 1)
    observation_at = datetime.fromisoformat(sc["observation_at"])
    if observation_at.tzinfo is None:
        raise GenerationError("scenario.observation_at must carry a UTC offset")

    periods: list[str] = []
    d = history_start
    while d < as_of:
        periods.append(period_of(d))
        d = next_month_first(d)
    audit_period = sc["audit_period"]
    if periods[-1] != audit_period:
        raise GenerationError(
            f"audit_period {audit_period} must be the last closed period "
            f"before as_of_date (got {periods[-1]})"
        )

    scen = Scenario(
        seed=int(gen["seed"]),
        as_of=as_of,
        history_start=history_start,
        periods=periods,
        open_period=period_of(as_of),
        audit_period=audit_period,
        observation_at=observation_at,
        tz=tz,
        vat_pct=int(sc["vat_rate_pct"]),
        invoice_lag_weights=list(sc["invoice_lag_weights"]),
        cancelled_rate_pct=int(sc["cancelled_order_rate_pct"]),
        return_lag_max=int(sc["return_received_lag_days_max"]),
        credit_lag_max=int(sc["credit_lag_business_days_max"]),
        materiality=dict(sc["materiality"]),
    )

    snap_t = time.fromisoformat(sc["board_snapshot_time"])
    close_t = time.fromisoformat(sc["close_time"])
    for period in periods + [scen.open_period]:
        nm = next_month_first(month_first(period))
        bds = business_days_of_month(nm.year, nm.month)
        batch = tuple(bds[i - 1] for i in sc["credit_batch_business_days"])
        scen.closes[period] = PeriodClose(
            period=period,
            bd1=bds[0],
            snapshot_at=datetime.combine(
                bds[sc["board_snapshot_business_day"] - 1], snap_t
            ).replace(tzinfo=tz),
            batch_days=batch,
            close_at=datetime.combine(bds[sc["close_business_day"] - 1], close_t).replace(
                tzinfo=tz
            ),
        )
    return scen


# ---------------------------------------------------------------------------
# Deterministic randomness helpers (stable RNG primitives only)
# ---------------------------------------------------------------------------


def stream(seed: int, name: str) -> random.Random:
    return random.Random(f"{seed}:{name}")


def rint(rng: random.Random, lo: int, hi: int) -> int:
    """Uniform integer in [lo, hi] from rng.random() (version-stable)."""
    return lo + int(rng.random() * (hi - lo + 1))


def rnorm(rng: random.Random) -> float:
    """Standard normal via Box-Muller from rng.random() (version-stable)."""
    u1 = 1.0 - rng.random()
    u2 = rng.random()
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


class Weighted:
    """Deterministic weighted chooser driven by rng.random()."""

    def __init__(self, values, weights):
        if len(values) != len(weights):
            raise GenerationError("weighted chooser: length mismatch")
        self.values = list(values)
        self.cum = []
        total = 0.0
        for w in weights:
            total += float(w)
            self.cum.append(total)
        self.total = total

    def pick(self, rng: random.Random):
        r = rng.random() * self.total
        lo, hi = 0, len(self.cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if r < self.cum[mid]:
                hi = mid
            else:
                lo = mid + 1
        return self.values[lo]


def largest_remainder(total: int, weights: list[float]) -> list[int]:
    s = sum(weights)
    raw = [total * w / s for w in weights]
    base = [int(x) for x in raw]
    rem = total - sum(base)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - base[i]), i))
    for i in order[:rem]:
        base[i] += 1
    return base


def rhu(numer: int, denom: int) -> int:
    """Round-half-up integer division for non-negative operands."""
    return (numer + denom // 2) // denom


def pct_of(amount: int, pct: int) -> int:
    return rhu(amount * pct, 100)


def day_time(rng: random.Random, d: date, tz: timezone, h_lo: int, h_hi: int) -> datetime:
    h = rint(rng, h_lo, h_hi - 1)
    m = rint(rng, 0, 59)
    s = rint(rng, 0, 59)
    return datetime.combine(d, time(h, m, s)).replace(tzinfo=tz)


# ---------------------------------------------------------------------------
# Fictional word lists (written for this project; every combination is
# synthetic -- SC-16 / Part III synthetic-data rules)
# ---------------------------------------------------------------------------

NAME_CORES = [
    "Makmur", "Sejahtera", "Abadi", "Sentosa", "Mandiri", "Berkah", "Cahaya",
    "Fajar", "Gemilang", "Harapan", "Karya", "Lestari", "Mitra", "Niaga",
    "Prima", "Rejeki", "Sinar", "Surya", "Tirta", "Usaha", "Bintang",
    "Delima", "Kencana", "Mutiara", "Pelangi", "Samudra", "Selaras", "Griya",
    "Arta", "Candra",
]
NAME_TAILS = [
    "Jaya", "Utama", "Perkasa", "Sakti", "Agung", "Baru", "Indah", "Raya",
    "Mulia", "Persada", "Santosa", "Terang", "Buana", "Kembar", "Lima",
]
BRAND_WORDS = [
    "Arunika", "Baskara", "Candani", "Dirgantara", "Elang Mas", "Gitarja",
    "Harsa", "Iswara", "Jelita", "Kirana", "Laksana", "Menara", "Naraya",
    "Oceana", "Pesona", "Ratna", "Sagara", "Taruna", "Wangi Alam", "Zamrud",
]

# (code, label, uom, price band in thousands of rupiah, max order qty)
CATEGORIES = [
    ("BEV", "Beverages", "carton", (90, 320), 60),
    ("SNK", "Snacks", "carton", (70, 260), 50),
    ("INS", "Instant Foods", "carton", (80, 300), 48),
    ("HHC", "Household Care", "box", (60, 420), 36),
    ("PSC", "Personal Care", "box", (90, 520), 30),
    ("STP", "Food Staples", "sack", (140, 900), 24),
    ("DRY", "Dry Goods", "box", (60, 240), 40),
    ("PAP", "Paper Goods", "pack", (50, 200), 44),
]
CATEGORY_ITEMS = {
    "BEV": ["Tea", "Coffee", "Cocoa Drink", "Fruit Syrup", "Mineral Water", "Soda"],
    "SNK": ["Crackers", "Wafer", "Potato Chips", "Roasted Peanuts", "Biscuits"],
    "INS": ["Instant Noodles", "Instant Porridge", "Seasoning Mix", "Instant Soup"],
    "HHC": ["Detergent", "Floor Cleaner", "Dish Soap", "Bleach"],
    "PSC": ["Shampoo", "Bar Soap", "Toothpaste", "Body Wash"],
    "STP": ["Rice", "Cooking Oil", "Sugar", "Wheat Flour"],
    "DRY": ["Dried Noodles", "Canned Fish", "Sweet Soy Sauce", "Chili Sauce"],
    "PAP": ["Facial Tissue", "Paper Towel", "Napkins"],
}
CATEGORY_SIZES = {
    "BEV": ["24x250ml", "12x1L", "6x1.5L", "24x330ml"],
    "SNK": ["20x100g", "12x250g", "40x50g"],
    "INS": ["40x85g", "24x120g", "12x400g"],
    "HHC": ["12x800g", "24x400ml", "6x2L"],
    "PSC": ["24x170ml", "48x90g", "36x120g"],
    "STP": ["20kg", "12x1L", "25kg", "10x1kg"],
    "DRY": ["24x140g", "48x155g", "12x600ml"],
    "PAP": ["36x200s", "24x2R", "48x50s"],
}

# (province, cities, sales_region) -- fictional sales-region groupings over
# public Indonesian geography (SC-1).
GEOGRAPHY = [
    ("DKI Jakarta", ["Jakarta"], "Jawa 1"),
    ("Jawa Barat", ["Bandung", "Bekasi", "Bogor", "Cirebon"], "Jawa 1"),
    ("Banten", ["Tangerang", "Serang"], "Jawa 1"),
    ("Jawa Tengah", ["Semarang", "Surakarta", "Tegal"], "Jawa 2"),
    ("DI Yogyakarta", ["Yogyakarta"], "Jawa 2"),
    ("Jawa Timur", ["Surabaya", "Malang", "Kediri"], "Jawa 2"),
    ("Sumatera Utara", ["Medan", "Pematangsiantar"], "Sumatera"),
    ("Riau", ["Pekanbaru"], "Sumatera"),
    ("Sumatera Selatan", ["Palembang"], "Sumatera"),
    ("Lampung", ["Bandar Lampung"], "Sumatera"),
    ("Sulawesi Selatan", ["Makassar"], "Indonesia Timur"),
    ("Kalimantan Timur", ["Balikpapan", "Samarinda"], "Indonesia Timur"),
    ("Bali", ["Denpasar"], "Indonesia Timur"),
    ("Nusa Tenggara Barat", ["Mataram"], "Indonesia Timur"),
]

SEGMENTS = ["modern_trade", "general_trade", "wholesale", "horeca"]
SEGMENT_WEIGHTS = [15, 45, 25, 15]
SEGMENT_PREFIXES = {
    "modern_trade": (["PT"], [1]),
    "general_trade": (["Toko", "CV", "UD"], [55, 25, 20]),
    "wholesale": (["PT", "CV"], [60, 40]),
    "horeca": (["Hotel", "Restoran", "Katering", "Kafe"], [30, 35, 20, 15]),
}
SEGMENT_TERMS = {
    "modern_trade": ([45, 60], [55, 45]),
    "general_trade": ([14, 30], [45, 55]),
    "wholesale": ([30, 45], [50, 50]),
    "horeca": ([14, 30], [60, 40]),
}
SEGMENT_ORDER_WEIGHT = {
    "modern_trade": 3.5,
    "general_trade": 1.0,
    "wholesale": 2.5,
    "horeca": 0.8,
}
SEGMENT_QTY_FACTOR = {
    "modern_trade": 1.6,
    "general_trade": 1.0,
    "wholesale": 2.2,
    "horeca": 0.7,
}

SEASONALITY = {
    1: 0.94, 2: 0.95, 3: 1.02, 4: 1.06, 5: 1.00, 6: 1.03,
    7: 1.00, 8: 1.02, 9: 1.00, 10: 1.01, 11: 1.03, 12: 1.08,
}


# ---------------------------------------------------------------------------
# Dataset container
# ---------------------------------------------------------------------------

TABLE_COLUMNS = {
    "core.customers": [
        "customer_id", "customer_code", "company_name", "segment", "province",
        "city", "sales_region", "credit_terms_days", "is_active", "created_at",
    ],
    "core.products": [
        "product_id", "sku", "product_name", "category", "uom", "list_price",
        "standard_cost", "is_active", "created_at",
    ],
    "core.product_cost_history": [
        "cost_history_id", "product_id", "cost_type", "effective_from",
        "unit_cost", "source", "created_at",
    ],
    "core.orders": [
        "order_id", "customer_id", "order_date", "requested_delivery_date",
        "status", "delivery_date", "cancelled_date", "created_at",
    ],
    "core.order_items": [
        "order_item_id", "order_id", "product_id", "qty", "unit_price",
        "discount_pct", "line_net_amount",
    ],
    "core.invoices": [
        "invoice_id", "order_id", "customer_id", "invoice_date",
        "accounting_period", "merchandise_amount", "freight_amount",
        "vat_amount", "total_amount", "created_at",
    ],
    "core.invoice_lines": [
        "invoice_line_id", "invoice_id", "line_no", "line_type",
        "order_item_id", "product_id", "qty", "unit_price", "discount_amount",
        "net_amount", "vat_amount", "unit_cost_actual",
    ],
    "core.payments": [
        "payment_id", "invoice_id", "payment_date", "amount", "method",
        "created_at",
    ],
    "core.returns": [
        "return_id", "invoice_id", "customer_id", "received_date",
        "reason_code", "status", "created_at",
    ],
    "core.return_items": [
        "return_item_id", "return_id", "invoice_line_id", "qty_returned",
    ],
    "core.credit_notes": [
        "credit_note_id", "return_id", "invoice_id", "customer_id",
        "posting_date", "accounting_period", "merchandise_amount",
        "vat_amount", "total_amount", "cogs_reversal_amount", "created_at",
    ],
    "analytics.etl_job_runs": [
        "run_id", "job_name", "run_for_period", "started_at", "completed_at",
        "status", "rows_written",
    ],
}


@dataclass
class Dataset:
    scenario: Scenario
    profile: str
    tables: dict = field(default_factory=dict)
    load_schedule: dict = field(default_factory=dict)  # delivery_date -> loaded_at
    expected: dict = field(default_factory=dict)


def dataset_fingerprint(ds: Dataset) -> str:
    h = hashlib.sha256()
    for name in sorted(ds.tables):
        h.update(name.encode())
        for row in ds.tables[name]:
            h.update(repr(row).encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Dataset build (Part III step 2: operational data in dependency order)
# ---------------------------------------------------------------------------


def build_dataset(config: dict, profile: str) -> Dataset:
    scen = build_scenario(config)
    if profile not in config["scale"]:
        raise GenerationError(f"unknown scale profile '{profile}'")
    scale = config["scale"][profile]
    seed = scen.seed
    tz = scen.tz
    horizon = scen.observation_at
    last_business_date = date(2026, 9, 7)  # last full business date before the horizon
    audit = scen.audit_period  # "2026-08"
    audit_first = month_first(audit)
    audit_close = scen.close_for(audit)
    ds = Dataset(scenario=scen, profile=profile)

    # ---- products ---------------------------------------------------------
    rng = stream(seed, "products")
    cat_chooser = Weighted(CATEGORIES, [16, 15, 15, 13, 12, 10, 10, 9])
    n_products = scale["products"]
    products = []  # rows (list) in TABLE_COLUMNS order, standard_cost patched later
    prod_aux = []  # dicts: category, qmax, weight, created (date), base_cost
    used_skus = set()
    for pid in range(1, n_products + 1):
        code, label, uom, (p_lo, p_hi), qmax = cat_chooser.pick(rng)
        brand = BRAND_WORDS[rint(rng, 0, len(BRAND_WORDS) - 1)]
        item = CATEGORY_ITEMS[code][rint(rng, 0, len(CATEGORY_ITEMS[code]) - 1)]
        size = CATEGORY_SIZES[code][rint(rng, 0, len(CATEGORY_SIZES[code]) - 1)]
        name = f"{brand} {item} {size}"
        sku = f"NS-{code}-{pid:04d}"
        if sku in used_skus:
            raise GenerationError("duplicate SKU")
        used_skus.add(sku)
        list_price = (p_lo + int(rng.random() * (p_hi - p_lo))) * 1000
        list_price = (list_price // 500) * 500
        base_cost_ratio = 0.68 + rng.random() * 0.12
        base_cost = (int(list_price * base_cost_ratio) // 100) * 100
        if rng.random() < 0.80:
            created = date(2021, 1, 1) + timedelta(days=rint(rng, 0, 970))  # pre-history
        else:
            span = (date(2026, 6, 30) - scen.history_start).days
            created = scen.history_start + timedelta(days=rint(rng, 0, span))
        is_active = rng.random() < 0.95
        weight = math.exp(1.1 * rnorm(rng))
        created_at = day_time(rng, created, tz, 8, 17)
        products.append([pid, sku, name, label, uom, list_price, None, is_active, created_at])
        prod_aux.append(
            {
                "category": code,
                "qmax": qmax,
                "weight": weight,
                "created": created,
                "base_cost": max(base_cost, 1000),
                "list_price": list_price,
            }
        )

    # ---- product cost history (SC-8) --------------------------------------
    rng = stream(seed, "cost_history")
    # ~20% of the catalog, striped across the popularity ranking so the share
    # among products actually delivered in the audit month stays inside the
    # SC-8 / SC-14 band, gets a forced actual-cost change inside the audit month.
    rank_order = sorted(range(n_products), key=lambda i: (-prod_aux[i]["weight"], i))
    aug_change = [False] * n_products
    # Each product's realized (actual) cost runs consistently above or below
    # its planning (standard) cost; striping the direction across the
    # popularity ranking keeps the volume-weighted standard-vs-actual gap
    # material by construction (SC-8 / SC-14) in every profile: four of
    # five products face supplier prices above plan, one in five below.
    act_direction = [1.0] * n_products
    for rank, idx in enumerate(rank_order):
        if rank % 5 == 2:
            aug_change[idx] = True
        if rank % 5 == 4:
            act_direction[idx] = -1.0

    revision_dates = []  # semi-annual standard revisions covering the history
    d = date(2023, 1, 1)
    while d <= scen.as_of:
        revision_dates.append(d)
        d = date(d.year + (1 if d.month == 7 else 0), 7 if d.month == 1 else 1, 1)

    cost_rows = []
    cost_id = 0
    std_hist = []  # per product: sorted list of (effective_from, cost)
    act_hist = []
    for pid in range(1, n_products + 1):
        aux = prod_aux[pid - 1]
        created = aux["created"]
        first_eff = created if created > date(2023, 7, 1) else date(2023, 7, 1)
        std = [(first_eff, aux["base_cost"])]
        for rev in revision_dates:
            if rev <= first_eff:
                continue
            r = rng.random()
            if r < 0.25:
                continue  # unchanged this cycle
            delta = (0.005 + rng.random() * 0.045) * (1 if rng.random() < 0.62 else -1)
            new = max(1000, (int(std[-1][1] * (1 + delta)) // 100) * 100)
            std.append((rev, new))

        def act_ratio() -> float:
            magnitude = 0.02 + rng.random() * 0.06  # per-product 2-8 percent
            return 1.0 + act_direction[pid - 1] * magnitude

        def std_at(day: date) -> int:
            cost = std[0][1]
            for eff, val in std:
                if eff <= day:
                    cost = val
            return cost

        act = [(first_eff, max(1000, (int(std[0][1] * act_ratio()) // 100) * 100))]
        # actual changes on arbitrary dates as supplier prices move
        window_start = first_eff
        while window_start < scen.as_of:
            # next semi-annual boundary (1 Jan / 1 Jul) after window_start
            if window_start.month >= 7:
                boundary = date(window_start.year + 1, 1, 1)
            else:
                boundary = date(window_start.year, 7, 1)
            window_end = min(boundary, scen.as_of)
            n_changes = 1 + int(rng.random() * 2)  # 1-2 per half-year window
            for _ in range(n_changes):
                span = (window_end - window_start).days
                if span <= 1:
                    continue
                eff = window_start + timedelta(days=1 + int(rng.random() * (span - 1)))
                if eff <= act[-1][0]:
                    continue
                in_audit_month = eff.year == audit_first.year and eff.month == audit_first.month
                if in_audit_month and not aug_change[pid - 1]:
                    # keep unflagged products stable inside the audit month
                    eff = date(eff.year, 7, 25 if eff.day > 25 else eff.day)
                    if eff <= act[-1][0]:
                        continue
                act.append((eff, max(1000, (int(std_at(eff) * act_ratio()) // 100) * 100)))
            window_start = window_end
        if aug_change[pid - 1]:
            eff = date(audit_first.year, audit_first.month, 3 + int(rng.random() * 25))
            if all(e != eff for e, _ in act):
                act.append((eff, max(1000, (int(std_at(eff) * act_ratio()) // 100) * 100)))
        act.sort(key=lambda t: t[0])
        # drop any change dated after the horizon
        act = [(e, v) for e, v in act if e <= horizon.date()]

        std_hist.append(std)
        act_hist.append(act)
        products[pid - 1][6] = std[-1][1]  # products.standard_cost mirrors latest standard
        for eff, val in std:
            cost_id += 1
            cost_rows.append(
                [cost_id, pid, "standard", eff, val, "pricing_team",
                 day_time(rng, eff, tz, 8, 11)]
            )
        for eff, val in act:
            cost_id += 1
            cost_rows.append(
                [cost_id, pid, "actual", eff, val, "purchasing",
                 day_time(rng, eff, tz, 8, 11)]
            )

    def std_cost_at(pid: int, day: date) -> int:
        cost = None
        for eff, val in std_hist[pid - 1]:
            if eff <= day:
                cost = val
        if cost is None:
            raise GenerationError(f"no standard cost for product {pid} at {day}")
        return cost

    def act_cost_at(pid: int, day: date) -> int:
        cost = None
        for eff, val in act_hist[pid - 1]:
            if eff <= day:
                cost = val
        if cost is None:
            raise GenerationError(f"no actual cost for product {pid} at {day}")
        return cost

    # ---- customers ---------------------------------------------------------
    rng = stream(seed, "customers")
    seg_chooser = Weighted(SEGMENTS, SEGMENT_WEIGHTS)
    geo_chooser = Weighted(GEOGRAPHY, [14, 16, 8, 10, 4, 12, 8, 4, 5, 4, 5, 4, 3, 3])
    n_customers = scale["customers"]
    customers = []
    cust_aux = []
    used_names = set()
    for cid in range(1, n_customers + 1):
        segment = seg_chooser.pick(rng)
        province, cities, region = geo_chooser.pick(rng)
        city = cities[rint(rng, 0, len(cities) - 1)]
        prefixes, pw = SEGMENT_PREFIXES[segment]
        prefix = Weighted(prefixes, pw).pick(rng)
        core_w = NAME_CORES[rint(rng, 0, len(NAME_CORES) - 1)]
        tail_w = NAME_TAILS[rint(rng, 0, len(NAME_TAILS) - 1)]
        name = f"{prefix} {core_w} {tail_w}"
        if name in used_names:
            name = f"{name} {city}"
        n_suffix = 2
        while name in used_names:
            name = f"{prefix} {core_w} {tail_w} {n_suffix}"
            n_suffix += 1
        used_names.add(name)
        terms_vals, terms_w = SEGMENT_TERMS[segment]
        terms = Weighted(terms_vals, terms_w).pick(rng)
        if rng.random() < 0.65:
            created = date(2019, 1, 1) + timedelta(days=rint(rng, 0, 1700))  # pre-history
        else:
            span = (date(2026, 7, 31) - scen.history_start).days
            created = scen.history_start + timedelta(days=rint(rng, 0, span))
        is_active = rng.random() < 0.94
        weight = SEGMENT_ORDER_WEIGHT[segment] * math.exp(0.9 * rnorm(rng))
        customers.append(
            [cid, f"C{cid:06d}", name, segment, province, city, region, terms,
             is_active, day_time(rng, created, tz, 8, 17)]
        )
        cust_aux.append(
            {"segment": segment, "region": region, "terms": terms,
             "weight": weight, "created": created, "active": is_active}
        )

    # ---- orders + order items ---------------------------------------------
    rng_o = stream(seed, "orders")
    rng_i = stream(seed, "order_items")
    n_orders = scale["orders"]

    month_starts = []
    d = scen.history_start
    while d <= scen.as_of:
        month_starts.append(d)
        d = next_month_first(d)
    month_weights = []
    for m_idx, ms in enumerate(month_starts):
        w = (1.008 ** m_idx) * SEASONALITY[ms.month]
        if period_of(ms) == scen.open_period:
            w *= 8 / 30  # partial month up to the horizon
        month_weights.append(w)
    month_orders = largest_remainder(n_orders, month_weights)

    lines_w = [24, 22, 18, 14, 10, 7, 5]  # 1..7 lines, mean ~3.05
    lines_chooser = Weighted(list(range(1, 8)), lines_w)
    delivery_lag_chooser = Weighted(list(range(1, 8)), [16, 22, 20, 15, 11, 9, 7])

    orders = []
    order_items = []
    order_lines_index = {}  # order_id -> (start, count) into order_items
    order_id = 0
    item_id = 0
    inactive_cutoff = date(2026, 3, 1)

    for m_idx, ms in enumerate(month_starts):
        count = month_orders[m_idx]
        if count == 0:
            continue
        open_month = period_of(ms) == scen.open_period
        # eligible day list (orders placed Mon-Sat)
        days = []
        d = ms
        month_end = next_month_first(ms) - ONE_DAY
        while d <= month_end:
            if d.weekday() != 6 and (not open_month or d <= date(2026, 9, 8)):
                days.append(d)
            d += ONE_DAY
        # customer pool for the month
        pool = []
        pool_w = []
        for cid in range(1, n_customers + 1):
            aux = cust_aux[cid - 1]
            if aux["created"] >= ms:
                continue
            if not aux["active"] and ms >= inactive_cutoff:
                continue
            pool.append(cid)
            pool_w.append(aux["weight"])
        cust_chooser = Weighted(pool, pool_w)
        # product pool for the month
        ppool = []
        ppool_w = []
        for pid in range(1, n_products + 1):
            aux = prod_aux[pid - 1]
            if aux["created"] >= ms:
                continue
            if not products[pid - 1][7] and ms >= date(2026, 1, 1):
                continue
            ppool.append(pid)
            ppool_w.append(aux["weight"])
        prod_chooser = Weighted(ppool, ppool_w)

        for _ in range(count):
            order_id += 1
            cid = cust_chooser.pick(rng_o)
            od = days[rint(rng_o, 0, len(days) - 1)]
            if od == date(2026, 9, 8):
                # horizon morning: orders exist only before the observation instant
                created_at = day_time(rng_o, od, tz, 7, 9)
            else:
                created_at = day_time(rng_o, od, tz, 8, 17)
            req = od + timedelta(days=rint(rng_o, 2, 7))
            status = "open"
            delivery = None
            cancelled = None
            if rng_o.random() < scen.cancelled_rate_pct / 100:
                status = "cancelled"
                cancelled = od + timedelta(days=rint(rng_o, 0, 3))
                if cancelled > last_business_date:
                    cancelled = last_business_date
            else:
                if rng_o.random() < 0.006:
                    lag = rint(rng_o, 10, 24)  # occasional backorder
                else:
                    lag = delivery_lag_chooser.pick(rng_o)
                dd = od + timedelta(days=lag)
                while dd.weekday() == 6:  # deliveries Mon-Sat
                    dd += ONE_DAY
                if dd <= last_business_date:
                    status = "delivered"
                    delivery = dd
            orders.append(
                [order_id, cid, od, req, status, delivery, cancelled, created_at]
            )

            n_lines = lines_chooser.pick(rng_i)
            seg_factor = SEGMENT_QTY_FACTOR[cust_aux[cid - 1]["segment"]]
            chosen = set()
            start = len(order_items)
            for line in range(n_lines):
                pid = prod_chooser.pick(rng_i)
                tries = 0
                while pid in chosen and tries < 4:
                    pid = prod_chooser.pick(rng_i)
                    tries += 1
                if pid in chosen:
                    continue
                chosen.add(pid)
                item_id += 1
                aux = prod_aux[pid - 1]
                qmax = max(2, int(aux["qmax"] * seg_factor))
                qty = 1 + int((qmax - 1) * (rng_i.random() ** 1.7))
                price = aux["list_price"]
                if rng_i.random() < 0.35:
                    disc_bp = 0
                else:
                    disc_bp = 25 * rint(rng_i, 8, 60)  # 2.00% - 15.00%
                line_net = rhu(qty * price * (10000 - disc_bp), 10000)
                order_items.append(
                    [item_id, order_id, pid, qty, price,
                     Decimal(disc_bp).scaleb(-4), line_net]
                )
            order_lines_index[order_id] = (start, len(order_items) - start)

    # ---- invoices + invoice lines (SC-6 posting lag; D1/D2 by construction)
    rng = stream(seed, "invoices")
    lag_chooser = Weighted([0, 1, 2, 3], scen.invoice_lag_weights)
    delivered = [o for o in orders if o[4] == "delivered"]
    delivered.sort(key=lambda o: (o[5], o[0]))

    invoices = []  # mutable rows + aux lag/delivery/time kept alongside
    inv_aux = []  # dicts: delivery, lag, time_r (fraction triple)
    inv_lines = []
    inv_by_order = {}
    invoice_id = 0
    line_id = 0

    def invoice_created_at(inv_date: date, fracs) -> datetime:
        h = 9 + int(fracs[0] * 8)
        m = int(fracs[1] * 60)
        s = int(fracs[2] * 60)
        return datetime.combine(inv_date, time(h, m, s)).replace(tzinfo=tz)

    for o in delivered:
        oid, cid, _, _, _, delivery, _, _ = o
        lag = lag_chooser.pick(rng)
        inv_date = add_business_days(delivery, lag)
        if inv_date > last_business_date:
            continue  # not yet billed at the horizon
        invoice_id += 1
        start, count = order_lines_index[oid]
        merch = 0
        vat = 0
        invoices.append(
            [invoice_id, oid, cid, inv_date, period_of(inv_date), 0, 0, 0, 0, None]
        )
        fracs = (rng.random(), rng.random(), rng.random())
        inv_aux.append({"delivery": delivery, "lag": lag, "fracs": fracs})
        ln = 0
        for k in range(start, start + count):
            item = order_items[k]
            pid, qty, price, line_net = item[2], item[3], item[4], item[6]
            ln += 1
            line_id += 1
            line_vat = pct_of(line_net, scen.vat_pct)
            cost = act_cost_at(pid, delivery)
            inv_lines.append(
                [line_id, invoice_id, ln, "merchandise", item[0], pid, qty,
                 price, qty * price - line_net, line_net, line_vat, cost]
            )
            merch += line_net
            vat += line_vat
        freight = 0
        if rng.random() < 0.40:
            freight = ((120000 + int(merch * 0.015)) // 1000) * 1000
            freight = min(freight, 900000)
            f_vat = pct_of(freight, scen.vat_pct)
            ln += 1
            line_id += 1
            inv_lines.append(
                [line_id, invoice_id, ln, "freight", None, None, None, None,
                 None, freight, f_vat, None]
            )
            vat += f_vat
        row = invoices[-1]
        row[5], row[6], row[7], row[8] = merch, freight, vat, merch + freight + vat
        row[9] = invoice_created_at(inv_date, fracs)
        inv_by_order[oid] = invoice_id

    def merch_of(period: str) -> int:
        return sum(r[5] for r in invoices if r[4] == period)

    def move_posting(inv_idx: int, new_lag: int) -> None:
        row = invoices[inv_idx]
        aux = inv_aux[inv_idx]
        new_date = add_business_days(aux["delivery"], new_lag)
        row[3] = new_date
        row[4] = period_of(new_date)
        row[9] = invoice_created_at(new_date, aux["fracs"])
        aux["lag"] = new_lag

    # D-calibration: guarantee that the period-basis legs D1 and D2 are
    # material (SC-14) without exceeding the SC-6 posting-lag bound.
    mat = scen.materiality
    sep_period = next_period(audit)
    jul_period = prev_period(audit)

    def d_values() -> tuple[int, int]:
        d1 = sum(
            invoices[i][5]
            for i in range(len(invoices))
            if period_of(inv_aux[i]["delivery"]) == audit and invoices[i][4] != audit
        )
        d2 = sum(
            invoices[i][5]
            for i in range(len(invoices))
            if period_of(inv_aux[i]["delivery"]) == jul_period and invoices[i][4] == audit
        )
        return d1, d2

    for _ in range(2):  # two passes: moves shift G_post slightly
        g_post_est = merch_of(audit)
        rnmr_est = int(g_post_est / 1.032)
        d1, d2 = d_values()
        d1_target = int(rnmr_est * max(float(mat["d1_min_pct_of_rnmr"]), 1.1) / 100)
        d2_target = int(rnmr_est * max(float(mat["d2_min_pct_of_rnmr"]), 1.1) / 100)
        if d2 < d2_target:
            cands = [
                i for i in range(len(invoices))
                if period_of(inv_aux[i]["delivery"]) == jul_period
                and invoices[i][4] == jul_period
                and add_business_days(inv_aux[i]["delivery"], 3) >= audit_first
            ]
            cands.sort(key=lambda i: (-invoices[i][5], i))
            for i in cands:
                if d2 >= d2_target:
                    break
                lag = inv_aux[i]["lag"]
                while lag < 3 and add_business_days(inv_aux[i]["delivery"], lag) < audit_first:
                    lag += 1
                if add_business_days(inv_aux[i]["delivery"], lag) >= audit_first:
                    move_posting(i, lag)
                    d2 += invoices[i][5]
        d1, d2 = d_values()
        if d1 < d1_target:
            sep_first = month_first(sep_period)
            cands = [
                i for i in range(len(invoices))
                if period_of(inv_aux[i]["delivery"]) == audit
                and invoices[i][4] == audit
                and add_business_days(inv_aux[i]["delivery"], 3) >= sep_first
            ]
            cands.sort(key=lambda i: (-invoices[i][5], i))
            for i in cands:
                if d1 >= d1_target:
                    break
                lag = inv_aux[i]["lag"]
                while lag < 3 and add_business_days(inv_aux[i]["delivery"], lag) < sep_first:
                    lag += 1
                if add_business_days(inv_aux[i]["delivery"], lag) >= sep_first:
                    move_posting(i, lag)
                    d1 += invoices[i][5]

    # ---- payments (lifecycle realism only; no reconciliation role) ---------
    rng = stream(seed, "payments")
    payments = []
    payment_id = 0
    method_chooser = Weighted(["transfer", "giro", "cash"], [72, 23, 5])
    jitter_chooser = Weighted(
        list(range(-5, 26)),
        [1, 1, 2, 3, 5, 12] + [6] * 10 + [3] * 10 + [2] * 5,
    )
    for idx, row in enumerate(invoices):
        invoice_id_, oid, cid, inv_date, _, _, _, _, total, _ = row
        terms = cust_aux[cid - 1]["terms"]
        pay_date = inv_date + timedelta(days=terms + jitter_chooser.pick(rng))
        pay_date = add_business_days(pay_date, 0)
        method = method_chooser.pick(rng)
        partial = rng.random() < 0.05
        if pay_date > last_business_date:
            continue  # outstanding at the horizon
        if partial:
            p1 = rhu(total * 60, 100)
            payment_id += 1
            payments.append(
                [payment_id, invoice_id_, pay_date, p1, method,
                 day_time(rng, pay_date, tz, 9, 16)]
            )
            pay2 = add_business_days(pay_date + timedelta(days=rint(rng, 7, 30)), 0)
            if pay2 <= last_business_date:
                payment_id += 1
                payments.append(
                    [payment_id, invoice_id_, pay2, total - p1, method,
                     day_time(rng, pay2, tz, 9, 16)]
                )
        else:
            payment_id += 1
            payments.append(
                [payment_id, invoice_id_, pay_date, total, method,
                 day_time(rng, pay_date, tz, 9, 16)]
            )

    # ---- returns + return items (SC-6; C_period by construction) ----------
    rng = stream(seed, "returns")
    rng_ri = stream(seed, "return_items")
    n_returns = scale["returns"]
    reason_chooser = Weighted(
        ["damaged", "expired", "wrong_item", "overstock", "quality"],
        [30, 18, 22, 18, 12],
    )
    recv_lag_chooser = Weighted(
        list(range(1, scen.return_lag_max + 1)),
        [math.exp(-lag / 12.0) for lag in range(1, scen.return_lag_max + 1)],
    )

    # allocate return counts per received-month, proportional to delivered
    # value, with a deliberate audit-month emphasis so the audit-period
    # credit population is material by construction (SC-14).
    month_value = {period_of(ms): 0 for ms in month_starts}
    for i, row in enumerate(invoices):
        month_value[period_of(inv_aux[i]["delivery"])] += row[5]
    recv_periods = sorted(p for p in month_value if month_value[p] > 0)
    recv_weights = []
    for p in recv_periods:
        w = float(month_value[p])
        if p == audit:
            w *= 1.30
        if p == scen.open_period:
            w *= 0.55  # only the first week exists
        recv_weights.append(w)
    month_returns = dict(zip(recv_periods, largest_remainder(n_returns, recv_weights)))

    inv_by_delivery_month: dict[str, list[int]] = {}
    for i in range(len(invoices)):
        inv_by_delivery_month.setdefault(period_of(inv_aux[i]["delivery"]), []).append(i)

    lines_by_invoice: dict[int, list[int]] = {}
    for li, lrow in enumerate(inv_lines):
        if lrow[3] == "merchandise":
            lines_by_invoice.setdefault(lrow[1], []).append(li)

    ret_specs = []  # dicts: inv_idx, received, reason, month
    returned_invoices = set()

    def receipt_pool(p: str, p_first: date, p_last: date) -> list[int]:
        pool = list(inv_by_delivery_month.get(p, [])) + list(
            inv_by_delivery_month.get(prev_period(p), [])
        )
        return [
            i for i in pool
            if inv_aux[i]["delivery"] + timedelta(days=1) <= p_last
            and inv_aux[i]["delivery"] + timedelta(days=scen.return_lag_max) >= p_first
        ]

    def try_make_return(p: str, p_first: date, p_last: date, chooser: Weighted) -> bool:
        # larger shipments are likelier to see a return (sqrt-of-value weight)
        for _ in range(40):
            i = chooser.pick(rng)
            inv_row = invoices[i]
            if inv_row[0] in returned_invoices:
                continue
            delivery = inv_aux[i]["delivery"]
            lo = max(1, (p_first - delivery).days)
            hi = min(scen.return_lag_max, (p_last - delivery).days)
            if lo > hi:
                continue
            lag = recv_lag_chooser.pick(rng)
            attempts = 0
            while not (lo <= lag <= hi) and attempts < 6:
                lag = recv_lag_chooser.pick(rng)
                attempts += 1
            if not (lo <= lag <= hi):
                lag = lo
            received = delivery + timedelta(days=lag)
            while received.weekday() == 6 or received > p_last:
                received -= ONE_DAY
            if received < p_first or received <= delivery:
                continue
            returned_invoices.add(inv_row[0])
            ret_specs.append(
                {"inv_idx": i, "received": received,
                 "reason": reason_chooser.pick(rng), "month": p}
            )
            return True
        return False

    for p in recv_periods:
        want = month_returns.get(p, 0)
        if want == 0:
            continue
        p_first = month_first(p)
        p_last = next_month_first(p_first) - ONE_DAY
        if p == scen.open_period:
            p_last = last_business_date
        pool = receipt_pool(p, p_first, p_last)
        if not pool:
            continue
        chooser = Weighted(pool, [math.sqrt(invoices[i][5]) for i in pool])
        made = 0
        while made < want and try_make_return(p, p_first, p_last, chooser):
            made += 1

    # Audit-month capacity guarantee: the audit-period credit merchandise
    # C_period equals the returned value of audit-month-received returns
    # (the period-end batch credits everything received by month end), so
    # the full-return capacity of those returns must comfortably cover the
    # SC-14 mid-band target. Add audit-month returns -- and retire the
    # newest return of the most-populated other month, keeping the
    # configured total -- until it does.
    g_post = merch_of(audit)
    lo_r, hi_r = (float(x) / 100 for x in mat["c_period_pct_of_rnmr"])
    mid_r = (lo_r + hi_r) / 2
    # c / (g_post - c) = t  =>  c = t * g_post / (1 + t)
    c_target = int(mid_r * g_post / (1 + mid_r))
    c_lo = int(lo_r * g_post / (1 + lo_r))
    c_hi = int(hi_r * g_post / (1 + hi_r))
    audit_first_d = month_first(audit)
    audit_last_d = next_month_first(audit_first_d) - ONE_DAY

    def aug_specs() -> list[dict]:
        return [s for s in ret_specs if s["month"] == audit]

    def aug_capacity() -> int:
        return sum(invoices[s["inv_idx"]][5] for s in aug_specs())

    cap_count = max(4, int(0.12 * max(1, len(inv_by_delivery_month.get(audit, [])))))
    topup_pool = receipt_pool(audit, audit_first_d, audit_last_d)
    topup_chooser = (
        Weighted(topup_pool, [math.sqrt(invoices[i][5]) for i in topup_pool])
        if topup_pool
        else None
    )
    while (
        aug_capacity() < int(1.30 * c_target)
        and len(aug_specs()) < cap_count
        and topup_chooser is not None
    ):
        if not try_make_return(audit, audit_first_d, audit_last_d, topup_chooser):
            break
        donor_months: dict[str, list[int]] = {}
        for idx, s in enumerate(ret_specs):
            if s["month"] != audit:
                donor_months.setdefault(s["month"], []).append(idx)
        if donor_months:
            donor = max(sorted(donor_months), key=lambda m: len(donor_months[m]))
            victim_idx = donor_months[donor][-1]
            victim = ret_specs.pop(victim_idx)
            returned_invoices.discard(invoices[victim["inv_idx"]][0])
    if aug_capacity() < c_lo:
        raise GenerationError(
            f"audit-month return capacity {aug_capacity()} cannot reach "
            f"the C_period band lower bound {c_lo}"
        )

    # finalize identities and rows in receipt order
    ret_specs.sort(key=lambda s: (s["received"], invoices[s["inv_idx"]][0]))
    returns = []
    ret_aux = []
    for ridx, s in enumerate(ret_specs, start=1):
        inv_row = invoices[s["inv_idx"]]
        returns.append(
            [ridx, inv_row[0], inv_row[2], s["received"], s["reason"], "received",
             day_time(rng, s["received"], tz, 9, 16)]
        )
        ret_aux.append({"inv_idx": s["inv_idx"], "received": s["received"], "items": []})

    for r_idx in range(len(returns)):
        aux = ret_aux[r_idx]
        mlines = lines_by_invoice[returns[r_idx][1]]
        k = min(len(mlines), 1 + int(rng_ri.random() * 3))
        picked = set()
        items = []
        for _ in range(k):
            li = mlines[rint(rng_ri, 0, len(mlines) - 1)]
            if li in picked:
                continue
            picked.add(li)
            qty = inv_lines[li][6]
            frac = 0.25 + 0.75 * (rng_ri.random() ** 1.3)
            qty_ret = max(1, min(qty, int(round(qty * frac))))
            items.append([li, qty_ret])
        items.sort(key=lambda it: inv_lines[it[0]][2])  # by line_no
        aux["items"] = items

    # Value helpers and the per-set calibration primitive used by the joint
    # audit-month calibration after credit-note sides are known (SC-14).
    def item_value(line_idx: int, qty_ret: int) -> int:
        line = inv_lines[line_idx]
        return rhu(qty_ret * line[9], line[6])

    def return_value(aux) -> int:
        return sum(item_value(li, q) for li, q in aux["items"])

    def calibrate_return_set(r_idxs: list[int], target: int) -> int:
        """Adjusts returned quantities on the given returns until their total
        returned value sits at the target (unit resolution: one carton)."""
        order = sorted(r_idxs, key=lambda r: (-invoices[ret_aux[r]["inv_idx"]][5], r))
        current = sum(return_value(ret_aux[r]) for r in r_idxs)
        if current < target:
            for r_idx in order:  # raise quantities toward full lines
                if current >= target:
                    break
                for it in ret_aux[r_idx]["items"]:
                    li, q = it
                    full = inv_lines[li][6]
                    if q < full:
                        current += item_value(li, full) - item_value(li, q)
                        it[1] = full
                    if current >= target:
                        break
        if current < target:
            for r_idx in order:  # add the invoice's remaining lines in full
                if current >= target:
                    break
                aux = ret_aux[r_idx]
                have = {it[0] for it in aux["items"]}
                for li in lines_by_invoice[returns[r_idx][1]]:
                    if li in have:
                        continue
                    q = inv_lines[li][6]
                    aux["items"].append([li, q])
                    current += item_value(li, q)
                    if current >= target:
                        break
                aux["items"].sort(key=lambda it: inv_lines[it[0]][2])
        if current > target:
            for r_idx in reversed(order):  # precise proportional trim
                if current <= target:
                    break
                for it in reversed(ret_aux[r_idx]["items"]):
                    excess = current - target
                    if excess <= 0:
                        break
                    li, q = it
                    line = inv_lines[li]
                    unit = max(1.0, line[9] / line[6])
                    reduce_units = min(q - 1, int(math.ceil(excess / unit)))
                    if reduce_units > 0:
                        new_q = q - reduce_units
                        current += item_value(li, new_q) - item_value(li, q)
                        it[1] = new_q
        return current


    # ---- credit notes (SC-5/SC-6 back-dating; C_late by construction) ------
    rng = stream(seed, "credit_notes")
    credit_lag_chooser = Weighted(
        list(range(1, scen.credit_lag_max + 1)),
        [18, 16, 14, 12, 10, 9, 8, 6, 4, 3][: scen.credit_lag_max],
    )
    credits = []  # mutable rows
    credit_aux = []  # dicts: return_idx, mode ('natural'|'bd1'|'batch')
    credit_note_id = 0

    def credit_amounts(aux) -> tuple[int, int, int]:
        merch = sum(item_value(li, q) for li, q in aux["items"])
        vat = pct_of(merch, scen.vat_pct)
        cogs = sum(q * inv_lines[li][11] for li, q in aux["items"])
        return merch, vat, cogs

    def batch_posting(close: PeriodClose, r: random.Random) -> datetime:
        day_pick = Weighted(list(close.batch_days), [45, 35, 20]).pick(r)
        if day_pick == close.batch_days[0]:
            t = time(14 + rint(r, 0, 2), rint(r, 0, 59), rint(r, 0, 59))
        else:
            t = time(9 + rint(r, 0, 7), rint(r, 0, 59), rint(r, 0, 59))
        return datetime.combine(day_pick, t).replace(tzinfo=tz)

    for r_idx in range(len(returns)):
        ret_row = returns[r_idx]
        aux = ret_aux[r_idx]
        received = aux["received"]
        p_r = period_of(received)
        close = scen.close_for(p_r)
        lag = credit_lag_chooser.pick(rng)
        natural = add_business_days(received + ONE_DAY, lag - 1)
        posted_at = None
        mode = None
        if period_of(natural) == p_r:
            posted_at = day_time(rng, natural, tz, 9, 17)
            mode = "natural"
        elif natural == close.bd1:
            posted_at = day_time(rng, natural, tz, 9, 17)
            mode = "bd1"
        else:
            posted_at = batch_posting(close, rng)
            mode = "batch"
        if posted_at > horizon:
            continue  # still uncredited at the horizon
        credit_note_id += 1
        inv_row = invoices[aux["inv_idx"]]
        merch, vat, cogs = credit_amounts(aux)
        credits.append(
            [credit_note_id, ret_row[0], inv_row[0], inv_row[2],
             posted_at.date(), p_r, merch, vat, merch + vat, cogs, posted_at]
        )
        credit_aux.append({"return_idx": r_idx, "mode": mode})
        ret_row[5] = "credited"

    # Joint audit-month calibration (SC-14): once each credit's side of the
    # board snapshot is known, dial the pre-snapshot and post-snapshot value
    # to explicit targets by adjusting returned quantities, then recompute
    # the audit credits' amounts from the calibrated items. This makes both
    # C_period and the C_late share hold by construction in every profile.
    rng_cal = stream(seed, "calibration")
    audit_credit_idx = [i for i in range(len(credits)) if credits[i][5] == audit]
    if not audit_credit_idx:
        raise GenerationError("no audit-period credit notes were generated")
    snapshot_at = audit_close.snapshot_at

    def is_late(i: int) -> bool:
        return credits[i][10] > snapshot_at

    def move_to_batch(i: int) -> None:
        posted_at = batch_posting(audit_close, rng_cal)
        credits[i][4] = posted_at.date()
        credits[i][10] = posted_at
        credit_aux[i]["mode"] = "batch"

    def move_to_bd1(i: int) -> None:
        posted_at = day_time(rng_cal, audit_close.bd1, tz, 9, 17)
        credits[i][4] = posted_at.date()
        credits[i][10] = posted_at
        credit_aux[i]["mode"] = "bd1"

    def received_of(i: int) -> date:
        return returns[credit_aux[i]["return_idx"]][3]

    late = [i for i in audit_credit_idx if is_late(i)]
    seen = [i for i in audit_credit_idx if not is_late(i)]

    def side_capacity(idxs: list[int]) -> int:
        return sum(
            invoices[ret_aux[credit_aux[i]["return_idx"]]["inv_idx"]][5] for i in idxs
        )

    late_target = int(c_target * 0.47)
    seen_target = c_target - late_target
    # Both sides must exist and carry enough full-return capacity. Moving a
    # pre-snapshot credit into the period-end batch models a credit Finance
    # simply had not raised yet (SC-6 says credits post "normally" within
    # ten business days -- outliers are the batch's reason to exist).
    movable = sorted(seen, key=lambda i: (received_of(i), credits[i][0]), reverse=True)
    while (
        movable
        and len(movable) > 1
        and (not late or side_capacity(late) < int(1.10 * late_target))
    ):
        i = movable.pop(0)
        move_to_batch(i)
        late.append(i)
        seen.remove(i)
    if not seen and late:
        by_received = sorted(late, key=lambda i: (received_of(i), credits[i][0]))
        i = by_received[0]
        move_to_bd1(i)
        late.remove(i)
        seen.append(i)
    if side_capacity(late) < late_target:
        raise GenerationError("late-credit capacity cannot reach the C_late target")
    if side_capacity(seen) < seen_target:
        raise GenerationError("pre-snapshot credit capacity cannot reach its target")

    calibrate_return_set([credit_aux[i]["return_idx"] for i in late], late_target)
    calibrate_return_set([credit_aux[i]["return_idx"] for i in seen], seen_target)

    for i in audit_credit_idx:  # recompute amounts from the calibrated items
        aux = ret_aux[credit_aux[i]["return_idx"]]
        merch, vat, cogs = credit_amounts(aux)
        credits[i][6], credits[i][7], credits[i][8], credits[i][9] = (
            merch, vat, merch + vat, cogs,
        )

    c_period_v = sum(credits[i][6] for i in audit_credit_idx)
    c_late_v = sum(credits[i][6] for i in audit_credit_idx if is_late(i))
    if not (c_lo <= c_period_v <= c_hi):
        raise GenerationError(f"C_period {c_period_v} outside [{c_lo}, {c_hi}]")
    if c_late_v / c_period_v < float(mat["c_late_min_share_of_c_period"]):
        raise GenerationError(
            f"C_late share {c_late_v / c_period_v:.3f} below the SC-14 minimum"
        )

    return_items = []
    ritem_id = 0
    for r_idx in range(len(returns)):
        aux = ret_aux[r_idx]
        for li, q in aux["items"]:
            ritem_id += 1
            return_items.append([ritem_id, returns[r_idx][0], inv_lines[li][0], q])

    # ---- nightly job schedule (fact loads + board runs) --------------------
    rng = stream(seed, "etl_job_runs")
    items_by_delivery: dict[date, int] = {}
    for o in orders:
        if o[4] == "delivered":
            _, cnt = order_lines_index[o[0]]
            items_by_delivery[o[5]] = items_by_delivery.get(o[5], 0) + cnt

    job_rows = []
    load_schedule = {}
    run_date = scen.history_start + ONE_DAY
    last_run_date = date(2026, 9, 8)
    while run_date <= last_run_date:
        started = datetime.combine(run_date, time(2, 0, 0)).replace(tzinfo=tz) + timedelta(
            seconds=rint(rng, 0, 299)
        )
        completed = started + timedelta(seconds=180 + rint(rng, 0, 419))
        prev = run_date - ONE_DAY
        rows_written = items_by_delivery.get(prev, 0)
        job_rows.append(
            ["refresh_delivered_sales", period_of(prev), started, completed,
             "success", rows_written]
        )
        load_schedule[prev] = completed
        run_date += ONE_DAY
    for p in scen.periods:
        close = scen.close_for(p)
        dur = timedelta(seconds=60 + rint(rng, 0, 120))
        job_rows.append(
            ["board_pack_monthly", p, close.snapshot_at - dur, close.snapshot_at,
             "success", 3]
        )
    job_rows.sort(key=lambda r: (r[2], r[0]))
    etl_rows = [[i + 1] + row for i, row in enumerate(job_rows)]

    # ---- assemble immutable tables ----------------------------------------
    ds.tables = {
        "core.customers": [tuple(r) for r in customers],
        "core.products": [tuple(r) for r in products],
        "core.product_cost_history": [tuple(r) for r in cost_rows],
        "core.orders": [tuple(r) for r in orders],
        "core.order_items": [tuple(r) for r in order_items],
        "core.invoices": [tuple(r) for r in invoices],
        "core.invoice_lines": [tuple(r) for r in inv_lines],
        "core.payments": [tuple(r) for r in payments],
        "core.returns": [tuple(r) for r in returns],
        "core.return_items": [tuple(r) for r in return_items],
        "core.credit_notes": [tuple(r) for r in credits],
        "analytics.etl_job_runs": [tuple(r) for r in etl_rows],
    }
    ds.load_schedule = load_schedule

    # ---- expected reconciliation quantities (independent Python-side) ------
    ds.expected = compute_expected(ds)
    verify_expected(ds)
    return ds


# ---------------------------------------------------------------------------
# Independent recomputation of every reconciliation quantity (Part III step 6)
# ---------------------------------------------------------------------------


def compute_expected(ds: Dataset) -> dict:
    scen = ds.scenario
    audit = scen.audit_period
    jul = prev_period(audit)
    close = scen.close_for(audit)
    snapshot_at = close.snapshot_at
    vat = scen.vat_pct

    orders = {r[0]: r for r in ds.tables["core.orders"]}
    invoices = {r[0]: r for r in ds.tables["core.invoices"]}
    inv_lines = ds.tables["core.invoice_lines"]
    credits = ds.tables["core.credit_notes"]

    std_hist: dict[int, list[tuple[date, int]]] = {}
    for r in ds.tables["core.product_cost_history"]:
        if r[2] == "standard":
            std_hist.setdefault(r[1], []).append((r[3], r[4]))
    for hist in std_hist.values():
        hist.sort(key=lambda t: t[0])

    def std_at(pid: int, day: date) -> int:
        cost = None
        for eff, val in std_hist[pid]:
            if eff <= day:
                cost = val
        if cost is None:
            raise GenerationError(f"no standard cost for product {pid} at {day}")
        return cost

    g_post = k_post = freight = 0
    d1 = d2 = k1 = k2 = 0
    for line in inv_lines:
        inv = invoices[line[1]]
        period = inv[4]
        if line[3] == "freight":
            if period == audit:
                freight += line[9]
            continue
        delivery = orders[inv[1]][5]
        dp = period_of(delivery)
        if period == audit:
            g_post += line[9]
            k_post += line[6] * line[11]
            if dp == jul:
                d2 += line[9]
                k2 += line[6] * line[11]
        if dp == audit and period != audit:
            d1 += line[9]
            k1 += line[6] * line[11]

    c_period = c_late = vat_seen = vat_late = r_period = r_early = r_late = 0
    late_count = seen_count = 0
    for cr in credits:
        if cr[5] != audit:
            continue
        c_period += cr[6]
        r_period += cr[9]
        if cr[10] <= snapshot_at:
            vat_seen += cr[7]
            r_early += cr[9]
            seen_count += 1
        else:
            c_late += cr[6]
            vat_late += cr[7]
            r_late += cr[9]
            late_count += 1

    dsv = k_std = 0
    aug_delivered_orders = set()
    aug_products = set()
    order_lines: dict[int, list] = {}
    for it in ds.tables["core.order_items"]:
        order_lines.setdefault(it[1], []).append(it)
    for o in ds.tables["core.orders"]:
        if o[4] != "delivered" or period_of(o[5]) != audit:
            continue
        aug_delivered_orders.add(o[0])
        for it in order_lines.get(o[0], []):
            dsv += it[6]
            k_std += it[3] * std_at(it[2], o[5])
            aug_products.add(it[2])

    k_act = k_post + k1 - k2
    rnmr = g_post - c_period
    arc = k_post - r_period
    fgm = rnmr - arc
    cm = dsv - k_std
    c_seen = c_period - c_late
    br = dsv - (c_seen + vat_seen)
    bgm = br - k_std

    def pct(margin: int, revenue: int, places: str) -> Decimal:
        return (Decimal(margin) * 100 / Decimal(revenue)).quantize(
            Decimal(places), rounding=ROUND_HALF_UP
        )

    # audit-month actual-cost-change share among delivered products (SC-8)
    changed = set()
    audit_first = month_first(audit)
    audit_last = next_month_first(audit_first) - ONE_DAY
    for r in ds.tables["core.product_cost_history"]:
        if r[2] == "actual" and audit_first <= r[3] <= audit_last:
            changed.add(r[1])
    aug_change_share = 100.0 * len(changed & aug_products) / max(1, len(aug_products))

    delivered_orders_total = sum(1 for o in ds.tables["core.orders"] if o[4] == "delivered")
    return {
        "g_post": g_post, "c_period": c_period, "c_late": c_late,
        "c_seen": c_seen, "vat_seen": vat_seen, "vat_late": vat_late,
        "d1": d1, "d2": d2, "k_post": k_post, "k1": k1, "k2": k2,
        "k_act": k_act, "k_std": k_std,
        "r_period": r_period, "r_early": r_early, "r_late": r_late,
        "freight_income": freight,
        "rnmr": rnmr, "arc": arc, "fgm": fgm,
        "dsv": dsv, "cm": cm, "br": br, "bgm": bgm,
        "fgm_pct": pct(fgm, rnmr, "0.01"),
        "cm_pct": pct(cm, dsv, "0.1"),
        "bgm_pct": pct(bgm, br, "0.1"),
        "vat_rate_pct": vat,
        "board_snapshot_at": snapshot_at,
        "finance_close_at": close.close_at,
        "credit_batch_days": [d.isoformat() for d in close.batch_days],
        "aug_delivered_orders": len(aug_delivered_orders),
        "aug_late_credit_count": late_count,
        "aug_seen_credit_count": seen_count,
        "aug_change_share": aug_change_share,
        "delivered_orders_total": delivered_orders_total,
    }


def verify_expected(ds: Dataset) -> None:
    """Coherence identities and SC-14 materiality, asserted by construction."""
    e = ds.expected
    mat = ds.scenario.materiality

    def check(cond: bool, msg: str) -> None:
        if not cond:
            raise GenerationError(f"scenario invariant violated: {msg}")

    check(e["rnmr"] == e["g_post"] - e["c_period"], "RNMR identity")
    check(e["arc"] == e["k_post"] - e["r_period"], "ARC identity")
    check(e["fgm"] == e["rnmr"] - e["arc"], "FGM identity")
    check(e["dsv"] == e["g_post"] + e["d1"] - e["d2"], "DSV identity")
    check(e["cm"] == e["dsv"] - e["k_std"], "CM identity")
    check(e["br"] == e["dsv"] - (e["c_seen"] + e["vat_seen"]), "BR identity")
    check(e["bgm"] == e["br"] - e["k_std"], "BGM identity")
    check(e["c_period"] == e["c_seen"] + e["c_late"], "credit split")
    check(e["r_period"] == e["r_early"] + e["r_late"], "R_period = R_early + R_late")

    rnmr = e["rnmr"]
    lo, hi = (float(x) for x in mat["c_period_pct_of_rnmr"])
    c_pct = 100 * e["c_period"] / rnmr
    check(lo <= c_pct <= hi, f"C_period {c_pct:.2f}% of RNMR outside [{lo}, {hi}]")
    share = e["c_late"] / e["c_period"]
    check(
        share >= float(mat["c_late_min_share_of_c_period"]),
        f"C_late share {share:.3f} below minimum",
    )
    check(
        100 * e["d1"] / rnmr >= float(mat["d1_min_pct_of_rnmr"]),
        f"D1 {100 * e['d1'] / rnmr:.2f}% of RNMR below minimum",
    )
    check(
        100 * e["d2"] / rnmr >= float(mat["d2_min_pct_of_rnmr"]),
        f"D2 {100 * e['d2'] / rnmr:.2f}% of RNMR below minimum",
    )
    cost_gap = 100 * abs(e["k_std"] - e["k_act"]) / e["k_act"]
    check(
        cost_gap >= float(mat["cost_basis_min_pct_of_k_act"]),
        f"standard-vs-actual gap {cost_gap:.2f}% below minimum",
    )
    min_rev = float(mat["revenue_pairwise_min_pct_of_rnmr"]) / 100 * rnmr
    for a, b, label in (
        (e["rnmr"], e["dsv"], "RNMR vs DSV"),
        (e["rnmr"], e["br"], "RNMR vs BR"),
        (e["dsv"], e["br"], "DSV vs BR"),
    ):
        check(abs(a - b) >= min_rev, f"revenue difference too small: {label}")
    pcts = {
        "FGM%": 100 * e["fgm"] / e["rnmr"],
        "CM%": 100 * e["cm"] / e["dsv"],
        "BGM%": 100 * e["bgm"] / e["br"],
    }
    min_pp = float(mat["margin_pairwise_min_pp"])
    labels = list(pcts)
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            check(
                abs(pcts[labels[i]] - pcts[labels[j]]) >= min_pp,
                f"margin-% difference too small: {labels[i]} vs {labels[j]}",
            )
    lo, hi = (float(x) for x in mat["fgm_pct_of_rnmr_band"])
    check(lo <= pcts["FGM%"] <= hi, f"FGM {pcts['FGM%']:.2f}% outside [{lo}, {hi}]")
    lo, hi = (float(x) for x in mat["aug_actual_cost_change_product_share_band_pct"])
    check(
        lo <= e["aug_change_share"] <= hi,
        f"audit-month actual-cost-change share {e['aug_change_share']:.1f}% outside band",
    )
    returned = len(ds.tables["core.returns"])
    ret_share = 100 * returned / e["delivered_orders_total"]
    check(5.0 <= ret_share <= 10.0, f"return share {ret_share:.2f}% outside [5, 10]")
    check(e["c_late"] > 0 and e["r_late"] > 0, "late credit population empty")
    check(e["c_seen"] > 0 and e["r_early"] > 0, "pre-snapshot credit population empty")

    # Horizon rule: no event date or system timestamp after the observation
    # instant (SC-5), anywhere in the environment. orders.requested_delivery_date
    # is exempt: it is a plan attribute known at the horizon, not an event
    # record, and is not in SC-6's event-timestamp table -- open orders
    # legitimately request delivery on future dates.
    horizon = ds.scenario.observation_at
    horizon_day = horizon.date()
    exempt = {"core.orders": {TABLE_COLUMNS["core.orders"].index("requested_delivery_date")}}
    for name, rows in sorted(ds.tables.items()):
        skip = exempt.get(name, set())
        for row in rows:
            for col, value in enumerate(row):
                if col in skip:
                    continue
                if isinstance(value, datetime):
                    check(value <= horizon, f"{name}: timestamp {value} after horizon")
                elif isinstance(value, date):
                    check(value <= horizon_day, f"{name}: date {value} after horizon")

    # SC-8: standard costs change only at the semi-annual revisions; the
    # audit month must contain no standard-cost change.
    audit_first = month_first(ds.scenario.audit_period)
    for row in ds.tables["core.product_cost_history"]:
        if row[2] == "standard":
            eff = row[3]
            in_audit_month = eff.year == audit_first.year and eff.month == audit_first.month
            check(not in_audit_month, f"standard cost change inside the audit month: {row}")


# ---------------------------------------------------------------------------
# Scenario SQL rendering (surfaces run their own SQL -- SC-9)
# ---------------------------------------------------------------------------


def _substitute(text: str, replacements: list[tuple[str, str, int]]) -> str:
    for old, new, count in replacements:
        found = text.count(old)
        if found != count:
            raise GenerationError(
                f"scenario SQL drift: expected {count} occurrence(s) of {old!r}, found {found}"
            )
        text = text.replace(old, new)
    return text


def read_scenario_file(name: str) -> str:
    return (SCENARIO_DIR / name).read_text(encoding="utf-8")


def finance_close_sql() -> str:
    return _substitute(
        read_scenario_file("finance_revenue.sql"),
        [("now()", "%(closed_at)s", 1), (":period", "%(period)s", 4)],
    )


def board_pack_sql(with_snapshot_restriction: bool) -> str:
    text = read_scenario_file("board_pack.sql")
    if with_snapshot_restriction:
        # SC-9.3: the historical snapshot is reproduced by evaluating the
        # same logic with the credit-note set restricted to rows that
        # existed when the pack job ran (created_at <= generated_at).
        text = _substitute(
            text,
            [(
                "where accounting_period = :period",
                "where accounting_period = :period\n"
                "       and created_at <= %(generated_at)s",
                1,
            )],
        )
    return _substitute(
        text,
        [
            (":period", "%(period)s", 6),
            ("now()", "%(generated_at)s", 3),
            # psycopg placeholder escaping for execution; the committed
            # evidence file keeps the plain KPI label
            ("'Gross Margin %'", "'Gross Margin %%'", 1),
        ],
    )


def sales_dashboard_parts() -> tuple[list[str], str]:
    """Returns (rendered nightly refresh statements, view DDL as committed)."""
    text = read_scenario_file("sales_dashboard.sql")
    idx = text.index("create or replace view")
    refresh = _substitute(
        text[:idx],
        [(":run_date", "%(run_date)s", 3), ("now()", "%(loaded_at)s", 1)],
    )
    statements = [s.strip() for s in refresh.split(";") if s.strip()]
    return statements, text[idx:].rstrip().rstrip(";")


# ---------------------------------------------------------------------------
# PostgreSQL load (Part III steps 2-5)
# ---------------------------------------------------------------------------

SCHEMAS = ["core", "finance", "analytics", "management"]

DDL = """
create table core.customers (
    customer_id bigint,
    customer_code text not null,
    company_name text not null,
    segment text not null,
    province text not null,
    city text not null,
    sales_region text not null,
    credit_terms_days integer not null,
    is_active boolean not null,
    created_at timestamptz not null
);
create table core.products (
    product_id bigint,
    sku text not null,
    product_name text not null,
    category text not null,
    uom text not null,
    list_price bigint not null,
    standard_cost bigint not null,
    is_active boolean not null,
    created_at timestamptz not null
);
create table core.product_cost_history (
    cost_history_id bigint,
    product_id bigint not null,
    cost_type text not null,
    effective_from date not null,
    unit_cost bigint not null,
    source text not null,
    created_at timestamptz not null
);
create table core.orders (
    order_id bigint,
    customer_id bigint not null,
    order_date date not null,
    requested_delivery_date date not null,
    status text not null,
    delivery_date date,
    cancelled_date date,
    created_at timestamptz not null
);
create table core.order_items (
    order_item_id bigint,
    order_id bigint not null,
    product_id bigint not null,
    qty integer not null,
    unit_price bigint not null,
    discount_pct numeric(6,4) not null,
    line_net_amount bigint not null
);
create table core.invoices (
    invoice_id bigint,
    order_id bigint not null,
    customer_id bigint not null,
    invoice_date date not null,
    accounting_period text not null,
    merchandise_amount bigint not null,
    freight_amount bigint not null,
    vat_amount bigint not null,
    total_amount bigint not null,
    created_at timestamptz not null
);
create table core.invoice_lines (
    invoice_line_id bigint,
    invoice_id bigint not null,
    line_no integer not null,
    line_type text not null,
    order_item_id bigint,
    product_id bigint,
    qty integer,
    unit_price bigint,
    discount_amount bigint,
    net_amount bigint not null,
    vat_amount bigint not null,
    unit_cost_actual bigint
);
create table core.payments (
    payment_id bigint,
    invoice_id bigint not null,
    payment_date date not null,
    amount bigint not null,
    method text not null,
    created_at timestamptz not null
);
create table core.returns (
    return_id bigint,
    invoice_id bigint not null,
    customer_id bigint not null,
    received_date date not null,
    reason_code text not null,
    status text not null,
    created_at timestamptz not null
);
create table core.return_items (
    return_item_id bigint,
    return_id bigint not null,
    invoice_line_id bigint not null,
    qty_returned integer not null
);
create table core.credit_notes (
    credit_note_id bigint,
    return_id bigint not null,
    invoice_id bigint not null,
    customer_id bigint not null,
    posting_date date not null,
    accounting_period text not null,
    merchandise_amount bigint not null,
    vat_amount bigint not null,
    total_amount bigint not null,
    cogs_reversal_amount bigint not null,
    created_at timestamptz not null
);
create table finance.monthly_pnl_extract (
    accounting_period text,
    gross_invoiced_merchandise bigint not null,
    credit_notes_merchandise bigint not null,
    net_merchandise_revenue bigint not null,
    freight_income bigint not null,
    cogs_invoiced bigint not null,
    cogs_reversed bigint not null,
    recognized_cogs bigint not null,
    gross_margin bigint not null,
    gross_margin_pct numeric(6,2),
    closed_at timestamptz not null,
    prepared_by text not null
);
create table analytics.delivered_sales (
    delivery_date date not null,
    order_id bigint not null,
    order_item_id bigint not null,
    customer_id bigint not null,
    sales_region text not null,
    product_id bigint not null,
    qty integer not null,
    gross_amount bigint not null,
    discount_amount bigint not null,
    net_amount bigint not null,
    std_unit_cost bigint not null,
    std_cost_amount bigint not null,
    loaded_at timestamptz not null
);
create table analytics.etl_job_runs (
    run_id bigint,
    job_name text not null,
    run_for_period text not null,
    started_at timestamptz not null,
    completed_at timestamptz not null,
    status text not null,
    rows_written integer not null
);
create table management.board_kpi_monthly (
    period text not null,
    kpi text not null,
    value numeric(20,2) not null,
    generated_at timestamptz not null,
    source_job text not null
);
"""

CONSTRAINTS = """
alter table core.customers add primary key (customer_id);
alter table core.customers add constraint customers_code_uniq unique (customer_code);
alter table core.products add primary key (product_id);
alter table core.products add constraint products_sku_uniq unique (sku);
alter table core.product_cost_history add primary key (cost_history_id);
alter table core.product_cost_history add foreign key (product_id) references core.products;
alter table core.orders add primary key (order_id);
alter table core.orders add foreign key (customer_id) references core.customers;
alter table core.order_items add primary key (order_item_id);
alter table core.order_items add foreign key (order_id) references core.orders;
alter table core.order_items add foreign key (product_id) references core.products;
alter table core.invoices add primary key (invoice_id);
alter table core.invoices add constraint invoices_order_uniq unique (order_id);
alter table core.invoices add foreign key (order_id) references core.orders;
alter table core.invoices add foreign key (customer_id) references core.customers;
alter table core.invoice_lines add primary key (invoice_line_id);
alter table core.invoice_lines add foreign key (invoice_id) references core.invoices;
alter table core.invoice_lines add foreign key (order_item_id) references core.order_items;
alter table core.invoice_lines add foreign key (product_id) references core.products;
alter table core.payments add primary key (payment_id);
alter table core.payments add foreign key (invoice_id) references core.invoices;
alter table core.returns add primary key (return_id);
alter table core.returns add foreign key (invoice_id) references core.invoices;
alter table core.returns add foreign key (customer_id) references core.customers;
alter table core.return_items add primary key (return_item_id);
alter table core.return_items add foreign key (return_id) references core.returns;
alter table core.return_items add foreign key (invoice_line_id) references core.invoice_lines;
alter table core.credit_notes add primary key (credit_note_id);
alter table core.credit_notes add constraint credit_notes_return_uniq unique (return_id);
alter table core.credit_notes add foreign key (return_id) references core.returns;
alter table core.credit_notes add foreign key (invoice_id) references core.invoices;
alter table core.credit_notes add foreign key (customer_id) references core.customers;
alter table finance.monthly_pnl_extract add primary key (accounting_period);
alter table analytics.delivered_sales add primary key (order_item_id);
alter table analytics.etl_job_runs add primary key (run_id);
alter table management.board_kpi_monthly add primary key (period, kpi);
create index on core.orders (delivery_date);
create index on core.invoices (accounting_period);
create index on core.invoice_lines (invoice_id);
create index on core.invoice_lines (order_item_id);
create index on core.order_items (order_id);
create index on core.payments (invoice_id);
create index on core.returns (invoice_id);
create index on core.return_items (return_id);
create index on core.credit_notes (accounting_period);
create index on core.product_cost_history (product_id, cost_type, effective_from);
create index on analytics.delivered_sales (delivery_date);
"""

# Fragmented documentation (SC-12.1): comments exist exactly where the
# contract says they exist; the sales_dashboard_monthly.revenue comment is
# deliberately stale (predates the February 2025 gross-of-returns change).
COMMENTS = [
    (
        "comment on table core.orders is "
        "'Customer orders. status open/cancelled/delivered; delivery_date is set "
        "when goods are handed to the customer and is never back-dated.'"
    ),
    (
        "comment on table core.invoices is "
        "'Sales invoices, one per delivered order, posted 0-3 working days after delivery.'"
    ),
    (
        "comment on column core.invoices.accounting_period is "
        "'Period in which merchandise revenue is recognized: always the period of invoice_date.'"
    ),
    (
        "comment on table core.credit_notes is "
        "'Credit notes for customer returns, one per credited return.'"
    ),
    (
        "comment on column core.credit_notes.accounting_period is "
        "'Period of posting_date, except period-end credits: a return received by the "
        "last day of a period and credited by its close is booked into that period.'"
    ),
    (
        "comment on table core.product_cost_history is "
        "'Unit cost history per product: standard (pricing team, revised each January "
        "and July) and actual (purchasing valuation, effective-dated).'"
    ),
    (
        "comment on table finance.monthly_pnl_extract is "
        "'Monthly closed P&L extract, one row per accounting period. Owned by Finance "
        "(DA); loaded at each period close by finance_revenue.sql.'"
    ),
    (
        "comment on table analytics.delivered_sales is "
        "'Refreshed nightly by refresh_delivered_sales (about 02:00 WIB, previous day''s deliveries).'"
    ),
    (
        "comment on column analytics.sales_dashboard_monthly.revenue is "
        "'Delivered merchandise for the month net of discounts and returns, ex VAT and freight.'"
    ),
]

DELIVERED_SALES_BACKFILL = """
insert into analytics.delivered_sales (
    delivery_date, order_id, order_item_id, customer_id, sales_region,
    product_id, qty, gross_amount, discount_amount, net_amount,
    std_unit_cost, std_cost_amount, loaded_at
)
select
    o.delivery_date,
    o.order_id,
    oi.order_item_id,
    o.customer_id,
    c.sales_region,
    oi.product_id,
    oi.qty,
    oi.qty * oi.unit_price,
    oi.qty * oi.unit_price - oi.line_net_amount,
    oi.line_net_amount,
    h.unit_cost,
    oi.qty * h.unit_cost,
    s.loaded_at
from core.orders o
join core.order_items oi on oi.order_id = o.order_id
join core.customers c on c.customer_id = o.customer_id
join lateral (
    select unit_cost
      from core.product_cost_history h
     where h.product_id = oi.product_id
       and h.cost_type = 'standard'
       and h.effective_from <= o.delivery_date
     order by h.effective_from desc
     limit 1
) h on true
join _northstar_load_schedule s on s.delivery_date = o.delivery_date
where o.status = 'delivered'
order by o.delivery_date, oi.order_item_id
"""


def load_postgres(ds: Dataset, dsn: str, progress=None) -> None:
    import psycopg

    scen = ds.scenario

    def note(msg: str) -> None:
        if progress:
            progress(msg)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for schema in SCHEMAS:
                cur.execute(f"drop schema if exists {schema} cascade")
                cur.execute(f"create schema {schema}")
            cur.execute("drop table if exists _northstar_load_schedule")
            for stmt in DDL.split(";"):
                if stmt.strip():
                    cur.execute(stmt)
            note("schemas created")

            for table, columns in TABLE_COLUMNS.items():
                rows = ds.tables[table]
                cols = ", ".join(columns)
                with cur.copy(f"copy {table} ({cols}) from stdin") as copy:
                    for row in rows:
                        copy.write_row(row)
                note(f"loaded {table} ({len(rows)} rows)")

            for stmt in CONSTRAINTS.split(";"):
                if stmt.strip():
                    cur.execute(stmt)
            cur.execute("analyze")
            note("constraints and indexes created")

            # Part III step 3: surfaces, each via its own SQL.
            cur.execute(
                "create table _northstar_load_schedule "
                "(delivery_date date primary key, loaded_at timestamptz not null)"
            )
            with cur.copy(
                "copy _northstar_load_schedule (delivery_date, loaded_at) from stdin"
            ) as copy:
                for d in sorted(ds.load_schedule):
                    copy.write_row((d, ds.load_schedule[d]))
            # Simulates the full history of nightly refresh_delivered_sales
            # runs in one set-based pass: same SELECT logic as the committed
            # refresh statement, standard cost effective at delivery (SC-8),
            # loaded_at from the job that loaded that delivery date.
            cur.execute(DELIVERED_SALES_BACKFILL)
            cur.execute("drop table _northstar_load_schedule")
            _, view_ddl = sales_dashboard_parts()
            cur.execute(view_ddl)
            note("analytics surface materialized")

            board_sql = board_pack_sql(with_snapshot_restriction=True)
            for period in scen.periods:
                close = scen.close_for(period)
                cur.execute(
                    board_sql,
                    {"period": period, "generated_at": close.snapshot_at},
                )
            note("board snapshots materialized")

            fin_sql = finance_close_sql()
            for period in scen.periods:
                close = scen.close_for(period)
                cur.execute(
                    fin_sql, {"period": period, "closed_at": close.close_at}
                )
            note("finance extract materialized")

            # Part III step 4: fragmented documentation.
            for stmt in COMMENTS:
                cur.execute(stmt)
        conn.commit()


# ---------------------------------------------------------------------------
# Post-load verification against the materialized surfaces
# ---------------------------------------------------------------------------


def verify_postgres(ds: Dataset, dsn: str) -> dict:
    """Reads the materialized surfaces back and cross-checks them against the
    independently computed Python-side expectations. Returns surface values."""
    import psycopg

    scen = ds.scenario
    e = ds.expected
    audit = scen.audit_period
    close = scen.close_for(audit)

    def check(cond: bool, msg: str) -> None:
        if not cond:
            raise GenerationError(f"surface verification failed: {msg}")

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "select gross_invoiced_merchandise, credit_notes_merchandise, "
            "net_merchandise_revenue, freight_income, cogs_invoiced, "
            "cogs_reversed, recognized_cogs, gross_margin, gross_margin_pct, "
            "closed_at, prepared_by from finance.monthly_pnl_extract "
            "where accounting_period = %s",
            (audit,),
        )
        fin = cur.fetchone()
        check(fin is not None, "finance extract row missing")
        check(fin[0] == e["g_post"], f"finance gross merchandise {fin[0]} != {e['g_post']}")
        check(fin[1] == e["c_period"], "finance credit merchandise mismatch")
        check(fin[2] == e["rnmr"], f"finance RNMR {fin[2]} != {e['rnmr']}")
        check(fin[3] == e["freight_income"], "finance freight income mismatch")
        check(fin[4] == e["k_post"], "finance invoiced COGS mismatch")
        check(fin[5] == e["r_period"], "finance reversed COGS mismatch")
        check(fin[6] == e["arc"], "finance ARC mismatch")
        check(fin[7] == e["fgm"], "finance FGM mismatch")
        check(fin[8] == e["fgm_pct"], f"finance margin pct {fin[8]} != {e['fgm_pct']}")
        check(fin[9] == close.close_at, "finance closed_at mismatch")

        cur.execute(
            "select coalesce(sum(revenue), 0), coalesce(sum(cogs_std), 0), "
            "coalesce(sum(margin), 0), coalesce(sum(returned_value), 0) "
            "from analytics.sales_dashboard_monthly where month = %s",
            (month_first(audit),),
        )
        sales = cur.fetchone()
        check(sales[0] == e["dsv"], f"sales DSV {sales[0]} != {e['dsv']}")
        check(sales[1] == e["k_std"], f"sales standard cost {sales[1]} != {e['k_std']}")
        check(sales[2] == e["cm"], f"sales CM {sales[2]} != {e['cm']}")

        cur.execute(
            "select kpi, value, generated_at from management.board_kpi_monthly "
            "where period = %s order by kpi",
            (audit,),
        )
        board = {kpi: (value, generated_at) for kpi, value, generated_at in cur.fetchall()}
        check(set(board) == {"Revenue", "Gross Margin", "Gross Margin %"}, "board KPI set")
        check(board["Revenue"][0] == e["br"], f"board revenue {board['Revenue'][0]} != {e['br']}")
        check(board["Gross Margin"][0] == e["bgm"], "board gross margin mismatch")
        check(board["Gross Margin %"][0] == e["bgm_pct"], "board margin pct mismatch")
        check(board["Revenue"][1] == close.snapshot_at, "board generated_at mismatch")

        # Freshness precondition: re-running the pack SQL against
        # horizon-state data does NOT reproduce the circulated snapshot.
        horizon_sql = board_pack_sql(with_snapshot_restriction=False).replace(
            "insert into management.board_kpi_monthly "
            "(period, kpi, value, generated_at, source_job)\n",
            "",
        )
        cur.execute(horizon_sql, {"period": audit, "generated_at": scen.observation_at})
        horizon_rows = {r[1]: r[2] for r in cur.fetchall()}
        check(
            horizon_rows["Revenue"] != e["br"],
            "horizon-state board rerun unexpectedly reproduces the snapshot",
        )
        expected_horizon_rev = e["dsv"] - (
            e["c_seen"] + e["vat_seen"] + e["c_late"] + e["vat_late"]
        )
        check(
            horizon_rows["Revenue"] == expected_horizon_rev,
            f"horizon-state board revenue {horizon_rows['Revenue']} != {expected_horizon_rev}",
        )
        conn.rollback()

    return {
        "finance": fin,
        "sales": sales,
        "board": {k: v[0] for k, v in board.items()},
    }


# ---------------------------------------------------------------------------
# Evidence directory and hidden ground truth (Part III steps 4-5)
# ---------------------------------------------------------------------------


def write_evidence(ds: Dataset, evidence_dir: Path) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for existing in sorted(evidence_dir.iterdir()):
        if existing.is_file():
            existing.unlink()
    for name in EVIDENCE_SOURCE_FILES:
        (evidence_dir / name).write_bytes((SCENARIO_DIR / name).read_bytes())
    e = ds.expected
    snapshot = e["board_snapshot_at"].isoformat()
    lines = ["period,kpi,value,generated_at"]
    for kpi, value in (
        ("Revenue", str(e["br"])),
        ("Gross Margin", str(e["bgm"])),
        ("Gross Margin %", str(e["bgm_pct"])),
    ):
        lines.append(f"{ds.scenario.audit_period},{kpi},{value},{snapshot}")
    (evidence_dir / "august_board_pack.csv").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    present = sorted(p.name for p in evidence_dir.iterdir() if p.is_file())
    if present != sorted(EVIDENCE_SOURCE_FILES + EVIDENCE_GENERATED_FILES):
        raise GenerationError(f"evidence inventory drifted: {present}")


def build_ground_truth(ds: Dataset) -> dict:
    scen = ds.scenario
    e = ds.expected
    audit = scen.audit_period
    close = scen.close_for(audit)
    sales_complete_at = ds.load_schedule[
        next_month_first(month_first(audit)) - ONE_DAY
    ]
    counts = {name.split(".", 1)[1]: len(rows) for name, rows in ds.tables.items()}
    return {
        "manifest_version": 2,
        "scenario": "northstar-2026-08-revenue-margin",
        "seed": scen.seed,
        "profile": ds.profile,
        "audit_period": audit,
        "decision_context": (
            "August 2026 Management/Board Financial-Performance Pack: board "
            "P&L view and separate commercial-performance view"
        ),
        "vat_rate_pct": scen.vat_pct,
        "timeline": {
            "history_start": scen.history_start.isoformat(),
            "period_end": (month_first(scen.open_period) - ONE_DAY).isoformat(),
            "sales_fact_complete_at": sales_complete_at.isoformat(),
            "board_snapshot_at": close.snapshot_at.isoformat(),
            "credit_batch_days": e["credit_batch_days"],
            "finance_close_at": close.close_at.isoformat(),
            "observation_at": scen.observation_at.isoformat(),
        },
        "surfaces": {
            "finance": {
                "object": "finance.monthly_pnl_extract",
                "snapshot_at": close.close_at.isoformat(),
                "concept": {"revenue": "RNMR", "margin": "FGM"},
                "reported": {
                    "revenue": e["rnmr"],
                    "gross_margin": e["fgm"],
                    "gross_margin_pct": str(e["fgm_pct"]),
                },
            },
            "sales": {
                "object": "analytics.sales_dashboard_monthly",
                "snapshot_at": sales_complete_at.isoformat(),
                "concept": {"revenue": "DSV", "margin": "CM"},
                "reported": {
                    "revenue": e["dsv"],
                    "gross_margin": e["cm"],
                    "gross_margin_pct": str(e["cm_pct"]),
                },
            },
            "board": {
                "object": "management.board_kpi_monthly",
                "snapshot_at": close.snapshot_at.isoformat(),
                "concept": {"revenue": "BR (hybrid)", "margin": "BGM (hybrid)"},
                "reported": {
                    "revenue": e["br"],
                    "gross_margin": e["bgm"],
                    "gross_margin_pct": str(e["bgm_pct"]),
                },
            },
        },
        "intermediate": {
            "g_post": e["g_post"],
            "c_period": e["c_period"],
            "c_late": e["c_late"],
            "c_seen_by_board": e["c_seen"],
            "vat_on_credits_seen_by_board": e["vat_seen"],
            "d1": e["d1"],
            "d2": e["d2"],
            "k_post": e["k_post"],
            "k1": e["k1"],
            "k2": e["k2"],
            "k_act": e["k_act"],
            "k_std": e["k_std"],
            "r_period": e["r_period"],
            "r_early": e["r_early"],
            "r_late": e["r_late"],
            "freight_income": e["freight_income"],
        },
        "expected_by_context": {
            "finance": {"rnmr": e["rnmr"], "arc": e["arc"], "fgm": e["fgm"]},
            "sales": {"dsv": e["dsv"], "standard_cost": e["k_std"], "cm": e["cm"]},
            "board_as_reported": {"br": e["br"], "bgm": e["bgm"]},
        },
        "bridges": {
            "revenue_finance_to_sales": [
                {
                    "line": "period_basis_delivery_vs_posting",
                    "category": "definition",
                    "amount": e["d1"] - e["d2"],
                },
                {
                    "line": "gross_of_returns_vs_net_of_credits",
                    "category": "definition",
                    "amount": e["c_period"],
                },
            ],
            "revenue_finance_to_board": [
                {
                    "line": "period_basis_delivery_vs_posting",
                    "category": "definition",
                    "amount": e["d1"] - e["d2"],
                },
                {
                    "line": "back_dated_credit_notes_after_snapshot",
                    "category": "timing",
                    "amount": e["c_late"],
                },
                {
                    "line": "vat_inclusive_credit_deduction",
                    "category": "defect",
                    "amount": -e["vat_seen"],
                },
            ],
            "gross_margin_finance_to_sales": [
                {
                    "line": "revenue_bridge_finance_to_sales",
                    "category": "by_line",
                    "amount": e["dsv"] - e["rnmr"],
                },
                {
                    "line": "period_basis_on_cost",
                    "category": "definition",
                    "amount": -(e["k1"] - e["k2"]),
                },
                {
                    "line": "standard_vs_actual_cost",
                    "category": "cost_basis",
                    "amount": -(e["k_std"] - e["k_act"]),
                },
                {
                    "line": "no_cogs_reversal_consistent_with_gross_revenue",
                    "category": "definition",
                    "amount": -e["r_period"],
                },
            ],
            "gross_margin_finance_to_board": [
                {
                    "line": "revenue_bridge_finance_to_board",
                    "category": "by_line",
                    "amount": e["br"] - e["rnmr"],
                },
                {
                    "line": "period_basis_on_cost",
                    "category": "definition",
                    "amount": -(e["k1"] - e["k2"]),
                },
                {
                    "line": "standard_vs_actual_cost",
                    "category": "cost_basis",
                    "amount": -(e["k_std"] - e["k_act"]),
                },
                {
                    "line": "cogs_reversal_on_credits_after_snapshot",
                    "category": "timing",
                    "amount": -e["r_late"],
                },
                {
                    "line": "cogs_not_reversed_on_credits_seen_by_board",
                    "category": "defect",
                    "amount": -e["r_early"],
                },
            ],
        },
        "board_defect": {
            "description": (
                "board_pack.sql deducts VAT-inclusive credit-note totals "
                "(total_amount) from an ex-VAT delivered-sales figure, and "
                "nets the credit notes it can see from Revenue without "
                "reversing their standard cost in Gross Margin. Both errors "
                "apply to the credits that existed at the pack snapshot; the "
                "credits posted after the snapshot are a timing difference, "
                "not part of the defect."
            ),
            "components": [
                {"line": "vat_inclusive_credit_deduction", "amount": -e["vat_seen"]},
                {
                    "line": "cogs_not_reversed_on_credits_seen_by_board",
                    "amount": -e["r_early"],
                },
            ],
        },
        "recommended_basis": {
            "board_financial_performance_pnl": "finance",
            "sales_commercial_performance": "sales",
            "board_pack_presentation": (
                "present finance P&L and sales commercial figures separately, "
                "labelled, regenerated after the Finance close; retire the hybrid"
            ),
        },
        "supporting_findings": [
            {
                "id": "board_pack_snapshot_precedes_finance_close",
                "summary": (
                    "The board pack for the audit period was generated at the "
                    "second business day snapshot, before Finance's period-end "
                    "back-dated credit batches and close; the Finance close is "
                    "the only complete snapshot of the period."
                ),
                "evidence": [
                    "management.board_kpi_monthly.generated_at",
                    "analytics.etl_job_runs",
                    "core.credit_notes.posting_date vs accounting_period",
                    "finance.monthly_pnl_extract.closed_at",
                ],
            },
            {
                "id": "no_agreed_board_pack_revenue_definition_or_owner",
                "summary": (
                    "Finance and Sales each hold an internally coherent Revenue "
                    "definition, but the board pack's hybrid definition exists "
                    "only in an inherited query and a stale 2024 handover note "
                    "with no named owner."
                ),
                "evidence": [
                    "board_pack_handover.md",
                    "comment on analytics.sales_dashboard_monthly.revenue (stale)",
                    "management.board_kpi_monthly (no comments)",
                    "finance_close_notes.md (silent on the pack)",
                ],
            },
        ],
        "scale": {
            "tables": counts,
            "august": {
                "delivered_orders": e["aug_delivered_orders"],
                "credit_notes_in_period": e["aug_seen_credit_count"]
                + e["aug_late_credit_count"],
                "credit_notes_after_snapshot": e["aug_late_credit_count"],
                "credit_notes_seen_by_board": e["aug_seen_credit_count"],
            },
        },
    }


def write_ground_truth(ds: Dataset, ground_truth_dir: Path) -> Path:
    ground_truth_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_ground_truth(ds)
    if "true_revenue" in json.dumps(manifest):
        raise GenerationError("ground truth must not claim a universal true revenue")
    path = ground_truth_dir / "northstar-2026-08-revenue-margin.json"
    path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2, separators=(",", ": ")) + "\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def run(
    profile: str,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    dsn: str | None = None,
    out_root: Path | str | None = None,
    quiet: bool = False,
) -> dict:
    config = load_config(config_path)

    def note(msg: str) -> None:
        if not quiet:
            print(f"[generate] {msg}", flush=True)

    if dsn is None:
        env_var = config["postgresql"]["dsn_env_var"]
        dsn = os.environ.get(env_var)
        if not dsn:
            raise GenerationError(
                f"set {env_var} to the target PostgreSQL DSN before generating"
            )
    out_root = Path(out_root) if out_root is not None else REPO_ROOT

    note(f"building dataset (profile={profile})")
    ds = build_dataset(config, profile)
    note(
        "dataset built: "
        + ", ".join(f"{k.split('.')[1]}={len(v)}" for k, v in sorted(ds.tables.items()))
    )
    load_postgres(ds, dsn, progress=note if not quiet else None)
    surfaces = verify_postgres(ds, dsn)
    note("surfaces verified against independent recomputation")

    evidence_dir = out_root / config["generation"]["data_dir"] / "evidence"
    write_evidence(ds, evidence_dir)
    gt_path = write_ground_truth(ds, out_root / config["generation"]["ground_truth_dir"])
    note(f"evidence written to {evidence_dir}")
    note(f"ground truth written to {gt_path}")

    e = ds.expected
    summary = {
        "profile": profile,
        "fingerprint": dataset_fingerprint(ds),
        "tables": {k: len(v) for k, v in ds.tables.items()},
        "rnmr": e["rnmr"], "arc": e["arc"], "fgm": e["fgm"],
        "fgm_pct": str(e["fgm_pct"]),
        "dsv": e["dsv"], "k_std": e["k_std"], "cm": e["cm"],
        "cm_pct": str(e["cm_pct"]),
        "br": e["br"], "bgm": e["bgm"], "bgm_pct": str(e["bgm_pct"]),
        "bridge": {
            "d1": e["d1"], "d2": e["d2"], "c_period": e["c_period"],
            "c_late": e["c_late"], "vat_seen": e["vat_seen"],
            "k1": e["k1"], "k2": e["k2"], "k_act": e["k_act"],
            "r_period": e["r_period"], "r_early": e["r_early"],
            "r_late": e["r_late"],
        },
        "evidence_dir": str(evidence_dir),
        "ground_truth": str(gt_path),
        "surfaces": {"board": {k: str(v) for k, v in surfaces["board"].items()}},
    }
    if not quiet:
        note(
            f"August 2026 -- RNMR {e['rnmr']:,} / DSV {e['dsv']:,} / BR {e['br']:,}; "
            f"FGM {e['fgm']:,} ({e['fgm_pct']}%) / CM {e['cm']:,} ({e['cm_pct']}%) / "
            f"BGM {e['bgm']:,} ({e['bgm_pct']}%)"
        )
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the Northstar Distribution demo environment."
    )
    parser.add_argument(
        "--profile",
        required=True,
        help="scale profile from benchmark.toml (e.g. smoke, demo)",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="path to benchmark.toml",
    )
    args = parser.parse_args(argv)
    try:
        run(args.profile, config_path=args.config)
    except GenerationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
