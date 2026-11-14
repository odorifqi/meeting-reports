"""Server texts in the UI languages (v1.7).

The browser sends its resolved UI language in the X-UI-Lang header. Background jobs
have no request, so they use the language of the last request (one user, one Mac).
Result file names and Transcript.txt labels do not use this module: they are English
in every UI language."""
from __future__ import annotations

import contextvars

LANGS = ("id", "en")
DEFAULT = "id"

_req_lang: contextvars.ContextVar[str | None] = contextvars.ContextVar("ui_lang", default=None)
_last = {"lang": DEFAULT}


def norm(lang: str | None) -> str | None:
    lang = (lang or "").strip().lower()[:2]
    return lang if lang in LANGS else None


def set_request_lang(lang: str | None) -> None:
    lang = norm(lang)
    _req_lang.set(lang)
    if lang:
        _last["lang"] = lang


def current() -> str:
    return _req_lang.get() or _last["lang"]


def plural(form: str | dict[str, str], n) -> str:
    """A text in one form, or {"one", "other"} English forms picked by n."""
    if isinstance(form, dict):
        return form["one"] if n == 1 else form["other"]
    return form


def tr(key: str, lang: str | None = None, **kw) -> str:
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    text = plural(entry.get(norm(lang) or current()) or entry[DEFAULT], kw.get("n"))
    return text.format(**kw) if kw else text


def dec(x: float, digits: int = 1, lang: str | None = None) -> str:
    """Decimal number with the decimal mark of the UI language."""
    s = f"{x:.{digits}f}"
    return s.replace(".", ",") if (norm(lang) or current()) == "id" else s


MESSAGES: dict[str, dict[str, str | dict[str, str]]] = {
    # names shown in the UI
    "prov_compat_name": {"id": "Kompatibel OpenAI (URL sendiri)", "en": "OpenAI-compatible (own URL)"},
    "prov_compat_short": {"id": "server kustom", "en": "custom server"},
    "prov_ollama_name": {"id": "Lokal di Mac ini (Ollama)", "en": "Local on this Mac (Ollama)"},
    "prov_ollama_short": {"id": "Ollama lokal", "en": "local Ollama"},
    "wm_cepat": {"id": "Cepat", "en": "Fast"},
    "wm_akurat": {"id": "Akurat", "en": "Accurate"},
    # transcript versions and changes
    "chg_added": {"id": "{n} peserta ditambah", "en": {"one": "{n} participant added", "other": "{n} participants added"}},
    "chg_renamed": {"id": "{n} nama peserta diubah", "en": {"one": "{n} participant name changed", "other": "{n} participant names changed"}},
    "chg_removed": {"id": "{n} peserta dihapus", "en": {"one": "{n} participant removed", "other": "{n} participants removed"}},
    "chg_tagged": {"id": "{n} segmen ditandai", "en": {"one": "{n} segment tagged", "other": "{n} segments tagged"}},
    "chg_edited": {"id": "{n} segmen diedit", "en": {"one": "{n} segment edited", "other": "{n} segments edited"}},
    "chg_merged": {"id": "{n} segmen digabung, dipecah, dihapus, atau ditambah",
                   "en": {"one": "{n} segment merged, split, deleted or added",
                          "other": "{n} segments merged, split, deleted or added"}},
    "chg_secret": {"id": "{n} tanda rahasia diubah", "en": {"one": "{n} confidential mark changed", "other": "{n} confidential marks changed"}},
    "ver_whisper": {"id": "Asli Whisper", "en": "Whisper original"},
    "ver_n": {"id": "versi {n}", "en": "version {n}"},
    "restored_from": {"id": "Dipulihkan dari {name}", "en": "Restored from {name}"},
    "restored_from_summary": {"id": "Dipulihkan dari ringkasan v{ver}", "en": "Restored from summary v{ver}"},
    "imported_v1": {"id": "Diimpor dari Meeting Notes v1", "en": "Imported from Meeting Notes v1"},
    "reason_low_conf": {"id": "Whisper ragu dengan kata ini, coba dengarkan",
                        "en": "Whisper is not sure about this word. Listen to it."},
    "reason_similar": {"id": "Mirip istilah atau nama peserta", "en": "Looks like a term or a participant name"},
    "reason_repeat": {"id": "Kata berulang", "en": "Repeated word"},
    "default_title": {"id": "Rapat", "en": "Meeting"},
    "pick_prompt": {"id": "Pilih rekaman", "en": "Select a recording"},
    # launcher loading screen (main.py)
    "loader_opening": {"id": "Membuka Meeting Report…", "en": "Opening Meeting Report…"},
    "loader_preparing": {"id": "Menyiapkan server…", "en": "Getting the server ready…"},
    "loader_starting": {"id": "Menyalakan server…", "en": "Starting the server…"},
    "loader_failed": {"id": "Meeting Report tidak bisa menyala", "en": "Meeting Report cannot start"},
    "loader_failed_hint": {"id": "Tutup jendela ini (⌘Q), atasi masalahnya, lalu buka Meeting Report lagi.",
                           "en": "Close this window (⌘Q), fix the problem, and then open Meeting Report again."},
    "bad_session_page": {"id": "<h3>Sesi tidak valid</h3><p>Buka Meeting Report dari aplikasinya, atau jalankan <code>./run.sh dev</code> lalu buka tautan yang dicetak di Terminal.</p>",
                         "en": "<h3>Session not valid</h3><p>Open Meeting Report from the app, or run <code>./run.sh dev</code> and open the link that it shows in Terminal.</p>"},
    # request guard
    "host_denied": {"id": "Host tidak diizinkan", "en": "Host not allowed"},
    "origin_denied": {"id": "Origin tidak diizinkan", "en": "Origin not allowed"},
    "bad_session": {"id": "Sesi tidak valid. Buka lewat Meeting Report.",
                    "en": "Session not valid. Open the page from Meeting Report."},
    # meetings and files
    "meeting_not_found": {"id": "Rapat tidak ditemukan", "en": "Meeting not found"},
    "picker_unavailable": {"id": "Pemilih file macOS tidak tersedia. Seret file ke jendela.",
                           "en": "The macOS file picker is not available. Drag the file into the window."},
    "file_not_found": {"id": "File tidak ditemukan", "en": "File not found"},
    "not_audio": {"id": "Format file tidak dikenali sebagai audio atau video",
                  "en": "The file format is not a known audio or video format"},
    "recording_not_found": {"id": "File rekaman tidak ditemukan", "en": "Recording file not found"},
    "recording_not_found_named": {"id": "File rekaman tidak ditemukan: {name}",
                                  "en": "Recording file not found: {name}"},
    "disk_full": {"id": "Ruang disk tidak cukup. Kosongkan sedikit ruang lalu coba lagi.",
                  "en": "Not enough disk space. Free some space, then try again."},
    "disk_full_results": {"id": "Ruang disk tidak cukup untuk menyimpan hasil. Kosongkan sedikit ruang lalu coba lagi.",
                          "en": "Not enough disk space to save the results. Free some space, then try again."},
    "busy_rename": {"id": "Rapat ini sedang diproses. Ubah judul setelah selesai.",
                    "en": "This meeting is being processed. Change the title when it is done."},
    "rename_failed": {"id": "Folder rapat tidak bisa diganti namanya. Tutup file di Finder lalu coba lagi.",
                      "en": "The meeting folder cannot be renamed. Close its files in Finder, then try again."},
    "busy_cancel_first": {"id": "Rapat ini sedang diproses. Batalkan dulu.",
                          "en": "This meeting is being processed. Cancel it first."},
    "busy": {"id": "Rapat ini sedang diproses", "en": "This meeting is being processed"},
    "retry_only_failed": {"id": "Hanya rapat yang gagal yang bisa diulang",
                          "en": "Only a failed meeting can be run again"},
    "finder_unavailable": {"id": "Finder tidak tersedia di mesin ini", "en": "Finder is not available on this computer"},
    "version_not_found": {"id": "Versi tidak ditemukan", "en": "Version not found"},
    "summary_version_not_found": {"id": "Versi ringkasan tidak ditemukan", "en": "Summary version not found"},
    "transcript_not_ready": {"id": "Transkrip belum tersedia", "en": "The transcript is not ready yet"},
    "transcription_not_done": {"id": "Transkripsi belum selesai", "en": "Transcription is not done yet"},
    "transcript_empty": {"id": "Transkrip kosong", "en": "The transcript is empty"},
    "segment_incomplete": {"id": "Segmen tidak lengkap", "en": "A segment is incomplete"},
    "save_first": {"id": "Simpan transkrip dulu", "en": "Save the transcript first"},
    "confirm_send": {"id": "Pengiriman ke layanan AI harus dikonfirmasi pengguna",
                     "en": "You must confirm before anything is sent to an AI service"},
    "bad_range": {"id": "Rentang waktu tidak valid", "en": "Time range not valid"},
    "bad_range_max": {"id": "Rentang waktu tidak valid (maksimal 10 menit)",
                      "en": "Time range not valid (10 minutes maximum)"},
    "original_not_found": {"id": "File rekaman asli tidak ditemukan", "en": "Original recording not found"},
    "whisper_busy": {"id": "Whisper sedang mentranskrip rapat lain. Coba lagi setelah selesai.",
                     "en": "Whisper is transcribing another meeting. Try again when it is done."},
    "retranscribe_failed": {"id": "Transkrip ulang gagal ({err})", "en": "Transcribe again failed ({err})"},
    "audio_not_found": {"id": "File audio tidak ditemukan", "en": "Audio file not found"},
    "term_empty": {"id": "Istilah kosong", "en": "The term is empty"},
    "title_empty": {"id": "Judul tidak boleh kosong.", "en": "Enter a title."},
    "title_bad_char": {"id": "Karakter {char} tidak bisa dipakai di judul karena dilarang di nama folder Mac.",
                       "en": "You cannot use {char} in a title, because Mac folder names do not allow it."},
    "title_too_long": {"id": "Judul maksimal {n} karakter.", "en": "Use {n} characters or fewer for the title."},
    # AI provider and API key
    "provider_unknown": {"id": "Penyedia AI tidak dikenal", "en": "Unknown AI provider"},
    "provider_no_key": {"id": "{provider} tidak memakai API key", "en": "{provider} does not use an API key"},
    "keychain_failed": {"id": "Gagal menyimpan ke Keychain", "en": "Could not save to Keychain"},
    "key_missing": {"id": "API key belum diisi", "en": "No API key yet"},
    "key_missing_open_settings": {"id": "API key {provider} belum diisi. Buka Pengaturan.",
                                  "en": "No {provider} API key yet. Open Settings."},
    "key_empty": {"id": "API key kosong", "en": "The API key is empty"},
    "key_format": {"id": "Format API key {provider} tidak dikenali (diawali {prefix})",
                   "en": "{provider} API key format not recognized (it starts with {prefix})"},
    "key_ok": {"id": "Terhubung ke {where} · model {model} · {secs} detik",
               "en": "Connected to {where} · model {model} · {secs} s"},
    # audio decoding and file check
    "ffmpeg_missing": {"id": "ffmpeg tidak ditemukan. Jalankan: brew install ffmpeg",
                       "en": "ffmpeg not found. Run: brew install ffmpeg"},
    "audio_read_failed": {"id": "Gagal membaca audio: {msg}", "en": "Could not read the audio: {msg}"},
    "no_audio": {"id": "File tidak berisi audio.", "en": "The file has no audio."},
    "probe_slow": {"id": "File terlalu lama dibaca. Mungkin rusak atau masih disalin.",
                   "en": "The file took too long to read. It may be damaged or still being copied."},
    "probe_bad": {"id": "File rusak atau formatnya tidak dikenali. Coba ekspor ulang, atau konversi dulu ke m4a.",
                  "en": "The file is damaged or its format is unknown. Export it again, or convert it to m4a first."},
    "video_no_sound": {"id": "Video ini tidak punya suara. Saat merekam layar, pastikan suara sistem atau mikrofon ikut direkam.",
                       "en": "This video has no sound. When you record the screen, also record the system sound or the microphone."},
    "file_no_sound": {"id": "File ini tidak berisi suara.", "en": "This file has no sound."},
    "too_short": {"id": "Rekaman terlalu pendek (kurang dari 1 detik).",
                  "en": "The recording is too short (less than 1 second)."},
    # job errors (stored in meeting.json in the language of that moment)
    "closed_during_job": {"id": "Aplikasi ditutup saat transkripsi berjalan. Bagian yang sudah selesai disimpan; lanjutkan dari sana.",
                          "en": "The app closed during transcription. Finished parts are saved; continue from there."},
    "closed_during_suggest": {"id": "Aplikasi ditutup saat saran AI dibuat. Coba lagi.",
                              "en": "The app closed while AI suggestions were being made. Try again."},
    "cancelled": {"id": "Dibatalkan. Bagian yang sudah selesai disimpan.",
                  "en": "Cancelled. Finished parts are saved."},
    # job log
    "log_reading": {"id": "Membaca rekaman", "en": "Reading the recording"},
    "log_video_audio_saved": {"id": "Suara video disimpan sebagai {name}", "en": "Video sound saved as {name}"},
    "log_video_audio_failed": {"id": "{name} gagal disimpan ({err})", "en": "Could not save {name} ({err})"},
    "log_durations": {"id": "Durasi {dur}, setelah buang hening {clean}", "en": "Duration {dur}, {clean} after silence removal"},
    "log_clean_saved": {"id": "{name} disimpan", "en": "{name} saved"},
    "log_clean_failed": {"id": "{name} gagal disimpan ({err})", "en": "Could not save {name} ({err})"},
    "log_model_download": {"id": "Mengunduh model {name} (±{gb} GB, sekali saja)",
                           "en": "Downloading model {name} (about {gb} GB, one time only)"},
    "log_model_ready": {"id": "Model {name} siap", "en": "Model {name} ready"},
    "log_model": {"id": "Model transkripsi: {label} ({name})", "en": "Transcription model: {label} ({name})"},
    "log_part_skip": {"id": "Bagian {i} dari {n} sudah ada, dilewati", "en": "Part {i} of {n} already done, skipped"},
    "log_part_start": {"id": "Mentranskrip bagian {i} dari {n}", "en": "Transcribing part {i} of {n}"},
    "log_gap_filled": {"id": "Celah {a}–{b} diisi ulang ({n} segmen)", "en": {"one": "Gap {a}–{b} transcribed again ({n} segment)",
                                                                        "other": "Gap {a}–{b} transcribed again ({n} segments)"}},
    "log_part_done": {"id": "Bagian {i} selesai ({n} segmen, {secs} detik)", "en": {"one": "Part {i} done ({n} segment, {secs} s)",
                                                                      "other": "Part {i} done ({n} segments, {secs} s)"}},
    "log_transcribed": {"id": "Transkripsi selesai: {n} segmen. Siap ditinjau.",
                        "en": {"one": "Transcription done: {n} segment. Ready for review.",
                               "other": "Transcription done: {n} segments. Ready for review."}},
    "log_cancelled": {"id": "Dibatalkan oleh pengguna", "en": "Cancelled by the user"},
    "log_failed": {"id": "Gagal: {err}", "en": "Failed: {err}"},
    "log_send_summary": {"id": "Kirim ringkasan ke {provider} ({host}), model {model}, {n} karakter",
                         "en": "Sending the summary request to {provider} ({host}), model {model}, {n} characters"},
    "log_answer_failed": {"id": "Jawaban gagal setelah {secs} detik: {kind}", "en": "No answer after {secs} s: {kind}"},
    "log_answer_ok": {"id": "Jawaban diterima dalam {secs} detik", "en": "Answer received in {secs} s"},
    "log_summary_done": {"id": "Ringkasan versi {ver} dibuat ({model})", "en": "Summary version {ver} made ({model})"},
    "log_summary_failed": {"id": "Ringkasan gagal: {err}", "en": "Summary failed: {err}"},
    # AI errors (_friendly)
    "ai_timeout": {"id": "{provider}{where} tidak mengirim jawaban dalam {mins} menit. Server mungkin sedang lambat atau model terlalu berat untuk transkrip sepanjang ini. Coba lagi, atau pilih model yang lebih cepat.",
                   "en": "{provider}{where} sent no answer in {mins} minutes. The server can be slow, or the model is too heavy for a transcript this long. Try again, or select a faster model."},
    "ai_ollama_down": {"id": "Ollama tidak berjalan di Mac ini. Buka Ollama, lalu coba lagi.",
                       "en": "Ollama is not running on this Mac. Open Ollama, then try again."},
    "ai_network": {"id": "Koneksi ke {provider}{where} terputus atau gagal dibuka ({detail}). Periksa internet dan alamat server di Pengaturan.",
                   "en": "The connection to {provider}{where} failed or stopped ({detail}). Check the internet connection and the server address in Settings."},
    "ai_network_generic": {"id": "jaringan", "en": "network"},
    "ai_empty": {"id": "{provider}{where} menjawab kosong. Periksa nama model di Pengaturan.",
                 "en": "{provider}{where} sent an empty answer. Check the model name in Settings."},
    "sug_reply_unreadable": {"id": "AI menjawab, tetapi daftar saran tidak bisa dibaca. Jawaban mentah disimpan di saran-claude-reply.json di folder rapat.",
                             "en": "The AI answered, but the suggestion list cannot be read. The raw answer is in saran-claude-reply.json in the meeting folder."},
    "sug_reply_cut_empty": {"id": "Jawaban AI terpotong sebelum ada saran yang utuh. Coba lagi, atau pakai model dengan batas jawaban lebih besar.",
                            "en": "The AI answer was cut off before one whole suggestion. Try again, or use a model with a larger answer limit."},
    "ai_said": {"id": " Pesan server: “{detail}”", "en": " Server message: “{detail}”"},
    "ai_key_rejected": {"id": "API key ditolak {provider} (HTTP {status}).{said}",
                        "en": "{provider} rejected the API key (HTTP {status}).{said}"},
    "ai_not_found": {"id": "Alamat atau model tidak ditemukan di {provider}{where} (HTTP 404). Isi alamat dasar saja, misalnya https://server/v1, dan periksa nama model.{said}",
                     "en": "Address or model not found at {provider}{where} (HTTP 404). Enter only the base address, for example https://server/v1, and check the model name.{said}"},
    "ai_rate_limit": {"id": "Batas pemakaian {provider} tercapai (HTTP 429). Coba lagi beberapa menit lagi.{said}",
                      "en": "{provider} usage limit reached (HTTP 429). Try again in a few minutes.{said}"},
    "ai_gateway_timeout": {"id": "Server {provider}{where} kehabisan waktu menunggu model (HTTP {status}). Coba lagi atau pilih model yang lebih cepat.{said}",
                           "en": "The {provider}{where} server timed out while it waited for the model (HTTP {status}). Try again, or select a faster model.{said}"},
    "ai_server_error": {"id": "Server {provider}{where} sedang bermasalah (HTTP {status}). Coba lagi.{said}",
                        "en": "The {provider}{where} server has a problem (HTTP {status}). Try again.{said}"},
    "ai_refused": {"id": "{provider}{where} menolak permintaan{status}.{said}",
                   "en": "{provider}{where} refused the request{status}.{said}"},
    "ai_key_rejected_plain": {"id": "API key ditolak {provider}. Periksa di Pengaturan.",
                              "en": "{provider} rejected the API key. Check it in Settings."},
    "ai_rate_limit_plain": {"id": "Batas pemakaian API tercapai. Coba lagi beberapa menit lagi.",
                            "en": "API usage limit reached. Try again in a few minutes."},
    "ai_no_connection": {"id": "Tidak bisa terhubung ke {provider}. Periksa koneksi internet.",
                         "en": "Cannot connect to {provider}. Check the internet connection."},
    "ai_busy": {"id": "Server {provider} sedang sibuk. Coba lagi.", "en": "The {provider} server is busy. Try again."},
    "ai_model_not_found": {"id": "Model tidak ditemukan di {provider}. Periksa nama model di Pengaturan.",
                           "en": "Model not found at {provider}. Check the model name in Settings."},
}
