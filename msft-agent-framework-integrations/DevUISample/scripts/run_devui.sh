#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_devui.sh — Launch DevUI using directory-based agent discovery
#
# DevUI scans ./agents/ and auto-discovers all agents/workflows.
#
# Usage:
#   ./scripts/run_devui.sh              # default port 8080
#   PORT=9000 ./scripts/run_devui.sh    # custom port
#
# References:
#   https://learn.microsoft.com/en-us/agent-framework/devui/directory-discovery
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

# ── Guard: venv must exist ─────────────────────────────────────────────────
if [ ! -d "${VENV_DIR}" ]; then
  echo "❌ .venv not found. Run ./scripts/setup.sh first."
  exit 1
fi

# ── Guard: .env must exist ─────────────────────────────────────────────────
if [ ! -f "${PROJECT_ROOT}/.env" ]; then
  echo "❌ .env not found. Copy .env.example → .env and fill in credentials."
  exit 1
fi

source "${VENV_DIR}/bin/activate"

PORT="${PORT:-8080}"
HOST="${HOST:-127.0.0.1}"
MODE="${MODE:-developer}"   # developer | user

echo "▶ Launching DevUI (directory discovery)"
echo "  Agents dir : ${PROJECT_ROOT}/agents"
echo "  URL        : http://${HOST}:${PORT}"
echo "  Mode       : ${MODE}"
echo ""

# Change to project root so relative paths work
cd "${PROJECT_ROOT}"

exec devui ./agents \
  --port "${PORT}" \
  --host "${HOST}" \
  --mode "${MODE}" \
  --tracing \
  --reload
