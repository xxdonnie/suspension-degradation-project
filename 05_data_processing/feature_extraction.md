# Feature Extraction

## Overview

After filtering and rainflow cycle counting, two sets of features are computed from each cleaned signal:

1. **Time- and frequency-domain features** — computed over sliding windows of the cleaned signal
2. **Rainflow-derived structural features** — computed from the cycle count and Miner's rule damage output

These features are the primary quantitative output of the processing pipeline. They serve as the inputs to the FEM comparison in `07_comparison/` and as the basis for any degradation trend analysis across multiple drive sessions.

Feature extraction is implemented in `scripts/process_pipeline.py` (function `extract_features`).

---

## Windowing parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Window length | 10 s (2000 samples at 200 Hz) | Long enough to capture several suspension cycles; short enough to track non-stationarity |
| Overlap | 50% (5 s step) | Standard for spectral estimation; reduces variance of windowed estimates |
| nperseg (Welch) | 512 samples | Frequency resolution of ≈ 0.39 Hz; adequate to resolve structural resonances above 1 Hz |
| noverlap (Welch) | 256 samples | 50% overlap within each Welch segment |

---

## Time-domain features (per window, averaged across all windows)

| Feature column | Description | Units |
|----------------|-------------|-------|
| `rms_mean` | Mean RMS amplitude across windows | signal units |
| `rms_std` | Standard deviation of RMS across windows | signal units |
| `peak_mean` | Mean peak (max absolute value) per window | signal units |
| `crest_factor_mean` | Mean crest factor (peak / RMS) — high values indicate impulsive loading | dimensionless |
| `kurtosis_mean` | Mean kurtosis across windows (Fisher=False, so Gaussian baseline = 3.0) | dimensionless |
| `kurtosis_std` | Standard deviation of kurtosis — elevated σ indicates intermittent impact events | dimensionless |
| `zcr_mean` | Mean zero-crossing rate (crossings per second) — proxy for dominant frequency | Hz |

**Interpretation notes:**
- Kurtosis > 3 indicates non-Gaussian (impulsive) loading, which is not well-captured by linear spectral methods and is associated with higher-than-predicted fatigue damage.
- Rising `rms_mean` or `crest_factor_mean` across repeated drive sessions on the same route indicates increasing loading severity (e.g. strut degradation changing system response).

---

## Frequency-domain features (per window, averaged across all windows)

| Feature column | Description | Units |
|----------------|-------------|-------|
| `psd_peak_freq_mean` | Mean frequency of the PSD peak (0.5–80 Hz) | Hz |
| `band_power_low` | Mean PSD power in the low band (0.5–5 Hz) — body motion, ride | (signal units)²/Hz |
| `band_power_mid` | Mean PSD power in the mid band (5–25 Hz) — wheel hop, structural resonance | (signal units)²/Hz |
| `band_power_high` | Mean PSD power in the high band (25–80 Hz) — road texture, brake judder | (signal units)²/Hz |
| `spectral_centroid` | Frequency-weighted mean of the PSD — shifts toward high frequencies with surface roughness | Hz |
| `total_power_mean` | Total integrated PSD power (0.5–80 Hz) | (signal units)²/Hz |

**Band definitions:**

| Band | Range | Primary content |
|------|-------|-----------------|
| Low | 0.5–5 Hz | Body bounce (1–2 Hz), pitch, roll |
| Mid | 5–25 Hz | Wheel hop (10–15 Hz), strut structural modes |
| High | 25–80 Hz | Road texture transmission, high-freq vibration |

---

## Rainflow-derived structural features (whole record)

These are computed from the full-record rainflow output and Miner's rule damage estimate, not from the windowed analysis.

| Feature column | Description | Units |
|----------------|-------------|-------|
| `sigma_eq_mpa` | Miner-weighted equivalent stress amplitude — single stress value that produces the same damage as the full cycle distribution | MPa |
| `damage_rate_per_s` | Miner's damage per second of driving — normalised for record duration to allow comparison across drive sessions of different lengths | D/s |
| `cycle_rate_per_s` | Total rainflow cycles per second | cycles/s |
| `large_cycle_fraction` | Fraction of cycles with amplitude > 50% of the maximum observed amplitude — indicates prevalence of high-severity events | dimensionless |

**Interpretation notes:**
- `sigma_eq_mpa` is only physically meaningful for the strain channel. For the acceleration channel it is a proxy in arbitrary units and must not be interpreted as a stress.
- `damage_rate_per_s` allows fair comparison between a 3-minute urban run and a 10-minute motorway run. Multiply by total mission duration to estimate cumulative damage.
- `large_cycle_fraction` > 0.05 (more than 5% of cycles at high amplitude) suggests the fatigue damage budget is dominated by rare large events rather than the bulk of small cycles — a condition where Miner's rule scatter is highest.

---

## Output files

| File | Content |
|------|---------|
| `{stem}_features_summary.csv` | One row per processed file; all features listed above plus `channel`, `duration_s`, `n_windows` |
| `{stem}_features_windows.csv` | One row per window; time-domain and frequency-domain features for each 10 s window (not aggregated) |

The per-window file is useful for identifying non-stationary sections of a drive record (e.g. a cobblestone segment vs. smooth road) and for visualising how kurtosis, RMS, and band power evolve over the route.

---

## Known limitations

- All features are computed on the low-pass filtered signal (80 Hz cutoff). Features above 80 Hz are not available.
- Windowed features are averaged across all windows. If the drive route contains qualitatively different surface types, the average will mask segment-level differences. Consider processing each segment independently.
- `sigma_eq_mpa` assumes uniaxial stress from a single strain gauge. Multiaxial stress states (bending + axial) are not captured and will cause under-estimation of the equivalent stress.
- The spectral centroid and band power ratios change with both road surface and vehicle speed. Speed should be recorded alongside the signal data to correctly normalise frequency-domain features.
