"""
nogdb_mr_parser.py
==================
Parser for NOG-DB variant format ECC ozonesonde files from
the Marambio station (Antarctica, SMN Argentina).

These files (.txt) share the same NOG-DB structure as the
historical Sodankyla files but with different parameter counts:
  - Sodankyla: ntot=37, nch=10, nnum=27
  - Marambio:  ntot=57, nch=19, nnum=38

The station marker is "MBI" (not "Sodankyla").

Output: SondeMetadata + pd.DataFrame compatible with woudc_export.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from sharp_dqa import SondeMetadata, apply_dqa, _is_fill as _sharp_is_fill
from nogdb_parser import _clean_serial


# ---------------------------------------------------------------------------
# Marambio station constants
# ---------------------------------------------------------------------------

STATION_ID      = "233"
STATION_NAME    = "MARAMBIO"
STATION_COUNTRY = "ATA"
STATION_GAW_ID  = "MBI"
STATION_LAT     = -64.233
STATION_LON     = -56.623
STATION_HEIGHT  = 198.0

AGENCY           = "FMI-SMNA"
SCIENTIFIC_AUTHORITY = "Rigel Kivi/Ricardo Sanchez"


# ---------------------------------------------------------------------------
# Defaults for fields missing from file metadata
# ---------------------------------------------------------------------------

DEFAULT_PUMP_CORR_TABLE = "Original table, Komhyr 1986"
DEFAULT_BG_METHOD       = "Pressure dependent"
DEFAULT_SENSOR_TYPE     = "SPC"
DEFAULT_SST_GL          = 10.0    # 1% KI (historical standard)
DEFAULT_METEOSONDE      = "Vaisala DigiCORA MW41"


# ---------------------------------------------------------------------------
# NOG-DB fill values (same set as nogdb_parser)
# ---------------------------------------------------------------------------

NOGDB_FILL_VALUES = {9999.0, 99999.0, 999.9, 999.0, 9.9, 99.9, 99.99, 999.99}


def _is_nogdb_fill(val: float) -> bool:
    for fv in NOGDB_FILL_VALUES:
        if abs(val - fv) < 1e-4 * max(abs(fv), 1):
            return True
    return False


# ---------------------------------------------------------------------------
# Numeric parameter index map (0-based in nvalues array, nnum=38)
# Derived from column name order in MR file header
# ---------------------------------------------------------------------------

# MR numeric parameter names (in order):
#   0: Number of levels
#   1: Launch time
#   2: East Longitude
#   3: Latitude
#   4: Wind speed at ground
#   5: Temperature at ground
#   6: Free lift (rubber)
#   7: Dummy weight (plastic)
#   8: Balloon volume (plastic)
#   9: Balloon weight (rubber)
#  10: Cathode solution amount
#  11: Cathode solution concentration
#  12: Flow rate (calibrator + sonde)
#  13: Flow rate (sonde only)
#  14: bg pre
#  15: bg post
#  16: Time for surface O3
#  17: Surface O3 value
#  18: Surface pressure
#  19: Pressure correction (ground)
#  20: Temperature correction (ground)
#  21: Humidity correction (ground)
#  22: COL1
#  23: COL2A
#  24: COL2B
#  25: Correction factor
#  26: Lab T
#  27: Lab RH
#  28: Inlet T
#  29: Pump T
#  30-33: Reserved
#  34: Iref_0c
#  35: Iref_lin
#  36: Iref_quad
#  37: Rntc_25oC

NUMERIC_INDICES = {
    "n_levels":             0,
    "launch_hour_ut":       1,
    "station_lon":          2,
    "station_lat":          3,
    "surface_wind_ms":      4,
    "surface_temp_c":       5,
    "cathode_vol_cm3":     10,
    "sst_concentration_gl": 11,
    "flow_rate_cal_mLmin": 12,
    "flow_rate_s100cm3":   13,
    "bg_pre_ua":           14,
    "bg_post_ua":          15,
    "surface_pressure_hpa": 18,
    "col1_du":             22,
    "col2a_du":            23,
    "col2b_du":            24,
    "corr_factor":         25,
    "t_lab_c":             26,
    "rh_lab_pct":          27,
    "t_pump_c":            29,
}


# ---------------------------------------------------------------------------
# Character parameter index map (0-based in chvalues array, nch=19)
# ---------------------------------------------------------------------------

# MR character parameter names (in order):
#   0: Ground equipment
#   1: Pump correction table
#   2: Background current correction method
#   3: Vertical averaging/smoothing method
#   4: Place of box temperature measurement
#   5: Name of raw data file
#   6: Lifting gas
#   7: Balloon material
#   8: Balloon brand
#   9: Balloon type
#  10: Reason for discontinuation
#  11: Weather condition at launch
#  12: Balloon pretreatment
#  13: Serial number of ECC
#  14: Serial number of interface card
#  15: Serial number of sonde
#  16: Reserved
#  17: Reserved
#  18: Ozone sensor type

CHAR_INDICES = {
    "ground_equipment":     0,
    "pump_corr_table":      1,
    "bg_method":            2,
    "smoothing_method":     3,
    "box_temp_location":    4,
    "raw_file":             5,
    "lifting_gas":          6,
    "balloon_material":     7,
    "balloon_brand":        8,
    "balloon_type":         9,
    "discontinuation":     10,
    "weather":             11,
    "pretreatment":        12,
    "serial_ecc":          13,
    "serial_interface":    14,
    "serial_sonde":        15,
    "reserved1":           16,
    "reserved2":           17,
    "sensor_type":         18,
}


# ---------------------------------------------------------------------------
# Profile columns (same 9-column layout as SHARP/NOG-DB)
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


# ---------------------------------------------------------------------------
# Header parser
# ---------------------------------------------------------------------------

def _parse_mr_raw(lines: list[str]) -> dict:
    """
    Parse MR NOG-DB variant header following the same structure
    as _parse_nogdb_raw() but with MR-specific counts.

    Returns dict with keys:
        date         : (year, month, day)
        ncol         : int
        c            : list[float]
        mis          : list[float]
        col_names    : list[str]
        ntot         : int (= 57)
        nch          : int (= 19)
        nnum         : int (= 38)
        caux         : list[float]
        missaux      : list[float]
        chlen        : list[int]
        chstr        : list[str]
        nname        : list[str]
        chname       : list[str]
        ncom1        : int
        com1         : list[str]
        ncom2        : int
        com2         : list[str]
        nvalues      : list[float]
        chvalues     : list[str]
        data_start   : int
    """
    idx = 0
    result = {}

    # Skip 6 lines (PI, agency, instrument, project, station, flags)
    idx += 6

    # Line 7 (idx=6): date
    da = list(map(int, lines[idx].strip().split()[:3]))
    result["date"] = tuple(da)
    idx += 1

    # Skip 4 lines (lines 8-11)
    idx += 4

    # ncol
    ncol = int(lines[idx].strip())
    result["ncol"] = ncol
    idx += 1

    # c: ncol floats
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

    # Column names: ncol lines
    col_names = []
    for _ in range(ncol):
        col_names.append(lines[idx].strip())
        idx += 1
    result["col_names"] = col_names

    # ntot, nch (MR specific: 57, 19)
    ntot = int(lines[idx].strip())
    idx += 1
    nch = int(lines[idx].strip())
    idx += 1
    nnum = ntot - nch  # = 38
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

    # Station marker: "MBI"
    marker_line = lines[idx].strip()
    if marker_line != "MBI":
        # Some files may have variations, but standard is "MBI"
        pass
    result["marker"] = marker_line
    idx += 1

    # nvalues: nnum floats
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
# Convert parsed header -> SondeMetadata
# ---------------------------------------------------------------------------

def _mr_to_metadata(
    result: dict,
    fname: str,
) -> SondeMetadata:
    """Convert parsed MR header into SondeMetadata."""
    meta = SondeMetadata(fpath=Path(fname))

    # Date
    yy, mm, dd = result["date"]
    try:
        meta.launch_date = date(yy, mm, dd)
    except ValueError:
        meta.launch_date = None

    # Station info (Marambio)
    meta.station_id      = STATION_ID
    meta.station_name    = STATION_NAME
    meta.station_country = STATION_COUNTRY
    meta.station_gaw_id  = STATION_GAW_ID
    meta.station_lat     = STATION_LAT
    meta.station_lon     = STATION_LON
    meta.station_height  = STATION_HEIGHT
    meta.agency           = AGENCY
    meta.scientific_authority = SCIENTIFIC_AUTHORITY

    # Map numeric parameters by index
    nvalues = result["nvalues"]
    for key, idx in NUMERIC_INDICES.items():
        if idx >= len(nvalues):
            continue
        val = nvalues[idx]
        if _is_nogdb_fill(val):
            continue
        setattr(meta, key, val)

    # Map character parameters by index
    chvalues = result["chvalues"]
    for key, idx in CHAR_INDICES.items():
        if idx >= len(chvalues):
            continue
        raw_val = chvalues[idx]
        meta_val = raw_val.strip()
        # Treat zzz... as empty
        if meta_val.startswith("z") and all(c == "z" or c == "Z" for c in meta_val):
            meta_val = ""
        if key == "serial_ecc":
            meta_val = _clean_serial(meta_val)
        setattr(meta, key, meta_val)

    # Extract lat/lon from numeric parameters if available (override constants
    # with file's own values for precision)
    lat_idx = NUMERIC_INDICES.get("station_lat")
    lon_idx = NUMERIC_INDICES.get("station_lon")
    if lat_idx is not None and lat_idx < len(nvalues):
        lat_val = nvalues[lat_idx]
        if not _is_nogdb_fill(lat_val):
            meta.station_lat = lat_val
    if lon_idx is not None and lon_idx < len(nvalues):
        lon_val = nvalues[lon_idx]
        if not _is_nogdb_fill(lon_val):
            meta.station_lon = lon_val

    # Fill defaults
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

    # Parse launch hour
    if meta.launch_hour_ut is not None:
        h = int(meta.launch_hour_ut)
        m = int((meta.launch_hour_ut - h) * 60)
        try:
            meta.launch_datetime  # trigger property
        except Exception:
            pass

    return meta


# ---------------------------------------------------------------------------
# Profile parsing (reuses the same 9-column format)
# ---------------------------------------------------------------------------

def _parse_profile(lines: list[str], data_start: int) -> pd.DataFrame:
    """
    Parse space-separated profile data starting at data_start.
    Returns DataFrame with 9 columns matching SHARP profile format.
    """
    data_rows = []
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) < 9:
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

def load_nogdb_mr(
    fpath: Path,
    apply_dqa_flag: bool = True,
) -> tuple[SondeMetadata, pd.DataFrame]:
    """
    Load and optionally DQA-homogenize a Marambio MR ozonesonde file.

    Parameters
    ----------
    fpath            : Path to .txt file
    apply_dqa_flag   : If True, run apply_dqa() after parsing

    Returns
    -------
    (meta, df) where df is (DQA-homogenized if apply_dqa_flag=True).
    """
    text = fpath.read_text(encoding="latin-1")
    lines = text.splitlines()
    parsed = _parse_mr_raw(lines)

    meta = _mr_to_metadata(parsed, str(fpath))
    df = _parse_profile(lines, parsed["data_start"])

    if apply_dqa_flag and not df.empty:
        df = apply_dqa(df, meta)

    return meta, df
