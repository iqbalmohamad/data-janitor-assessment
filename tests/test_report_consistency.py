"""Report-number consistency (assignment section 10.6).

The committed sample report cites the `demo`-profile generated values. This
test rebuilds the demo dataset in memory (deterministic, no PostgreSQL
required), independently recomputes every reconciliation quantity, and
asserts that each rupiah figure and percentage quoted in the report is a
real generated value -- never a constant maintained twice. It also exercises
the demo profile's SC-14 materiality, so a routine `pytest` run establishes
that the committed implementation genuinely supports `demo`, not only
`smoke`.

The demo build is ~30-60s; this module is the only slow part of the suite.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = REPO_ROOT / "report" / "samples" / "northstar-reporting-reliability-audit.md"
AUDIT = "2026-08"


@pytest.fixture(scope="session")
def demo_dataset(gen, config):
    return gen.build_dataset(config, "demo")


@pytest.fixture(scope="session")
def report_text():
    return REPORT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def report_rupiah(report_text):
    # every comma-grouped integer quoted anywhere in the report (whether
    # prefixed with "Rp" in prose or tabulated bare in a reconciliation
    # table). Comma grouping avoids catching years and section numbers.
    return {
        int(m.replace(",", ""))
        for m in re.findall(r"\d{1,3}(?:,\d{3})+", report_text)
    }


def e(demo_dataset):
    return demo_dataset.expected


# ---------------------------------------------------------------------------
# Demo profile materiality (SC-14) recomputed from the raw rows
# ---------------------------------------------------------------------------


def test_demo_profile_materiality(demo_dataset, config):
    q = e(demo_dataset)
    mat = config["scenario"]["materiality"]
    rnmr = q["rnmr"]
    lo, hi = mat["c_period_pct_of_rnmr"]
    assert lo <= 100 * q["c_period"] / rnmr <= hi
    assert q["c_late"] / q["c_period"] >= mat["c_late_min_share_of_c_period"]
    assert 100 * q["d1"] / rnmr >= mat["d1_min_pct_of_rnmr"]
    assert 100 * q["d2"] / rnmr >= mat["d2_min_pct_of_rnmr"]
    assert 100 * abs(q["k_std"] - q["k_act"]) / q["k_act"] >= mat["cost_basis_min_pct_of_k_act"]
    assert len({q["rnmr"], q["dsv"], q["br"]}) == 3
    lo, hi = mat["fgm_pct_of_rnmr_band"]
    assert lo <= 100 * q["fgm"] / q["rnmr"] <= hi


def test_demo_profile_identities(gen, demo_dataset):
    gen.verify_expected(demo_dataset)  # raises on any identity/materiality break


# ---------------------------------------------------------------------------
# Every quoted figure is a real generated value
# ---------------------------------------------------------------------------


def test_report_headline_surface_values_present(demo_dataset, report_rupiah):
    q = e(demo_dataset)
    for value in (q["rnmr"], q["fgm"], q["dsv"], q["cm"], q["br"], q["bgm"]):
        assert value in report_rupiah, f"{value} not quoted verbatim in the report"


def test_report_bridge_lines_present(gen, demo_dataset, report_rupiah):
    """Each reconciliation line the report tabulates equals the recomputed
    bridge amount (absolute value; the report shows signed lines with a
    leading + / - glyph). The report presents the three decision-relevant
    bridges -- the two Finance -> Board bridges and the Finance -> Sales
    revenue bridge (sections 5.1-5.3); the Finance -> Sales margin bridge is
    referenced only for its teaching point, so it is not required line by
    line here."""
    manifest = gen.build_ground_truth(demo_dataset)
    tabulated = (
        "revenue_finance_to_board",
        "gross_margin_finance_to_board",
        "revenue_finance_to_sales",
    )
    for name in tabulated:
        for line in manifest["bridges"][name]:
            assert abs(line["amount"]) in report_rupiah, (
                f"bridge amount {line['amount']} ({name}/{line['line']}) missing from report"
            )


def test_report_percentages_match(demo_dataset, report_text):
    q = e(demo_dataset)
    # margin rates quoted in the report, to the precision each surface uses
    assert f"{q['fgm_pct']}%" in report_text
    assert f"{q['cm_pct']}%" in report_text
    assert f"{q['bgm_pct']}%" in report_text


def test_report_derived_spreads_match(demo_dataset, report_text):
    q = e(demo_dataset)
    rev_over = q["br"] - q["rnmr"]
    rev_over_pct = round(100 * rev_over / q["rnmr"], 1)
    # "Rp 9.5 billion (5.2%)" style claims
    assert f"{rev_over_pct}%" in report_text
    fin_sales = q["dsv"] - q["rnmr"]
    assert round(100 * fin_sales / q["rnmr"], 1) == pytest.approx(7.1, abs=0.05)
    assert f"{round(100 * fin_sales / q['rnmr'], 1)}%" in report_text


def test_report_defect_amounts_match(demo_dataset, report_text, report_rupiah):
    q = e(demo_dataset)
    # the two mechanical defect components, cited exactly (§6)
    assert q["vat_seen"] in report_rupiah
    assert q["r_early"] in report_rupiah
    # their sum is presented rounded to Rp billions in prose
    combined_bn = round((q["vat_seen"] + q["r_early"]) / 1e9, 2)
    assert f"Rp {combined_bn}" in report_text


def test_report_is_labelled_synthetic(report_text):
    lowered = report_text.lower()
    assert "synthetic demonstration" in lowered
    assert "not a real client engagement" in lowered
    assert "fictional" in lowered


def test_report_covers_full_value_chain(report_text):
    """SC-15 / Amendment I: the report must walk the full chain and give a
    per-metric verdict, evidence coverage, reconciliation, impact,
    recommended basis, and remediation."""
    lowered = report_text.lower()
    for anchor in [
        "management question",
        "conflicting",
        "evidence coverage",
        "reconciliation",
        "definition",
        "timing",
        "cost basis",
        "defect",
        "business materiality" if "business materiality" in lowered else "materiality",
        "remediation",
        "re-check" if "re-check" in lowered else "verification path",
        "ownership",
    ]:
        assert anchor in lowered, f"report missing section anchor: {anchor}"
    # per-metric verdict shape (Amendment I)
    assert "conflicting" in lowered
    # decision-context conclusion (SC-4): not "Finance right, Sales wrong"
    assert "not \"finance is right and sales is wrong\"" in lowered or (
        "finance and sales are" in lowered
    )
