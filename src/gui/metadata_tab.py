import threading
import time
import tkinter as tk
from tkinter import ttk
from tkinter.filedialog import askdirectory, asksaveasfilename
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sharp_dqa import SondeMetadata, parse_sharp
from nogdb_parser import _parse_nogdb_raw, _nogdb_to_metadata
from nogdb_mr_parser import _parse_mr_raw, _mr_to_metadata

from .processing_tab import classify_files


def _extract_meta_row(fpath, station):
    """Extract one metadata row from a raw file.

    Returns dict with keys: Filename, Launch time, Serial number,
    Flow rate, Background current, T_lab, RH_lab, P_lab.
    """
    text = fpath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if station == "sdk" and fpath.name.lower().startswith("so") and \
       fpath.suffix.lower().startswith(".q"):
        meta, _ = parse_sharp(fpath)
    elif station == "sdk":
        result = _parse_nogdb_raw(lines)
        fname = fpath.name
        meta = _nogdb_to_metadata(result, fname, manual={})
    else:
        result = _parse_mr_raw(lines)
        meta = _mr_to_metadata(result, fpath.name)

    return {
        "Filename":              fpath.name,
        "Launch time":           str(meta.launch_datetime) if meta.launch_datetime else "",
        "Serial number":         meta.serial_ecc or "",
        "Flow rate":             str(meta.flow_rate_s100cm3) if meta.flow_rate_s100cm3 else "",
        "Background current":    str(meta.bg_post_ua) if meta.bg_post_ua else "",
        "T_lab":                 f"{meta.t_lab_c:.1f}" if meta.t_lab_c else "",
        "RH_lab":                f"{meta.rh_lab_pct:.1f}" if meta.rh_lab_pct else "",
        "P_lab":                 f"{meta.surface_pressure_hpa:.1f}" if meta.surface_pressure_hpa else "",
    }


def write_tables(rows, output_prefix):
    """Write CSV and XLSX from a list of dict rows."""
    import pandas as pd

    df = pd.DataFrame(rows)
    csv_path = Path(output_prefix).with_suffix(".csv")
    xlsx_path = Path(output_prefix).with_suffix(".xlsx")

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    try:
        df.to_excel(xlsx_path, index=False)
    except ImportError:
        xlsx_path = None

    return csv_path, xlsx_path


class MetadataTab(ttk.Frame):
    """Tab 2 - Metadata Tables."""

    def __init__(self, parent, i18n):
        super().__init__(parent)
        self.i18n = i18n
        self._running = False
        self._build_ui()

    def _build_ui(self):
        t = self.i18n
        pad = {"padx": 8, "pady": 4}

        row = ttk.Frame(self)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text=t("input_dir"), width=16).pack(side=tk.LEFT)
        self.input_dir_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.input_dir_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4)
        )
        ttk.Button(row, text=t("browse"), command=self._browse_input).pack(side=tk.RIGHT)

        row = ttk.Frame(self)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text=t("station"), width=16).pack(side=tk.LEFT)
        self.station_var = tk.StringVar(value="sdk")
        ttk.Radiobutton(row, text=t("station_sdk"), variable=self.station_var,
                        value="sdk").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(row, text=t("station_mr"), variable=self.station_var,
                        value="mr").pack(side=tk.LEFT)

        row = ttk.Frame(self)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text=t("output_prefix"), width=16).pack(side=tk.LEFT)
        self.prefix_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.prefix_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4)
        )
        ttk.Button(row, text=t("browse"), command=self._browse_output).pack(side=tk.RIGHT)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, **pad)

        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, **pad)

        self._log_widget = ScrolledText(
            log_frame, state=tk.DISABLED, wrap=tk.WORD,
            font=("Consolas", 9), height=14,
        )
        self._log_widget.pack(fill=tk.BOTH, expand=True)

        self._progress = ttk.Progressbar(self, mode="determinate", value=0)
        self._progress.pack(fill=tk.X, padx=8, pady=(0, 4))

        btn_row = ttk.Frame(self)
        btn_row.pack(fill=tk.X, **pad)
        self._gen_btn = ttk.Button(
            btn_row, text=t("generate"), command=self._start_generate,
            style="success.TButton",
        )
        self._gen_btn.pack(side=tk.RIGHT)

    def _browse_input(self):
        d = askdirectory(title=self.i18n("choose_input"))
        if d:
            self.input_dir_var.set(d)

    def _browse_output(self):
        d = asksaveasfilename(
            title=self.i18n("choose_output_file"),
            defaultextension=".csv",
            filetypes=[(self.i18n("csv_filter"), "*.csv"),
                       (self.i18n("xlsx_filter"), "*.xlsx"),
                       (self.i18n("all_filter"), "*.*")],
        )
        if d:
            p = Path(d)
            self.prefix_var.set(str(p.with_suffix("")))

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

    def _done(self):
        self._running = False
        self.after(0, lambda: self._gen_btn.configure(state=tk.NORMAL))
        self._progress["value"] = 0

    def _start_generate(self):
        if self._running:
            return

        input_dir = Path(self.input_dir_var.get().strip())
        if not input_dir.exists():
            self._log(f"[ERR] {self.i18n('not_found')}: {input_dir}")
            return

        prefix = self.prefix_var.get().strip()
        if not prefix:
            self._log("[ERR] Output prefix is required")
            return

        self._running = True
        self._gen_btn.configure(state=tk.DISABLED)
        self._log_widget.configure(state=tk.NORMAL)
        self._log_widget.delete("1.0", tk.END)
        self._log_widget.configure(state=tk.DISABLED)
        self._progress["value"] = 0

        th = threading.Thread(
            target=self._run, args=(input_dir, prefix), daemon=True,
        )
        th.start()

    def _run(self, input_dir, output_prefix):
        t0 = time.time()
        station = self.station_var.get()

        sharp, nogdb, mr, _ = classify_files(input_dir)
        if station == "sdk":
            files = sharp + nogdb
        else:
            files = mr

        if not files:
            self._log(f"[WARN] {self.i18n('no_files')}")
            self._done()
            return

        total = len(files)
        self._log(f"Extracting metadata from {total} file(s) ...")

        rows = []
        for i, fpath in enumerate(files):
            try:
                row = _extract_meta_row(fpath, station)
                rows.append(row)
                if (i + 1) % 50 == 0:
                    self._log(f"  {i+1}/{total}")
            except Exception as e:
                self._log(f"  ERR {fpath.name}: {e}")
            self._update_progress(i + 1, total)

        self._log(f"Writing {len(rows)} rows ...")
        csv_path, xlsx_path = write_tables(rows, output_prefix)

        self._log(f"  CSV : {csv_path}")
        if xlsx_path:
            self._log(f"  XLSX: {xlsx_path}")
        self._log(f"  {self.i18n('tables_written')}")
        elapsed = time.time() - t0
        self._log(f"  {self.i18n('elapsed')}: {elapsed:.1f}s")
        self._log(f"  {self.i18n('done')}.")

        self._done()

    def set_language(self, i18n):
        self.i18n = i18n
        self._rebuild_ui()

    def _rebuild_ui(self):
        for w in self.winfo_children():
            w.destroy()
        self._build_ui()
