# Driving Conditions

## Overview

All data collection was conducted on public roads in Germany. The target was a repeatable route that could be driven in approximately 15–20 minutes and contains a representative mix of urban surface types. The same route is used for all sessions to allow direct comparison across different vehicle conditions or time periods.

---

## Reference route

The reference route was selected to provide:

- At least one segment of smooth asphalt (motorway or bypass road) for a baseline low-severity loading condition
- At least one segment of worn or rough urban asphalt representing typical daily driving
- A controlled-speed cobblestone or severely paved section for high-amplitude cycle generation
- A small number of discrete obstacles (speed bumps, railway crossings) at known locations that produce identifiable high-amplitude events in the signal

The route is driven at a consistent speed profile. Speed bumps are driven at approximately 15–20 km/h. Urban segments are driven at 30–50 km/h as traffic allows. Any session where traffic forced a significant deviation from the speed profile is noted in the session log.

**Route length:** approximately 8–12 km  
**Session duration:** 15–25 minutes depending on traffic  
**Surface types included:** smooth asphalt, worn urban asphalt, cobblestones, at least two speed bumps

---

## Load state

All reference condition sessions are conducted with:
- Driver only (no passengers, no cargo)
- Fuel tank level noted at each session (to control vehicle mass)
- Standard tyre pressures verified before each session (manufacturer-specified values, typically 2.2–2.4 bar front for the Space Star)

Any sessions with passengers or non-standard load are logged separately and not included in the reference dataset.

---

## Environmental conditions

| Parameter | Recorded? | Note |
|---|---|---|
| Ambient temperature | Yes (noted) | Affects strain gauge apparent strain; flag sessions with Δ>15°C during session |
| Weather (wet/dry) | Yes (noted) | Wet roads change tyre contact patch and may produce different load amplitudes |
| Wind | No | Effect on vehicle loads at urban speeds considered negligible |

Sessions in heavy rain or during winter (risk of ice or standing water producing handling interventions) are excluded from the reference dataset. Light rain is acceptable but noted.

---

## Surface type segments

The following surface segments are identified in the route and used to segment data for comparative analysis:

| Segment label | Surface type | Approx. speed | Expected dominant content |
|---|---|---|---|
| S1 | Smooth asphalt (bypass road) | 70–90 km/h | Low-amplitude, high-frequency road texture |
| S2 | Worn urban asphalt | 30–50 km/h | Medium amplitude, mixed frequency |
| S3 | Cobblestone section | 20–30 km/h | High amplitude, impulsive, elevated kurtosis |
| S4 | Speed bumps (3 bumps) | 15–20 km/h | Discrete high-amplitude events |
| S5 | Mixed urban (start/end) | 30–50 km/h | Variable |

Segment boundaries are marked approximately in the session log by timestamp. Exact identification in the signal requires manual inspection of the acceleration record (speed bumps produce clearly identifiable large-amplitude transients that anchor the time reference).

---

## Session log requirements

Each session is logged with the following metadata, stored in a plain text file alongside the CSV data:

```
Date:           YYYY-MM-DD
Start time:     HH:MM
Vehicle mileage: XXXXX km
Tyre pressure (front): X.X bar
Fuel level:     approx. XX%
Weather:        dry / light rain
Temp (ambient): XX°C
Driver:         (initials)
Route deviation: none / [description]
Notes:          [any anomalies — cable snag, SD error, unusual road event]
```

---

## What is not recorded

- GPS position (not instrumented; route is defined by manual description)
- Vehicle speed (not logged; estimated from known route segments and drive time)
- Engine state (idling vs. driving; all data is collected while moving)
- Brake applications (no brake sensor; identifiable from longitudinal acceleration spikes but not systematically recorded)

The absence of GPS and speed data means that frequency-domain features cannot be normalised by speed, which introduces speed as an uncontrolled variable in the PSD comparison. This is a known limitation and is discussed in `07_comparison/mismatch_analysis.md`.

---

## Known confounders

- **Traffic:** Stops, slow-moving traffic, and emergency braking events produce load patterns inconsistent with the target route profile. Segments affected by significant traffic are noted in the session log.
- **Road surface changes:** Road resurfacing or seasonal deterioration can change the character of familiar segments between sessions. Any visible surface change is noted.
- **Temperature:** Tyre stiffness and damper oil viscosity both change with temperature. Sessions at ambient temperatures below 5°C or above 30°C are flagged for this reason.
