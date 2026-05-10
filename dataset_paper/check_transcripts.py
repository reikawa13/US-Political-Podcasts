#!/usr/bin/env python3
"""Verify that every metadata row has a matching transcript file.

By default this script reads `podMetadata_Nov5_with_leaning.csv` and checks for
files stored under:
    final_Transcripts_beforeNov5/<podName>/trans_<ID>.txt

It prints a short report with the number of files found and missing. If any
transcripts are missing, their expected paths are listed so you can investigate.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import List, Tuple

DEFAULT_INPUT = "podMetadata_Nov5_with_leaning.csv"
DEFAULT_BASE = Path("final_Transcripts_beforeNov5")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether transcript files exist for every metadata row."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT),
        help="Metadata CSV with ID and podName columns (default: %(default)s).",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE,
        help="Directory that contains per-podcast transcript folders (default: %(default)s).",
    )
    parser.add_argument(
        "--show-missing",
        action="store_true",
        help="List every missing file path instead of just the first few.",
    )
    return parser.parse_args()


def expected_path(base: Path, pod_name: str, episode_id: str) -> Path:
    """Return the expected transcript path for a single row."""
    return base / pod_name / f"trans_{episode_id}.txt"


def check_transcripts(csv_path: Path, base: Path) -> Tuple[int, List[Path]]:
    """Return total rows and a list of missing transcript paths."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Input file not found: {csv_path}")
    missing: List[Path] = []
    total = 0
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            episode_id = (row.get("ID") or "").strip()
            pod_name = (row.get("podName") or "").strip()
            if not episode_id or not pod_name:
                # Skip rows missing essential info but count them toward total.
                missing.append(Path(f"[missing fields] row {total}"))
                continue
            path = expected_path(base, pod_name, episode_id)
            if not path.exists():
                missing.append(path)
    return total, missing


def main() -> None:
    args = parse_args()
    total, missing = check_transcripts(args.input, args.base_dir)

    print(f"Checked {total} metadata rows.")
    print(f"Transcript base directory: {args.base_dir.resolve()}")

    if not missing:
        print("All transcript files are present ✅")
        return

    print(f"Missing {len(missing)} transcript files.")
    sample = missing if args.show_missing else missing[:10]
    print("Examples of missing files:")
    for path in sample:
        print(f"  - {path}")
    if not args.show_messing and len(missing) > len(sample):
        print("  ... (use --show-missing to display the full list)")


if __name__ == "__main__":
    main()
