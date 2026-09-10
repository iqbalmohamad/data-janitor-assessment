"""Guards on the canonical benchmark configuration (revised M0 governance
baseline, per SPEC.md Amendment 001).

These tests pin the invariants the revised M0 assignment declares
canonical: the seed, the PostgreSQL-as-canonical / DuckDB-as-internal
environment split, the canonical schema set, and the two scale profiles.
The scenario itself is fixed by the Scenario Contract (benchmark/README.md,
Part II); the M0 implementation adds generator/output/reconciliation tests
beside this file (see "Current Assignment.md" section 10).
"""

import tomllib
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "benchmark" / "config" / "benchmark.toml"

CANONICAL_SEED = 20260910

# Independently generated core tables that carry configured row counts
# (benchmark/README.md, Scenario Contract SC-7 / SC-14). The remaining
# lifecycle tables (invoices, invoice_lines, return_items, credit_notes,
# product_cost_history) are derived from these and carry no counts.
CONFIGURED_SCALE_TABLES = {
    "customers",
    "products",
    "orders",
    "order_items",
    "payments",
    "returns",
}

# Canonical PostgreSQL schema set (Scenario Contract SC-7 / SC-9).
CANONICAL_SCHEMAS = {"core", "finance", "analytics", "management"}

REQUIRED_SCALE_PROFILES = {"demo", "smoke"}


def load_config():
    with CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)


def test_config_exists_and_parses():
    assert CONFIG_PATH.is_file()
    config = load_config()
    assert "generation" in config
    assert "postgresql" in config
    assert "duckdb" in config
    assert "scale" in config


def test_canonical_seed():
    config = load_config()
    assert config["generation"]["seed"] == CANONICAL_SEED


def test_as_of_date_is_fixed_date():
    config = load_config()
    as_of = date.fromisoformat(config["generation"]["as_of_date"])
    assert as_of == date(2026, 9, 1)


def test_scenario_is_reconciliation_not_six_dimension_catalog():
    config = load_config()
    # The revised M0 targets one reconciliation scenario, not a
    # six-dimension defect catalog (SPEC.md Amendment section Q).
    assert "scenario" in config["generation"]
    assert config["generation"]["scenario"]


def test_postgresql_is_canonical_with_no_hardcoded_credentials():
    config = load_config()
    pg = config["postgresql"]
    assert "dsn_env_var" in pg, "connection must come from an env var, never a literal DSN"
    for key, value in pg.items():
        if isinstance(value, str):
            assert "://" not in value, f"postgresql.{key} looks like a hard-coded connection string"
    assert set(pg["schemas"]) == CANONICAL_SCHEMAS


def test_duckdb_is_marked_as_internal_only():
    config = load_config()
    duckdb_cfg = config["duckdb"]
    # A dev/test mirror path is fine; DuckDB must never be configured as
    # the canonical target (that's postgresql's job).
    assert "dsn_env_var" not in duckdb_cfg


def test_both_scale_profiles_present():
    config = load_config()
    scale = config["scale"]
    missing = REQUIRED_SCALE_PROFILES - set(scale)
    assert not missing, f"missing scale profiles: {sorted(missing)}"


def test_smoke_profile_is_smaller_than_demo_profile():
    config = load_config()
    demo = config["scale"]["demo"]
    smoke = config["scale"]["smoke"]
    for key in smoke:
        assert key in demo, f"smoke profile has unknown table '{key}'"
        assert smoke[key] < demo[key], f"smoke.{key} should be smaller than demo.{key}"


def test_scale_profiles_cover_configured_tables():
    config = load_config()
    for profile_name in REQUIRED_SCALE_PROFILES:
        profile = config["scale"][profile_name]
        missing = CONFIGURED_SCALE_TABLES - set(profile)
        assert not missing, f"{profile_name} profile missing row counts: {sorted(missing)}"


def test_row_counts_positive_and_laptop_scale():
    config = load_config()
    for profile_name, profile in config["scale"].items():
        for name, count in profile.items():
            assert isinstance(count, int) and count > 0, f"{profile_name}.{name}"
            assert count <= 5_000_000, f"{profile_name}.{name} exceeds benchmark scale"


def test_ground_truth_dir_is_separate_from_generation_output():
    config = load_config()
    gt = Path(config["generation"]["ground_truth_dir"])
    duckdb_mirror = Path(config["duckdb"]["dev_mirror_path"])
    assert gt != duckdb_mirror
    assert gt not in duckdb_mirror.parents and duckdb_mirror not in gt.parents, (
        "ground truth must stay separate from generated/assessment-visible data"
    )
