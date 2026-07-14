"""
nogdb_parser.py
===============
Parser for NOG-DB format ECC ozonesonde files (1988-1994)
from the FMI Sodankyla station.

The NOG-DB format is the historical archive format used before
the Vaisala DigiCORA MW41 SHARP format. Files have a header
structured as documented in parluku2.m / SondeInfo.m (Kivi, FMI).

Output : SondeMetadata + pd.DataFrame compatible with woudc_export.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from sharp_dqa import SondeMetadata, apply_dqa, _is_fill as _sharp_is_fill


# ---------------------------------------------------------------------------
# Constants - Sodankyla station (same as woudc_export.py)
# ---------------------------------------------------------------------------

STATION_LAT  = 67.37
STATION_LON  = 26.63
STATION_HEIGHT = 179.0  # m asl

# Default values for fields missing from NOG-DB files
DEFAULT_PUMP_CORR_TABLE = "STOIC 1989"
DEFAULT_BG_METHOD       = "Unknown"
DEFAULT_SENSOR_TYPE     = "SPC"
DEFAULT_SST_GL          = 10.0    # 1% KI (historical standard)
DEFAULT_METEOSONDE      = "Vaisala RS80"


# ---------------------------------------------------------------------------
# NOG-DB numeric metadata indices (0-based, 27 parameters)
# ---------------------------------------------------------------------------

# NOG-DB common fill values (not all in sharp_dqa.FILL_NUMERIC)
NOGDB_FILL_VALUES = {9999.0, 99999.0, 999.9, 999.0, 9.9, 99.9, 99.99, 999.99}


def _is_nogdb_fill(val: float) -> bool:
    """Check if value is a NOG-DB fill (encompassing sharp_dqa fills + 999.0)."""
    for fv in NOGDB_FILL_VALUES:
        if abs(val - fv) < 1e-4 * max(abs(fv), 1):
            return True
    return False


# Maps from NOG-DB numeric parameter name (lowercase, stripped)
# to (target_field, transform_fn_or_None)
NUMERIC_PARAM_MAP: dict[str, tuple[str, Optional[str]]] = {
    "number of pressure levels":                         ("n_levels",              "int"),
    "launch time (ut hours from 0 hours on day given by date)": ("launch_hour_ut", "float"),
    "east longitude of station (degrees)":               ("lon",                   "float"),
    "latitude of station":                                ("lat",                   "float"),
    "wind speed at ground at launch (m/s)":               None,   # not used
    "temperature at ground at launch (c)":               None,   # not used
    "free lift for rubber balloon (g)":                  None,
    "dummy weight for plastic balloon  (g)":             None,
    "balloon volume for plastic balloon  (m^3)":         None,
    "balloon weight for rubber balloon (g)":             None,
    "interface parameter u1":                            None,
    "interface parameter u2":                            None,
    "interface parameter r1":                            None,
    "interface parameter r2":                            None,
    "interface parameter r3":                            None,
    "interface parameter k0":                            None,
    "interface parameter k1":                            None,
    "interface parameter k2":                            None,
    "amount of cathode solution (cm3)":                  ("cathode_vol_cm3",       "float"),
    "sensor air flow rate (s)":                         ("flow_rate_s100cm3",     "float"),
    "background sensor current (ua)":                   ("bg_post_ua",            "float"),
    "background surface pressure (hpa)":                ("surface_pressure_hpa",  "float"),
    "pressure correction factor":                        None,
    "temperature correction factor":                     None,
    "humidity correction factor":                        None,
    "total ozone from sondeprofile":                     ("col1_du",               "float"),
    "total ozone measured with dobson/brewer":           ("col2b_du",              "float"),
    # .z09 variant (Sodankyla 2024-2026 NOG-DB) - keys must be lowercase
    "concentration of cathode solution (mg/l)":                        ("sst_concentration_gl", "float"),
    "sensor air flow rate (ozonesonde pump only operating) (sec/100cm^3)": ("flow_rate_s100cm3", "float"),
    "background sensor current in the end of the pre-flight calibration (microamperes)": ("bg_post_ua", "float"),
    "launch time (decimal ut hours from 0 hours on day given by date)": ("launch_hour_ut",       "float"),
    "east longitude of station (decimal degrees)":                     ("lon",                   "float"),
    "latitude of station (decimal degrees)":                            ("lat",                   "float"),
    # Oct-Dec 1994 variant (ntot=41, nch=10, nnum=31)
    "sensor air flow rate (ozonesonde pump only operating)(s)":        ("flow_rate_s100cm3",     "float"),
    "background sensor current just before launch (microamperes)":     ("bg_post_ua",            "float"),
    "background sensor current (before cell is exposed to ozone (microamperes)": ("bg_pre_ua", "float"),
    "total ozone from sondeprofile (col1)":                            ("col1_du",               "float"),
    "total ozone measured with dobson/brewer (best value) (col2b)":   ("col2b_du",              "float"),
    "total ozone measured with dobson/brewer (daily mean) (col2a)":   ("col2a_du",              "float"),
}

# Maps from NOG-DB character parameter name to target field
CHAR_PARAM_MAP: dict[str, str] = {
    "lifting gas":                    None,
    "balloon material (rubber or plastic)": None,
    "balloon brand (e.g. totex, raven)":   None,
    "balloon type, (e.g. tx1200, cl0019)": None,
    "reason for discontinuation":          None,
    "weather condition at launch":         None,
    "balloon pretreatment":                None,
    "serial number of ecc":               "serial_ecc",
    "serial number of interface card":    None,
    "serial number of rs-80":             None,
    # .z09 variant (Sodankyla 2024-2026 NOG-DB) - keys must be lowercase
    "pump correction table":              "pump_corr_table",
    "background current correction method": "bg_method",
    "ground equipment":                   None,
    "place of box temperature measurement": None,
    "serial number of rs41":              None,
    "serial number of imet":              None,
}


def _clean_serial(raw: str) -> str:
    """Clean a serial number (strip zzz..., return UNKNOWN if empty)."""
    s = raw.strip()
    if not s or all(c.lower() == "z" for c in s) or s.upper() in ("UNKNOWN", "ZZZ", ""):
        return "UNKNOWN"
    return s


def _is_comment_line(line: str) -> bool:
    """Check if a line is a NOG-DB comment (starts with space/no token)."""
    s = line.strip()
    # Lines starting with 'C' in NOG-DB format
    return not s or s.startswith("C") or (not s[0:1].isalpha() and not s[0:1].isdigit() and s != "")


# ---------------------------------------------------------------------------
# Core parser - follows parluku2.m / SondeInfo.m logic
# ---------------------------------------------------------------------------

def parse_nogdb(
    fpath: Path,
    manual_params: Optional[dict] = None,
) -> tuple[SondeMetadata, pd.DataFrame]:
    """
    Parse a NOG-DB format file (1988-1994) into SondeMetadata + raw DataFrame.

    Parameters
    ----------
    fpath          : Path to the .F?? or .j?? or .K?? file
    manual_params  : Optional dict keyed by filename with overrides:
                     {filename: {ib2_ua: ..., flow_rate_s100cm3: ..., sensor_type: ..., sst_gl: ...}}

    Returns
    -------
    (meta, df) compatible with apply_dqa() and woudc_export.write_woudc_csv().
    """
    text = fpath.read_text(encoding="latin-1")
    lines = text.splitlines()
    meta = SondeMetadata(fpath=fpath)
    manual = manual_params or {}

    # ------------------------------------------------------------------
    # Parse header using parluku2.m structure
    # ------------------------------------------------------------------

    # Line 1-6: skip (format codes, PI, agency, instrument, project, flags)
    # Line 7 (index 6): launch date + conversion date
    date_parts = lines[6].strip().split()
    if len(date_parts) >= 3:
        try:
            meta.launch_date = date(
                int(date_parts[0]),
                int(date_parts[1]),
                int(date_parts[2]),
            )
        except ValueError:
            pass

    # Fallback: parse date from filename (SOYYMMDD or soYYMMDD)
    if meta.launch_date is None:
        import re
        m = re.search(r"(?:SO|so)(\d{2})(\d{2})(\d{2})", fpath.stem)
        if m:
            yy = int(m.group(1))
            if yy > 50:
                yy += 1900
            else:
                yy += 2000
            meta.launch_date = date(yy, int(m.group(2)), int(m.group(3)))

    # Line 7-11: skip remaining date numbers and lines 8-11
    line_idx = 12  # we are now at what would be line 12 (0-indexed)

    # Line 12: ncol (number of data columns - typically 8 or 9)
    ncol = int(lines[line_idx].strip())
    line_idx += 1

    # Lines 13-14: scaling factors and fill values (ncol each)
    # c = list(map(float, lines[line_idx].strip().split()))
    line_idx += 1
    # mis = list(map(float, lines[line_idx].strip().split()))
    line_idx += 1

    # Lines 15-(15+ncol-1): column names - skip
    line_idx += ncol  # skip column names + first column name already read? No.
    # Wait, actually lines 15-22 are the column name lines. Line 15 was already
    # consumed as a line in the earlier skip. Let me recount...

    # Actually, the parluku2.m code reads:
    # - Skip rest of line 14
    # - Read ncol column names (one per line)
    # So after line 14, we read ncol lines (lines 15-22 for ncol=8)

    # Line 23 (after ncol column names): ntot (total parameters = 37)
    # Line 24: nch (character parameters = 10)
    ntot = int(lines[line_idx].strip())
    line_idx += 1
    nch = int(lines[line_idx].strip())
    line_idx += 1
    nnum = ntot - nch  # 27

    # caux : nnum vs. read
    line_idx += 1  # skip caux line (flags - all 1s typically)

    # missaux : nnum vs. read
    line_idx += 1  # skip missaux line (fill values)
    # There are actually 3 lines of missaux (lines 28-30 split across 3 real lines)
    # caux was 1 line (line 25), missaux is 3 lines (lines 28-30)
    # The MATLAB fscanf reads 27 contiguous values across however many lines they span.
    # Since we already consumed line_idx for line 25 (caux), and line 28 would be
    # missaux, I need to account for lines 26-27 being part of caux as well...
    # Actually no - caux is 27 values from line 25, 26, 27.
    # missaux is 27 values from line 28, 29, 30.
    # But the code did fscanf for 27 values, which reads across newlines.

    # This is getting complicated with the line-by-line approach.
    # Let me re-read the file from the beginning using a more robust approach.

# ---------------------------------------------------------------------------
# Restart: NOG-DB parser - robust line-by-line following parluku2.m
# ---------------------------------------------------------------------------

def _parse_nogdb_raw(lines: list[str]) -> dict:
    """
    Parse NOG-DB header following parluku2.m exactly.

    Returns dict with keys:
        date   : (year, month, day)  - launch date
        ncol   : int - number of profile columns
        c      : list[float] - column scaling factors (ncol)
        mis    : list[float] - column fill values (ncol)
        col_names : list[str] - column names (ncol)
        ntot   : int - total parameters
        nch    : int - character parameters
        nnum   : int - numeric parameters
        caux   : list[float] - numeric parameter flags (nnum)
        missaux : list[float] - numeric parameter fill values (nnum)
        chlen  : list[int] - character field widths (nch)
        chstr  : list[str] - character placeholder strings (nch)
        nname  : list[str] - numeric parameter names (nnum)
        chname : list[str] - character parameter names (nch)
        ncom1  : int - comment block 1 count
        com1   : list[str] - comment block 1 lines
        ncom2  : int - comment block 2 count
        com2   : list[str] - comment block 2 lines
        nvalues: list[float] - numeric parameter values (nnum)
        chvalues: list[str] - character parameter values (nch)
    """
    idx = 0
    result = {}

    # Skip 6 lines
    idx += 6

    # Read 3 date ints from next line (line 7, the rest is conversion date to skip)
    da = list(map(int, lines[idx].strip().split()[:3]))
    result["date"] = tuple(da)
    idx += 1

    # Skip 4 more lines (lines 8-11) - the 5th "skip" in MATLAB is the
    # rest-of-line-7 after fscanf, already handled by idx += 1 above
    idx += 4

    # ncol
    ncol = int(lines[idx].strip())
    result["ncol"] = ncol
    idx += 1

    # c: ncol floats (may span multiple lines)
    c_values = []
    while len(c_values) < ncol:
        c_values.extend(map(float, lines[idx].strip().split()))
        idx += 1
    result["c"] = c_values[:ncol]

    # mis: ncol floats
    mis_values = []
    while len(mis_values) < ncol:
        mis_values.extend(map(float, lines[idx].strip().split()))
        idx += 1
    result["mis"] = mis_values[:ncol]

    # Column names: ncol lines (one per line)
    col_names = []
    for _ in range(ncol):
        col_names.append(lines[idx].strip())
        idx += 1
    result["col_names"] = col_names

    # ntot, nch
    ntot = int(lines[idx].strip())
    idx += 1
    nch = int(lines[idx].strip())
    idx += 1
    nnum = ntot - nch
    result["ntot"] = ntot
    result["nch"] = nch
    result["nnum"] = nnum

    # caux: nnum floats
    caux = []
    while len(caux) < nnum:
        caux.extend(map(float, lines[idx].strip().split()))
        idx += 1
    result["caux"] = caux[:nnum]

    # missaux: nnum floats
    missaux = []
    while len(missaux) < nnum:
        missaux.extend(map(float, lines[idx].strip().split()))
        idx += 1
    result["missaux"] = missaux[:nnum]

    # chlen: nch ints
    chlen = list(map(int, lines[idx].strip().split()))
    result["chlen"] = chlen[:nch]
    idx += 1

    # chstr: nch placeholder strings (zzz...)
    chstr = []
    for _ in range(nch):
        chstr.append(lines[idx])
        idx += 1
    result["chstr"] = chstr

    # nname: nnum parameter name lines
    nname = []
    for _ in range(nnum):
        nname.append(lines[idx].strip())
        idx += 1
    result["nname"] = nname

    # chname: nch parameter name lines
    chname = []
    for _ in range(nch):
        chname.append(lines[idx].strip())
        idx += 1
    result["chname"] = chname

    # ncom1
    ncom1 = int(lines[idx].strip())
    idx += 1
    com1 = []
    for _ in range(ncom1):
        com1.append(lines[idx])
        idx += 1
    result["ncom1"] = ncom1
    result["com1"] = com1

    # ncom2
    ncom2 = int(lines[idx].strip())
    idx += 1
    com2 = []
    for _ in range(ncom2):
        com2.append(lines[idx])
        idx += 1
    result["ncom2"] = ncom2
    result["com2"] = com2

    # Sodankyla marker
    sodankyla_line = lines[idx].strip()
    assert sodankyla_line.lower() == "sodankyla", (
        f"Expected 'Sodankyla' marker at line {idx+1}, got '{sodankyla_line}'"
    )
    result["sodankyla_idx"] = idx
    idx += 1

    # nvalues: nnum floats (3 lines after Sodankyla)
    nvalues = []
    while len(nvalues) < nnum:
        nvalues.extend(map(float, lines[idx].strip().split()))
        idx += 1
    result["nvalues"] = nvalues[:nnum]

    # chvalues: nch string lines
    chvalues = []
    for _ in range(nch):
        chvalues.append(lines[idx])
        idx += 1
    result["chvalues"] = chvalues

    # Data starts at current idx
    result["data_start"] = idx

    return result


# ---------------------------------------------------------------------------
# NOG-DB → SondeMetadata conversion
# ---------------------------------------------------------------------------

def _nogdb_to_metadata(
    result: dict,
    fname: str,
    manual: Optional[dict] = None,
) -> SondeMetadata:
    """
    Convert parsed NOG-DB header into a SondeMetadata dataclass.
    """
    meta = SondeMetadata(fpath=Path(fname))
    manual = manual or {}

    # Date
    yy, mm, dd = result["date"]
    try:
        meta.launch_date = date(yy, mm, dd)
    except ValueError:
        meta.launch_date = None

    # Map numeric parameters
    nname = [n.lower().strip() for n in result["nname"]]
    nvalues = result["nvalues"]
    for i, name in enumerate(nname):
        mapping = NUMERIC_PARAM_MAP.get(name)
        if mapping is None:
            continue
        target_field, transform = mapping
        val = nvalues[i]
        if val is None or _is_nogdb_fill(val):
            continue
        if transform == "int":
            val = int(round(val))
        elif transform == "float":
            val = float(val)
        setattr(meta, target_field, val)

    # Map character parameters
    chname = [c.lower().strip() for c in result["chname"]]
    chvalues = result["chvalues"]
    for i, name in enumerate(chname):
        target_field = CHAR_PARAM_MAP.get(name)
        if target_field is None:
            continue
        raw_val = chvalues[i] if i < len(chvalues) else ""
        setattr(meta, target_field, _clean_serial(raw_val))

    # Apply manual overrides
    file_key = Path(fname).name
    overrides = manual.get(file_key, {})
    for key, val in overrides.items():
        if key == "ib2_ua":
            meta.bg_post_ua = val
        elif key == "flow_rate_s100cm3":
            meta.flow_rate_s100cm3 = val
        elif key == "sensor_type":
            meta.sensor_type = val
        elif key == "sst_gl":
            meta.sst_concentration_gl = val
        elif key == "meteosonde":
            meta.meteosonde = val

    # Detect radiosonde type from serial number presence in char params
    # (applies to .z09 variant with RS41 or iMet serials)
    for i, name in enumerate(chname):
        name_lower = name.lower().strip()
        raw_val = chvalues[i] if i < len(chvalues) else ""
        cleaned = _clean_serial(raw_val)
        if cleaned == "UNKNOWN":
            continue
        if name_lower == "serial number of rs41":
            meta.meteosonde = "Vaisala RS41/DigiCORA MW41"
            break
        elif name_lower == "serial number of imet":
            meta.meteosonde = "iMet"
            break

    # Fill defaults for modern fields missing from NOG-DB
    if not meta.sensor_type:
        meta.sensor_type = DEFAULT_SENSOR_TYPE
    if meta.sst_concentration_gl is None or meta.sst_concentration_gl == 0:
        meta.sst_concentration_gl = DEFAULT_SST_GL
    if not meta.pump_corr_table:
        meta.pump_corr_table = DEFAULT_PUMP_CORR_TABLE
    if not meta.bg_method:
        meta.bg_method = DEFAULT_BG_METHOD
    if not meta.meteosonde:
        meta.meteosonde = DEFAULT_METEOSONDE

    # Parse launch hour from numeric parameter
    if meta.launch_hour_ut is not None:
        h = int(meta.launch_hour_ut)
        m = int((meta.launch_hour_ut - h) * 60)
        try:
            meta.launch_datetime  # trigger property
        except Exception:
            pass

    return meta


# ---------------------------------------------------------------------------
# Profile parsing
# ---------------------------------------------------------------------------

PROFILE_COLUMNS = [
    "pressure_hPa",
    "time_s",
    "altitude_gpm",
    "temp_C",
    "rh_pct",
    "temp_box_C",
    "PO3_raw_mPa",
    "wind_dir_deg",
    "wind_spd_ms",
]


def _parse_profile(lines: list[str], data_start: int) -> pd.DataFrame:
    """
    Parse the space-separated profile data starting at data_start.

    Returns DataFrame with 9 columns matching SHARP profile format.
    """
    data_rows = []
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) < 9:
            # Skip short/incomplete lines at end of file
            continue
        try:
            row = [float(p) for p in parts[:9]]
        except ValueError:
            continue
        data_rows.append(row)

    if not data_rows:
        return pd.DataFrame(columns=PROFILE_COLUMNS)

    df = pd.DataFrame(data_rows, columns=PROFILE_COLUMNS)

    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: np.nan if _sharp_is_fill(x) else x
        )

    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_nogdb(
    fpath: Path,
    manual_params: Optional[dict] = None,
    apply_dqa_flag: bool = True,
) -> tuple[SondeMetadata, pd.DataFrame]:
    """
    Load and optionally DQA-homogenize a NOG-DB ozonesonde file.

    Parameters
    ----------
    fpath            : Path to .F?? / .j?? / .K?? file
    manual_params    : dict mapping filename -> override params
    apply_dqa_flag   : If True, run apply_dqa() after parsing

    Returns
    -------
    (meta, df) where df is (DQA-homogenized if apply_dqa_flag=True).
    """
    text = fpath.read_text(encoding="latin-1")
    lines = text.splitlines()
    parsed = _parse_nogdb_raw(lines)

    meta = _nogdb_to_metadata(parsed, str(fpath), manual_params)
    df = _parse_profile(lines, parsed["data_start"])

    if apply_dqa_flag and not df.empty:
        df = apply_dqa(df, meta)

    return meta, df
