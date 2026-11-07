"""Meeting Notes pipeline: load audio, remove silence, transcribe, summarize, export.

Kept free of GUI code so it can be tested on its own. mlx_whisper and anthropic
are imported lazily inside the functions that need them.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SR = 16000            # Whisper works at 16 kHz mono
FRAME = 0.03          # energy analysis window, seconds
CHUNK_SEC = 600       # transcribe in ~10 minute chunks so the UI can show progress

WHISPER_REPO = "mlx-community/whisper-large-v3-turbo"
CLAUDE_MODEL = "claude-sonnet-5-5"
KEYCHAIN_SERVICE = "MeetingNotes"
KEYCHAIN_ACCOUNT = "anthropic-api-key"

SUPPORT_DIR = Path(os.environ.get("MN_SUPPORT_DIR")
                   or Path.home() / "Library" / "Application Support" / "MeetingNotes")
OUTPUT_ROOT = Path(os.environ.get("MN_OUTPUT_DIR") or Path.home() / "Documents" / "Meeting Notes")
VOICE_MEMOS_DIR = (Path.home() / "Library" / "Group Containers"
                   / "group.com.apple.VoiceMemos.shared" / "Recordings")


# --------------------------------------------------------------------------- config

DEFAULT_CONFIG = {
    "claude_model": CLAUDE_MODEL,
    "whisper_repo": WHISPER_REPO,
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

def load_audio(path: str) -> np.ndarray:
    """Decode any ffmpeg-readable file to 16 kHz mono float32."""
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
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


def chunk_bounds(clean: CleanResult, chunk_sec: float = CHUNK_SEC) -> list[tuple[int, int]]:
    """Split the cleaned audio into ~chunk_sec pieces, cutting only where silence was removed."""
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

LOW_WORD_PROB = 0.45      # words below this probability are flagged for review


class Cancelled(Exception):
    """Raised when the user cancels a running transcription."""


def whisper_prompt(vocabulary: str = "", participants: list[str] | None = None) -> str | None:
    parts = []
    if vocabulary.strip():
        parts.append(f"Istilah: {vocabulary.strip()}.")
    names = [p for p in (participants or []) if p.strip()]
    if names:
        parts.append(f"Peserta: {', '.join(names)}.")
    return " ".join(parts) if parts else None


def transcribe_chunk(audio: np.ndarray, language: str | None, prompt: str | None,
                     repo: str = WHISPER_REPO, word_confidence: bool = True) -> list[dict]:
    """Transcribe one chunk. Times are relative to the chunk start (clean timeline)."""
    import mlx_whisper  # Apple Silicon only

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
        if not text:
            continue
        # standard Whisper hallucination guard
        if s.get("no_speech_prob", 0) > 0.6 and s.get("avg_logprob", 0) < -1.0:
            continue
        low = []
        for w in s.get("words") or []:
            word = str(w.get("word", "")).strip()
            if word and float(w.get("probability", 1.0)) < LOW_WORD_PROB:
                low.append(word.strip(".,?!;:"))
        out.append({
            "start": float(s["start"]),
            "end": float(s["end"]),
            "text": text,
            "avg_logprob": round(float(s.get("avg_logprob", 0.0)), 3),
            "low_words": [w for w in low if w],
        })
    return out


def place_chunk(clean: CleanResult, chunk_start_sample: int, segs: list[dict]) -> list[dict]:
    """Map chunk-relative segment times back to the original recording."""
    base = chunk_start_sample / SR
    placed = []
    for s in segs:
        placed.append({**s, "start": round(clean.to_original(base + s["start"]), 2),
                       "end": round(clean.to_original(base + s["end"]), 2)})
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
    recording, language, version, tagging status, Claude suggestions and the
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
        L.append(f"Saran Claude : ✦ Disarankan Claude, {fmt_date_short(dt.datetime.fromisoformat(cs['at']))}"
                 f" ({cs.get('accepted', 0)} diterima, {cs.get('rejected', 0)} ditolak)")
    else:
        L.append("Saran Claude : Tidak dijalankan")
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
            text = s["text"] + "  (rahasia, tidak dikirim ke Claude)"
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


# --------------------------------------------------------------------------- API key (macOS Keychain)

def get_api_key() -> str | None:
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env:
        return env
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE,
                              "-a", KEYCHAIN_ACCOUNT, "-w"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def delete_api_key() -> None:
    subprocess.run(["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE,
                    "-a", KEYCHAIN_ACCOUNT], capture_output=True)


def set_api_key(key: str) -> None:
    subprocess.run(["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE,
                    "-a", KEYCHAIN_ACCOUNT, "-w", key.strip()],
                   capture_output=True, check=True)


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


def claude_text(system: str, user: str, api_key: str, model: str = CLAUDE_MODEL,
                max_tokens: int = 8000) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def summarize(transcript: str, api_key: str, model: str = CLAUDE_MODEL, context: str = "",
              header: str = "") -> str:
    user = ""
    if header.strip():
        user += f"<info_rapat>\n{header.strip()}\n</info_rapat>\n\n"
    user += f"<transkrip>\n{transcript}\n</transkrip>"
    if context.strip():
        user += f"\n\nKonteks tambahan dari pengguna: {context.strip()}"
    return claude_text(SUMMARY_SYSTEM, user, api_key, model)


def test_api_key(api_key: str, model: str = CLAUDE_MODEL) -> None:
    """Raise if the key is rejected. Sends no meeting data."""
    claude_text("Jawab dengan satu kata.", "ok", api_key, model, max_tokens=5)


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


def make_output_dir(source: Path, root: Path | None = None, when: dt.datetime | None = None) -> Path:
    stem = re.sub(r"[^\w\- ]+", "", source.stem).strip() or "Rapat"
    base = f"{(when or dt.datetime.now()):%Y-%m-%d %H%M} - {stem[:60]}"
    root = root or OUTPUT_ROOT
    folder, n = root / base, 2
    while folder.exists():
        folder, n = root / f"{base} ({n})", n + 1
    folder.mkdir(parents=True)
    return folder
