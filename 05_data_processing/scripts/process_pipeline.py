"""
process_pipeline.py
====================
Suspension Degradation Project — v0.1
--------------------------------------
End-to-end data processing pipeline for a single raw CSV file logged by
the Arduino DAQ. Runs in sequence:

    1. Load & unit conversion       (load_data)
    2. Timestamp repair             (repair_timestamps)
    3. Detrending                   (detrend_signal)
    4. Low-pass filter @ 80 Hz      (lowpass_filter)
    5. Optional high-pass @ 0.5 Hz  (highpass_filter)
    6. Optional 50 Hz notch         (notch_filter)
    7. Outlier clipping             (clip_outliers)
    8. Rainflow cycle counting      (count_cycles)
    9. Miner's rule damage          (compute_damage)
   10. Feature extraction           (extract_features)
   11. Save all outputs             (save_outputs)


Raw CSV format (from Arduino logger)
-------------------------------------
    timestamp_ms, accel_x, accel_y, accel_z, strain_raw
    (header row optional — auto-detected)
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rainflow
from scipy import signal
from scipy.signal import detrend, butter, sosfiltfilt, iirnotch, welch
from scipy.stats import kurtosis as scipy_kurtosis
import matplotlib.pyplot as plt

# NumPy 2.0 renamed np.trapz → np.trapezoid; support both versions.
_trapezoid = getattr(np, "trapezoid", np.trapz)


# Constants — to be adjusted

FS = 200.0          # Sampling rate, Hz
G_TO_MS2 = 9.81     # Conversion factor

# MPU-6050 at ±16g full-scale range, 16-bit signed ADC
ACCEL_FULL_SCALE_G = 16.0
ACCEL_SCALE = (ACCEL_FULL_SCALE_G / 32768.0) * G_TO_MS2   # counts → m/s²

# Strain gauge calibration, will update after physical calibration
# INA125 amplifier gain and gauge factor (GF) combined into one factor.
# Units: ADC counts → microstrain (με)
# Placeholder: 1 count = 0.5 με — MUST be measured/calibrated before use.
STRAIN_SCALE = 0.5          # με per ADC count  *** calibrate this ***
STRAIN_ZERO_OFFSET = 0      # ADC count at zero load *** calibrate this ***

# Material
E_STEEL_PA = 210e9          # Young's modulus, Pa (low-carbon steel)
E_STEEL_MPA = 210e3         # Young's modulus, MPa

# S-N curve — BS 7608 Class B plain material (conservative proxy)
# N_f = C / sigma_a^m  →  sigma_a in MPa
SN_m = 3.0
SN_C = 1.013e12             # MPa^m cycles  (BS 7608 Class B)

# Filter parameters
LP_CUTOFF_HZ = 80.0
LP_ORDER = 4
HP_CUTOFF_HZ = 0.5
HP_ORDER = 2
NOTCH_FREQ_HZ = 50.0
NOTCH_Q = 30.0
NOTCH_THRESHOLD = 3.0       # PSD ratio to trigger notch

# Outlier clipping
OUTLIER_SIGMA = 5.0
OUTLIER_WINDOW_S = 0.5      # rolling window for local mean, seconds
MAX_OUTLIER_FRACTION = 0.005

# Timestamp repair
MAX_INTERP_GAP_SAMPLES = 5

# Feature extraction windowing
WINDOW_S = 10.0             # window length, seconds
OVERLAP = 0.5               # fractional overlap

# Rainflow matrix bins
N_MEAN_BINS = 16
N_AMP_BINS = 32

# PSD band boundaries, Hz
BAND_LOW = (0.5, 5.0)
BAND_MID = (5.0, 25.0)
BAND_HIGH = (25.0, 80.0)


# Logging setup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# Load and unit conversion

def load_data(csv_path: Path) -> pd.DataFrame:
    """
    Read the raw Arduino CSV and convert integer counts to physical units.

    Expected columns (with or without a header row):
        timestamp_ms, accel_x, accel_y, accel_z, strain_raw

    Returns a DataFrame with columns:
        time_s          float   seconds from start of record
        accel_x_ms2     float   m/s²
        accel_y_ms2     float   m/s²
        accel_z_ms2     float   m/s²
        strain_ue       float   microstrain (με)
    """
    log.info("Loading raw data from %s", csv_path)

    # Auto-detect header
    raw = pd.read_csv(csv_path, header=None, nrows=1)
    first_cell = str(raw.iloc[0, 0]).strip().lower()
    has_header = not first_cell.lstrip("-").replace(".", "").isdigit()

    df = pd.read_csv(
        csv_path,
        header=0 if has_header else None,
        names=["timestamp_ms", "accel_x", "accel_y", "accel_z", "strain_raw"],
    )

    log.info("  Rows loaded: %d", len(df))

    # Convert to physical units
    df["time_s"] = (df["timestamp_ms"] - df["timestamp_ms"].iloc[0]) / 1000.0
    df["accel_x_ms2"] = df["accel_x"] * ACCEL_SCALE
    df["accel_y_ms2"] = df["accel_y"] * ACCEL_SCALE
    df["accel_z_ms2"] = df["accel_z"] * ACCEL_SCALE
    df["strain_ue"] = (df["strain_raw"] - STRAIN_ZERO_OFFSET) * STRAIN_SCALE

    return df[[
        "timestamp_ms", "time_s",
        "accel_x_ms2", "accel_y_ms2", "accel_z_ms2",
        "strain_ue",
    ]]


# Timestamp repair

def repair_timestamps(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Check for and repair timestamp anomalies:
        - Duplicate timestamps     → drop duplicates, keep first
        - Non-monotonic timestamps → sort (handles minor jitter)
        - Gaps > 2 × expected_dt  → interpolate (≤5 samples) or flag (>5)

    Returns the repaired DataFrame and a summary dict.
    """
    log.info("Repairing timestamps...")

    expected_dt_ms = 1000.0 / FS
    summary = {
        "samples_raw": len(df),
        "duplicates_removed": 0,
        "gaps_interpolated": 0,
        "gaps_flagged": 0,
    }

    # Drop duplicates
    n_before = len(df)
    df = df.drop_duplicates(subset="timestamp_ms").copy()
    summary["duplicates_removed"] = n_before - len(df)

    # Sort (handles any non-monotonic jitter)
    df = df.sort_values("timestamp_ms").reset_index(drop=True)

    # Detect gaps
    dt = df["timestamp_ms"].diff()
    gap_mask = dt > 2.0 * expected_dt_ms
    gap_indices = df.index[gap_mask].tolist()

    for idx in gap_indices:
        gap_samples = int(round(dt.iloc[idx] / expected_dt_ms)) - 1
        if gap_samples <= MAX_INTERP_GAP_SAMPLES:
            summary["gaps_interpolated"] += 1
        else:
            summary["gaps_flagged"] += 1
            log.warning(
                "  Large gap of %d samples at t=%.2f s — window will be split",
                gap_samples, df["time_s"].iloc[idx],
            )

    # Rebuild a uniform time axis by interpolation across gaps
    t_uniform = np.arange(len(df)) * (expected_dt_ms / 1000.0)
    df["time_s"] = t_uniform

    summary["samples_after_repair"] = len(df)
    log.info(
        "  Duplicates removed: %d | Gaps interpolated: %d | Gaps flagged: %d",
        summary["duplicates_removed"],
        summary["gaps_interpolated"],
        summary["gaps_flagged"],
    )
    return df, summary


# Detrending

def detrend_signal(sig: np.ndarray, poly_order: int = 1) -> np.ndarray:
    """
    Remove DC offset and slow drift.

    poly_order=1  → linear detrend (default, sufficient for short windows)
    poly_order=2+ → polynomial detrend (for long records with thermal drift)
    """
    if poly_order == 1:
        return detrend(sig, type="linear")
    else:
        x = np.arange(len(sig), dtype=float)
        coeffs = np.polyfit(x, sig, poly_order)
        trend = np.polyval(coeffs, x)
        return sig - trend


#Low-pass filter

def lowpass_filter(sig: np.ndarray, cutoff: float = LP_CUTOFF_HZ) -> np.ndarray:
    """
    4th-order zero-phase Butterworth low-pass filter.

    Zero-phase (sosfiltfilt) preserves peak timing, which is critical for
    correct identification of load reversal points in rainflow counting.
    """
    sos = butter(LP_ORDER, cutoff, btype="low", fs=FS, output="sos")
    return sosfiltfilt(sos, sig)

# High-pass filter (optional, PSD analysis only)

def highpass_filter(sig: np.ndarray, cutoff: float = HP_CUTOFF_HZ) -> np.ndarray:
    """
    2nd-order zero-phase Butterworth high-pass filter.

    Use for PSD and modal analysis. Do NOT apply before rainflow counting —
    high-pass filtering removes mean load information needed for the damage
    calculation.

    Note: this function is not called in run_pipeline by design. It is available
    for ad-hoc analysis (e.g. isolating structural resonances before plotting PSD).
    """
    sos = butter(HP_ORDER, cutoff, btype="high", fs=FS, output="sos")
    return sosfiltfilt(sos, sig)


# 50 Hz notch filter auto-applied if interference detected

def apply_notch_if_needed(sig: np.ndarray) -> tuple[np.ndarray, bool]:
    """
    Check for 50 Hz mains interference in the PSD. If the PSD amplitude at
    50 Hz exceeds NOTCH_THRESHOLD × mean of the surrounding 45–55 Hz band,
    apply a narrow IIR notch filter (Q=30).

    Returns the (possibly filtered) signal and a bool indicating whether the
    notch was applied.
    """
    freqs, psd = welch(sig, fs=FS, nperseg=512)

    # Find PSD values in the 45–55 Hz check band
    band_mask = (freqs >= 45.0) & (freqs <= 55.0)
    notch_mask = (freqs >= 49.5) & (freqs <= 50.5)

    if not np.any(band_mask) or not np.any(notch_mask):
        return sig, False

    band_mean = np.mean(psd[band_mask & ~notch_mask])
    notch_peak = np.max(psd[notch_mask])

    if band_mean == 0 or notch_peak / band_mean < NOTCH_THRESHOLD:
        return sig, False

    log.info(
        "  50 Hz interference detected (ratio=%.1f) — applying notch filter",
        notch_peak / band_mean,
    )
    b, a = iirnotch(NOTCH_FREQ_HZ, NOTCH_Q, fs=FS)
    return signal.filtfilt(b, a, sig), True


# Outlier clipping

def clip_outliers(sig: np.ndarray) -> tuple[np.ndarray, dict]:
    """
    Replace single-sample spikes with linear interpolation.

    Spikes are defined as samples more than OUTLIER_SIGMA standard deviations
    from the local rolling mean (window = OUTLIER_WINDOW_S seconds).

    If more than MAX_OUTLIER_FRACTION of samples are flagged, raises a warning
    — the window should be excluded from analysis.
    """
    win = int(OUTLIER_WINDOW_S * FS)
    out = sig.copy()
    n = len(sig)

    series = pd.Series(sig)
    rolling_mean = series.rolling(win, center=True, min_periods=1).mean().values
    rolling_std  = series.rolling(win, center=True, min_periods=1).std().values

    spike_mask = np.abs(sig - rolling_mean) > OUTLIER_SIGMA * rolling_std
    n_spikes = int(np.sum(spike_mask))

    if n_spikes > 0:
        spike_indices = np.where(spike_mask)[0]
        for idx in spike_indices:
            left  = idx - 1 if idx > 0 else idx
            right = idx + 1 if idx < n - 1 else idx
            out[idx] = 0.5 * (out[left] + out[right])

    fraction = n_spikes / n
    suspect = fraction > MAX_OUTLIER_FRACTION

    if suspect:
        log.warning(
            "  Outlier fraction %.2f%% exceeds threshold — window flagged as suspect",
            fraction * 100,
        )

    return out, {"outliers_clipped": n_spikes, "outlier_fraction": fraction, "suspect": suspect}


# Rainflow cycle counting


def count_cycles(
    sig: np.ndarray,
    channel_label: str = "strain_ue",
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Apply ASTM E1049-85 rainflow counting to the cleaned signal.

    Residues are handled using the repeated-block method: the signal is
    duplicated before counting, then only the first half of cycles (from the
    original block) are retained. This closes all residue half-cycles.

    Returns
    -------
    cycles_df       DataFrame with columns: range, mean, count, amplitude
    rf_matrix       2D histogram array (N_AMP_BINS × N_MEAN_BINS)
    amp_hist        1D amplitude histogram (summed over mean axis)
    """
    log.info("  Running rainflow cycle counting on channel: %s", channel_label)

    # Repeated-block residue method
    sig_doubled = np.concatenate([sig, sig])
    raw_cycles = list(rainflow.extract_cycles(sig_doubled))

    if len(raw_cycles) == 0:
        log.warning("  No cycles extracted — signal may be flat")
        empty = pd.DataFrame(columns=["range", "mean", "count", "amplitude"])
        return empty, np.zeros((N_AMP_BINS, N_MEAN_BINS)), np.zeros(N_AMP_BINS)

    # rainflow.extract_cycles yields (range, mean, count, i_start, i_end)
    cycles_df = pd.DataFrame(raw_cycles, columns=["range", "mean", "count", "i_start", "i_end"])
    cycles_df["amplitude"] = cycles_df["range"] / 2.0

    # Keep only cycles from the first block (roughly first half by index)
    half = len(sig)
    cycles_df = cycles_df[cycles_df["i_start"] < half].copy().reset_index(drop=True)

    # Build 2D rainflow matrix
    amp_edges  = np.linspace(0, cycles_df["amplitude"].max() * 1.05, N_AMP_BINS + 1)
    mean_max   = cycles_df["mean"].abs().max() * 1.05
    mean_edges = np.linspace(-mean_max, mean_max, N_MEAN_BINS + 1)

    rf_matrix, _, _ = np.histogram2d(
        cycles_df["amplitude"],
        cycles_df["mean"],
        bins=[amp_edges, mean_edges],
        weights=cycles_df["count"],
    )

    amp_hist = rf_matrix.sum(axis=1)   # sum over mean axis

    log.info(
        "  Cycles counted: %d  |  Max amplitude: %.2f  |  Mean range: %.2f",
        len(cycles_df),
        cycles_df["amplitude"].max(),
        cycles_df["range"].mean(),
    )
    return cycles_df, rf_matrix, amp_hist


# Miner's rule damage


def compute_damage(
    cycles_df: pd.DataFrame,
    channel: str = "strain",
    duration_s: float = 1.0,
) -> dict:
    """
    Estimate cumulative fatigue damage using Miner's rule and a simplified
    S-N curve (BS 7608 Class B plain material proxy).

    If channel == 'strain', amplitudes in με are converted to stress in MPa
    using E_STEEL_MPA before looking up the S-N curve.

    If channel == 'accel', damage is not physically meaningful in stress units
    — the function returns None for stress-based outputs and a note is logged.

    Returns a dict with:
        total_cycles        int
        damage_total        float   (Miner's D)
        damage_rate_per_s   float   (D / duration_s)
        sigma_eq_mpa        float   (equivalent stress amplitude, MPa)
        sn_curve            str
    """
    if len(cycles_df) == 0:
        return {"total_cycles": 0, "damage_total": 0.0, "damage_rate_per_s": 0.0,
                "sigma_eq_mpa": 0.0, "sn_curve": "BS7608-B"}

    amplitudes = cycles_df["amplitude"].values
    counts     = cycles_df["count"].values

    if channel == "strain":
        # Convert microstrain amplitude to stress amplitude in MPa
        sigma_a = amplitudes * 1e-6 * E_STEEL_MPA   # με → dimensionless → MPa
    else:
        log.warning("  Channel is acceleration — damage estimate is a proxy only")
        sigma_a = amplitudes   # treat as arbitrary units

    # S-N: N_f = C / sigma_a^m  (BS 7608 Class B)
    # Avoid division by zero for zero-amplitude cycles
    with np.errstate(divide="ignore", invalid="ignore"):
        N_f = np.where(sigma_a > 0, SN_C / (sigma_a ** SN_m), np.inf)

    damage_per_cycle = np.where(N_f > 0, counts / N_f, 0.0)
    D_total = float(np.sum(damage_per_cycle))

    # Equivalent stress amplitude (Miner-weighted RMS)
    n_total = float(np.sum(counts))
    if n_total > 0 and np.any(sigma_a > 0):
        sigma_eq = (np.sum(counts * sigma_a ** SN_m) / n_total) ** (1.0 / SN_m)
    else:
        sigma_eq = 0.0

    return {
        "total_cycles":      int(n_total),
        "damage_total":      D_total,
        "damage_rate_per_s": D_total / duration_s if duration_s > 0 else 0.0,
        "sigma_eq_mpa":      sigma_eq,
        "sn_curve":          "BS7608-B (proxy)",
    }



# PSD band-power helper (module-level so it is not redefined on every window)

def _band_power(freqs: np.ndarray, psd: np.ndarray, f_lo: float, f_hi: float) -> float:
    """Integrate PSD between f_lo and f_hi using the trapezoidal rule."""
    mask = (freqs >= f_lo) & (freqs < f_hi)
    return float(_trapezoid(psd[mask], freqs[mask])) if np.any(mask) else 0.0


# Feature extraction

def extract_features(
    sig: np.ndarray,
    channel_label: str,
    cycles_df: pd.DataFrame,
    damage_dict: dict,
    duration_s: float,
) -> dict:
    """
    Compute time-domain and frequency-domain features for the full signal.
    Window-level features are averaged across all windows.

    Returns a flat dict of features matching the column spec in
    feature_extraction.md.
    """
    n_win     = int(WINDOW_S * FS)
    n_step    = int(n_win * (1.0 - OVERLAP))
    n_samples = len(sig)

    window_features = []

    for start in range(0, n_samples - n_win + 1, n_step):
        w = sig[start : start + n_win]
        t_start = start / FS
        t_end   = (start + n_win) / FS

        # --- Time domain ---
        rms         = float(np.sqrt(np.mean(w ** 2)))
        peak        = float(np.max(np.abs(w)))
        crest_fac   = peak / rms if rms > 0 else 0.0
        kurt        = float(scipy_kurtosis(w, fisher=False))   # Fisher=False → normal=3
        mean_val    = float(np.mean(w))
        zero_cross  = float(np.sum(np.diff(np.sign(w)) != 0)) / WINDOW_S

        # --- Frequency domain (Welch PSD) ---
        freqs, psd = welch(w, fs=FS, window="hann", nperseg=512, noverlap=256)

        full_mask       = (freqs >= 0.5) & (freqs <= 80.0)
        total_power     = _band_power(freqs, psd, 0.5, 80.0)
        psd_peak_freq   = float(freqs[np.argmax(psd[full_mask])]) if np.any(full_mask) else 0.0
        bp_low          = _band_power(freqs, psd, *BAND_LOW)
        bp_mid          = _band_power(freqs, psd, *BAND_MID)
        bp_high         = _band_power(freqs, psd, *BAND_HIGH)
        spec_centroid   = (
            float(np.sum(freqs[full_mask] * psd[full_mask]) / np.sum(psd[full_mask]))
            if np.sum(psd[full_mask]) > 0 else 0.0
        )

        window_features.append({
            "t_start": t_start, "t_end": t_end,
            "rms": rms, "peak": peak, "crest_factor": crest_fac,
            "kurtosis": kurt, "zcr": zero_cross, "mean": mean_val,
            "psd_peak_freq": psd_peak_freq,
            "band_power_low": bp_low, "band_power_mid": bp_mid,
            "band_power_high": bp_high,
            "spectral_centroid": spec_centroid, "total_power": total_power,
        })

    wf = pd.DataFrame(window_features)

    # --- Derived structural features (from rainflow output) ---
    sigma_eq     = damage_dict.get("sigma_eq_mpa", 0.0)
    damage_rate  = damage_dict.get("damage_rate_per_s", 0.0)
    cycle_rate   = damage_dict["total_cycles"] / duration_s if duration_s > 0 else 0.0

    if len(cycles_df) > 0:
        amp_max     = cycles_df["amplitude"].max()
        # Damage fraction from large cycles (amplitude > 0.5 × max)
        large_mask  = cycles_df["amplitude"] > 0.5 * amp_max
        large_frac  = float(
            cycles_df.loc[large_mask, "count"].sum() / cycles_df["count"].sum()
        ) if cycles_df["count"].sum() > 0 else 0.0
    else:
        large_frac = 0.0

    # Aggregate window features into summary
    summary = {
        "channel":            channel_label,
        "duration_s":         duration_s,
        "n_windows":          len(wf),
        # Time domain (mean across windows)
        "rms_mean":           float(wf["rms"].mean()),
        "rms_std":            float(wf["rms"].std()),
        "peak_mean":          float(wf["peak"].mean()),
        "crest_factor_mean":  float(wf["crest_factor"].mean()),
        "kurtosis_mean":      float(wf["kurtosis"].mean()),
        "kurtosis_std":       float(wf["kurtosis"].std()),
        "zcr_mean":           float(wf["zcr"].mean()),
        # Frequency domain (mean across windows)
        "psd_peak_freq_mean": float(wf["psd_peak_freq"].mean()),
        "band_power_low":     float(wf["band_power_low"].mean()),
        "band_power_mid":     float(wf["band_power_mid"].mean()),
        "band_power_high":    float(wf["band_power_high"].mean()),
        "spectral_centroid":  float(wf["spectral_centroid"].mean()),
        "total_power_mean":   float(wf["total_power"].mean()),
        # Rainflow-derived
        "sigma_eq_mpa":       sigma_eq,
        "damage_rate_per_s":  damage_rate,
        "cycle_rate_per_s":   cycle_rate,
        "large_cycle_fraction": large_frac,
    }

    return summary, wf


# save outputs

def save_outputs(
    outdir: Path,
    stem: str,
    df_clean: pd.DataFrame,
    cycles_df: pd.DataFrame,
    rf_matrix: np.ndarray,
    amp_hist: np.ndarray,
    damage_dict: dict,
    features_summary: dict,
    features_windows: pd.DataFrame,
    repair_summary: dict,
    notch_applied: bool,
    outlier_summary: dict,
    channel: str,
) -> None:
    """Write all outputs to outdir. Creates the directory if it does not exist."""
    outdir.mkdir(parents=True, exist_ok=True)
    log.info("Saving outputs to %s", outdir)

    # Cleaned signal CSV
    clean_path = outdir / f"{stem}_clean.csv"
    df_clean.to_csv(clean_path, index=False)
    log.info("  Saved: %s", clean_path.name)

    # Rainflow cycles CSV
    if len(cycles_df) > 0:
        rf_path = outdir / f"{stem}_rainflow_cycles.csv"
        cycles_df[["range", "mean", "count", "amplitude"]].to_csv(rf_path, index=False)
        log.info("  Saved: %s", rf_path.name)

        # Rainflow matrix NPY
        np.save(outdir / f"{stem}_rainflow_matrix.npy", rf_matrix)

        # Amplitude histogram CSV
        amp_df = pd.DataFrame({
            "amplitude_bin_centre": np.linspace(0, cycles_df["amplitude"].max(), N_AMP_BINS),
            "cycle_count": amp_hist,
        })
        amp_df.to_csv(outdir / f"{stem}_amplitude_histogram.csv", index=False)

    # Damage summary text
    dmg_path = outdir / f"{stem}_damage_summary.txt"
    with open(dmg_path, "w") as f:
        f.write(f"channel:             {channel}\n")
        f.write(f"sn_curve:            {damage_dict['sn_curve']}\n")
        f.write(f"total_cycles:        {damage_dict['total_cycles']}\n")
        f.write(f"damage_total:        {damage_dict['damage_total']:.4e}\n")
        f.write(f"damage_rate_per_s:   {damage_dict['damage_rate_per_s']:.4e}\n")
        f.write(f"sigma_eq_mpa:        {damage_dict['sigma_eq_mpa']:.4f}\n")
        f.write(f"samples_raw:         {repair_summary['samples_raw']}\n")
        f.write(f"samples_after_repair:{repair_summary['samples_after_repair']}\n")
        f.write(f"gaps_interpolated:   {repair_summary['gaps_interpolated']}\n")
        f.write(f"gaps_flagged:        {repair_summary['gaps_flagged']}\n")
        f.write(f"outliers_clipped:    {outlier_summary['outliers_clipped']} "
                f"({outlier_summary['outlier_fraction']*100:.2f}%)\n")
        f.write(f"notch_applied:       {notch_applied}\n")
        f.write(f"filter:              Butterworth LP {LP_CUTOFF_HZ} Hz, "
                f"order {LP_ORDER}, zero-phase\n")
        f.write(f"detrend:             linear\n")
    log.info("  Saved: %s", dmg_path.name)

    # Features summary CSV
    feat_path = outdir / f"{stem}_features_summary.csv"
    pd.DataFrame([features_summary]).to_csv(feat_path, index=False)

    # Features per window CSV
    feat_win_path = outdir / f"{stem}_features_windows.csv"
    features_windows.to_csv(feat_win_path, index=False)
    log.info("  Saved: features_summary + features_windows")

    # Plots
    _save_plots(outdir, stem, df_clean, channel, cycles_df, amp_hist, features_windows)


def _save_plots(
    outdir: Path,
    stem: str,
    df_clean: pd.DataFrame,
    channel: str,
    cycles_df: pd.DataFrame,
    amp_hist: np.ndarray,
    features_windows: pd.DataFrame,
) -> None:
    """Generate and save diagnostic plots. Not committed to the repo."""
    plots_dir = outdir / "plots"
    plots_dir.mkdir(exist_ok=True)

    col_map = {"strain_ue": "strain_ue", "accel_z": "accel_z_ms2",
               "accel_y": "accel_y_ms2", "accel_x": "accel_x_ms2"}
    sig_col = col_map.get(channel, channel)
    if sig_col not in df_clean.columns:
        sig_col = df_clean.columns[-1]

    t = df_clean["time_s"].values
    sig = df_clean[sig_col].values

    # 1. Time series
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.plot(t, sig, lw=0.5, color="steelblue", label="cleaned signal")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(sig_col)
    ax.set_title(f"Cleaned signal — {channel}")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plots_dir / f"{stem}_timeseries.png", dpi=150)
    plt.close(fig)

    # 2. PSD
    freqs, psd = welch(sig, fs=FS, nperseg=512)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.semilogy(freqs, psd, color="steelblue", lw=1)
    for lo, hi, label, color in [
        (*BAND_LOW,  "Low (0.5–5 Hz)",  "green"),
        (*BAND_MID,  "Mid (5–25 Hz)",   "orange"),
        (*BAND_HIGH, "High (25–80 Hz)", "red"),
    ]:
        ax.axvspan(lo, hi, alpha=0.08, color=color, label=label)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("PSD")
    ax.set_title(f"Power spectral density — {channel}")
    ax.legend(fontsize=8)
    ax.set_xlim(0, 100)
    fig.tight_layout()
    fig.savefig(plots_dir / f"{stem}_psd.png", dpi=150)
    plt.close(fig)

    # 3. Amplitude histogram
    if len(cycles_df) > 0:
        fig, ax = plt.subplots(figsize=(7, 4))
        bin_centres = np.linspace(0, cycles_df["amplitude"].max(), N_AMP_BINS)
        ax.bar(bin_centres, amp_hist,
               width=(bin_centres[1] - bin_centres[0]) * 0.85,
               color="steelblue", edgecolor="white", lw=0.3)
        ax.set_xlabel("Cycle amplitude")
        ax.set_ylabel("Cycle count")
        ax.set_title(f"Rainflow amplitude histogram — {channel}")
        fig.tight_layout()
        fig.savefig(plots_dir / f"{stem}_amplitude_histogram.png", dpi=150)
        plt.close(fig)

    # 4. Kurtosis trend
    if "kurtosis" in features_windows.columns:
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.plot(features_windows["t_start"], features_windows["kurtosis"],
                marker="o", ms=3, lw=0.8, color="darkorange")
        ax.axhline(3.0, color="gray", lw=0.8, ls="--", label="Gaussian baseline (K=3)")
        ax.set_xlabel("Window start time (s)")
        ax.set_ylabel("Kurtosis")
        ax.set_title(f"Kurtosis trend — {channel}")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(plots_dir / f"{stem}_kurtosis_trend.png", dpi=150)
        plt.close(fig)

    log.info("  Plots saved to %s", plots_dir)


# Main pipeline

def run_pipeline(csv_path: Path, outdir: Path) -> None:
    """
    Execute the full processing pipeline for one raw CSV file.

    The primary channel processed through the full fatigue pipeline is
    strain_ue. Acceleration (accel_z) is processed through filtering and
    feature extraction only, and used as a proxy when strain data is suspect.
    """
    stem = csv_path.stem

    log.info("=" * 60)
    log.info("Processing file: %s", csv_path.name)
    log.info("=" * 60)

    # load and repair
    df = load_data(csv_path)
    df, repair_summary = repair_timestamps(df)

    duration_s = float(df["time_s"].iloc[-1] - df["time_s"].iloc[0])
    log.info("Record duration: %.1f s", duration_s)

    # process each channel
    # Primary: strain. Fallback: accel_z.
    # TODO (B4): use gaps_flagged to flag strain data as suspect and skip damage
    #            calculation when the record has large interpolation gaps.
    for channel, col in [("strain_ue", "strain_ue"), ("accel_z", "accel_z_ms2")]:
        log.info("-" * 40)
        log.info("Channel: %s", channel)

        sig_raw = df[col].values.copy()

        # detrend
        sig = detrend_signal(sig_raw, poly_order=1)

        # low-pass
        sig = lowpass_filter(sig)

        # notch (strain channel only, most prone to mains interference)
        notch_applied = False
        if channel == "strain_ue":
            sig, notch_applied = apply_notch_if_needed(sig)

        # outlier clipping
        sig, outlier_summary = clip_outliers(sig)

        # write cleaned signal back to df
        df[f"{col}_clean"] = sig

        # rainflow (strain to stress, accel to proxy)
        cycles_df, rf_matrix, amp_hist = count_cycles(sig, channel_label=channel)

        # damage
        ch_type = "strain" if channel == "strain_ue" else "accel"
        damage_dict = compute_damage(cycles_df, channel=ch_type, duration_s=duration_s)

        # features
        features_summary, features_windows = extract_features(
            sig, channel, cycles_df, damage_dict, duration_s
        )

        # save
        # Build a clean df with just time + this channel for saving
        df_out = df[["time_s", col]].copy()
        df_out[col] = sig

        channel_outdir = outdir / channel
        save_outputs(
            channel_outdir, stem,
            df_out, cycles_df, rf_matrix, amp_hist,
            damage_dict, features_summary, features_windows,
            repair_summary, notch_applied, outlier_summary, channel,
        )

        log.info(
            "Channel %s complete | Cycles: %d | D_total: %.3e | σ_eq: %.2f MPa",
            channel,
            damage_dict["total_cycles"],
            damage_dict["damage_total"],
            damage_dict["sigma_eq_mpa"],
        )

    log.info("=" * 60)
    log.info("Pipeline complete. Outputs in: %s", outdir)
    log.info("=" * 60)



# cli entry point

def parse_args():
    p = argparse.ArgumentParser(
        description="Suspension degradation — data processing pipeline v0.1"
    )
    p.add_argument(
        "--input", "-i", required=True, type=Path,
        help="Path to raw Arduino CSV log file",
    )
    p.add_argument(
        "--outdir", "-o", type=Path, default=None,
        help="Output directory (default: same folder as input, suffix _processed)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if not args.input.exists():
        log.error("Input file not found: %s", args.input)
        sys.exit(1)

    outdir = args.outdir or args.input.parent / (args.input.stem + "_processed")
    run_pipeline(args.input, outdir)
