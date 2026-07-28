# EHRSQL PostgreSQL

PostgreSQL-oriented preprocessing and benchmark files for the EHRSQL benchmark.

The original EHRSQL repository is kept as a Git submodule at `code/`:

```bash
git submodule update --init --recursive
```

## Contents

- `code/`: upstream EHRSQL source repository.
- `convert_sqlite_to_postgres.py`: exports the benchmark SQLite databases into PostgreSQL-loadable CSV and SQL files.
- `generate_ehrsql_postgres_benchmarks.py`: generates PostgreSQL-normalized EHRSQL benchmark JSON files.
- `generate_human_executable_benchmarks.py`: produces the human-executable benchmark subsets.
- `benchmark_generation_README.md`: notes on generated benchmark JSON files and validation status.
- `postgres_import/`: PostgreSQL schemas, load scripts, row counts, and import notes.

The generated database payloads are intentionally excluded from this GitHub repository:

- `eicu.sqlite`
- `mimic_iii.sqlite`
- `postgres_import/eicu/csv/`
- `postgres_import/mimic_iii/csv/`

These data artifacts are hosted in the Hugging Face Dataset repository:

https://huggingface.co/datasets/JimHue/EHRSQL_PostgreSQL_data

Download them into this repository root with the Hugging Face CLI:

```bash
hf download JimHue/EHRSQL_PostgreSQL_data --repo-type dataset --local-dir .
```

Or clone the dataset repository separately:

```bash
git clone https://huggingface.co/datasets/JimHue/EHRSQL_PostgreSQL_data
cp EHRSQL_PostgreSQL_data/eicu.sqlite .
cp EHRSQL_PostgreSQL_data/mimic_iii.sqlite .
cp -R EHRSQL_PostgreSQL_data/postgres_import/eicu/csv postgres_import/eicu/
cp -R EHRSQL_PostgreSQL_data/postgres_import/mimic_iii/csv postgres_import/mimic_iii/
```

## Rebuild

Generate PostgreSQL import files from the SQLite databases:

```bash
python3 convert_sqlite_to_postgres.py
```

Generate PostgreSQL benchmark JSON files:

```bash
python3 generate_ehrsql_postgres_benchmarks.py
python3 generate_human_executable_benchmarks.py
```

## Attribution

This repository builds on EHRSQL: A Practical Text-to-SQL Benchmark for
Electronic Health Records. The upstream repository is included as a submodule:
https://github.com/glee4810/EHRSQL.
