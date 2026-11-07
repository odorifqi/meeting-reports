#!/bin/bash
# Meeting Report v1.3, jalankan dari repo (untuk pengembangan).
#   ./run.sh dev     server dengan auto-reload, dibuka di Chrome (seperti "npm run dev")
#   ./run.sh app     jendela Mac (pywebview) memakai kode di repo ini
#   ./run.sh test    jalankan tes
# Data di ~/Documents/Meeting Report. Untuk data uji terpisah:
#   MN_OUTPUT_DIR=~/Desktop/mn-uji ./run.sh dev
set -euo pipefail
cd "$(dirname "$0")"
VENV=.venv
PORT="${MN_PORT:-8765}"

ensure_venv() {
  if [[ ! -x "$VENV/bin/python" ]]; then
    if command -v uv >/dev/null 2>&1; then uv venv --python 3.12 "$VENV"; else python3 -m venv "$VENV"; fi
  fi
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$VENV/bin/python" -q -r app/requirements.txt pytest httpx
  else
    "$VENV/bin/pip" install -q -r app/requirements.txt pytest httpx
  fi
}

if_running_stop() {
  if curl -fs "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    echo "Server Meeting Report (versi terpasang) sedang jalan di port $PORT. Menghentikannya dulu..."
    pkill -f "MeetingNotes/app/server.py" || true
    sleep 1
  fi
}

case "${1:-dev}" in
  dev)
    ensure_venv
    if_running_stop
    TOKEN=$("$VENV/bin/python" -c "import sys; sys.path.insert(0,'app'); import server; print(server.session_token())")
    URL="http://127.0.0.1:$PORT/?t=$TOKEN"
    echo ""
    echo "Meeting Report (dev) -> $URL"
    echo "Tekan Ctrl+C untuk berhenti."
    (sleep 2; open -a "Google Chrome" "$URL" 2>/dev/null || open "$URL") &
    exec "$VENV/bin/uvicorn" server:app --app-dir app --reload --reload-dir app \
      --host 127.0.0.1 --port "$PORT" --log-level warning --no-access-log
    ;;
  app)
    ensure_venv
    exec "$VENV/bin/python" app/main.py
    ;;
  test)
    ensure_venv
    exec "$VENV/bin/python" -m pytest -q tests
    ;;
  *)
    echo "Pakai: ./run.sh [dev|app|test]"; exit 1 ;;
esac
