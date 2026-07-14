"""
make_table.py
=============
Generate per-station CSV tables of sonde metadata including
flow rate, background current, T_lab, RH_lab, and P_lab.

Output:
  data/output/sodankyla_sondes.csv   (SHARP 24-26 + NOG-DB 89-94)
  data/output/marambio_sondes.csv    (MR files)

Usage:
  python make_table.py
"""

"""
make_table.py
=============
Generate per-station CSV/XLSX tables of sonde metadata including
flow rate, background current, T_lab, RH_lab, and P_lab.

Output in data/output/:
  sodankyla_1988_1994.{csv,xlsx}   (NOG-DB)
  sodankyla_2024_2026.{csv,xlsx}   (SHARP)
  marambio.{csv,xlsx}              (MR files)

Usage:
  python make_table.py
"""

import sys
from pathlib import Path
import csv

_SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(_SRC))

from sharp_dqa import load_sondes
from nogdb_parser import load_nogdb
from nogdb_mr_parser import load_nogdb_mr

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "output"

HEADERS = [
    "Filename", "Launch time", "Serial number",
    "Flow rate", "Background current",
    "T_lab", "RH_lab", "P_lab",
]


def _none_str(val):
    return "" if val is None else str(val)


def _make_rows_sodankyla_nogdb():
    """1988-1994 : NOG-DB raw files."""
    rows = []
    nogdb_dir = DATA_DIR / "raw" / "nogdb"
    nogdb_files = sorted(nogdb_dir.glob("*"))
    if not nogdb_files:
        return rows
    manual_params = {}
    manual_path = BASE_DIR / "manual_params.csv"
    if manual_path.exists():
        with open(manual_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fname = row.get("filename", "").strip()
                if not fname:
                    continue
                params = {}
                for key in ("ib2_ua", "flow_rate_s100cm3", "sensor_type", "sst_gl", "meteosonde"):
                    val = row.get(key, "").strip()
                    if val:
                        try:
                            params[key] = float(val) if key in ("ib2_ua", "flow_rate_s100cm3", "sst_gl") else val
                        except ValueError:
                            params[key] = val
                if params:
                    manual_params[fname] = params
    for f in nogdb_files:
        try:
            meta, _ = load_nogdb(f, manual_params=manual_params)
            rows.append({
                "Filename": meta.fpath.name,
                "Launch time": str(meta.launch_date or ""),
                "Serial number": meta.serial_ecc,
                "Flow rate": _none_str(meta.flow_rate_s100cm3),
                "Background current": _none_str(meta.bg_post_ua),
                "T_lab": _none_str(meta.t_lab_c),
                "RH_lab": _none_str(meta.rh_lab_pct),
                "P_lab": _none_str(meta.surface_pressure_hpa),
            })
        except Exception as e:
            print(f"  ERROR: {f.name}: {e}")
    rows.sort(key=lambda r: r["Launch time"])
    return rows


def _make_rows_sodankyla_sharp():
    """2024-2026 : SHARP raw files."""
    rows = []
    sharp_dir = DATA_DIR / "raw" / "sharp"
    sharp_files = sorted(sharp_dir.glob("so*.q*"))
    if not sharp_files:
        return rows
    results = load_sondes(sharp_files)
    for meta, _ in results:
        rows.append({
            "Filename": meta.fpath.name,
            "Launch time": str(meta.launch_date or ""),
            "Serial number": meta.serial_ecc,
            "Flow rate": _none_str(meta.flow_rate_s100cm3),
            "Background current": _none_str(meta.bg_post_ua),
            "T_lab": _none_str(meta.t_lab_c),
            "RH_lab": _none_str(meta.rh_lab_pct),
            "P_lab": _none_str(meta.surface_pressure_hpa),
        })
    rows.sort(key=lambda r: r["Launch time"])
    return rows


def _make_rows_marambio():
    rows = []
    mr_dir = DATA_DIR / "raw" / "mr"
    mr_files = sorted(mr_dir.glob("*.txt"))
    if mr_files:
        for f in mr_files:
            try:
                meta, _ = load_nogdb_mr(f)
                rows.append({
                    "Filename": meta.fpath.name,
                    "Launch time": str(meta.launch_date or ""),
                    "Serial number": meta.serial_ecc,
                    "Flow rate": _none_str(meta.flow_rate_s100cm3),
                    "Background current": _none_str(meta.bg_post_ua),
                    "T_lab": _none_str(meta.t_lab_c),
                    "RH_lab": _none_str(meta.rh_lab_pct),
                    "P_lab": _none_str(meta.surface_pressure_hpa),
                })
            except Exception as e:
                print(f"  ERROR: {f.name}: {e}")
    rows.sort(key=lambda r: r["Launch time"])
    return rows


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        w.writerows(rows)
    print(f"  {len(rows)} rows -> {path}")


def _write_xlsx(path, rows):
    import pandas as pd
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=HEADERS)
    df.to_excel(path, index=False, engine="openpyxl")
    print(f"  {len(rows)} rows -> {path}")


def main():
    # --- Sodankyla 1988-1994 (NOG-DB) ---
    print("=" * 55)
    print("Sodankyla 1988-1994 (NOG-DB)")
    print("=" * 55)
    nogdb_rows = _make_rows_sodankyla_nogdb()
    if nogdb_rows:
        _write_csv(OUTPUT_DIR / "sodankyla_1988_1994.csv", nogdb_rows)
        _write_xlsx(OUTPUT_DIR / "sodankyla_1988_1994.xlsx", nogdb_rows)
    else:
        print("  (no files)\n")

    # --- Sodankyla 2024-2026 (SHARP) ---
    print()
    print("=" * 55)
    print("Sodankyla 2024-2026 (SHARP)")
    print("=" * 55)
    sharp_rows = _make_rows_sodankyla_sharp()
    if sharp_rows:
        _write_csv(OUTPUT_DIR / "sodankyla_2024_2026.csv", sharp_rows)
        _write_xlsx(OUTPUT_DIR / "sodankyla_2024_2026.xlsx", sharp_rows)
    else:
        print("  (no files)\n")

    # --- Marambio ---
    print()
    print("=" * 55)
    print("Marambio sondes")
    print("=" * 55)
    mr_rows = _make_rows_marambio()
    if mr_rows:
        _write_csv(OUTPUT_DIR / "marambio.csv", mr_rows)
        _write_xlsx(OUTPUT_DIR / "marambio.xlsx", mr_rows)
    else:
        print("  (no files)\n")

    total = len(nogdb_rows) + len(sharp_rows) + len(mr_rows)
    print(f"\nDone. {total} sondes total.")


if __name__ == "__main__":
    main()
