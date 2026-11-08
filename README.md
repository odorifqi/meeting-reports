# Meeting Report

**Rekam rapat, dapatkan transkrip dan laporan rapat yang rapi, tanpa audio Anda keluar dari Mac.**

Meeting Report mengubah rekaman suara atau video rapat menjadi tiga hal yang Anda butuhkan sesudah rapat: transkrip lengkap dengan nama pembicara, audio yang sudah dibersihkan dari bagian hening, dan laporan rapat siap kirim (Markdown dan Word). Transkripsi berjalan 100% di Mac Anda dengan Whisper, jadi rapat yang rahasia tetap rahasia.

## Kenapa Meeting Report

- **Privasi sejak awal.** Audio dan transkripsi tidak pernah meninggalkan Mac. Server aplikasi hanya mendengar di `127.0.0.1` dengan token sesi.
- **Data sensitif disaring otomatis.** Sebelum teks dikirim ke AI untuk dibuat laporan, nomor rekening, NIK, nomor HP, nomor kartu, NPWP, email, dan kata sensitif Anda diganti token seperti `<REKENING_1>`. Token dipulihkan lagi di Mac. Segmen bertanda Rahasia tidak dikirim sama sekali.
- **Anda yang memilih AI-nya.** Anthropic, OpenAI, Gemini, server kompatibel OpenAI, atau Ollama lokal (tanpa internet). Tidak ada teks yang dikirim sebelum Anda konfirmasi.
- **Transkrip yang bisa dipercaya.** Bagian suara yang terlewat Whisper ditranskrip ulang otomatis. Anda bisa edit, cari dan ganti, gabung atau pecah segmen, dan putar potongan suara per segmen.
- **Setiap perubahan tercatat.** Setiap simpan membuat versi baru. Bandingkan versi mana pun per kata, lalu pulihkan dengan satu klik.
- **Ramah buta warna.** Perbedaan tidak pernah ditandai dengan warna saja: dihapus merah dengan tanda −, ditambah biru dengan tanda +.

## Dibanding cara lain

| | Meeting Report | Layanan transkrip cloud | Perekam AI berbentuk alat | Catat manual |
| --- | --- | --- | --- | --- |
| Audio keluar dari perangkat | ✕ Tidak, tetap di Mac | ✓ Ya, diunggah ke server | ✓ Umumnya ya, ke cloud vendor | ✕ Tidak |
| Transkripsi tanpa internet | ✓ Ya | ✕ Tidak | ✕ Umumnya tidak | Tidak berlaku |
| Filter data sensitif sebelum ke AI | ✓ Otomatis | ✕ Jarang ada | ✕ Jarang ada | Tidak berlaku |
| Pilih penyedia AI sendiri (atau lokal) | ✓ 5 pilihan, termasuk Ollama | ✕ Ditentukan vendor | ✕ Ditentukan vendor | Tidak berlaku |
| Biaya | Gratis, hanya biaya API AI bila dipakai | Langganan bulanan | Harga alat + langganan | Waktu notulis |
| Versi dan perbandingan transkrip | ✓ Per kata | Terbatas | Terbatas | ✕ |

## Cara kerja

1. **Pilih rekaman.** Tarik file suara atau video rekaman layar (mp4, mov, webm; boleh di atas 1 GB). Isi judul, bahasa, dan daftar peserta bila ada.
2. **Tunggu transkripsi.** Pilih model **Cepat** (large-v3-turbo) atau **Akurat** (large-v3). Progres, perkiraan sisa waktu, dan log tampil langsung. Jendela boleh ditutup.
3. **Tinjau dan tandai pembicara.** Tekan 1 sampai 9 untuk menandai pembicara. Terima atau tolak saran ejaan lokal.
4. **Buat laporan.** Satu klik untuk ringkasan rapat, keputusan, dan tindak lanjut dengan PIC. Laporan ikut ditandai usang bila transkrip berubah sesudahnya.

## Hasil per rapat

Setiap rapat punya foldernya sendiri di `~/Documents/Meeting Report/`:

| File | Isi |
| --- | --- |
| `Transkrip.txt` | Transkrip terbaru dengan nama pembicara |
| `Transkrip asli.txt` | Hasil Whisper, tidak pernah diubah |
| `Ringkasan.md` / `.docx` | Laporan rapat terbaru |
| `Audio bersih.m4a` | Rekaman tanpa bagian hening (opsional) |
| `versions/`, `summaries/` | Semua versi transkrip dan laporan |

## Instalasi

Butuh Mac Apple Silicon, macOS 13 atau lebih baru, [Homebrew](https://brew.sh), dan ruang kosong sekitar 4 GB.

```bash
git clone https://github.com/odorifqi/meeting-reports.git
cd meeting-reports
./install.sh
```

Installer memasang ffmpeg, uv, dan Python 3.12, lalu membuat `~/Applications/Meeting Report.app`. Buka **Meeting Report** dari Finder > Applications. Model Whisper diunduh sekali saat pertama dipakai.

## Untuk pengembang

```bash
./run.sh dev    # server dengan auto-reload, dibuka di browser
./run.sh app    # jendela Mac memakai kode di repo ini
./run.sh test   # tes otomatis (pytest)
```

Coba tanpa data asli: `MN_OUTPUT_DIR=~/Desktop/mn-uji ./run.sh dev`. `tests/demo_server.py` menjalankan UI dengan Whisper dan AI palsu.

Arsitektur: FastAPI di `127.0.0.1:8765`, UI HTML/CSS/JS tanpa build step di jendela pywebview (WKWebView), transkripsi dengan mlx-whisper.

```
app/core.py      audio, buang hening, Whisper per bagian, penyedia AI, .docx
app/store.py     folder rapat, versi, ringkasan
app/filters.py   filter data sensitif dan pratinjau kirim
app/suggest.py   saran kata lokal dan saran AI
app/jobs.py      worker transkripsi dan ringkasan, event SSE
app/server.py    FastAPI dan keamanan lokal
app/main.py      launcher .app
app/static/      UI
tests/           pytest
```

## Kalau ada masalah

- Log server: `~/Library/Application Support/MeetingNotes/logs/server.log` (log tidak pernah berisi isi transkrip).
- Server berhenti sendiri 30 menit setelah jendela ditutup.
