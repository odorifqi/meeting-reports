"""One background worker for the heavy jobs (PRD: one job at a time).

Jobs: transcribe (local Whisper), summary (Claude, after confirmation) and
suggest (optional Claude word suggestions). Progress goes to meeting.json and
to every open window through the event bus (SSE). Logs never contain
transcript text.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import queue
import shutil
import threading
import time
import traceback
from pathlib import Path

import core
import filters
import store as store_mod
import suggest

PARTS = ".parts"


class Bus:
    """Fan-out of small JSON events to SSE listeners (thread safe)."""

    def __init__(self):
        self._subs: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subs.append((asyncio.get_running_loop(), q))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs = [s for s in self._subs if s[1] is not q]

    def publish(self, event: dict) -> None:
        with self._lock:
            subs = list(self._subs)
        for loop, q in subs:
            def put(q=q):
                if not q.full():
                    q.put_nowait(event)
            try:
                loop.call_soon_threadsafe(put)
            except RuntimeError:  # loop closed
                pass


def _clock() -> str:
    return dt.datetime.now().strftime("%H:%M:%S")


def postprocess_summary(md: str, meta: dict, version: dict, model: str, send: dict) -> str:
    """Add the fixed header lines, notes and footer from the approved sample report."""
    lines = md.strip().splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("# ")), None)
    if start is None:
        lines = [f"# {meta.get('title') or 'Laporan Rapat'}", ""] + lines
        start = 0
    else:
        lines = lines[start:]
    segs = version.get("segments", [])
    parts = version.get("participants") or []
    ids = {p["id"] for p in parts}
    tagged = sum(1 for s in segs if s.get("speaker_id") in ids)
    rev = meta.get("transcript_rev")
    date = ""
    if meta.get("created"):
        date = core.fmt_date_id(dt.datetime.fromisoformat(meta["created"]))
    if meta.get("duration_sec"):
        date += f" · Durasi {core.fmt_dur(meta['duration_sec'])}"
    tag_txt = (f"{tagged} dari {len(segs)} segmen ditandai" if parts else "tanpa penanda peserta")
    head = [lines[0], ""]
    if date:
        head += [date, ""]
    head.append(f"_Dibuat dari transkrip versi {rev} · {tag_txt}_")
    body = lines[1:]
    while body and not body[0].strip():
        body = body[1:]
    lines = head + [""] + body

    notes = []
    cs = meta.get("claude_suggest")
    if cs:
        notes.append(f"- Transkrip sudah melalui saran Claude (✦ Disarankan Claude: {cs.get('accepted', 0)} "
                     f"diterima, {cs.get('rejected', 0)} ditolak).")
    if send.get("masked") or send.get("withheld"):
        notes.append(f"- {send.get('masked', 0)} data sensitif disamarkan sebelum dikirim dan dipulihkan di Mac ini; "
                     f"{send.get('withheld', 0)} segmen rahasia tidak dikirim.")
    if parts and tagged < len(segs):
        notes.append(f"- {len(segs) - tagged} segmen belum ditandai pembicaranya. PIC dari segmen itu ditulis "
                     f"\"Belum ditandai\".")
    if notes:
        idx = next((i for i, l in enumerate(lines) if l.strip().lower() == "## catatan lain"), None)
        if idx is None:
            lines += ["", "## Catatan Lain"] + notes
        else:
            end = next((j for j in range(idx + 1, len(lines)) if lines[j].startswith("## ")
                        or lines[j].strip() == "---"), len(lines))
            while end > idx + 1 and not lines[end - 1].strip():
                end -= 1
            existing = [l for l in lines[idx + 1:end] if l.strip()]
            if existing and all(l.strip("- ").lower().startswith(("tidak ada", "-")) for l in existing):
                lines[idx + 1:end] = notes
            else:
                lines[end:end] = notes
    # drop any footer Claude wrote itself, then add ours
    while lines and (not lines[-1].strip() or lines[-1].strip() == "---"):
        lines.pop()
    lines += ["", "---", f"_Dibuat {core.fmt_date_short(dt.datetime.now())} · {model} · dari transkrip versi {rev}_"]
    return "\n".join(lines) + "\n"


class Jobs:
    def __init__(self, store: store_mod.Store, bus: Bus, *, load_audio=None, transcribe_chunk=None,
                 save_m4a=None, claude=None, api_key=None, config=None):
        self.store = store
        self.bus = bus
        self.load_audio = load_audio or core.load_audio
        self.transcribe_chunk = transcribe_chunk or core.transcribe_chunk
        self.save_m4a = save_m4a or core.save_audio_m4a
        self.claude = claude or core.claude_text
        self.api_key = api_key or core.get_api_key
        self.config = config or core.load_config
        self.q: queue.Queue = queue.Queue()
        self.current: dict | None = None
        self.pending: list[dict] = []
        self.cancelled: set[str] = set()
        self.last_activity = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True, name="mn-worker")
        self._thread.start()

    # ---------------------------------------------------------------- queue
    def busy(self) -> bool:
        return self.current is not None or not self.q.empty()

    def state(self) -> dict:
        return {"current": self.current, "pending": list(self.pending)}

    def submit(self, kind: str, mid: str, **args) -> None:
        job = {"kind": kind, "mid": mid, "args": args}
        self.cancelled.discard(mid)
        self.pending.append({"kind": kind, "mid": mid})
        self.q.put(job)
        self.last_activity = time.time()
        self._emit(mid, kind="queued")

    def cancel(self, mid: str) -> None:
        self.cancelled.add(mid)
        self._emit(mid, kind="cancel_requested")

    def recover(self) -> None:
        """After a crash or quit, nothing is running: mark interrupted jobs."""
        for mid in self.store.ids():
            try:
                m = self.store.meta(mid)
            except Exception:
                continue
            if m.get("status") in ("queued", "transcribing"):
                self.store.update(mid, status="failed", progress=None,
                                  error={"message": "Aplikasi ditutup saat transkripsi berjalan. "
                                                    "Bagian yang sudah selesai disimpan; lanjutkan dari sana.",
                                         "chunk": (m.get("progress") or {}).get("chunk")})
            elif m.get("status") == "summarizing":
                self.store.update(mid, status=m.get("prev_status") or "transcript_only", progress=None,
                                  summary_error="Aplikasi ditutup saat ringkasan dibuat. Coba lagi.")
            elif m.get("suggest_job"):
                self.store.update(mid, suggest_job=None)

    def _emit(self, mid: str, **ev) -> None:
        self.bus.publish({"mid": mid, **ev})

    def _log(self, mid: str, text: str) -> None:
        with self.store.lock:
            m = self.store.meta(mid)
            log = m.get("log") or []
            log.append({"t": _clock(), "text": text})
            m["log"] = log[-200:]
            self.store.save_meta(mid, m)
        self._emit(mid, kind="log", text=text)

    def _progress(self, mid: str, **p) -> None:
        self.store.update(mid, progress=p)
        self._emit(mid, kind="progress", progress=p)

    def _run(self) -> None:
        while True:
            job = self.q.get()
            self.pending = [p for p in self.pending if not (p["mid"] == job["mid"] and p["kind"] == job["kind"])]
            self.current = {"kind": job["kind"], "mid": job["mid"]}
            try:
                getattr(self, f"_job_{job['kind']}")(job["mid"], **job["args"])
            except Exception:  # never let the worker die
                traceback.print_exc()
            finally:
                self.current = None
                self.last_activity = time.time()
                self._emit(job["mid"], kind="done", job=job["kind"])

    # ---------------------------------------------------------------- transcription
    def _job_transcribe(self, mid: str) -> None:
        st = self.store
        folder = st.path(mid)
        m = st.meta(mid)
        cfg = self.config()
        s = m.get("settings") or {}
        parts_dir = folder / PARTS
        fp = json.dumps({"lang": s.get("language"), "rs": s.get("remove_silence", True),
                         "vocab": s.get("vocabulary", ""), "repo": cfg.get("whisper_repo"),
                         "ms": cfg.get("min_silence_sec")}, sort_keys=True)
        if parts_dir.exists() and (parts_dir / "settings.json").exists() and \
                (parts_dir / "settings.json").read_text() != fp:
            shutil.rmtree(parts_dir)
        parts_dir.mkdir(exist_ok=True)
        (parts_dir / "settings.json").write_text(fp)
        chunk_i, n = 0, 0
        st.update(mid, status="transcribing", error=None)
        try:
            src = Path(m["source"])
            if not src.exists():
                raise RuntimeError(f"File rekaman tidak ditemukan: {src.name}")
            self._progress(mid, phase="decode", pct=0, chunk=0, chunks=0, eta=None)
            self._log(mid, "Membaca rekaman")
            audio = self.load_audio(str(src))
            dur = len(audio) / core.SR
            clean = core.clean_audio(audio, s.get("remove_silence", True), cfg.get("min_silence_sec", 2.0))
            self._log(mid, f"Durasi {core.fmt_dur(dur)}, setelah buang hening {core.fmt_dur(clean.clean_sec)}")
            st.update(mid, duration_sec=round(dur, 1), clean_sec=round(clean.clean_sec, 1))
            if s.get("save_clean_audio", True) and s.get("remove_silence", True) and \
                    not (folder / "Audio bersih.m4a").exists():
                try:
                    self.save_m4a(clean.audio, folder / "Audio bersih.m4a")
                    self._log(mid, "Audio bersih disimpan")
                except Exception as exc:  # noqa: BLE001 - optional output
                    self._log(mid, f"Audio bersih gagal disimpan ({type(exc).__name__})")
            chunks = core.chunk_bounds(clean)
            n = len(chunks)
            names = [p["name"] for p in m.get("participants") or []]
            prompt = core.whisper_prompt(s.get("vocabulary", ""), names)
            lang = s.get("language") or None
            done_audio, spent = 0.0, 0.0
            segments: list[dict] = []
            for chunk_i, (a, b) in enumerate(chunks):
                part = parts_dir / f"chunk-{chunk_i}.json"
                length = (b - a) / core.SR
                if part.exists():
                    segments.extend(json.loads(part.read_text(encoding="utf-8")))
                    self._log(mid, f"Bagian {chunk_i + 1} dari {n} sudah ada, dilewati")
                    continue
                if mid in self.cancelled:
                    raise core.Cancelled()
                remaining = sum((y - x) / core.SR for x, y in chunks[chunk_i:])
                eta = round(spent / done_audio * remaining) if done_audio else None
                self._progress(mid, phase="transcribe", pct=round(100 * chunk_i / n), chunk=chunk_i + 1,
                               chunks=n, eta=eta)
                self._log(mid, f"Mentranskrip bagian {chunk_i + 1} dari {n}")
                t0 = time.time()
                segs = self.transcribe_chunk(clean.audio[a:b], lang, prompt, cfg.get("whisper_repo", core.WHISPER_REPO),
                                             cfg.get("word_confidence", True))
                placed = core.place_chunk(clean, a, segs)
                part.write_text(json.dumps(placed, ensure_ascii=False), encoding="utf-8")
                segments.extend(placed)
                spent += time.time() - t0
                done_audio += length
                self._log(mid, f"Bagian {chunk_i + 1} selesai ({len(placed)} segmen, {round(time.time() - t0)} detik)")
            segments = core.dedupe(segments)
            self._progress(mid, phase="finish", pct=100, chunk=n, chunks=n, eta=0)
            st.save_whisper(mid, segments, {"progress": None, "error": None,
                                            "duration_sec": round(dur, 1), "clean_sec": round(clean.clean_sec, 1)})
            shutil.rmtree(parts_dir, ignore_errors=True)
            self._log(mid, f"Transkripsi selesai: {len(segments)} segmen. Siap ditinjau.")
            self._emit(mid, kind="status", status="awaiting_review")
        except core.Cancelled:
            st.update(mid, status="failed", progress=None,
                      error={"message": "Dibatalkan. Bagian yang sudah selesai disimpan.", "chunk": chunk_i + 1,
                             "chunks": n, "cancelled": True})
            self._log(mid, "Dibatalkan oleh pengguna")
            self._emit(mid, kind="status", status="failed")
        except Exception as exc:  # noqa: BLE001
            msg = str(exc) or type(exc).__name__
            st.update(mid, status="failed", progress=None,
                      error={"message": msg, "chunk": chunk_i + 1 if n else None, "chunks": n or None})
            self._log(mid, f"Gagal: {type(exc).__name__}")
            self._emit(mid, kind="status", status="failed")
        finally:
            self.cancelled.discard(mid)

    # ---------------------------------------------------------------- summary
    def _job_summary(self, mid: str, context: str = "", model: str | None = None, note: str | None = None) -> None:
        st = self.store
        m = st.meta(mid)
        prev = m.get("status") if m.get("status") != "summarizing" else (m.get("prev_status") or "transcript_only")
        cfg = self.config()
        model = model or cfg.get("claude_model") or core.CLAUDE_MODEL
        v = st.latest(mid)
        send = filters.build_send(m, v, cfg, context)
        st.update(mid, status="summarizing", prev_status=prev, summary_error=None)
        self._progress(mid, phase="send", masked=send["masked"], withheld=send["withheld"], words=send["words"],
                       model=model)
        self._emit(mid, kind="status", status="summarizing")
        try:
            key = self.api_key()
            if not key:
                raise RuntimeError("API key Anthropic belum diisi. Buka Pengaturan.")
            user = f"<info_rapat>\n{send['header']}\n</info_rapat>\n\n<transkrip>\n{send['transcript']}\n</transkrip>"
            if send["context"]:
                user += f"\n\nKonteks tambahan dari pengguna: {send['context']}"
            st.log_send(mid, {"kind": "summary", "model": model, "words": send["words"],
                              "masked": send["masked"], "withheld": send["withheld"], "rev": m.get("transcript_rev")})
            raw = self.claude(core.SUMMARY_SYSTEM, user, key, model, 8000)
            self._progress(mid, phase="restore", masked=send["masked"], withheld=send["withheld"],
                           words=send["words"], model=model)
            md = filters.restore(raw, send["tokens"])
            md = postprocess_summary(md, st.meta(mid), v, model, send)
            ver = st.add_summary(mid, md, m.get("transcript_rev"), model, context,
                                 {"counts": send["counts"], "withheld": send["withheld"]}, note=note)
            st.update(mid, status="done", progress=None, prev_status=None)
            self._log(mid, f"Ringkasan versi {ver} dibuat ({model})")
            self._emit(mid, kind="status", status="done", summary=ver)
        except Exception as exc:  # noqa: BLE001
            st.update(mid, status=prev, progress=None, prev_status=None,
                      summary_error=_friendly(exc))
            self._log(mid, f"Ringkasan gagal: {type(exc).__name__}")
            self._emit(mid, kind="status", status=prev, error=True)

    # ---------------------------------------------------------------- Claude suggestions
    def _job_suggest(self, mid: str, model: str | None = None) -> None:
        st = self.store
        m = st.meta(mid)
        cfg = self.config()
        model = model or cfg.get("claude_model") or core.CLAUDE_MODEL
        st.update(mid, suggest_job={"state": "running", "at": store_mod.now_iso()})
        self._emit(mid, kind="suggest", state="running")
        try:
            key = self.api_key()
            if not key:
                raise RuntimeError("API key Anthropic belum diisi. Buka Pengaturan.")
            v = st.latest(mid)
            vocab = (m.get("settings") or {}).get("vocabulary", "") or cfg.get("vocabulary", "")
            items, send = suggest.claude_suggestions(m, v, cfg, key, model, vocab, call=self.claude)
            st.log_send(mid, {"kind": "suggest", "model": model, "words": send["words"], "masked": send["masked"],
                              "withheld": send["withheld"], "rev": m.get("transcript_rev")})
            store_mod._write_json(st.path(mid) / "saran-claude.json",
                                  {"at": store_mod.now_iso(), "based_on_rev": m.get("transcript_rev"),
                                   "model": model, "items": items})
            st.update(mid, suggest_job={"state": "ready", "count": len(items), "at": store_mod.now_iso()})
            self._emit(mid, kind="suggest", state="ready", count=len(items))
        except Exception as exc:  # noqa: BLE001
            st.update(mid, suggest_job={"state": "failed", "error": _friendly(exc)})
            self._emit(mid, kind="suggest", state="failed")


def _friendly(exc: Exception) -> str:
    name = type(exc).__name__
    msg = str(exc)
    if "Authentication" in name or "401" in msg:
        return "API key ditolak Anthropic. Periksa di Pengaturan."
    if "RateLimit" in name or "429" in msg:
        return "Batas pemakaian API tercapai. Coba lagi beberapa menit lagi."
    if "Connection" in name or "Timeout" in name:
        return "Tidak bisa terhubung ke Anthropic. Periksa koneksi internet."
    if "Overloaded" in msg or "529" in msg:
        return "Server Anthropic sedang sibuk. Coba lagi."
    return msg or name
