# Failure Modes

## Overview

MacPherson strut degradation occurs through several parallel mechanisms, each at a different timescale. This document describes the failure modes relevant to this project, and honestly assesses which ones this instrumentation setup can and cannot detect.

---

## 1. Damper seal leakage and loss of hydraulic damping

**Mechanism:** The piston rod seal retains hydraulic oil inside the damper. Road vibration, thermal cycling, and lateral side loads cause progressive seal lip wear. Once oil escapes, damping force drops — often by 20–40% before external symptoms (oil streak on the tube) become visible.

**Typical onset:** 60,000–120,000 km under normal use. Significantly accelerated by repeated severe impacts, unpaved roads, and salt exposure degrading the seal material.

**Observable signal effects:**
- Increased acceleration amplitude in the wheel hop frequency range (10–15 Hz) as the under-damped resonance is no longer suppressed
- Higher rainflow cycle counts — residual oscillations after each impact add many small-amplitude cycles
- Rising `band_power_mid` in the frequency features

**Detectability with this setup:** Moderate. The z-axis accelerometer is well positioned to observe changes in wheel hop amplitude. The strain gauge alone is less sensitive to this mode because the small residual oscillations produce small strains.

---

## 2. Spring seat fatigue cracking

**Mechanism:** The spring seat weld toe acts as a stress concentrator under cyclic bending from the eccentrically loaded spring and bump forces. A fatigue crack initiates at the weld toe and can propagate into the tube wall. Full circumferential propagation causes rapid structural failure.

**Typical onset:** Rare in passenger vehicles within 150,000 km under normal use. Corrosion at the weld toe (particularly in salted road environments) dramatically reduces the number of cycles to initiation by creating pits that act as pre-existing stress raisers.

**Observable signal effects:**
- A propagating crack that significantly reduces local stiffness could shift the strut's natural frequencies
- A large crack might produce a visible step change in mean strain as the load path geometry alters
- Small cracks (< 5 mm) are essentially invisible at this sensor placement and resolution

**Detectability with this setup:** Low. This setup cannot detect incipient fatigue cracking. Its value for this failure mode is in building a reference load history (the input to a fracture mechanics crack growth calculation), not in direct crack detection.

---

## 3. Upper mount rubber degradation

**Mechanism:** The rubber element in the upper mount hardens and loses compliance with age and thermal cycling, independently of driving load severity. A hardened mount transmits more high-frequency vibration into the body. In advanced cases, the rubber delaminates from the metal inserts, producing knocking or clunking at low speeds.

**Typical onset:** 5–10 years or 80,000–120,000 km, depending strongly on climate. UV and ozone exposure accelerate degradation.

**Observable signal effects:**
- Increased power in the high-frequency band (25–80 Hz) in the body acceleration, as the mount no longer attenuates high-frequency transmission
- Slight upward shift in the body's apparent natural frequency as the compliant mount stiffens
- Intermittent high-kurtosis transients if the mount produces impact events (knocking)

**Detectability with this setup:** Moderate for stiffness change via frequency content; low for the gradual rubber hardening process before it produces audible symptoms.

---

## 4. Coil spring fracture

**Mechanism:** Corrosion pitting on the spring wire surface (most severe at the lower coil, which collects road spray) creates stress raisers that reduce fatigue life from millions of cycles to tens of thousands. Spring fracture is sudden and safety-critical — wheel alignment and ride height change immediately when a coil breaks.

**Typical onset:** 8–15 years with salt road exposure. Unlikely within the project timeframe with new components on a vehicle primarily driven in urban conditions.

**Observable signal effects:**
- Sudden permanent drop in ride height → change in mean strain level at the gauge
- If only one coil breaks, the active spring length decreases and the effective rate increases slightly
- The dynamic frequency response is essentially unchanged until near-complete fracture

**Detectability with this setup:** Low for gradual corrosion fatigue progression. A full fracture would cause a detectable step change in mean strain that persists across all subsequent sessions.

---

## 5. Lower control arm bush wear

**Mechanism:** The rubber bushes connecting the lower control arm to the subframe degrade over time, introducing compliance in the fore-aft and lateral directions. This is not a strut failure mode, but it changes the effective suspension geometry and can modify the strut's load path.

**Typical onset:** Variable; 60,000–150,000 km depending on driving style.

**Observable signal effects:**
- Primarily affects low-frequency lateral and longitudinal dynamics
- Difficult to separate from road surface variation using a single vertical accelerometer

**Detectability with this setup:** Not detectable.

---

## Summary table

| Failure mode | Typical onset | Primary signal change | Detectability |
|---|---|---|---|
| Damper seal leakage | 60–120 kkm | ↑ wheel hop amplitude (10–15 Hz) | Moderate |
| Spring seat fatigue crack | Rare; corrosion-dependent | Stiffness shift, mean strain step | Low |
| Upper mount degradation | 5–10 yr / 80–120 kkm | ↑ high-freq power, kurtosis spikes | Moderate |
| Coil spring fracture | 8–15 yr (salt roads) | Permanent ride height / mean strain drop | Low (late stage) |
| Control arm bush wear | 60–150 kkm | Lateral/longitudinal handling change | Not detectable |

---

## What this setup can realistically do

The primary value of this dataset is establishing a reference load history at the known new-strut condition. If measurements are repeated after significant additional mileage, changes in `band_power_mid`, `damage_rate_per_s`, and the wheel hop frequency content are the most likely indicators of damper degradation. Spring seat cracking and bush wear are effectively invisible to this sensor configuration.
