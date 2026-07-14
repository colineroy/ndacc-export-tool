"""
run_mr.py
=========
Batch processing of NOG-DB variant ECC ozonesonde files from
the Marambio station (Antarctica, SMN Argentina), exporting to
WOUDC extCSV format.

Usage:
    python run_mr.py
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(_SRC))

from nogdb_mr_parser import load_nogdb_mr
from woudc_export import write_woudc_batch

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

INPUT_DIR  = DATA_DIR / "raw" / "mr"
OUTPUT_DIR = DATA_DIR / "output" / "woudc" / "mr"


# ---------------------------------------------------------------------------
# Process all MR files
# ---------------------------------------------------------------------------

print("=" * 55)
print("Marambio MR files")
print("=" * 55)

mr_files = sorted(INPUT_DIR.glob("*.txt"))
print(f"  {len(mr_files)} MR file(s) found in {INPUT_DIR}")

if not mr_files:
    print("  (no files to process)")
    sys.exit(0)

results = []
errors = []
for f in mr_files:
    try:
        meta, df = load_nogdb_mr(f)
        results.append((meta, df))
        print(f"  OK: {f.name} ({meta.launch_date}, {meta.serial_ecc})")
    except Exception as e:
        errors.append((f.name, str(e)))
        print(f"  FAIL: {f.name}: {e}")

print(f"\n  {len(results)} / {len(mr_files)} processed successfully")
if errors:
    print(f"  {len(errors)} error(s):")
    for name, msg in errors[:5]:
        print(f"    - {name}: {msg}")
    if len(errors) > 5:
        print(f"    ... and {len(errors) - 5} more")

if results:
    written = write_woudc_batch(results, output_dir=str(OUTPUT_DIR))
    print(f"  {len(written)} WOUDC file(s) generated in {OUTPUT_DIR}")

# Summary of Brewer availability
no_brewer = [meta for meta, _ in results if not meta.brewer_available]
if no_brewer:
    print(f"\n{len(no_brewer)} flight(s) without Brewer normalization:")
    for meta in no_brewer[:10]:
        print(f"  - {meta.launch_date} ({meta.serial_ecc})")

print(f"\nDone. Total: {len(results)} profile(s) processed.")
