"""F14: word suggestions for the transcript editor.

Local suggestions run on this Mac and are the default. Claude suggestions are
optional, go through the F15 filter, and are only proposals: the user accepts
or rejects each one. Nothing here edits the transcript by itself.
"""
from __future__ import annotations

import difflib
import json
import re

import core
import filters

WORD = re.compile(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'-]*")
HONORIFICS = {"pak", "bu", "ibu", "bapak", "mas", "mbak", "bang", "kak"}


def terms(vocabulary: str, participants: list[dict]) -> list[str]:
    out: list[str] = []
    for t in re.split(r"[,\n;]", vocabulary or ""):
        t = t.strip()
        if len(t) >= 3:
            out.append(t)
    for p in participants or []:
        name = (p.get("name") or "").strip()
        words = [w for w in name.split() if w.lower().strip(".") not in HONORIFICS]
        if words:
            out.append(" ".join(words))
            if len(words) > 1:
                out.extend(w for w in words if len(w) >= 4)
    seen, uniq = set(), []
    for t in out:
        if t.lower() not in seen:
            seen.add(t.lower())
            uniq.append(t)
    return uniq


def _ngrams(text: str, n: int):
    ws = list(WORD.finditer(text))
    for i in range(len(ws) - n + 1):
        a, b = ws[i].start(), ws[i + n - 1].end()
        yield text[a:b]


def local_suggestions(segments: list[dict], participants: list[dict], vocabulary: str,
                      low_words: dict[str, list[str]] | None = None, cutoff: float = 0.8) -> list[dict]:
    """Return [{seg_id, from, to, reason, kind}] for the editor's suggestion rows."""
    vocab = terms(vocabulary, participants)
    lower = {t.lower() for t in vocab}
    out: list[dict] = []
    for s in segments:
        text = s.get("text") or ""
        if s.get("secret"):
            continue
        seen: set[str] = set()
        # 1. near-miss of a known term or participant name
        for t in vocab:
            n = len(t.split())
            for g in _ngrams(text, n):
                gl = g.lower()
                if gl in lower or gl in seen or len(g) < 4:
                    continue
                r = difflib.SequenceMatcher(None, gl, t.lower()).ratio()
                if r >= cutoff and gl[0] == t.lower()[0]:
                    seen.add(gl)
                    out.append({"seg_id": s["id"], "from": g, "to": t, "kind": "local",
                                "reason": "Mirip istilah atau nama peserta"})
        # 2. the same word twice in a row ("yang yang")
        for m in re.finditer(r"(?<!\w)(\w{2,})\s+\1(?!\w)", text, re.I):
            if m.group(0).lower() not in seen:
                seen.add(m.group(0).lower())
                out.append({"seg_id": s["id"], "from": m.group(0), "to": m.group(1), "kind": "local",
                            "reason": "Kata berulang"})
        # 3. words Whisper was unsure about: a hint without a replacement
        for w in (low_words or {}).get(s["id"], []):
            wl = w.lower()
            if wl in seen or wl in lower or not re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", text):
                continue
            seen.add(wl)
            out.append({"seg_id": s["id"], "from": w, "to": None, "kind": "local",
                        "reason": "Whisper ragu dengan kata ini, coba dengarkan"})
    return out


CLAUDE_SYSTEM = """Kamu membantu memeriksa transkrip hasil speech-to-text otomatis (Whisper).
Tugasmu hanya menunjuk kata atau frasa yang kemungkinan besar salah dengar, lalu mengusulkan perbaikannya.

Aturan:
- Jangan menulis ulang kalimat, jangan memperbaiki gaya bahasa, jangan merangkum.
- Usulkan hanya bila yakin itu salah dengar (misalnya istilah teknis, nama produk, nama orang yang ada di daftar atau di daftar istilah).
- Teks berisi token seperti ‹REKENING_1› atau ‹NAMA_1›. Itu data yang disamarkan. Jangan mengubah, menebak, atau memasukkan token ke usulan.
- Baris "(segmen rahasia, tidak dikirim)" sengaja ditahan. Abaikan.
- "from" harus persis sama dengan potongan teks di segmen itu.

Jawab hanya dengan JSON array, tanpa teks lain:
[{"id": "s00012", "from": "kata salah", "to": "kata benar", "reason": "alasan singkat"}]
Kalau tidak ada yang perlu diusulkan, jawab [].
"""


def parse_claude(text: str) -> list[dict]:
    m = re.search(r"\[.*\]", text or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []
    return [d for d in data if isinstance(d, dict)]


def claude_suggestions(meta: dict, version: dict, cfg: dict, api_key: str, model: str,
                       vocabulary: str = "", call=core.claude_text) -> tuple[list[dict], dict]:
    """Ask Claude for word fixes. Returns (suggestions, send info for the send log)."""
    send = filters.build_send(meta, version, cfg, with_ids=True)
    user = f"<info_rapat>\n{send['header']}\n</info_rapat>\n\n"
    if vocabulary.strip():
        user += f"<istilah>\n{filters.Redactor(cfg.get('redact'), filters.split_words(cfg.get('sensitive_words', ''))).apply(vocabulary)}\n</istilah>\n\n"
    user += f"<transkrip>\n{send['transcript']}\n</transkrip>"
    raw = call(CLAUDE_SYSTEM, user, api_key, model, 4000)
    by_id = {s["id"]: s for s in version.get("segments", [])}
    out = []
    for d in parse_claude(raw):
        sid = str(d.get("id", ""))
        seg = by_id.get(sid)
        if not seg or seg.get("secret"):
            continue
        frm = filters.restore(str(d.get("from", "")), send["tokens"])
        to = filters.restore(str(d.get("to", "")), send["tokens"])
        if not frm or frm == to or frm not in seg["text"] or filters.TOKEN_RE.search(to):
            continue
        out.append({"seg_id": sid, "from": frm, "to": to, "kind": "claude",
                    "reason": str(d.get("reason", ""))[:200]})
    return out, send
