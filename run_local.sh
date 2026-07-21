#!/usr/bin/env bash
# DACA Ops — one-command local launcher.
#
#   ./run_local.sh
#
# Starts the web app at http://127.0.0.1:8000 against a local SQLite register.
# On first run it installs deps into a local virtualenv (.venv). The register
# database (daca_register.db) is NOT in git — it holds real client data and must
# be placed next to this script (the agent sends it to you separately). If it's
# missing, the app still starts with an empty register you can add cases to.

set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
export DACA_REGISTER_DB="${DACA_REGISTER_DB:-$(pwd)/daca_register.db}"
export DACA_OPERATOR="${DACA_OPERATOR:-human:$(git config user.email 2>/dev/null || echo operator@rho.co)}"

if [ ! -d .venv ]; then
  echo "→ creating virtualenv (.venv) and installing dependencies (first run only)…"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

if [ ! -f "$DACA_REGISTER_DB" ]; then
  echo "⚠  No register DB at $DACA_REGISTER_DB — starting with an empty register."
  echo "   (Drop the daca_register.db the agent sent you next to this script to see your real cases.)"
fi

echo "→ DACA Ops running at http://127.0.0.1:${PORT}   (Ctrl+C to stop)"
exec ./.venv/bin/python -m uvicorn src.webapp.app:app --host 127.0.0.1 --port "${PORT}"
