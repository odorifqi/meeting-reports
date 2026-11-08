"""Interactive Transcript (v1.6): word times for a saved transcript version, and the Silence removed audio time map."""
from __future__ import annotations

import bisect
import re
from difflib import SequenceMatcher

SR = 16000          # NOTE: same rate as core.SR; not imported, so this module stays free of numpy
_NORM = re.compile(r"[^\w]+", re.UNICODE)


def norm(token: str) -> str:
    """Comparable form of a word: lower case, punctuation removed ("Kamis," == "kamis")."""
    return _NORM.sub("", token.lower())


def tokens(text: str) -> list[str]:
    return str(text or "").split()


def _spread(toks: list[str], a: float, b: float) -> list[list[float]]:
    """Times for tokens laid out between a and b in proportion to their length."""
    if not toks:
        return []
    b = max(b, a)
    weights = [len(t) + 1 for t in toks]
    total = float(sum(weights))
    out, t = [], a
    for w in weights:
        d = (b - a) * w / total
        out.append([round(t, 2), round(t + d, 2)])
        t += d
    return out


def _assign(segments: list[dict], words: list) -> list[list]:
    """Put each Whisper word in the segment whose time span holds its midpoint."""
    order = sorted(range(len(segments)), key=lambda i: float(segments[i].get("start", 0)))
    starts = [float(segments[i].get("start", 0)) for i in order]
    buckets: list[list] = [[] for _ in segments]
    for w in words or []:
        try:
            mid = (float(w[0]) + float(w[1])) / 2
        except (TypeError, ValueError, IndexError):
            continue
        k = bisect.bisect_right(starts, mid + 0.05) - 1
        cands = [j for j in (k, k + 1) if 0 <= j < len(order)]
        best, dist = None, None
        for j in cands:
            s = segments[order[j]]
            a, b = float(s.get("start", 0)), float(s.get("end", 0))
            d = 0.0 if a - 0.05 <= mid <= b + 0.05 else min(abs(mid - a), abs(mid - b))
            if dist is None or d < dist:
                best, dist = order[j], d
        if best is not None and dist <= 0.6:
            buckets[best].append(w)
    return buckets


def align_segment(seg: dict, words: list) -> tuple[list[list[float]], bool]:
    """Times for the tokens of seg["text"]; returns (times, estimated)."""
    toks = tokens(seg.get("text"))
    a, b = float(seg.get("start", 0)), float(seg.get("end", 0))
    if not toks:
        return [], False
    words = sorted(words or [], key=lambda w: float(w[0]))
    if not words:
        return _spread(toks, a, b), True
    sm = SequenceMatcher(None, [norm(t) for t in toks], [norm(str(w[2])) for w in words], autojunk=False)
    times: list[list[float] | None] = [None] * len(toks)
    matched = 0
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            w = words[blk.b + k]
            times[blk.a + k] = [round(float(w[0]), 2), round(max(float(w[0]), float(w[1])), 2)]
            matched += 1
    i = 0
    while i < len(toks):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(toks) and times[j] is None:
            j += 1
        lo = times[i - 1][1] if i > 0 else min(a, times[j][0] if j < len(toks) else a)
        hi = times[j][0] if j < len(toks) else max(b, lo)
        if hi <= lo:
            hi = lo + 0.05 * (j - i)
        for k, t in enumerate(_spread(toks[i:j], lo, hi)):
            times[i + k] = t
        i = j
    # NOTE: Whisper word times can overlap by a few ms
    for k in range(1, len(times)):
        if times[k][0] < times[k - 1][0]:
            times[k][0] = times[k - 1][0]
            times[k][1] = max(times[k][1], times[k][0])
    return times, matched < len(toks) / 2


def align(segments: list[dict], words: list | None) -> list[dict]:
    """Segments of one version with per-token times for the Audio tab."""
    buckets = _assign(segments, words) if words else [[] for _ in segments]
    out = []
    for s, ws in zip(segments, buckets):
        times, est = align_segment(s, ws)
        row = {"id": s.get("id"), "start": s.get("start"), "end": s.get("end"), "text": s.get("text") or "",
               "speaker_id": s.get("speaker_id"), "secret": bool(s.get("secret")), "w": times, "est": est}
        out.append(row)
    return out


def rows_from_regions(regions: list, total: float | None = None) -> list[list[float]]:
    """The mapping core.clean_audio builds from the kept spans (same sample rounding)."""
    rows, c = [], 0.0
    limit = int(total * SR) if total else None
    for a, b in regions or []:
        x, y = int(float(a) * SR), int(float(b) * SR)
        if limit is not None:
            y = min(y, limit)
        if y <= x:
            continue
        d = (y - x) / SR
        rows.append([round(c, 3), round(x / SR, 3), round(d, 3)])
        c += d
    return rows


def clean_map(saved: dict | None, regions: dict | None, meta: dict, has_clean_file: bool) -> dict | None:
    """Time map for Silence removed.m4a, or None when the meeting has no such file."""
    if not has_clean_file:
        return None
    if saved and saved.get("rows"):
        return {"rows": saved["rows"], "clean_sec": saved.get("clean_sec"), "derived": False}
    settings = meta.get("settings") or {}
    if regions and regions.get("regions") and settings.get("remove_silence", True):
        rows = rows_from_regions(regions["regions"], regions.get("total"))
        if rows:
            r = rows[-1]
            return {"rows": rows, "clean_sec": round(r[0] + r[2], 3), "derived": True}
    return {"rows": [], "clean_sec": None, "derived": True}
