# Calibration Notes

## Status

**Accelerometer calibration: complete (factory).**
The MPU-6050 ships with factory-calibrated sensitivity. No field calibration is required beyond selecting the correct full-scale range (±16g) and verifying the correct conversion factor in `process_pipeline.py`.

**Strain gauge calibration: incomplete.**
The strain scale factor (`STRAIN_SCALE`) in `process_pipeline.py` is currently a placeholder. Physical calibration has not been performed. All strain amplitudes, stress amplitudes, and Miner's rule damage numbers derived from the strain channel carry an unknown systematic error until this is resolved.

---

## Accelerometer — conversion factor

The MPU-6050 raw output is a 16-bit signed integer representing acceleration in ADC counts. The conversion to physical units is:

```
a [m/s²] = counts × (full_scale_g / 32768) × 9.81
```

For the configured ±16g full-scale range:

```
a [m/s²] = counts × (16 / 32768) × 9.81
         = counts × 0.004788 m/s²/count
```

This value is implemented as `ACCEL_SCALE` in `process_pipeline.py`. It assumes the factory sensitivity is accurate, which is typically within ±1% for the MPU-6050. No field calibration has been performed.

**Cross-axis sensitivity:** The MPU-6050 has a cross-axis sensitivity of approximately ±2%, meaning a pure 1g vertical input produces a small non-zero reading on the x and y axes. This is not corrected in the pipeline — for the intended purpose (characterising vertical loading) the error is negligible.

---

## Strain gauge — current placeholder values

| Constant | Current value | Status |
|---|---|---|
| `STRAIN_SCALE` | 0.5 με/count | **PLACEHOLDER — not calibrated** |
| `STRAIN_ZERO_OFFSET` | 0 | **PLACEHOLDER — not set** |

`STRAIN_SCALE` was estimated as follows: with the INA125 configured at a nominal gain G, and a strain gauge with gauge factor GF ≈ 2.0, the output voltage per microstrain is:

```
V_out per με = V_excitation × GF × 10⁻⁶ × G / 2
```

With V_excitation ≈ 5 V, GF = 2.0, and a gain chosen to map the expected ±500 με range to approximately ±2.5 V (half the ADC range), the approximate scale factor works out to roughly 0.5 με/count. The actual gain resistor value must be measured after assembly.

---

## Planned strain calibration procedure

Two methods are practical without a laboratory load frame.

### Method 1 — Shunt calibration (preferred)

Shunt calibration simulates a known strain by placing a precision resistor in parallel with one arm of the Wheatstone bridge, creating a known imbalance.

**Procedure:**
1. With the gauge installed on the strut and the INA125 powered, record the ADC output with no load applied (static vehicle weight on the strut). This is the zero reference.
2. Connect a precision shunt resistor (R_shunt, value chosen so that the simulated strain is approximately 200–300 με) in parallel with one arm of the bridge.
3. Record the ADC output with the shunt connected.
4. The simulated strain is:

```
ε_simulated [με] = −(R_gauge / (R_shunt + R_gauge)) × 10⁶ / GF
```

For R_gauge = 120 Ω and GF = 2.0, a shunt of R_shunt = 60,000 Ω gives:

```
ε_simulated = −(120 / 60120) × 10⁶ / 2.0 ≈ −998 με
```

5. Calculate `STRAIN_SCALE`:

```
STRAIN_SCALE [με/count] = ε_simulated / (ADC_shunted − ADC_zero)
```

**Advantages:** Does not require physical loading of the vehicle. Can be done at the bench before installation. Verifies the complete signal chain including the amplifier gain and ADC.

**Disadvantage:** Only verifies the sensitivity at one point. Linearity is assumed across the range.

### Method 2 — Dead weight loading

If the strut can be removed and clamped in a vice, a known load can be applied with calibrated weights and the ADC response recorded.

**Procedure:**
1. Clamp the strut vertically in a vice at the knuckle end.
2. Apply a known force (e.g. 50 N, 100 N, 200 N) axially via a weight hung from the upper mount or a load spreader.
3. Record ADC count at each load level.
4. Calculate the stress at the gauge from the applied axial force and the tube cross-section area, then convert to strain via E = 210 GPa.
5. Fit a linear relationship between ADC count and calculated strain.

**Disadvantage:** The strut must be removed from the vehicle. The calculated strain assumes a known force application point and a simple stress state (pure axial), which may not perfectly represent the combined loading in-situ.

---

## Zero offset procedure

`STRAIN_ZERO_OFFSET` should be set to the mean ADC count measured over a 30-second static period with the vehicle stationary on level ground, engine off, driver in the seat (to represent the in-service static tare state). This value is then subtracted from all subsequent readings to give the dynamic variation about the static mean.

If the zero offset is not set and left at 0, all strain readings are relative to the ADC mid-scale reference of the INA125, which includes the static load of the vehicle weight. Rainflow cycle amplitudes are not affected by a constant offset but the absolute mean stress values are wrong.

---

## When to update calibration constants

- After any remounting of the strain gauge (if the gauge is removed or the adhesive bond breaks)
- After any change to the INA125 gain resistor
- If the static zero reading drifts by more than ±10 counts between sessions (indicates thermal drift or partial debonding)

Updated values are set directly in the constants section of `process_pipeline.py` and committed with a note on the calibration date and method.
