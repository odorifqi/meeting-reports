# Meeting Notes

Aplikasi Mac untuk mengubah rekaman rapat menjadi transkrip dan laporan.

## Alur kerja

1. Tarik file rekaman (dari Voice Memos, QuickTime, dll.) ke jendela aplikasi.
2. Bagian hening dibuang otomatis (bisa dimatikan).
3. Audio ditranskrip **di laptop** dengan Whisper large-v3-turbo (MLX). Audio tidak dikirim ke mana pun.
4. Muncul konfirmasi: **Buat Ringkasan** (kirim transkrip ke Claude API) atau **Transkrip Saja**.
5. Hasil tersimpan di `~/Documents/Meeting Notes/<tanggal> - <nama file>/`:
   - `Transkrip.txt`: teks lengkap dengan timestamp. Timestamp mengacu ke rekaman asli, bukan ke audio yang sudah dibersihkan.
   - `Audio bersih.m4a`: rekaman tanpa bagian hening (opsional).
   - `Ringkasan.md` dan `Ringkasan.docx`: ringkasan, keputusan, action item, isu terbuka.

Kalau memilih "Transkrip Saja", ringkasan masih bisa dibuat nanti lewat tombol **Buat Ringkasan**, selama jendela aplikasi belum ditutup.

## Instalasi

Butuh: Mac Apple Silicon, macOS 13+, [Homebrew](https://brew.sh), ruang kosong ±4 GB.

```bash
cd ~/Downloads/meeting-notes
bash install.sh
```

Installer memasang ffmpeg dan uv lewat Homebrew, menyiapkan Python 3.12, lalu mengunduh model Whisper (~1,6 GB). Aplikasinya dibuat di `~/Applications/Meeting Notes.app`.

## API key Claude

Buat key di https://console.anthropic.com (perlu saldo/billing). Saat pertama kali membuat ringkasan, aplikasi meminta key dan menyimpannya di macOS Keychain. Untuk mengganti key, pakai tombol **API Key…**.

## Pengaturan

| Pengaturan | Default | Keterangan |
|---|---|---|
| Buang bagian hening | aktif, 2 detik | Jeda lebih lama dari ini dipotong. Sisa 0,4 detik di tiap sisi supaya kata tidak terpotong. Ambang suara menyesuaikan otomatis dengan tingkat bising ruangan. |
| Simpan audio bersih | aktif | Disimpan dalam kualitas suara rapat (16 kHz mono). |
| Bahasa rapat | Bahasa Indonesia | Pilih "Deteksi otomatis" kalau rapat campur bahasa. |
| Istilah/nama penting | kosong | Contoh: `BRICORE, i-SDM, RAYAFIN, Jagat Raya`. Membantu Whisper mengeja istilah dengan benar. |

Model Claude bisa diganti di `~/Library/Application Support/MeetingNotes/config.json` (key `claude_model`).

## Voice Memos

Tombol **Dari Voice Memos…** membuka folder rekaman Voice Memos. Kalau macOS menolak akses ke folder itu, ada dua cara:
- Di Voice Memos, klik kanan rekaman lalu pilih **Share > Save to Files** (atau drag ke Desktop), lalu tarik file itu ke aplikasi.
- Atau beri izin **Full Disk Access** untuk "Meeting Notes" di System Settings > Privacy & Security.

## Batasan

- Belum ada pemisahan pembicara (speaker diarization). Ringkasan hanya menyebut nama yang terucap.
- Transkripsi 1 jam rapat butuh waktu kira-kira beberapa menit di M5. Rekaman pertama lebih lama karena model dimuat.
- Ringkasan lewat Claude API mengirim teks transkrip ke Anthropic. Pastikan sesuai kebijakan data kantor.

## Masalah

Log error: `~/Library/Application Support/MeetingNotes/logs/error.log`

Hapus aplikasi:
```bash
rm -rf ~/Applications/"Meeting Notes.app" ~/Library/Application\ Support/MeetingNotes
rm -rf ~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo
security delete-generic-password -s MeetingNotes -a anthropic-api-key
```
