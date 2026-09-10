"""Guards on the committed scenario sources and the no-leak rules (SC-12).

These tests make the ground-truth separation meaningful rather than merely
documented: assessment-visible artifacts (surface SQL, notes, database
comments) must never disclose the planted diagnosis, and the generator
source must obey the deterministic-generation rules.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DIR = REPO_ROOT / "benchmark" / "scenario"

# SC-12.3: none of these may appear in any assessment-visible artifact --
# names, comments, or contents. (Reason-code data values such as
# 'wrong_item' are business data, not metadata, and are checked separately.)
FORBIDDEN_TOKENS = [
    "is_wrong",
    "expected_revenue",
    "correct_definition",
    "true_value",
    "true_revenue",
    "mechanism",
    "planted",
    "scenario",
    "defect",
    "ground_truth",
    "ground truth",
    "intentional",
    "hardcoded",
    "known_issue",
    "known issue",
    "broken",
    "bug",
]

EXPECTED_SOURCES = {
    "finance_revenue.sql",
    "sales_dashboard.sql",
    "board_pack.sql",
    "finance_close_notes.md",
    "sales_dashboard_notes.md",
    "board_pack_handover.md",
}


def assert_clean(text: str, where: str) -> None:
    lowered = text.lower()
    for token in FORBIDDEN_TOKENS:
        assert token not in lowered, f"answer-leaking token {token!r} in {where}"


def test_scenario_source_inventory_matches_contract(gen):
    present = {p.name for p in SCENARIO_DIR.iterdir() if p.is_file()}
    assert present == EXPECTED_SOURCES
    # the generated evidence directory adds exactly the circulated pack CSV
    assert set(gen.EVIDENCE_SOURCE_FILES) == EXPECTED_SOURCES
    assert gen.EVIDENCE_GENERATED_FILES == ["august_board_pack.csv"]


def test_scenario_sources_do_not_leak(gen):
    for path in sorted(SCENARIO_DIR.iterdir()):
        assert_clean(path.name, "file name")
        assert_clean(path.read_text(encoding="utf-8"), path.name)


def test_database_comments_do_not_leak(gen):
    for stmt in gen.COMMENTS:
        assert_clean(stmt, "database comment")


def test_no_registry_style_objects(gen):
    ddl = gen.DDL.lower()
    for name in ("metric_definitions", "dataset_registry", "kpi_catalog",
                 "metric_catalog", "data_dictionary"):
        assert name not in ddl


def test_stale_dashboard_comment_contradicts_current_view(gen):
    """SC-11: the revenue column comment still claims net-of-returns while
    the committed view SQL is gross of returns."""
    stale = [c for c in gen.COMMENTS if "sales_dashboard_monthly.revenue" in c]
    assert len(stale) == 1
    assert "net of discounts and returns" in stale[0]
    view_sql = (SCENARIO_DIR / "sales_dashboard.sql").read_text(encoding="utf-8")
    # the view computes revenue from delivered_sales.net_amount only;
    # returns feed the separate returned_value column
    assert "sum(ds.net_amount) as revenue" in view_sql
    assert "returned_value" in view_sql


def test_scenario_sql_renders_for_execution(gen):
    # occurrence-checked substitutions guarantee that the SQL the generator
    # executes is the committed evidence SQL, not a drifted copy
    assert "%(period)s" in gen.finance_close_sql()
    snapshot_sql = gen.board_pack_sql(with_snapshot_restriction=True)
    assert snapshot_sql.count("created_at <= %(generated_at)s") == 1
    horizon_sql = gen.board_pack_sql(with_snapshot_restriction=False)
    assert "created_at" not in horizon_sql
    refresh, view_ddl = gen.sales_dashboard_parts()
    assert len(refresh) == 2  # delete + insert
    assert view_ddl.startswith("create or replace view")


def test_generator_obeys_deterministic_generation_rules(config):
    """No wall-clock reads, no uuid4/os.urandom, and the canonical seed is
    read from configuration, never hardcoded (assignment section 9)."""
    for path in sorted((REPO_ROOT / "benchmark").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for banned in ("datetime.now(", "date.today(", "time.time(",
                       "os.urandom", "uuid4", "utcnow("):
            assert banned not in source, f"{banned} used in {path.name}"
        assert str(config["generation"]["seed"]) not in source, (
            f"canonical seed hardcoded in {path.name}"
        )
        # only contracted-stable RNG primitives (assignment section 9)
        for banned in (".choices(", ".shuffle(", ".sample(", ".gauss(",
                       ".randint(", ".choice("):
            assert banned not in source, f"{banned} used in {path.name}"


def test_generated_output_stays_out_of_git(config):
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "benchmark/data/" in gitignore
    assert "benchmark/ground_truth/" in gitignore
    gt_dir = Path(config["generation"]["ground_truth_dir"])
    data_dir = Path(config["generation"]["data_dir"])
    assert gt_dir != data_dir
    assert data_dir not in gt_dir.parents and gt_dir not in data_dir.parents


def test_ground_truth_never_read_by_assessment_visible_logic(gen):
    """The scenario SQL (the only logic an assessor sees) references only
    core and surface objects -- never the ground-truth directory."""
    for path in sorted(SCENARIO_DIR.glob("*.sql")):
        text = path.read_text(encoding="utf-8").lower()
        assert "json" not in text
        for schema in re.findall(r"\bfrom\s+([a-z_]+)\.", text):
            assert schema in {"core", "finance", "analytics", "management"}


def test_no_natural_person_fields(gen):
    """SC-16: no PII scenario -- the schema carries no natural-person
    fields and the notes refer to staff by initials only."""
    ddl = gen.DDL.lower()
    for banned in ("contact_name", "email", "phone", "first_name", "last_name",
                   "birth", "national_id", "ktp", "npwp", "address"):
        assert banned not in ddl
    for path in sorted(SCENARIO_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        assert "@" not in text  # no email addresses
        assert not re.search(r"\+?\d[\d\s-]{8,}\d", text)  # no phone numbers
