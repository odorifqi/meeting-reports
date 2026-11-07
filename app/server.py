"""Meeting Notes v1.1 local server: FastAPI on 127.0.0.1 only.

Security model (PRD): binds to 127.0.0.1, checks the Host header (DNS
rebinding), requires the session token (cookie set from the launcher URL, or
the X-MN-Token header), checks Origin on every write, never sends the API key
to the browser, and never logs transcript text.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import core
import filters
import jobs as jobs_mod
import store as store_mod
import suggest

APP_VERSION = "1.2.0"
PORT = int(os.environ.get("MN_PORT", "8765"))
STATIC = Path(__file__).parent / "static"
COOKIE = "mn_session"
AUDIO_EXT = {".m4a", ".mp3", ".wav", ".aac", ".mp4", ".mov", ".caf", ".aiff", ".aif", ".flac", ".ogg",
             ".webm", ".m4v", ".qta"}
EDITABLE_SETTINGS = {"claude_model", "remove_silence", "min_silence_sec", "save_clean_audio", "language",
                     "vocabulary", "theme", "redact", "sensitive_words", "word_confidence"}
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"]


def session_token() -> str:
    env = os.environ.get("MN_TOKEN")
    if env:
        return env
    f = core.SUPPORT_DIR / "session-token"
    try:
        tok = f.read_text().strip()
        if len(tok) >= 32:
            return tok
    except OSError:
        pass
    core.SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_urlsafe(32)
    f.write_text(tok)
    os.chmod(f, 0o600)
    return tok


def create_app(store: store_mod.Store | None = None, jobs: jobs_mod.Jobs | None = None,
               token: str | None = None, port: int = PORT) -> FastAPI:
    st = store or store_mod.Store()
    bus = jobs.bus if jobs else jobs_mod.Bus()
    jb = jobs or jobs_mod.Jobs(st, bus)
    tok = token or session_token()
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    origins = {f"http://{h}" for h in hosts}
    app = FastAPI(title="Meeting Notes", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.jobs, app.state.token = st, jb, tok
    app.state.clients = 0
    app.state.last_seen = time.time()
    jb.recover()

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.headers.get("host") not in hosts:
            return JSONResponse({"detail": "Host tidak diizinkan"}, status_code=403)
        path = request.url.path
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and origin not in origins:
                return JSONResponse({"detail": "Origin tidak diizinkan"}, status_code=403)
        if path.startswith("/api/") and path != "/api/health":
            given = request.headers.get("x-mn-token") or request.cookies.get(COOKIE)
            if not given or not secrets.compare_digest(given, tok):
                return JSONResponse({"detail": "Sesi tidak valid. Buka lewat Meeting Notes."}, status_code=401)
            app.state.last_seen = time.time()
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if path == "/" or path.endswith(".html"):
            resp.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        return resp

    # ------------------------------------------------------------------ page
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, t: str | None = None):
        cookie = request.cookies.get(COOKIE)
        ok = (t and secrets.compare_digest(t, tok)) or (cookie and secrets.compare_digest(cookie, tok))
        if not ok:
            return HTMLResponse("<!doctype html><meta charset=utf-8><title>Meeting Notes</title>"
                                "<body style='font:15px -apple-system,sans-serif;padding:40px'>"
                                "<h3>Sesi tidak valid</h3><p>Buka Meeting Notes dari aplikasinya, atau jalankan "
                                "<code>./run.sh dev</code> lalu buka tautan yang dicetak di Terminal.</p>",
                                status_code=401)
        resp = FileResponse(STATIC / "index.html", media_type="text/html")
        resp.set_cookie(COOKIE, tok, httponly=True, samesite="strict", path="/")
        return resp

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    def meta_or_404(mid: str) -> dict:
        try:
            return st.meta(mid)
        except KeyError:
            raise HTTPException(404, "Rapat tidak ditemukan")

    def job_on(mid: str) -> str | None:
        cur = jb.current
        if cur and cur["mid"] == mid:
            return cur["kind"]
        for p in jb.pending:
            if p["mid"] == mid:
                return p["kind"]
        return None

    # ------------------------------------------------------------------ state + events
    @app.get("/api/state")
    def state():
        cfg = core.load_config()
        return {"version": APP_VERSION, "busy": jb.busy(), "jobs": jb.state(),
                "api_key": bool(core.get_api_key()), "theme": cfg.get("theme", "system"),
                "output_root": str(st.root), "models": MODELS, "model": cfg.get("claude_model")}

    @app.get("/api/events")
    async def events(request: Request):
        q = bus.subscribe()
        app.state.clients += 1

        async def gen():
            try:
                yield "retry: 2000\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        ev = await asyncio.wait_for(q.get(), timeout=15)
                        yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                bus.unsubscribe(q)
                app.state.clients -= 1
                app.state.last_seen = time.time()
        return StreamingResponse(gen(), media_type="text/event-stream")

    # ------------------------------------------------------------------ meetings
    @app.get("/api/meetings")
    def list_meetings(q: str = "", status: str = ""):
        rows = st.list(q, status)
        for r in rows:
            r["job"] = job_on(r["id"])
        return {"meetings": rows, "root": str(st.root)}

    @app.post("/api/pick-file")
    def pick_file():
        loc = core.VOICE_MEMOS_DIR if core.VOICE_MEMOS_DIR.exists() else Path.home()
        script = (f'POSIX path of (choose file with prompt "Pilih rekaman rapat" '
                  f'default location (POSIX file "{loc}"))')
        try:
            out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=600)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            raise HTTPException(501, "Pemilih file macOS tidak tersedia. Seret file ke jendela.")
        if out.returncode != 0:
            return {"cancel": True}
        p = Path(out.stdout.strip())
        return file_info(p)

    def file_info(p: Path) -> dict:
        if not p.is_file():
            raise HTTPException(400, "File tidak ditemukan")
        return {"path": str(p), "name": p.name, "size": p.stat().st_size,
                "audio": p.suffix.lower() in AUDIO_EXT}

    @app.post("/api/file-info")
    def file_info_ep(body: dict = Body(...)):
        """File opened from Finder ("Open with Meeting Notes")."""
        return file_info(Path(str(body.get("path") or "")).expanduser())

    @app.post("/api/upload")
    async def upload(request: Request):
        name = Path(request.headers.get("x-filename", "rekaman.m4a")).name
        if Path(name).suffix.lower() not in AUDIO_EXT:
            raise HTTPException(400, "Format file tidak dikenali sebagai audio atau video")
        d = core.SUPPORT_DIR / "incoming" / uuid.uuid4().hex
        d.mkdir(parents=True)
        dest = d / name
        with dest.open("wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
        return file_info(dest)

    @app.get("/api/participants/recent")
    def recent_participants():
        out = []
        for r in st.list():
            m = st.meta(r["id"])
            if m.get("participants"):
                out.append({"id": r["id"], "title": r["title"], "created": r["created"],
                            "participants": m["participants"]})
            if len(out) >= 8:
                break
        return {"meetings": out}

    @app.post("/api/meetings")
    def create_meeting(body: dict = Body(...)):
        src = Path(str(body.get("source_path") or ""))
        if not src.is_file():
            raise HTTPException(400, "File rekaman tidak ditemukan")
        cfg = core.load_config()
        settings = {
            "language": body.get("language", cfg.get("language", "id")),
            "remove_silence": bool(body.get("remove_silence", cfg.get("remove_silence", True))),
            "save_clean_audio": bool(body.get("save_clean_audio", cfg.get("save_clean_audio", True))),
            "vocabulary": str(body.get("vocabulary", cfg.get("vocabulary", ""))),
        }
        parts = []
        for i, p in enumerate(body.get("participants") or []):
            name = str(p.get("name", "")).strip()
            if name:
                parts.append({"id": f"p{i + 1}", "name": name, "role": str(p.get("role") or "").strip()})
        title = str(body.get("title") or "").strip() or src.stem
        mid = st.create(src, title, settings, parts)
        incoming = core.SUPPORT_DIR / "incoming"
        if incoming in src.parents:   # dragged in: keep the copy with the meeting
            dest = st.path(mid) / f"Rekaman asli{src.suffix.lower()}"
            shutil.move(str(src), dest)
            shutil.rmtree(src.parent, ignore_errors=True)
            st.update(mid, source=str(dest))
        jb.submit("transcribe", mid)
        return {"id": mid}

    def detail(mid: str) -> dict:
        m = meta_or_404(mid)
        p = st.path(mid)
        counts = st.tag_counts(mid, m)
        sums = m.get("summaries") or []
        src = Path(m.get("source") or "")
        sug = store_mod._read_json(p / "saran-claude.json")
        return {
            **{k: v for k, v in m.items() if k not in ("sends",)},
            "stale": st.is_stale(m),
            "stale_text": store_mod.change_text(m.get("stale_changes") or {}) if st.is_stale(m) else "",
            "counts": counts,
            "versions": st.versions(mid) if (p / store_mod.VERS).exists() else [],
            "summary_count": len(sums),
            "audio": {"asli": bool(m.get("source")) and src.is_file(),
                      "bersih": (p / "Audio bersih.m4a").exists()},
            "files": sorted(f.name for f in p.iterdir() if f.is_file() and not f.name.startswith(".")
                            and f.suffix in (".txt", ".md", ".docx", ".m4a")),
            "has_draft": (p / store_mod.DRAFT).exists(),
            "claude_pending": bool(sug and sug.get("based_on_rev") == m.get("transcript_rev")
                                   and not sug.get("reviewed")),
            "job": job_on(mid),
            "sends": len(m.get("sends") or []),
            "folder": str(p),
        }

    @app.get("/api/meetings/{mid}")
    def get_meeting(mid: str):
        return detail(mid)

    @app.patch("/api/meetings/{mid}")
    def patch_meeting(mid: str, body: dict = Body(...)):
        meta_or_404(mid)
        title = str(body.get("title") or "").strip()
        if title:
            st.update(mid, title=title)
            if st.meta(mid).get("transcript_rev"):
                st.write_transcript_files(mid)
        return detail(mid)

    @app.delete("/api/meetings/{mid}")
    def delete_meeting(mid: str):
        meta_or_404(mid)
        if job_on(mid):
            raise HTTPException(409, "Rapat ini sedang diproses. Batalkan dulu.")
        st.trash(mid)
        return {"ok": True}

    @app.post("/api/meetings/{mid}/retry")
    def retry(mid: str):
        m = meta_or_404(mid)
        if m.get("status") != "failed":
            raise HTTPException(409, "Hanya rapat yang gagal yang bisa diulang")
        st.update(mid, status="queued", error=None)
        jb.submit("transcribe", mid)
        return {"ok": True}

    @app.post("/api/meetings/{mid}/cancel")
    def cancel(mid: str):
        meta_or_404(mid)
        jb.cancel(mid)
        return {"ok": True}

    @app.post("/api/meetings/{mid}/reveal")
    def reveal(mid: str, body: dict = Body(default={})):
        p = st.path(mid)
        name = Path(str(body.get("file") or "")).name
        target = p / name if name and (p / name).exists() else p
        args = ["open", "-R", str(target)] if body.get("reveal", True) or target == p else ["open", str(target)]
        try:
            subprocess.run(args, check=False, timeout=10)
        except FileNotFoundError:
            raise HTTPException(501, "Finder tidak tersedia di mesin ini")
        return {"ok": True}

    # ------------------------------------------------------------------ transcript + editor
    def base_version(mid: str, m: dict) -> dict:
        rev = m.get("transcript_rev", 0)
        return st.read_version(mid, rev)

    @app.get("/api/meetings/{mid}/transcript")
    def transcript(mid: str, rev: int | None = None):
        m = meta_or_404(mid)
        try:
            return st.read_version(mid, rev) if rev is not None else base_version(mid, m)
        except KeyError:
            raise HTTPException(404, "Versi tidak ditemukan")

    @app.get("/api/meetings/{mid}/versions")
    def versions(mid: str):
        meta_or_404(mid)
        return {"versions": st.versions(mid)}

    @app.get("/api/meetings/{mid}/editor")
    def editor(mid: str):
        m = meta_or_404(mid)
        try:
            base = base_version(mid, m)
            raw = st.read_version(mid, 0)
        except KeyError:
            raise HTTPException(409, "Transkrip belum tersedia")
        low = {s["id"]: s.get("low_words") or [] for s in raw.get("segments", [])}
        cfg = core.load_config()
        vocab = ", ".join(x for x in [(m.get("settings") or {}).get("vocabulary", ""), cfg.get("vocabulary", "")] if x)
        draft = st.read_draft(mid)
        segs = (draft or base)["segments"]
        parts = (draft or base).get("participants") or m.get("participants") or []
        sug = store_mod._read_json(st.path(mid) / "saran-claude.json")
        claude = sug["items"] if sug and sug.get("based_on_rev") == m.get("transcript_rev") and not sug.get("reviewed") else []
        return {
            "base": {"rev": base.get("rev"), "segments": base["segments"],
                     "participants": base.get("participants") or m.get("participants") or []},
            "draft": draft,
            "local": suggest.local_suggestions(segs, parts, vocab, low),
            "claude": claude,
            "low_words": low,
            "rev_hash": m.get("rev_hash"),
        }

    @app.put("/api/meetings/{mid}/draft")
    def put_draft(mid: str, body: dict = Body(...)):
        meta_or_404(mid)
        st.write_draft(mid, {"segments": store_mod.canon_segments(body.get("segments") or []),
                             "participants": store_mod.canon_participants(body.get("participants") or [])})
        return {"ok": True}

    @app.delete("/api/meetings/{mid}/draft")
    def del_draft(mid: str):
        meta_or_404(mid)
        st.clear_draft(mid)
        return {"ok": True}

    @app.post("/api/meetings/{mid}/check")
    def check_changed(mid: str, body: dict = Body(...)):
        """Lets the editor enable/disable Simpan using the same hash as the store."""
        m = meta_or_404(mid)
        h = store_mod.content_hash(body.get("segments") or [], body.get("participants") or [])
        return {"changed": not (m.get("transcript_rev", 0) > 0 and h == m.get("rev_hash"))}

    @app.post("/api/meetings/{mid}/save")
    def save(mid: str, body: dict = Body(...)):
        m = meta_or_404(mid)
        if m.get("status") in ("queued", "transcribing"):
            raise HTTPException(409, "Transkripsi belum selesai")
        segs = body.get("segments")
        parts = body.get("participants") or []
        if not isinstance(segs, list) or not segs:
            raise HTTPException(400, "Transkrip kosong")
        for s in segs:
            if not {"id", "start", "end"} <= set(s):
                raise HTTPException(400, "Segmen tidak lengkap")
        cl = body.get("claude")
        source = "claude" if cl and cl.get("accepted") else ("first" if not m.get("transcript_rev") else "edit")
        res = st.save_version(mid, segs, parts, source=source,
                              note="Saran Claude diterapkan" if source == "claude" else None)
        if cl:
            st.update(mid, claude_suggest={"at": store_mod.now_iso(), "accepted": int(cl.get("accepted", 0)),
                                           "rejected": int(cl.get("rejected", 0))})
            f = st.path(mid) / "saran-claude.json"
            sug = store_mod._read_json(f)
            if sug:
                sug["reviewed"] = True
                store_mod._write_json(f, sug)
            st.write_transcript_files(mid)
        m = st.meta(mid)
        if m.get("status") == "awaiting_review":
            st.update(mid, status="done" if m.get("summaries") else "transcript_only")
        st.clear_draft(mid)
        d = detail(mid)
        return {"changed": res["changed"], "rev": res["rev"],
                "changes_text": store_mod.change_text(res.get("changes") or {}), "meeting": d}

    @app.post("/api/meetings/{mid}/restore")
    def restore(mid: str, body: dict = Body(...)):
        meta_or_404(mid)
        try:
            res = st.restore_version(mid, int(body.get("rev")))
        except (KeyError, TypeError, ValueError):
            raise HTTPException(404, "Versi tidak ditemukan")
        return {"changed": res["changed"], "rev": res["rev"], "meeting": detail(mid)}

    # ------------------------------------------------------------------ Claude: preview, summary, suggest
    @app.post("/api/meetings/{mid}/preview")
    def preview(mid: str, body: dict = Body(default={})):
        m = meta_or_404(mid)
        if not m.get("transcript_rev"):
            raise HTTPException(409, "Simpan transkrip dulu")
        send = filters.build_send(m, st.latest(mid), core.load_config(), str(body.get("context") or ""),
                                  with_ids=bool(body.get("with_ids")))
        return filters.public_preview(send)

    @app.post("/api/meetings/{mid}/summary")
    def make_summary(mid: str, body: dict = Body(...)):
        m = meta_or_404(mid)
        if body.get("confirmed") is not True:
            raise HTTPException(400, "Pengiriman ke Anthropic harus dikonfirmasi pengguna")
        if not m.get("transcript_rev"):
            raise HTTPException(409, "Simpan transkrip dulu")
        if job_on(mid):
            raise HTTPException(409, "Rapat ini sedang diproses")
        model = body.get("model") if body.get("model") in MODELS else None
        jb.submit("summary", mid, context=str(body.get("context") or ""), model=model,
                  note=body.get("note"))
        return {"ok": True}

    @app.post("/api/meetings/{mid}/suggest")
    def claude_suggest(mid: str, body: dict = Body(...)):
        m = meta_or_404(mid)
        if body.get("confirmed") is not True:
            raise HTTPException(400, "Pengiriman ke Anthropic harus dikonfirmasi pengguna")
        if not m.get("transcript_rev"):
            raise HTTPException(409, "Simpan transkrip dulu")
        if job_on(mid):
            raise HTTPException(409, "Rapat ini sedang diproses")
        model = body.get("model") if body.get("model") in MODELS else None
        jb.submit("suggest", mid, model=model)
        return {"ok": True}

    @app.post("/api/meetings/{mid}/claude-review")
    def claude_review(mid: str, body: dict = Body(...)):
        """Close the Claude review without changes (counts still mark the meeting)."""
        meta_or_404(mid)
        st.update(mid, claude_suggest={"at": store_mod.now_iso(), "accepted": int(body.get("accepted", 0)),
                                       "rejected": int(body.get("rejected", 0))})
        f = st.path(mid) / "saran-claude.json"
        sug = store_mod._read_json(f)
        if sug:
            sug["reviewed"] = True
            store_mod._write_json(f, sug)
        if st.meta(mid).get("transcript_rev"):
            st.write_transcript_files(mid)
        return detail(mid)

    @app.get("/api/meetings/{mid}/summaries")
    def summaries(mid: str):
        m = meta_or_404(mid)
        return {"summaries": m.get("summaries") or [], "transcript_rev": m.get("transcript_rev")}

    @app.get("/api/meetings/{mid}/summaries/{ver}")
    def summary(mid: str, ver: int):
        m = meta_or_404(mid)
        sums = m.get("summaries") or []
        if not 1 <= ver <= len(sums):
            raise HTTPException(404, "Versi ringkasan tidak ditemukan")
        return {"info": sums[ver - 1], "md": st.read_summary(mid, ver), "latest": len(sums),
                "stale_line": st.stale_line(m) if st.is_stale(m) and ver == len(sums) else None}

    @app.post("/api/meetings/{mid}/summaries/{ver}/restore")
    def restore_summary(mid: str, ver: int):
        m = meta_or_404(mid)
        if not 1 <= ver <= len(m.get("summaries") or []):
            raise HTTPException(404, "Versi ringkasan tidak ditemukan")
        new = st.restore_summary(mid, ver)
        return {"ver": new, "meeting": detail(mid)}

    # ------------------------------------------------------------------ audio (HTTP Range, F16)
    @app.get("/api/meetings/{mid}/audio/{kind}")
    def audio(mid: str, kind: str):
        m = meta_or_404(mid)
        if kind == "bersih":
            f = st.path(mid) / "Audio bersih.m4a"
        elif kind == "asli":
            f = Path(m.get("source") or "")
        else:
            raise HTTPException(404)
        if not f.is_file():
            raise HTTPException(404, "File audio tidak ditemukan")
        mt = {".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".aac": "audio/aac",
              ".mp4": "video/mp4", ".mov": "video/quicktime", ".caf": "audio/x-caf", ".flac": "audio/flac",
              ".ogg": "audio/ogg", ".webm": "audio/webm", ".aiff": "audio/aiff", ".aif": "audio/aiff",
              ".qta": "video/quicktime", ".m4v": "video/mp4"}.get(f.suffix.lower(), "application/octet-stream")
        return FileResponse(f, media_type=mt)

    # ------------------------------------------------------------------ settings
    @app.get("/api/settings")
    def get_settings():
        cfg = core.load_config()
        return {"config": {k: cfg.get(k) for k in EDITABLE_SETTINGS}, "api_key": bool(core.get_api_key()),
                "models": MODELS, "output_root": str(st.root), "categories": filters.CATEGORIES}

    @app.put("/api/settings")
    def put_settings(body: dict = Body(...)):
        cfg = core.load_config()
        for k, v in body.items():
            if k not in EDITABLE_SETTINGS:
                continue
            if k == "claude_model" and v not in MODELS:
                continue
            if k == "redact":
                cfg["redact"] = {c: bool((v or {}).get(c, cfg["redact"].get(c, True))) for c in filters.CATEGORIES}
            else:
                cfg[k] = v
        core.save_config(cfg)
        return get_settings()

    @app.post("/api/vocabulary")
    def add_term(body: dict = Body(...)):
        term = str(body.get("term") or "").strip()
        if not term:
            raise HTTPException(400, "Istilah kosong")
        cfg = core.load_config()
        cur = [t.strip() for t in (cfg.get("vocabulary") or "").split(",") if t.strip()]
        if term.lower() not in {t.lower() for t in cur}:
            cur.append(term)
        cfg["vocabulary"] = ", ".join(cur)
        core.save_config(cfg)
        return {"vocabulary": cfg["vocabulary"]}

    @app.post("/api/settings/api-key")
    def set_key(body: dict = Body(...)):
        key = str(body.get("key") or "").strip()
        if not key.startswith("sk-ant-"):
            raise HTTPException(400, "Format API key tidak dikenali (diawali sk-ant-)")
        try:
            core.set_api_key(key)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise HTTPException(500, "Gagal menyimpan ke Keychain")
        return {"api_key": True}

    @app.delete("/api/settings/api-key")
    def del_key():
        core.delete_api_key()
        return {"api_key": bool(core.get_api_key())}

    @app.post("/api/settings/test-key")
    def test_key():
        key = core.get_api_key()
        if not key:
            raise HTTPException(400, "API key belum diisi")
        try:
            core.test_api_key(key, core.load_config().get("claude_model", core.CLAUDE_MODEL))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": jobs_mod._friendly(exc)}
        return {"ok": True}

    @app.get("/api/send-log")
    def send_log(limit: int = 20):
        return {"sends": st.send_log(limit)}

    @app.post("/api/reveal-root")
    def reveal_root():
        st.root.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["open", str(st.root)], check=False, timeout=10)
        except FileNotFoundError:
            raise HTTPException(501, "Finder tidak tersedia di mesin ini")
        return {"ok": True}

    @app.get("/api/health")
    def health():
        return {"ok": True, "app": "meeting-notes", "version": APP_VERSION}

    return app


def idle_watch(app: FastAPI, minutes: float) -> None:
    """Launcher mode: stop the server when no window and no job for a while."""
    import threading

    def loop():
        while True:
            time.sleep(30)
            idle = time.time() - max(app.state.last_seen, app.state.jobs.last_activity)
            if app.state.clients <= 0 and not app.state.jobs.busy() and idle > minutes * 60:
                os._exit(0)
    threading.Thread(target=loop, daemon=True).start()


def main() -> None:
    import uvicorn

    app = create_app()
    if os.environ.get("MN_IDLE_MIN"):
        idle_watch(app, float(os.environ["MN_IDLE_MIN"]))
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning", access_log=False)


# `uvicorn server:app --reload` (run.sh dev) imports this module attribute lazily
def __getattr__(name):
    if name == "app":
        a = create_app()
        globals()["app"] = a
        return a
    raise AttributeError(name)


if __name__ == "__main__":
    main()
