"""Interactive Transcript in the Audio tab (v1.6): word timings, edits, time map, endpoint."""
from pathlib import Path

import numpy as np

import core
import sync
from test_server import env, wait  # noqa: F401  (fixture)


def words_for(text, a, b):
    toks = text.split()
    d = (b - a) / len(toks)
    return [[a + k * d, a + (k + 0.9) * d, " " + t] for k, t in enumerate(toks)]


def test_align_keeps_whisper_times_for_unchanged_words():
    w = words_for("Rilis ditahan sampai perbaikan lolos.", 10.0, 15.0)
    seg = {"id": "s1", "start": 10.0, "end": 15.0, "text": "Rilis ditunda sampai perbaikan lolos uji ulang."}
    out = sync.align([seg], w)[0]
    assert len(out["w"]) == len(seg["text"].split())
    assert out["w"][0] == [10.0, 10.9]                       # "Rilis" matched
    assert out["w"][2] == [round(w[2][0], 2), round(w[2][1], 2)]   # "sampai" matched
    assert w[0][1] <= out["w"][1][0] <= w[2][0]              # "ditunda" sits between its neighbours
    assert all(out["w"][k][0] <= out["w"][k + 1][0] for k in range(len(out["w"]) - 1))
    assert out["est"] is False


def test_align_without_words_is_estimated_and_spread():
    seg = {"id": "m1", "start": 2.0, "end": 6.0, "text": "satu dua tiga empat"}
    out = sync.align([seg], None)[0]
    assert out["est"] and out["w"][0][0] == 2.0 and abs(out["w"][-1][1] - 6.0) < 0.02


def test_words_go_to_the_segment_that_holds_them():
    segs = [{"id": "a", "start": 0, "end": 2, "text": "halo semua"},
            {"id": "b", "start": 2.2, "end": 4, "text": "mulai rapat"}]
    w = words_for("halo semua", 0, 2) + words_for("mulai rapat", 2.2, 4)
    out = sync.align(segs, w)
    assert out[0]["w"][1][0] < 2 and out[1]["w"][0][0] >= 2.2 and not out[1]["est"]


def test_time_map_round_trip():
    sr = core.SR
    tone = np.ones(sr * 3, dtype=np.float32) * 0.3
    a = np.concatenate([np.zeros(sr * 5, np.float32), tone, np.zeros(sr * 6, np.float32), tone])
    clean = core.clean_audio(a, True, 2.0)
    assert len(clean.mapping) == 2
    for t in (0.1, 1.5, clean.mapping[1][0] + 0.5, clean.clean_sec - 0.1):
        assert abs(clean.to_clean(clean.to_original(t)) - t) < 1e-6
    # a moment inside a removed silence goes to the start of the next kept span
    gap = clean.mapping[0][1] + clean.mapping[0][2] + 1.0
    assert clean.to_clean(gap) == clean.mapping[1][0]
    # older meetings: the same table comes back from regions.json
    rows = sync.rows_from_regions(clean.regions, len(a) / sr)
    assert [[round(x, 3) for x in r] for r in clean.mapping] == rows


def test_transcript_sync_endpoint(env):  # noqa: F811
    c, st, jb, src = env
    jb.transcribe_chunk = lambda audio, lang, prompt, repo, wc=True: [] if len(audio) / core.SR < 10 else [
        {"start": 0.5, "end": 3.0, "text": "Selamat pagi semuanya.", "low_words": [],
         "words": words_for("Selamat pagi semuanya.", 0.5, 3.0)},
        {"start": 6.5, "end": 9.0, "text": "Pak Andi tolong siapkan laporan.", "low_words": [],
         "words": words_for("Pak Andi tolong siapkan laporan.", 6.5, 9.0)},
    ]
    mid = c.post("/api/meetings", json={"source_path": str(src), "title": "Sinkron"}).json()["id"]
    wait(jb)
    k = c.get(f"/api/meetings/{mid}/transcript-sync").json()
    assert k["rev"] == 0 and k["has_words"] and len(k["segments"]) == 2
    s1 = k["segments"][1]
    assert not s1["est"] and len(s1["w"]) == 5 and s1["w"][0][0] > 6     # mapped to the original timeline
    m = k["map"]
    assert m and not m["derived"] and m["rows"] and m["rows"][1][1] > m["rows"][1][0]   # 4 s silence removed

    # edit a word and add a manual segment: timings of untouched words survive
    ed = c.get(f"/api/meetings/{mid}/editor").json()
    segs, parts = ed["base"]["segments"], ed["base"]["participants"]
    segs[1]["text"] = "Pak Andi tolong kirim laporan."
    segs.append({"id": "m1", "start": 12.0, "end": 14.0, "text": "Baik terima kasih.", "manual": True})
    assert c.post(f"/api/meetings/{mid}/save", json={"segments": segs, "participants": parts}).json()["rev"] == 1
    k2 = c.get(f"/api/meetings/{mid}/transcript-sync").json()
    assert k2["rev"] == 1 and k2["segments"][1]["w"][0] == s1["w"][0] and k2["segments"][2]["est"]
    words_file = st.path(mid) / "versions" / "words.json"
    assert words_file.exists() and "\n" not in words_file.read_text()


def test_retranscribe_adds_words(env):  # noqa: F811
    c, st, jb, src = env
    mid = c.post("/api/meetings", json={"source_path": str(src), "title": "Celah kata"}).json()["id"]
    wait(jb)
    jb.transcribe_chunk = lambda audio, lang, prompt, repo, wc=True: [
        {"start": 2.0, "end": 4.0, "text": "isi celah", "low_words": [], "words": [[2.0, 2.8, " isi"], [3.0, 3.9, " celah"]]}]
    c.post(f"/api/meetings/{mid}/retranscribe", json={"start": 9.0, "end": 14.0})
    w = st.read_words(mid)
    assert [x[2].strip() for x in w if 9 <= x[0] <= 14] == ["isi", "celah"]


def test_meeting_before_v22_has_no_words_but_still_works(env):  # noqa: F811
    c, st, jb, src = env
    mid = c.post("/api/meetings", json={"source_path": str(src), "title": "Lama"}).json()["id"]
    wait(jb)
    (st.path(mid) / "versions" / "words.json").unlink()
    (st.path(mid) / "versions" / "clean_map.json").unlink()
    k = c.get(f"/api/meetings/{mid}/transcript-sync").json()
    assert not k["has_words"] and all(s["est"] for s in k["segments"])
    assert k["map"]["derived"] and k["map"]["rows"]
