# raw_to_woudc

DQA homogenization pipeline for ECC ozonesonde data from FMI Sodankyla and Marambio.
Converts raw SHARP (2024-2026), NOG-DB (1988-1994) and MR (2019-2022) files to WOUDC extCSV and NASA AIMS (.bXX) formats.

## Quick start

```bash
pip install -r requirements.txt
python gui.py          # graphical interface (WOUDC + NASA AIMS export)
```

## Command-line usage

### Single file processing (Python API)

```python
from pathlib import Path
sys.path.insert(0, "src")

# Sodankyla - SHARP format
from sharp_dqa import parse_sharp, apply_dqa
meta, df = parse_sharp("so240111.q10")
df = apply_dqa(df, meta)

# Marambio - MR format
from nogdb_mr_parser import load_nogdb_mr
meta, df = load_nogdb_mr("mr_20211020_1146.txt")

# Export to WOUDC
from woudc_export import write_woudc_csv
write_woudc_csv(meta, df, "output.csv")

# Export to NASA AIMS
from nasaaims_export import write_nasa_aims
write_nasa_aims(meta, df, output_dir=".", station_key="sdk")
```

### Batch processing (Sodankyla)

```bash
# With default paths (data/raw/sharp/ and data/raw/nogdb/)
python run.py

# With custom directories
python run.py --sharp-dir D:\sondes\sharp --nogdb-dir D:\sondes\nogdb --output-dir D:\sondes\woudc
```

### Concrete example

```bash
# --- WOUDC export ---

# Convert all SHARP files from a folder to WOUDC
python export.py woudc --sdk "D:\sondes\*.q*" -o "D:\sondes\woudc_output"

# Convert a single SHARP file
python export.py woudc --sdk "D:\sondes\so240111.q10" -o "D:\sondes\woudc_output"

# --- NASA AIMS export ---

# Convert all SHARP files to NASA AIMS (.bXX)
python export.py aims --sdk "D:\sondes\*.q*" -o "D:\sondes\aims_output"

# Convert a single SHARP file
python export.py aims --sdk "D:\sondes\so240111.q10" -o "D:\sondes\aims_output"

# --- Metadata tables ---

# Generate CSV/XLSX metadata tables (uses data/raw/ by default)
python make_table.py
```

### Batch processing (Marambio)

```bash
python run_mr.py
```

### Unified CLI

```bash
# WOUDC export (all stations)
python export.py woudc --sdk *.q* --mr *.txt

# NASA AIMS export
python export.py aims --sdk *.q* --mr *.txt
```

## Directory layout

```
raw_to_woudc/
  run.py                   # GUI launcher (WOUDC + NASA AIMS export)
  gui.py                   # Alternative entry point
  gui.spec                 # PyInstaller spec file
  manual_params.csv        # Manual parameters for NOG-DB files
  requirements.txt
  nasaaims/                # Reference NASA AIMS .bXX files
  src/
    sharp_dqa.py           # SHARP parsing + DQA homogenization
    nogdb_parser.py        # NOG-DB format parser (Sodankyla historical)
    nogdb_mr_parser.py     # MR format parser (Marambio)
    woudc_export.py        # WOUDC extCSV export
    nasaaims_export.py     # NASA AIMS format export
    gui/
      app.py               # Main window with tabbed interface
      i18n.py              # Internationalization (EN/FI/FR)
      processing_tab.py    # WOUDC export tab
      nasaaims_tab.py      # NASA AIMS export tab
      metadata_tab.py      # Metadata table viewer
      about_tab.py         # About / documentation tab
```

## Output formats

### WOUDC extCSV

Standard WOUDC OzoneSonde extCSV format with 11-column profile and full metadata blocks. Compatible with the WOUDC data repository.

### NASA AIMS (.bXX)

NASA Ames FFI 2160 format for NDACC submission.
- File naming: `soYYMMDD.bHH` where `HH` = UTC launch hour (e.g. `.b09` = 09:xx UTC)
- 109-line header (Sodankyla) or 112-line header (Marambio)
- 38 numeric auxiliary variables, 19 character auxiliary variables
- 9-column profile data (Pressure, Time, Height, Temp, RH, BoxTemp, O3, WindDir, WindSpd)

## Corrections applied

1. **Background current** - constant bg_post subtraction (Smit & O3S-DQA 2012)
2. **Pump efficiency** - STOIC 1989 table (Smit & O3S-DQA 2012, Table A1)
3. **Transfer function** - DMT-Z / SST 0.5% (Deshler et al. 2017)
4. **Brewer normalization** - COL2B/COL1 factor when available

## Data sources

| Station   | Period     | Format         | Parser              |
|-----------|------------|----------------|---------------------|
| Sodankyla | 2024-2026  | SHARP (.q*)    | `sharp_dqa.py`      |
| Sodankyla | 1988-1994  | NOG-DB (.F*)   | `nogdb_parser.py`   |
| Marambio  | 2019-2022  | MR (.txt)      | `nogdb_mr_parser.py`|

## Building an executable

```bash
pip install -r requirements.txt
pip install pyinstaller
pyinstaller gui.spec
```

The standalone executable will be created in the `dist/` directory.

## References

- Smit, H.G.J. and O3S-DQA Panel (2012). SPARC-IGACO-IOC Report.
- Deshler, T. et al. (2017), *AMT*, 10, 2021-2043.
- Poyraz, D. (2021): https://github.com/denizpoyraz/o3s-dqa-homogenization
