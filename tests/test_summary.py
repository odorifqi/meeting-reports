import core
import suggest


def test_prompts_are_not_tied_to_one_organization():
    for text in (core.SUMMARY_SYSTEM, suggest.CLAUDE_SYSTEM):
        assert "bank" not in text.lower()
    assert "bukan rapat" in core.SUMMARY_SYSTEM
    assert core.whisper_prompt("xG, pressing", ["Andi"]) == "Istilah: xG, pressing. Peserta: Andi."
    assert core.whisper_prompt() is None


def _docx_lines(md, tmp_path):
    from docx import Document
    path = tmp_path / "r.docx"
    core.markdown_to_docx(md, path)
    return [p.text for p in Document(str(path)).paragraphs if p.text]


def test_docx_numbers_each_list_from_its_own_start(tmp_path):
    md = ("## Poin Pembahasan\n1. Satu\n\n1. Dua\n1. Tiga\n\n"
          "## Keputusan\n1. Putusan A\n2. Putusan B\n")
    lines = _docx_lines(md, tmp_path)
    assert lines == ["Poin Pembahasan", "1.\tSatu", "2.\tDua", "3.\tTiga",
                     "Keputusan", "1.\tPutusan A", "2.\tPutusan B"]


def test_docx_bold_with_italic_inside(tmp_path):
    from docx import Document
    path = tmp_path / "r.docx"
    core.markdown_to_docx("**Kelemahan *half space***. Lalu **Pressing** dan *miring*.", path)
    runs = [(r.text, bool(r.bold), bool(r.italic)) for r in Document(str(path)).paragraphs[0].runs]
    assert ("Kelemahan half space", True, False) in runs
    assert ("miring", False, True) in runs
    assert "*" not in "".join(t for t, _, _ in runs)


def test_report_notes_use_singular_for_one():
    import jobs
    ver = {"segments": [{"id": "s1", "start": 1, "end": 2, "text": "a", "speaker_id": "p1"},
                        {"id": "s2", "start": 3, "end": 4, "text": "b", "speaker_id": None}],
           "participants": [{"id": "p1", "name": "Sari"}]}
    md = jobs.postprocess_summary("# Report\n\nBody", {"title": "Report"}, ver, "m",
                                  {"masked": 1, "withheld": 1}, "en")
    assert "1 sensitive item was masked before sending and restored on this Mac; " \
           "1 confidential segment was not sent." in md
    assert "1 segment has no speaker tag." in md
    md_id = jobs.postprocess_summary("# Laporan\n\nIsi", {"title": "Laporan"}, ver, "m",
                                     {"masked": 2, "withheld": 1}, "id")
    assert "2 data sensitif disamarkan sebelum dikirim dan dipulihkan di Mac ini; 1 segmen rahasia tidak dikirim." in md_id


def test_chunk_bounds_reads_chunk_sec_when_called(monkeypatch):
    import numpy as np
    clean = core.CleanResult(audio=np.zeros(core.SR * 100, dtype=np.float32), regions=[(0.0, 100.0)],
                             original_sec=100.0, threshold_db=-40.0,
                             mapping=[(float(t), float(t), 10.0) for t in range(0, 100, 10)])
    assert len(core.chunk_bounds(clean)) == 1
    monkeypatch.setattr(core, "CHUNK_SEC", 20)
    assert len(core.chunk_bounds(clean)) == 5
