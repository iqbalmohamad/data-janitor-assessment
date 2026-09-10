"""Guards on the canonical benchmark configuration (M0 governance baseline).

These tests pin the invariants the M0 assignment declares canonical:
the seed, the required dataset list, and the config's basic sanity.
The M0 implementation adds generator/output tests beside this file
(see "Current Assignment.md" section 10).
"""

import tomllib
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "benchmark" / "config" / "benchmark.toml"

CANONICAL_SEED = 20260910

REQUIRED_DATASETS = {
    "customers",
    "products",
    "orders",
    "order_items",
    "payments",
    "returns",
    "customer_export",
    "metric_definitions",
    "pipeline_runs",
    "dataset_registry",
}

# Optional datasets included with justification recorded in
# "Current Assignment.md" section 7.
JUSTIFIED_OPTIONAL_DATASETS = {
    "sales_summary",
    "customer_master_legacy",
}


def load_config():
    with CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)


def test_config_exists_and_parses():
    assert CONFIG_PATH.is_file()
    config = load_config()
    assert "generation" in config
    assert "row_counts" in config


def test_canonical_seed():
    config = load_config()
    assert config["generation"]["seed"] == CANONICAL_SEED


def test_as_of_date_is_fixed_date():
    config = load_config()
    as_of = date.fromisoformat(config["generation"]["as_of_date"])
    assert as_of == date(2026, 9, 1)


def test_all_required_datasets_have_row_counts():
    config = load_config()
    row_counts = config["row_counts"]
    missing = REQUIRED_DATASETS - set(row_counts)
    assert not missing, f"required datasets missing row counts: {sorted(missing)}"


def test_no_unapproved_datasets():
    config = load_config()
    allowed = REQUIRED_DATASETS | JUSTIFIED_OPTIONAL_DATASETS
    extra = set(config["row_counts"]) - allowed
    assert not extra, f"datasets outside the M0-approved list: {sorted(extra)}"


def test_row_counts_positive_and_laptop_scale():
    config = load_config()
    for name, count in config["row_counts"].items():
        assert isinstance(count, int) and count > 0, name
        assert count <= 1_000_000, f"{name} exceeds benchmark scale"


def test_output_dirs_separate_data_from_ground_truth():
    config = load_config()
    gen = config["generation"]
    out = Path(gen["output_dir"])
    gt = Path(gen["ground_truth_dir"])
    assert out != gt
    assert gt not in out.parents and out not in gt.parents, (
        "ground truth must stay separate from assessment inputs"
    )
