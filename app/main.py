"""Meeting Notes v1.2 launcher (what the .app runs).

Starts the local server on 127.0.0.1 if it is not running yet, then opens the
UI in a native macOS window (pywebview / WKWebView). Closing the window does
not stop a running job: the server keeps going and stops itself after 30
minutes with no window and no job.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import core  # noqa: E402
import server  # noqa: E402

PORT = server.PORT
BASE = f"http://127.0.0.1:{PORT}"
IDLE_MIN = os.environ.get("MN_IDLE_MIN", "30")


def healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE}/api/health", timeout=1.5) as r:
            return json.load(r).get("app") == "meeting-notes"
    except Exception:
        return False


def start_server() -> None:
    logs = core.SUPPORT_DIR / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "MN_IDLE_MIN": IDLE_MIN}
    with open(logs / "server.log", "ab") as log:
        subprocess.Popen([sys.executable, str(HERE / "server.py")], cwd=str(HERE), env=env,
                         stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(100):
        if healthy():
            return
        time.sleep(0.2)
    raise RuntimeError(f"Server Meeting Notes tidak menyala. Lihat {logs / 'server.log'}")


def main() -> None:
    if not healthy():
        start_server()
    url = f"{BASE}/?t={server.session_token()}"
    try:
        import webview  # pywebview
    except ImportError:
        subprocess.run(["open", url])
        return
    webview.create_window("Meeting Notes", url, width=1180, height=780, min_size=(920, 600),
                          text_select=True)
    webview.start(private_mode=False)


if __name__ == "__main__":
    main()
