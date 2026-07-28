#!/usr/bin/env python3
"""Generate PostgreSQL-ready EHRSQL test benchmarks.

The source EHRSQL test files contain both answerable and impossible examples,
and their gold SQL is SQLite-flavored. This script keeps only answerable test
examples and emits LiveSQLBench/BIRD-compatible JSON rows with PostgreSQL gold
SQL for the converted Docker databases.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CURRENT_TIME = "2105-12-31 23:59:00"

VITAL_RANGES = {
    "temperature": (35.5, 38.1),
    "sao2": (95.0, 100.0),
    "heart rate": (60.0, 100.0),
    "respiration": (12.0, 18.0),
    "systolic bp": (90.0, 120.0),
    "diastolic bp": (60.0, 90.0),
    "mean bp": (60.0, 110.0),
}


@dataclass(frozen=True)
class Dataset:
    source_name: str
    postgres_database: str
    source_path: Path
    output_path: Path


DATASETS = [
    Dataset(
        source_name="eicu",
        postgres_database="ehrsql_eicu",
        source_path=ROOT / "code/dataset/ehrsql/eicu/test.json",
        output_path=ROOT / "ehrsql_eicu_test_postgresql.json",
    ),
    Dataset(
        source_name="mimic_iii",
        postgres_database="ehrsql_mimic_iii",
        source_path=ROOT / "code/dataset/ehrsql/mimic_iii/test.json",
        output_path=ROOT / "ehrsql_mimic_iii_test_postgresql.json",
    ),
]


def official_ehrsql_post_process(sql: str) -> str:
    """Mirror EHRSQL/code/evaluate.py post_process_sql before PG translation."""
    query = sql.lower()
    query = query.replace("current_time", f"'{CURRENT_TIME}'")

    lower_match = re.search(r"[ \n]+([a-zA-Z0-9_]+_lower)", query)
    upper_match = re.search(r"[ \n]+([a-zA-Z0-9_]+_upper)", query)
    if lower_match and upper_match:
        lower_expr = lower_match.group(1)
        upper_expr = upper_match.group(1)
        names = set(
            re.findall(r"([a-zA-Z0-9_]+)_lower", lower_expr)
            + re.findall(r"([a-zA-Z0-9_]+)_upper", upper_expr)
        )
        if len(names) == 1:
            vital_name = next(iter(names)).replace("_", " ")
            if vital_name in VITAL_RANGES:
                lower, upper = VITAL_RANGES[vital_name]
                query = query.replace(lower_expr, str(lower)).replace(upper_expr, str(upper))

    query = query.replace("''", "'").replace("< =", "<=")
    query = query.replace("%y", "%Y").replace("%j", "%J")
    query = query.replace("'now'", f"'{CURRENT_TIME}'")
    return query


def split_sql_args(inner: str) -> list[str]:
    args: list[str] = []
    start = 0
    in_string = False
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "'":
            if in_string and i + 1 < len(inner) and inner[i + 1] == "'":
                i += 2
                continue
            in_string = not in_string
        elif ch == "," and not in_string:
            args.append(inner[start:i].strip())
            start = i + 1
        i += 1
    args.append(inner[start:].strip())
    return args


def translate_datetime(inner: str) -> str:
    args = split_sql_args(inner)
    if not args:
        raise ValueError(f"Invalid datetime() expression: {inner}")

    expr = f"({args[0]})::timestamp"
    for raw_modifier in args[1:]:
        modifier = raw_modifier.strip().strip("'").lower()
        if modifier == "start of year":
            expr = f"date_trunc('year', {expr})"
        elif modifier == "start of month":
            expr = f"date_trunc('month', {expr})"
        elif modifier == "start of day":
            expr = f"date_trunc('day', {expr})"
        else:
            match = re.fullmatch(r"([+-]\d+)\s+(year|month|day)s?", modifier)
            if not match:
                raise ValueError(f"Unsupported SQLite datetime modifier: {raw_modifier}")
            amount, unit = match.groups()
            expr = f"({expr} + interval '{amount} {unit}')"
    return expr


def translate_strftime(fmt: str, expr: str) -> str:
    ts_expr = f"({expr})::timestamp"
    fmt_map = {
        "%Y": "YYYY",
        "%m": "MM",
        "%d": "DD",
        "%Y-%m": "YYYY-MM",
        "%Y-%m-%d": "YYYY-MM-DD",
        "%m-%d": "MM-DD",
    }
    if fmt == "%J":
        return f"(extract(epoch from {ts_expr}) / 86400.0 + 2440587.5)"
    if fmt in fmt_map:
        return f"to_char({ts_expr}, '{fmt_map[fmt]}')"
    raise ValueError(f"Unsupported SQLite strftime format: {fmt}")


def find_matching_paren(sql: str, open_index: int) -> int | None:
    depth = 0
    in_string = False
    i = open_index
    while i < len(sql):
        ch = sql[i]
        if ch == "'":
            if in_string and i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2
                continue
            in_string = not in_string
        elif not in_string:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return None


def fix_sqlite_cross_joins(sql: str) -> str:
    """Translate SQLite JOIN-without-ON derived-table joins to CROSS JOIN."""
    result: list[str] = []
    lower_sql = sql.lower()
    cursor = 0
    pattern = re.compile(r"\bjoin\s+\(", re.IGNORECASE)
    for match in pattern.finditer(sql):
        join_start = match.start()
        open_index = match.end() - 1
        close_index = find_matching_paren(sql, open_index)
        if close_index is None:
            continue
        after = lower_sql[close_index + 1 :]
        alias_match = re.match(r"\s+as\s+[a-z_][a-z0-9_]*\s+", after)
        if not alias_match:
            continue
        next_token_start = close_index + 1 + alias_match.end()
        next_token_match = re.match(r"([a-z_]+)", lower_sql[next_token_start:])
        next_token = next_token_match.group(1) if next_token_match else ""
        if next_token in {"where", "group", "order", "limit", "offset", "union", "except"} or not next_token:
            result.append(sql[cursor:join_start])
            result.append("cross join (")
            cursor = open_index + 1
    result.append(sql[cursor:])
    return "".join(result)


def fix_eicu_age_comparisons(sql: str) -> str:
    age_expr = "(nullif(regexp_replace(patient.age, '[^0-9]', '', 'g'), '')::int)"
    sql = re.sub(
        r"\bpatient\.age\s+between\b",
        f"{age_expr} between",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"\bpatient\.age\s*(>=|<=|>|<)\s*(\d+)",
        rf"{age_expr} \1 \2",
        sql,
        flags=re.IGNORECASE,
    )
    return sql


def fix_text_numeric_aggregates(sql: str) -> str:
    dose_number = (
        "(substring(prescriptions.dose_val_rx from "
        "'[-+]?[0-9]*\\.?[0-9]+'))::numeric"
    )
    return re.sub(
        r"\bsum\s*\(\s*prescriptions\.dose_val_rx\s*\)",
        f"sum({dose_number})",
        sql,
        flags=re.IGNORECASE,
    )


def fix_top_level_count_order_by(sql: str) -> str:
    if not re.match(r"^\s*select\s+count\s*\(\s*\*\s*\)\s*>\s*0\b", sql, re.IGNORECASE):
        return sql
    lower_sql = sql.lower()
    in_string = False
    depth = 0
    last_top_level_order = None
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'":
            if in_string and i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2
                continue
            in_string = not in_string
        elif not in_string:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0 and lower_sql.startswith(" order by ", i):
                last_top_level_order = i
        i += 1
    if last_top_level_order is None:
        return sql
    suffix = sql[last_top_level_order:]
    if re.match(r"\s+order\s+by\s+.+?\s+(?:asc|desc)\s+limit\s+\d+\s*$", suffix, re.IGNORECASE):
        return sql[:last_top_level_order]
    return sql


def fix_bare_min_having(sql: str) -> str:
    """Emulate SQLite bare-column min() rows with PostgreSQL DISTINCT ON."""

    pattern = re.compile(
        r"select\s+(?P<select>[^()]*?)\s+from\s+(?P<body>.*?)\s+"
        r"group\s+by\s+(?P<groups>[^()]*?)\s+having\s+"
        r"min\s*\(\s*(?P<time>[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)\s*\)\s*=\s*(?P=time)"
        r"(?P<rest>\s+and\s+.*?)?"
        r"(?=\s*\)\s+as|\s*$)",
        flags=re.IGNORECASE,
    )

    previous = None
    while previous != sql:
        previous = sql

        def replace(match: re.Match[str]) -> str:
            select_list = match.group("select").strip()
            body = match.group("body").strip()
            groups = match.group("groups").strip()
            time_col = match.group("time").strip()
            rest = (match.group("rest") or "").strip()
            inner = (
                f"select distinct on ({groups}) {select_list} from {body} "
                f"order by {groups}, {time_col} asc"
            )
            if rest:
                return f"select * from ( {inner} ) as _ehrsql_min where {rest[4:].strip()}"
            return inner

        sql = pattern.sub(replace, sql)
    return sql


def sqlite_to_postgres_sql(sql: str) -> str:
    query = official_ehrsql_post_process(sql)

    query = re.sub(
        r"datetime\s*\(([^()]*)\)",
        lambda match: translate_datetime(match.group(1)),
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(
        r"strftime\s*\(\s*'([^']+)'\s*,\s*([^()]*)\)",
        lambda match: translate_strftime(match.group(1), match.group(2).strip()),
        query,
        flags=re.IGNORECASE,
    )
    query = fix_sqlite_cross_joins(query)
    query = fix_eicu_age_comparisons(query)
    query = fix_text_numeric_aggregates(query)
    query = fix_top_level_count_order_by(query)
    return query


def difficulty_from_source(row: dict[str, Any]) -> str:
    importance = str(row.get("importance") or "").lower()
    return {
        "low": "simple",
        "medium": "moderate",
        "high": "challenging",
    }.get(importance, "unknown")


def make_benchmark_row(
    dataset: Dataset,
    source_row: dict[str, Any],
    question_id: int,
) -> dict[str, Any]:
    question = str(source_row["question"])
    pg_sql = sqlite_to_postgres_sql(str(source_row["query"]))
    return {
        "instance_id": f"{dataset.source_name}_{source_row['id']}",
        "question_id": question_id,
        "db_id": dataset.postgres_database,
        "selected_database": dataset.postgres_database,
        "question": question,
        "query": question,
        "SQL": pg_sql,
        "gt_sql": pg_sql,
        "gold_sql": pg_sql,
        "difficulty": difficulty_from_source(source_row),
        "difficulty_tier": difficulty_from_source(source_row).title(),
        "category": "Query",
        "external_knowledge": [],
        "test_cases": [],
        "conditions": {
            "decimal": [],
            "distinct": "distinct" in pg_sql.lower(),
            "order": " order by " in pg_sql.lower(),
        },
        "source_benchmark": "EHRSQL",
        "source_split": "test",
        "source_db_id": source_row.get("db_id"),
        "source_id": source_row.get("id"),
        "template": source_row.get("template"),
        "tag": source_row.get("tag"),
        "q_tag": source_row.get("q_tag"),
        "value": source_row.get("value"),
        "department": source_row.get("department"),
        "importance": source_row.get("importance"),
        "para_type": source_row.get("para_type"),
        "is_impossible": False,
        "ehrsql_sqlite_query": source_row.get("query"),
        "ehrsql_current_time": CURRENT_TIME,
    }


def generate_dataset(dataset: Dataset) -> list[dict[str, Any]]:
    with dataset.source_path.open(encoding="utf-8") as handle:
        source_rows = json.load(handle)

    answerable = [
        row
        for row in source_rows
        if row.get("split") == "test"
        and not bool(row.get("is_impossible"))
        and str(row.get("query") or "").strip()
        and str(row.get("query") or "").strip().lower() != "nan"
    ]

    rows = [
        make_benchmark_row(dataset, source_row, question_id)
        for question_id, source_row in enumerate(answerable, 1)
    ]
    with dataset.output_path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return rows


def main() -> None:
    for dataset in DATASETS:
        rows = generate_dataset(dataset)
        print(
            f"{dataset.output_path}: wrote {len(rows)} answerable "
            f"{dataset.source_name} test samples"
        )


if __name__ == "__main__":
    main()
