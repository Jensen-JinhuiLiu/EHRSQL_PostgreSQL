#!/usr/bin/env python3
"""Prepare PostgreSQL import artifacts for the EHRSQL SQLite databases.

The EHRSQL DDL files are already PostgreSQL-flavored. For loading, this script
keeps table/column types, primary keys, and uniqueness constraints, but removes
foreign key clauses. The benchmark schemas contain a few relationships that are
polymorphic or not directly enforceable in PostgreSQL, and FK enforcement is not
needed for read-only agent evaluation.
"""

from __future__ import annotations

import csv
import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "postgres_import"


@dataclass(frozen=True)
class Dataset:
    name: str
    postgres_db: str
    sqlite_path: Path
    ddl_path: Path


DATASETS = [
    Dataset(
        name="eicu",
        postgres_db="ehrsql_eicu",
        sqlite_path=ROOT / "eicu.sqlite",
        ddl_path=ROOT / "code/dataset/ehrsql/eicu/eicu.sql",
    ),
    Dataset(
        name="mimic_iii",
        postgres_db="ehrsql_mimic_iii",
        sqlite_path=ROOT / "mimic_iii.sqlite",
        ddl_path=ROOT / "code/dataset/ehrsql/mimic_iii/mimic_iii.sql",
    ),
]


def strip_foreign_keys(ddl: str) -> str:
    statements = []
    for raw_statement in ddl.split(";"):
        statement = raw_statement.strip()
        if not statement:
            continue
        if re.match(r"(?is)^drop\s+table\s+if\s+exists\b", statement):
            continue
        if not re.match(r"(?is)^create\s+table\b", statement):
            statements.append(statement + ";")
            continue

        lines = statement.splitlines()
        kept_lines = []
        for line in lines:
            if re.match(r"^\s*foreign\s+key\b", line, flags=re.IGNORECASE):
                continue
            kept_lines.append(line)

        cleaned = "\n".join(kept_lines)
        cleaned = re.sub(r",(\s*\n\s*\))", r"\1", cleaned)
        statements.append(cleaned + ";")
    return "\n\n".join(statements) + "\n"


def quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def pg_ident(identifier: str) -> str:
    """Return an identifier that matches PostgreSQL's unquoted folding.

    The EHRSQL benchmark SQL uses ordinary unquoted identifiers. PostgreSQL
    folds those to lower case, so quoting uppercase SQLite table names during
    COPY would look for a different, case-sensitive table.
    """
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", identifier):
        return identifier
    return quote_ident(identifier)


def sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({quote_ident(table)})").fetchall()
    return [row[1] for row in rows]


def write_csv(conn: sqlite3.Connection, table: str, columns: list[str], path: Path) -> int:
    query = (
        "SELECT "
        + ", ".join(quote_ident(column) for column in columns)
        + " FROM "
        + quote_ident(table)
    )
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        for row in conn.execute(query):
            writer.writerow(["\\N" if value is None else value for value in row])
            count += 1
    return count


def prepare_dataset(dataset: Dataset) -> None:
    dataset_dir = OUT_DIR / dataset.name
    csv_dir = dataset_dir / "csv"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)

    ddl = dataset.ddl_path.read_text(encoding="utf-8")
    (dataset_dir / "schema_no_fk.sql").write_text(strip_foreign_keys(ddl), encoding="utf-8")

    conn = sqlite3.connect(dataset.sqlite_path)
    tables = sqlite_tables(conn)

    load_lines = [
        "\\set ON_ERROR_STOP on",
        "BEGIN;",
        "SET client_min_messages TO WARNING;",
    ]
    expected_rows = []
    for table in tables:
        columns = sqlite_columns(conn, table)
        csv_name = f"{table}.csv"
        count = write_csv(conn, table, columns, csv_dir / csv_name)
        expected_rows.append((table, count))
        column_sql = ", ".join(pg_ident(column) for column in columns)
        load_lines.append(
            f"\\copy {pg_ident(table)} ({column_sql}) "
            f"FROM '/tmp/ehrsql_import/{dataset.name}/csv/{csv_name}' "
            "WITH (FORMAT csv, NULL '\\N')"
        )
    load_lines.append("COMMIT;")
    (dataset_dir / "load_data.sql").write_text("\n".join(load_lines) + "\n", encoding="utf-8")

    with (dataset_dir / "expected_row_counts.tsv").open("w", encoding="utf-8") as handle:
        handle.write("table\texpected_rows\n")
        for table, count in expected_rows:
            handle.write(f"{table}\t{count}\n")

    conn.close()


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    create_db_lines = ["\\set ON_ERROR_STOP on"]
    for dataset in DATASETS:
        create_db_lines.extend(
            [
                f"DROP DATABASE IF EXISTS {dataset.postgres_db};",
                f"CREATE DATABASE {dataset.postgres_db};",
            ]
        )
    (OUT_DIR / "create_databases.sql").write_text(
        "\n".join(create_db_lines) + "\n", encoding="utf-8"
    )

    for dataset in DATASETS:
        prepare_dataset(dataset)


if __name__ == "__main__":
    main()
