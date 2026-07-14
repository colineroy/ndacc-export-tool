"""
run.py
======
Batch processing of SHARP (2024-2026) and NOG-DB (1988-1994) ozonesonde files
from the FMI Sodankyla station, exporting to WOUDC extCSV format.

Usage:
    python run.py [--sharp-dir <path>] [--nogdb-dir <path>] [--output-dir <path>]

Examples:
    # Process all data from default locations
    python run.py

    # Process only SHARP files
    python run.py --nogdb-dir ""
"""

import sys
from pathlib import Path

# Ensure src/ is on the Python path
_SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(_SRC))

from sharp_dqa import load_sondes
from nogdb_parser import load_nogdb
from woudc_export import write_woudc_batch
import csv

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

SHARP_INPUT_DIR  = DATA_DIR / "raw" / "sharp"
SHARP_OUTPUT_DIR = DATA_DIR / "output" / "woudc" / "24-26"

NOGDB_INPUT_DIR     = DATA_DIR / "raw" / "nogdb"
NOGDB_OUTPUT_DIR    = DATA_DIR / "output" / "woudc" / "89-94"
MANUAL_PARAMS_PATH  = BASE_DIR / "manual_params.csv"


def _load_manual_params(path: Path) -> dict:
    """Load manual parameters CSV -> {filename: {param: val}}."""
    if not path.exists():
        print(f"[INFO] No manual params file: {path}")
        return {}
    manual = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
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
                manual[fname] = params
    print(f"[INFO] {len(manual)} manual entries loaded from {path}")
    return manual


# ---------------------------------------------------------------------------
# 1. SHARP files - 2024-2026
# ---------------------------------------------------------------------------

print("=" * 55)
print("SHARP files (2024-2026)")
print("=" * 55)

sharp_files = sorted(SHARP_INPUT_DIR.glob("so*.q*"))
print(f"  {len(sharp_files)} SHARP file(s) found in {SHARP_INPUT_DIR}")

if sharp_files:
    sharp_results = load_sondes(sharp_files)
    print(f"  {len(sharp_results)} / {len(sharp_files)} processed successfully")
    written = write_woudc_batch(sharp_results, output_dir=str(SHARP_OUTPUT_DIR))
    print(f"  {len(written)} WOUDC file(s) generated in {SHARP_OUTPUT_DIR}\n")
else:
    print("  (no files)\n")


# ---------------------------------------------------------------------------
# 2. NOG-DB files - 1988-1994
# ---------------------------------------------------------------------------

print("=" * 55)
print("NOG-DB files (1988-1994)")
print("=" * 55)

nogdb_files = sorted(NOGDB_INPUT_DIR.glob("*"))
print(f"  {len(nogdb_files)} NOG-DB file(s) found in {NOGDB_INPUT_DIR}")

if nogdb_files:
    manual_params = _load_manual_params(MANUAL_PARAMS_PATH)
    nogdb_results = []
    errors = []
    for f in nogdb_files:
        try:
            meta, df = load_nogdb(f, manual_params=manual_params)
            nogdb_results.append((meta, df))
        except Exception as e:
            errors.append((f.name, str(e)))
    print(f"  {len(nogdb_results)} / {len(nogdb_files)} processed successfully")
    if errors:
        print(f"  {len(errors)} error(s):")
        for name, msg in errors[:5]:
            print(f"    - {name}: {msg}")
        if len(errors) > 5:
            print(f"    ... and {len(errors) - 5} more")

    written = write_woudc_batch(nogdb_results, output_dir=str(NOGDB_OUTPUT_DIR))
    print(f"  {len(written)} WOUDC file(s) generated in {NOGDB_OUTPUT_DIR}\n")


# ---------------------------------------------------------------------------
# 3. Summary
# ---------------------------------------------------------------------------

all_results = (sharp_results if sharp_files else []) + (nogdb_results if nogdb_files else [])
no_brewer = [meta for meta, _ in all_results if not meta.brewer_available]
if no_brewer:
    print(f"\n{len(no_brewer)} flight(s) without Brewer normalization"
          f" (likely polar night or Brewer unavailable):")
    for meta in no_brewer[:10]:
        print(f"  - {meta.launch_date} ({meta.serial_ecc})")

print(f"\nDone. Total: {len(all_results)} profile(s) processed.")
