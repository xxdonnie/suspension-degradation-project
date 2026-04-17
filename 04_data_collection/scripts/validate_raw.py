"""
validate_raw.py — pre-flight validator for raw Arduino DAQ CSV files.

Checks columns, record length, timestamp integrity, sampling rate,
data gaps, and ADC saturation. Run before process_pipeline.py.

Usage:
  python validate_raw.py path/to/log.csv          # single file
  python validate_raw.py path/to/raw_data/        # all CSVs in dir
  python validate_raw.py path/to/log.csv --json   # JSON output

Exit codes: 0 = clean, 1 = warnings, 2 = errors.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# Constants — must match process_pipeline.py
FS_EXPECTED       = 200.0          # Hz
MIN_RECORD_S      = 10.0           # seconds — shorter records are flagged as errors
WARN_RECORD_S     = 30.0           # seconds — shorter records get a warning
FS_TOLERANCE      = 0.05           # ±5% tolerance on measured sampling rate
GAP_THRESHOLD     = 2.0            # multiples of expected dt before flagging a gap
MAX_GAP_FRACTION  = 0.01           # >1% gap samples → error
MAX_DUP_FRACTION  = 0.001          # >0.1% duplicates → error

# MPU-6050 16-bit signed: rail at ±32767
ACCEL_RAIL        = 32767
ACCEL_SAT_MARGIN  = 16             # flag if within 16 counts of rail

# Arduino 10-bit ADC for strain (0–1023). Adjust to 4095 for 12-bit.
STRAIN_ADC_MAX    = 1023
STRAIN_SAT_MARGIN = 8              # flag if within 8 counts of either rail

EXPECTED_COLS = ["timestamp_ms", "accel_x", "accel_y", "accel_z", "strain_raw"]


PASS    = "PASS"
WARN    = "WARN"
ERROR   = "ERROR"

def _check(status: str, label: str, message: str) -> dict:
    return {"status": status, "check": label, "message": message}


def check_columns(df: pd.DataFrame) -> dict:
    cols = list(df.columns)
    if cols == EXPECTED_COLS:
        return _check(PASS, "columns", "columns OK")
    missing = [c for c in EXPECTED_COLS if c not in cols]
    extra   = [c for c in cols if c not in EXPECTED_COLS]
    msg = []
    if missing:
        msg.append(f"missing: {missing}")
    if extra:
        msg.append(f"unexpected: {extra}")
    return _check(ERROR, "columns", "; ".join(msg))


def check_row_count(df: pd.DataFrame) -> dict:
    n = len(df)
    duration_s = n / FS_EXPECTED
    if duration_s < MIN_RECORD_S:
        return _check(ERROR, "row_count",
                      f"{n} rows (~{duration_s:.1f} s) — below minimum {MIN_RECORD_S} s")
    if duration_s < WARN_RECORD_S:
        return _check(WARN, "row_count",
                      f"{n} rows (~{duration_s:.1f} s) — short record, review before use")
    return _check(PASS, "row_count", f"{n} rows (~{duration_s:.1f} s)")


def check_monotonicity(df: pd.DataFrame) -> dict:
    ts = df["timestamp_ms"].values
    backwards = int(np.sum(np.diff(ts) < 0))
    if backwards == 0:
        return _check(PASS, "monotonicity", "Timestamps are monotonically increasing")
    return _check(ERROR, "monotonicity",
                  f"{backwards} backwards timestamp step(s) detected")


def check_duplicates(df: pd.DataFrame) -> dict:
    n_dup = int(df["timestamp_ms"].duplicated().sum())
    frac  = n_dup / len(df)
    if n_dup == 0:
        return _check(PASS, "duplicates", "No duplicate timestamps")
    status = ERROR if frac > MAX_DUP_FRACTION else WARN
    return _check(status, "duplicates",
                  f"{n_dup} duplicate timestamps ({frac*100:.2f}%)")


def check_sampling_rate(df: pd.DataFrame) -> dict:
    ts = df["timestamp_ms"].values
    dt = np.diff(ts)
    median_dt_ms = float(np.median(dt))
    measured_fs  = 1000.0 / median_dt_ms if median_dt_ms > 0 else 0.0
    err_frac     = abs(measured_fs - FS_EXPECTED) / FS_EXPECTED

    msg = (f"median dt = {median_dt_ms:.2f} ms → "
           f"estimated FS = {measured_fs:.1f} Hz (expected {FS_EXPECTED:.0f} Hz)")

    if err_frac > FS_TOLERANCE:
        return _check(WARN, "sampling_rate", msg + f" — {err_frac*100:.1f}% off target")
    return _check(PASS, "sampling_rate", msg)


def check_gaps(df: pd.DataFrame) -> dict:
    ts            = df["timestamp_ms"].values
    expected_dt   = 1000.0 / FS_EXPECTED
    dt            = np.diff(ts)
    gap_mask      = dt > GAP_THRESHOLD * expected_dt
    n_gaps        = int(np.sum(gap_mask))
    total_missing = int(np.sum(np.round(dt[gap_mask] / expected_dt).astype(int) - 1))
    gap_frac      = total_missing / len(df)

    if n_gaps == 0:
        return _check(PASS, "gaps", "No data gaps detected")

    gap_times = (ts[:-1][gap_mask] - ts[0]) / 1000.0  # seconds from start
    gap_str   = ", ".join(f"{t:.1f}s" for t in gap_times[:5])
    if len(gap_times) > 5:
        gap_str += f" … (+{len(gap_times)-5} more)"

    status = ERROR if gap_frac > MAX_GAP_FRACTION else WARN
    return _check(status, "gaps",
                  f"{n_gaps} gap(s), ~{total_missing} missing samples "
                  f"({gap_frac*100:.2f}%) at: {gap_str}")


def check_saturation(df: pd.DataFrame) -> list[dict]:
    results = []

    for col in ["accel_x", "accel_y", "accel_z"]:
        if col not in df.columns:
            continue
        vals   = df[col].values
        n_sat  = int(np.sum(np.abs(vals) >= ACCEL_RAIL - ACCEL_SAT_MARGIN))
        frac   = n_sat / len(vals)
        label  = f"saturation_{col}"
        if n_sat == 0:
            results.append(_check(PASS, label, "no saturation"))
        else:
            status = ERROR if frac > 0.001 else WARN
            results.append(_check(status, label,
                                  f"{n_sat} saturated samples ({frac*100:.3f}%)"))

    if "strain_raw" in df.columns:
        vals  = df["strain_raw"].values
        n_lo  = int(np.sum(vals <= STRAIN_SAT_MARGIN))
        n_hi  = int(np.sum(vals >= STRAIN_ADC_MAX - STRAIN_SAT_MARGIN))
        n_sat = n_lo + n_hi
        frac  = n_sat / len(vals)
        label = "saturation_strain_raw"
        if n_sat == 0:
            results.append(_check(PASS, label, "no saturation"))
        else:
            status = ERROR if frac > 0.001 else WARN
            results.append(_check(status, label,
                                  f"{n_sat} saturated samples ({frac*100:.3f}%) "
                                  f"[low: {n_lo}, high: {n_hi}]"))

    return results


def channel_stats(df: pd.DataFrame) -> dict:
    """Return basic per-channel statistics."""
    stats = {}
    for col in EXPECTED_COLS[1:]:   # skip timestamp_ms
        if col not in df.columns:
            continue
        v = df[col].values
        stats[col] = {
            "mean":   round(float(np.mean(v)), 3),
            "std":    round(float(np.std(v)),  3),
            "min":    round(float(np.min(v)),  3),
            "max":    round(float(np.max(v)),  3),
        }
    return stats


def validate_file(csv_path: Path) -> dict:
    result = {
        "file":   str(csv_path),
        "status": ERROR,
        "checks": [],
        "stats":  {},
    }

    try:
        raw = pd.read_csv(csv_path, header=None, nrows=1)
        first_cell = str(raw.iloc[0, 0]).strip().lower()
        has_header = not first_cell.lstrip("-").replace(".", "").isdigit()

        df = pd.read_csv(
            csv_path,
            header=0 if has_header else None,
            names=EXPECTED_COLS,
        )
    except Exception as exc:
        result["checks"].append(_check(ERROR, "load", f"Failed to read file: {exc}"))
        return result

    checks: list[dict] = []

    col_check = check_columns(df)
    checks.append(col_check)

    if col_check["status"] == ERROR:
        result["checks"] = checks
        return result   # no point continuing with wrong schema

    checks.append(check_row_count(df))
    checks.append(check_monotonicity(df))
    checks.append(check_duplicates(df))
    checks.append(check_sampling_rate(df))
    checks.append(check_gaps(df))
    checks.extend(check_saturation(df))

    levels = {PASS: 0, WARN: 1, ERROR: 2}
    worst  = max(checks, key=lambda x: levels[x["status"]])["status"]

    n   = len(df)
    dur = round(n / FS_EXPECTED, 1)

    result.update({
        "status":     worst,
        "n_rows":     n,
        "duration_s": dur,
        "checks":     checks,
        "stats":      channel_stats(df),
    })
    return result


_ICONS = {PASS: "✓", WARN: "△", ERROR: "✗"}


def _print_result(result: dict) -> None:
    icon = _ICONS[result["status"]]
    path = Path(result["file"]).name
    print(f"\n{'='*60}")
    print(f"  {icon}  {path}  [{result['status']}]")
    if "n_rows" in result:
        print(f"     {result['n_rows']} rows  /  {result['duration_s']} s")
    print(f"{'='*60}")

    for c in result["checks"]:
        icon_c = _ICONS[c["status"]]
        print(f"  {icon_c}  [{c['check']:25s}]  {c['message']}")

    if result["stats"]:
        print(f"\n  Channel statistics (raw ADC counts / physical pre-conversion):")
        for col, s in result["stats"].items():
            print(f"    {col:15s}  mean={s['mean']:>10.2f}  "
                  f"std={s['std']:>10.2f}  "
                  f"min={s['min']:>10.2f}  "
                  f"max={s['max']:>10.2f}")
    print()


def parse_args():
    p = argparse.ArgumentParser(
        description="Pre-flight validator for raw Arduino DAQ CSV files."
    )
    p.add_argument(
        "path", type=Path,
        help="Path to a single CSV file or a directory of CSV files",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Output results as JSON (suppresses human-readable output)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.path.is_dir():
        files = sorted(args.path.glob("*.csv"))
        if not files:
            print(f"No CSV files found in {args.path}", file=sys.stderr)
            return 2
    elif args.path.is_file():
        files = [args.path]
    else:
        print(f"Path not found: {args.path}", file=sys.stderr)
        return 2

    results  = [validate_file(f) for f in files]
    levels   = {PASS: 0, WARN: 1, ERROR: 2}
    worst    = max(results, key=lambda r: levels[r["status"]])["status"]
    exit_code = levels[worst]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            _print_result(r)

        n_pass  = sum(1 for r in results if r["status"] == PASS)
        n_warn  = sum(1 for r in results if r["status"] == WARN)
        n_error = sum(1 for r in results if r["status"] == ERROR)
        print(f"Summary: {len(results)} file(s) — "
              f"{n_pass} clean, {n_warn} warnings, {n_error} errors")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
