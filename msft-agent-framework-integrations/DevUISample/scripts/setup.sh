#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh — Create .venv and install all dependencies
#
# Usage:
#   chmod +x scripts/setup.sh
#   ./scripts/setup.sh           # runtime deps only
#   ./scripts/setup.sh --dev     # include dev/test deps
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

echo "╔══════════════════════════════════════════════════╗"
echo "║  DevUI Python Sample — Environment Setup         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Project root : ${PROJECT_ROOT}"
echo "Virtual env  : ${VENV_DIR}"
echo ""

# ── Pick Python 3.11 (agent-framework requires >=3.10) ───────────────────
PYTHON_BIN="$(command -v python3.11 || command -v python3.10 || command -v python3.12)"
if [ -z "${PYTHON_BIN}" ]; then
  echo "Python 3.10+ not found. Please install it first."
  exit 1
fi
echo "Using Python: ${PYTHON_BIN} ($( ${PYTHON_BIN} --version ))"

# ── Create virtual environment ────────────────────────────────────────────
if [ ! -d "${VENV_DIR}" ]; then
  echo "▶ Creating virtual environment..."
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
else
  echo "✔ Virtual environment already exists."
fi

# ── Activate ──────────────────────────────────────────────────────────────
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

echo "▶ Upgrading pip..."
pip install --quiet --upgrade pip

# ── Install deps ──────────────────────────────────────────────────────────
DEV_FLAG="${1:-}"
if [ "${DEV_FLAG}" = "--dev" ]; then
  echo "▶ Installing runtime + dev dependencies..."
  pip install --pre -r "${PROJECT_ROOT}/requirements-dev.txt"
else
  echo "▶ Installing runtime dependencies..."
  pip install --pre -r "${PROJECT_ROOT}/requirements.txt"
fi

# ── Env file ──────────────────────────────────────────────────────────────
if [ ! -f "${PROJECT_ROOT}/.env" ]; then
  echo ""
  echo "⚠  No .env found. Creating from .env.example ..."
  cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
  echo "   → Edit ${PROJECT_ROOT}/.env and fill in your credentials."
fi

if [ ! -f "${PROJECT_ROOT}/agents/.env" ]; then
  cp "${PROJECT_ROOT}/agents/.env.example" "${PROJECT_ROOT}/agents/.env"
fi

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Fill in credentials:  ${PROJECT_ROOT}/.env"
echo "  2. Launch DevUI (directory discovery):"
echo "       ./scripts/run_devui.sh"
echo "  3. OR launch programmatically:"
echo "       ./scripts/run_programmatic.sh"
