#!/usr/bin/env python3
"""Generate human-only EHRSQL benchmark files whose gold SQL runs on PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import psycopg2


DEFAULT_INPUTS = {
    "ehrsql_eicu": Path("EHRSQL/ehrsql_eicu_test_postgresql.json"),
    "ehrsql_mimic_iii": Path("EHRSQL/ehrsql_mimic_iii_test_postgresql.json"),
}

DEFAULT_OUTPUTS = {
    "ehrsql_eicu": Path("EHRSQL/ehrsql_eicu_test_human_executable_postgresql.json"),
    "ehrsql_mimic_iii": Path("EHRSQL/ehrsql_mimic_iii_test_human_executable_postgresql.json"),
}

DEFAULT_NON_EXECUTABLE_OUTPUT = Path(
    "EHRSQL/ehrsql_test_human_non_executable_postgresql.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Filter EHRSQL PostgreSQL benchmark files to human paraphrases whose "
            "gold SQL is executable on the converted PostgreSQL databases."
        )
    )
    parser.add_argument("--pg-host", default=os.environ.get("PGHOST", "localhost"))
    parser.add_argument("--pg-port", type=int, default=int(os.environ.get("PGPORT", "5432")))
    parser.add_argument("--pg-user", default=os.environ.get("PGUSER", "root"))
    parser.add_argument("--pg-password", default=os.environ.get("PGPASSWORD", "123123"))
    parser.add_argument("--schema", default=os.environ.get("PGSCHEMA", "public"))
    parser.add_argument("--statement-timeout-ms", type=int, default=30000)
    parser.add_argument(
        "--para-type",
        default="human",
        help="Only rows with this para_type are considered. Use an empty value to consider all rows.",
    )
    parser.add_argument(
        "--non-executable-output",
        type=Path,
        default=DEFAULT_NON_EXECUTABLE_OUTPUT,
    )
    parser.add_argument(
        "--eicu-output",
        type=Path,
        default=DEFAULT_OUTPUTS["ehrsql_eicu"],
    )
    parser.add_argument(
        "--mimic-iii-output",
        type=Path,
        default=DEFAULT_OUTPUTS["ehrsql_mimic_iii"],
    )
    parser.add_argument(
        "--skip-executable-output",
        action="store_true",
        help="Only write the non-executable audit file.",
    )
    return parser.parse_args()


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise TypeError(f"{path} must contain a JSON list")
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def gold_sql(row: dict[str, Any]) -> str:
    sql = row.get("SQL") or row.get("gold_sql") or row.get("gt_sql")
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError(f"Missing SQL for row {row.get('instance_id') or row.get('question_id')}")
    return sql


def connect(args: argparse.Namespace, db_id: str):
    options = (
        f"-c search_path={args.schema},public "
        f"-c statement_timeout={args.statement_timeout_ms}"
    )
    conn = psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        dbname=db_id,
        user=args.pg_user,
        password=args.pg_password,
        options=options,
    )
    conn.autocommit = True
    return conn


def execute_gold(conn, row: dict[str, Any]) -> tuple[bool, dict[str, str] | None]:
    try:
        with conn.cursor() as cur:
            cur.execute(gold_sql(row))
            if cur.description is not None:
                cur.fetchall()
        return True, None
    except Exception as exc:  # noqa: BLE001 - preserve database exception details.
        conn.rollback()
        return False, {
            "error_type": type(exc).__name__,
            "sqlstate": getattr(exc, "pgcode", None) or "",
            "error_message": str(exc).strip(),
        }


def should_consider(row: dict[str, Any], para_type: str) -> bool:
    if not para_type:
        return True
    return row.get("para_type") == para_type


def main() -> None:
    args = parse_args()
    para_type = args.para_type.strip()
    all_non_executable: list[dict[str, Any]] = []
    executable_outputs = {
        "ehrsql_eicu": args.eicu_output,
        "ehrsql_mimic_iii": args.mimic_iii_output,
    }

    for db_id, input_path in DEFAULT_INPUTS.items():
        rows = load_json(input_path)
        candidates = [row for row in rows if should_consider(row, para_type)]
        executable: list[dict[str, Any]] = []
        non_executable: list[dict[str, Any]] = []

        print(f"{db_id}: checking {len(candidates)} candidate rows from {input_path}")
        conn = connect(args, db_id)
        try:
            for idx, row in enumerate(candidates, 1):
                ok, error = execute_gold(conn, row)
                if ok:
                    executable.append(row)
                else:
                    assert error is not None
                    failed = {
                        "db_id": db_id,
                        "instance_id": row.get("instance_id"),
                        "question_id": row.get("question_id"),
                        "para_type": row.get("para_type"),
                        "difficulty": row.get("difficulty"),
                        "importance": row.get("importance"),
                        "department": row.get("department"),
                        "error_type": error["error_type"],
                        "sqlstate": error["sqlstate"],
                        "error_message": error["error_message"],
                        "sample": row,
                    }
                    non_executable.append(failed)
                    all_non_executable.append(failed)
                if idx % 100 == 0:
                    print(f"  {idx}/{len(candidates)} checked")
        finally:
            conn.close()

        output_path = executable_outputs[db_id]
        if not args.skip_executable_output:
            write_json(output_path, executable)

        error_counts = Counter(item["sqlstate"] or item["error_type"] for item in non_executable)
        if args.skip_executable_output:
            print(f"{db_id}: {len(executable)} executable; {len(non_executable)} non-executable")
        else:
            print(
                f"{db_id}: wrote {len(executable)} executable rows to {output_path}; "
                f"{len(non_executable)} non-executable"
            )
        if error_counts:
            print(f"{db_id}: non-executable errors: {dict(error_counts)}")

    write_json(args.non_executable_output, all_non_executable)
    print(
        f"wrote {len(all_non_executable)} total non-executable rows to "
        f"{args.non_executable_output}"
    )


if __name__ == "__main__":
    main()
