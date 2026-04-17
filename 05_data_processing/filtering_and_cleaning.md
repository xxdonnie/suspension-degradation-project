# Filtering and Cleaning

## Overview

Raw signals from the Arduino DAQ contain several artefacts that must be removed before fatigue analysis:

- **DC offset and slow drift** — thermal effects in the INA125 amplifier and MPU-6050 bias shift the baseline over time
- **High-frequency noise above the structural bandwidth** — sensor self-noise and ADC quantisation above 80 Hz carry no structural information and inflate cycle counts
- **Mains interference at 50 Hz** — the INA125 amplifier circuit may couple to the vehicle's 12 V electrical system via ground loops
- **Impulsive spikes** — single-sample outliers from ADC glitches or connector vibration

All filtering is implemented in `scripts/process_pipeline.py`. The filter order follows the sequence in `run_pipeline`: detrend → low-pass → notch (conditional) → outlier clipping. The high-pass filter is available as a utility function but is **not** applied in the main pipeline (see [High-pass filter](#high-pass-filter) below).

---

## 1. Detrending

**Function:** `detrend_signal(sig, poly_order=1)`

**Purpose:** Remove DC offset and slow drift before filtering. A linear detrend (default, `poly_order=1`) fits and subtracts a straight line from the signal. A polynomial detrend (`poly_order ≥ 2`) is available for long records where thermal drift is non-linear.

**When to use polynomial order:** Records longer than approximately 5 minutes, or any record where the baseline visibly curves over time.

**Implementation note:** For `poly_order=1`, `scipy.signal.detrend(type='linear')` is used directly (efficient, no manual fitting). For higher orders, `np.polyfit` / `np.polyval` are used.

---

## 2. Low-pass filter

**Function:** `lowpass_filter(sig, cutoff=80.0)`

**Parameters:**
- Cutoff: 80 Hz
- Filter type: Butterworth, 4th order
- Phase: zero-phase (bidirectional, `sosfiltfilt`)

**Purpose:** Remove high-frequency noise above the structural bandwidth of the strut. The MacPherson strut's structural resonances are expected below 50 Hz; the cutoff is set to 80 Hz to retain all structural content while attenuating ADC self-noise.

**Why zero-phase?** `sosfiltfilt` applies the filter twice (forward and backward), producing zero phase distortion. This is essential for rainflow counting: any phase shift would misplace the load reversal points and bias the cycle amplitude distribution. Causal filters (`sosfilt`) must not be used upstream of rainflow counting.

**Why SOS form?** Second-order sections (`output='sos'`) are numerically more stable than transfer-function form (`ba`) for higher-order filters, particularly for low cutoffs relative to the sampling rate.

---

## 3. High-pass filter (utility only)

**Function:** `highpass_filter(sig, cutoff=0.5)`

**Parameters:**
- Cutoff: 0.5 Hz
- Filter type: Butterworth, 2nd order
- Phase: zero-phase

**Purpose:** Remove very-low-frequency content for PSD and modal analysis. **Not applied in the main pipeline** — the high-pass filter removes mean load information that Miner's rule damage accumulation depends on. It is available for ad-hoc spectral analysis (e.g. isolating resonance peaks) but must never be applied before rainflow counting.

---

## 4. 50 Hz notch filter (conditional)

**Function:** `apply_notch_if_needed(sig)`

**Parameters:**
- Notch frequency: 50 Hz
- Q factor: 30 (narrow, ±0.83 Hz at –3 dB)
- Trigger threshold: PSD at 50 Hz > 3× mean PSD of the 45–55 Hz band

**Purpose:** Suppress mains interference from the vehicle electrical system. The filter is only applied if the PSD check detects a significant 50 Hz peak, avoiding unnecessary spectral distortion in clean records.

**Trigger logic:** A Welch PSD is computed on the signal. If the maximum PSD within 49.5–50.5 Hz exceeds 3× the mean PSD of the surrounding 45–55 Hz band (excluding the notch region), the IIR notch filter is applied via `scipy.signal.filtfilt`. The result and a boolean flag (`notch_applied`) are returned and recorded in the damage summary.

**Applied to:** Strain channel only (most susceptible to mains coupling through the INA125 amplifier). Acceleration channels are not notch-filtered.

---

## 5. Outlier clipping

**Function:** `clip_outliers(sig)`

**Parameters:**
- Threshold: 5σ from local rolling mean
- Rolling window: 0.5 s (100 samples at 200 Hz)
- Max acceptable outlier fraction: 0.5%

**Purpose:** Replace single-sample ADC spikes with linear interpolation. Spikes produce extremely high-amplitude phantom cycles in the rainflow count, inflating the damage estimate by orders of magnitude.

**Method:** A centred rolling mean and standard deviation are computed. Samples more than `OUTLIER_SIGMA = 5` standard deviations from the local mean are replaced by the average of their two nearest neighbours. Using a local (rolling) reference rather than a global one prevents over-clipping in records with genuine amplitude variation.

**Suspect flag:** If more than 0.5% of samples are flagged as outliers, the window is flagged as suspect in the output summary. Records exceeding this threshold should be inspected manually before use in the fatigue analysis.

---

## Filter sequence summary

```
raw ADC counts
    │
    ▼ load_data()          unit conversion (counts → m/s², με)
    │
    ▼ detrend_signal()     remove DC offset and drift
    │
    ▼ lowpass_filter()     Butterworth LP 80 Hz, 4th order, zero-phase
    │
    ▼ apply_notch_if_needed()   50 Hz IIR notch (strain channel, conditional)
    │
    ▼ clip_outliers()      5σ rolling spike removal
    │
    └── cleaned signal → rainflow counting, feature extraction
```

---

## Output

The cleaned signal is written to `{stem}_clean.csv` in the channel output directory. The damage summary text file records which filters were applied (`notch_applied`, `filter` field) and the outlier count.

---

## Known limitations

- Detrending assumes drift is slow relative to the structural signal. If road segments produce genuine step changes in mean load (e.g. speed bump followed by smooth road), linear detrending will introduce an artificial slope. Segment the record at major load transitions before processing.
- The 50 Hz notch check is based on a single Welch estimate over the whole record. Intermittent interference that comes and goes will not be detected reliably. Consider time-frequency analysis (short-time Fourier transform) if intermittent interference is suspected.
- Outlier clipping only corrects single isolated samples. Multi-sample transients (e.g. 3–5 consecutive corrupted readings) pass through undetected. These should be caught by the timestamp gap check in `repair_timestamps`.
