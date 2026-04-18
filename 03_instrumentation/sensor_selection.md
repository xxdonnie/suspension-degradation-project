# Sensor Selection

## Design constraints

The instrumentation had to meet several non-negotiable constraints before component selection:

- **Cost:** Total sensor and DAQ cost under ~€100. No industrial-grade hardware.
- **Non-invasive mounting:** Cannot drill into or permanently modify the strut. Adhesive or clamp mounting only.
- **Self-contained logging:** The vehicle interior cannot be modified. The DAQ must log autonomously without a laptop present.
- **200 Hz minimum sample rate:** Captures up to 100 Hz via Nyquist — sufficient to resolve wheel hop (~12 Hz) and the lower structural modes of the strut.
- **Dual channel:** At least one acceleration channel and one strain channel, to allow the comparison between load input (acceleration) and load response (strain).

---

## Accelerometer — MPU-6050

| Parameter | Value |
|---|---|
| Sensor | InvenSense MPU-6050 |
| Interface | I2C (400 kHz fast mode) |
| Axes | 3-axis accelerometer + 3-axis gyroscope (gyro not used) |
| ADC resolution | 16-bit signed |
| Full-scale range (configured) | ±16g |
| Sensitivity at ±16g | 2048 LSB/g |
| Noise density | ~400 μg/√Hz |
| Approximate noise floor (at 200 Hz) | ~20–30 mg RMS |
| Supply voltage | 3.3 V (via Arduino 3.3 V rail) |
| Cost | ~€3–5 (breakout board) |

**Why ±16g range?** Normal suspension events on road surfaces produce accelerations of 1–5g at the wheel hub. A large pothole or kerb can produce 10–15g transiently. The ±16g range avoids saturation in virtually all on-road events while accepting a higher noise floor than the ±2g or ±4g ranges. The ±16g range with 16-bit ADC gives a resolution of approximately 0.488 mg per count, which is adequate for resolving structural vibrations above 0.1g.

**Why not a MEMS accelerometer with lower noise?** Industrial MEMS units (e.g. PCB Piezotronics, Kistler) with noise floors of 1–10 μg/√Hz would give far superior signal quality but cost €200–1000 per channel. The MPU-6050 is a reasonable trade-off given the project constraints. Its noise floor (20–30 mg) is acceptable because the structural signals of interest (wheel hop, body bounce) are well above this level.

**Why three axes?** The z-axis (vertical, perpendicular to the road) is the primary fatigue loading direction. The x and y axes (lateral and longitudinal) provide additional context for identifying cornering and braking events and can be used for signal quality checks. Only z is used in the primary pipeline.

---

## Strain measurement — INA125 + foil strain gauge

### Strain gauge

| Parameter | Value |
|---|---|
| Type | Bonded foil resistance strain gauge |
| Resistance | 120 Ω (standard) |
| Gauge factor | ~2.0 (manufacturer nominal for constantan foil) |
| Grid length | ~6 mm |
| Backing | Polyimide (suitable for steel substrates) |
| Operating temperature range | −30°C to +120°C |
| Cost | ~€3–8 per gauge |

A single-axis gauge was selected (not a rosette) because the budget and ADC channel count allowed only one strain measurement. The gauge axis is aligned with the expected dominant principal stress direction at the mounting location (see `03_instrumentation/sensor_placement.md`).

### Amplifier — INA125

| Parameter | Value |
|---|---|
| Chip | Texas Instruments INA125 |
| Type | Instrumentation amplifier with integrated bridge excitation |
| Bridge excitation | ~5 V internal reference |
| Gain range | 4 to 10,000 (set by single external resistor R_G) |
| Gain configured | To be measured/confirmed during calibration |
| CMRR | 90 dB typical |
| Supply voltage | 5 V (from Arduino 5 V rail) |
| Output | 0 to Vcc, centred at mid-supply for zero strain |
| Cost | ~€5–10 (DIP package) |

**Why INA125?** It integrates the bridge excitation voltage reference (±5 V bridge supply) and instrumentation amplifier into a single IC, minimising component count. Competing options (AD620, INA128) require an external reference for bridge excitation. The INA125 is well suited for single-channel bridge measurements with a microcontroller ADC.

**Gain selection:** The gain resistor R_G is chosen to map the expected strain range (±0 to ±500 με) to a useful fraction of the ADC range (0–1023 counts on a 10-bit Arduino ADC). The exact gain used and the resulting scale factor are documented in `03_instrumentation/calibration_notes.md`.

---

## Data acquisition — Arduino

| Parameter | Value |
|---|---|
| Board | Arduino Uno R3 (or compatible) |
| Processor | ATmega328P, 16 MHz |
| ADC (strain) | 10-bit, successive approximation, 0–5 V input range |
| ADC resolution | 1024 counts, ~4.9 mV per count at 5 V |
| I2C master | Hardware I2C (SCL/SDA pins) for MPU-6050 |
| Storage | SD card module via SPI |
| Sampling rate | 200 Hz (5 ms loop, blocking I2C + ADC read) |
| Power | USB power bank (5 V, ≥1 A) |
| Cost | ~€5–20 (clone board) |

**Why Arduino?** The 10-bit ADC and 16 MHz processor are significant limitations compared to 12-bit or 16-bit DAQ systems. However, the Arduino ecosystem provides a well-understood, low-cost hardware platform with SD card logging libraries that can sustain 200 Hz. The 10-bit ADC resolution (4.9 mV/count, approximately 0.5 με/count for the configured gain) is marginally adequate for detecting fatigue-relevant strain amplitudes above approximately 10 με.

**Logging format:** Each sample is written to an SD card as a CSV row: `timestamp_ms, accel_x, accel_y, accel_z, strain_raw`. The Arduino `millis()` function provides the timestamp. No buffering is used — each sample is written immediately, which limits achievable sample rate but prevents data loss on SD write errors.

---

## Component summary

| Component | Model | Purpose | Cost (approx.) |
|---|---|---|---|
| Accelerometer | MPU-6050 breakout | 3-axis acceleration (z primary) | €3–5 |
| Instrumentation amp | INA125 DIP | Strain gauge bridge amplifier | €5–10 |
| Strain gauge | 120 Ω foil gauge | Surface strain measurement | €3–8 |
| Microcontroller | Arduino Uno | ADC, I2C master, SD logging | €5–20 |
| SD module | SPI SD breakout | Data storage | €2–5 |
| Power | USB power bank | Self-contained operation | €10–20 |
| **Total** | | | **~€30–70** |
