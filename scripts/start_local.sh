#!/usr/bin/env bash
# Start the DACA Operations Platform locally (no Docker needed).
# Prerequisites: Python 3.11+, Node 18+, npm
set -e

cd "$(dirname "$0")/.."
ROOT=$(pwd)

echo "=== DACA Operations Platform — Local Setup ==="
echo ""

# Find a Python 3.11+ interpreter
PY=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        VERSION=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
        MAJOR=${VERSION%%.*}
        MINOR=${VERSION#*.}
        if [ "$MAJOR" = "3" ] && [ "$MINOR" -ge 10 ] 2>/dev/null; then
            PY="$candidate"
            echo "Using Python: $candidate ($VERSION)"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    echo ""
    echo "ERROR: Python 3.10 or newer is required but not found."
    echo ""
    echo "On macOS, install with Homebrew:"
    echo "  brew install python@3.11"
    echo ""
    echo "On Ubuntu/Debian:"
    echo "  sudo apt install python3.11 python3.11-venv"
    echo ""
    exit 1
fi

# 1. Install Python dependencies
echo "[1/5] Installing Python dependencies..."
"$PY" -m pip install -r requirements.txt --quiet

# 2. Create database + seed data
echo "[2/5] Creating database and seeding data..."
"$PY" -m scripts.seed_data

# 3. Install frontend dependencies
echo "[3/5] Installing frontend dependencies..."
cd "$ROOT/frontend"
npm install --silent

# 4. Start API server (background)
echo "[4/5] Starting API server on http://localhost:8000 ..."
cd "$ROOT"
"$PY" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

# 5. Start frontend dev server (foreground)
echo "[5/5] Starting frontend on http://localhost:5173 ..."
echo ""
echo "=============================================="
echo "  Open http://localhost:5173 in your browser"
echo "  API docs: http://localhost:8000/api/docs"
echo "  Press Ctrl+C to stop both servers"
echo "=============================================="
echo ""

cd "$ROOT/frontend"

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $API_PID 2>/dev/null
    exit 0
}
trap cleanup INT TERM

npx vite --host 0.0.0.0 --port 5173
