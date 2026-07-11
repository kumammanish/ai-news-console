#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

VENV_DIR=".venv"
HOST="127.0.0.1"
PORT="8000"
URL="http://localhost:${PORT}"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment…"
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Installing dependencies…"
pip3 install --quiet --upgrade pip
pip3 install --quiet -r requirements.txt

mkdir -p data

if lsof -i "TCP:${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Server already running on port ${PORT}."
  if [ "${NO_AUTO_OPEN:-}" != "1" ]; then
    open "$URL"
  fi
  exit 0
fi

echo "Starting AI News Console on ${URL} …"
if [ "${NO_AUTO_OPEN:-}" != "1" ]; then
  (
    for i in $(seq 1 30); do
      sleep 0.5
      if curl -sf "$URL" >/dev/null 2>&1; then
        open "$URL"
        break
      fi
    done
  ) &
fi

exec uvicorn app.main:app --host "$HOST" --port "$PORT"
