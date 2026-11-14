import pytest

import filters
import suggest


def red(**kw):
    return filters.Redactor(kw.get("enabled"), kw.get("words"))


def test_rekening_and_restore():
    r = red()
    out = r.apply("Dana masuk ke rekening 0331 0100 0412 hari Senin.")
    assert "0331" not in out and "‹REKENING_1›" in out
    assert filters.restore(out, r.tokens) == "Dana masuk ke rekening 0331 0100 0412 hari Senin."


def test_same_value_same_token():
    r = red()
    out = r.apply("rek 033101000412 dan lagi 0331 0100 0412")
    assert out.count("‹REKENING_1›") == 2 and "‹REKENING_2›" not in out


def test_money_not_masked():
    r = red()
    for s in ("plafon Rp 2500000000 disetujui", "sebesar 2.500.000.000 rupiah", "total 150000000 rupiah"):
        assert r.apply(s) == s


def test_nik_hp_email_npwp_card():
    r = red()
    out = r.apply("NIK 3174012345670001, HP 0812-3456-7890, email andi@contoh.co.id, "
                  "NPWP 01.234.567.8-901.000, kartu 4111 1111 1111 1111")
    for tok in ("‹NIK_1›", "‹HP_1›", "‹EMAIL_1›", "‹NPWP_1›", "‹KARTU_1›"):
        assert tok in out, out
    assert "3174" not in out and "4111" not in out and "@" not in out


def test_disabled_category_kept():
    r = red(enabled={"rekening": False})
    assert r.apply("rekening 0331 0100 0412") == "rekening 0331 0100 0412"


def test_custom_words():
    r = red(words=["PT Sinar Tani"])
    out = r.apply("Debitur pt sinar tani menunggak.")
    assert out == "Debitur ‹NAMA_1› menunggak."
    assert filters.restore(out, r.tokens) == "Debitur pt sinar tani menunggak."


def test_build_send_withholds_secret():
    meta = {"title": "Rapat KUR", "created": "2026-11-05T09:00:00"}
    ver = {"segments": [
        {"id": "s1", "start": 1, "end": 2, "text": "Halo semua", "speaker_id": "p1", "secret": False},
        {"id": "s2", "start": 3, "end": 4, "text": "rekening 0331 0100 0412", "speaker_id": None, "secret": True},
    ], "participants": [{"id": "p1", "name": "Bu Sari", "role": "Kadiv"}]}
    send = filters.build_send(meta, ver, {"redact": None, "sensitive_words": ""})
    assert "0331" not in send["transcript"]
    assert filters.SECRET_LINE in send["transcript"]
    assert "Bu Sari: Halo semua" in send["transcript"]
    assert "(Belum ditandai)" in send["transcript"]
    assert send["withheld"] == 1
    assert "tokens" not in filters.public_preview(send)


def test_local_suggestions():
    segs = [{"id": "s1", "text": "Kita bahas restrukturasi KUR dan dana dana", "start": 0, "end": 1}]
    out = suggest.local_suggestions(segs, [{"id": "p1", "name": "Pak Andi Wijaya"}],
                                    "restrukturisasi, KUR", {"s1": ["bahas"]})
    kinds = {(o["from"], o["to"]) for o in out}
    assert ("restrukturasi", "restrukturisasi") in kinds
    assert ("dana dana", "dana") in kinds
    assert ("bahas", None) in kinds


def test_claude_suggestions_restore_and_validate():
    meta = {"title": "Rapat"}
    ver = {"segments": [{"id": "s00001", "start": 0, "end": 1, "text": "pembiayaan untuk rek 0331 0100 0412 di cabang"},
                        {"id": "s00002", "start": 1, "end": 2, "text": "rahasia", "secret": True}],
           "participants": []}
    sent = {}

    def fake(system, user, key, model, max_tokens):
        sent["user"] = user
        return ('Berikut: [{"id":"s00001","from":"rek ‹REKENING_1›","to":"rekening ‹REKENING_1›","reason":"x"},'
                '{"id":"s00001","from":"cabang","to":"Cabang","reason":"kapital"},'
                '{"id":"s00002","from":"rahasia","to":"x"},'
                '{"id":"s00001","from":"tidak ada","to":"y"}]')
    items, send, reply = suggest.claude_suggestions(meta, ver, {}, "k", "m", call=fake)
    assert reply["complete"] and reply["received"] == 4 and reply["dropped"] == 2
    assert "0331" not in sent["user"]
    assert [(i["from"], i["to"]) for i in items] == [("rek 0331 0100 0412", "rekening 0331 0100 0412"),
                                                     ("cabang", "Cabang")]


def test_english_tokens_and_singular_segment():
    r = filters.Redactor(None, ["PT Sinar Tani"], "en")
    out = r.apply("PT Sinar Tani, account 0331 0100 0412, phone 0812-3456-7890, NIK 3174012345670001")
    for tok in ("‹NAME_1›", "‹ACCOUNT_1›", "‹PHONE_1›", "‹ID_1›"):
        assert tok in out, out
    assert filters.restore(out, r.tokens).startswith("PT Sinar Tani, account 0331 0100 0412")
    meta = {"title": "KUR"}
    ver = {"segments": [{"id": "s1", "start": 1, "end": 2, "text": "Hello", "speaker_id": "p1"},
                        {"id": "s2", "start": 3, "end": 4, "text": "Hi", "speaker_id": "p2"},
                        {"id": "s3", "start": 5, "end": 6, "text": "Yes", "speaker_id": "p2"}],
           "participants": [{"id": "p1", "name": "Sari"}, {"id": "p2", "name": "Andi"}]}
    head = filters.build_send(meta, ver, {"redact": None, "sensitive_words": ""}, lang="en")["header"]
    assert "- Sari | – | 1 segment\n" in head and "- Andi | – | 2 segments" in head
    head_id = filters.build_send(meta, ver, {"redact": None, "sensitive_words": ""})["header"]
    assert "- Sari | – | 1 segmen\n" in head_id


def test_parse_claude_cut_off_and_unreadable():
    items, complete = suggest.parse_claude('```json\n[{"id":"s1","from":"a","to":"b"}]\n```')
    assert complete and items == [{"id": "s1", "from": "a", "to": "b"}]
    # cut by the token limit: the whole objects are kept
    items, complete = suggest.parse_claude('[{"id":"s1","from":"a","to":"b"},{"id":"s2","from":"c","to"')
    assert not complete and items == [{"id": "s1", "from": "a", "to": "b"}]
    # a note with a bracket before the list does not hide the list
    items, complete = suggest.parse_claude('Segmen [s1] diperiksa.\n[{"id":"s1","from":"a","to":"b"}]')
    assert complete and len(items) == 1
    assert suggest.parse_claude("[]") == ([], True)
    for bad in ("Tidak ada saran.", "[ini bukan json]"):
        with pytest.raises(suggest.SuggestReplyError):
            suggest.parse_claude(bad)


def test_claude_suggestions_cut_off():
    meta = {"title": "Rapat"}
    ver = {"segments": [{"id": "s00001", "start": 0, "end": 1, "text": "bar reskrim memanggil"}], "participants": []}
    asked = {}

    def cut(system, user, key, model, max_tokens):
        asked["max"] = max_tokens
        return '[{"id":"s00001","from":"bar reskrim","to":"Bareskrim","reason":"nama lembaga"},{"id":"s000'
    items, _, reply = suggest.claude_suggestions(meta, ver, {}, "k", "m", call=cut)
    assert asked["max"] == suggest.SUGGEST_MAX_TOKENS >= 16000
    assert [(i["from"], i["to"]) for i in items] == [("bar reskrim", "Bareskrim")] and not reply["complete"]
    with pytest.raises(suggest.SuggestReplyError) as e:
        suggest.claude_suggestions(meta, ver, {}, "k", "m", call=lambda *a: '[{"id":"s00001","fr')
    assert e.value.raw.startswith("[{")
