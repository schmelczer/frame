#!/usr/bin/env bash
# Format and lint Python sources with Ruff.
# Pass --check to fail (instead of fix) — used by CI.
set -euo pipefail

cd "$(dirname "$0")"

if [[ "${1:-}" == "--check" ]]; then
    uv run --group dev ruff format --check .
    uv run --group dev ruff check .
else
    uv run --group dev ruff format .
    uv run --group dev ruff check --fix .
fi
