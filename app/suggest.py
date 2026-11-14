"""F14: word suggestions for the transcript editor.

Local suggestions run on this Mac and are the default. AI suggestions (any
provider from Pengaturan) are optional, go through the F15 filter, and are only proposals: the user accepts
or rejects each one. Nothing here edits the transcript by itself.
"""
from __future__ import annotations

import difflib
import json
import re

import core
import filters
from i18n import tr

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
                                "reason": tr("reason_similar")})
        # 2. the same word twice in a row ("yang yang")
        for m in re.finditer(r"(?<!\w)(\w{2,})\s+\1(?!\w)", text, re.I):
            if m.group(0).lower() not in seen:
                seen.add(m.group(0).lower())
                out.append({"seg_id": s["id"], "from": m.group(0), "to": m.group(1), "kind": "local",
                            "reason": tr("reason_repeat")})
        # 3. words Whisper was unsure about: no replacement, so the editor shows these
        #    only as "Tandai kata ragu" highlights, never as a suggestion card
        for w in (low_words or {}).get(s["id"], []):
            wl = w.lower()
            if wl in seen or wl in lower or not re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", text):
                continue
            seen.add(wl)
            out.append({"seg_id": s["id"], "from": w, "to": None, "kind": "local",
                        "reason": tr("reason_low_conf")})
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


SUGGEST_MAX_TOKENS = 16000   # NOTE: a long transcript with many fixes overflows 4000 and cuts the JSON


class SuggestReplyError(RuntimeError):
    """The AI answered, but no suggestion list could be read from the answer."""

    def __init__(self, msg: str, raw: str = ""):
        super().__init__(msg)
        self.raw = raw


def parse_claude(text: str) -> tuple[list[dict], bool]:
    """Read the JSON array of suggestions. Returns (items, complete).

    An answer cut off by the token limit has no closing "]": every object that is
    already whole is still kept, and complete is False. No "[" at all, or an array
    that cannot be read, raises SuggestReplyError, so the user sees an error and not
    "0 suggestions"."""
    text = text or ""
    dec = json.JSONDecoder()
    for m in re.finditer(r"\[", text):
        try:
            data, _ = dec.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(data, list) and all(isinstance(d, dict) for d in data):
            return data, True
    m = re.search(r"\[\s*\{", text)
    if not m:
        raise SuggestReplyError(tr("sug_reply_unreadable"), text)
    items, i = [], m.start() + 1
    while True:
        j = text.find("{", i)
        if j < 0:
            break
        try:
            obj, i = dec.raw_decode(text, j)
        except ValueError:
            break
        if isinstance(obj, dict):
            items.append(obj)
    if not items and "]" in text[m.start():]:
        raise SuggestReplyError(tr("sug_reply_unreadable"), text)
    return items, False


def claude_suggestions(meta: dict, version: dict, cfg: dict, api_key: str, model: str,
                       vocabulary: str = "", call=core.ai_text, send: dict | None = None,
                       on_reply=None) -> tuple[list[dict], dict, dict]:
    """Ask the AI provider for word fixes.

    Returns (suggestions, send info for the send log, reply info). Reply info keeps the
    raw answer, whether it was complete, and how many items did not match the transcript."""
    send = send or filters.build_send(meta, version, cfg, with_ids=True)
    user = f"<info_rapat>\n{send['header']}\n</info_rapat>\n\n"
    if vocabulary.strip():
        user += f"<istilah>\n{filters.Redactor(cfg.get('redact'), filters.split_words(cfg.get('sensitive_words', ''))).apply(vocabulary)}\n</istilah>\n\n"
    user += f"<transkrip>\n{send['transcript']}\n</transkrip>"
    raw = call(CLAUDE_SYSTEM, user, api_key, model, SUGGEST_MAX_TOKENS)
    if on_reply:
        on_reply()
    reply = {"raw": raw, "complete": True, "received": 0, "dropped": 0}
    parsed, reply["complete"] = parse_claude(raw)
    if not parsed and not reply["complete"]:
        raise SuggestReplyError(tr("sug_reply_cut_empty"), raw)
    reply["received"] = len(parsed)
    by_id = {s["id"]: s for s in version.get("segments", [])}
    out = []
    for d in parsed:
        sid = str(d.get("id", ""))
        seg = by_id.get(sid)
        if not seg or seg.get("secret"):
            reply["dropped"] += 1
            continue
        frm = filters.restore(str(d.get("from", "")), send["tokens"])
        to = filters.restore(str(d.get("to", "")), send["tokens"])
        if not frm or frm == to or frm not in seg["text"] or filters.TOKEN_RE.search(to):
            reply["dropped"] += 1
            continue
        out.append({"seg_id": sid, "from": frm, "to": to, "kind": "claude",
                    "reason": str(d.get("reason", ""))[:200]})
    return out, send, reply
