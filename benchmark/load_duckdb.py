"""Internal offline test mirror. Northstar itself is PostgreSQL."""

from pathlib import Path

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.generate import CORE_ORDER, generate_core, load_config, materialize, schema_sql, write_evidence


class LocalMirror:
    """Only the parameter spelling differs; the reporting SQL is shared verbatim."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=None):
        return self.connection.execute(sql.replace("%s", "?"), params) if params is not None else self.connection.execute(sql)


def load(cfg, profile, directory, database=":memory:"):
    import duckdb
    directory = Path(directory)
    counts = generate_core(cfg, profile, directory / "core")
    conn = LocalMirror(duckdb.connect(str(database)))
    conn.execute("SET threads=2")
    conn.execute("BEGIN TRANSACTION")
    conn.execute(schema_sql())
    for table in CORE_ORDER:
        path = str((directory / "core" / f"{table}.csv").resolve()).replace("'", "''")
        conn.execute(f"COPY core.{table} FROM '{path}' (HEADER, DELIMITER ',', NULL '')")
    materialize(conn, cfg)
    write_evidence(conn, cfg, directory / "evidence")
    conn.execute("COMMIT")
    return conn, counts


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "demo"), default="smoke")
    parser.add_argument("--output", type=Path, default=Path("benchmark/data/offline"))
    args = parser.parse_args()
    config = load_config(profile=args.profile)
    connection, counts = load(config, args.profile, args.output, args.output / "northstar_dev.duckdb")
    print(counts)
    connection.connection.close()
