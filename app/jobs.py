"""One background worker for the heavy jobs (PRD: one job at a time).

Jobs: transcribe (local Whisper), summary (the chosen AI provider, after
confirmation) and suggest (optional AI word suggestions). Progress goes to meeting.json and
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


def load_track(load_audio, path: str, track=None, start=None, dur=None):
    """Call load_audio with only the arguments it needs (tests pass simpler fakes)."""
    kw = {}
    if start is not None:
        kw.update(start=start, dur=dur)
    if track is not None:
        kw["track"] = track
    return load_audio(path, **kw)


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
        notes.append(f"- Transkrip sudah melalui saran AI (✦ Disarankan AI: {cs.get('accepted', 0)} "
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
    # drop any footer the model wrote itself, then add ours
    while lines and (not lines[-1].strip() or lines[-1].strip() == "---"):
        lines.pop()
    lines += ["", "---", f"_Dibuat {core.fmt_date_short(dt.datetime.now())} · {model} · dari transkrip versi {rev}_"]
    return "\n".join(lines) + "\n"


class Jobs:
    def __init__(self, store: store_mod.Store, bus: Bus, *, load_audio=None, transcribe_chunk=None,
                 save_m4a=None, claude=None, api_key=None, config=None, model_ready=None, download_model=None):
        self.store = store
        self.bus = bus
        self.load_audio = load_audio or core.load_audio
        self.transcribe_chunk = transcribe_chunk or core.transcribe_chunk
        self.save_m4a = save_m4a or core.save_audio_m4a
        self.claude = claude or core.ai_text
        self.api_key = api_key or core.get_api_key
        self.config = config or core.load_config
        self.model_ready = model_ready or core.whisper_downloaded
        self.download_model = download_model or core.download_whisper
        self.q: queue.Queue = queue.Queue()
        self.current: dict | None = None
        self.pending: list[dict] = []
        self.cancelled: set[str] = set()
        self.last_activity = time.time()
        # Whisper uses the GPU; the worker and "Transkrip ulang bagian ini" never run together
        self.whisper_lock = threading.Lock()
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
            elif (m.get("suggest_job") or {}).get("state") in ("queued", "running"):
                self.store.update(mid, suggest_job={"state": "failed",
                                                    "error": "Aplikasi ditutup saat saran AI dibuat. Coba lagi."})
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
        m = self.store.update(mid, progress=p)
        # durations ride along so the step list updates without a full reload
        self._emit(mid, kind="progress", progress=p, duration_sec=m.get("duration_sec"),
                   clean_sec=m.get("clean_sec"))

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
        wm = core.whisper_model(s.get("whisper_model") or cfg.get("whisper_model"))
        repo = wm["repo"]
        parts_dir = folder / PARTS
        fp = json.dumps({"lang": s.get("language"), "rs": s.get("remove_silence", True),
                         "vocab": s.get("vocabulary", ""), "repo": repo,
                         "ms": cfg.get("min_silence_sec"), "track": s.get("audio_track")}, sort_keys=True)
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
            free = core.disk_free(folder)
            if free is not None and free < core.disk_need(m.get("duration_sec"), s.get("video")):
                raise RuntimeError("Ruang disk tidak cukup untuk menyimpan hasil. Kosongkan sedikit ruang lalu coba lagi.")
            audio = load_track(self.load_audio, str(src), s.get("audio_track"))
            dur = len(audio) / core.SR
            if s.get("video") and not (folder / "Audio rapat.m4a").exists():
                # sound of the video for playback in the editor (timestamps = original)
                try:
                    self.save_m4a(audio, folder / "Audio rapat.m4a")
                    self._log(mid, "Suara video disimpan sebagai Audio rapat.m4a")
                except Exception as exc:  # noqa: BLE001 - playback falls back to the video
                    self._log(mid, f"Audio rapat gagal disimpan ({type(exc).__name__})")
            clean = core.clean_audio(audio, s.get("remove_silence", True), cfg.get("min_silence_sec", 2.0))
            self._log(mid, f"Durasi {core.fmt_dur(dur)}, setelah buang hening {core.fmt_dur(clean.clean_sec)}")
            st.update(mid, duration_sec=round(dur, 1), clean_sec=round(clean.clean_sec, 1))
            # where someone speaks, used by the editor to point at skipped stretches
            regions = clean.regions if s.get("remove_silence", True) else \
                core.detect_speech(audio, min_silence=cfg.get("min_silence_sec", 2.0))[0]
            st.save_regions(mid, regions, dur)
            gap_sec = float(cfg.get("gap_fill_sec", 3.0) or 0)
            if s.get("save_clean_audio", True) and s.get("remove_silence", True) and \
                    not (folder / "Audio bersih.m4a").exists():
                try:
                    self.save_m4a(clean.audio, folder / "Audio bersih.m4a")
                    # NOTE: the map describes this file, so it is written only together with it
                    st.save_clean_map(mid, clean.mapping, clean.clean_sec)
                    self._log(mid, "Audio bersih disimpan")
                except Exception as exc:  # noqa: BLE001 - optional output
                    self._log(mid, f"Audio bersih gagal disimpan ({type(exc).__name__})")
            if self.model_ready(repo) is False:
                # first use of this model: download it before the first chunk so the
                # progress screen says why nothing moves for a while
                self._progress(mid, phase="download", pct=0, chunk=0, chunks=0, eta=None)
                self._log(mid, f"Mengunduh model {wm['name']} (±{wm['size_gb']:.1f} GB, sekali saja)".replace(".", ",", 1))
                self.download_model(repo)
                self._log(mid, f"Model {wm['name']} siap")
            self._log(mid, f"Model transkripsi: {wm['label']} ({wm['name']})")
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
                wc = cfg.get("word_confidence", True)
                with self.whisper_lock:
                    segs = self.transcribe_chunk(clean.audio[a:b], lang, prompt, repo, wc)
                    if gap_sec > 0:
                        # Whisper sometimes skips a whole 30 s window; try those stretches again
                        # on their own, without the prompt (Usulan 3)
                        segs, report = core.fill_gaps(
                            clean.audio[a:b], segs,
                            lambda piece: self.transcribe_chunk(piece, lang, None, repo, wc), gap_sec)
                        for ga, gb, found in report:
                            oa = clean.to_original(a / core.SR + ga)
                            ob = clean.to_original(a / core.SR + gb)
                            self._log(mid, f"Celah {core.fmt_ts(oa)}–{core.fmt_ts(ob)} diisi ulang ({found} segmen)")
                placed = core.place_chunk(clean, a, segs)
                part.write_text(json.dumps(placed, ensure_ascii=False), encoding="utf-8")
                segments.extend(placed)
                spent += time.time() - t0
                done_audio += length
                self._log(mid, f"Bagian {chunk_i + 1} selesai ({len(placed)} segmen, {round(time.time() - t0)} detik)")
            segments = core.dedupe(segments)
            self._progress(mid, phase="finish", pct=100, chunk=n, chunks=n, eta=0)
            st.save_whisper(mid, segments, {"progress": None, "error": None,
                                            "whisper_model": {"key": wm["key"], "name": wm["name"], "repo": repo},
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
        provider = core.provider_id(cfg)
        pname = core.provider_name(cfg, provider)
        model = model or core.provider_model(cfg, provider)
        v = st.latest(mid)
        send = filters.build_send(m, v, cfg, context)
        st.update(mid, status="summarizing", prev_status=prev, summary_error=None)
        self._progress(mid, phase="send", masked=send["masked"], withheld=send["withheld"], words=send["words"],
                       model=model)
        self._emit(mid, kind="status", status="summarizing")
        try:
            key = self.api_key(provider)
            if not key:
                raise RuntimeError(f"API key {pname} belum diisi. Buka Pengaturan.")
            user = f"<info_rapat>\n{send['header']}\n</info_rapat>\n\n<transkrip>\n{send['transcript']}\n</transkrip>"
            if send["context"]:
                user += f"\n\nKonteks tambahan dari pengguna: {send['context']}"
            st.log_send(mid, {"kind": "summary", "provider": provider, "model": model, "words": send["words"],
                              "masked": send["masked"], "withheld": send["withheld"], "rev": m.get("transcript_rev")})
            host = core._host(core.provider_url(cfg, provider)) if provider != "anthropic" else "api.anthropic.com"
            n_chars = f"{len(user):,}".replace(",", ".")
            self._log(mid, f"Kirim ringkasan ke {pname} ({host}), model {model}, {n_chars} karakter")
            t0 = time.time()
            try:
                raw = self.claude(core.SUMMARY_SYSTEM, user, key, model, 8000)
            except Exception as exc:
                kind = getattr(exc, "kind", type(exc).__name__)
                status = getattr(exc, "status", None)
                self._log(mid, f"Jawaban gagal setelah {round(time.time() - t0)} detik: {kind}"
                               + (f" HTTP {status}" if status else ""))
                raise
            self._log(mid, f"Jawaban diterima dalam {round(time.time() - t0)} detik")
            self._progress(mid, phase="restore", masked=send["masked"], withheld=send["withheld"],
                           words=send["words"], model=model)
            md = filters.restore(raw, send["tokens"])
            md = postprocess_summary(md, st.meta(mid), v, model, send)
            ver = st.add_summary(mid, md, m.get("transcript_rev"), model, context,
                                 {"counts": send["counts"], "withheld": send["withheld"]}, note=note,
                                 source=provider)
            st.update(mid, status="done", progress=None, prev_status=None)
            self._log(mid, f"Ringkasan versi {ver} dibuat ({model})")
            self._emit(mid, kind="status", status="done", summary=ver)
        except Exception as exc:  # noqa: BLE001
            st.update(mid, status=prev, progress=None, prev_status=None,
                      summary_error=_friendly(exc, pname))
            self._log(mid, f"Ringkasan gagal: {type(exc).__name__}")
            self._emit(mid, kind="status", status=prev, error=True)

    # ---------------------------------------------------------------- AI suggestions
    def _job_suggest(self, mid: str, model: str | None = None) -> None:
        st = self.store
        m = st.meta(mid)
        cfg = self.config()
        provider = core.provider_id(cfg)
        pname = core.provider_name(cfg, provider)
        model = model or core.provider_model(cfg, provider)
        job = {"state": "running", "phase": "wait", "at": store_mod.now_iso(), "model": model}

        def step(**changes) -> None:
            job.update(changes)
            st.update(mid, suggest_job=dict(job))
            self._emit(mid, kind="suggest", state=job["state"], job=dict(job), count=job.get("count"))

        try:
            v = st.latest(mid)
            send = filters.build_send(m, v, cfg, with_ids=True)
            step(masked=send["masked"], withheld=send["withheld"], words=send["words"])
            key = self.api_key(provider)
            if not key:
                raise RuntimeError(f"API key {pname} belum diisi. Buka Pengaturan.")
            vocab = (m.get("settings") or {}).get("vocabulary", "") or cfg.get("vocabulary", "")
            items, send = suggest.claude_suggestions(m, v, cfg, key, model, vocab, call=self.claude, send=send,
                                                     on_reply=lambda: step(phase="match"))
            st.log_send(mid, {"kind": "suggest", "provider": provider, "model": model, "words": send["words"], "masked": send["masked"],
                              "withheld": send["withheld"], "rev": m.get("transcript_rev")})
            store_mod._write_json(st.path(mid) / "saran-claude.json",
                                  {"at": store_mod.now_iso(), "based_on_rev": m.get("transcript_rev"),
                                   "provider": provider, "model": model, "items": items})
            step(state="ready", phase=None, count=len(items), at=store_mod.now_iso())
        except Exception as exc:  # noqa: BLE001
            step(state="failed", phase=None, error=_friendly(exc, pname))


def _friendly(exc: Exception, provider: str = "Anthropic") -> str:
    name = type(exc).__name__
    msg = str(exc)
    if isinstance(exc, core.AIError) and exc.kind != "other":
        where = f" ({exc.host})" if exc.host else ""
        said = f" Pesan server: \u201c{exc.detail}\u201d" if exc.detail and exc.kind == "http" else ""
        if exc.kind == "config":
            return msg
        if exc.kind == "timeout":
            return (f"{provider}{where} tidak mengirim jawaban dalam {core.AI_TIMEOUT // 60} menit. "
                    "Server mungkin sedang lambat atau model terlalu berat untuk transkrip sepanjang ini. "
                    "Coba lagi, atau pilih model yang lebih cepat.")
        if exc.kind == "network":
            if provider == "Ollama lokal":
                return "Ollama tidak berjalan di Mac ini. Buka Ollama, lalu coba lagi."
            return (f"Koneksi ke {provider}{where} terputus atau gagal dibuka ({exc.detail or 'jaringan'}). "
                    "Periksa internet dan alamat server di Pengaturan.")
        if exc.kind == "empty":
            return f"{provider}{where} menjawab kosong. Periksa nama model di Pengaturan."
        s = exc.status
        if s in (401, 403):
            return f"API key ditolak {provider} (HTTP {s}).{said}"
        if s == 404:
            return (f"Alamat atau model tidak ditemukan di {provider}{where} (HTTP 404). Isi alamat dasar saja, "
                    f"misalnya https://server/v1, dan periksa nama model.{said}")
        if s == 429:
            return f"Batas pemakaian {provider} tercapai (HTTP 429). Coba lagi beberapa menit lagi.{said}"
        if s in (408, 504, 524):
            return (f"Server {provider}{where} kehabisan waktu menunggu model (HTTP {s}). "
                    f"Coba lagi atau pilih model yang lebih cepat.{said}")
        if s and s >= 500:
            return f"Server {provider}{where} sedang bermasalah (HTTP {s}). Coba lagi.{said}"
        return f"{provider}{where} menolak permintaan" + (f" (HTTP {s})." if s else ".") + said
    if "Authentication" in name or "401" in msg or "403" in msg:
        return f"API key ditolak {provider}. Periksa di Pengaturan."
    if "RateLimit" in name or "429" in msg:
        return "Batas pemakaian API tercapai. Coba lagi beberapa menit lagi."
    if "Connection" in name or "Timeout" in name or msg.startswith("Connection"):
        if provider == "Ollama lokal":
            return "Ollama tidak berjalan di Mac ini. Buka Ollama, lalu coba lagi."
        return f"Tidak bisa terhubung ke {provider}. Periksa koneksi internet."
    if "Overloaded" in msg or "529" in msg or "503" in msg:
        return f"Server {provider} sedang sibuk. Coba lagi."
    if "404" in msg:
        return f"Model tidak ditemukan di {provider}. Periksa nama model di Pengaturan."
    return msg or name
