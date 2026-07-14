import threading
import time
import tkinter as tk
from tkinter import ttk
from tkinter.filedialog import askdirectory
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sharp_dqa import parse_sharp, apply_dqa as _apply_dqa
from nogdb_mr_parser import load_nogdb_mr
from nasaaims_export import write_nasa_aims_batch


def classify_files(dirpath):
    """Classify files in a directory by their type."""
    sharp = []
    mr = []
    ignored = []
    for f in sorted(dirpath.iterdir()):
        if not f.is_file():
            continue
        name = f.name.lower()
        if name.startswith("so") and f.suffix.startswith(".q"):
            sharp.append(f)
        elif f.suffix == ".txt":
            mr.append(f)
        else:
            ignored.append(f)
    return sharp, mr, ignored


class NasaAimsTab(ttk.Frame):
    """Tab 2 - NASA AIMS Export."""

    def __init__(self, parent, i18n):
        super().__init__(parent)
        self.i18n = i18n
        self._running = False
        self._build_ui()

    # ── UI construction ─────────────────────────────────────────────

    def _build_ui(self):
        t = self.i18n
        pad = {"padx": 8, "pady": 4}

        # ── Input directory ──
        row = ttk.Frame(self)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text=t("input_dir"), width=16).pack(side=tk.LEFT)
        self.input_dir_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.input_dir_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4)
        )
        ttk.Button(row, text=t("browse"), command=self._browse_input).pack(side=tk.RIGHT)

        # ── Output directory ──
        row = ttk.Frame(self)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text=t("output_dir"), width=16).pack(side=tk.LEFT)
        self.output_dir_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.output_dir_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4)
        )
        ttk.Button(row, text=t("browse"), command=self._browse_output).pack(side=tk.RIGHT)

        # ── Station ──
        row = ttk.Frame(self)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text=t("station"), width=16).pack(side=tk.LEFT)
        self.station_var = tk.StringVar(value="sdk")
        ttk.Radiobutton(row, text=t("station_sdk"), variable=self.station_var,
                        value="sdk").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(row, text=t("station_mr"), variable=self.station_var,
                        value="mr").pack(side=tk.LEFT)

        # ── Separator ──
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, **pad)

        # ── DQA checkbox ──
        self.do_dqa_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, text=t("apply_dqa"),
                        variable=self.do_dqa_var).pack(anchor=tk.W, **pad)

        # ── Separator ──
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, **pad)

        # ── Run button ──
        btn_row = ttk.Frame(self)
        btn_row.pack(fill=tk.X, **pad)
        self._run_btn = ttk.Button(
            btn_row, text="▶  " + t("run_aims"),
            command=self._start_processing,
            style="success.TButton",
        )
        self._run_btn.pack(pady=6)
        style = ttk.Style()
        style.configure("success.TButton", font=("Segoe UI", 11, "bold"), padding=8)

        btn_row.columnconfigure(0, weight=1)
        self._run_btn.grid(row=0, column=0)

        # ── Log panel ──
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, **pad)

        self._log_widget = ScrolledText(
            log_frame, state=tk.DISABLED, wrap=tk.WORD,
            font=("Consolas", 9), height=12,
        )
        self._log_widget.pack(fill=tk.BOTH, expand=True)

        # ── Progress bar ──
        self._progress = ttk.Progressbar(self, mode="determinate", value=0)
        self._progress.pack(fill=tk.X, padx=8, pady=(0, 4))

    # ── File dialogs ────────────────────────────────────────────────

    def _browse_input(self):
        d = askdirectory(title=self.i18n("choose_input"))
        if d:
            self.input_dir_var.set(d)

    def _browse_output(self):
        d = askdirectory(title=self.i18n("choose_output"))
        if d:
            self.output_dir_var.set(d)

    # ── Processing ──────────────────────────────────────────────────

    def _start_processing(self):
        if self._running:
            return

        input_dir = Path(self.input_dir_var.get().strip())
        if not input_dir.exists():
            self._log(f"[ERR] {self.i18n('not_found')}: {input_dir}")
            return

        output_dir = Path(self.output_dir_var.get().strip())
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self._log(f"[ERR] Cannot create output dir: {e}")
                return

        self._running = True
        self._run_btn.configure(state=tk.DISABLED)
        self._log_widget.configure(state=tk.NORMAL)
        self._log_widget.delete("1.0", tk.END)
        self._log_widget.configure(state=tk.DISABLED)
        self._progress["value"] = 0

        th = threading.Thread(target=self._run, args=(input_dir, output_dir),
                              daemon=True)
        th.start()

    def _log(self, msg):
        self.after(0, lambda: self._append_log(msg))

    def _append_log(self, msg):
        self._log_widget.configure(state=tk.NORMAL)
        self._log_widget.insert(tk.END, msg + "\n")
        self._log_widget.see(tk.END)
        self._log_widget.configure(state=tk.DISABLED)

    def _update_progress(self, value, maximum):
        self.after(0, lambda: self._set_progress(value, maximum))

    def _set_progress(self, value, maximum):
        if maximum > 0:
            self._progress["maximum"] = maximum
            self._progress["value"] = value

    def _processing_done(self):
        self._running = False
        self.after(0, lambda: self._run_btn.configure(state=tk.NORMAL))
        self._progress["value"] = 0

    def _run(self, input_dir, output_dir):
        t0 = time.time()
        station = self.station_var.get()
        do_dqa = self.do_dqa_var.get()

        # 1. Classify files
        sharp_files, mr_files, ignored = classify_files(input_dir)

        if station == "sdk":
            files = sharp_files
        else:
            files = mr_files

        if not files:
            self._log(f"[WARN] {self.i18n('no_files')}")
            self._processing_done()
            return

        total = len(files)
        if ignored:
            self._log(f"[INFO] Ignored {len(ignored)} unrecognised file(s)")

        self._log(f"{'='*50}")
        self._log(f"  {total} file(s) to process ({station})")
        self._log(f"{'='*50}")

        # 2. Parse each file
        results = []
        errs = []
        for i, fpath in enumerate(files):
            self._log(f"[{i+1}/{total}] {self.i18n('processing')}: {fpath.name} ...")
            try:
                if station == "sdk":
                    meta, df = parse_sharp(fpath)
                    if do_dqa:
                        df = _apply_dqa(df, meta)
                else:
                    meta, df = load_nogdb_mr(fpath, apply_dqa_flag=do_dqa)
                results.append((meta, df))
                self._log(f"       {self.i18n('summary_ok')}")
            except Exception as e:
                errs.append((fpath.name, str(e)))
                self._log(f"       ERR: {e}")
            self._update_progress(i + 1, total)

        self._log("")
        self._update_progress(total, total)

        # 3. Write NASA AIMS files
        if results:
            self._log(f"[{self.i18n('writing_aims')}] ...")
            written = write_nasa_aims_batch(
                results, output_dir=str(output_dir), station_key=station,
            )
            self._log(f"  {len(written)} {self.i18n('aims_written')} → {output_dir}")
        else:
            written = []

        # 4. Summary
        self._log("")
        self._log(f"{'─'*40}")
        ok_count = len(results)
        err_count = len(errs)
        self._log(f"  {ok_count} / {total} {self.i18n('summary_ok')}")
        if err_count:
            self._log(f"  {err_count} {self.i18n('summary_err')}:")
            for name, msg in errs[:5]:
                self._log(f"    - {name}: {msg}")

        elapsed = time.time() - t0
        self._log(f"  {self.i18n('total')}: {len(results)}")
        self._log(f"  {self.i18n('elapsed')}: {elapsed:.1f}s")
        self._log(f"{'─'*40}")
        self._log(f"  {self.i18n('done')}.")

        self._processing_done()

    def set_language(self, i18n):
        self.i18n = i18n
        self._rebuild_ui()

    def _rebuild_ui(self):
        for w in self.winfo_children():
            w.destroy()
        self._build_ui()
