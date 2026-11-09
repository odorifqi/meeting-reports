"""Meeting Report pipeline: load audio, remove silence, transcribe, summarize, export.

Kept free of GUI code so it can be tested on its own. mlx_whisper and anthropic
are imported lazily inside the functions that need them.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import math
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SR = 16000            # Whisper works at 16 kHz mono
FRAME = 0.03          # energy analysis window, seconds
CHUNK_SEC = 600       # transcribe in ~10 minute chunks so the UI can show progress

WHISPER_REPO = "mlx-community/whisper-large-v3-turbo"
# transcription models the user picks from: fast (default) or accurate (3-6x slower)
WHISPER_MODELS = {
    "cepat": {"repo": WHISPER_REPO, "label": "Cepat", "name": "large-v3-turbo", "size_gb": 1.6},
    "akurat": {"repo": "mlx-community/whisper-large-v3-mlx", "label": "Akurat", "name": "large-v3", "size_gb": 3.1},
}
CLAUDE_MODEL = "claude-sonnet-5-5"
KEYCHAIN_SERVICE = "MeetingNotes"
KEYCHAIN_ACCOUNT = "anthropic-api-key"

SUPPORT_DIR = Path(os.environ.get("MN_SUPPORT_DIR")
                   or Path.home() / "Library" / "Application Support" / "MeetingNotes")
OUTPUT_ROOT = Path(os.environ.get("MN_OUTPUT_DIR") or Path.home() / "Documents" / "Meeting Report")
# results folder before v1.3; moved to OUTPUT_ROOT once (migrate_output_root)
OLD_OUTPUT_ROOT = Path.home() / "Documents" / "Meeting Notes"
VOICE_MEMOS_DIR = (Path.home() / "Library" / "Group Containers"
                   / "group.com.apple.VoiceMemos.shared" / "Recordings")


# --------------------------------------------------------------------------- config

DEFAULT_CONFIG = {
    "claude_model": CLAUDE_MODEL,
    "whisper_model": "cepat",
    "remove_silence": True,
    "min_silence_sec": 2.0,
    "save_clean_audio": True,
    "language": "id",
    "vocabulary": "",
    "theme": "system",
    # F15: categories masked before any text leaves the Mac
    "redact": {"rekening": True, "nik": True, "hp": True, "kartu": True, "npwp": True, "email": True},
    "sensitive_words": "",
    "word_confidence": True,
    # AI provider for summaries and word suggestions (Usulan 14)
    "ai_provider": "anthropic",
    "ai_models": {},
    "ai_base_url": {},
    # re-transcribe stretches of speech Whisper skipped (seconds, clean timeline)
    "gap_fill_sec": 3.0,
}


def load_config() -> dict:
    path = SUPPORT_DIR / "config.json"
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        redact = {**cfg["redact"], **(saved.get("redact") or {})}
        cfg.update(saved)
        cfg["redact"] = redact
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg: dict) -> None:
    SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    (SUPPORT_DIR / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- audio

def _track_args(track, n_audio: int | None = None) -> list[str]:
    """ffmpeg arguments that pick one audio track of a video, or mix them all."""
    if track == "mix" and (n_audio or 0) > 1:
        return ["-filter_complex", f"amix=inputs={n_audio}:duration=longest:normalize=0", "-vn"]
    if isinstance(track, int) and track >= 0:
        return ["-map", f"0:a:{track}", "-vn"]
    return ["-vn"]


def load_audio(path: str, start: float | None = None, dur: float | None = None,
               track=None) -> np.ndarray:
    """Decode any ffmpeg-readable file to 16 kHz mono float32 (optionally only a range).

    Video files work too: only the audio is read (ffmpeg streams it, the video is
    never loaded), so a 1 GB screen recording costs the same memory as its audio:
    about 0.35 GB of RAM per hour of recording."""
    rng = []
    if start is not None:
        rng += ["-ss", f"{max(0.0, start):.3f}"]
    if dur is not None:
        rng += ["-t", f"{max(0.1, dur):.3f}"]
    n_audio = None
    if track == "mix":
        n_audio = len((probe(Path(path)).get("tracks") or []))
    cmd = ["ffmpeg", "-nostdin", "-v", "error", *rng, "-i", str(path), *_track_args(track, n_audio),
           "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg tidak ditemukan. Jalankan: brew install ffmpeg") from exc
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["?"]
        raise RuntimeError(f"Gagal membaca audio: {msg[0]}") from exc
    audio = np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0
    if audio.size == 0:
        raise RuntimeError("File tidak berisi audio.")
    return audio


VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".qta", ".avi"}


def probe(path: Path) -> dict:
    """Check a recording before processing (Usulan 15): audio tracks, codec, duration.

    Returns {ok, video, duration, tracks: [{n, codec, channels, duration, label}],
    problem}. Without ffprobe it returns ok=True and unknown=True (checked later)."""
    path = Path(path)
    out = {"ok": True, "video": path.suffix.lower() in VIDEO_EXT, "duration": None, "tracks": [],
           "problem": None, "unknown": False}
    try:
        res = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
                              "-show_streams", str(path)], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        out["unknown"] = True
        return out
    except subprocess.TimeoutExpired:
        out.update(ok=False, problem="File terlalu lama dibaca. Mungkin rusak atau masih disalin.")
        return out
    if res.returncode != 0:
        out.update(ok=False, problem="File rusak atau formatnya tidak dikenali. Coba ekspor ulang, "
                                     "atau konversi dulu ke m4a.")
        return out
    try:
        data = json.loads(res.stdout or "{}")
    except ValueError:
        data = {}
    fmt = data.get("format") or {}
    out["duration"] = _finite(fmt.get("duration"))
    n = 0
    for st in data.get("streams") or []:
        kind = st.get("codec_type")
        if kind == "video" and (st.get("disposition") or {}).get("attached_pic") != 1:
            out["video"] = True
        if kind != "audio":
            continue
        tags = st.get("tags") or {}
        d = _finite(st.get("duration")) or out["duration"]
        label = " · ".join(x for x in [tags.get("title") or tags.get("handler_name") or "",
                                        tags.get("language") if tags.get("language") not in (None, "und") else ""]
                           if x and x not in ("SoundHandler", "Core Media Audio"))
        out["tracks"].append({"n": n, "codec": st.get("codec_name") or "?", "channels": st.get("channels"),
                              "duration": d, "label": label})
        n += 1
    if not out["tracks"]:
        out.update(ok=False, problem=("Video ini tidak punya suara. Saat merekam layar, pastikan "
                                      "suara sistem atau mikrofon ikut direkam." if out["video"] else
                                      "File ini tidak berisi suara."))
    elif out["duration"] is not None and out["duration"] < 1:
        out.update(ok=False, problem="Rekaman terlalu pendek (kurang dari 1 detik).")
    return out


def default_track(info: dict):
    """The longest audio track (screen recorders sometimes add a short or silent one)."""
    tracks = info.get("tracks") or []
    if len(tracks) <= 1:
        return None
    return max(tracks, key=lambda t: t.get("duration") or 0)["n"]


def disk_need(duration: float | None, video: bool) -> int:
    """Bytes a meeting needs on disk: Audio bersih.m4a (+ Audio rapat.m4a for a video),
    transcripts and a safety margin. The recording itself is never copied."""
    hours = max((duration or 0) / 3600, 0.25)
    per_hour = 30 * 1024 ** 2 * (2 if video else 1)
    return int(hours * per_hour + 200 * 1024 ** 2)


def disk_free(path: Path) -> int | None:
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return None


@dataclass
class CleanResult:
    audio: np.ndarray                      # speech-only audio
    regions: list[tuple[float, float]]     # kept spans, original timeline (s)
    original_sec: float
    threshold_db: float
    mapping: list[tuple[float, float, float]] = field(default_factory=list)
    # mapping rows: (clean_start, orig_start, duration)

    @property
    def clean_sec(self) -> float:
        return len(self.audio) / SR

    @property
    def removed_sec(self) -> float:
        return max(0.0, self.original_sec - self.clean_sec)

    def to_original(self, t_clean: float) -> float:
        """Map a timestamp in the cleaned audio back to the original recording."""
        if not self.mapping:
            return t_clean
        row = self.mapping[0]
        for r in self.mapping:
            if r[0] <= t_clean:
                row = r
            else:
                break
        offset = min(max(t_clean - row[0], 0.0), row[2])
        return row[1] + offset

    def to_clean(self, t_orig: float) -> float:
        """Map a timestamp in the original recording to the cleaned audio.

        A moment inside a removed silence maps to the start of the next kept span."""
        return to_clean(self.mapping, t_orig)


def to_clean(mapping, t_orig: float) -> float:
    """Original-recording time to cleaned-audio time for mapping rows (clean_start, orig_start, dur)."""
    if not mapping:
        return t_orig
    for c0, o0, d in mapping:
        if t_orig < o0:
            return c0
        if t_orig <= o0 + d:
            return c0 + (t_orig - o0)
    c0, _, d = mapping[-1]
    return c0 + d


def detect_speech(audio: np.ndarray, min_silence: float = 2.0, pad: float = 0.4,
                  threshold_db: float | None = None) -> tuple[list[tuple[float, float]], float]:
    """Return speech regions (start, end) in seconds and the threshold used.

    A stretch counts as silence when its energy stays below the threshold for at
    least `min_silence` seconds. `pad` seconds of each silence are kept on both
    sides so words are not clipped. With no threshold given, it adapts to the
    recording: 10 dB above the room's noise floor, clamped to [-55, -30] dBFS.
    """
    total = len(audio) / SR
    hop = int(SR * FRAME)
    n = len(audio) // hop
    if n == 0:
        return [(0.0, total)], threshold_db or -40.0

    frames = audio[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1)) + 1e-10
    db = 20 * np.log10(rms)
    if threshold_db is None:
        floor = float(np.percentile(db, 15))
        threshold_db = float(np.clip(floor + 10.0, -55.0, -30.0))

    quiet = np.concatenate(([0], (db <= threshold_db).astype(np.int8), [0]))
    edges = np.diff(quiet)
    q_starts = np.where(edges == 1)[0]
    q_ends = np.where(edges == -1)[0]
    min_frames = int(round(min_silence / FRAME))

    cuts = []
    for s, e in zip(q_starts, q_ends):
        if e - s < min_frames:
            continue
        cs = 0.0 if s == 0 else s * FRAME + pad
        ce = total if e >= n else e * FRAME - pad
        if ce - cs > 0.05:
            cuts.append((cs, ce))

    regions = []
    cursor = 0.0
    for cs, ce in cuts:
        if cs - cursor > 0.05:
            regions.append((float(cursor), float(cs)))
        cursor = max(cursor, ce)
    if total - cursor > 0.05:
        regions.append((float(cursor), float(total)))
    return regions, threshold_db


def clean_audio(audio: np.ndarray, enabled: bool = True, min_silence: float = 2.0) -> CleanResult:
    total = len(audio) / SR
    if enabled:
        regions, thr = detect_speech(audio, min_silence=min_silence)
    else:
        regions, thr = [(0.0, total)], float("nan")

    parts, mapping, clean_t = [], [], 0.0
    for start, end in regions:
        a, b = int(start * SR), min(int(end * SR), len(audio))
        if b <= a:
            continue
        parts.append(audio[a:b])
        dur = (b - a) / SR
        mapping.append((clean_t, a / SR, dur))
        clean_t += dur
    joined = np.concatenate(parts) if parts else np.zeros(0, np.float32)
    return CleanResult(joined, regions, total, thr, mapping)


def save_audio_m4a(audio: np.ndarray, path: Path) -> None:
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR),
           "-ac", "1", "-i", "-", "-c:a", "aac", "-b:a", "64k", str(path)]
    subprocess.run(cmd, input=pcm, capture_output=True, check=True)


def chunk_bounds(clean: CleanResult, chunk_sec: float | None = None) -> list[tuple[int, int]]:
    """Split the cleaned audio into ~chunk_sec pieces, cutting only where silence was removed."""
    chunk_sec = chunk_sec or CHUNK_SEC
    n = len(clean.audio)
    if n == 0:
        return []
    cut_points = [int(row[0] * SR) for row in clean.mapping[1:]]
    bounds, start = [], 0
    for p in cut_points:
        if (p - start) / SR >= chunk_sec:
            bounds.append((start, p))
            start = p
    # no silence to cut at: fall back to fixed slices
    if not bounds and n / SR > 1.5 * chunk_sec:
        step = int(chunk_sec * SR)
        return [(i, min(i + step, n)) for i in range(0, n, step)]
    bounds.append((start, n))
    return bounds


# --------------------------------------------------------------------------- transcription

LOW_WORD_PROB = 0.30      # words below this probability are flagged for review (Usulan 4)


class Cancelled(Exception):
    """Raised when the user cancels a running transcription."""


def whisper_model(key: str | None) -> dict:
    """Model info for a key; unknown keys fall back to the fast model."""
    k = key if key in WHISPER_MODELS else "cepat"
    return {"key": k, **WHISPER_MODELS[k]}


def whisper_downloaded(repo: str) -> bool | None:
    """True if the model is already in the Hugging Face cache (None if that cannot be checked)."""
    try:
        from huggingface_hub import scan_cache_dir
        return any(r.repo_id == repo and r.size_on_disk > 100_000_000 for r in scan_cache_dir().repos)
    except Exception:  # noqa: BLE001 - no cache yet, or library missing
        return None


def download_whisper(repo: str) -> None:
    from huggingface_hub import snapshot_download
    snapshot_download(repo)


def whisper_prompt(vocabulary: str = "", participants: list[str] | None = None) -> str | None:
    parts = []
    if vocabulary.strip():
        parts.append(f"Istilah: {vocabulary.strip()}.")
    names = [p for p in (participants or []) if p.strip()]
    if names:
        parts.append(f"Peserta: {', '.join(names)}.")
    return " ".join(parts) if parts else None


@contextlib.contextmanager
def carry_initial_prompt(module):
    """Give every 30 s window the initial prompt, not only the first one.

    NOTE: with condition_on_previous_text=False, mlx-whisper (0.4.x) resets the prompt after
    each window, so the vocabulary and participant names reached only the first 30 s of a
    chunk. The transcribe loop builds DecodingOptions(prompt=...) per window: the first
    non-empty prompt is the initial prompt, and later empty prompts get it back.
    """
    original = module.DecodingOptions
    first: list[int] = []

    def options(**kwargs):
        prompt = kwargs.get("prompt")
        if prompt:
            if not first:
                first.extend(prompt)
        elif first:
            kwargs["prompt"] = list(first)
        return original(**kwargs)

    module.DecodingOptions = options
    try:
        yield
    finally:
        module.DecodingOptions = original


def transcribe_chunk(audio: np.ndarray, language: str | None, prompt: str | None,
                     repo: str = WHISPER_REPO, word_confidence: bool = True) -> list[dict]:
    """Transcribe one chunk. Times are relative to the chunk start (clean timeline)."""
    import mlx_whisper  # Apple Silicon only

    # NOTE: the package attribute mlx_whisper.transcribe is the function; the loop module sits in sys.modules
    loop = sys.modules["mlx_whisper.transcribe"]
    with carry_initial_prompt(loop) if prompt else contextlib.nullcontext():
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=repo,
            language=language or None,
            condition_on_previous_text=False,   # avoids repeated-phrase loops
            initial_prompt=prompt,
            word_timestamps=word_confidence,
            verbose=None,
        )
    out = []
    for s in result.get("segments", []):
        text = s.get("text", "").strip()
        # no letters or digits ("!", "...") = an empty decode, not speech
        if not text or not re.search(r"\w", text):
            continue
        lp = _finite(s.get("avg_logprob"))
        # standard Whisper hallucination guard
        if _finite(s.get("no_speech_prob")) is not None and s.get("no_speech_prob") > 0.6 \
                and lp is not None and lp < -1.0:
            continue
        low, words = [], []
        for w in s.get("words") or []:
            word = str(w.get("word", "")).strip()
            if word and float(w.get("probability", 1.0)) < LOW_WORD_PROB:
                low.append(word.strip(".,?!;:"))
            ws, we = _finite(w.get("start")), _finite(w.get("end"))
            if word and ws is not None and we is not None:
                words.append([ws, max(ws, we), word])
        out.append({
            "start": float(s["start"]),
            "end": float(s["end"]),
            "text": text,
            "avg_logprob": round(lp, 3) if lp is not None else None,
            "low_words": [w for w in low if w],
            "words": words,
        })
    return out


def shift_words(words, f) -> list:
    """Apply a time function to [start, end, word] rows (chunk offset, clean to original)."""
    return [[round(f(w[0]), 2), round(f(w[1]), 2), w[2]] for w in words or []]


def _finite(x) -> float | None:
    """A float that JSON can carry; NaN/inf/None become None."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def find_gaps(segs: list[dict], length: float, min_gap: float = 3.0) -> list[tuple[float, float]]:
    """Stretches longer than min_gap with no segment, in the chunk's own (clean) timeline.

    Silence above ~2 s was already removed, so a long empty stretch here is almost
    always speech that Whisper skipped (it jumps a whole 30 s window sometimes)."""
    gaps, cursor = [], 0.0
    for s in sorted(segs, key=lambda x: x["start"]):
        if s["start"] - cursor > min_gap:
            gaps.append((cursor, s["start"]))
        cursor = max(cursor, s["end"])
    if length - cursor > min_gap:
        gaps.append((cursor, length))
    return gaps


def fill_gaps(audio: np.ndarray, segs: list[dict], transcribe, min_gap: float = 3.0,
              pad: float = 1.0) -> tuple[list[dict], list[tuple[float, float, int]]]:
    """Transcribe each gap again on its own and insert what Whisper finds there.

    `transcribe(audio_slice)` returns segments relative to the slice. Returns the
    merged segments and [(gap_start, gap_end, n_found)] for the log."""
    length = len(audio) / SR
    gaps = find_gaps(segs, length, min_gap)
    if not gaps:
        return segs, []
    out, report = list(segs), []
    for a, b in gaps:
        lo, hi = max(0.0, a - pad), min(length, b + pad)
        found = []
        for s in transcribe(audio[int(lo * SR):int(hi * SR)]) or []:
            st, en = lo + s["start"], lo + s["end"]
            mid = (st + en) / 2
            if a <= mid <= b:
                found.append({**s, "start": round(st, 2), "end": round(min(en, hi), 2), "gap_fill": True,
                              "words": shift_words(s.get("words"), lambda t, lo=lo: lo + t)})
        out.extend(found)
        report.append((a, b, len(found)))
    out.sort(key=lambda x: x["start"])
    return out, report


def place_chunk(clean: CleanResult, chunk_start_sample: int, segs: list[dict]) -> list[dict]:
    """Map chunk-relative segment times back to the original recording."""
    base = chunk_start_sample / SR
    placed = []
    for s in segs:
        placed.append({**s, "start": round(clean.to_original(base + s["start"]), 2),
                       "end": round(clean.to_original(base + s["end"]), 2),
                       "words": shift_words(s.get("words"), lambda t: clean.to_original(base + t))})
    return placed


def dedupe(segments: list[dict]) -> list[dict]:
    out: list[dict] = []
    for s in segments:
        if out and out[-1]["text"] == s["text"]:
            continue
        out.append(s)
    return out


def transcribe(clean: CleanResult, language: str | None, vocabulary: str = "",
               repo: str = WHISPER_REPO, progress=None, participants=None,
               word_confidence: bool = True) -> list[dict]:
    """Whole-recording transcription (kept for scripts and v1 compatibility)."""
    chunks = chunk_bounds(clean)
    prompt = whisper_prompt(vocabulary, participants)
    segments: list[dict] = []
    for i, (a, b) in enumerate(chunks):
        if progress:
            progress(i, len(chunks))
        segs = transcribe_chunk(clean.audio[a:b], language, prompt, repo, word_confidence)
        segments.extend(place_chunk(clean, a, segs))
    if progress:
        progress(len(chunks), len(chunks))
    return dedupe(segments)


def fmt_ts(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def fmt_dur(sec: float) -> str:
    sec = int(round(sec))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
         "September", "Oktober", "November", "Desember"]


def fmt_date_id(d: dt.datetime, with_day: bool = True) -> str:
    base = f"{d.day} {BULAN[d.month - 1]} {d.year}, {d:%H.%M}"
    return f"{HARI[d.weekday()]}, {base}" if with_day else base


def fmt_date_short(d: dt.datetime) -> str:
    return f"{d.day} {BULAN[d.month - 1][:3]} {d.year} {d:%H.%M}"


def format_transcript(segments: list[dict], title: str, clean: CleanResult | None = None,
                      meta: dict | None = None, participants: list[dict] | None = None) -> str:
    """Write Transkrip.txt.

    With `meta` (v1.1) the header follows the approved sample report: title, date,
    recording, language, version, tagging status, AI suggestions and the
    participant block. Lines are "[HH:MM:SS] Nama: teks", "(Belum ditandai): teks"
    when a participant list exists but the segment is untagged, or plain text
    when no participants were entered.
    """
    if meta is None:   # v1 format
        lines = [f"Transkrip: {title}",
                 f"Dibuat: {dt.datetime.now():%d %B %Y %H:%M}"]
        if clean is not None:
            lines.append(f"Durasi rekaman: {fmt_ts(clean.original_sec)}"
                         f"  |  bagian hening dibuang: {fmt_ts(clean.removed_sec)}")
        lines.append("Timestamp mengacu ke rekaman asli.")
        lines.append("")
        lines += [f"[{fmt_ts(s['start'])}] {s['text']}" for s in segments]
        return "\n".join(lines) + "\n"

    parts = participants or []
    names = {p["id"]: p["name"] for p in parts}
    total = len(segments)
    tagged = sum(1 for s in segments if s.get("speaker_id") in names)
    L = ["TRANSKRIP RAPAT",
         f"Judul        : {title}"]
    if meta.get("created"):
        L.append(f"Tanggal      : {fmt_date_id(dt.datetime.fromisoformat(meta['created']))}")
    rec = meta.get("source_name") or ""
    if meta.get("duration_sec"):
        rec += f" ({fmt_dur(meta['duration_sec'])}"
        if meta.get("clean_sec") and meta.get("remove_silence", True):
            rec += f"; setelah buang hening {fmt_dur(meta['clean_sec'])}"
        rec += ")"
    if rec.strip():
        L.append(f"Rekaman      : {rec.strip()}")
    L.append(f"Bahasa       : {LANG_NAMES.get(meta.get('language') or '', 'Otomatis')}")
    wm = meta.get("whisper_model") or {}
    if wm.get("name"):
        L.append(f"Model        : Whisper {wm['name']} ({WHISPER_MODELS.get(wm.get('key'), {}).get('label', '')}, lokal)".replace(" (, lokal)", " (lokal)"))
    if meta.get("rev"):
        saved = meta.get("saved_at")
        L.append(f"Versi        : {meta['rev']}" + (
            f", disimpan {fmt_date_short(dt.datetime.fromisoformat(saved))}" if saved else ""))
    if not parts:
        L.append(f"Penanda      : Tidak ada (0 dari {total} segmen)")
    elif tagged == total:
        L.append(f"Penanda      : {tagged} dari {total} segmen ditandai")
    else:
        L.append(f"Penanda      : {tagged} dari {total} segmen ditandai, {total - tagged} belum ditandai")
    cs = meta.get("claude_suggest")
    if cs:
        who = f" · {cs['provider']}" if cs.get("provider") else ""
        L.append(f"Saran AI     : ✦ Disarankan AI{who}, {fmt_date_short(dt.datetime.fromisoformat(cs['at']))}"
                 f" ({cs.get('accepted', 0)} diterima, {cs.get('rejected', 0)} ditolak)")
    else:
        L.append("Saran AI     : Tidak dijalankan")
    L.append("Timestamp mengacu ke rekaman asli.")
    L.append("")
    if not parts:
        L.append("PESERTA      : Tidak diisi")
    else:
        L.append(f"PESERTA ({len(parts)})")
        for i, p in enumerate(parts):
            L.append(f"  {i + 1}. {p['name'].ljust(16)}{p.get('role') or ''}".rstrip())
    L.append("")
    L.append("─" * 44)
    for s in segments:
        ts = f"[{fmt_ts(s['start'])}]"
        if s.get("secret"):
            text = s["text"] + "  (rahasia, tidak dikirim ke layanan AI)"
        else:
            text = s["text"]
        if not parts:
            L.append(f"{ts} {text}")
        elif s.get("speaker_id") in names:
            L.append(f"{ts} {names[s['speaker_id']]}: {text}")
        else:
            L.append(f"{ts} (Belum ditandai): {text}")
    return "\n".join(L) + "\n"


LANG_NAMES = {"id": "Indonesia", "en": "Inggris", "": "Otomatis"}


# --------------------------------------------------------------------------- AI providers + API keys (Keychain)

# Usulan 14: summaries and word suggestions can use any of these. Keys live in the
# macOS Keychain, one entry per provider. Ollama runs on this Mac and needs no key.
PROVIDERS = {
    "anthropic": {"name": "Anthropic (Claude)", "short": "Anthropic", "key": True, "prefix": "sk-ant-",
                  "models": ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"], "url": "",
                  "local": False},
    "openai": {"name": "OpenAI", "short": "OpenAI", "key": True, "prefix": "sk-",
               "models": ["gpt-5", "gpt-5-mini"], "url": "https://api.openai.com/v1", "local": False},
    "gemini": {"name": "Google Gemini", "short": "Gemini", "key": True, "prefix": "",
               "models": ["gemini-2.5-pro", "gemini-2.5-flash"],
               "url": "https://generativelanguage.googleapis.com/v1beta", "local": False},
    "compat": {"name": "Kompatibel OpenAI (URL sendiri)", "short": "server kustom", "key": True, "prefix": "",
               "models": [], "url": "", "local": False},
    "ollama": {"name": "Lokal di Mac ini (Ollama)", "short": "Ollama lokal", "key": False, "prefix": "",
               "models": ["qwen3:14b", "llama3.1:8b"], "url": "http://127.0.0.1:11434/v1", "local": True},
}
ENV_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}


def provider_id(cfg: dict | None = None) -> str:
    p = (cfg or load_config()).get("ai_provider") or "anthropic"
    return p if p in PROVIDERS else "anthropic"


def provider_model(cfg: dict | None = None, provider: str | None = None) -> str:
    cfg = cfg or load_config()
    provider = provider or provider_id(cfg)
    m = (cfg.get("ai_models") or {}).get(provider)
    if not m and provider == "anthropic":
        m = cfg.get("claude_model")
    if not m:
        models = PROVIDERS[provider]["models"]
        m = models[0] if models else ""
    return m


def provider_url(cfg: dict | None = None, provider: str | None = None) -> str:
    cfg = cfg or load_config()
    provider = provider or provider_id(cfg)
    return normalize_base_url((cfg.get("ai_base_url") or {}).get(provider) or PROVIDERS[provider]["url"])


def provider_name(cfg: dict | None = None, provider: str | None = None) -> str:
    return PROVIDERS[provider or provider_id(cfg)]["short"]


def _account(provider: str) -> str:
    return KEYCHAIN_ACCOUNT if provider == "anthropic" else f"{provider}-api-key"


def get_api_key(provider: str | None = None) -> str | None:
    provider = provider or provider_id()
    if not PROVIDERS[provider]["key"]:
        return "local"
    env = os.environ.get(ENV_KEYS.get(provider, ""), "") if provider in ENV_KEYS else ""
    if env:
        return env
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE,
                              "-a", _account(provider), "-w"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def has_api_key(provider: str | None = None) -> bool:
    provider = provider or provider_id()
    return not PROVIDERS[provider]["key"] or bool(get_api_key(provider))


def delete_api_key(provider: str | None = None) -> None:
    subprocess.run(["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE,
                    "-a", _account(provider or provider_id())], capture_output=True)


def set_api_key(key: str, provider: str | None = None) -> None:
    subprocess.run(["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE,
                    "-a", _account(provider or provider_id()), "-w", key.strip()],
                   capture_output=True, check=True)


def key_problem(key: str, provider: str) -> str | None:
    pre = PROVIDERS[provider]["prefix"]
    if not key:
        return "API key kosong"
    if pre and not key.startswith(pre):
        return f"Format API key {PROVIDERS[provider]['short']} tidak dikenali (diawali {pre})"
    return None


class AIError(RuntimeError):
    """Error from a provider. kind: "timeout", "network", "http", "empty" or "config";
    status: HTTP status for "http"; detail: the server's own error text (short)."""

    def __init__(self, msg: str, kind: str = "other", status: int | None = None, detail: str = "",
                 host: str = ""):
        super().__init__(msg)
        self.kind, self.status, self.detail, self.host = kind, status, detail, host


AI_TIMEOUT = 300        # seconds without any data from the server before giving up
_ENDPOINT_TAIL = re.compile(r"/(chat/completions|completions|responses|models|messages)/?$", re.I)


def normalize_base_url(url: str) -> str:
    """Users often paste the full endpoint (".../v1/chat/completions"). The app adds
    the endpoint itself, so keep only the base (".../v1")."""
    url = (url or "").strip().rstrip("/")
    while True:
        new = _ENDPOINT_TAIL.sub("", url).rstrip("/")
        if new == url:
            return url
        url = new


def _host(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc or url


def _err_detail(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace").strip()
    try:
        data = json.loads(text)
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            text = err.get("message") or json.dumps(err, ensure_ascii=False)
        elif err:
            text = str(err)
        elif isinstance(data, dict) and data.get("message"):
            text = str(data["message"])
    except ValueError:
        text = re.sub(r"<[^>]+>", " ", text)       # HTML error pages from proxies
    return re.sub(r"\s+", " ", text).strip()[:300]


def _raise_net(exc: BaseException, url: str, timeout: float):
    import socket
    host = _host(url)
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, (TimeoutError, socket.timeout)) or isinstance(exc, (TimeoutError, socket.timeout)):
        raise AIError(f"timeout after {int(timeout)} s", "timeout", host=host) from exc
    raise AIError(f"network: {type(reason).__name__}: {reason}", "network", detail=str(reason)[:200],
                  host=host) from exc


def _http_json(url: str, body: dict, headers: dict, timeout: float = AI_TIMEOUT) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = _err_detail(exc.read() or b"")
        raise AIError(f"HTTP {exc.code}: {detail}".strip(": "), "http", exc.code, detail, _host(url)) from exc
    except (urllib.error.URLError, OSError) as exc:
        _raise_net(exc, url, timeout)


def _chat_stream(url: str, body: dict, headers: dict, timeout: float = AI_TIMEOUT) -> str:
    """POST an OpenAI-style chat request with stream=true and join the pieces.

    Streaming keeps data flowing while a long summary is written, so proxies and
    gateways that drop silent connections (often after 60-120 s) do not cut it, and
    `timeout` applies to each wait for data instead of to the whole answer. A server
    that ignores "stream" and answers with plain JSON is handled too."""
    req = urllib.request.Request(url, data=json.dumps({**body, "stream": True}).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "Accept": "text/event-stream",
                                          **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "event-stream" not in ctype:
                data = json.loads(r.read().decode("utf-8"))
                if isinstance(data, dict) and data.get("error"):
                    detail = _err_detail(json.dumps(data).encode())
                    raise AIError(detail, "http", None, detail, _host(url))
                choices = data.get("choices") or []
                return ((choices[0].get("message") or {}).get("content") or "") if choices else ""
            out = []
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    ev = json.loads(payload)
                except ValueError:
                    continue
                if ev.get("error"):
                    detail = _err_detail(payload.encode())
                    raise AIError(detail, "http", None, detail, _host(url))
                for ch in ev.get("choices") or []:
                    piece = (ch.get("delta") or {}).get("content") or (ch.get("message") or {}).get("content")
                    if piece:
                        out.append(piece)
            return "".join(out)
    except urllib.error.HTTPError as exc:
        detail = _err_detail(exc.read() or b"")
        raise AIError(f"HTTP {exc.code}: {detail}".strip(": "), "http", exc.code, detail, _host(url)) from exc
    except AIError:
        raise
    except (urllib.error.URLError, OSError) as exc:
        _raise_net(exc, url, timeout)


def ai_text(system: str, user: str, api_key: str, model: str = CLAUDE_MODEL,
            max_tokens: int = 8000, provider: str | None = None, base_url: str | None = None) -> str:
    """One prompt to the chosen provider, returns the text answer."""
    cfg = load_config()
    provider = provider or provider_id(cfg)
    url = normalize_base_url(base_url or provider_url(cfg, provider))
    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                     messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    if provider == "gemini":
        data = _http_json(f"{url}/models/{model}:generateContent",
                          {"systemInstruction": {"parts": [{"text": system}]},
                           "contents": [{"role": "user", "parts": [{"text": user}]}],
                           "generationConfig": {"maxOutputTokens": max_tokens}},
                          {"x-goog-api-key": api_key})
        cands = data.get("candidates") or []
        parts = (cands[0].get("content") or {}).get("parts", []) if cands else []
        return "".join(p.get("text", "") for p in parts).strip()
    # openai, compat (any OpenAI-compatible server) and ollama
    if not url:
        raise AIError("Alamat server belum diisi di Pengaturan.", "config")
    headers = {"Authorization": f"Bearer {api_key}"} if PROVIDERS[provider]["key"] else {}
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    body["max_completion_tokens" if provider == "openai" else "max_tokens"] = max_tokens
    text = _chat_stream(f"{url}/chat/completions", body, headers,
                        timeout=900 if provider == "ollama" else AI_TIMEOUT).strip()
    if not text:
        raise AIError("empty answer", "empty", host=_host(url))
    return text


claude_text = ai_text   # older name, kept for scripts


# --------------------------------------------------------------------------- summary

SUMMARY_SYSTEM = """Kamu adalah notulis profesional.
Tugasmu menyusun laporan dari transkrip hasil speech-to-text otomatis yang sudah ditinjau pengguna.

Jenis rekaman:
- Rekaman bisa berupa rapat, diskusi, wawancara, kuliah, presentasi, podcast, siaran, atau narasi video.
- Kenali jenisnya dari isi, lalu tulis laporan yang cocok untuk jenis itu. Jangan menilai rekaman sebagai salah tempat atau "bukan rapat".
- Pakai info rapat dan konteks tambahan dari pengguna bila ada. Jangan mengarang konteks organisasi yang tidak disebut.
- Bagian yang tidak relevan untuk jenis rekaman itu (misalnya Keputusan atau Action Items pada narasi video) tetap ditulis, isinya "Tidak ada".

Aturan umum:
- Tulis dalam bahasa yang sama dengan transkrip (umumnya Bahasa Indonesia baku, ringkas).
- Jangan mengarang. Kalau tenggat atau angka tidak disebut, tulis "Tidak disebutkan".
- Transkrip bisa berisi salah dengar. Tafsirkan sesuai konteks. Istilah yang ragu, tandai dengan (?).
- Sertakan timestamp [HH:MM:SS] untuk poin, keputusan, dan action item bila bisa dilacak.
- Teks berisi token seperti ‹REKENING_1›, ‹NIK_1›, ‹NAMA_1›. Itu data yang disamarkan. Salin token apa adanya, jangan diubah, ditebak, atau dijelaskan.
- Baris "(segmen rahasia, tidak dikirim)" berarti isinya sengaja ditahan. Jangan menebak isinya.

Label pembicara:
- Baris "[HH:MM:SS] Nama: teks" berarti suara itu sudah ditandai sebagai peserta tersebut.
- Baris "[HH:MM:SS] (Belum ditandai): teks" berarti pembicaranya belum ditandai. Jangan menebak namanya dari konteks, misalnya dari sapaan di segmen sebelumnya.
- Baris tanpa label berarti daftar peserta tidak diisi dan tidak ada penanda sama sekali.

Bagian Peserta:
- Kalau ada daftar peserta, buat bagian "## Peserta" berupa tabel | Nama | Jabatan/Unit | Segmen | dari daftar (jumlah segmen sudah diberikan). Kalau ada segmen belum ditandai, tambahkan baris "| ? Belum ditandai | – | <jumlah> |". Nama yang disebut dalam percakapan sebagai peserta tetapi tidak ada di daftar, tulis di bawah tabel dengan judul tebal "Disebut dalam percakapan, belum ada di daftar peserta:" beserta timestamp.
- Kalau daftar peserta tidak diisi, buat bagian "## Peserta yang Disebut" (format lama): hanya nama yang terucap dalam percakapan, beserta konteks singkat dan timestamp, diawali catatan miring bahwa nama diambil dari isi percakapan, bukan dari suara.
- Orang yang hanya dibicarakan (klien, pihak luar, tokoh yang dibahas) tidak dimasukkan ke bagian Peserta.

Atribusi dan PIC (cek dari atas, pakai sumber pertama yang ada):
1. Ditunjuk dengan nama dalam percakapan ("Pak Andi, tolong ..."): PIC = nama itu. Dasar PIC: "◆ Ditunjuk dengan nama [HH:MM:SS]".
2. Menyanggupi sendiri dan suaranya ditandai: PIC = nama dari label. Dasar PIC: "✓ Menyanggupi, suara ditandai [HH:MM:SS]".
3. Menyebut unit, bukan orang ("biar tim produk yang susun"): PIC = unit, plus nama dalam kurung bila suaranya ditandai. Dasar PIC: "◆ Unit disebut [HH:MM:SS]" atau "✓ Menyanggupi untuk unit, suara ditandai [HH:MM:SS]".
4. Menyanggupi sendiri tetapi suaranya belum ditandai: PIC = "? Belum ditandai · HH:MM:SS". Dasar PIC: "? Menyanggupi, suara belum ditandai [HH:MM:SS]".
5. Forum menyatakan belum ada penanggung jawab: PIC = "Belum ditentukan".
6. Tidak ada informasi sama sekali: PIC = "Tidak disebutkan".
- Untuk poin dan keputusan: pakai nama bila suaranya ditandai; kalau belum, pakai unit yang disebut ("Perwakilan IT") atau "pembicara yang belum ditandai", atau "pimpinan rapat". Jangan pernah menyimpulkan nama dari suara yang belum ditandai.
- Kalau ada action item dengan PIC "? Belum ditandai", tambahkan butir di Isu Terbuka: PIC action item No X belum pasti karena pembicaranya belum ditandai; sebut timestamp-nya.

Gunakan format Markdown persis seperti ini (tanpa teks lain sebelum judul):

# <Judul yang disimpulkan dari isi>

## Ringkasan Eksekutif
<3-5 kalimat>

## Peserta
<tabel atau "## Peserta yang Disebut" sesuai aturan di atas>

## Poin Pembahasan
1. **<Topik>** [HH:MM:SS–HH:MM:SS]. <isi>
2. **<Topik>** [HH:MM:SS–HH:MM:SS]. <isi>

## Keputusan
1. ...

## Action Items
| No | Tugas | PIC | Tenggat | Dasar PIC |
|---|---|---|---|---|
| 1 | ... | ... | ... | ... |

## Isu Terbuka dan Risiko
- ...

## Catatan Lain
- ...
"""


def summarize(transcript: str, api_key: str, model: str = CLAUDE_MODEL, context: str = "",
              header: str = "") -> str:
    user = ""
    if header.strip():
        user += f"<info_rapat>\n{header.strip()}\n</info_rapat>\n\n"
    user += f"<transkrip>\n{transcript}\n</transkrip>"
    if context.strip():
        user += f"\n\nKonteks tambahan dari pengguna: {context.strip()}"
    return ai_text(SUMMARY_SYSTEM, user, api_key, model)


def test_api_key(api_key: str, model: str = CLAUDE_MODEL, provider: str | None = None,
                 base_url: str | None = None) -> None:
    """Raise if the provider rejects the key or cannot be reached. Sends no meeting data.
    Goes through the same path as a summary (same URL, model and streaming)."""
    try:
        ai_text("Jawab dengan satu kata.", "ok", api_key, model, max_tokens=200, provider=provider,
                base_url=base_url)
    except AIError as exc:
        if exc.kind != "empty":     # reasoning models may spend a tiny budget thinking; the server works
            raise


# --------------------------------------------------------------------------- export

_INLINE = re.compile(r"(\*\*.+?\*\*(?!\*)|`[^`]+`|(?<!\w)_[^_]+_(?!\w)|(?<![*\w])\*[^*\s][^*]*\*(?!\*))")


def _add_inline(paragraph, text: str) -> None:
    for part in _INLINE.split(text):
        if not part:
            continue
        if len(part) > 4 and part.startswith("**") and part.endswith("**"):
            paragraph.add_run(re.sub(r"\*([^*]+)\*", r"\1", part[2:-2])).bold = True
        elif part.startswith("`") and part.endswith("`"):
            paragraph.add_run(part[1:-1]).font.name = "Menlo"
        elif len(part) > 2 and part[0] in "_*" and part[-1] == part[0]:
            paragraph.add_run(part[1:-1]).italic = True
        else:
            paragraph.add_run(part)


def markdown_to_docx(md: str, path: Path) -> None:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)

    lines = md.splitlines()
    i = 0
    number = None
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped or re.fullmatch(r"-{3,}", stripped):
            i += 1
            continue
        num = re.match(r"^(\d+)[.)]\s+", stripped)
        if not num:
            number = None
        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                cols = max(len(r) for r in rows)
                table = doc.add_table(rows=len(rows), cols=cols)
                table.style = "Table Grid"
                for r, cells in enumerate(rows):
                    for c in range(cols):
                        cell_p = table.cell(r, c).paragraphs[0]
                        _add_inline(cell_p, cells[c] if c < len(cells) else "")
                        if r == 0:
                            for run in cell_p.runs:
                                run.bold = True
                doc.add_paragraph()
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", stripped)
        if m:
            doc.add_heading(m.group(2).strip(), level=min(len(m.group(1)) - 1, 3) if len(m.group(1)) > 1 else 0)
        elif re.match(r"^[-*]\s+", stripped):
            indent = (len(line) - len(line.lstrip())) // 2
            style = "List Bullet 2" if indent else "List Bullet"
            _add_inline(doc.add_paragraph(style=style), re.sub(r"^[-*]\s+", "", stripped))
        elif num:
            # NOTE: Word's "List Number" style shares one counter for the whole file, so write the number as text
            number = int(num.group(1)) if number is None else number
            para = doc.add_paragraph()
            para.paragraph_format.left_indent = Pt(18)
            para.paragraph_format.first_line_indent = Pt(-18)
            para.add_run(f"{number}.\t")
            _add_inline(para, stripped[num.end():])
            number += 1
        else:
            _add_inline(doc.add_paragraph(), stripped)
        i += 1
    doc.save(str(path))


FORBIDDEN_TITLE = re.compile(r"[/:\\]")
TITLE_MAX = 80


def safe_title(title: str) -> str:
    """Title as it may appear in a Finder folder name: no / : \\, no leading dot."""
    t = FORBIDDEN_TITLE.sub("-", str(title or ""))
    t = re.sub(r"[\x00-\x1f]", "", t)
    t = re.sub(r"\s+", " ", t).strip().lstrip(".").strip()
    return t[:TITLE_MAX].strip() or "Rapat"


def title_problem(title: str) -> str | None:
    """Validation message for a title typed by the user, or None when it is fine."""
    t = str(title or "").strip()
    if not t:
        return "Judul tidak boleh kosong."
    bad = FORBIDDEN_TITLE.search(t)
    if bad:
        return f"Karakter {bad.group(0)} tidak bisa dipakai di judul karena dilarang di nama folder Mac."
    if len(t) > TITLE_MAX:
        return f"Judul maksimal {TITLE_MAX} karakter."
    return None


_REC_NAME = re.compile(r"(20\d{2})(\d{2})(\d{2})[ _-]?(\d{2})(\d{2})(\d{2})")


def recording_time(path: Path) -> dt.datetime:
    """When the meeting was recorded: from a Voice Memos style name (20261105 134717),
    else the file's creation time, else its modification time."""
    m = _REC_NAME.search(Path(path).stem)
    if m:
        try:
            return dt.datetime(*(int(x) for x in m.groups()))
        except ValueError:
            pass
    try:
        st = Path(path).stat()
        ts = getattr(st, "st_birthtime", None) or st.st_mtime
        return dt.datetime.fromtimestamp(ts).replace(microsecond=0)
    except OSError:
        return dt.datetime.now().replace(microsecond=0)


def folder_name(title: str, when: dt.datetime) -> str:
    return f"{when:%Y-%m-%d %H%M} - {safe_title(title)}"


def free_folder(root: Path, base: str, keep: Path | None = None) -> Path:
    folder, n = root / base, 2
    while folder.exists() and folder != keep:
        folder, n = root / f"{base} ({n})", n + 1
    return folder


def migrate_output_root(old: Path | None = None, new: Path | None = None) -> list[str]:
    """Move the results folder from "Meeting Notes" to "Meeting Report" (v1.3).

    Same disk, so this is a rename: nothing is copied or deleted. When the new
    folder already exists, each meeting folder is moved into it unless a folder
    with that name is already there (that one stays in the old folder).
    Absolute paths inside meeting.json that pointed into the old folder are
    rewritten. Returns what was moved."""
    old = Path(old or OLD_OUTPUT_ROOT)
    new = Path(new or OUTPUT_ROOT)
    if not old.is_dir() or old.resolve() == new.resolve():
        return []
    moved = []
    if not new.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        moved = [p.name for p in new.iterdir()]
    else:
        for p in sorted(old.iterdir()):
            if p.name.startswith(".") or (new / p.name).exists():
                continue
            try:
                p.rename(new / p.name)
                moved.append(p.name)
            except OSError:
                continue
    prefix = str(old) + os.sep
    for name in moved:
        mf = new / name / "meeting.json"
        if not mf.is_file():
            continue
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
            src = m.get("source")
            if isinstance(src, str) and src.startswith(prefix):
                m["source"] = str(new) + os.sep + src[len(prefix):]
                tmp = mf.with_suffix(".tmp")
                tmp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp, mf)
        except (OSError, ValueError):
            continue
    return moved


def make_output_dir(title: str, root: Path | None = None, when: dt.datetime | None = None) -> Path:
    root = root or OUTPUT_ROOT
    folder = free_folder(root, folder_name(title, when or dt.datetime.now()))
    folder.mkdir(parents=True)
    return folder
