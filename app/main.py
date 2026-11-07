"""Meeting Report launcher (what the .app runs).

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


def health() -> dict | None:
    try:
        with urllib.request.urlopen(f"{BASE}/api/health", timeout=1.5) as r:
            return json.load(r)
    except Exception:
        return None


def healthy() -> bool:
    h = health() or {}
    return h.get("app") == "meeting-report" and h.get("version") == server.APP_VERSION


def stop_old_server() -> None:
    """A server from an older version (e.g. Meeting Notes 1.2) still running after an
    update would serve the old screens: stop it once a job is not running."""
    h = health()
    if not h or healthy():
        return
    subprocess.run(["pkill", "-f", str(HERE / "server.py")], capture_output=True)
    for _ in range(25):
        if not health():
            return
        time.sleep(0.2)


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
    raise RuntimeError(f"Server Meeting Report tidak menyala. Lihat {logs / 'server.log'}")


def on_drop(window, e) -> None:
    """Drag a recording into the window: pass its path, so a 1 GB video is read where
    it is instead of being copied in (Usulan 15)."""
    try:
        files = (e.get("dataTransfer") or {}).get("files") or []
        path = files[0].get("pywebviewFullPath") if files else None
    except Exception:  # noqa: BLE001
        path = None
    if path:
        window.evaluate_js(f"window.MN && window.MN.dropPath({json.dumps(path)})")


def main() -> None:
    if not healthy():
        stop_old_server()
        start_server()
    url = f"{BASE}/?t={server.session_token()}"
    try:
        import webview  # pywebview
    except ImportError:
        subprocess.run(["open", url])
        return
    window = webview.create_window("Meeting Report", url, width=1180, height=780, min_size=(920, 600),
                                   text_select=True)

    def bind(win):
        try:
            from webview.dom import DOMEventHandler
            win.dom.document.events.drop += DOMEventHandler(lambda e: on_drop(win, e), False, False)
        except Exception:  # noqa: BLE001 - older pywebview: dropping falls back to copying
            pass

    webview.start(bind, window, private_mode=False)


if __name__ == "__main__":
    main()
