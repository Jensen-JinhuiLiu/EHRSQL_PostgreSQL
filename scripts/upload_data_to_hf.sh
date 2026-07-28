#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <hf_dataset_repo_id>"
  echo "Example: $0 JimHue/EHRSQL_PostgreSQL_data"
  exit 1
fi

repo_id="$1"

if ! command -v hf >/dev/null 2>&1; then
  echo "Missing 'hf' CLI. Install it with: pip install -U huggingface_hub"
  exit 1
fi

hf repos create "$repo_id" --repo-type dataset --public --exist-ok

hf upload "$repo_id" DATA_CARD.md README.md --repo-type dataset
hf upload "$repo_id" data_artifacts_manifest.tsv data_artifacts_manifest.tsv --repo-type dataset
hf upload "$repo_id" eicu.sqlite eicu.sqlite --repo-type dataset
hf upload "$repo_id" mimic_iii.sqlite mimic_iii.sqlite --repo-type dataset
hf upload "$repo_id" postgres_import/eicu/csv postgres_import/eicu/csv --repo-type dataset
hf upload "$repo_id" postgres_import/mimic_iii/csv postgres_import/mimic_iii/csv --repo-type dataset
