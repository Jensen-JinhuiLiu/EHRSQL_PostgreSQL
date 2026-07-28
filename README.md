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

Those files should be published in a Hugging Face Dataset repository. See
`DATA_CARD.md` and `data_artifacts_manifest.tsv` for the suggested dataset card
and file inventory.

After installing the Hugging Face CLI and logging in, upload the data artifacts
with:

```bash
scripts/upload_data_to_hf.sh Jensen-JinhuiLiu/EHRSQL_PostgreSQL_data
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
