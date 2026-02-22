#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_programmatic.sh — Launch DevUI via in-memory (programmatic) registration
#
# Agents are registered directly in main.py — no directory scan needed.
#
# Usage:
#   ./scripts/run_programmatic.sh
#
# References:
#   https://learn.microsoft.com/en-us/agent-framework/devui/?pivots=programming-language-python
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

if [ ! -d "${VENV_DIR}" ]; then
  echo "❌ .venv not found. Run ./scripts/setup.sh first."
  exit 1
fi

if [ ! -f "${PROJECT_ROOT}/.env" ]; then
  echo "❌ .env not found. Copy .env.example → .env and fill in credentials."
  exit 1
fi

source "${VENV_DIR}/bin/activate"

cd "${PROJECT_ROOT}"

echo "▶ Launching DevUI (programmatic registration)"
echo "  Entry point: main.py"
echo ""

exec python main.py
