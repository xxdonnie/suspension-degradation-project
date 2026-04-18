# Data Logging Plan

## Hardware setup

Before each session, verify the following:

1. Arduino is powered from the USB power bank (not a laptop — avoids ground loop noise from the laptop charger)
2. SD card is inserted and has sufficient free space (each 15-minute session at 200 Hz × 5 columns ≈ 18 MB)
3. Strain gauge cable is dressed and secured along the damper tube — no contact with the coil spring
4. Accelerometer orientation mark is aligned with the reference mark on the strut tower panel
5. Check that the previous session's file was closed cleanly (file size > 0, not zero bytes from an interrupted session)

The Arduino sketch is loaded once and does not require modification between sessions. It begins logging immediately on power-up.

---

## File naming convention

Each session produces one CSV file named:

```
YYYYMMDD_HHMM_<condition>.csv
```

Examples:
```
20240315_1430_reference.csv     — standard reference route, dry
20240318_0900_reference_wet.csv — reference route, light rain
20240322_1100_speedbump_only.csv — isolated speed bump test
```

The `condition` suffix is a short freeform label. For reference dataset sessions it is always `reference`. Supplementary or exploratory sessions use a descriptive suffix.

---

## CSV file format

The Arduino logger writes one row per sample with no header row by default. The format is:

```
timestamp_ms,accel_x,accel_y,accel_z,strain_raw
```

| Column | Units | Description |
|---|---|---|
| `timestamp_ms` | milliseconds | Arduino `millis()` counter; starts at 0 at power-up |
| `accel_x` | ADC counts (16-bit signed) | MPU-6050 x-axis (longitudinal, forward positive) |
| `accel_y` | ADC counts (16-bit signed) | MPU-6050 y-axis (lateral, left positive) |
| `accel_z` | ADC counts (16-bit signed) | MPU-6050 z-axis (vertical, upward positive) |
| `strain_raw` | ADC counts (10-bit unsigned, 0–1023) | INA125 output after Arduino ADC |

No header row is written by the Arduino sketch. The processing pipeline (`process_pipeline.py`) and validator (`validate_raw.py`) auto-detect whether a header is present and assign column names accordingly.

---

## Pre-session checklist

Run `validate_raw.py` on the previous session's file before starting a new session. This catches:
- Truncated files from SD write failures
- Sampling rate drift (indicates Arduino timing issues)
- Saturation events on either channel
- Timestamp monotonicity errors

```bash
python 04_data_collection/scripts/validate_raw.py path/to/previous_session.csv
```

If the validation returns errors, investigate before collecting more data. Do not discard the errored file — it may still contain usable segments.

---

## Session procedure

1. Install Arduino + power bank in the vehicle (footwell or centre console)
2. Route cable to engine bay; verify no snagging against moving parts
3. Power on Arduino — it begins logging immediately
4. Wait 30 seconds in the stationary vehicle (engine off) to capture the static zero reference
5. Start the engine; note any changes in the baseline (engine vibration should be visible in the strain channel)
6. Drive the reference route following the standard speed profile
7. On return, park, engine off, wait 15 seconds (static end reference)
8. Power off Arduino
9. Remove SD card; copy file to laptop; verify file size and row count

---

## Session duration target

| Session type | Target duration | Minimum acceptable |
|---|---|---|
| Reference route (full) | 15–20 min | 10 min |
| Isolated surface segment | 5–10 min | 3 min |
| Speed bump test | 2–5 min | — |

The minimum acceptable duration is set by the requirement for at least 10 minutes of data to produce statistically stable rainflow amplitude histograms. Short sessions (< 3 minutes) have insufficient cycles in the low-to-mid amplitude range and produce noisy damage estimates.

---

## Storage and backup

Raw CSV files are stored in `04_data_collection/raw_data/` (excluded from git via `.gitignore`). Each session directory should contain:

```
04_data_collection/raw_data/
└── YYYYMMDD_HHMM_condition/
    ├── YYYYMMDD_HHMM_condition.csv     ← raw Arduino output
    └── session_log.txt                 ← metadata (see driving_conditions.md)
```

Backup to an external drive or cloud storage after each session. The raw data cannot be regenerated once the session is over — it is the primary measurement record.

---

## Processing workflow after collection

Once a raw file passes validation:

```bash
# 1. Validate
python 04_data_collection/scripts/validate_raw.py raw_data/session.csv

# 2. Process (single file)
python 05_data_processing/scripts/process_pipeline.py \
    raw_data/session.csv \
    --outdir processed/session/

# 3. Batch process (all sessions)
python 05_data_processing/scripts/batch_process.py \
    --input-dir raw_data/ \
    --outdir processed/

# 4. Build FEM load cases from amplitude histogram
python 06_fem_model/scripts/build_load_cases.py \
    --histogram processed/session/strain_ue/session_amplitude_histogram.csv \
    --n-levels 8 \
    --channel strain \
    --outdir 06_fem_model/load_cases/
```

Processed outputs are also excluded from git (see `.gitignore`). Only the scripts, documentation, and summary tables are tracked.
