# Meeting Report v1.3

Aplikasi Mac untuk rekaman rapat: transkrip lokal, editor transkrip, penanda peserta, dan laporan rapat. Sejak v1.2 aplikasi memakai server lokal (FastAPI di `127.0.0.1:8765`) dengan tampilan HTML di jendela Mac sendiri (pywebview, WKWebView).

## Yang tetap di Mac ini

- Audio dan transkripsi Whisper 100% lokal. Pilih model **Cepat** (large-v3-turbo, bawaan) atau **Akurat** (large-v3, sedikit lebih akurat tetapi 3–6× lebih lambat, ±3,1 GB diunduh sekali saat pertama dipakai). Model yang dipakai dicatat di `meeting.json` dan baris `Model` di `Transkrip.txt`.
- Server hanya mendengar di `127.0.0.1`, memakai token sesi dan cek Origin. Tidak bisa dibuka dari jaringan.
- Teks baru dikirim ke penyedia AI pilihan Anda (Anthropic, OpenAI, Gemini, server kompatibel OpenAI, atau Ollama lokal) setelah Anda konfirmasi (ringkasan atau saran AI), dan selalu lewat filter lokal dulu: nomor rekening, NIK, nomor HP, nomor kartu, NPWP, email, dan kata sensitif Anda diganti token seperti `‹REKENING_1›`, segmen bertanda Rahasia tidak dikirim, lalu token dipulihkan di Mac ini.
- API key (satu per penyedia) ada di Keychain macOS dan tidak pernah dikirim ke tampilan.
- Log tidak pernah berisi isi transkrip.

## Instalasi (pemakaian harian)

Butuh Mac Apple Silicon, macOS 13+, [Homebrew](https://brew.sh), ruang kosong sekitar 4 GB.

```bash
cd ~/meeting-report
./install.sh
```

Installer memasang ffmpeg dan uv, menyalin aplikasi ke `~/Library/Application Support/MeetingNotes/app`, menyimpan v1 sebagai cadangan di `app-v1/`, menyiapkan Python 3.12, dan membuat `~/Applications/Meeting Report.app` dengan ikonnya. `Meeting Notes.app` lama dipindah ke Trash. Model Whisper yang sudah terunduh dipakai ulang.

Buka **Meeting Report** dari Finder > Applications. Folder hasil sekarang `~/Documents/Meeting Report`. Saat pertama dibuka, isi `~/Documents/Meeting Notes` dipindah ke sana (diganti nama, tidak disalin), lalu folder rapat lama diganti nama sekali menjadi `tanggal jam - judul` (isi file tidak diubah). Hasil v1 ikut tampil di Riwayat.

## Menjalankan dari repo (pengembangan)

```bash
./run.sh dev    # server dengan auto-reload, dibuka di Chrome (mirip "npm run dev")
./run.sh app    # jendela Mac memakai kode di repo ini
./run.sh test   # tes otomatis
```

Mode dev memakai data asli di `~/Documents/Meeting Report`. Untuk mencoba dengan folder terpisah:

```bash
MN_OUTPUT_DIR=~/Desktop/mn-uji ./run.sh dev
```

## Alur

1. **Rapat Baru**: pilih atau tarik rekaman suara atau video rekaman layar (mp4, mov, webm; boleh di atas 1 GB), isi judul, model transkripsi (Cepat/Akurat), bahasa, buang hening, istilah penting, dan (opsional) daftar peserta. Urutan peserta = tombol 1 sampai 9 di editor (seret untuk mengurutkan; tombol P untuk mencari nama, berguna bila peserta lebih dari 9). Video dicek dulu (ada suara, codec, file rusak, ruang disk); bila ada lebih dari satu jalur suara, pilih salah satu atau gabung semua.
2. **Progres**: transkripsi per bagian ±10 menit, persen, perkiraan sisa waktu, log. Bagian suara yang terlewat Whisper (lebih dari 3 detik tanpa teks) otomatis ditranskrip ulang. Jendela boleh ditutup. Kalau gagal, coba lagi melanjutkan dari bagian yang gagal.
3. **Tinjau transkrip**: edit teks, cari dan ganti, gabung dan pecah segmen, tandai rahasia, putar potongan suara per segmen (Spasi), tandai pembicara (1 sampai 9, 0 hapus), terima atau tolak saran lokal, transkrip ulang celah yang masih kosong. Draf tersimpan otomatis.
4. **Simpan**: membuat versi 1. Lalu pilih **Buat Ringkasan**, **Transkrip Saja**, atau **Minta saran AI dulu** (opsional, rapat diberi tanda ✦ Disarankan AI).
5. **Edit lagi kapan saja**: versi hanya bertambah kalau isinya benar berubah. Kalau sudah ada ringkasan, aplikasi menawarkan **Perbarui ringkasan**; kalau ditunda, ringkasan diberi tanda usang dan `Ringkasan.md`/`.docx` diberi baris ⚠ di atasnya.
6. **Bandingkan**: diff berdampingan atau inline, per kata, untuk transkrip (asli Whisper, simpan terakhir, versi mana pun) dan ringkasan. Kanan otomatis versi terbaru; bila dua versi lama dibandingkan, tombol Pulihkan ada di kiri dan kanan. Memulihkan selalu membuat versi baru.

Warna diff aman untuk buta warna: dihapus merah tua dengan tanda −, ditambah biru/indigo dengan tanda +, kata yang berubah diberi latar lebih pekat dan kotak.

## Isi folder per rapat

```
~/Documents/Meeting Report/2026-11-05 1347 - Judul/
  Transkrip.txt          transkrip versi terbaru (dengan nama peserta)
  Transkrip asli.txt     hasil Whisper, tidak pernah diubah
  Ringkasan.md / .docx   ringkasan terbaru (baris ⚠ bila usang)
  Audio bersih.m4a       opsional
  Audio rapat.m4a        suara yang diambil dari video (untuk pemutaran)
  meeting.json           status, peserta, daftar ringkasan, log kirim
  versions/rev-N.json    setiap versi transkrip (rev-0 = Whisper)
  summaries/sum-N.md     setiap versi ringkasan
  draft.json             draf editor yang belum disimpan
```

Rekaman asli tidak disalin; aplikasi memutarnya dari lokasi awal (misalnya Voice Memos). Rekaman yang ditarik ke jendela disalin ke folder rapat sebagai `Rekaman asli.*`. Video selalu dibaca dari lokasinya (tidak disalin); di jendela Mac, video yang ditarik juga tidak disalin.

## Struktur kode

```
app/core.py      audio, buang hening, probe video, Whisper per bagian + isi celah, format Transkrip.txt, penyedia AI, .docx
app/store.py     folder rapat, versi (hash isi), ringkasan, baris usang, migrasi v1
app/filters.py   F15 filter data sensitif dan pratinjau kirim
app/suggest.py   F14 saran kata lokal dan saran AI
app/jobs.py      satu worker: transkripsi, ringkasan, saran AI; event SSE
app/server.py    FastAPI + keamanan lokal
app/main.py      launcher .app (server + jendela pywebview)
app/static/      UI (HTML, CSS, JS tanpa build step)
tests/           pytest; tests/demo_server.py menjalankan UI dengan Whisper dan AI palsu
```

## Kalau ada masalah

- Log server: `~/Library/Application Support/MeetingNotes/logs/server.log`
- Server tetap jalan selama ada proses, lalu berhenti sendiri 30 menit setelah jendela ditutup.
- Kembali ke v1 sementara: `~/Library/Application Support/MeetingNotes/venv/bin/python ~/Library/Application\ Support/MeetingNotes/app-v1/main.py`
