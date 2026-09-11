"""Every displayed generated amount/rate in the committed audit has a check anchor."""

import re
from decimal import Decimal

import pytest

from benchmark.generate import ROOT
from benchmark.scenario.reconcile import verify_scenario

REPORT = ROOT / "report/samples/northstar-august-2026-audit.md"
PDF = REPORT.with_suffix(".pdf")
NUMBER = re.compile(r"(Rp -?[\d,]+|-?[\d.]+(?:%| pp)) <!-- number:([\w.]+) -->")


def report_numbers(result):
    v = dict(result["values"])
    v.update(board_revenue_difference=v["BR"]-v["RNMR"],
             board_margin_difference=v["BGM"]-v["FGM"],
             board_revenue_difference_pct=Decimal(v["BR"]-v["RNMR"])/v["RNMR"],
             board_margin_difference_pp=Decimal(v["board_margin_pct"])-Decimal(v["finance_margin_pct"]))
    for bridge, lines in result["bridges"].items():
        for line in lines:
            v[bridge + "." + line["line"]] = line["amount"]
            baseline = v["RNMR"] if bridge.startswith("revenue") else v["FGM"]
            v[bridge + "." + line["line"] + ".pct"] = Decimal(line["amount"]) / baseline
    for key, row in result["materiality"].items():
        v["materiality." + key] = row["observed"]
    return v


def test_sample_report_numbers(dataset):
    conn, cfg, profile, *_ = dataset
    if profile != "demo":
        pytest.skip("Committed audit uses demo; enable NORTHSTAR_QA_DEMO=1 for numeric verification")
    result = verify_scenario(conn, cfg)
    expected = report_numbers(result)
    text = REPORT.read_text(encoding="utf-8")
    anchors = NUMBER.findall(text)
    assert {key for _,key in anchors} == set(expected), "Every generated component and every bridge line must be checked"
    for token, key in anchors:
        if token.startswith("Rp "):
            assert token == f"Rp {int(expected[key]):,}", key
        else:
            suffix = " pp" if token.endswith(" pp") else "%"
            assert token == f"{Decimal(str(expected[key]))*100:.4f}{suffix}", key
    # Money outside an anchor would bypass evidence validation.
    assert not re.search(r"Rp -?[\d,]+", NUMBER.sub("", text))
    assert "23 of 23 supplied assets inspected" in text
    assert cfg["scenario"]["audit_period"] in text
    # Threshold claims are separately checked against the canonical configuration.
    t = cfg["materiality"]
    for claim in (f"{t['credit_rnmr_min']*100:.1f}%-{t['credit_rnmr_max']*100:.1f}%",
                  f"At least {t['late_credit_share_min']*100:g}%",
                  f"At least {t['period_leg_rnmr_min']*100:g}%",
                  f"At least {t['cost_difference_min']*100:g}%",
                  f"At least {t['pairwise_revenue_rnmr_min']*100:g}%",
                  f"At least {t['pairwise_margin_pct_min']*100:g} pp",
                  f"{t['finance_margin_min']*100:g}%-{t['finance_margin_max']*100:g}%"):
        assert claim in text


def test_sample_report_pdf_and_context():
    text = REPORT.read_text(encoding="utf-8")
    assert "Synthetic demonstration - not a real client engagement" in text
    assert "CONFLICTING" in text and "fully reconciled" in text
    assert "R_period = R_early + R_late" in text
    assert "not cash losses" in text
    assert "accountable" in text and "re-check" in text
    assert PDF.is_file()
    raw = PDF.read_bytes()
    assert raw.startswith(b"%PDF")
    # ReportLab's uncompressed Tj text fragments let this specific artifact be
    # checked without a PDF-library dependency. A line/font boundary may split Rp
    # from the following amount; normalize the extracted text fragments first.
    fragments = re.findall(rb"\(((?:\\.|[^\\()])*)\)\s*Tj", raw)
    visible = re.sub(r"\s+", " ", b" ".join(fragments).decode("latin-1"))
    for token, _ in NUMBER.findall(text):
        assert token in visible, f"PDF missing or outdated amount: {token}"
