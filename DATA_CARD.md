---
license: cc-by-4.0
task_categories:
- text2sql
- question-answering
language:
- en
tags:
- ehrsql
- electronic-health-records
- sql
- postgresql
- sqlite
pretty_name: EHRSQL PostgreSQL Artifacts
---

# EHRSQL PostgreSQL Artifacts

This dataset repository is intended to host database artifacts generated for
the companion GitHub repository:

https://github.com/Jensen-JinhuiLiu/EHRSQL_PostgreSQL

## Files

- `eicu.sqlite`: original benchmark SQLite database artifact used for eICU.
- `mimic_iii.sqlite`: original benchmark SQLite database artifact used for MIMIC-III.
- `postgres_import/eicu/csv/`: CSV exports for loading the eICU PostgreSQL database.
- `postgres_import/mimic_iii/csv/`: CSV exports for loading the MIMIC-III PostgreSQL database.

The companion GitHub repository contains the preprocessing scripts,
PostgreSQL schema/load files, generated benchmark JSON files, and a checksum
manifest for these artifacts.

## Loading PostgreSQL

After downloading the artifacts into the GitHub repository root, follow:

- `postgres_import/README.md`
- `postgres_import/create_databases.sql`
- `postgres_import/eicu/schema_no_fk.sql`
- `postgres_import/eicu/load_data.sql`
- `postgres_import/mimic_iii/schema_no_fk.sql`
- `postgres_import/mimic_iii/load_data.sql`

## Attribution

These artifacts are derived from the EHRSQL benchmark:

EHRSQL: A Practical Text-to-SQL Benchmark for Electronic Health Records
https://github.com/glee4810/EHRSQL
