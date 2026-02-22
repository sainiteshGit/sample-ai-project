#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_tests.sh — Run unit tests inside the .venv
#
# Usage:
#   ./scripts/run_tests.sh            # run all tests
#   ./scripts/run_tests.sh -v         # verbose
#   ./scripts/run_tests.sh -k weather # filter by name
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

if [ ! -d "${VENV_DIR}" ]; then
  echo "❌ .venv not found. Run ./scripts/setup.sh --dev first."
  exit 1
fi

source "${VENV_DIR}/bin/activate"
cd "${PROJECT_ROOT}"

echo "▶ Running tests..."
exec pytest tests/ "$@"
