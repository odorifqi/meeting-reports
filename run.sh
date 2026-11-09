#!/bin/bash
# Meeting Report v1.6, jalankan dari repo (untuk pengembangan).
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
  if curl -fs -m 2 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    echo "Server Meeting Report (versi terpasang) sedang jalan di port $PORT. Menghentikannya dulu..."
    pkill -f "MeetingNotes/app/server.py" || true
    sleep 1
  fi
}

port_free_or_exit() {
  local pid pgid
  pid=$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)
  if [[ -n "$pid" ]]; then
    pgid=$(ps -o pgid= -p "$pid" | tr -d ' ' || true)
    echo "Port $PORT masih dipakai proses lain:"
    ps -o pid=,stat=,command= -p "$pid" || true
    echo "STAT T = proses dijeda (misalnya karena Ctrl+Z). Hentikan seluruh grup prosesnya dengan:"
    echo "  kill -CONT -- -${pgid:-$pid}; kill -- -${pgid:-$pid}"
    exit 1
  fi
}

open_when_ready() {
  for _ in $(seq 1 120); do
    if curl -fs -m 2 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
      echo "Server siap. Membuka browser..."
      open -a "Google Chrome" "$1" 2>/dev/null || open "$1"
      return
    fi
    sleep 0.5
  done
  echo "Server belum menjawab setelah 60 detik. Buka tautan di atas secara manual."
}

case "${1:-dev}" in
  dev)
    ensure_venv
    if_running_stop
    port_free_or_exit
    TOKEN=$("$VENV/bin/python" -c "import sys; sys.path.insert(0,'app'); import server; print(server.session_token())")
    URL="http://127.0.0.1:$PORT/?t=$TOKEN"
    echo ""
    echo "Meeting Report (dev) -> $URL"
    echo "Terminal ini tetap diam selama server jalan. Tekan Ctrl+C untuk berhenti (jangan Ctrl+Z: itu hanya menjeda dan port tetap terpakai)."
    open_when_ready "$URL" &
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
