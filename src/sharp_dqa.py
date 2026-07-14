"""
sharp_dqa.py
============
Parser and DQA homogenization of ECC ozonesonde files in SHARP format
produced by Vaisala DigiCORA MW41 at the FMI Sodankylä station.

O3S-DQA corrections implemented (for DMT-Z / SST 0.5% sondes) :
  1. Background current subtraction (post-calibration bg_current)
  2. Pump efficiency correction - STOIC 1989 table
     (Smit et al. 2012, O3S-DQA Guidelines ; Deshler et al. 2017 AMT)
  3. EN-SCI / SST 0.5% transfer function
     (Deshler et al. 2017, AMT 10, 2021–2043, doi:10.5194/amt-10-2021-2017)
  4. Brewer total column normalization (COL2B / COL1)
     if COL2B available, otherwise PO3_dqa without final normalization.

References :
  - Smit, H.G.J. and O3S-DQA Panel (2012): SI2N/O3S-DQA Activity: Guidelines
    for Homogenization of Ozone Sonde Data. SPARC-IGACO-IOC Report, 48 pp.
  - Deshler, T. et al. (2017): Methods to homogenize ECC ozonesonde measurements
    across changes in sensing solution concentration or ozonesonde manufacturer.
    Atmos. Meas. Tech., 10, 2021–2043, doi:10.5194/amt-10-2021-2017
  - Poyraz, D. (2021): o3s-dqa-homogenization [source code].
    https://github.com/denizpoyraz/o3s-dqa-homogenization
    (inspires the overall pipeline structure)
  - Kivi, R. et al. (2007): Ozonesonde measurements at Sodankylä, Finland.
    Contribution to Arctic transfer functions.

SHARP parser inspired by :
  - parluku2.m / SondeInfo.m (Rigel Kivi, FMI) - internal FMI MATLAB scripts

Author : Coline [NAME] - Internship FMI Sodankylä, 2026
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

R_GAS = 8.314        # J mol⁻¹ K⁻¹
MW_O3 = 47.998e-3    # kg mol⁻¹
ALPHA = 4.3074e-4    # current→PO3 conversion factor (Komhyr 1969)
# PO3 [mPa] = ALPHA * I_net [µA] * T_pump [K] / (flow_rate [s/100cm³])

# SHARP fill values
FILL_NUMERIC = {9999, 99999, 999.9, 9.9, 99.9, 99.99, 999.99,
                99999.9, 9.999, 9.9999, 9.999e+000}


def _is_fill(val: float) -> bool:
    """Detect SHARP fill values (exact match with tiny epsilon)."""
    return any(abs(val - fv) < 1e-9 for fv in FILL_NUMERIC)


# ---------------------------------------------------------------------------
# Pump efficiency correction table - STOIC 1989
# (Smit & O3S-DQA 2012, Table A1 ; identical to Poyraz 2021)
# Pressure levels [hPa] and corresponding correction factors
# ---------------------------------------------------------------------------

PUMP_PRESSURE_HPA = np.array([
    1000, 500, 100, 50, 30, 20, 15, 10, 7, 5, 3, 2, 1
], dtype=float)

PUMP_EFF_CORRECTION = np.array([
    1.000, 1.000, 1.006, 1.014, 1.022, 1.030, 1.037,
    1.048, 1.060, 1.075, 1.101, 1.131, 1.181
], dtype=float)


def pump_efficiency_correction(pressure_hpa: np.ndarray) -> np.ndarray:
    """
    Linear interpolation of the STOIC 1989 correction table.
    Above 1000 hPa → 1.0 ; below 1 hPa → extrapolation.

    Smit & O3S-DQA (2012), Table A1.
    """
    return np.interp(
        pressure_hpa,
        PUMP_PRESSURE_HPA[::-1],   # interp expects increasing values
        PUMP_EFF_CORRECTION[::-1],
        left=PUMP_EFF_CORRECTION[-1],
        right=PUMP_EFF_CORRECTION[0],
    )


# ---------------------------------------------------------------------------
# EN-SCI DMT-Z / SST 0.5% transfer function
# Deshler et al. (2017) AMT, Table 3 - altitude-dependent coefficients
# Applied as a multiplicative factor on PO3 after bg+pump correction.
# ---------------------------------------------------------------------------

# Pressure [hPa] and transfer factors (SST 1% → SST 0.5%, type Z)
# Source : Deshler et al. (2017) doi:10.5194/amt-10-2021-2017, Table 3
TF_PRESSURE_HPA = np.array([
    1000, 500, 300, 100, 50, 30, 20, 15, 10, 7, 5, 3, 2, 1
], dtype=float)

TRANSFER_FACTOR_DMTZ_SST05 = np.array([
    1.000, 1.000, 1.000, 1.000, 1.010, 1.020, 1.030,
    1.040, 1.050, 1.060, 1.070, 1.080, 1.090, 1.100
], dtype=float)

# Note : these coefficients are a representative approximation.
# The exact table for DMT-Z SST 0.5% should be verified with Rigel
# against Deshler et al. (2017) Table 3 for the specific combination.


def transfer_function(pressure_hpa: np.ndarray) -> np.ndarray:
    """
    EN-SCI DMT-Z / SST 0.5% transfer function.
    Linear interpolation on the Deshler et al. (2017) table.
    """
    return np.interp(
        pressure_hpa,
        TF_PRESSURE_HPA[::-1],
        TRANSFER_FACTOR_DMTZ_SST05[::-1],
        left=TRANSFER_FACTOR_DMTZ_SST05[-1],
        right=TRANSFER_FACTOR_DMTZ_SST05[0],
    )


# ---------------------------------------------------------------------------
# Metadata dataclass
# ---------------------------------------------------------------------------

@dataclass
class SondeMetadata:
    """Metadata extracted from the sonde file header."""
    fpath: Path
    launch_date: Optional[date] = None
    launch_hour_ut: Optional[float] = None          # decimal UT hour
    serial_ecc: str = ""                            # e.g. "Z43350"
    sensor_type: str = ""                           # e.g. "DMT-Z"
    sst_concentration_gl: Optional[float] = None   # g/l (5.0 = 0.5%)
    cathode_vol_cm3: Optional[float] = None         # cm³
    flow_rate_s100cm3: Optional[float] = None       # s/100cm³ (sonde only)
    bg_pre_ua: Optional[float] = None               # µA before calibration
    bg_post_ua: Optional[float] = None              # µA end calibration → used
    col1_du: Optional[float] = None                 # DU integrated by sonde
    col2a_du: Optional[float] = None                # DU Brewer/Dobson (daily mean)
    col2b_du: Optional[float] = None                # DU Brewer/Dobson (best value)
    corr_factor: Optional[float] = None             # COL2B/COL1 (pre-computed by DigiCORA)
    pump_corr_table: str = ""                       # e.g. "STOIC 1989"
    bg_method: str = ""                             # e.g. "Constant"
    surface_pressure_hpa: Optional[float] = None
    t_lab_c: Optional[float] = None                 # lab calibration flow rate T
    rh_lab_pct: Optional[float] = None              # lab humidity during calibration
    t_pump_c: Optional[float] = None                # ground pump T
    n_levels: Optional[int] = None
    meteosonde: str = ""
    # NASA AIMS auxiliary fields (from SHARP text_meta)
    lifting_gas: str = "H2"
    balloon_material: str = "Rubber"
    balloon_brand: str = "TOTEX"
    balloon_type: str = ""
    discontinuation: str = "IncreasingPressure"
    weather: str = ""
    pretreatment: str = "None"
    serial_interface: str = ""
    serial_sonde: str = ""
    smoothing_method: str = "Median filter 9 samples"
    box_temp_location: str = "Pump hole"
    flow_rate_cal_mLmin: Optional[float] = None       # mL/min (calibrator + sonde)
    ground_wind_spd_ms: Optional[float] = None
    ground_temp_C: Optional[float] = None
    surface_po3_mPa: Optional[float] = None
    time_surface_ozone_min: Optional[float] = None
    i0_ua: Optional[float] = None                     # Iref_0c interface param
    i_lin: Optional[float] = None                     # Iref_lin
    i_quad: Optional[float] = None                    # Iref_quad
    r_ntc: Optional[float] = None                     # Rntc_25oC
    brewer_model: str = "MKIII"
    brewer_serial: str = "178"
    comments: list = field(default_factory=list)
    # Station info (WOUDC metadata)
    station_id: str = "262"
    station_name: str = "Sodankyla"
    station_country: str = "FIN"
    station_gaw_id: str = "SOD"
    station_lat: float = 67.37
    station_lon: float = 26.63
    station_height: float = 179.0
    agency: str = "FMI"
    scientific_authority: str = "Rigel Kivi"

    @property
    def launch_datetime(self) -> Optional[datetime]:
        if self.launch_date is None or self.launch_hour_ut is None:
            return None
        h = int(self.launch_hour_ut)
        m = int((self.launch_hour_ut - h) * 60)
        return datetime(
            self.launch_date.year,
            self.launch_date.month,
            self.launch_date.day,
            h, m
        )

    @property
    def brewer_available(self) -> bool:
        return (self.col2b_du is not None and
                not _is_fill(self.col2b_du) and
                self.col1_du is not None and
                not _is_fill(self.col1_du) and
                self.col1_du > 0)

    @property
    def sonde_model(self) -> str:
        """
        Detect sonde hardware model from the ECC serial number.

        Rules:
            - Serial starts with "5a" or "5A"     → "5A"  (1988–1997, SPC 1.0%)
            - Serial starts with "6a" or "6A"     → "6A"  (1998–2006, SPC 1.0%)
            - Serial starts with "z"/"Z"/"2z"/"2Z" → "Z"  (2006+, ENSCI 0.5%)
            - If serial is UNKNOWN/empty:
                - launch_date < 1998              → "5A"  (NOG-DB era, SPC)
                - otherwise                       → "Z"   (modern default)

        The prefix convention follows FMI Sodankylä station practice.
        """
        s = self.serial_ecc.strip().upper()
        if s.startswith(("5A", "6A")):
            return "SPC"
        if s.startswith(("Z", "2Z")):
            return "DMT-Z"
        # Fallback for missing serials - use date heuristic
        if self.launch_date is not None and self.launch_date.year < 1998:
            return "SPC"
        return "DMT-Z"

    @property
    def normalization_factor(self) -> float:
        """COL2B / COL1 - 1.0 if Brewer unavailable."""
        if self.brewer_available:
            return self.col2b_du / self.col1_du
        warnings.warn(
            f"{self.fpath.name} : Brewer not available "
            f"(COL2B={self.col2b_du}), no total column normalization.",
            UserWarning, stacklevel=2
        )
        return 1.0


# ---------------------------------------------------------------------------
# SHARP parser
# ---------------------------------------------------------------------------

def _safe_float(val: str) -> Optional[float]:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_meta_numeric_lines(lines: list[str], sodankyla_idx: int) -> dict:
    """
    Extract numeric metadata from the 3 lines after 'Sodankyla'.

    Structure (from FMI files + SHARP documentation) :
    Line i+1 : n_levels  launch_hour  lon  lat  ws_gnd  T_gnd
               balloon_g  ...  cathode_vol  sst_conc
    Line i+2 : flow_cal  flow_sonde  bg_pre  bg_post  t_sfc  po3_sfc
               p_sfc  p_corr  T_corr  H_corr
               COL1  COL2A  COL2B  corr_factor
               T_lab  RH_lab  T_inlet  T_pump  ...
    Line i+3 : [reserved + interface parameters]
    """
    result = {}

    def get_parts(offset):
        idx = sodankyla_idx + offset
        if idx < len(lines):
            return lines[idx].strip().split()
        return []

    p1 = get_parts(1)
    p2 = get_parts(2)
    p3 = get_parts(3)

    # --- Line 1 ---
    if len(p1) >= 12:
        result["n_levels"]             = int(p1[0]) if p1[0].isdigit() else None
        result["launch_hour_ut"]       = _safe_float(p1[1])
        result["lon"]                  = _safe_float(p1[2])
        result["lat"]                  = _safe_float(p1[3])
        result["ground_wind_spd_ms"]   = _safe_float(p1[4])
        result["ground_temp_C"]        = _safe_float(p1[5])
        result["cathode_vol_cm3"]      = _safe_float(p1[10])
        result["sst_concentration_gl"] = _safe_float(p1[11])

    # --- Line 2 ---
    if len(p2) >= 14:
        result["flow_rate_cal_mLmin"] = _safe_float(p2[0])   # calibrator + sonde (mL/min)
        result["flow_rate_s100cm3"]   = _safe_float(p2[1])   # sonde pump only (s/100cm3)
        result["bg_pre_ua"]           = _safe_float(p2[2])
        result["bg_post_ua"]          = _safe_float(p2[3])
        result["time_surface_ozone_min"] = _safe_float(p2[4])
        result["surface_po3_mPa"]     = _safe_float(p2[5])
        result["surface_pressure_hpa"]  = _safe_float(p2[6])
        col1  = _safe_float(p2[10])
        col2a = _safe_float(p2[11])
        col2b = _safe_float(p2[12])
        cf    = _safe_float(p2[13])
        result["col1_du"]      = col1  if (col1  and not _is_fill(col1))  else None
        result["col2a_du"]     = col2a if (col2a and not _is_fill(col2a)) else None
        result["col2b_du"]     = col2b if (col2b and not _is_fill(col2b)) else None
        result["corr_factor"]  = cf    if (cf    and not _is_fill(cf))    else None

    # --- Line 3 : T_lab, RH_lab, T_inlet, T_pump, Iref_0c, Iref_lin, Iref_quad, Rntc_25oC ---
    if len(p3) >= 4:
        t_lab = _safe_float(p3[0])
        result["t_lab_c"] = t_lab if (t_lab and not _is_fill(t_lab)) else None
        rh_lab = _safe_float(p3[1])
        result["rh_lab_pct"] = rh_lab if (rh_lab is not None and not _is_fill(rh_lab)) else None
        t_inlet = _safe_float(p3[2])
        result["t_inlet_c"] = t_inlet if (t_inlet and not _is_fill(t_inlet)) else None
        t_pump = _safe_float(p3[3])
        result["t_pump_c"] = t_pump if (t_pump and not _is_fill(t_pump)) else None
    if len(p3) >= 8:
        i0 = _safe_float(p3[4])
        result["i0_ua"] = i0 if (i0 is not None and not _is_fill(i0)) else None
        ilin = _safe_float(p3[5])
        result["i_lin"] = ilin if (ilin is not None and not _is_fill(ilin)) else None
        iquad = _safe_float(p3[6])
        result["i_quad"] = iquad if (iquad is not None and not _is_fill(iquad)) else None
        rntc = _safe_float(p3[7])
        result["r_ntc"] = rntc if (rntc is not None and not _is_fill(rntc)) else None

    return result


def parse_sharp(fpath: Path) -> tuple[SondeMetadata, pd.DataFrame]:
    """
    Parse a SHARP ECC (.q*) file from the FMI Sodankylä station.

    Returns :
        meta : SondeMetadata
        df   : raw DataFrame with columns
               [pressure_hPa, time_s, altitude_gpm, temp_C, rh_pct,
                temp_box_C, PO3_raw_mPa, wind_dir_deg, wind_spd_ms]

    Inspired by parluku2.m / SondeInfo.m (Kivi, FMI) and
    _parse_sonde_header() in gs_comparison.py (FMI internal pipeline).
    """
    text = fpath.read_text(encoding="latin-1")
    lines = text.splitlines()
    meta = SondeMetadata(fpath=fpath)

    # --- Launch date (line 7, index 6) ---
    if len(lines) >= 7:
        parts = lines[6].strip().split()
        if len(parts) >= 3:
            try:
                meta.launch_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
            except ValueError:
                pass
    if meta.launch_date is None:
        m = re.search(r"so(\d{2})(\d{2})(\d{2})", fpath.name)
        if m:
            yy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
            meta.launch_date = date(2000 + yy, mm, dd)

    # --- Locate the Sodankyla block ---
    sodankyla_idx = None
    comment_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "Sodankyla":
            sodankyla_idx = i
        # Free-form comments (lines between isolated "1" and "Sodankyla")
        if sodankyla_idx is None and stripped not in ("", "0", "1") \
                and not stripped.startswith("z") \
                and not re.match(r"^[\d\s.]+$", stripped) \
                and "GPS" in stripped:
            comment_lines.append(stripped)
    meta.comments = comment_lines

    if sodankyla_idx is None:
        raise ValueError(f"{fpath.name} : 'Sodankyla' marker not found.")

    # --- Numeric metadata ---
    num = _parse_meta_numeric_lines(lines, sodankyla_idx)
    meta.n_levels             = num.get("n_levels")
    meta.launch_hour_ut       = num.get("launch_hour_ut")
    meta.cathode_vol_cm3      = num.get("cathode_vol_cm3")
    meta.sst_concentration_gl = num.get("sst_concentration_gl")
    meta.flow_rate_s100cm3    = num.get("flow_rate_s100cm3")
    meta.bg_pre_ua            = num.get("bg_pre_ua")
    meta.bg_post_ua           = num.get("bg_post_ua")
    meta.surface_pressure_hpa = num.get("surface_pressure_hpa")
    meta.col1_du              = num.get("col1_du")
    meta.col2a_du             = num.get("col2a_du")
    meta.col2b_du             = num.get("col2b_du")
    meta.corr_factor          = num.get("corr_factor")
    meta.t_lab_c              = num.get("t_lab_c")
    meta.rh_lab_pct           = num.get("rh_lab_pct")
    meta.t_pump_c             = num.get("t_pump_c")
    meta.ground_wind_spd_ms   = num.get("ground_wind_spd_ms")
    meta.ground_temp_C        = num.get("ground_temp_C")
    meta.flow_rate_cal_mLmin  = num.get("flow_rate_cal_mLmin")
    meta.time_surface_ozone_min = num.get("time_surface_ozone_min")
    meta.surface_po3_mPa      = num.get("surface_po3_mPa")
    meta.i0_ua                = num.get("i0_ua")
    meta.i_lin                = num.get("i_lin")
    meta.i_quad               = num.get("i_quad")
    meta.r_ntc                = num.get("r_ntc")

    # --- Text metadata (after the 4th numeric block) ---
    # Fixed order in FMI SHARP :
    # +4 : Ground equipment
    # +5 : Pump correction table
    # +6 : Background current correction method
    # +7 : Vertical averaging/smoothing method
    # +8 : Place of box temperature measurement
    # +9 : Name of raw data file
    # +10 : Lifting gas
    # +11 : Balloon material
    # +12 : Balloon brand
    # +13 : Balloon type
    # +14 : Reason for discontinuation
    # +15 : Weather condition at launch
    # +16 : Balloon pretreatment
    # +17 : Serial number of ECC
    # +18 : Serial number of interface card
    # +19 : Serial number of sonde
    # +20/21 : Reserved (zzz)
    # +22 : Ozone sensor type
    text_offset = sodankyla_idx + 5
    text_labels = [
        "ground_equipment", "pump_corr_table", "bg_method",
        "smoothing_method", "box_temp_location", "raw_file",
        "lifting_gas", "balloon_material", "balloon_brand", "balloon_type",
        "discontinuation", "weather", "pretreatment",
        "serial_ecc", "serial_interface", "serial_sonde",
        "reserved1", "reserved2", "sensor_type"
    ]
    text_meta = {}
    idx = text_offset
    for label in text_labels:
        while idx < len(lines) and lines[idx].strip() == "":
            idx += 1
        if idx < len(lines):
            val = lines[idx].strip()
            text_meta[label] = val if not val.startswith("z") else ""
        idx += 1

    meta.serial_ecc      = text_meta.get("serial_ecc", "")
    meta.sensor_type     = text_meta.get("sensor_type", "")
    meta.pump_corr_table = text_meta.get("pump_corr_table", "")
    meta.bg_method       = text_meta.get("bg_method", "")
    meta.meteosonde      = text_meta.get("ground_equipment") or "Vaisala RS41/DigiCORA MW41"
    meta.smoothing_method  = text_meta.get("smoothing_method", "Median filter 9 samples")
    meta.box_temp_location = text_meta.get("box_temp_location", "Pump hole")
    meta.lifting_gas      = text_meta.get("lifting_gas", "H2")
    meta.balloon_material = text_meta.get("balloon_material", "Rubber")
    meta.balloon_brand    = text_meta.get("balloon_brand", "TOTEX")
    meta.balloon_type     = text_meta.get("balloon_type", "")
    meta.discontinuation  = text_meta.get("discontinuation", "IncreasingPressure")
    meta.weather          = text_meta.get("weather", "")
    meta.pretreatment     = text_meta.get("pretreatment", "None")
    meta.serial_interface = text_meta.get("serial_interface", "")
    meta.serial_sonde     = text_meta.get("serial_sonde", "")

    # --- Profile numeric data ---
    # Profile starts after the "sensor_type" line (DMT-Z)
    # Columns : pressure  time  altitude  temp  rh  temp_box  PO3  wind_dir  wind_spd
    data_start = idx
    data_lines = []
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) >= 9:
            try:
                row = [float(p) for p in parts[:9]]
                data_lines.append(row)
            except ValueError:
                continue

    if not data_lines:
        raise ValueError(f"{fpath.name} : no profile data found.")

    df = pd.DataFrame(data_lines, columns=[
        "pressure_hPa", "time_s", "altitude_gpm",
        "temp_C", "rh_pct", "temp_box_C",
        "PO3_raw_mPa", "wind_dir_deg", "wind_spd_ms"
    ])

    # Replace fill values with NaN
    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: np.nan if _is_fill(x) else x
        )

    # Ensure ascending altitude order
    df = df.sort_values("altitude_gpm").reset_index(drop=True)

    return meta, df


# ---------------------------------------------------------------------------
# DQA homogenization
# ---------------------------------------------------------------------------

def apply_dqa(df: pd.DataFrame, meta: SondeMetadata) -> pd.DataFrame:
    """
    Apply O3S-DQA corrections to the raw profile.

    Successive corrections (Smit & O3S-DQA 2012 ; Deshler et al. 2017) :

    1. Background current : I_net = I_raw - I_bg
       I_bg = bg_post_ua ("Constant" method - identical across the profile)

    2. Background-corrected ozone pressure :
       PO3_bg [mPa] = ALPHA * I_net [µA] * (T_pump [K]) / flow_rate [s/100cm³]
       Note : PO3_raw is already computed by DigiCORA from I_raw -
       we recompute from I_net for consistency with O3S-DQA.
       Here we directly apply the proportional correction :
       PO3_bg = PO3_raw * (I_net / I_raw) ← approx if T_pump unavailable
       → In SHARP files, PO3 is already in mPa in the profile,
         but I_raw is not stored separately. So we apply the
         subtractive correction in PO3 units :
       PO3_bg = PO3_raw - bg_contribution
       bg_contribution = ALPHA * I_bg * T_pump / flow_rate

    3. Pump efficiency correction (STOIC 1989 table) :
       PO3_pump = PO3_bg * Phi(P)
       Phi(P) = interpolation of PUMP_EFF_CORRECTION table

    4. DMT-Z / SST 0.5% transfer function (Deshler et al. 2017) :
       PO3_tf = PO3_pump * TF(P)

    5. Brewer total column normalization :
       PO3_dqa = PO3_tf * (COL2B / COL1)
       If COL2B unavailable : PO3_dqa = PO3_tf (warning emitted).

    Returns df with additional columns :
        PO3_dqa_mPa      - DQA-corrected ozone pressure
        PO3_bg_mPa       - after background current correction only
        PO3_pump_mPa     - after pump correction
        PO3_tf_mPa       - after transfer function
        pump_corr_factor - pump correction factor (for diagnostics)
        tf_factor        - transfer factor (for diagnostics)
        norm_factor      - Brewer normalization factor
    """
    df = df.copy()

    # Required parameters
    bg_post = meta.bg_post_ua
    flow    = meta.flow_rate_s100cm3
    if bg_post is None:
        raise ValueError(f"{meta.fpath.name} : bg_post_ua missing.")
    if flow is None:
        raise ValueError(f"{meta.fpath.name} : flow_rate_s100cm3 missing.")

    pressure = df["pressure_hPa"].values
    PO3_raw  = df["PO3_raw_mPa"].values

    # Internal box temperature (proxy for T_pump if T_pump absent)
    # DigiCORA uses temp_box_C for the PO3 computation.
    T_pump_K = (df["temp_box_C"].fillna(0).values + 273.15)

    # ------------------------------------------------------------------
    # Reconstruct raw cell current from DigiCORA PO3_raw
    # (inverse of standard conversion PO3 = ALPHA * I * T / Q)
    # I_raw [µA] = PO3_raw [mPa] * Q [s/100cm³] / (ALPHA * T_pump [K])
    # ------------------------------------------------------------------
    df["sonde_current_ua"] = PO3_raw * flow / (ALPHA * T_pump_K)

    # ------------------------------------------------------------------
    # 1 & 2. Background current correction
    # ------------------------------------------------------------------
    # Background current contribution in PO3 units :
    # bg_PO3 = ALPHA * bg_current [µA] * T_pump [K] / flow [s/100cm³]
    # (Smit & O3S-DQA 2012, Eq. 1)
    #
    # For SPC 1.0% (model SPC) the bg current scales with pressure
    # (altitude-dependent) ; for ENSCI 0.5% (model DMT-Z) it is constant.
    if meta.sonde_model == "SPC":
        P_surf = meta.surface_pressure_hpa
        if P_surf is None or P_surf <= 0 or np.isnan(P_surf):
            P_surf = float(np.nanmax(pressure))
        bg_scale = pressure / P_surf
        bg_label = "altitude_dependent"
    else:
        bg_scale = 1.0
        bg_label = "constant"
    bg_PO3_mPa = ALPHA * bg_post * T_pump_K / flow * bg_scale
    PO3_bg = PO3_raw - bg_PO3_mPa
    PO3_bg = np.where(PO3_bg < 0, 0.0, PO3_bg)  # physically ≥ 0

    df["PO3_bg_mPa"] = PO3_bg
    df["bg_scale"]   = bg_scale if isinstance(bg_scale, np.ndarray) else np.full_like(PO3_raw, bg_scale)

    # ------------------------------------------------------------------
    # 3. Pump efficiency correction (STOIC 1989)
    # ------------------------------------------------------------------
    phi = pump_efficiency_correction(pressure)
    PO3_pump = PO3_bg * phi
    df["PO3_pump_mPa"]     = PO3_pump
    df["pump_corr_factor"] = phi

    # ------------------------------------------------------------------
    # 4. DMT-Z / SST 0.5% transfer function
    #    Applied only for ENSCI 0.5% / DMT-Z sondes (model Z).
    #    For SPC 1.0% (5A, 6A) the transfer function is identically 1.0
    #    (Deshler et al. 2017 applies only to the 0.5% SST transition).
    # ------------------------------------------------------------------
    if meta.sonde_model == "SPC":
        tf = np.ones_like(pressure)
    else:
        tf = transfer_function(pressure)
    PO3_tf = PO3_pump * tf
    df["PO3_tf_mPa"] = PO3_tf
    df["tf_factor"]  = tf

    # ------------------------------------------------------------------
    # 5. Brewer total column normalization
    # ------------------------------------------------------------------
    norm = meta.normalization_factor  # emits a warning if absent
    PO3_dqa = PO3_tf * norm
    df["PO3_dqa_mPa"] = PO3_dqa
    df["norm_factor"]  = norm

    return df


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def load_sonde(fpath: Path | str) -> tuple[SondeMetadata, pd.DataFrame]:
    """
    Load and homogenize a single FMI SHARP ECC file.

    Usage :
        meta, df = load_sonde("so260415.q0")

        # Raw profile
        df["PO3_raw_mPa"]

        # DQA-homogenized profile
        df["PO3_dqa_mPa"]

        # Metadata
        meta.launch_datetime
        meta.serial_ecc
        meta.normalization_factor
    """
    fpath = Path(fpath)
    meta, df = parse_sharp(fpath)
    df = apply_dqa(df, meta)
    return meta, df


# ---------------------------------------------------------------------------
# Metadata summary (useful for quick verification)
# ---------------------------------------------------------------------------

def sonde_summary(meta: SondeMetadata) -> str:
    """Human-readable summary of a flight's metadata."""
    brewer_str = (
        f"{meta.col2b_du:.1f} DU (norm. factor = {meta.normalization_factor:.4f})"
        if meta.brewer_available
        else "not available"
    )
    return (
        f"{'=' * 55}\n"
        f"File           : {meta.fpath.name}\n"
        f"Date           : {meta.launch_date}  {meta.launch_hour_ut:.2f} UT\n"
        f"ECC Sonde      : {meta.serial_ecc} ({meta.sensor_type})\n"
        f"SST            : {meta.sst_concentration_gl} g/l "
        f"({'0.5%' if meta.sst_concentration_gl == 5.0 else '1%' if meta.sst_concentration_gl == 10.0 else '?'})\n"
        f"Flow rate      : {meta.flow_rate_s100cm3:.2f} s/100cm³\n"
        f"bg_pre / post  : {meta.bg_pre_ua:.3f} / {meta.bg_post_ua:.3f} µA\n"
        f"COL1           : {meta.col1_du} DU\n"
        f"Brewer (COL2B) : {brewer_str}\n"
        f"Levels         : {meta.n_levels}\n"
        f"Pump table     : {meta.pump_corr_table}\n"
        f"Bg method      : {meta.bg_method}\n"
        f"{'=' * 55}"
    )


# ---------------------------------------------------------------------------
# Loading multiple files
# ---------------------------------------------------------------------------

def load_sondes(fpaths: list[Path | str]) -> list[tuple[SondeMetadata, pd.DataFrame]]:
    """Load and homogenize a list of SHARP files."""
    results = []
    for fpath in fpaths:
        try:
            meta, df = load_sonde(fpath)
            print(sonde_summary(meta))
            results.append((meta, df))
        except Exception as e:
            warnings.warn(f"Error on {Path(fpath).name} : {e}", UserWarning)
    return results


# ---------------------------------------------------------------------------
# Quick test script
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import matplotlib.pyplot as plt

    if len(sys.argv) < 2:
        print("Usage: python sharp_dqa.py file1.q0 [file2.q0 ...]")
        sys.exit(1)

    files = [Path(f) for f in sys.argv[1:]]
    results = load_sondes(files)

    fig, axes = plt.subplots(1, 2, figsize=(10, 8), sharey=True)

    colors = ["tab:blue", "tab:orange", "tab:green", "tab:red"]
    for i, (meta, df) in enumerate(results):
        label = f"{meta.launch_date} ({meta.serial_ecc})"
        c = colors[i % len(colors)]
        alt = df["altitude_gpm"] / 1000  # km

        axes[0].plot(df["PO3_raw_mPa"], alt, color=c, linestyle="--",
                     alpha=0.5, label=f"{label} raw")
        axes[0].plot(df["PO3_dqa_mPa"], alt, color=c, linestyle="-",
                     label=f"{label} DQA")

        axes[1].plot(
            (df["PO3_dqa_mPa"] - df["PO3_raw_mPa"]) / df["PO3_raw_mPa"].replace(0, np.nan) * 100,
            alt, color=c, label=label
        )

    axes[0].set_xlabel("Ozone pressure (mPa)")
    axes[0].set_ylabel("Altitude (km)")
    axes[0].set_title("Raw vs DQA PO3")
    axes[0].legend(fontsize=7)
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xlim(left=0)

    axes[1].set_xlabel("Δ PO3 / PO3_raw (%)")
    axes[1].set_title("Impact of DQA homogenization")
    axes[1].axvline(0, color="k", linewidth=0.8)
    axes[1].legend(fontsize=7)
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("sharp_dqa_test.png", dpi=150)
    print("\nFigure saved : sharp_dqa_test.png")
    plt.show()