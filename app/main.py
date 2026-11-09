"""Meeting Report launcher (what the .app runs).

Starts the local server on 127.0.0.1 if it is not running yet, then opens the
UI in a native macOS window (pywebview / WKWebView). Closing the window does
not stop a running job: the server keeps going and stops itself after 30
minutes with no window and no job.
"""
from __future__ import annotations

import errno
import json
import os
import signal
import socket
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
SPARE_PORTS = range(PORT + 1, PORT + 21)
IDLE_MIN = os.environ.get("MN_IDLE_MIN", "30")


def base() -> str:
    return f"http://127.0.0.1:{PORT}"


def port_file() -> Path:
    return core.SUPPORT_DIR / "port"


def use_port(port: int) -> None:
    global PORT
    PORT = port


def saved_port() -> int | None:
    try:
        p = int(port_file().read_text().strip())
    except (OSError, ValueError):
        return None
    return p if p == server.PORT or p in SPARE_PORTS else None


def health() -> dict | None:
    try:
        with urllib.request.urlopen(f"{base()}/api/health", timeout=1.5) as r:
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


def show_error(message: str) -> None:
    """The window never opened, so tell the user in a macOS dialog instead of quitting silently."""
    print(message, file=sys.stderr)
    script = ['on run argv', 'display dialog (item 1 of argv) with title "Meeting Report" '
              'buttons {"OK"} default button 1 with icon stop', 'end run']
    args = ["osascript"] + [a for line in script for a in ("-e", line)] + [message]
    try:
        subprocess.run(args, capture_output=True, timeout=600)
    except (OSError, subprocess.SubprocessError):
        pass


def port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", PORT))
        except OSError as e:
            return e.errno == errno.EADDRINUSE
    return False


def port_owner() -> tuple[str, str, str]:
    """(pid, process group id, description) of the process listening on PORT; empty strings if unknown."""
    try:
        pids = subprocess.run(["lsof", "-nP", f"-iTCP:{PORT}", "-sTCP:LISTEN", "-t"],
                              capture_output=True, text=True, timeout=5).stdout.split()
        if not pids:
            return "", "", ""
        out = subprocess.run(["ps", "-o", "pgid=,stat=,command=", "-p", pids[0]],
                             capture_output=True, text=True, timeout=5).stdout.split(None, 2)
    except (OSError, subprocess.SubprocessError):
        return "", "", ""
    if len(out) < 3:
        return pids[0], "", f"PID {pids[0]}"
    pgid, stat, cmd = out
    paused = " (dijeda, mis. karena Ctrl+Z)" if stat.startswith("T") else ""
    return pids[0], pgid, f"PID {pids[0]}{paused}: {cmd.strip()}"


def port_busy_message() -> str:
    pid, pgid, desc = port_owner()
    # NOTE: `uvicorn --reload` runs a reloader and a worker in one process group, and Ctrl+Z pauses both:
    # resume and stop the whole group, or the reloader waits for its paused worker.
    target = f"-- -{pgid}" if pgid else (pid or "<PID>")
    return (f"Port {PORT} sudah dipakai proses lain, jadi Meeting Report tidak bisa menyala.\n\n"
            f"{desc[:160] or 'Cek dengan: lsof -nP -iTCP:' + str(PORT) + ' -sTCP:LISTEN'}\n\n"
            f"Biasanya ini server dev (./run.sh dev) yang masih jalan. Hentikan dengan Ctrl+C di Terminal-nya, "
            f"atau jalankan:\n  kill -CONT {target}; kill {target}\nLalu buka Meeting Report lagi.")


def log_tail(path: Path, lines: int = 6) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return ""


def start_server() -> None:
    logs = core.SUPPORT_DIR / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "MN_IDLE_MIN": IDLE_MIN, "MN_PORT": str(PORT)}
    with open(logs / "server.log", "ab") as log:
        proc = subprocess.Popen([sys.executable, str(HERE / "server.py")], cwd=str(HERE), env=env,
                                stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(100):
        if healthy():
            return
        if proc.poll() is not None:
            break
        time.sleep(0.2)
    if port_in_use() and not healthy():
        raise RuntimeError(port_busy_message())
    raise RuntimeError(f"Server Meeting Report tidak menyala. Lihat {logs / 'server.log'}:\n\n"
                       f"{log_tail(logs / 'server.log')}")


def is_meeting_report(cmd: str) -> bool:
    return ("server:app" in cmd or "server.py" in cmd) and ("MeetingNotes" in cmd or "meeting-report" in cmd)


def stop_group(pgid: str) -> bool:
    """Resume, then stop a whole process group (a paused `uvicorn --reload` has a paused worker too)."""
    try:
        g = int(pgid)
        if g <= 1 or g == os.getpgrp():
            return False
        os.killpg(g, signal.SIGCONT)
        os.killpg(g, signal.SIGTERM)
        for _ in range(25):
            if not port_in_use():
                return True
            time.sleep(0.2)
        os.killpg(g, signal.SIGKILL)
        time.sleep(0.5)
    except (ValueError, ProcessLookupError, PermissionError):
        pass
    return not port_in_use()


def free_port() -> None:
    """Make PORT usable: stop a stuck Meeting Report server on it, or move to a spare port.

    A Meeting Report server that answers (e.g. a dev server of another version) is left
    running; only one that does not answer is stopped. Another app's port is never touched.
    """
    if not port_in_use():
        return
    if not health():
        _, pgid, desc = port_owner()
        if desc and is_meeting_report(desc) and pgid and stop_group(pgid):
            return
    for p in SPARE_PORTS:
        use_port(p)
        if not port_in_use():
            core.SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
            port_file().write_text(str(p))
            return
    use_port(server.PORT)
    raise RuntimeError(port_busy_message())


def on_drop(window, e) -> None:
    """Drag a recording into the window: pass its path, so a 1 GB video is read where
    it is instead of being copied in (Usulan 15)."""
    try:
        files = (e.get("dataTransfer") or {}).get("files") or []
        path = files[0].get("pywebviewFullPath") if files else None
    except Exception:  # noqa: BLE001
        path = None
    if path:
        window.run_js(f"window.MN && window.MN.dropPath({json.dumps(path)})")


def main() -> None:
    use_port(saved_port() or server.PORT)
    if not healthy():
        stop_old_server()
        try:
            if not healthy():
                if PORT != server.PORT:  # try the usual port again first
                    use_port(server.PORT)
                    port_file().unlink(missing_ok=True)
                free_port()
                if not healthy():
                    start_server()
        except RuntimeError as e:
            show_error(str(e))
            sys.exit(1)
    url = f"{base()}/?t={server.session_token()}&shell=app"
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
