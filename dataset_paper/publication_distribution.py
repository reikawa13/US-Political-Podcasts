#!/usr/bin/env python3
"""Generate the monthly podcast publication chart used in the report.

This script re-creates the black-background bar chart that shows how many
episodes were published per month.  It expects the metadata CSV exported on
Nov 5 (the file with the `date` column used earlier in the project).

Dependencies:
    - pandas
    - matplotlib

Usage:
    python publication_distribution.py \
        --input podMetadata_Nov5_with_leaning.csv \
        --output graphs/pod_publication_distribution.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %z"
DEFAULT_INPUT = "podMetadata_Nov5_with_leaning.csv"
DEFAULT_OUTPUT = "graphs/pod_publication_distribution.png"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for flexible file locations."""
    parser = argparse.ArgumentParser(
        description="Plot the monthly publication volume of podcast episodes."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT),
        help="CSV file containing the `date` column (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT),
        help="Where to save the generated PNG chart (default: %(default)s).",
    )
    return parser.parse_args()


def load_monthly_counts(csv_path: Path) -> pd.Series:
    """Read the CSV and aggregate counts per month.

    Returns a pandas Series indexed by month start timestamps, ordered chronologically.
    Episodes with missing or malformed dates are ignored.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Input file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    # Parse publication dates; coerce invalid rows to NaT so we can drop them.
    df["date"] = pd.to_datetime(df["date"], format=DATE_FORMAT, errors="coerce", utc=True)
    df = df.dropna(subset=["date"])

    # Convert to regular timestamp so matplotlib sees chronological spacing.
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    counts = df.groupby("month").size().sort_index()
    if counts.empty:
        raise ValueError("No valid dates found; cannot build monthly distribution.")
    return counts


def plot_distribution(counts: pd.Series, output_path: Path) -> None:
    """Render the bar chart so it matches the style requested by the user."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 4))
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")

    labels = [month.strftime("%Y-%m") for month in counts.index]

    ax.bar(labels, counts.values, color="#1abc9c", width=0.8)
    ax.set_xlabel("Months", color="white", labelpad=10)
    ax.set_ylabel("# Episodes", color="white", labelpad=10)
    ax.set_title("Podcast Publication Volume by Month", color="white", pad=12)

    ax.tick_params(axis="x", colors="white", rotation=60, labelsize=7)
    ax.tick_params(axis="y", colors="white")
    for spine in ax.spines.values():
        spine.set_color("white")

    ax.margins(x=0)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    args = parse_args()
    counts = load_monthly_counts(args.input)
    plot_distribution(counts, args.output)
    print(f"Saved chart with {len(counts)} months to {args.output}")


if __name__ == "__main__":
    main()
