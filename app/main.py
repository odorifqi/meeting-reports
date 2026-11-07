"""Meeting Notes: drag-and-drop meeting recorder companion for macOS.

Flow: drop audio -> remove silence -> transcribe locally (mlx-whisper) ->
ask the user: summary (Claude API) or transcript only -> save files.
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:  # library missing or tkdnd failed to load
    HAS_DND = False

LANGS = {"Bahasa Indonesia": "id", "English": "en", "Deteksi otomatis": None}


class App:
    def __init__(self) -> None:
        self.root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
        self.root.title("Meeting Notes")
        self.root.geometry("620x640")
        self.root.minsize(560, 560)
        self.cfg = core.load_config()
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.job: dict | None = None      # state of the last processed recording
        self.started_at = 0.0
        self._build_ui()
        self._register_open_document()
        self.root.after(100, self._drain_events)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        pad = {"padx": 14, "pady": 6}
        root = self.root

        self.drop = tk.Label(
            root, text="Tarik file rekaman ke sini\n(.m4a, .mp3, .wav, .mp4, .qta)",
            relief="groove", bd=2, height=6, font=("Helvetica", 15), fg="#555",
        )
        self.drop.pack(fill="x", **pad)
        if HAS_DND:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self._on_drop)
        else:
            self.drop.config(text="Klik \"Pilih File\" untuk memilih rekaman")

        row = ttk.Frame(root)
        row.pack(fill="x", **pad)
        ttk.Button(row, text="Pilih File…", command=self._pick_file).pack(side="left")
        ttk.Button(row, text="Dari Voice Memos…",
                   command=lambda: self._pick_file(core.VOICE_MEMOS_DIR)).pack(side="left", padx=6)

        opts = ttk.LabelFrame(root, text="Pengaturan")
        opts.pack(fill="x", **pad)

        self.var_clean = tk.BooleanVar(value=self.cfg["remove_silence"])
        self.var_min_sil = tk.DoubleVar(value=self.cfg["min_silence_sec"])
        self.var_save_clean = tk.BooleanVar(value=self.cfg["save_clean_audio"])
        lang_name = next((k for k, v in LANGS.items() if v == self.cfg["language"]), "Bahasa Indonesia")
        self.var_lang = tk.StringVar(value=lang_name)
        self.var_vocab = tk.StringVar(value=self.cfg["vocabulary"])

        r1 = ttk.Frame(opts); r1.pack(fill="x", padx=8, pady=3)
        ttk.Checkbutton(r1, text="Buang bagian hening lebih dari", variable=self.var_clean).pack(side="left")
        ttk.Spinbox(r1, from_=0.5, to=30, increment=0.5, width=5,
                    textvariable=self.var_min_sil).pack(side="left", padx=4)
        ttk.Label(r1, text="detik").pack(side="left")

        r2 = ttk.Frame(opts); r2.pack(fill="x", padx=8, pady=3)
        ttk.Checkbutton(r2, text="Simpan juga audio yang sudah dibersihkan",
                        variable=self.var_save_clean).pack(side="left")

        r3 = ttk.Frame(opts); r3.pack(fill="x", padx=8, pady=3)
        ttk.Label(r3, text="Bahasa rapat:").pack(side="left")
        ttk.Combobox(r3, textvariable=self.var_lang, values=list(LANGS), state="readonly",
                     width=18).pack(side="left", padx=6)

        r4 = ttk.Frame(opts); r4.pack(fill="x", padx=8, pady=(3, 8))
        ttk.Label(r4, text="Istilah/nama penting:").pack(side="left")
        ttk.Entry(r4, textvariable=self.var_vocab).pack(side="left", fill="x", expand=True, padx=6)

        self.status = ttk.Label(root, text="Siap.", font=("Helvetica", 13, "bold"))
        self.status.pack(anchor="w", **pad)
        self.progress = ttk.Progressbar(root, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=14)

        self.log = tk.Text(root, height=10, wrap="word", state="disabled",
                           font=("Menlo", 11), relief="flat", bg="#f4f4f4")
        self.log.pack(fill="both", expand=True, **pad)

        bottom = ttk.Frame(root)
        bottom.pack(fill="x", padx=14, pady=(0, 12))
        self.btn_summary = ttk.Button(bottom, text="Buat Ringkasan", state="disabled",
                                      command=self._summary_from_saved)
        self.btn_summary.pack(side="left")
        self.btn_open = ttk.Button(bottom, text="Buka Folder Hasil", state="disabled",
                                   command=self._open_output)
        self.btn_open.pack(side="left", padx=6)
        ttk.Button(bottom, text="API Key…", command=self._ask_api_key).pack(side="right")

    def _register_open_document(self) -> None:
        # Files dropped on the Dock icon arrive as an Apple Event.
        try:
            self.root.createcommand("::tk::mac::OpenDocument",
                                    lambda *paths: paths and self._start(paths[0]))
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ helpers

    def _log(self, text: str) -> None:
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _post(self, kind: str, *args) -> None:
        self.events.put((kind, args))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, args = self.events.get_nowait()
                getattr(self, f"_ev_{kind}")(*args)
        except queue.Empty:
            pass
        if self.busy and self.started_at:
            elapsed = int(time.time() - self.started_at)
            self.root.title(f"Meeting Notes  ·  {elapsed // 60}:{elapsed % 60:02d}")
        self.root.after(200, self._drain_events)

    def _ev_status(self, text: str, pct: float | None = None) -> None:
        self.status.config(text=text)
        if pct is None:
            if str(self.progress["mode"]) != "indeterminate":
                self.progress.config(mode="indeterminate")
                self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.config(mode="determinate", value=pct)

    def _ev_log(self, text: str) -> None:
        self._log(text)

    def _ev_error(self, text: str) -> None:
        self._finish()
        self._ev_status("Gagal.", 0)
        self._log("ERROR: " + text)
        if self.job:
            self.btn_summary.config(state="normal")
        messagebox.showerror("Meeting Notes", text)

    def _ev_transcribed(self) -> None:
        self._finish()
        self.btn_open.config(state="normal")
        self.btn_summary.config(state="normal")
        self._ev_status("Transkrip selesai.", 100)
        self._ask_summary()

    def _ev_summarized(self) -> None:
        self._finish()
        self.btn_summary.config(state="disabled")
        self._ev_status("Ringkasan selesai.", 100)
        self._open_output()

    def _finish(self) -> None:
        self.busy = False
        self.started_at = 0.0
        self.root.title("Meeting Notes")

    def _save_settings(self) -> None:
        try:
            min_sil = float(self.var_min_sil.get())
        except (tk.TclError, ValueError):
            min_sil = 2.0
        self.cfg.update({
            "remove_silence": bool(self.var_clean.get()),
            "min_silence_sec": max(0.5, min_sil),
            "save_clean_audio": bool(self.var_save_clean.get()),
            "language": LANGS.get(self.var_lang.get(), "id"),
            "vocabulary": self.var_vocab.get(),
        })
        core.save_config(self.cfg)

    # ------------------------------------------------------------------ input

    def _on_drop(self, event) -> None:
        paths = self.root.tk.splitlist(event.data)
        if paths:
            self._start(paths[0])

    def _pick_file(self, initial: Path | None = None) -> None:
        kwargs = {"title": "Pilih rekaman rapat"}
        if initial and initial.exists():
            kwargs["initialdir"] = str(initial)
        path = filedialog.askopenfilename(**kwargs)
        if path:
            self._start(path)

    def _start(self, path: str) -> None:
        if self.busy:
            messagebox.showinfo("Meeting Notes", "Masih memproses rekaman lain.")
            return
        src = Path(path)
        if not src.is_file():
            messagebox.showerror("Meeting Notes", f"File tidak ditemukan:\n{src}")
            return
        self._save_settings()
        self.busy = True
        self.started_at = time.time()
        self.btn_summary.config(state="disabled")
        self.log.config(state="normal"); self.log.delete("1.0", "end"); self.log.config(state="disabled")
        self._log(f"File: {src.name}")
        threading.Thread(target=self._run_transcription, args=(src, dict(self.cfg)), daemon=True).start()

    # ------------------------------------------------------------------ worker: transcription

    def _run_transcription(self, src: Path, cfg: dict) -> None:
        try:
            self._post("status", "Membaca audio…", None)
            audio = core.load_audio(str(src))

            if cfg["remove_silence"]:
                self._post("status", "Membuang bagian hening…", None)
            clean = core.clean_audio(audio, cfg["remove_silence"], cfg["min_silence_sec"])
            del audio
            if clean.clean_sec < 1:
                raise RuntimeError("Tidak ada suara percakapan yang terdeteksi di rekaman ini.")
            self._post("log", f"Durasi asli {core.fmt_ts(clean.original_sec)}, "
                              f"setelah dibersihkan {core.fmt_ts(clean.clean_sec)} "
                              f"(hening dibuang {core.fmt_ts(clean.removed_sec)}).")

            out_dir = core.make_output_dir(src)
            if cfg["remove_silence"] and cfg["save_clean_audio"] and clean.removed_sec > 1:
                core.save_audio_m4a(clean.audio, out_dir / "Audio bersih.m4a")
                self._post("log", "Audio bersih disimpan.")

            self._post("status", "Memuat model Whisper (pertama kali: unduh ~1,6 GB)…", None)

            def progress(done: int, total: int) -> None:
                pct = 100 * done / max(total, 1)
                self._post("status", f"Mentranskrip… bagian {min(done + 1, total)}/{total}", pct)

            segments = core.transcribe(clean, cfg["language"], cfg["vocabulary"],
                                       cfg["whisper_repo"], progress)
            if not segments:
                raise RuntimeError("Whisper tidak menghasilkan teks. Cek apakah rekamannya berisi suara.")

            text = core.format_transcript(segments, src.stem, clean)
            (out_dir / "Transkrip.txt").write_text(text, encoding="utf-8")
            words = sum(len(s["text"].split()) for s in segments)
            self._post("log", f"Transkrip disimpan: {len(segments)} segmen, ±{words} kata.")
            self.job = {"src": src, "out": out_dir, "transcript": text, "clean": clean}
            self._post("transcribed")
        except Exception as exc:  # surface everything to the user
            traceback.print_exc()
            self._post("error", str(exc) or exc.__class__.__name__)

    # ------------------------------------------------------------------ summary confirmation

    def _ask_summary(self) -> None:
        job = self.job
        if not job:
            return
        win = tk.Toplevel(self.root)
        win.title("Lanjut buat ringkasan?")
        win.transient(self.root)
        win.resizable(False, False)
        clean = job["clean"]
        msg = (f"Transkrip sudah tersimpan.\n\n"
               f"Durasi rapat: {core.fmt_ts(clean.original_sec)}\n"
               f"Bagian hening dibuang: {core.fmt_ts(clean.removed_sec)}\n\n"
               "Mau dibuatkan ringkasan dengan Claude API?\n"
               "Isi transkrip akan dikirim ke Anthropic.")
        ttk.Label(win, text=msg, justify="left", wraplength=380).pack(padx=18, pady=(16, 8))
        ttk.Label(win, text="Konteks tambahan (opsional), mis. nama rapat atau peserta:").pack(
            anchor="w", padx=18)
        ctx = tk.StringVar()
        ttk.Entry(win, textvariable=ctx, width=52).pack(padx=18, pady=(2, 12))
        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=18, pady=(0, 16))

        def transcript_only() -> None:
            win.destroy()
            self._log("Hanya transkrip. Ringkasan bisa dibuat nanti lewat tombol \"Buat Ringkasan\".")
            self._open_output()

        def do_summary() -> None:
            context = ctx.get()
            win.destroy()
            self._start_summary(context)

        ttk.Button(btns, text="Transkrip Saja", command=transcript_only).pack(side="left")
        ttk.Button(btns, text="Buat Ringkasan", command=do_summary).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", transcript_only)
        win.grab_set()

    def _summary_from_saved(self) -> None:
        if self.job and not self.busy:
            self._ask_summary()

    def _start_summary(self, context: str) -> None:
        key = core.get_api_key() or self._ask_api_key()
        if not key:
            self._log("Ringkasan dibatalkan: API key belum diisi.")
            return
        self.busy = True
        self.started_at = time.time()
        self.btn_summary.config(state="disabled")
        threading.Thread(target=self._run_summary, args=(key, context), daemon=True).start()

    def _run_summary(self, key: str, context: str) -> None:
        job = self.job
        try:
            self._post("status", "Membuat ringkasan dengan Claude…", None)
            md = core.summarize(job["transcript"], key, self.cfg["claude_model"], context)
            (job["out"] / "Ringkasan.md").write_text(md + "\n", encoding="utf-8")
            core.markdown_to_docx(md, job["out"] / "Ringkasan.docx")
            self._post("log", "Ringkasan disimpan (Ringkasan.md dan Ringkasan.docx).")
            self._post("summarized")
        except Exception as exc:
            traceback.print_exc()
            name = exc.__class__.__name__
            hint = " Cek API key lewat tombol \"API Key…\"." if "Authentication" in name else ""
            self._post("error", f"Gagal membuat ringkasan: {exc}{hint}")

    # ------------------------------------------------------------------ misc

    def _ask_api_key(self) -> str | None:
        key = simpledialog.askstring(
            "Anthropic API Key",
            "Tempel API key dari console.anthropic.com.\nKey disimpan di macOS Keychain.",
            parent=self.root, show="•")
        if key and key.strip():
            try:
                core.set_api_key(key)
                self._log("API key disimpan di Keychain.")
            except Exception as exc:
                messagebox.showerror("Meeting Notes", f"Gagal menyimpan ke Keychain: {exc}")
            return key.strip()
        return None

    def _open_output(self) -> None:
        if self.job:
            subprocess.run(["open", str(self.job["out"])], check=False)

    def run(self) -> None:
        if len(sys.argv) > 1:
            self.root.after(300, lambda: self._start(sys.argv[1]))
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
