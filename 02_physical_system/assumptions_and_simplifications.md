# Assumptions and Simplifications

Every significant assumption made across the physical, measurement, and modelling domains is listed here. Each entry states the assumption, its justification, and the consequence of violating it.

---

## Physical and material assumptions

**A1 — Linear elastic material behaviour**

The strut operates in the linear elastic regime throughout. Plastic deformation is not modelled. This is reasonable for normal driving loads on a correctly designed OEM component. A single severe pothole impact could locally yield the tube wall, after which the residual stress state changes and the elastic assumption no longer holds for subsequent cycles.

**A2 — Uniaxial stress at the strain gauge location**

The strain gauge measures strain in one direction only. The actual stress state at the spring seat region is biaxial — axial compression combined with a bending moment from spring eccentricity and lateral loads. Treating the single-axis gauge reading as the full stress amplitude underestimates damage unless the gauge axis is aligned with the dominant principal stress direction. The gauge orientation is documented in `03_instrumentation/sensor_placement.md`.

**A3 — Homogeneous isotropic steel throughout**

The damper tube is treated as uniform low-carbon steel (E = 210 GPa) everywhere. Weld zones and the heat-affected zone (HAZ) around the spring seat have a different grain structure and altered local mechanical properties. The FEM material model (see `06_fem_model/material_model.md`) uses bulk steel properties throughout and does not model the HAZ.

**A4 — Quasi-static loading**

FEM load cases apply each representative amplitude as a static force. The actual loading is dynamic — damper forces, inertial effects, and resonant amplification all contribute to the stress state. For load frequencies well below the first structural natural frequency of the strut, the quasi-static approximation is adequate. At and near wheel hop frequency (10–15 Hz), dynamic amplification is not captured and FEM stresses will be underestimated.

**A5 — Tyre treated as a vertical force input**

The tyre, wheel, and hub are not modelled. The strut input is a vertical force applied at the knuckle. Tyre lateral compliance, fore-aft compliance, and tyre damping are all ignored. This is standard for quasi-static strut analysis but removes the high-rate cushioning effect of the tyre during sharp impacts.

---

## Instrumentation and measurement assumptions

**A6 — Uniform sampling at 200 Hz**

The Arduino is programmed to sample at 200 Hz. Inter-sample intervals vary in practice due to I2C latency and loop execution time. The `repair_timestamps` function in `process_pipeline.py` reconstructs a uniform time axis from the median measured rate. This is valid when timing jitter is small (< 5% of the nominal interval). Samples genuinely missing due to SD write latency cannot be reconstructed and are flagged as gaps by `validate_raw.py`.

**A7 — MPU-6050 at ±16g full scale**

The ±16g range was selected to prevent saturation during sharp impacts. The trade-off is a noise floor of approximately ±20–30 mg (≈ ±0.2–0.3 m/s²). Low-amplitude vibrations below this level are not reliably measured and do not appear in the rainflow count.

**A8 — Approximate strain gauge calibration**

`STRAIN_SCALE = 0.5 με/count` is a placeholder derived from an estimated amplifier gain and a nominal gauge factor of 2.0. It has not been verified by physical calibration. Until calibration is completed (see `03_instrumentation/calibration_notes.md`), all derived quantities — stress amplitude, Miner's rule damage — carry an unknown systematic error. Results should be treated as order-of-magnitude estimates.

**A9 — Zero strain reference at startup**

`STRAIN_ZERO_OFFSET = 0` means the ADC reading at the start of each session is taken as the zero-load reference. The vehicle's static weight is already on the gauge at startup, so the measured signal represents dynamic variation around the static load, not the absolute strain from an unloaded state. Rainflow counting captures the variable-amplitude component correctly. The mean stress in each cycle is relative to the loaded reference, not absolute — the FEM comparison of mean stress is therefore not meaningful.

**A10 — Vertical load dominant**

Primary loading is assumed vertical (z-axis acceleration, axial strut load). Lateral forces from cornering and longitudinal forces from braking are not separately characterised. For straight-line driving on smooth roads this is acceptable. Combined loading events (braking over a bump, cornering on rough surfaces) produce a multiaxial stress state that a single vertical accelerometer and uniaxial strain gauge cannot fully capture.

---

## Modelling assumptions

**A11 — BS 7608 Class B S-N curve**

The actual material S-N curve for the Space Star strut is not available. BS 7608 Class B (plain material, m = 3.0, C = 1.013×10¹²) is used as a structural steel proxy. The real curve may be more or less conservative depending on tube grade and surface finish. Absolute fatigue life numbers derived from this curve should not be relied upon; relative comparisons between sessions are more meaningful.

**A12 — Linear damage accumulation (Miner's rule)**

Miner's rule ignores load sequence effects. High-amplitude cycles early in a loading history consume more life per cycle than the same amplitude cycles applied after extensive low-amplitude cycling (sequence effect). Since the order of road events on a real drive is effectively random, Miner's rule is the standard approximation and is accepted here with this known limitation.

**A13 — Fixed boundary at the knuckle**

The FEM fixes all six degrees of freedom at the strut-to-knuckle connection. The real joint has finite compliance through the wheel bearing and lower control arm bushes. A fully rigid boundary modestly overestimates bending stress at the strut base relative to a compliant boundary.

---

## Summary

| ID | Assumption | Consequence if violated |
|---|---|---|
| A1 | Linear elastic | Residual stress after overload not captured |
| A2 | Uniaxial stress | Damage underestimated if gauge misaligned with principal stress |
| A3 | Homogeneous steel | HAZ fatigue strength overestimated at spring seat weld |
| A4 | Quasi-static loads | Dynamic amplification near resonance not captured; FEM stresses underestimated |
| A5 | Vertical force input | High-rate tyre cushioning and lateral coupling ignored |
| A6 | Uniform 200 Hz | Cycle amplitudes wrong if large gaps are silently interpolated |
| A7 | ±16g full scale | Low-amplitude vibration below noise floor not counted |
| A8 | Approximate calibration | Absolute stress values carry unknown systematic error |
| A9 | Static tare at startup | Mean stress per cycle relative to loaded state, not absolute |
| A10 | Vertical load dominant | Combined loading events underestimated |
| A11 | BS 7608 Class B | Absolute fatigue life estimates unreliable |
| A12 | Miner's rule | Sequence effects ignored |
| A13 | Fixed knuckle boundary | Bending stress at strut base slightly overestimated |
