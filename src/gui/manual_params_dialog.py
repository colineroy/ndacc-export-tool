import csv
import tkinter as tk
from tkinter import ttk
from pathlib import Path


class ManualParamsDialog(tk.Toplevel):
    """Dialog for editing per-file manual parameters."""

    FIELDS = ("ib2_ua", "flow_rate_s100cm3", "sensor_type", "sst_gl", "meteosonde")

    def __init__(self, parent, input_dir, i18n):
        super().__init__(parent)
        self.i18n = i18n
        self.input_dir = Path(input_dir)
        self.result = None

        t = self.i18n
        self.title(t("manual_params"))
        self.transient(parent)
        self.grab_set()
        self.geometry("800x500")

        self._build_ui()
        self._load_manual_params()
        self._scan_files()
        self._sync_tree()

        self.wait_window()

    def _build_ui(self):
        t = self.i18n

        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=(8, 0))

        ttk.Label(top, text=t("input_dir")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(top, text=str(self.input_dir), font=("Segoe UI", 9, "bold")).pack(
            side=tk.LEFT
        )

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=8, pady=4)

        ttk.Button(btn_frame, text=t("select_all"), command=self._select_all).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(btn_frame, text=t("deselect_all"), command=self._deselect_all).pack(
            side=tk.LEFT
        )

        cols = ("selected",) + self.FIELDS
        self.tree = ttk.Treeview(
            self, columns=cols, show="tree headings", selectmode="none",
            height=16,
        )
        self.tree.heading("#0", text=self.i18n("filename"), anchor=tk.W)
        self.tree.column("#0", width=200, minwidth=150, anchor=tk.W)
        col_widths = {"selected": 50, "ib2_ua": 90, "flow_rate_s100cm3": 110,
                      "sensor_type": 100, "sst_gl": 70, "meteosonde": 120}
        for c in cols:
            self.tree.heading(c, text=c, anchor=tk.CENTER)
            self.tree.column(c, width=col_widths.get(c, 80), anchor=tk.CENTER)

        vsb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=4)
        vsb.pack(side=tk.LEFT, fill=tk.Y, pady=4)

        self._bind_edit_events()

        btn_row = ttk.Frame(self)
        btn_row.pack(fill=tk.X, padx=8, pady=(4, 8))

        ttk.Button(btn_row, text=t("save"), command=self._save).pack(
            side=tk.RIGHT, padx=(4, 0)
        )
        ttk.Button(btn_row, text=t("cancel"), command=self.destroy).pack(
            side=tk.RIGHT, padx=(4, 0)
        )

        self._params = {}
        self._all_files = []
        self._checkboxes = {}

    def _scan_files(self):
        from .processing_tab import classify_files
        sharp, nogdb, mr, _ = classify_files(self.input_dir)
        self._all_files = sorted((sharp or []) + (nogdb or []) + (mr or []))

    def _load_manual_params(self):
        path = Path(self.input_dir).parent / "manual_params.csv"
        if not path.exists():
            path = Path("manual_params.csv")
        if not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fname = row.get("filename", "").strip()
                if fname:
                    params = {}
                    for key in self.FIELDS:
                        val = row.get(key, "").strip()
                        if val:
                            params[key] = val
                    if params:
                        self._params[fname] = params

    def _sync_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for f in self._all_files:
            name = f.name
            sel = "☑" if name in self._params else "☐"
            vals = [sel]
            for key in self.FIELDS:
                vals.append(self._params.get(name, {}).get(key, ""))
            self.tree.insert("", tk.END, iid=name, text=name, values=vals)

    def _bind_edit_events(self):
        def on_click(event):
            col = self.tree.identify_column(event.x)
            row = self.tree.identify_row(event.y)
            if not row or col == "#0":
                return
            col_idx = int(col.replace("#", "")) - 1
            if col_idx == 0:
                self._toggle_checkbox(row)
                return
            self._edit_cell(row, col_idx)

        self.tree.bind("<Button-1>", on_click)

    def _toggle_checkbox(self, name):
        if name in self._params:
            del self._params[name]
        else:
            self._params[name] = {}
        self._sync_tree()

    def _edit_cell(self, name, col_idx):
        if col_idx < 1 or col_idx > len(self.FIELDS):
            return
        key = self.FIELDS[col_idx - 1]
        x, y, w, h = self.tree.bbox(name, column=f"#{col_idx + 1}")
        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, self._params.get(name, {}).get(key, ""))
        entry.focus_set()
        entry.selection_range(0, tk.END)

        def on_destroy(event=None):
            val = entry.get().strip()
            if name not in self._params:
                self._params[name] = {}
            if val:
                self._params[name][key] = val
            elif key in self._params.get(name, {}):
                del self._params[name][key]
            self._sync_tree()

        entry.bind("<Return>", on_destroy)
        entry.bind("<FocusOut>", on_destroy)
        entry.bind("<Escape>", lambda e: entry.destroy())

    def _select_all(self):
        for f in self._all_files:
            self._params.setdefault(f.name, {})
        self._sync_tree()

    def _deselect_all(self):
        self._params.clear()
        self._sync_tree()

    def _save(self):
        self.result = {
            fname: params for fname, params in self._params.items() if params
        }
        self.destroy()
