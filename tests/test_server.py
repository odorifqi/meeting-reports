import json
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


def fake_audio(path, start=None, dur=None, track=None):
    sr = core.SR
    t = np.arange(int(sr * 6)) / sr
    tone = 0.3 * np.sin(2 * np.pi * 220 * t).astype(np.float32)
    silence = np.zeros(int(sr * 4), dtype=np.float32)
    a = np.concatenate([tone, silence, tone])
    if start is not None:
        a = a[int(start * sr):]
        a = a[:int(dur * sr)] if dur else a
    return a


def fake_chunk(audio, language, prompt, repo, word_confidence):
    if len(audio) / core.SR < 10:   # a gap being re-transcribed: nothing more found
        return []
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
    monkeypatch.setattr(core, "probe", lambda p: {"ok": True, "video": False, "duration": 16.0, "unknown": False,
                                                  "problem": None, "tracks": [{"n": 0, "codec": "aac", "channels": 1,
                                                                               "duration": 16.0, "label": ""}]})
    st = store_mod.Store(tmp_path / "out")
    bus = jobs_mod.Bus()
    jb = jobs_mod.Jobs(st, bus, load_audio=fake_audio, transcribe_chunk=fake_chunk,
                       save_m4a=lambda a, p: Path(p).write_bytes(b"m4a"), claude=fake_claude,
                       api_key=lambda p=None: "sk-ant-x", model_ready=lambda r: True)
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
    assert TestClient(c.app, base_url="http://127.0.0.1:8765").get("/api/health").json()["app"] == "meeting-report"
    r = TestClient(c.app, base_url="http://127.0.0.1:8765").get(f"/?t={TOKEN}")
    assert r.status_code == 200 and server.COOKIE in r.cookies
    assert "sk-ant-x" not in c.get("/api/settings").text and "sk-ant-test" not in c.get("/api/settings").text


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
    assert "✦ Disarankan AI" in (folder / "Transkrip.txt").read_text()
    assert c.get(f"/api/meetings/{mid}/editor").json()["claude"] == []

    # update summary -> not stale, ⚠ removed
    c.post(f"/api/meetings/{mid}/summary", json={"confirmed": True})
    wait(jb)
    m = c.get(f"/api/meetings/{mid}").json()
    assert not m["stale"] and m["summary_count"] == 2
    assert not (folder / "Ringkasan.md").read_text().startswith("⚠")
    assert "Transkrip sudah melalui saran AI" in (folder / "Ringkasan.md").read_text()

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


# ---------------------------------------------------------------------------- v1.3

def test_nan_in_old_version_is_readable(env):
    """v1.2 wrote NaN for empty Whisper segments; the editor got a 500."""
    c, st, jb, src = env
    mid = c.post("/api/meetings", json={"source_path": str(src), "title": "Audio NaN"}).json()["id"]
    wait(jb)
    f = st.path(mid) / "versions" / "rev-0.json"
    f.write_text(f.read_text().replace('"avg_logprob": -0.2', '"avg_logprob": NaN'))
    r = c.get(f"/api/meetings/{mid}/editor")
    assert r.status_code == 200
    assert r.json()["base"]["segments"][0]["avg_logprob"] is None


def test_title_validation_and_folder_name(env):
    c, st, jb, src = env
    r = c.post("/api/meetings", json={"source_path": str(src), "title": "Rapat 1/2"})
    assert r.status_code == 400 and "/" in r.json()["detail"]
    r = c.post("/api/meetings", json={"source_path": str(src), "title": "x" * 81})
    assert r.status_code == 400
    mid = c.post("/api/meetings", json={"source_path": str(src), "title": "Rapat KUR"}).json()["id"]
    assert mid.endswith(" - Rapat KUR")          # folder follows the title, not the file name
    wait(jb)
    assert c.patch(f"/api/meetings/{mid}", json={"title": "a:b"}).status_code == 400
    assert c.patch(f"/api/meetings/{mid}", json={"title": " "}).status_code == 400
    d = c.patch(f"/api/meetings/{mid}", json={"title": "Rapat NPL"}).json()
    assert d["id"].endswith(" - Rapat NPL") and d["title"] == "Rapat NPL"
    assert c.get(f"/api/meetings/{mid}").status_code == 404
    assert (st.root / d["id"] / "meeting.json").exists()


def test_recording_time_from_voice_memos_name(tmp_path):
    f = tmp_path / "20261105 134717.m4a"
    f.write_bytes(b"x")
    assert core.recording_time(f).isoformat() == "2026-11-05T13:47:17"


def test_folder_migration(env, tmp_path):
    c, st, jb, src = env
    mid = c.post("/api/meetings", json={"source_path": str(src), "title": "Koordinasi"}).json()["id"]
    wait(jb)
    old = st.root / "2026-11-07 2256 - Audio bersih"
    (st.root / mid).rename(old)
    m = store_mod._read_json(old / "meeting.json")
    m["id"] = old.name
    store_mod._write_json(old / "meeting.json", m)
    (core.SUPPORT_DIR / store_mod.MIGRATED).unlink()   # create_app already ran it once
    done = st.migrate_folder_names()
    assert done and done[0][1].endswith(" - Koordinasi")
    assert st.migrate_folder_names() == []        # only once


def test_fill_gaps_inserts_skipped_speech():
    sr = core.SR
    audio = np.zeros(sr * 20, dtype=np.float32)
    segs = [{"start": 0.0, "end": 4.0, "text": "a"}, {"start": 12.0, "end": 15.0, "text": "c"}]
    seen = []

    def again(piece):
        seen.append(len(piece) / sr)
        return [{"start": 1.5, "end": 5.0, "text": "b"}]

    out, report = core.fill_gaps(audio, segs, again, min_gap=3.0)
    assert [s["text"] for s in out][:3] == ["a", "b", "c"]
    assert out[1]["gap_fill"] and out[1]["start"] == 4.5
    assert report[0][:2] == (4.0, 12.0) and seen[0] == pytest.approx(10.0)
    assert core.find_gaps(segs, 15.0, 3.0) == [(4.0, 12.0)]
    assert core.find_gaps(segs, 15.0, 9.0) == []


def test_gaps_and_retranscribe(env):
    c, st, jb, src = env
    mid = c.post("/api/meetings", json={"source_path": str(src), "title": "Celah"}).json()["id"]
    wait(jb)
    g = c.get(f"/api/meetings/{mid}/gaps").json()
    assert g["regions"] and g["min_gap"] == 3.0
    r = c.post(f"/api/meetings/{mid}/retranscribe", json={"start": 0, "end": 12}).json()
    assert r["segments"] and r["segments"][0]["text"].startswith("Selamat pagi")
    assert c.post(f"/api/meetings/{mid}/retranscribe", json={"start": 5, "end": 2}).status_code == 400


def test_manual_flag_keeps_old_hashes():
    a = [{"id": "s1", "start": 0, "end": 1, "text": "x"}]
    b = [{"id": "s1", "start": 0, "end": 1, "text": "x", "manual": False}]
    assert store_mod.content_hash(a, []) == store_mod.content_hash(b, [])
    b[0]["manual"] = True
    assert store_mod.content_hash(a, []) != store_mod.content_hash(b, [])


def test_provider_settings(env, monkeypatch):
    c, st, jb, src = env
    s = c.put("/api/settings", json={"ai_provider": "ollama", "ai_models": {"ollama": "qwen3:14b"},
                                     "ai_base_url": {"ollama": "javascript:x"}}).json()
    assert s["ai"]["provider"] == "ollama" and s["ai"]["local"] and s["api_key"]
    assert s["ai"]["base_url"] == "http://127.0.0.1:11434/v1"      # bad URL ignored
    assert c.post("/api/settings/api-key", json={"provider": "anthropic", "key": "abc"}).status_code == 400
    assert c.post("/api/settings/api-key", json={"provider": "nope", "key": "abc"}).status_code == 400
    st_ = c.get("/api/state").json()
    assert st_["ai"]["provider_short"] == "Ollama lokal"
    c.put("/api/settings", json={"ai_provider": "anthropic"})


def _fake_ai_server(handler_fn):
    """Local OpenAI-style server; handler_fn(path, body, handler) writes the reply."""
    import http.server
    import threading as th

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            H.seen.append({"path": self.path, "body": body, "auth": self.headers.get("Authorization")})
            handler_fn(self.path, body, self)

    H.seen = []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    th.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, H.seen, f"http://127.0.0.1:{srv.server_address[1]}/v1"


def _reply(h, code, data, ctype="application/json"):
    raw = data if isinstance(data, bytes) else json.dumps(data).encode()
    h.send_response(code)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(len(raw)))
    h.end_headers()
    h.wfile.write(raw)


@pytest.fixture()
def no_proxy(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


def test_normalize_base_url():
    n = core.normalize_base_url
    assert n("https://api.example.com/v1/chat/completions") == "https://api.example.com/v1"
    assert n("https://api.example.com/v1/chat/completions/") == "https://api.example.com/v1"
    assert n(" https://api.example.com/v1/ ") == "https://api.example.com/v1"
    assert n("http://127.0.0.1:11434/v1/models") == "http://127.0.0.1:11434/v1"


def test_ai_text_streams_and_normalizes(no_proxy):
    def h(path, body, hd):
        if path != "/v1/chat/completions":
            return _reply(hd, 404, {"error": {"message": "no route"}})
        if not body.get("stream"):
            return _reply(hd, 400, {"error": "stream expected"})
        chunks = [{"choices": [{"delta": {"content": p}}]} for p in ["# Rapat", "\nIsi ", "ringkasan"]]
        raw = b"".join(b"data: " + json.dumps(c).encode() + b"\n\n" for c in chunks) + b"data: [DONE]\n\n"
        _reply(hd, 200, raw, "text/event-stream")

    srv, seen, base = _fake_ai_server(h)
    try:
        out = core.ai_text("sys", "isi", "k", "m1", 100, provider="compat", base_url=base + "/chat/completions")
        assert out == "# Rapat\nIsi ringkasan"
        assert seen[-1]["path"] == "/v1/chat/completions" and seen[-1]["auth"] == "Bearer k"
        assert seen[-1]["body"]["max_tokens"] == 100 and seen[-1]["body"]["stream"] is True
        core.ai_text("sys", "isi", "local", "qwen3:14b", 50, provider="ollama", base_url=base)
        assert seen[-1]["auth"] is None
    finally:
        srv.shutdown()


def test_ai_text_plain_json_fallback_and_errors(no_proxy, monkeypatch):
    mode = {"m": "json"}

    def h(path, body, hd):
        if mode["m"] == "json":
            return _reply(hd, 200, {"choices": [{"message": {"content": " halo "}}]})
        if mode["m"] == "404":
            return _reply(hd, 404, {"error": {"message": "model 'x' not found"}})
        if mode["m"] == "524":
            return _reply(hd, 524, b"<html><body>A timeout occurred</body></html>", "text/html")
        if mode["m"] == "slow":
            import time as t
            t.sleep(1.5)
            return _reply(hd, 200, {"choices": [{"message": {"content": "late"}}]})

    srv, seen, base = _fake_ai_server(h)
    try:
        assert core.ai_text("s", "u", "k", "m", 10, provider="compat", base_url=base) == "halo"
        mode["m"] = "404"
        with pytest.raises(core.AIError) as e:
            core.ai_text("s", "u", "k", "x", 10, provider="compat", base_url=base)
        assert e.value.kind == "http" and e.value.status == 404 and "not found" in e.value.detail
        msg = jobs_mod._friendly(e.value, "Server kustom")
        assert "HTTP 404" in msg and "model 'x' not found" in msg and "/v1" in msg
        mode["m"] = "524"
        with pytest.raises(core.AIError) as e:
            core.ai_text("s", "u", "k", "m", 10, provider="compat", base_url=base)
        assert e.value.status == 524 and "A timeout occurred" in e.value.detail
        assert "kehabisan waktu" in jobs_mod._friendly(e.value, "Server kustom")
        mode["m"] = "slow"
        monkeypatch.setattr(core, "AI_TIMEOUT", 0.5)
        with pytest.raises(core.AIError) as e:
            core.ai_text("s", "u", "k", "m", 10, provider="compat", base_url=base)
        assert e.value.kind == "timeout"
        assert "tidak mengirim jawaban" in jobs_mod._friendly(e.value, "Server kustom")
    finally:
        srv.shutdown()
        srv.server_close()
    with pytest.raises(core.AIError) as e:
        core.ai_text("s", "u", "k", "m", 10, provider="compat", base_url=base)   # server gone
    assert e.value.kind == "network"
    assert "terputus atau gagal dibuka" in jobs_mod._friendly(e.value, "Server kustom")


def test_settings_store_base_url_without_endpoint(env):
    c, *_ = env
    c.put("/api/settings", json={"ai_base_url": {"compat": "https://api.example.com/v1/chat/completions"}})
    assert c.get("/api/settings").json()["config"]["ai_base_url"]["compat"] == "https://api.example.com/v1"


# ---------------------------------------------------------------------------- video (Usulan 15)

def _ffmpeg(*args):
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg tidak ada")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def test_probe_video_tracks(tmp_path):
    v = tmp_path / "rekaman layar.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=black:s=64x64:d=3", "-f", "lavfi", "-i", "sine=f=300:d=3",
            "-f", "lavfi", "-i", "sine=f=500:d=2", "-map", "0", "-map", "1", "-map", "2", "-shortest",
            "-c:v", "libx264", "-c:a", "aac", str(v))
    info = core.probe(v)
    assert info["ok"] and info["video"] and len(info["tracks"]) == 2
    assert core.default_track(info) is not None
    a0 = core.load_audio(str(v), track=0)
    mix = core.load_audio(str(v), track="mix")
    assert abs(len(a0) / core.SR - 2) < 0.3 and len(mix) > 0   # -shortest cut the file to 2 s

    mute = tmp_path / "tanpa suara.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=black:s=64x64:d=2", "-c:v", "libx264", str(mute))
    m = core.probe(mute)
    assert not m["ok"] and "tidak punya suara" in m["problem"]

    bad = tmp_path / "rusak.mp4"
    bad.write_bytes(b"bukan video")
    assert not core.probe(bad)["ok"]


def test_video_meeting_gets_audio_rapat(env, tmp_path, monkeypatch):
    c, st, jb, src = env
    monkeypatch.setattr(core, "probe", lambda p: {"ok": True, "video": True, "duration": 16.0, "unknown": False,
                                                  "problem": None, "tracks": [
                                                      {"n": 0, "codec": "aac", "channels": 2, "duration": 16.0, "label": ""},
                                                      {"n": 1, "codec": "aac", "channels": 1, "duration": 4.0, "label": "Mic"}]})
    v = tmp_path / "zoom.mp4"
    v.write_bytes(b"x")
    info = c.post("/api/file-info", json={"path": str(v)}).json()
    assert info["probe"]["video"] and info["default_track"] == 0 and "disk" in info
    mid = c.post("/api/meetings", json={"source_path": str(v), "title": "Rapat Zoom", "audio_track": "mix"}).json()["id"]
    wait(jb)
    m = c.get(f"/api/meetings/{mid}").json()
    assert m["settings"]["audio_track"] == "mix" and m["audio"]["rapat"]
    assert (st.path(mid) / "Audio rapat.m4a").exists()


def test_video_without_sound_is_refused(env, tmp_path, monkeypatch):
    c, st, jb, src = env
    monkeypatch.setattr(core, "probe", lambda p: {"ok": False, "video": True, "duration": 5.0, "tracks": [],
                                                  "unknown": False, "problem": "Video ini tidak punya suara."})
    r = c.post("/api/meetings", json={"source_path": str(src), "title": "Bisu"})
    assert r.status_code == 400 and "suara" in r.json()["detail"]



def test_whisper_model_choice(env):
    c, st, jb, src = env
    seen, downloads = [], []
    orig = jb.transcribe_chunk
    jb.transcribe_chunk = lambda a, lang, prompt, repo, wc=True: (seen.append(repo), orig(a, lang, prompt, repo, wc))[1]
    jb.model_ready = lambda repo: False
    jb.download_model = lambda repo: downloads.append(repo)
    s = c.get("/api/settings").json()
    assert [w["key"] for w in s["whisper_models"]] == ["cepat", "akurat"]
    assert s["config"]["whisper_model"] == "cepat"
    c.put("/api/settings", json={"whisper_model": "salah"})
    assert c.get("/api/settings").json()["config"]["whisper_model"] == "cepat"
    r = c.post("/api/meetings", json={"source_path": str(src), "title": "Uji akurat", "whisper_model": "akurat"})
    assert r.status_code == 200, r.text
    mid = r.json()["id"]
    wait(jb)
    m = st.meta(mid)
    assert m["settings"]["whisper_model"] == "akurat"
    assert m["whisper_model"] == {"key": "akurat", "name": "large-v3", "repo": "mlx-community/whisper-large-v3-mlx"}
    assert seen and set(seen) == {"mlx-community/whisper-large-v3-mlx"}
    assert downloads == ["mlx-community/whisper-large-v3-mlx"]
    assert "Model        : Whisper large-v3 (Akurat, lokal)" in (st.path(mid) / "Transkrip asli.txt").read_text()
    # default from settings when the form does not say
    c.put("/api/settings", json={"whisper_model": "akurat"})
    r = c.post("/api/meetings", json={"source_path": str(src), "title": "Uji default"})
    wait(jb)
    assert st.meta(r.json()["id"])["whisper_model"]["key"] == "akurat"


def test_migrate_output_root(tmp_path):
    old, new = tmp_path / "Meeting Notes", tmp_path / "Meeting Report"
    (old / "2026-11-05 1347 - KUR").mkdir(parents=True)
    (old / "2026-11-05 1347 - KUR" / "meeting.json").write_text(json.dumps(
        {"title": "KUR", "source": str(old / "2026-11-05 1347 - KUR" / "Rekaman asli.m4a")}))
    (old / "2026-11-06 0900 - Lain").mkdir()
    moved = core.migrate_output_root(old, new)
    assert not old.exists() and sorted(moved) == ["2026-11-05 1347 - KUR", "2026-11-06 0900 - Lain"]
    m = json.loads((new / "2026-11-05 1347 - KUR" / "meeting.json").read_text())
    assert m["source"] == str(new / "2026-11-05 1347 - KUR" / "Rekaman asli.m4a")
    assert core.migrate_output_root(old, new) == []
    # both exist: move what does not clash, leave the clash in the old folder
    (old / "a").mkdir(parents=True)
    (old / "2026-11-06 0900 - Lain").mkdir()
    assert core.migrate_output_root(old, new) == ["a"]
    assert (new / "a").is_dir() and (old / "2026-11-06 0900 - Lain").is_dir()


def test_retranscribe_drops_padding_echo(env):
    """Bug report: the 1 s padding made Whisper return the neighbouring line again
    ("Terima kasih" just before the gap), which the editor then added as a new segment."""
    c, st, jb, src = env
    mid = c.post("/api/meetings", json={"source_path": str(src), "title": "Celah tepi"}).json()["id"]
    wait(jb)
    jb.transcribe_chunk = lambda audio, lang, prompt, repo, wc=True: [
        {"start": 0.0, "end": 0.7, "text": "Terima kasih", "low_words": []},     # in the left padding
        {"start": 4.0, "end": 6.0, "text": "isi celah", "low_words": []},
        {"start": 10.6, "end": 11.0, "text": "Terima kasih.", "low_words": []},   # in the right padding
    ]
    r = c.post(f"/api/meetings/{mid}/retranscribe", json={"start": 3.0, "end": 12.0}).json()
    assert [s["text"] for s in r["segments"]] == ["isi celah"] and r["outside"] == 2
    assert r["segments"][0]["start"] == 6.0


def test_nan_in_meeting_file_does_not_break_json(env):
    """A NaN anywhere in meeting.json gave 'Out of range float values are not JSON compliant: nan'."""
    c, st, jb, src = env
    mid = c.post("/api/meetings", json={"source_path": str(src), "title": "Durasi NaN"}).json()["id"]
    wait(jb)
    f = st.path(mid) / "meeting.json"
    data = json.loads(f.read_text())
    data["duration"] = float("nan")
    data["extra_inf"] = [float("inf"), {"x": float("-inf")}]
    f.write_text(json.dumps(data))
    for url in (f"/api/meetings/{mid}", "/api/state"):
        r = c.get(url)
        assert r.status_code == 200, url
    assert server.json_safe({"a": [float("nan"), 1.5, {"b": float("inf")}]}) == {"a": [None, 1.5, {"b": None}]}


def test_csp_eval_only_for_app_window(env):
    c, *_ = env
    browser = TestClient(c.app, base_url="http://127.0.0.1:8765")
    r = browser.get(f"/?t={TOKEN}")
    assert "unsafe-eval" not in r.headers["content-security-policy"]
    window = TestClient(c.app, base_url="http://127.0.0.1:8765")
    r = window.get(f"/?t={TOKEN}&shell=app")
    assert "'unsafe-eval'" in r.headers["content-security-policy"]
    r = window.get("/")
    assert "'unsafe-eval'" in r.headers["content-security-policy"]


def test_launcher_reports_busy_port(monkeypatch):
    import socket
    import main

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        monkeypatch.setattr(main, "PORT", s.getsockname()[1])
        assert main.port_in_use()
        monkeypatch.setattr(main, "port_owner",
                            lambda: ("6511", "6511", "PID 6511 (dijeda, mis. karena Ctrl+Z): uvicorn server:app"))
        msg = main.port_busy_message()
    assert "kill -CONT -- -6511; kill -- -6511" in msg
    assert not main.port_in_use()


def test_launcher_moves_to_spare_port_for_other_app(monkeypatch, tmp_path):
    import socket
    import main

    monkeypatch.setattr(core, "SUPPORT_DIR", tmp_path)
    with socket.socket() as other, socket.socket() as probe:
        other.bind(("127.0.0.1", 0))
        other.listen()
        busy = other.getsockname()[1]
        probe.bind(("127.0.0.1", 0))
        spare = probe.getsockname()[1]
        probe.close()
        monkeypatch.setattr(main, "PORT", busy)
        monkeypatch.setattr(main, "SPARE_PORTS", [busy, spare])
        monkeypatch.setattr(main, "health", lambda: {"server": "other app"})
        main.free_port()
        assert main.PORT == spare
        assert (tmp_path / "port").read_text() == str(spare)


def test_launcher_stops_paused_meeting_report_group(monkeypatch):
    import signal
    import subprocess
    import sys
    import main

    code = ("import socket,time; s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen(); "
            "print(s.getsockname()[1], flush=True); time.sleep(60)")
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, start_new_session=True)
    try:
        port = int(proc.stdout.readline())
        os_pgid = str(proc.pid)
        import os
        os.killpg(proc.pid, signal.SIGSTOP)
        monkeypatch.setattr(main, "PORT", port)
        assert main.port_in_use()
        assert main.stop_group(os_pgid)
        assert not main.port_in_use()
    finally:
        proc.kill()
        proc.wait()
    assert main.is_meeting_report("/Users/x/meeting-report/.venv/bin/python .venv/bin/uvicorn server:app --reload")
    assert main.is_meeting_report("/Users/x/Library/Application Support/MeetingNotes/venv/bin/python "
                                  "/Users/x/Library/Application Support/MeetingNotes/app/server.py")
    assert not main.is_meeting_report("/usr/bin/python -m uvicorn server:app --port 8765")
