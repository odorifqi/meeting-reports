"""F15: local filter that runs before any text leaves the Mac.

Every send to an AI provider (summary or AI suggestions) goes through
`build_send`. Sensitive values are replaced by tokens such as ‹REKENING_1›,
segments marked Rahasia are withheld, and the token map stays on this Mac so
`restore` can put the real values back into the model's answer.
"""
from __future__ import annotations

import re

import core

CATEGORIES = {
    "rekening": "Nomor rekening",
    "nik": "NIK",
    "hp": "Nomor HP",
    "kartu": "Nomor kartu",
    "npwp": "NPWP",
    "email": "Email",
}
TOKEN_NAME = {"rekening": "REKENING", "nik": "NIK", "hp": "HP", "kartu": "KARTU",
              "npwp": "NPWP", "email": "EMAIL", "kata": "NAMA"}
SECRET_LINE = "(segmen rahasia, tidak dikirim)"
TOKEN_RE = re.compile(r"‹([A-Z]+)_(\d+)›")

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_NPWP = re.compile(r"(?<![\d.])\d{2}\.\d{3}\.\d{3}\.\d[-.]\d{3}\.\d{3}(?![\d])")
_HP = re.compile(r"(?<![\d+])(?:\+62|62|0)[\s-]?8\d{1,2}(?:[\s-]?\d){6,9}(?![\d])")
# digit runs with optional single spaces or dashes between groups
_DIGITS = re.compile(r"(?<!\d)(?<!\d[.,])\d(?:[ -]?\d){7,18}(?!\d|[.,]\d)")
_MONEY_BEFORE = re.compile(r"(?:rp\.?|idr|usd|\$)\s*$", re.I)
_MONEY_AFTER = re.compile(r"^\s*(?:rupiah|juta|miliar|milyar|ribu|triliun|persen|%)", re.I)
_NIK_HINT = re.compile(r"(?:nik|ktp|kependudukan)\W{0,12}$", re.I)
_NPWP_HINT = re.compile(r"npwp\W{0,12}$", re.I)
_CARD_HINT = re.compile(r"(?:kartu|card|cc|debit|kredit)\W{0,20}$", re.I)


def luhn(num: str) -> bool:
    total, alt = 0, False
    for ch in reversed(num):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _classify_digits(raw: str, before: str, after: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    n = len(digits)
    if _MONEY_BEFORE.search(before) or _MONEY_AFTER.search(after):
        return None
    if _NPWP_HINT.search(before) and n in (15, 16):
        return "npwp"
    if _NIK_HINT.search(before) and n == 16:
        return "nik"
    if 13 <= n <= 19 and luhn(digits) and (_CARD_HINT.search(before) or n in (15, 16)):
        if n == 16 and not _CARD_HINT.search(before) and digits[:2] in _NIK_PROV:
            return "nik"
        return "kartu"
    if n == 16:
        return "nik"
    if n == 15:
        return "npwp"
    if 8 <= n <= 16:
        return "rekening"
    return None


# first two NIK digits are a province code (11..94)
_NIK_PROV = {f"{i}" for i in (11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 31, 32, 33, 34, 35, 36,
                              51, 52, 53, 61, 62, 63, 64, 65, 71, 72, 73, 74, 75, 76, 81, 82,
                              91, 92, 93, 94)}


def split_words(text: str) -> list[str]:
    out = []
    for line in (text or "").replace(",", "\n").splitlines():
        w = line.strip()
        if len(w) >= 2:
            out.append(w)
    return out


class Redactor:
    """Holds the token map for one send so equal values get the same token."""

    def __init__(self, enabled: dict | None = None, words: list[str] | None = None):
        self.enabled = {k: True for k in CATEGORIES} if enabled is None else dict(enabled)
        self.words = sorted({w for w in (words or []) if w.strip()}, key=len, reverse=True)
        self.tokens: dict[str, str] = {}      # token -> original
        self._by_value: dict[tuple[str, str], str] = {}
        self.counts: dict[str, int] = {}

    def _token(self, cat: str, value: str) -> str:
        key = (cat, re.sub(r"\s+", "", value).lower() if cat != "kata" else value.lower())
        tok = self._by_value.get(key)
        if tok is None:
            n = sum(1 for k in self._by_value if k[0] == cat) + 1
            tok = f"‹{TOKEN_NAME[cat]}_{n}›"
            self._by_value[key] = tok
            self.tokens[tok] = value
        self.counts[cat] = self.counts.get(cat, 0) + 1
        return tok

    def apply(self, text: str) -> str:
        if not text:
            return text
        on = self.enabled
        if self.words:
            pat = re.compile(r"(?<!\w)(" + "|".join(re.escape(w) for w in self.words) + r")(?!\w)", re.I)
            text = pat.sub(lambda m: self._token("kata", m.group(0)), text)
        if on.get("email"):
            text = _EMAIL.sub(lambda m: self._token("email", m.group(0)), text)
        if on.get("npwp"):
            text = _NPWP.sub(lambda m: self._token("npwp", m.group(0)), text)
        if on.get("hp"):
            text = _HP.sub(lambda m: self._token("hp", m.group(0)), text)

        def digits(m: re.Match) -> str:
            raw = m.group(0)
            cat = _classify_digits(raw, m.string[max(0, m.start() - 24):m.start()], m.string[m.end():m.end() + 12])
            if cat is None or not on.get(cat):
                return raw
            return self._token(cat, raw)
        return _DIGITS.sub(digits, text)

    @property
    def masked(self) -> int:
        return sum(self.counts.values())


def restore(text: str, tokens: dict[str, str]) -> str:
    if not text or not tokens:
        return text
    return TOKEN_RE.sub(lambda m: tokens.get(m.group(0), m.group(0)), text)


def segment_lines(segments: list[dict], participants: list[dict], red: Redactor,
                  with_ids: bool = False) -> tuple[list[str], int]:
    names = {p["id"]: p["name"] for p in participants}
    lines, withheld = [], 0
    for s in segments:
        ts = f"[{core.fmt_ts(s['start'])}]"
        if with_ids:
            ts = f"[{s['id']}] {ts}"
        if s.get("secret"):
            withheld += 1
            body = SECRET_LINE
        else:
            body = red.apply(s["text"])
        if not participants:
            lines.append(f"{ts} {body}")
        elif s.get("speaker_id") in names:
            lines.append(f"{ts} {red.apply(names[s['speaker_id']])}: {body}")
        else:
            lines.append(f"{ts} (Belum ditandai): {body}")
    return lines, withheld


def header_text(meta: dict, segments: list[dict], participants: list[dict], red: Redactor) -> str:
    import datetime as dt
    L = [f"Judul: {red.apply(meta.get('title') or '')}"]
    if meta.get("created"):
        L.append(f"Tanggal: {core.fmt_date_id(dt.datetime.fromisoformat(meta['created']))}")
    if meta.get("duration_sec"):
        L.append(f"Durasi rekaman: {core.fmt_dur(meta['duration_sec'])}")
    total = len(segments)
    if participants:
        per: dict[str, int] = {}
        for s in segments:
            per[s.get("speaker_id")] = per.get(s.get("speaker_id"), 0) + 1
        L.append(f"Daftar peserta ({len(participants)}):")
        for p in participants:
            role = f" | {red.apply(p['role'])}" if p.get("role") else " | –"
            L.append(f"- {red.apply(p['name'])}{role} | {per.get(p['id'], 0)} segmen")
        tagged = sum(per.get(p["id"], 0) for p in participants)
        L.append(f"Segmen ditandai: {tagged} dari {total}; belum ditandai: {total - tagged}")
    else:
        L.append("Daftar peserta: tidak diisi (tidak ada penanda suara)")
    return "\n".join(L)


def build_send(meta: dict, version: dict, cfg: dict, context: str = "", with_ids: bool = False) -> dict:
    """Everything that would be sent, already filtered, plus what the preview shows."""
    red = Redactor(cfg.get("redact"), split_words(cfg.get("sensitive_words", "")))
    segs = version.get("segments", [])
    parts = version.get("participants") or []
    header = header_text(meta, segs, parts, red)
    lines, withheld = segment_lines(segs, parts, red, with_ids)
    ctx = red.apply(context.strip()) if context else ""
    transcript = "\n".join(lines)
    words = len(re.findall(r"\S+", header + " " + transcript + " " + ctx))
    return {
        "header": header,
        "transcript": transcript,
        "context": ctx,
        "tokens": red.tokens,
        "counts": dict(red.counts),
        "masked": red.masked,
        "withheld": withheld,
        "words": words,
    }


def public_preview(send: dict) -> dict:
    """What the UI may show: the filtered text, counts, never the token map."""
    return {k: send[k] for k in ("header", "transcript", "context", "counts", "masked", "withheld", "words")}
