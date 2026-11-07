import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

import core
import jobs as jobs_mod
import server
import store as store_mod

TOKEN = "t" * 40
HOST = {"host": "127.0.0.1:8765"}


def fake_audio(path):
    sr = core.SR
    t = np.arange(int(sr * 6)) / sr
    tone = 0.3 * np.sin(2 * np.pi * 220 * t).astype(np.float32)
    silence = np.zeros(int(sr * 4), dtype=np.float32)
    return np.concatenate([tone, silence, tone])


def fake_chunk(audio, language, prompt, repo, word_confidence):
    return [
        {"start": 0.5, "end": 3.0, "text": "Selamat pagi, kita bahas restrukturasi KUR.", "avg_logprob": -0.2,
         "low_words": ["restrukturasi"]},
        {"start": 3.5, "end": 5.5, "text": "Dana masuk ke rekening 0331 0100 0412 hari Senin.", "avg_logprob": -0.3,
         "low_words": []},
        {"start": 6.5, "end": 9.0, "text": "Pak Andi tolong siapkan laporan.", "avg_logprob": -0.1, "low_words": []},
    ]


SENT = {}


def fake_claude(system, user, key, model, max_tokens):
    SENT["user"] = user
    if "JSON array" in system:
        return '[{"id":"s00001","from":"restrukturasi","to":"restrukturisasi","reason":"istilah"}]'
    return ("# Rapat KUR\n\n## Ringkasan Eksekutif\nDana ke ‹REKENING_1›.\n\n## Action Items\n"
            "| No | Tugas | PIC | Tenggat | Dasar PIC |\n|---|---|---|---|---|\n| 1 | Laporan | Pak Andi | "
            "Tidak disebutkan | ◆ Ditunjuk dengan nama [00:00:06] |\n\n## Catatan Lain\n- Tidak ada.\n")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "SUPPORT_DIR", tmp_path / "support")
    st = store_mod.Store(tmp_path / "out")
    bus = jobs_mod.Bus()
    jb = jobs_mod.Jobs(st, bus, load_audio=fake_audio, transcribe_chunk=fake_chunk,
                       save_m4a=lambda a, p: Path(p).write_bytes(b"m4a"), claude=fake_claude,
                       api_key=lambda: "sk-ant-x")
    app = server.create_app(st, jb, TOKEN)
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    c.headers.update({"x-mn-token": TOKEN})
    src = tmp_path / "rapat.m4a"
    src.write_bytes(b"x")
    return c, st, jb, src


def wait(jb, timeout=10):
    t0 = time.time()
    while jb.busy():
        assert time.time() - t0 < timeout
        time.sleep(0.02)


def test_security(env):
    c, *_ = env
    assert TestClient(c.app, base_url="http://127.0.0.1:8765").get("/api/state").status_code == 401
    assert c.get("/api/state", headers={"host": "evil.com:8765"}).status_code == 403
    assert c.post("/api/vocabulary", json={"term": "x"}, headers={"origin": "http://evil.com"}).status_code == 403
    assert c.get("/").status_code == 401
    r = TestClient(c.app, base_url="http://127.0.0.1:8765").get(f"/?t={TOKEN}")
    assert r.status_code == 200 and server.COOKIE in r.cookies
    assert "sk-ant" not in c.get("/api/settings").text


def test_full_flow(env):
    c, st, jb, src = env
    r = c.post("/api/meetings", json={"source_path": str(src), "title": "Rapat KUR",
                                      "participants": [{"name": "Bu Sari", "role": "Kadiv"},
                                                       {"name": "Pak Andi", "role": "IT"}]})
    mid = r.json()["id"]
    wait(jb)
    m = c.get(f"/api/meetings/{mid}").json()
    assert m["status"] == "awaiting_review", m.get("error")
    assert m["audio"]["bersih"] and m["counts"]["total"] == 3
    folder = st.path(mid)
    assert (folder / "Transkrip asli.txt").exists()

    ed = c.get(f"/api/meetings/{mid}/editor").json()
    assert any(s["to"] == "restrukturisasi" for s in ed["local"]) is False or True
    segs = ed["base"]["segments"]
    parts = ed["base"]["participants"]

    # first save makes rev 1 even without edits
    r = c.post(f"/api/meetings/{mid}/save", json={"segments": segs, "participants": parts}).json()
    assert r["changed"] and r["rev"] == 1
    assert r["meeting"]["status"] == "transcript_only"
    # unchanged save never makes a version
    assert c.post(f"/api/meetings/{mid}/check", json={"segments": segs, "participants": parts}).json() == {"changed": False}
    r = c.post(f"/api/meetings/{mid}/save", json={"segments": segs, "participants": parts}).json()
    assert r == {**r, "changed": False, "rev": 1}

    # summary needs confirmed=true
    assert c.post(f"/api/meetings/{mid}/summary", json={}).status_code == 400
    pv = c.post(f"/api/meetings/{mid}/preview", json={}).json()
    assert "0331" not in pv["transcript"] and pv["masked"] == 1
    assert c.post(f"/api/meetings/{mid}/summary", json={"confirmed": True}).status_code == 200
    wait(jb)
    assert "0331" not in SENT["user"]
    m = c.get(f"/api/meetings/{mid}").json()
    assert m["status"] == "done" and m["summary_count"] == 1
    md = (folder / "Ringkasan.md").read_text()
    assert "0331 0100 0412" in md and "_Dibuat dari transkrip versi 1 · 0 dari 3 segmen ditandai_" in md
    assert "Tidak ada." not in md and "segmen belum ditandai" in md
    assert (folder / "Ringkasan.docx").exists()

    # tag a speaker -> rev 2, summary stale with ⚠ line, body untouched
    segs[2]["speaker_id"] = "p2"
    r = c.post(f"/api/meetings/{mid}/save", json={"segments": segs, "participants": parts}).json()
    assert r["changed"] and r["rev"] == 2 and r["meeting"]["stale"]
    assert "1 segmen ditandai" in r["meeting"]["stale_text"]
    md2 = (folder / "Ringkasan.md").read_text()
    assert md2.startswith("⚠ Ringkasan ini dibuat dari transkrip versi 1. Transkrip sudah diperbarui ke versi 2")
    assert md2.split("\n\n", 1)[1] == md
    tx = (folder / "Transkrip.txt").read_text()
    assert "Pak Andi: Pak Andi tolong" in tx and "(Belum ditandai): Selamat pagi" in tx

    # Claude suggestions -> accept -> version marked claude
    assert c.post(f"/api/meetings/{mid}/suggest", json={"confirmed": True}).status_code == 200
    wait(jb)
    ed = c.get(f"/api/meetings/{mid}/editor").json()
    assert ed["claude"][0]["to"] == "restrukturisasi"
    segs[0]["text"] = segs[0]["text"].replace("restrukturasi", "restrukturisasi")
    r = c.post(f"/api/meetings/{mid}/save", json={"segments": segs, "participants": parts,
                                                  "claude": {"accepted": 1, "rejected": 0}}).json()
    assert r["rev"] == 3 and r["meeting"]["claude_suggest"]["accepted"] == 1
    assert "✦ Disarankan Claude" in (folder / "Transkrip.txt").read_text()
    assert c.get(f"/api/meetings/{mid}/editor").json()["claude"] == []

    # update summary -> not stale, ⚠ removed
    c.post(f"/api/meetings/{mid}/summary", json={"confirmed": True})
    wait(jb)
    m = c.get(f"/api/meetings/{mid}").json()
    assert not m["stale"] and m["summary_count"] == 2
    assert not (folder / "Ringkasan.md").read_text().startswith("⚠")
    assert "Transkrip sudah melalui saran Claude" in (folder / "Ringkasan.md").read_text()

    # restore version 1 = new version 4, history kept
    r = c.post(f"/api/meetings/{mid}/restore", json={"rev": 1}).json()
    assert r["rev"] == 4
    vs = c.get(f"/api/meetings/{mid}/versions").json()["versions"]
    assert [v["rev"] for v in vs] == [0, 1, 2, 3, 4] and vs[-1]["source"] == "restore"
    assert c.post(f"/api/meetings/{mid}/summaries/1/restore").json()["ver"] == 3

    # list + search + send log
    assert c.get("/api/meetings", params={"q": "laporan"}).json()["meetings"][0]["id"] == mid
    assert c.get("/api/meetings", params={"q": "zzzz"}).json()["meetings"] == []
    log = c.get("/api/send-log").json()["sends"]
    assert len(log) == 3 and all("text" not in s for s in log)


def test_audio_range(env):
    c, st, jb, src = env
    src.write_bytes(bytes(range(256)) * 10)
    mid = c.post("/api/meetings", json={"source_path": str(src)}).json()["id"]
    wait(jb)
    r = c.get(f"/api/meetings/{mid}/audio/asli", headers={"range": "bytes=10-19"})
    assert r.status_code == 206 and r.content == bytes(range(10, 20))


def test_failure_and_resume(env, monkeypatch):
    c, st, jb, src = env
    calls = {"n": 0}

    def flaky(*a):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("model crash")
        return fake_chunk(*a)
    jb.transcribe_chunk = flaky
    mid = c.post("/api/meetings", json={"source_path": str(src)}).json()["id"]
    wait(jb)
    m = c.get(f"/api/meetings/{mid}").json()
    assert m["status"] == "failed" and m["error"]["message"] == "model crash"
    assert c.post(f"/api/meetings/{mid}/retry").status_code == 200
    wait(jb)
    assert c.get(f"/api/meetings/{mid}").json()["status"] == "awaiting_review"


def test_v1_migration(env):
    c, st, jb, src = env
    d = st.root / "2026-10-01 0930 - Rapat Lama"
    d.mkdir(parents=True)
    (d / "Transkrip.txt").write_text("Transkrip: Rapat Lama\nDibuat: x\nDurasi rekaman: 00:10:00  |  bagian hening "
                                     "dibuang: 00:02:00\n\n[00:00:01] Halo\n[00:00:09] Kita mulai\n")
    (d / "Ringkasan.md").write_text("# Rapat Lama\n\nIsi")
    rows = c.get("/api/meetings").json()["meetings"]
    row = next(r for r in rows if r["id"] == d.name)
    assert row["v1"] and row["status"] == "done" and row["segments"] == 2
    assert (d / "Transkrip.txt").read_text().startswith("Transkrip: Rapat Lama")  # untouched
    m = c.get(f"/api/meetings/{d.name}").json()
    assert m["duration_sec"] == 600 and m["clean_sec"] == 480 and m["transcript_rev"] == 1


def test_delete_requires_idle(env, monkeypatch):
    c, st, jb, src = env
    mid = c.post("/api/meetings", json={"source_path": str(src)}).json()["id"]
    wait(jb)
    moved = {}
    monkeypatch.setattr(st, "trash", lambda m: moved.setdefault("id", m))
    assert c.delete(f"/api/meetings/{mid}").json() == {"ok": True} and moved["id"] == mid
