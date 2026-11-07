"""Run the real server with fake Whisper and Claude, for UI checks without a Mac.

    python tests/demo_server.py /tmp/demo-root
"""
import os
import sys
import time
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mn-demo")
os.environ["MN_SUPPORT_DIR"] = str(root / "support")
os.environ["MN_OUTPUT_DIR"] = str(root / "out")
os.environ["MN_TOKEN"] = "demo-token-" + "x" * 32
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-demo")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import uvicorn  # noqa: E402

import core  # noqa: E402
import jobs as jobs_mod  # noqa: E402
import server  # noqa: E402
import store as store_mod  # noqa: E402

LINES = [
    ("Selamat pagi, kita mulai rapat koordinasi kredit mikro kuartal empat.", ["koordinasi"]),
    ("Agenda pertama soal restrukturasi KUR untuk wilayah timur.", ["restrukturasi"]),
    ("Realisasi kuartal ini sudah sembilan puluh dua persen dari target.", []),
    ("NPL wilayah timur naik ke tiga koma satu persen.", []),
    ("Pak Andi tolong siapkan laporan per cabang paling lambat Kamis.", []),
    ("Siap Bu, kami kirim Kamis sore.", []),
    ("Dana masuk ke rekening 0331 0100 0412 hari Senin.", []),
    ("Klien minta dihubungi di 0812 3456 7890.", []),
    ("Untuk debitur PT Sinar Tani sudah masuk restrukturisasi.", []),
    ("Baik kita lanjut ke agenda kedua soal top up.", ["top"]),
]


def fake_audio(path):
    sr = core.SR
    out = []
    for _ in range(len(LINES)):
        t = np.arange(int(sr * 4)) / sr
        out.append((0.3 * np.sin(2 * np.pi * 200 * t)).astype(np.float32))
        out.append(np.zeros(int(sr * 3), dtype=np.float32))
    return np.concatenate(out)


def fake_chunk(audio, language, prompt, repo, wc):
    time.sleep(1.5)
    n = len(audio) / core.SR
    k = len(LINES)
    return [{"start": i * n / k, "end": (i + 0.9) * n / k, "text": t, "avg_logprob": -0.3, "low_words": lw}
            for i, (t, lw) in enumerate(LINES)]


def fake_claude(system, user, key, model, max_tokens):
    time.sleep(1.5)
    if "JSON array" in system:
        return ('[{"id":"s00003","from":"sembilan puluh dua persen","to":"92%","reason":"angka"},'
                '{"id":"s00004","from":"tiga koma satu persen","to":"3,1%","reason":"angka"}]')
    return """# Rapat Koordinasi Kredit Mikro Q4

## Ringkasan Eksekutif
Rapat membahas realisasi KUR dan kenaikan NPL wilayah timur. Dana ke ‹REKENING_1› dijadwalkan Senin.

## Peserta
| Nama | Jabatan/Unit | Segmen |
|---|---|---|
| Bu Sari | Kadiv Mikro | 3 |
| ? Belum ditandai | – | 7 |

## Poin Pembahasan
1. **Realisasi KUR** [00:00:14–00:00:21]. Sudah 92% dari target.
2. **NPL timur** [00:00:21]. Naik ke 3,1%.

## Keputusan
1. Laporan per cabang dikirim Kamis.

## Action Items
| No | Tugas | PIC | Tenggat | Dasar PIC |
|---|---|---|---|---|
| 1 | Laporan per cabang | Pak Andi | Kamis | ◆ Ditunjuk dengan nama [00:00:28] |

## Isu Terbuka dan Risiko
- NPL wilayah timur perlu dipantau.

## Catatan Lain
- Tidak ada.
"""


st = store_mod.Store(root / "out")
bus = jobs_mod.Bus()
jb = jobs_mod.Jobs(st, bus, load_audio=fake_audio, transcribe_chunk=fake_chunk,
                   save_m4a=lambda a, p: Path(p).write_bytes(b""), claude=fake_claude,
                   api_key=lambda: "sk-ant-demo")
# small chunks so progress has several parts
core.CHUNK_SEC = 20
app = server.create_app(st, jb, os.environ["MN_TOKEN"])
print(f"http://127.0.0.1:8765/?t={os.environ['MN_TOKEN']}", flush=True)
uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
