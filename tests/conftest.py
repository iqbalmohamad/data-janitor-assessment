"""Offline checks always run; PostgreSQL acceptance is explicitly opt-in."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.generate import generate, load_config
from benchmark.load_duckdb import load
from benchmark.scenario.reconcile import verify_scenario, manifest

PROFILES = ["smoke", "demo"] if os.environ.get("NORTHSTAR_QA_DEMO") == "1" else ["smoke"]
BACKENDS = ["offline", "postgresql"]


@pytest.fixture(scope="session", params=[(b, p) for b in BACKENDS for p in PROFILES])
def dataset(request, tmp_path_factory):
    backend, profile = request.param
    cfg = load_config(profile=profile)
    root = tmp_path_factory.mktemp(f"{backend}-{profile}")
    data, truth = root / "data", root / "hidden"
    if backend == "offline":
        conn, counts = load(cfg, profile, data)
        result = verify_scenario(conn, cfg)
        expected = manifest(conn, cfg, profile, counts, result)
        truth.mkdir()
        (truth / f"{profile}.json").write_text(json.dumps(expected, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
        yield conn, cfg, profile, data, truth, expected, backend
        conn.connection.close()
    else:
        dsn = os.environ.get("NORTHSTAR_TEST_DATABASE_URL")
        if not dsn:
            pytest.skip("Set NORTHSTAR_TEST_DATABASE_URL to a local PostgreSQL role allowed to CREATE DATABASE")
        import psycopg
        from psycopg import sql
        from psycopg.conninfo import make_conninfo
        name = f"northstar_qa_{os.getpid()}_{profile}"
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            target = make_conninfo(dsn, dbname=name)
            key = cfg["postgresql"]["dsn_env_var"]
            previous = os.environ.get(key)
            os.environ[key] = target
            try:
                expected = generate(cfg, profile, data, truth)
                with psycopg.connect(target) as conn:
                    yield conn, cfg, profile, data, truth, expected, backend
            finally:
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
