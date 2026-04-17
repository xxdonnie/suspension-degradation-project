"""
build_load_cases.py
====================
Suspension Degradation Project
---------------------------------
Convert the experimental rainflow amplitude histogram produced by
process_pipeline.py into a set of representative FEM load cases for
static fatigue analysis.

Background
-----------
A FEM solver cannot run one load step per counted cycle (there may be
thousands). Instead, the amplitude histogram is discretized into N
representative load levels. Each level has:
  - A representative stress/strain amplitude
  - A total cycle count (summed from its constituent histogram bins)
  - A cumulative damage fraction (from Miner's rule)

The binning strategy used here is damage-weighted: bins are grouped so
that each load level contributes approximately equal damage to the total.
This ensures that no important amplitude range is under-represented in
the FEM model.

Inputs
-------
  --histogram   {stem}_amplitude_histogram.csv
                  columns: amplitude_bin_centre, cycle_count
  --cycles      {stem}_rainflow_cycles.csv  (optional, more precise)
                  columns: range, mean, count, amplitude

  --channel     'strain' or 'accel' (default: strain)
                  'strain' → amplitudes in με, converted to MPa via E
                  'accel'  → amplitudes in m/s², kept as proxy units

  --n-levels    Number of representative load levels (default: 8)

Outputs
--------
  {stem}_fem_load_cases.csv
      load_case, amplitude_signal, stress_mpa, n_cycles,
      cycle_fraction, damage_fraction, cumulative_damage_fraction

  {stem}_fem_load_cases_summary.txt
      Human-readable summary of load levels + run metadata

Usage
------
  python build_load_cases.py \\
      --histogram path/to/stem_amplitude_histogram.csv \\
      --n-levels 8 \\
      --channel strain \\
      --outdir path/to/06_fem_model/load_cases/

  # Use full rainflow cycles CSV for more precise binning
  python build_load_cases.py \\
      --cycles path/to/stem_rainflow_cycles.csv \\
      --n-levels 8 --channel strain

S-N curve
----------
Miner's rule uses BS 7608 Class B (plain material proxy):
  N_f = C / sigma_a^m   (sigma_a in MPa)
  m = 3.0,  C = 1.013e12

These must match the constants in process_pipeline.py.
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# Constants — must match process_pipeline.py
E_STEEL_MPA = 210e3         # Young's modulus, MPa (low-carbon steel)
SN_m        = 3.0
SN_C        = 1.013e12      # MPa^m cycles — BS 7608 Class B


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def amplitude_to_stress(amplitude_signal: np.ndarray, channel: str) -> np.ndarray:
    """
    Convert amplitude in signal units to stress amplitude in MPa.

    For strain channel: amplitude in με → stress in MPa via σ = E × ε.
    For accel channel:  amplitude kept in m/s² (proxy, not a stress).
    """
    if channel == "strain":
        return amplitude_signal * 1e-6 * E_STEEL_MPA
    else:
        log.warning(
            "Channel is 'accel' — stress_mpa column contains m/s² values, "
            "not physical stress. Do not use for Miner's rule damage."
        )
        return amplitude_signal.copy()


def miner_damage(stress_mpa: np.ndarray, counts: np.ndarray) -> np.ndarray:
    """Miner's partial damage D_i = n_i / N_f(sigma_i) for each cycle group."""
    with np.errstate(divide="ignore", invalid="ignore"):
        N_f = np.where(stress_mpa > 0, SN_C / (stress_mpa ** SN_m), np.inf)
    return np.where(N_f > 0, counts / N_f, 0.0)


def load_histogram(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read amplitude histogram CSV; returns (amplitudes, counts), zeros excluded."""
    df = pd.read_csv(path)
    if not {"amplitude_bin_centre", "cycle_count"}.issubset(df.columns):
        raise ValueError(
            f"Expected columns 'amplitude_bin_centre' and 'cycle_count' "
            f"in {path}. Got: {list(df.columns)}"
        )
    mask = df["cycle_count"] > 0
    return df.loc[mask, "amplitude_bin_centre"].values, df.loc[mask, "cycle_count"].values


def load_cycles(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read full rainflow cycles CSV; returns (amplitudes, counts), zeros excluded."""
    df = pd.read_csv(path)
    if not {"amplitude", "count"}.issubset(df.columns):
        raise ValueError(
            f"Expected columns 'amplitude' and 'count' in {path}. "
            f"Got: {list(df.columns)}"
        )
    mask = df["count"] > 0
    return df.loc[mask, "amplitude"].values, df.loc[mask, "count"].values


def damage_weighted_bins(
    amplitudes: np.ndarray,
    counts: np.ndarray,
    stress_mpa: np.ndarray,
    n_levels: int,
) -> pd.DataFrame:
    """
    Group amplitude histogram bins into n_levels representative load levels
    using equal-damage-fraction partitioning.

    Within each group the representative amplitude is the damage-weighted
    mean amplitude (not the simple mean), which best preserves the fatigue
    damage when applied as a single load case.

    Returns a DataFrame with one row per load level.
    """
    damage = miner_damage(stress_mpa, counts)
    D_total = damage.sum()

    if D_total == 0:
        log.warning("Total damage is zero — all amplitudes may be below the S-N endurance limit")
        # Fall back to equal-count partitioning
        cum_counts  = np.cumsum(counts)
        boundaries  = np.linspace(0, cum_counts[-1], n_levels + 1)
        split_by    = "count"
        cumulative  = cum_counts
    else:
        cum_damage  = np.cumsum(damage)
        boundaries  = np.linspace(0, D_total, n_levels + 1)
        split_by    = "damage"
        cumulative  = cum_damage

    rows = []
    for i in range(n_levels):
        lo, hi = boundaries[i], boundaries[i + 1]
        mask = (cumulative > lo) & (cumulative <= hi)

        # Last level picks up anything that fell through rounding
        if i == n_levels - 1:
            mask = cumulative > lo

        if not np.any(mask):
            continue

        grp_amp    = amplitudes[mask]
        grp_count  = counts[mask]
        grp_stress = stress_mpa[mask]
        grp_dmg    = damage[mask]

        # Damage-weighted representative amplitude
        dmg_sum = grp_dmg.sum()
        if dmg_sum > 0:
            rep_amp    = float(np.sum(grp_amp    * grp_dmg) / dmg_sum)
            rep_stress = float(np.sum(grp_stress * grp_dmg) / dmg_sum)
        else:
            rep_amp    = float(np.mean(grp_amp))
            rep_stress = float(np.mean(grp_stress))

        rows.append({
            "load_case":                  i + 1,
            "amplitude_signal":           round(rep_amp,    4),
            "stress_mpa":                 round(rep_stress, 4),
            "n_cycles":                   round(float(grp_count.sum()), 2),
            "cycle_fraction":             round(float(grp_count.sum() / counts.sum()), 6),
            "damage_fraction":            round(float(dmg_sum / D_total), 6) if D_total > 0 else 0.0,
            "cumulative_damage_fraction": 0.0,   # filled in below
            "n_bins_merged":              int(np.sum(mask)),
            "amp_min":                    round(float(grp_amp.min()), 4),
            "amp_max":                    round(float(grp_amp.max()), 4),
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["cumulative_damage_fraction"] = df["damage_fraction"].cumsum().round(6)
    return df


def write_summary(
    outdir: Path,
    stem: str,
    lc_df: pd.DataFrame,
    channel: str,
    source_file: str,
    n_levels: int,
    amplitudes: np.ndarray,
    counts: np.ndarray,
    stress_mpa: np.ndarray,
) -> None:
    D_total = miner_damage(stress_mpa, counts).sum()
    path    = outdir / f"{stem}_fem_load_cases_summary.txt"

    with open(path, "w") as f:
        f.write(f"FEM Load Cases — {stem}\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"Source file:    {source_file}\n")
        f.write(f"Channel:        {channel}\n")
        f.write(f"SN curve:       BS 7608 Class B  (m={SN_m}, C={SN_C:.3e})\n")
        f.write(f"E (steel):      {E_STEEL_MPA:.0f} MPa\n\n")
        f.write(f"Input bins:     {len(amplitudes)} non-zero bins\n")
        f.write(f"Total cycles:   {counts.sum():.0f}\n")
        f.write(f"Total damage:   {D_total:.4e}  (Miner's D)\n")
        f.write(f"Load levels:    {len(lc_df)} (requested {n_levels})\n\n")
        f.write(f"{'LC':>4}  {'Amp (signal)':>14}  {'Stress MPa':>10}  "
                f"{'N cycles':>10}  {'Cycle %':>8}  {'Damage %':>9}  {'Cum D%':>8}\n")
        f.write(f"{'-'*4}  {'-'*14}  {'-'*10}  {'-'*10}  {'-'*8}  {'-'*9}  {'-'*8}\n")
        for _, row in lc_df.iterrows():
            f.write(
                f"{int(row['load_case']):>4}  "
                f"{row['amplitude_signal']:>14.4f}  "
                f"{row['stress_mpa']:>10.4f}  "
                f"{row['n_cycles']:>10.0f}  "
                f"{row['cycle_fraction']*100:>7.2f}%  "
                f"{row['damage_fraction']*100:>8.2f}%  "
                f"{row['cumulative_damage_fraction']*100:>7.2f}%\n"
            )
        f.write(f"\nNote: amplitude_signal is in με for strain channel, "
                f"m/s² for accel channel.\n")
        f.write(f"      stress_mpa is physically meaningful only for strain channel.\n")

    log.info("Summary written: %s", path)


def build_load_cases(
    histogram_path: Path | None,
    cycles_path:    Path | None,
    outdir:         Path,
    n_levels:       int,
    channel:        str,
) -> pd.DataFrame:
    if cycles_path is not None:
        log.info("Loading full rainflow cycles from %s", cycles_path)
        amplitudes, counts = load_cycles(cycles_path)
        source_file = str(cycles_path)
        stem = cycles_path.stem.replace("_rainflow_cycles", "")
    elif histogram_path is not None:
        log.info("Loading amplitude histogram from %s", histogram_path)
        amplitudes, counts = load_histogram(histogram_path)
        source_file = str(histogram_path)
        stem = histogram_path.stem.replace("_amplitude_histogram", "")
    else:
        raise ValueError("Provide at least one of --histogram or --cycles")

    log.info("  %d non-zero amplitude bins, %.0f total cycles", len(amplitudes), counts.sum())

    stress_mpa = amplitude_to_stress(amplitudes, channel)

    log.info("Building %d damage-weighted load levels...", n_levels)
    lc_df = damage_weighted_bins(amplitudes, counts, stress_mpa, n_levels)

    if lc_df.empty:
        log.error("No load cases generated — check input data")
        return lc_df

    log.info("  %d load levels generated", len(lc_df))

    outdir.mkdir(parents=True, exist_ok=True)

    csv_path = outdir / f"{stem}_fem_load_cases.csv"
    lc_df.to_csv(csv_path, index=False)
    log.info("Load cases CSV written: %s", csv_path)

    write_summary(outdir, stem, lc_df, channel, source_file,
                  n_levels, amplitudes, counts, stress_mpa)

    log.info("\nLoad case table:")
    header = (f"  {'LC':>3}  {'Amp(signal)':>12}  {'Stress MPa':>10}  "
              f"{'N cycles':>9}  {'Dmg %':>7}  {'CumDmg %':>9}")
    log.info(header)
    for _, row in lc_df.iterrows():
        log.info(
            "  %3d  %12.3f  %10.4f  %9.0f  %6.2f%%  %8.2f%%",
            row["load_case"],
            row["amplitude_signal"],
            row["stress_mpa"],
            row["n_cycles"],
            row["damage_fraction"] * 100,
            row["cumulative_damage_fraction"] * 100,
        )

    return lc_df


def parse_args():
    p = argparse.ArgumentParser(
        description="Convert experimental amplitude histogram to FEM load cases."
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument(
        "--histogram", type=Path, default=None,
        help="Path to {stem}_amplitude_histogram.csv (from process_pipeline)",
    )
    src.add_argument(
        "--cycles", type=Path, default=None,
        help="Path to {stem}_rainflow_cycles.csv (higher resolution alternative)",
    )
    p.add_argument(
        "--outdir", "-o", type=Path, default=None,
        help="Output directory (default: same as input file)",
    )
    p.add_argument(
        "--n-levels", "-n", type=int, default=8,
        help="Number of representative FEM load levels (default: 8)",
    )
    p.add_argument(
        "--channel", choices=["strain", "accel"], default="strain",
        help="Signal channel: 'strain' (με→MPa via E) or 'accel' (proxy units). Default: strain",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.histogram is None and args.cycles is None:
        log.error("Provide --histogram or --cycles (see --help)")
        return 1

    source = args.cycles or args.histogram
    if not source.exists():
        log.error("Input file not found: %s", source)
        return 1

    if args.n_levels < 1:
        log.error("--n-levels must be at least 1")
        return 1

    outdir = args.outdir or source.parent

    try:
        lc_df = build_load_cases(
            histogram_path = args.histogram,
            cycles_path    = args.cycles,
            outdir         = outdir,
            n_levels       = args.n_levels,
            channel        = args.channel,
        )
    except Exception as exc:
        log.error("Failed: %s", exc)
        return 1

    return 0 if not lc_df.empty else 1


if __name__ == "__main__":
    sys.exit(main())
