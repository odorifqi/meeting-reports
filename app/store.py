"""Meeting storage: one folder per meeting under ~/Documents/Meeting Notes.

The folder stays the source of truth (no database). Next to the files a user
already knows (Transkrip.txt, Ringkasan.md/.docx, Audio bersih.m4a) v1.1 keeps:

    meeting.json            metadata, status, participants, summary list, send log
    draft.json              editor autosave (never creates a version)
    versions/rev-0.json     Whisper output, never changed (also Transkrip asli.txt)
    versions/rev-N.json     every save that really changed the content
    summaries/sum-N.md      every summary version, raw (tokens already restored)

v1 folders (only Transkrip.txt and maybe Ringkasan.md) are migrated on the first
scan by adding meeting.json and versions/; v1 files are not modified.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

import core

META = "meeting.json"
DRAFT = "draft.json"
VERS = "versions"
SUMS = "summaries"

STATUSES = ("queued", "transcribing", "awaiting_review", "awaiting_confirmation",
            "summarizing", "done", "transcript_only", "failed")


def now_iso() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def _write_json(path: Path, data) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def canon_segments(segments: list[dict]) -> list[dict]:
    """The part of a segment that counts as content (what a version stores)."""
    out = []
    for s in segments:
        out.append({
            "id": str(s["id"]),
            "start": round(float(s["start"]), 2),
            "end": round(float(s["end"]), 2),
            "text": str(s.get("text", "")).strip(),
            "speaker_id": s.get("speaker_id") or None,
            "secret": bool(s.get("secret")),
        })
    return out


def canon_participants(parts: list[dict]) -> list[dict]:
    return [{"id": str(p["id"]), "name": str(p.get("name", "")).strip(),
             "role": str(p.get("role") or "").strip()} for p in parts]


def content_hash(segments: list[dict], participants: list[dict]) -> str:
    blob = json.dumps({"s": canon_segments(segments), "p": canon_participants(participants)},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def describe_changes(old: dict, new: dict) -> dict:
    """Counts used in the 'Perbarui ringkasan?' dialog and the stale banner."""
    op = {p["id"]: p for p in old.get("participants", [])}
    np_ = {p["id"]: p for p in new.get("participants", [])}
    added = [p["name"] for i, p in np_.items() if i not in op]
    renamed = [p["name"] for i, p in np_.items() if i in op and op[i]["name"] != p["name"]]
    removed = [p["name"] for i, p in op.items() if i not in np_]
    os_ = {s["id"]: s for s in old.get("segments", [])}
    ns = {s["id"]: s for s in new.get("segments", [])}
    edited = sum(1 for i, s in ns.items() if i in os_ and os_[i]["text"] != s["text"])
    tagged = sum(1 for i, s in ns.items()
                 if i in os_ and (os_[i].get("speaker_id") or None) != (s.get("speaker_id") or None))
    secret = sum(1 for i, s in ns.items() if i in os_ and bool(os_[i].get("secret")) != bool(s.get("secret")))
    merged = sum(1 for i in os_ if i not in ns) + sum(1 for i in ns if i not in os_)
    return {"added": added, "renamed": renamed, "removed": removed, "edited": edited,
            "tagged": tagged, "secret": secret, "merged": merged}


def change_text(c: dict) -> str:
    out = []
    if c.get("added"):
        out.append(f"{len(c['added'])} peserta ditambah")
    if c.get("renamed"):
        out.append(f"{len(c['renamed'])} nama peserta diubah")
    if c.get("removed"):
        out.append(f"{len(c['removed'])} peserta dihapus")
    if c.get("tagged"):
        out.append(f"{c['tagged']} segmen ditandai")
    if c.get("edited"):
        out.append(f"{c['edited']} segmen diedit")
    if c.get("merged"):
        out.append(f"{c['merged']} segmen digabung atau dipecah")
    if c.get("secret"):
        out.append(f"{c['secret']} tanda rahasia diubah")
    return ", ".join(out)


# --------------------------------------------------------------------------- v1 import

_V1_LINE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\]\s?(.*)$")
_V1_DIR = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2})(\d{2}) - (.+)$")


def parse_v1_transcript(text: str) -> tuple[dict, list[dict]]:
    info: dict = {}
    segs: list[dict] = []
    for line in text.splitlines():
        m = _V1_LINE.match(line.strip())
        if m:
            h, mi, s, body = m.groups()
            segs.append({"start": int(h) * 3600 + int(mi) * 60 + int(s), "text": body.strip()})
            continue
        if line.startswith("Transkrip:"):
            info["title"] = line.split(":", 1)[1].strip()
        elif line.startswith("Durasi rekaman:"):
            m2 = re.search(r"(\d{2}):(\d{2}):(\d{2})", line)
            if m2:
                info["duration_sec"] = int(m2[1]) * 3600 + int(m2[2]) * 60 + int(m2[3])
            m3 = re.search(r"dibuang:\s*(\d{2}):(\d{2}):(\d{2})", line)
            if m3 and info.get("duration_sec"):
                info["clean_sec"] = info["duration_sec"] - (int(m3[1]) * 3600 + int(m3[2]) * 60 + int(m3[3]))
    out = []
    for i, s in enumerate(segs):
        end = segs[i + 1]["start"] if i + 1 < len(segs) else s["start"] + 5
        out.append({"id": f"s{i + 1:05d}", "start": float(s["start"]), "end": float(max(end, s["start"])),
                    "text": s["text"], "speaker_id": None, "secret": False})
    return info, out


# --------------------------------------------------------------------------- store

class Store:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or core.OUTPUT_ROOT)
        self.lock = threading.RLock()
        self._text_cache: dict[str, tuple[float, str]] = {}

    # ---------------------------------------------------------------- paths
    def path(self, mid: str) -> Path:
        if not mid or "/" in mid or "\\" in mid or mid in (".", "..") or mid.startswith("."):
            raise KeyError(mid)
        p = self.root / mid
        if not p.is_dir():
            raise KeyError(mid)
        return p

    def meta(self, mid: str) -> dict:
        m = _read_json(self.path(mid) / META)
        if m is None:
            m = self.migrate_v1(mid)
        return m

    def save_meta(self, mid: str, meta: dict) -> None:
        with self.lock:
            _write_json(self.path(mid) / META, meta)

    def update(self, mid: str, **fields) -> dict:
        with self.lock:
            m = self.meta(mid)
            m.update(fields)
            self.save_meta(mid, m)
            return m

    # ---------------------------------------------------------------- create / list
    def create(self, source: Path, title: str, settings: dict, participants: list[dict],
               when: dt.datetime | None = None) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock:
            folder = core.make_output_dir(source, self.root, when)
            (folder / VERS).mkdir()
            (folder / SUMS).mkdir()
            meta = {
                "schema": 2,
                "id": folder.name,
                "title": title or source.stem,
                "created": (when or dt.datetime.now()).replace(microsecond=0).isoformat(),
                "source": str(source),
                "source_name": source.name,
                "language": settings.get("language") or "",
                "settings": settings,
                "participants": canon_participants(participants),
                "status": "queued",
                "progress": None,
                "error": None,
                "log": [],
                "duration_sec": None,
                "clean_sec": None,
                "transcript_rev": 0,
                "rev_hash": None,
                "saved_at": None,
                "claude_suggest": None,
                "summaries": [],
                "sends": [],
                "v1": False,
            }
            _write_json(folder / META, meta)
            return folder.name

    def ids(self) -> list[str]:
        if not self.root.is_dir():
            return []
        out = []
        for p in self.root.iterdir():
            if p.is_dir() and not p.name.startswith(".") and (
                    (p / META).exists() or (p / "Transkrip.txt").exists()):
                out.append(p.name)
        return out

    def summary_row(self, mid: str) -> dict:
        m = self.meta(mid)
        rows = self.tag_counts(mid, m)
        return {
            "id": mid,
            "title": m.get("title") or mid,
            "created": m.get("created"),
            "duration_sec": m.get("duration_sec"),
            "status": m.get("status"),
            "progress": m.get("progress"),
            "stale": self.is_stale(m),
            "claude": bool(m.get("claude_suggest")),
            "v1": bool(m.get("v1")),
            "has_summary": bool(m.get("summaries")),
            "segments": rows["total"],
            "tagged": rows["tagged"],
        }

    def list(self, q: str = "", status: str = "") -> list[dict]:
        rows = []
        for mid in self.ids():
            try:
                row = self.summary_row(mid)
            except Exception:  # unreadable folder: skip, never crash the list
                continue
            if status and status != "all" and row["status"] != status:
                continue
            if q and not self.matches(mid, row, q):
                continue
            rows.append(row)
        rows.sort(key=lambda r: r.get("created") or "", reverse=True)
        return rows

    def matches(self, mid: str, row: dict, q: str) -> bool:
        q = q.lower().strip()
        if q in (row.get("title") or "").lower():
            return True
        return q in self.search_text(mid)

    def search_text(self, mid: str) -> str:
        p = self.path(mid)
        f = p / VERS / f"rev-{self.meta(mid).get('transcript_rev', 0)}.json"
        if not f.exists():
            return ""
        mt = f.stat().st_mtime
        hit = self._text_cache.get(mid)
        if hit and hit[0] == mt:
            return hit[1]
        v = _read_json(f, {})
        text = " ".join(s.get("text", "") for s in v.get("segments", [])).lower()
        self._text_cache[mid] = (mt, text)
        return text

    # ---------------------------------------------------------------- versions
    def is_stale(self, m: dict) -> bool:
        sums = m.get("summaries") or []
        return bool(sums) and sums[-1]["based_on_rev"] < m.get("transcript_rev", 0)

    def read_version(self, mid: str, rev: int) -> dict:
        v = _read_json(self.path(mid) / VERS / f"rev-{int(rev)}.json")
        if v is None:
            raise KeyError(f"rev-{rev}")
        return v

    def versions(self, mid: str) -> list[dict]:
        out = []
        m = self.meta(mid)
        used = {s["based_on_rev"]: s["ver"] for s in m.get("summaries", [])}
        for f in sorted((self.path(mid) / VERS).glob("rev-*.json"), key=lambda x: int(x.stem[4:])):
            v = _read_json(f, {})
            out.append({"rev": v.get("rev"), "created": v.get("created"), "source": v.get("source"),
                        "note": v.get("note"), "used_by_summary": used.get(v.get("rev"))})
        return out

    def save_whisper(self, mid: str, segments: list[dict], meta_updates: dict) -> None:
        """Store the raw Whisper result as rev-0 and open the draft for review."""
        p = self.path(mid)
        segs = []
        for i, s in enumerate(segments):
            segs.append({"id": f"s{i + 1:05d}", "start": s["start"], "end": s["end"], "text": s["text"],
                         "speaker_id": None, "secret": False,
                         "avg_logprob": s.get("avg_logprob"), "low_words": s.get("low_words") or []})
        with self.lock:
            m = self.meta(mid)
            _write_json(p / VERS / "rev-0.json", {"rev": 0, "created": now_iso(), "source": "whisper",
                                                 "segments": segs, "participants": m["participants"]})
            m.update(meta_updates)
            m["status"] = "awaiting_review"
            self.save_meta(mid, m)
            plain = core.format_transcript(segs, m["title"], meta={**m, "rev": None},
                                           participants=[])
            (p / "Transkrip asli.txt").write_text(plain, encoding="utf-8")

    def latest(self, mid: str) -> dict:
        m = self.meta(mid)
        return self.read_version(mid, m.get("transcript_rev", 0))

    def save_version(self, mid: str, segments: list[dict], participants: list[dict],
                     source: str = "save", note: str | None = None) -> dict:
        """Create rev N+1 only when the content really changed (PRD F9/F17)."""
        with self.lock:
            m = self.meta(mid)
            p = self.path(mid)
            h = content_hash(segments, participants)
            cur_rev = m.get("transcript_rev", 0)
            if cur_rev > 0 and h == m.get("rev_hash"):
                return {"changed": False, "rev": cur_rev}
            # extra fields (confidence) are kept from rev-0 so local hints survive saves
            raw = {s["id"]: s for s in self.read_version(mid, 0)["segments"]} if (p / VERS / "rev-0.json").exists() else {}
            segs = []
            for s in canon_segments(segments):
                extra = raw.get(s["id"], {})
                if extra.get("avg_logprob") is not None:
                    s["avg_logprob"] = extra["avg_logprob"]
                segs.append(s)
            parts = canon_participants(participants)
            prev = self.read_version(mid, cur_rev) if cur_rev > 0 or (p / VERS / "rev-0.json").exists() else {}
            changes = describe_changes(prev, {"segments": segs, "participants": parts}) if prev else {}
            rev = cur_rev + 1
            _write_json(p / VERS / f"rev-{rev}.json", {"rev": rev, "created": now_iso(), "source": source,
                                                      "note": note, "hash": h, "segments": segs,
                                                      "participants": parts, "changes": changes})
            m["transcript_rev"] = rev
            m["rev_hash"] = h
            m["saved_at"] = now_iso()
            m["participants"] = parts
            if m.get("summaries"):
                base = m["summaries"][-1]["based_on_rev"]
                base_v = self.read_version(mid, base) if base else {}
                m["stale_changes"] = describe_changes(base_v, {"segments": segs, "participants": parts})
            self.save_meta(mid, m)
            self.write_transcript_files(mid)
            if m.get("summaries"):
                self.write_summary_files(mid)
            self.clear_draft(mid)
            return {"changed": True, "rev": rev, "changes": changes}

    def restore_version(self, mid: str, rev: int) -> dict:
        v = self.read_version(mid, rev)
        name = "Asli Whisper" if int(rev) == 0 else f"versi {rev}"
        return self.save_version(mid, v["segments"], v.get("participants") or self.meta(mid)["participants"],
                                 source="restore", note=f"Dipulihkan dari {name}")

    def write_transcript_files(self, mid: str) -> None:
        m = self.meta(mid)
        v = self.latest(mid)
        txt = core.format_transcript(v["segments"], m["title"],
                                     meta={**m, "rev": m.get("transcript_rev")},
                                     participants=v.get("participants") or [])
        (self.path(mid) / "Transkrip.txt").write_text(txt, encoding="utf-8")

    def tag_counts(self, mid: str, m: dict | None = None) -> dict:
        m = m or self.meta(mid)
        try:
            v = self.latest(mid) if m.get("transcript_rev") else self.read_version(mid, 0)
        except KeyError:
            return {"total": 0, "tagged": 0, "per": {}}
        ids = {p["id"] for p in v.get("participants") or []}
        per: dict[str, int] = {}
        for s in v.get("segments", []):
            if s.get("speaker_id") in ids:
                per[s["speaker_id"]] = per.get(s["speaker_id"], 0) + 1
        return {"total": len(v.get("segments", [])), "tagged": sum(per.values()), "per": per}

    # ---------------------------------------------------------------- draft
    def read_draft(self, mid: str) -> dict | None:
        return _read_json(self.path(mid) / DRAFT)

    def write_draft(self, mid: str, draft: dict) -> None:
        draft = {**draft, "updated": now_iso()}
        _write_json(self.path(mid) / DRAFT, draft)

    def clear_draft(self, mid: str) -> None:
        try:
            (self.path(mid) / DRAFT).unlink()
        except FileNotFoundError:
            pass

    # ---------------------------------------------------------------- summaries
    def add_summary(self, mid: str, md: str, based_on_rev: int, model: str, context: str = "",
                    redaction: dict | None = None, source: str = "claude", note: str | None = None) -> int:
        with self.lock:
            m = self.meta(mid)
            ver = len(m.get("summaries", [])) + 1
            (self.path(mid) / SUMS).mkdir(exist_ok=True)
            (self.path(mid) / SUMS / f"sum-{ver}.md").write_text(md, encoding="utf-8")
            m.setdefault("summaries", []).append({
                "ver": ver, "based_on_rev": based_on_rev, "created": now_iso(), "model": model,
                "context": context, "redaction": redaction or {}, "source": source, "note": note})
            m.pop("stale_changes", None)
            if self.is_stale(m):
                base_v = self.read_version(mid, based_on_rev) if based_on_rev else {}
                m["stale_changes"] = describe_changes(base_v, self.latest(mid))
            self.save_meta(mid, m)
            self.write_summary_files(mid)
            return ver

    def read_summary(self, mid: str, ver: int) -> str:
        return (self.path(mid) / SUMS / f"sum-{int(ver)}.md").read_text(encoding="utf-8")

    def restore_summary(self, mid: str, ver: int) -> int:
        m = self.meta(mid)
        info = m["summaries"][int(ver) - 1]
        return self.add_summary(mid, self.read_summary(mid, ver), info["based_on_rev"], info["model"],
                                info.get("context", ""), info.get("redaction"), source="restore",
                                note=f"Dipulihkan dari ringkasan v{ver}")

    def stale_line(self, m: dict) -> str:
        s = m["summaries"][-1]
        when = m.get("saved_at")
        when_txt = f" pada {core.fmt_date_short(dt.datetime.fromisoformat(when))}" if when else ""
        return (f"⚠ Ringkasan ini dibuat dari transkrip versi {s['based_on_rev']}. Transkrip sudah "
                f"diperbarui ke versi {m['transcript_rev']}{when_txt}. Buka Meeting Notes untuk "
                f"memperbarui ringkasan.")

    def write_summary_files(self, mid: str) -> None:
        """Ringkasan.md/.docx = latest summary, with a ⚠ line on top while it is stale.

        The summary body itself is never changed by this (approved rule)."""
        m = self.meta(mid)
        if not m.get("summaries"):
            return
        body = self.read_summary(mid, m["summaries"][-1]["ver"])
        md = (self.stale_line(m) + "\n\n" + body) if self.is_stale(m) else body
        p = self.path(mid)
        (p / "Ringkasan.md").write_text(md, encoding="utf-8")
        try:
            core.markdown_to_docx(md, p / "Ringkasan.docx")
        except Exception:  # docx is a convenience copy; md is the record
            pass

    def log_send(self, mid: str, entry: dict) -> None:
        with self.lock:
            m = self.meta(mid)
            m.setdefault("sends", []).append({"at": now_iso(), **entry})
            self.save_meta(mid, m)

    def send_log(self, limit: int = 20) -> list[dict]:
        out = []
        for mid in self.ids():
            try:
                m = self.meta(mid)
            except Exception:
                continue
            for s in m.get("sends", []):
                out.append({**s, "meeting": m.get("title"), "id": mid})
        out.sort(key=lambda s: s["at"], reverse=True)
        return out[:limit]

    # ---------------------------------------------------------------- delete
    def trash(self, mid: str) -> None:
        p = self.path(mid)
        try:
            subprocess.run(["osascript", "-e",
                            f'tell application "Finder" to delete (POSIX file "{p}" as alias)'],
                           check=True, capture_output=True)
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
        trash = Path.home() / ".Trash"
        trash.mkdir(exist_ok=True)
        dest, n = trash / p.name, 2
        while dest.exists():
            dest, n = trash / f"{p.name} {n}", n + 1
        shutil.move(str(p), str(dest))

    # ---------------------------------------------------------------- v1 migration
    def migrate_v1(self, mid: str) -> dict:
        p = self.path(mid)
        tx = p / "Transkrip.txt"
        if not tx.exists():
            raise KeyError(mid)
        with self.lock:
            if (p / META).exists():
                return _read_json(p / META)
            info, segs = parse_v1_transcript(tx.read_text(encoding="utf-8", errors="replace"))
            dm = _V1_DIR.match(p.name)
            created = (dt.datetime(int(dm[1]), int(dm[2]), int(dm[3]), int(dm[4]), int(dm[5]))
                       if dm else dt.datetime.fromtimestamp(tx.stat().st_mtime)).isoformat()
            (p / VERS).mkdir(exist_ok=True)
            (p / SUMS).mkdir(exist_ok=True)
            h = content_hash(segs, [])
            _write_json(p / VERS / "rev-0.json", {"rev": 0, "created": created, "source": "v1",
                                                 "segments": segs, "participants": []})
            _write_json(p / VERS / "rev-1.json", {"rev": 1, "created": created, "source": "v1",
                                                 "note": "Diimpor dari Meeting Notes v1", "hash": h,
                                                 "segments": segs, "participants": [], "changes": {}})
            meta = {
                "schema": 2, "id": p.name,
                "title": info.get("title") or (dm[6] if dm else p.name),
                "created": created, "source": "", "source_name": "",
                "language": "id", "settings": {}, "participants": [],
                "status": "transcript_only", "progress": None, "error": None, "log": [],
                "duration_sec": info.get("duration_sec"), "clean_sec": info.get("clean_sec"),
                "transcript_rev": 1, "rev_hash": h, "saved_at": created,
                "claude_suggest": None, "summaries": [], "sends": [], "v1": True,
            }
            rs = p / "Ringkasan.md"
            if rs.exists():
                (p / SUMS / "sum-1.md").write_text(rs.read_text(encoding="utf-8", errors="replace"),
                                                  encoding="utf-8")
                meta["summaries"].append({"ver": 1, "based_on_rev": 1, "created": created,
                                          "model": core.CLAUDE_MODEL, "context": "", "redaction": {},
                                          "source": "v1", "note": "Diimpor dari Meeting Notes v1"})
                meta["status"] = "done"
            _write_json(p / META, meta)
            return meta
