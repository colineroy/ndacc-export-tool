"""
woudc_export.py
===============
Export DQA-homogenised ECC ozonesonde profiles to WOUDC extCSV format.

WOUDC extCSV (extended CSV) is the international archiving standard
for ozone data at the World Ozone and Ultraviolet Radiation Data Centre
(WMO/GAW). This module generates files compliant with the specification:

    WOUDC Contributor Guide, Section 3.2-3.3
    https://guide.woudc.org/en/

Generated tables:
    #CONTENT          - class and category
    #DATA_GENERATION  - date, agency, version
    #PLATFORM         - Sodankyla station (GAW ID 02836)
    #INSTRUMENT       - ECC DMT-Z sonde
    #LOCATION         - FMI Sodankyla coordinates
    #TIMESTAMP        - launch UTC date/time
    #FLIGHT_SUMMARY   - IntegratedO3, CorrectionCode, SondeTotalO3
    #AUXILIARY_DATA   - operational metadata (bg, flow rate...)
    #PUMP_CORRECTION  - STOIC 1989 pump efficiency table
    #PROFILE          - full vertical profile

References:
    - WOUDC (2013): Data Submission Guide, extCSV format specification.
      https://guide.woudc.org/en/
    - Smit, H.G.J. and O3S-DQA Panel (2012): SI2N/O3S-DQA Activity: Guidelines
      for Homogenization of Ozone Sonde Data. SPARC-IGACO-IOC Report.
    - Poyraz, D. (2021): o3s-dqa-homogenization [source code, WOUDC CSV writer].
      https://github.com/denizpoyraz/o3s-dqa-homogenization
      (inspires the #FLIGHT_SUMMARY and #AUXILIARY_DATA table structure)

Author: Coline Roy - Internship FMI Sodankyla, 2026
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from sharp_dqa import SondeMetadata, PUMP_PRESSURE_HPA, PUMP_EFF_CORRECTION


# ---------------------------------------------------------------------------
# WOUDC codes
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

# CorrectionCode (WOUDC §3.3) :
#   0 = no correction
#   1 = Dobson total column
#   2 = Brewer total column
#   6 = ib2 constant background correction
# Use 6 (bg constant) combined with 2 (Brewer) -> composite value 8
# (Poyraz 2021 convention for full DQA with Brewer)
CORRECTION_CODE_DQA_BREWER  = 8
CORRECTION_CODE_DQA_NOBREWER = 6           # if Brewer unavailable

# ObsType : 0 = direct sun
OBS_TYPE = 0

# Sodankyla reference Brewer (for #OZONE_REFERENCE)
BREWER_NAME   = "Brewer"
BREWER_MODEL  = "MKIII"
BREWER_SERIAL = "178"
WL_CODE       = 9       # Brewer standard wavelength pair
UTC_MEAN      = "12:00:00"


# ---------------------------------------------------------------------------
# Formatting utilities
# ---------------------------------------------------------------------------

def _fmt(val, fmt=".3f", missing="") -> str:
    """Format a value or return an empty string for missing values."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return missing
    return format(val, fmt)


def _fmt_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _fmt_time(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    return dt.strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# extCSV block construction
# ---------------------------------------------------------------------------

def _block_content() -> str:
    return (
        "#CONTENT\n"
        "Class,Category,Level,Form\n"
        "WOUDC,OzoneSonde,1.0,1\n"
    )


def _block_data_generation(meta: SondeMetadata, generation_date: date, version: str = "1.0") -> str:
    return (
        "#DATA_GENERATION\n"
        "Date,Agency,Version,ScientificAuthority\n"
        f"{_fmt_date(generation_date)},{meta.agency},{version},{meta.scientific_authority}\n"
    )


def _block_platform(meta: SondeMetadata) -> str:
    return (
        "#PLATFORM\n"
        "Type,ID,Name,Country,GAW_ID\n"
        f"STN,{meta.station_id},{meta.station_name},{meta.station_country},{meta.station_gaw_id}\n"
    )


def _block_instrument(meta: SondeMetadata) -> str:
    # Name=ECC, Model=sonde_model (5A/6A/Z detected from serial),
    # Number=serial number
    model  = meta.sonde_model
    number = meta.serial_ecc if meta.serial_ecc else "na"
    return (
        "#INSTRUMENT\n"
        "Name,Model,Number\n"
        f"ECC,{model},{number}\n"
    )


def _block_location(meta: SondeMetadata) -> str:
    return (
        "#LOCATION\n"
        "Latitude,Longitude,Height\n"
        f"{meta.station_lat},{meta.station_lon},{meta.station_height}\n"
    )


def _block_timestamp(meta: SondeMetadata) -> str:
    dt = meta.launch_datetime
    date_str = _fmt_date(meta.launch_date) if meta.launch_date else ""
    time_str = _fmt_time(dt)
    return (
        "#TIMESTAMP\n"
        "UTCOffset,Date,Time\n"
        f"+00:00:00,{date_str},{time_str}\n"
    )


def _block_flight_summary(meta: SondeMetadata, df: pd.DataFrame) -> str:
    """
    #FLIGHT_SUMMARY
    Fields: IntegratedO3, CorrectionCode, SondeTotalO3,
            CorrectionFactor, TotalO3, WLCode, ObsType, Instrument, Number

    IntegratedO3  = COL1 corrected by DQA factor (integrated PO3_dqa)
    SondeTotalO3  = raw COL1 (integrated PO3_raw)
    CorrectionFactor = COL2B / COL1 (empty if Brewer absent)
    TotalO3, WLCode, ObsType, Instrument, Number

    NOTE - TotalO3, WLCode, ObsType, Instrument, Number fields are left
    EMPTY here following the official WOUDC example
    (https://woudc.org/archive/Documentation/Examples-extCSV/Ozonesonde.csv).
    These values are now reported in #OZONE_REFERENCE.
    """
    col_dqa  = _integrate_col(df["pressure_hPa"].values, df["PO3_dqa_mPa"].values)

    corr_code = (
        CORRECTION_CODE_DQA_BREWER
        if meta.brewer_available
        else CORRECTION_CODE_DQA_NOBREWER
    )

    col_dqa_str = _fmt(col_dqa, ".1f")
    # SondeTotalO3 = COL1 as reported by SHARP (DigiCORA reference),
    # not recomputed - this follows the official example (373.3 = reported
    # value, not a numerical re-integration of PO3_raw).
    sonde_total_str = _fmt(meta.col1_du, ".1f")

    return (
        "#FLIGHT_SUMMARY\n"
        "IntegratedO3,CorrectionCode,SondeTotalO3,"
        "CorrectionFactor,TotalO3,WLCode,ObsType,Instrument,Number\n"
        f"{col_dqa_str},{corr_code},{sonde_total_str}\n"
    )


def _integrate_col(pressure: np.ndarray, po3_mpa: np.ndarray) -> float:
    """
    Integrate PO3 [mPa] over the pressure profile to compute the total
    column in Dobson Units (DU).

    Rigorous derivation (hydrostatic + ideal gas law for O3 and air):

        n_O3 = P_O3 / (k_B T)                      (O3 number density)
        dz = -dP / (rho_air g),  rho_air = P M_air / (R T)   (hydrostatic)

        => column [molec/m^2] = (N_A / (M_air g)) x integral (P_O3/P) dP

    With P_O3 and P in pascals. For P_O3 in mPa and P in hPa (conversion
    1e-3 and 1e2 respectively), the constant simplifies to:

        C = (N_A / (M_air x g)) x 1e-3   [molec/m^2 per unit integral (mPa/hPa).hPa]

    Final conversion to DU (1 DU = 2.6868e20 molec/m^2):

        C_DU = C / DU ~ 7.891 DU per unit integral integral(PO3[mPa]/P[hPa]) dP[hPa]

    Important: integration is over P (trapezoids), NOT over ln(P).
    A previous version incorrectly integrated over d(ln P) with a
    different constant, overestimating the column by a factor of
    ~2.5-3x (bug identified on real Sodankyla 2024 profiles where
    IntegratedO3 came out at 865-891 DU instead of the expected ~330-360 DU).

    Constants used: N_A = 6.02214076e23 /mol (CODATA),
    M_air = 28.9644e-3 kg/mol (dry air), g = 9.80665 m/s^2 (standard g),
    1 DU = 2.6868e20 molec/m^2 (standard definition).
    """
    N_A   = 6.02214076e23   # /mol
    M_AIR = 28.9644e-3      # kg/mol
    G     = 9.80665         # m/s^2
    DU    = 2.6868e20       # molec/m^2 per DU

    C_DU = (N_A / (M_AIR * G)) * 1e-3 / DU   # ≈ 7.891

    valid = ~(np.isnan(pressure) | np.isnan(po3_mpa)) & (pressure > 0) & (po3_mpa >= 0)
    p  = pressure[valid]
    o3 = po3_mpa[valid]

    if len(p) < 2:
        return np.nan

    # Sort by decreasing pressure (balloon ascent order)
    idx = np.argsort(p)[::-1]
    p  = p[idx]
    o3 = o3[idx]

    # Trapezoids over P directly (not ln P): integral (PO3/P) dP
    ratio = o3 / p
    col   = np.trapezoid(ratio, -p) * C_DU   # -p because P decreases with altitude
    return float(col)


def _block_auxiliary_data(meta: SondeMetadata) -> str:
    """
    #AUXILIARY_DATA
    Operational ground metadata (inspired by Poyraz 2021 and
    the official WOUDC example).

    Fields: MeteoSonde, ib1, ib2, PumpRate, BackgroundCorr,
            SampleTemperatureType, MinutesGroundO3

    ib1 is left EMPTY (WOUDC convention): only the background
    current used for correction (bg_post = ib2) is archived.
    BackgroundCorr is read from meta.bg_method.
    """
    ib2      = _fmt(meta.bg_post_ua, ".3f")
    pumprate = _fmt(meta.flow_rate_s100cm3, ".2f")
    bg_corr  = meta.bg_method if meta.bg_method else "Constant_ib2"
    meteo    = meta.meteosonde or "Vaisala RS41/DigiCORA MW41"
    minutes_gnd = "10.00"

    return (
        "#AUXILIARY_DATA\n"
        "MeteoSonde,ib1,ib2,PumpRate,BackgroundCorr,"
        "SampleTemperatureType,MinutesGroundO3\n"
        f"{meteo},,{ib2},{pumprate},{bg_corr},Pump,{minutes_gnd}\n"
    )


def _block_ozone_reference(meta: SondeMetadata, version: str = "1.0") -> str:
    """
    #OZONE_REFERENCE
    Reference total ozone (Brewer) used for DQA normalization.

    Fields (WOUDC section 3.3.4.8):
        Name, Model, Number, Version, TotalO3, WLCode, ObsType, UTC_Mean
    """
    total_o3 = _fmt(meta.col2b_du, ".1f") if meta.brewer_available else ""
    model    = meta.brewer_model or BREWER_MODEL
    number   = meta.brewer_serial or BREWER_SERIAL
    return (
        "#OZONE_REFERENCE\n"
        "Name,Model,Number,Version,TotalO3,WLCode,ObsType,UTC_Mean\n"
        f"{BREWER_NAME},{model},{number},{version},"
        f"{total_o3},{WL_CODE},{OBS_TYPE},{UTC_MEAN}\n"
    )


def _block_pump_correction() -> str:
    """
    #PUMP_CORRECTION
    STOIC 1989 pump efficiency correction table used.
    (Smit & O3S-DQA 2012, Table A1)
    """
    lines = ["#PUMP_CORRECTION", "Pressure,Correction"]
    # Ascending pressure order (WOUDC convention, as in the Alert example)
    p_sorted = PUMP_PRESSURE_HPA[::-1]   # 1 hPa -> 1000 hPa
    c_sorted = PUMP_EFF_CORRECTION[::-1]
    for p, c in zip(p_sorted, c_sorted):
        lines.append(f"{p:.1f},{c:.3f}")
    return "\n".join(lines) + "\n"


def _block_profile(df: pd.DataFrame) -> str:
    """
    #PROFILE
    Vertical profile with DQA-homogenised PO3.

    Standard WOUDC columns:
        Pressure          [hPa]
        O3PartialPressure [mPa]   <- PO3_dqa (homogenised)
        Temperature       [degC]
        WindSpeed         [m/s]
        WindDirection     [deg]
        LevelCode         []
        Duration          [s]
        GPHeight          [gpm]
        RelativeHumidity  [%]
        SampleTemperature [degC]    <- temp_box_C (internal box T)
        SondeCurrent      [uA]   <- reconstructed I_raw (PO3_raw x Q / alpha T)

    Note: O3PartialPressure = PO3_dqa (bg + pump + TF + Brewer normalisation corrected).
    The raw PO3_raw profile is kept in the Python DataFrame but is NOT
    included in the WOUDC file (only the homogenised version is archived).

    LevelCode - WOUDC convention observed in the official example
    (https://woudc.org/archive/Documentation/Examples-extCSV/Ozonesonde.csv):
        0 = standard measurement level (most rows)
        3 = standard/round pressure level (1000, 850, 700, 500, 400,
            300, 250, 200, 150, 100, 70, 50, 30, 20, 10, 7, 5, 3, 2, 1 hPa)
        2 = level with one or more missing variables
    This implementation is a best-effort APPROXIMATION: mark 3 at standard
    pressure levels (with tolerance), 2 if SampleTemperature or wind are
    missing at that level, 0 otherwise. The exact LevelCode semantics used
    historically by FMI should be confirmed with Rigel; this field cannot be
    derived with certainty from SHARP format alone.
    """
    STANDARD_PRESSURES_HPA = [
        1000, 850, 700, 500, 400, 300, 250, 200, 150, 100,
        70, 50, 30, 20, 10, 7, 5, 3, 2, 1
    ]

    def _level_code(p, t_samp, wspd) -> str:
        if p is not None and not (isinstance(p, float) and np.isnan(p)):
            for sp in STANDARD_PRESSURES_HPA:
                # Absolute tolerance of 0.5 hPa: a "standard" pressure
                # level in the WOUDC sense corresponds to a round value
                # explicitly targeted by the radiosonde (e.g. 1000.00,
                # 850.00 hPa), not an incidental nearby value.
                if abs(p - sp) < 0.5:
                    return "3"
        missing = (
            (t_samp is None or (isinstance(t_samp, float) and np.isnan(t_samp))) or
            (wspd is None or (isinstance(wspd, float) and np.isnan(wspd)))
        )
        return "2" if missing else "0"

    lines = [
        "#PROFILE",
        "Pressure,O3PartialPressure,Temperature,WindSpeed,WindDirection,"
        "LevelCode,Duration,GPHeight,RelativeHumidity,SampleTemperature,"
        "SondeCurrent"
    ]

    for _, row in df.iterrows():
        p_raw   = row.get("pressure_hPa")
        t_samp_raw = row.get("temp_box_C")
        wspd_raw   = row.get("wind_spd_ms")

        p      = _fmt(p_raw,             ".2f")
        po3    = _fmt(row.get("PO3_dqa_mPa"),    ".3f")
        temp   = _fmt(row.get("temp_C"),          ".1f")
        wspd   = _fmt(wspd_raw,           ".1f")
        wdir   = _fmt(row.get("wind_dir_deg"),    ".0f")
        dur    = _fmt(row.get("time_s"),          ".0f")
        gph    = _fmt(row.get("altitude_gpm"),    ".0f")
        rh     = _fmt(row.get("rh_pct"),          ".0f")
        t_samp = _fmt(t_samp_raw,         ".1f")
        lvl    = _level_code(p_raw, t_samp_raw, wspd_raw)
        curr   = _fmt(row.get("sonde_current_ua"), ".3f")

        lines.append(
            f"{p},{po3},{temp},{wspd},{wdir},{lvl},{dur},{gph},{rh},{t_samp},{curr}"
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

def write_woudc_csv(
    meta: SondeMetadata,
    df: pd.DataFrame,
    output_dir: Path | str = ".",
    version: str = "1.0",
    generation_date: Optional[date] = None,
) -> Path:
    """
    Write a DQA-homogenised WOUDC extCSV file.

    Parameters
    ----------
    meta           : SondeMetadata - flight metadata
    df             : DataFrame - profile with PO3_dqa_mPa column (from apply_dqa)
    output_dir     : output directory
    version        : processing version (e.g. "1.0")
    generation_date: file generation date (default: today)

    Returns
    -------
    Path of the created file.

    Filename: YYYYMMDD.ECC.Z.<serial>.FMI.csv
    WOUDC Archive-NewFormat convention.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if generation_date is None:
        generation_date = date.today()

    # Verify that apply_dqa() was called
    if "PO3_dqa_mPa" not in df.columns:
        raise ValueError(
            "Column 'PO3_dqa_mPa' is missing from the DataFrame. "
            "Call apply_dqa() before write_woudc_csv()."
        )

    # WOUDC file naming convention
    date_str   = meta.launch_date.strftime("%Y%m%d") if meta.launch_date else "00000000"
    model_str  = meta.sonde_model
    serial_str = meta.serial_ecc.replace(" ", "") if meta.serial_ecc else "na"
    agency_str = meta.agency.replace("/", "-").replace(" ", "")
    filename   = f"{date_str}.ECC.{model_str}.{serial_str}.{agency_str}.csv"
    fout       = output_dir / filename

    # Assemble blocks
    blocks = [
        _block_content(),
        _block_data_generation(meta, generation_date, version),
        _block_platform(meta),
        _block_instrument(meta),
        _block_location(meta),
        _block_timestamp(meta),
        _block_flight_summary(meta, df),
        _block_auxiliary_data(meta),
        _block_ozone_reference(meta, version),
        _block_pump_correction(),
        _block_profile(df),
    ]

    content = "\n\n".join(b.rstrip("\n") for b in blocks) + "\n"

    fout.write_text(content, encoding="utf-8")
    print(f"WOUDC file written: {fout}")
    return fout


# ---------------------------------------------------------------------------
# Export batch
# ---------------------------------------------------------------------------

def write_woudc_batch(
    results: list[tuple[SondeMetadata, pd.DataFrame]],
    output_dir: Path | str = "woudc_output",
    version: str = "1.0",
) -> list[Path]:
    """
    Export a list of (meta, df) tuples to WOUDC CSV files.

    Usage:
        from sharp_dqa import load_sondes
        from woudc_export import write_woudc_batch

        results = load_sondes(["so260331.q0", "so260415.q0", "so260430.q0"])
        write_woudc_batch(results, output_dir="woudc_dqa")
    """
    output_dir = Path(output_dir)
    written = []
    for meta, df in results:
        try:
            fout = write_woudc_csv(meta, df, output_dir=output_dir, version=version)
            written.append(fout)
        except Exception as e:
            import warnings
            warnings.warn(f"Export error {meta.fpath.name}: {e}", UserWarning)
    return written


# ---------------------------------------------------------------------------
# Test script
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from sharp_dqa import load_sondes

    if len(sys.argv) < 2:
        print("Usage: python woudc_export.py file1.q0 [file2.q0 ...]")
        sys.exit(1)

    files   = [Path(f) for f in sys.argv[1:]]
    results = load_sondes(files)
    written = write_woudc_batch(results, output_dir="woudc_dqa")

    print(f"\n{len(written)} WOUDC file(s) generated in woudc_dqa/")
    for f in written:
        print(f"  {f.name}")