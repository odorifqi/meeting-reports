"""v1.7: both UI languages have every text, with the same placeholders."""
import json
import re
import subprocess
from pathlib import Path

import i18n

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
PH = re.compile(r"\{(\w+)\}")


def _forms(v):
    return list(v.values()) if isinstance(v, dict) else [v]


def test_server_messages_have_both_languages():
    for key, v in i18n.MESSAGES.items():
        assert set(v) == {"id", "en"}, key
        for form in _forms(v["id"]) + _forms(v["en"]):
            assert form.strip(), key
            assert set(PH.findall(form)) == set(PH.findall(v["id"])), key
        if isinstance(v["en"], dict):
            assert set(v["en"]) == {"one", "other"}, key


def test_tr_picks_english_singular():
    assert i18n.tr("chg_tagged", "en", n=1) == "1 segment tagged"
    assert i18n.tr("chg_tagged", "en", n=3) == "3 segments tagged"
    assert i18n.tr("chg_tagged", "id", n=1) == "1 segmen ditandai"


def test_tr_uses_request_language_and_falls_back():
    assert i18n.tr("cancelled", "en") != i18n.tr("cancelled", "id")
    assert i18n.tr("no-such-key", "en") == "no-such-key"
    assert i18n.norm("en-GB") == "en" and i18n.norm("fr") is None


def _ui_dict():
    js = (STATIC / "i18n.js").read_text()
    body = js[js.index("{", js.index("MR_I18N")): js.rindex("}") + 1]
    return json.loads(re.sub(r",\s*}$", "}", body.strip()))


def test_ui_dictionary_parity():
    d = _ui_dict()
    for key, v in d.items():
        assert set(v) == {"id", "en"}, key
        want = set(PH.findall(v["id"]))
        for form in _forms(v["en"]):
            assert form.strip(), key
            assert set(PH.findall(form)) <= want | {"nn", "n"}, key
        if isinstance(v["en"], dict):
            assert "other" in v["en"], key


def test_every_ui_key_used_in_app_js_exists():
    d = _ui_dict()
    js = (STATIC / "app.js").read_text()
    used = set(re.findall(r"_t\('([\w.]+)'", js))
    dynamic = {"status.", "set.out_", "set.conf_", "cat."}
    missing = {k for k in used if k not in d and not any(k == p for p in dynamic)}
    assert not missing, sorted(missing)


def test_app_js_parses():
    for f in ("i18n.js", "app.js"):
        r = subprocess.run(["node", "--check", str(STATIC / f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
