import importlib.util
import types
from pathlib import Path

import pytest

import core


def _fake_loop():
    seen = []

    class Options:
        def __init__(self, **kw):
            self.prompt = kw.get("prompt")
            seen.append(self.prompt)

    mod = types.SimpleNamespace(DecodingOptions=Options)

    def transcribe(windows):
        # mlx-whisper with condition_on_previous_text=False: the prompt is the initial
        # prompt in window 1 and empty after that (temperature fallback repeats a window)
        for i in range(windows):
            for _ in range(2 if i == 1 else 1):
                mod.DecodingOptions(prompt=[11, 12] if i == 0 else [], temperature=0.0)

    return mod, transcribe, seen


def test_initial_prompt_reaches_every_window():
    mod, transcribe, seen = _fake_loop()
    original = mod.DecodingOptions
    with core.carry_initial_prompt(mod):
        transcribe(4)
    assert seen == [[11, 12]] * 5
    assert mod.DecodingOptions is original


def test_without_prompt_nothing_changes():
    mod, _, seen = _fake_loop()
    with core.carry_initial_prompt(mod):
        mod.DecodingOptions(prompt=[])
        mod.DecodingOptions(prompt=[])
    assert seen == [[], []]


@pytest.mark.skipif(importlib.util.find_spec("mlx_whisper") is None, reason="mlx-whisper runs on Apple Silicon only")
def test_mlx_whisper_still_builds_options_per_window():
    import sys
    import mlx_whisper  # noqa: F401
    src = Path(sys.modules["mlx_whisper.transcribe"].__file__).read_text()
    assert 'decode_options["prompt"] = all_tokens[prompt_reset_since:]' in src
    assert "options = DecodingOptions(**kwargs, temperature=t)" in src
