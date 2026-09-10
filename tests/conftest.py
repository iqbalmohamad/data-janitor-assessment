"""Shared fixtures for the M0 test suite.

The generator is a script, not an installed package; it is loaded by file
path. Tests that need PostgreSQL read the DSN from the canonical
environment variable (benchmark.toml postgresql.dsn_env_var) and skip
cleanly when it is not set -- see README.md for the disposable-instance
setup used for the canonical acceptance run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relpath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def gen():
    return load_module("northstar_generate", "benchmark/generate.py")


@pytest.fixture(scope="session")
def config(gen):
    return gen.load_config()


@pytest.fixture(scope="session")
def smoke_dataset(gen, config):
    return gen.build_dataset(config, "smoke")
