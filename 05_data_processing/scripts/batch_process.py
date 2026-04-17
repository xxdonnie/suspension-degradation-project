"""
batch_process.py
=================
Suspension Degradation Project
---------------------------------
Batch runner for process_pipeline.py.
Processes every raw CSV file in an input directory and aggregates
all per-file feature summaries into a single master table.

Usage
------
  # Process all CSVs in raw_data/, output to processed/
  python batch_process.py --input-dir ../../04_data_collection/raw_data \\
                          --outdir ./processed

  # Dry run — list files that would be processed without running pipeline
  python batch_process.py --input-dir path/to/csvs --dry-run

  # Skip files that have already been processed
  python batch_process.py --input-dir path/to/csvs --skip-existing

Output structure
-----------------
  <outdir>/
    <stem>/
      strain_ue/    (per-file pipeline outputs, same as single-file run)
      accel_z/
    ...
  all_sessions_features.csv   ← master table, one row per file × channel
  batch_summary.txt           ← run log with pass/fail per file
"""

import argparse
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# process_pipeline.py lives in the same scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent))
try:
    from process_pipeline import run_pipeline
except ImportError as e:
    log.error("Could not import process_pipeline: %s", e)
    log.error("Ensure batch_process.py is in the same directory as process_pipeline.py")
    sys.exit(1)


def collect_feature_summaries(outdir: Path) -> pd.DataFrame:
    """Collect all *_features_summary.csv files under outdir into one DataFrame."""
    summaries = []
    for summary_path in sorted(outdir.rglob("*_features_summary.csv")):
        try:
            df = pd.read_csv(summary_path)
            stem    = summary_path.stem.replace("_features_summary", "")
            channel = summary_path.parent.name   # strain_ue or accel_z
            df.insert(0, "session", stem)
            df.insert(1, "channel_dir", channel)
            df.insert(2, "summary_path", str(summary_path))
            summaries.append(df)
        except Exception as exc:
            log.warning("Could not read %s: %s", summary_path, exc)

    if not summaries:
        return pd.DataFrame()
    return pd.concat(summaries, ignore_index=True)


def run_batch(
    input_dir: Path,
    outdir: Path,
    skip_existing: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Process all CSVs in input_dir through run_pipeline.

    Returns a summary dict with keys:
      total, succeeded, failed, skipped, failed_files
    """
    csv_files = sorted(input_dir.glob("*.csv"))

    if not csv_files:
        log.warning("No CSV files found in %s", input_dir)
        return {"total": 0, "succeeded": 0, "failed": 0, "skipped": 0, "failed_files": []}

    log.info("Found %d CSV file(s) in %s", len(csv_files), input_dir)

    summary = {
        "total":        len(csv_files),
        "succeeded":    0,
        "failed":       0,
        "skipped":      0,
        "failed_files": [],
    }

    for csv_path in csv_files:
        stem        = csv_path.stem
        file_outdir = outdir / stem

        if skip_existing:
            existing = list(file_outdir.rglob("*_features_summary.csv"))
            if existing:
                log.info("  SKIP  %s  (outputs exist, use --skip-existing=false to rerun)",
                         csv_path.name)
                summary["skipped"] += 1
                continue

        if dry_run:
            log.info("  DRY   %s  → %s", csv_path.name, file_outdir)
            continue

        log.info("  RUN   %s", csv_path.name)
        try:
            run_pipeline(csv_path, file_outdir)
            summary["succeeded"] += 1
            log.info("  OK    %s", csv_path.name)
        except Exception:
            summary["failed"] += 1
            summary["failed_files"].append(str(csv_path))
            log.error("  FAIL  %s\n%s", csv_path.name, traceback.format_exc())

    return summary


def build_master_table(outdir: Path) -> Path | None:
    """Write all_sessions_features.csv; returns the path or None if no summaries found."""
    master = collect_feature_summaries(outdir)
    if master.empty:
        log.warning("No feature summary files found under %s — master table not written", outdir)
        return None

    master_path = outdir / "all_sessions_features.csv"
    master.to_csv(master_path, index=False)
    log.info("Master table written: %s  (%d rows)", master_path, len(master))
    return master_path


def write_batch_summary(
    outdir: Path,
    summary: dict,
    input_dir: Path,
    master_path: Path | None,
) -> None:
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path = outdir / "batch_summary.txt"

    with open(path, "w") as f:
        f.write(f"Batch run: {ts}\n")
        f.write(f"Input dir: {input_dir}\n")
        f.write(f"Output dir: {outdir}\n\n")
        f.write(f"Total files:  {summary['total']}\n")
        f.write(f"Succeeded:    {summary['succeeded']}\n")
        f.write(f"Failed:       {summary['failed']}\n")
        f.write(f"Skipped:      {summary['skipped']}\n")
        if summary["failed_files"]:
            f.write("\nFailed files:\n")
            for ff in summary["failed_files"]:
                f.write(f"  {ff}\n")
        if master_path:
            f.write(f"\nMaster table: {master_path}\n")

    log.info("Batch summary written: %s", path)


def parse_args():
    p = argparse.ArgumentParser(
        description="Batch process raw CSV files through the suspension pipeline."
    )
    p.add_argument(
        "--input-dir", "-i", required=True, type=Path,
        help="Directory containing raw Arduino CSV files",
    )
    p.add_argument(
        "--outdir", "-o", type=Path, default=None,
        help="Root output directory (default: <input-dir>/../processed)",
    )
    p.add_argument(
        "--skip-existing", action="store_true", default=False,
        help="Skip files whose output directory already contains feature summaries",
    )
    p.add_argument(
        "--dry-run", action="store_true", default=False,
        help="List files that would be processed without running the pipeline",
    )
    p.add_argument(
        "--no-master", action="store_true", default=False,
        help="Skip building the master all_sessions_features.csv table",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not args.input_dir.exists():
        log.error("Input directory not found: %s", args.input_dir)
        return 1

    outdir = args.outdir or args.input_dir.parent / "processed"
    outdir.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("Batch processor — suspension degradation project")
    log.info("Input:  %s", args.input_dir)
    log.info("Output: %s", outdir)
    if args.dry_run:
        log.info("DRY RUN — no files will be processed")
    log.info("=" * 60)

    summary = run_batch(
        input_dir     = args.input_dir,
        outdir        = outdir,
        skip_existing = args.skip_existing,
        dry_run       = args.dry_run,
    )

    master_path = None
    if not args.dry_run and not args.no_master:
        master_path = build_master_table(outdir)

    if not args.dry_run:
        write_batch_summary(outdir, summary, args.input_dir, master_path)

    log.info("=" * 60)
    log.info(
        "Done — %d/%d succeeded, %d failed, %d skipped",
        summary["succeeded"], summary["total"],
        summary["failed"], summary["skipped"],
    )
    log.info("=" * 60)

    return 1 if summary["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
