#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
validation_dir="$(mktemp -d)"
trap 'rm -rf -- "$validation_dir"' EXIT
export UV_PROJECT_ENVIRONMENT="$validation_dir/venv"
unset PYTHONPATH PYTHONHOME

uv sync --locked --no-editable --group dev
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest
uv run --no-sync xian-legacy-genesis --help >/dev/null
uv build
