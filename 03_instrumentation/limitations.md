# Instrumentation Limitations

This document lists the specific technical limitations of the measurement setup and their practical consequences for the fatigue analysis. Each limitation is cross-referenced to where it is handled (or noted as unhandled) in the processing pipeline.

---

## L1 — 10-bit ADC resolution on strain channel

**Limitation:** The Arduino's ADC has 10-bit resolution: 1024 discrete levels over a 0–5 V input range. At 5 V full scale, one count corresponds to approximately 4.9 mV.

**Consequence:** With the nominal calibration of 0.5 με/count, the minimum detectable strain change is ~0.5 με. This is adequate for measuring amplitudes above ~10 με but means that very small vibrations (e.g. fine road texture, engine vibration below 10 με amplitude) are not resolved.

In the rainflow count, this quantisation floor means that many real small cycles may be mapped to 0 amplitude and not counted, slightly underestimating the total cycle count and the associated low-amplitude damage. Since damage scales with σ³ under BS 7608, small-amplitude cycles contribute negligibly to Miner's rule D anyway — the quantisation error is not significant for the damage estimate.

**Where handled:** The 10-bit limit is declared as `STRAIN_ADC_MAX = 1023` in `validate_raw.py`. Saturation checks flag counts within 8 of either rail.

---

## L2 — Approximate strain calibration

**Limitation:** `STRAIN_SCALE = 0.5 με/count` is a placeholder. The actual scale factor depends on the exact INA125 gain resistor value, the gauge resistance, and the excitation voltage — none of which have been measured under calibrated conditions.

**Consequence:** All derived quantities (stress amplitude in MPa, Miner's rule damage D, equivalent stress σ_eq) carry an unknown systematic proportional error. If the true scale factor is 0.4 vagy 0.6 instead of 0.5, all stress amplitudes are in error by 20%. Because Miner's rule damage scales with σ³, a 20% error in stress amplitude produces a 73% error in the damage estimate ((1.2³ = 1.73).

**Where handled:** Warned in the constants block of `process_pipeline.py`. Documented in `03_instrumentation/calibration_notes.md`. No software correction is applied until physical calibration is performed.

---

## L3 — Single-axis strain gauge (uniaxial measurement only)

**Limitation:** One gauge in one orientation measures strain in one direction. The actual stress state at the spring seat is biaxial.

**Consequence:** If the principal stress direction does not align with the gauge axis, the gauge output is a projection of the actual principal strain onto the gauge direction. The maximum error occurs when the principal stress is at 45° to the gauge, in which case the measured strain underestimates the maximum principal strain by approximately 30%.

**Where handled:** Noted as assumption A2 in `02_physical_system/assumptions_and_simplifications.md`. The gauge axis orientation is documented in `03_instrumentation/sensor_placement.md`. No correction is applied in software.

---

## L4 — Accelerometer noise floor at ±16g range

**Limitation:** At the ±16g full-scale range, the MPU-6050 noise density is approximately 400 μg/√Hz. At 200 Hz bandwidth, the RMS noise is approximately 400 × √100 ≈ 4,000 μg = 4 mg, or about 0.04 m/s².

**Consequence:** Structural vibrations with amplitudes below ~0.05 m/s² are not reliably resolved. This affects the low-amplitude end of the acceleration rainflow distribution. The wheel hop resonance at 10–15 Hz and body bounce at 1–2 Hz are well above this floor under all normal driving conditions.

**Where handled:** Declared as `ACCEL_FULL_SCALE_G = 16` in `process_pipeline.py`. The saturation limit (32767 counts) is checked in `validate_raw.py` with a margin of 16 counts.

---

## L5 — Arduino timing jitter

**Limitation:** The Arduino `millis()` timer has 1 ms resolution. Loop execution time varies by ±0.5–1 ms due to I2C bus wait times and SD card write latency. The nominal 200 Hz (5 ms interval) can drift up to ±20% on individual samples.

**Consequence:** The uniform time axis assumed by the Butterworth filter and Welch PSD estimator is not strictly correct. The `repair_timestamps` function in `process_pipeline.py` corrects this by reconstructing a uniform time axis from the median measured rate. Residual jitter after this correction is small and does not materially affect the filter response or frequency estimates.

An SD card write that takes longer than 5 ms (common for cards with slow erase blocks) drops one or more samples entirely. These true gaps are flagged by `validate_raw.py`.

**Where handled:** `repair_timestamps` in `process_pipeline.py`. Gap detection in `validate_raw.py`.

---

## L6 — Single measurement point on one strut

**Limitation:** One strain gauge and one accelerometer on one strut provide a single spatial measurement point on one side of the vehicle.

**Consequence:** Any asymmetry in the loading (e.g. the right strut consistently sees higher loads due to road camber, or the left strut is more loaded in right-hand corners) is not captured. The measured data is representative only of the instrumented strut and cannot be generalised to the other side without additional measurements.

**Where handled:** Not corrected — this is an inherent limitation of the budget and the non-invasive mounting constraint. Noted here and in `01_problem_definition/scope_and_objectives.md`.

---

## L7 — No temperature compensation

**Limitation:** Bonded foil strain gauges exhibit apparent strain due to thermal expansion mismatch between the gauge alloy and the substrate. For a steel substrate and constantan gauge, the thermal sensitivity is approximately 10–15 με per 10°C temperature change without a dummy gauge or temperature compensation network.

**Consequence:** A temperature change of 20°C between the start and end of a drive session would appear as a ~20–30 με drift in the baseline. The detrending step (`detrend_signal`, linear detrend) removes slow drift, including thermal drift, but only if the temperature change is approximately linear over the record. Rapid temperature changes at the start of a cold weather session (gauge warms up faster than the strut tube) can produce a non-linear drift that detrending does not fully remove.

**Where handled:** The detrending step removes linear drift. Non-linear thermal drift is not corrected. Sessions started in extreme cold or with rapid ambient temperature changes should be flagged.

---

## Summary table

| ID | Limitation | Affected outputs | Severity |
|---|---|---|---|
| L1 | 10-bit ADC on strain | Small-amplitude cycles missed | Low (small cycles negligible in damage) |
| L2 | Uncalibrated strain scale | All stress/damage values | High — systematic error of unknown magnitude |
| L3 | Uniaxial gauge | Stress amplitude may be underestimated | Medium — depends on gauge alignment |
| L4 | Accel noise floor at ±16g | Low-amplitude accel cycles | Low |
| L5 | Arduino timing jitter | Spectral estimates, filter response | Low (after timestamp repair) |
| L6 | Single measurement point | Spatial representativeness | Medium — other strut not characterised |
| L7 | No temperature compensation | Baseline drift in strain | Medium for cold/hot sessions |
