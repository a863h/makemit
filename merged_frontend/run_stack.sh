#!/usr/bin/env bash
set -euo pipefail

# Runs the merged stack with explicit module paths so imports work
# even when launched from merged_frontend/.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
PLAYER_HOST="${PLAYER_HOST:-127.0.0.1}"
PLAYER_PORT="${PLAYER_PORT:-8502}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

cleanup() {
  jobs -p | xargs -r kill >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

cd "$ROOT_DIR"

echo "[1/3] Starting cadence API on ${API_HOST}:${API_PORT} ..."
python -m uvicorn api_endpoint.algo:app --reload --host "$API_HOST" --port "$API_PORT" &

echo "[2/3] Starting player server on ${PLAYER_HOST}:${PLAYER_PORT} ..."
python -m uvicorn merged_frontend.player_server:app --reload --host "$PLAYER_HOST" --port "$PLAYER_PORT" &

echo "[3/3] Starting Streamlit on 127.0.0.1:${STREAMLIT_PORT} ..."
python -m streamlit run merged_frontend/streamlit_merged_app.py --server.port "$STREAMLIT_PORT" &

echo "Stack started. Open:"
echo "- Player:    http://${PLAYER_HOST}:${PLAYER_PORT}/player"
echo "- Frontend:  http://127.0.0.1:${STREAMLIT_PORT}"
echo
echo "Press Ctrl+C to stop all three processes."

wait
