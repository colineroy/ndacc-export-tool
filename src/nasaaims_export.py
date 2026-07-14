"""
nasaaims_export.py
==================
Generate NASA Ames FFI 2160 format files (ozone sonde profiles)
for the NDACC / NASA AIMS database.

The format follows the NASA Ames 2160 convention used by the
Norwegian Institute for Air Research (NILU) ozonesonde pipeline:

    - 109-line header (FFI 2160) with 57 auxiliary variables
    - Station marker + 38 numeric + 19 character aux values
    - Profile data (9 fixed-width columns)

References:
    - NASA Ames FFI 2160: http://badc.nerc.ac.uk
    - NILU ozonesonde convention (soYYMMDD.bHH filename)

Author: Coline Roy - Internship FMI Sodankyla, 2026
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from sharp_dqa import SondeMetadata


# ---------------------------------------------------------------------------
# Station-specific configuration
# ---------------------------------------------------------------------------

_STATION_CFG = {
    "sdk": {
        "first_line_pi": "KIVI R.",
        "oname": "Kivi, Rigel",
        "org": "Finnish Meteorological Institute",
        "sname": "Vaisala DigiCORA MW41 + ECC",
        "mname": "FMI",
        "station_marker": "Sodankyla",
        "first_line_station": "SODANKYLA",
        "first_line_instr": "O3SONDE",
        "first_line_param": "OZONE",
    },
    "mr": {
        "first_line_pi": "SANCHEZ R.",
        "oname": "Rigel Kivi (FMI) - Ricardo Sanchez (SMN)",
        "org": "FMI - SMNA",
        "sname": "Vaisala DigiCORA MW41 + ECC",
        "mname": "Marambio",
        "station_marker": "MBI",
        "first_line_station": "MARAMBIO",
        "first_line_instr": "O3SONDE",
        "first_line_param": "OZONE",
    },
}


# ---------------------------------------------------------------------------
# NASA Ames 2160 fixed header (lines 2–107)
# ---------------------------------------------------------------------------

# nlhead = 106 (std lines 2-107) + 1 (nscoml) + nscoml + 1 (nncoml) + nncoml
_NLHEAD_SIMPLE = 108    # Sodankyla: nscoml=0, nncoml=0 → 106+1+0+1+0=108
_NLHEAD_MARAMBIO = 112  # Marambio: nscoml=2, nncoml=2 → 106+1+2+1+2=112
_FFI = 2160
_NV = 8
_NAUXV = 57
_NAUXC = 19
_NUMERIC_AUX = _NAUXV - _NAUXC  # 38

_VSCAL = " ".join("1" for _ in range(_NV))

_VMISS = "99999 99999 999.9 999 999.9 99.99 999 999.9"

_DV_NAMES = [
    "Time after launch (s)",
    "Geopotential height (gpm)",
    "Temperature (C)",
    "Relative humidity (%)",
    "Temperature inside styrofoam box (C)",
    "Ozone partial pressure (mPa)",
    "Horizontal wind direction (degrees)",
    "Horizontal wind speed (m/s)",
]

_ASCAL = " ".join("1" for _ in range(_NUMERIC_AUX))

# 38 numeric missing-value sentinels (exact from reference files)
_AMISS_NUM_LINES = [
    "9999 99.99 999.99 999.99 999.9 99.9 99999.9 99999.9 99999.9 99999.9 9.9 99.9",
    "99.99 99.99 9.999 9.999 99.9 99.99 9999.9 9.9 9.9 9.9 999.9 999.9 999.9 9.999",
    "99.9 999 999.9 999.9 99999.9 99999.9 99999.9 99999.9 99.99 9.999e+000 9.999e+000",
    "99999",
]

_LENA = "40 20 20 40 20 13 2 7 20 20 40 10 20 20 20 20 40 40 20"

# 19 character missing-value strings (zzzz... padded to field widths)
_CHAR_WIDTHS = [40, 20, 20, 40, 20, 13, 2, 7, 20, 20, 40, 10, 20, 20, 20, 20, 40, 40, 20]
_AMISS_CHAR = ["z" * w for w in _CHAR_WIDTHS]

_AUX_NAMES = [
    "Number of levels",
    "Launch time (Decimal UT hours from 0 hours on day given by DATE)",
    "East Longitude of station (decimal degrees)",
    "Latitude of station (decimal degrees)",
    "Wind speed at ground at launch (m/s)",
    "Temperature at ground at launch (C)",
    "Free lift for rubber balloon (g)",
    "Dummy weight for plastic balloon (g)",
    "Balloon volume for plastic balloon (m^3)",
    "Balloon weight for rubber balloon (g)",
    "Amount of cathode solution (cm3)",
    "Concentration of cathode solution (g/l)",
    "Sensor air flow rate (calibrator and ozonesonde pumps operating) (sec/100cm^3)",
    "Sensor air flow rate (ozonesonde pump only operating) (sec/100cm^3)",
    "Background sensor current before cell is exposed to ozone (microamperes)",
    "Background sensor current in the end of the pre-flight calibration (microamperes)",
    "Time the sonde was run for surface ozone (min)",
    "Surface ozone measured with the sonde prior to launch (mPa)",
    "Background surface pressure (hPa)",
    "Pressure correction at ground",
    "Temperature correction at ground",
    "Humidity correction at ground",
    "Total ozone from sondeprofile (COL1)",
    "Total ozone measured with Dobson/Brewer (daily mean) (COL2A)",
    "Total ozone measured with Dobson/Brewer (best value) (COL2B)",
    "Correction factor (COL2A/COL1 or COL2B/COL1) (NOT APPLIED TO DATA)",
    "Temperature in laboratory during sonde flow rate calibration",
    "Relative humidity in laboratory during sonde flow rate calibration",
    "Temperature at sonde inlet tube prior to launch (C)",
    "Temperature at sonde pump prior to launch",
    "Reserved",
    "Reserved",
    "Reserved",
    "Reserved",
    "Interface parameter Iref_0c",
    "Interface parameter Iref_lin",
    "Interface parameter Iref_quad",
    "Interface parameter Rntc_25oC",
    "Ground equipment",
    "Pump correction table",
    "Background current correction method",
    "Vertical averaging/smoothing method",
    "Place of box temperature measurement",
    "Name of raw data file",
    "Lifting gas",
    "Balloon material (RUBBER or PLASTIC)",
    "Balloon brand (e.g. TOTEX, RAVEN)",
    "Balloon type (e.g. TX1200, CL0019)",
    "Reason for discontinuation",
    "Weather condition at launch",
    "Balloon pretreatment",
    "Serial number of ECC",
    "Serial number of interface card",
    "Serial number of sonde",
    "Reserved",
    "Reserved",
    "Ozone sensor type",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_miss(val, fmt: str, missing: str) -> str:
    """Format a value or return the missing sentinel."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return missing
    return format(val, fmt)


# ---------------------------------------------------------------------------
# Header assembly
# ---------------------------------------------------------------------------

def _pad(s: str, width: int) -> str:
    """Right-pad string to exact width."""
    return s.ljust(width)[:width]


def _header_standard_lines(cfg: dict, nlhead: int) -> list[str]:
    """Generate lines 2-107 (fixed NASA Ames 2160 header metadata)."""
    lines: list[str] = []
    lines.append(f"{nlhead}    {_FFI}")
    lines.append(cfg["oname"])
    lines.append(cfg["org"])
    lines.append(cfg["sname"])
    lines.append(cfg["mname"])
    lines.append("1    1")                                              # 7
    lines.append("{date}")                                              # 8 – placeholder
    lines.append("0")                                                   # 9
    lines.append("40")                                                  # 10
    lines.append("Pressure at observation (hPa)")                       # 11
    lines.append("Sounding station identifier")                         # 12
    lines.append(str(_NV))                                              # 13
    lines.append(_VSCAL)                                                # 14
    lines.append(_VMISS)                                                # 15
    lines.extend(_DV_NAMES)                                             # 16-23
    lines.append(str(_NAUXV))                                           # 24
    lines.append(str(_NAUXC))                                           # 25
    lines.append(_ASCAL)                                                # 26
    lines.extend(_AMISS_NUM_LINES)                                      # 27-30
    lines.append(_LENA)                                                 # 31
    lines.extend(_AMISS_CHAR)                                           # 32-50
    lines.extend(_AUX_NAMES)                                            # 51-107
    # Total: 2 + 4 + 1 + 1 + 1 + 1 + 1 + 2 + 1 + 8 + 1 + 1 + 1 + 4 + 1 + 19 + 57
    #       = 106 lines (2-107)
    return lines


def _header_tail(cfg: dict) -> list[str]:
    """
    Generate lines after aux names: nscoml, nncoml, station marker.

    Sodankyla: nscoml=0, nncoml=0  (2 lines)
    Marambio:  nscoml=2, nncoml=2  (6 lines)
    """
    lines: list[str] = []
    if cfg["station_marker"] == "MBI":
        lines.append("2")
        lines.append("Integrated value = ")
        lines.append("Residual value = ")
        lines.append("2")
        lines.append("  P    Time  Z    T    U    TI    PO3    Dir    SPD")
        lines.append("*************************End Of Header******************")
    else:
        lines.append("0")   # nscoml
        lines.append("0")   # nncoml
    lines.append(cfg["station_marker"])
    return lines


# ---------------------------------------------------------------------------
# Auxiliary data values
# ---------------------------------------------------------------------------

# Sentinel strings for 38 numeric aux vars (from reference files)
_AUX_SENTINELS = [
    "9999", "99.99", "999.99", "999.99", "999.9", "99.9",
    "99999.9", "99999.9", "99999.9", "99999.9", "9.9", "99.9",
    "99.99", "99.99", "9.999", "9.999", "99.9", "99.99",
    "9999.9", "9.9", "9.9", "9.9", "999.9", "999.9",
    "999.9", "9.999", "99.9", "999", "999.9", "999.9",
    "99999.9", "99999.9", "99999.9", "99999.9", "99.99",
    "9.999e+00", "9.999e+00", "99999",
]

# Per-var formatting
_AUX_FORMATS = [
    "d", ".2f", ".2f", ".2f", ".1f", ".1f",
    ".1f", ".1f", ".1f", ".0f", ".1f", ".1f",
    ".2f", ".2f", ".3f", ".3f", ".1f", ".2f",
    ".1f", ".1f", ".1f", ".1f", ".1f", ".1f",
    ".1f", ".3f", ".1f", ".0f", ".1f", ".1f",
    ".1f", ".1f", ".1f", ".1f", ".2f",
    ".3e", ".3e", ".0f",
]


def _fmt_aux(v, idx: int) -> str:
    """Format one numeric aux value; use sentinel if missing."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return _AUX_SENTINELS[idx]
    fmt = _AUX_FORMATS[idx]
    if fmt == "d":
        return f"{int(v)}"
    if fmt == ".3e":
        s = format(v, ".3e")
        # Normalize to match reference (9.999e+00)
        if "e+" in s:
            exp = int(s.split("e+")[1])
            s = f"{float(s.split('e')[0]):.3f}e+{exp:02d}"
        elif "e-" in s:
            exp = int(s.split("e-")[1])
            s = f"{float(s.split('e')[0]):.3f}e-{exp:02d}"
        return s
    return format(v, fmt)


def _aux_numeric_lines(meta: SondeMetadata, nx: int, df: pd.DataFrame) -> list[str]:
    """
    Generate the 4 numeric auxiliary data lines (38 values).
    """
    def _g(v):
        """Return value or NaN if missing."""
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return np.nan
        return v

    first_row = df.iloc[0] if not df.empty else {}
    po3_col = "PO3_raw_mPa" if "PO3_raw_mPa" in df.columns else "PO3_dqa_mPa"

    gnd_ws = _g(meta.ground_wind_spd_ms if meta.ground_wind_spd_ms is not None
                else first_row.get("wind_spd_ms", np.nan))
    gnd_t  = _g(meta.ground_temp_C if meta.ground_temp_C is not None
                else first_row.get("temp_C", np.nan))
    surf_o3 = _g(meta.surface_po3_mPa if meta.surface_po3_mPa is not None
                 else first_row.get(po3_col, np.nan))
    # T_inlet from first row if not in metadata
    t_inlet = first_row.get("temp_box_C", np.nan)  # proxy for T_inlet

    vals = [
        nx,
        _g(meta.launch_hour_ut),
        _g(meta.station_lon),
        _g(meta.station_lat),
        gnd_ws,
        gnd_t,
        2400.0,            # 7 - free lift (hardcoded default)
        np.nan,            # 8 - dummy weight
        np.nan,            # 9 - balloon volume
        1500.0,            # 10 - balloon weight (hardcoded default)
        _g(meta.cathode_vol_cm3),
        _g(meta.sst_concentration_gl),
        _g(meta.flow_rate_cal_mLmin),
        _g(meta.flow_rate_s100cm3),
        _g(meta.bg_pre_ua),
        _g(meta.bg_post_ua),
        _g(meta.time_surface_ozone_min),
        surf_o3,
        _g(meta.surface_pressure_hpa),
        np.nan,             # 20 - pressure correction
        np.nan,             # 21 - temperature correction
        np.nan,             # 22 - humidity correction
        _g(meta.col1_du),
        _g(meta.col2a_du),
        _g(meta.col2b_du),
        _g(meta.corr_factor),
        _g(meta.t_lab_c),
        _g(meta.rh_lab_pct),
        t_inlet,            # 29 - T_inlet (from box temp)
        _g(meta.t_pump_c),
        np.nan,             # 31-34: reserved
        np.nan,
        np.nan,
        np.nan,
        _g(meta.i0_ua),
        _g(meta.i_lin),
        _g(meta.i_quad),
        _g(meta.r_ntc),
    ]

    fvals = [_fmt_aux(v, i) for i, v in enumerate(vals)]
    line1 = " ".join(fvals[:12])
    line2 = " ".join(fvals[12:26])
    line3 = " ".join(fvals[26:37])
    line4 = fvals[37]

    return [line1, line2, line3, line4]


_LIFTING_GAS_ABBREV = {
    "hydrogen": "H2",
    "helium": "He",
}

def _norm_lifting_gas(val: str) -> str:
    """Normalize lifting gas to abbreviated form (e.g. 'Hydrogen' -> 'H2')."""
    v = (val or "").strip()
    if not v:
        return v
    lower = v.lower()
    return _LIFTING_GAS_ABBREV.get(lower, v)


def _aux_char_lines(meta: SondeMetadata, cfg: dict) -> list[str]:
    """
    Generate the 19 character auxiliary data lines (aux vars 39-57).
    """
    raw_fname = meta.fpath.name if meta.fpath else ""

    def _c(val: str, default_z: str) -> str:
        """Return non-empty value or zzz sentinel."""
        v = (val or "").strip()
        return v if v else default_z

    char_vals = [
        _c(meta.meteosonde, _AMISS_CHAR[0]),              # 39
        _c(meta.pump_corr_table, _AMISS_CHAR[1]),         # 40
        _c(meta.bg_method, _AMISS_CHAR[2]),               # 41
        _c(meta.smoothing_method, _AMISS_CHAR[3]),        # 42
        _c(meta.box_temp_location, _AMISS_CHAR[4]),       # 43
        _c(raw_fname, _AMISS_CHAR[5]),                    # 44
        _c(_norm_lifting_gas(meta.lifting_gas), _AMISS_CHAR[6]),  # 45
        _c(meta.balloon_material, _AMISS_CHAR[7]),        # 46
        _c(meta.balloon_brand, _AMISS_CHAR[8]),           # 47
        _c(meta.balloon_type, _AMISS_CHAR[9]),            # 48
        _c(meta.discontinuation, _AMISS_CHAR[10]),        # 49
        _c(meta.weather, _AMISS_CHAR[11]),                # 50
        _c(meta.pretreatment, _AMISS_CHAR[12]),           # 51
        _c(meta.serial_ecc, _AMISS_CHAR[13]),             # 52
        _c(meta.serial_interface, _AMISS_CHAR[14]),       # 53
        _c(meta.serial_sonde, _AMISS_CHAR[15]),           # 54
        _AMISS_CHAR[16],                                   # 55 Reserved
        _AMISS_CHAR[17],                                   # 56 Reserved
        _c(meta.sensor_type, _AMISS_CHAR[18]),            # 57
    ]

    return char_vals


# ---------------------------------------------------------------------------
# Profile data
# ---------------------------------------------------------------------------

def _profile_lines(df: pd.DataFrame) -> list[str]:
    """
    Generate profile data lines (9 fixed-width columns).

    Format matches the existing .bXX example files:
        Pressure  Time(s)  Height  Temp  RH  BoxTemp  O3(mPa)  WindDir  WindSpd
    """
    MISS_P  = -99999.0
    MISS_T  = -99999.0
    MISS_F  = 99999.0
    MISS_RH = 999.0
    MISS_O3 = 999.9
    MISS_WD = 999.0
    MISS_WS = 999.9

    lines: list[str] = []
    for _, row in df.iterrows():
        p     = row.get("pressure_hPa", np.nan)
        t_s   = row.get("time_s", np.nan)
        alt   = row.get("altitude_gpm", np.nan)
        temp  = row.get("temp_C", np.nan)
        rh    = row.get("rh_pct", np.nan)
        tbox  = row.get("temp_box_C", np.nan)
        po3   = row.get("PO3_dqa_mPa", row.get("PO3_raw_mPa", np.nan))
        wdir  = row.get("wind_dir_deg", np.nan)
        wspd  = row.get("wind_spd_ms", np.nan)

        def _mv(v, miss_sentinel, fmt: str = ".1f") -> str:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return f"{miss_sentinel:{fmt}}" if fmt.startswith(".") else str(miss_sentinel)
            return format(float(v), fmt)

        # Each column right-aligned to match example format
        p_str   = _mv(p, MISS_P, ".2f")
        ts_str  = _mv(t_s, -99999, ".0f")
        alt_str = _mv(alt, 99999, ".0f")
        t_str   = _mv(temp, MISS_T, ".1f")
        rh_str  = _mv(rh, 999, ".0f")
        tb_str  = _mv(tbox, 999.9, ".1f")
        o3_str  = _mv(po3, 999.9, ".2f")
        wd_str  = _mv(wdir, 999, ".0f")
        ws_str  = _mv(wspd, 999.9, ".1f")

        # Right-align each field to match example fixed-width format
        line = f"{p_str:>7s} {ts_str:>5s} {alt_str:>5s} {t_str:>5s} {rh_str:>4s} {tb_str:>5s} {o3_str:>5s} {wd_str:>4s} {ws_str:>5s}"
        lines.append(line)

    return lines


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

def write_nasa_aims(
    meta: SondeMetadata,
    df: pd.DataFrame,
    output_dir: Path | str = ".",
    station_key: str = "sdk",
) -> Path:
    """
    Write a NASA Ames FFI 2160 (.bXX) file.

    Parameters
    ----------
    meta           : SondeMetadata - flight metadata
    df             : DataFrame - profile with at least pressure_hPa, time_s,
                     altitude_gpm, temp_C, rh_pct, temp_box_C,
                     PO3_dqa_mPa (falls back to PO3_raw_mPa), wind_dir_deg,
                     wind_spd_ms
    output_dir     : output directory
    station_key    : "sdk" for Sodankyla, "mr" for Marambio

    Returns Path of the created file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = _STATION_CFG.get(station_key, _STATION_CFG["sdk"])

    # Compute nlhead
    is_marambio = (station_key == "mr")
    if is_marambio:
        nlhead = _NLHEAD_MARAMBIO
    else:
        nlhead = _NLHEAD_SIMPLE

    # -- Filename: soYYMMDD.bHH --
    if meta.launch_date and meta.launch_hour_ut is not None:
        yymmdd = meta.launch_date.strftime("%y%m%d")
        hh = f"{int(meta.launch_hour_ut):02d}"
        fname = f"so{yymmdd}.b{hh}"
    else:
        yymmdd = meta.launch_date.strftime("%y%m%d") if meta.launch_date else "000000"
        fname = f"so{yymmdd}.b00"

    fout = output_dir / fname

    lines: list[str] = []

    # -- Line 1: Fixed-width identification record --
    dt = meta.launch_datetime
    if dt is None:
        start_str = end_str = "01-JAN-2000 00:00:00"
    else:
        start_str = dt.strftime("%d-%b-%Y %H:%M:%S").upper()
        last_ts = float(df["time_s"].iloc[-1]) if not df.empty and "time_s" in df.columns else 7200
        from datetime import timedelta
        end_dt_obj = dt + timedelta(seconds=last_ts)
        end_str = end_dt_obj.strftime("%d-%b-%Y %H:%M:%S").upper()

    pi = _pad(cfg["first_line_pi"], 20)
    instr = _pad(cfg["first_line_instr"], 12)
    station = _pad(cfg["first_line_station"], 12)
    param = _pad(cfg["first_line_param"], 12)
    ver = "0001"
    first = f"{pi}{instr}{station}{param}{start_str}{end_str}{ver}"
    lines.append(first)

    # -- Lines 2-107: Standard header --
    header_std = _header_standard_lines(cfg, nlhead)
    date_str = meta.launch_date
    if date_str:
        d = date_str if isinstance(date_str, date) else meta.launch_date
        date_line = f"{d.year} {d.month} {d.day}    {d.year} {d.month} {d.day}"
    else:
        date_line = "2000 1 1    2000 1 1"
    # Replace placeholder on line 8 (index 6 in header_std)
    header_std[6] = date_line
    lines.extend(header_std)

    # -- Lines 108+: Tail (nscoml, nncoml, station marker) --
    header_tail = _header_tail(cfg)
    lines.extend(header_tail)

    # -- Auxiliary data --
    nx = len(df)
    aux_num = _aux_numeric_lines(meta, nx, df)
    lines.extend(aux_num)

    aux_char = _aux_char_lines(meta, cfg)
    lines.extend(aux_char)

    # -- Profile data --
    profile = _profile_lines(df)
    lines.extend(profile)

    import io
    content = "\n".join(lines) + "\n"
    with open(fout, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(content)
    print(f"NASA AIMS file written: {fout}")
    return fout


# ---------------------------------------------------------------------------
# Batch export
# ---------------------------------------------------------------------------

def write_nasa_aims_batch(
    results: list[tuple[SondeMetadata, pd.DataFrame]],
    output_dir: Path | str = "nasaaims_output",
    station_key: str = "sdk",
) -> list[Path]:
    """
    Export a list of (meta, df) tuples to NASA AIMS .bXX files.

    Parameters
    ----------
    results      : list of (SondeMetadata, DataFrame) tuples
    output_dir   : output directory
    station_key  : "sdk" or "mr"

    Returns list of written file paths.
    """
    output_dir = Path(output_dir)
    written: list[Path] = []
    for meta, df in results:
        try:
            fout = write_nasa_aims(meta, df, output_dir=output_dir, station_key=station_key)
            written.append(fout)
        except Exception as e:
            import warnings
            warnings.warn(f"NASA AIMS export error {meta.fpath.name}: {e}", UserWarning)
    return written
