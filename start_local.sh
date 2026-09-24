#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"
mkdir -p logs

if [[ ! -d ".venv" ]]; then
  echo "ERROR: Python virtual environment .venv was not found."
  echo "Create it first with: python3 -m venv .venv"
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo "ERROR: .env was not found in $(pwd)."
  exit 1
fi

source .venv/bin/activate
set -a
source .env
set +a

echo "==============================================="
echo " AniToon_1Bot Local Launcher"
echo "==============================================="
echo "Directory: $(pwd)"
echo

# Pull the newest committed bot code before every local start.
# Never overwrite local changes: stop with a clear message instead.
if git diff --quiet && git diff --cached --quiet; then
  echo "[1/3] Updating local code from GitHub..."
  if ! git pull --ff-only; then
    echo "WARNING: Git update failed. Starting the current local version."
  fi
else
  echo "WARNING: Local uncommitted changes detected."
  echo "Skipping git pull so your local changes are not overwritten."
fi

echo
echo "[2/3] Starting AniToon supervisor..."
PYTHONUNBUFFERED=1 python run.py >>logs/bot-supervisor.log 2>&1 &
BOT_PID=$!

cleanup() {
  echo
  echo "Stopping local AniToon services..."
  kill "$BOT_PID" 2>/dev/null || true
  if [[ -n "${TUNNEL_PID:-}" ]]; then
    kill "$TUNNEL_PID" 2>/dev/null || true
  fi
  wait "$BOT_PID" 2>/dev/null || true
  if [[ -n "${TUNNEL_PID:-}" ]]; then
    wait "$TUNNEL_PID" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

# Give the Flask health server a moment to start before Cloudflare connects.
sleep 3

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "ERROR: cloudflared is not installed."
  echo "Install it first with the Cloudflare package instructions."
  exit 1
fi

echo "[3/3] Starting Cloudflare Quick Tunnel..."
(
  while true; do
    echo
    echo "---------- Cloudflare Tunnel starting ----------"
    cloudflared tunnel --url http://localhost:10000 2>&1 | tee -a logs/cloudflared.log
    status=$?
    echo "Cloudflare Tunnel exited with status $status. Retrying in 3 seconds..."
    sleep 3
  done
) &
TUNNEL_PID=$!

echo
echo "==============================================="
echo " AniToon local services are running."
echo " Bot logs:    logs/bot-supervisor.log"
echo " Tunnel logs: logs/cloudflared.log"
echo
echo "The Cloudflare URL is printed above whenever the"
echo "Quick Tunnel starts. Keep this window open."
echo "==============================================="

# Keep this launcher window alive while the services run.
wait "$BOT_PID"
