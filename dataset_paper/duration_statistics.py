#!/usr/bin/env python3
"""Compute descriptive statistics for episode durations.

Replicates the summary reported earlier (sum, mean, median, standard deviation,
min, max) when pointed at the Nov 5 metadata CSV.  The script converts the
`duration` column to numeric values, ignores any missing/invalid entries, and
prints the resulting statistics with clear labels.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DEFAULT_INPUT = "podMetadata_Nov5_with_leaning.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate summary statistics for the `duration` column."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT),
        help="CSV file to read (default: %(default)s).",
    )
    return parser.parse_args()


def format_episode_row(row: pd.Series) -> str:
    pod = row.get("podName", "")
    title = row.get("title", "")
    duration = row["duration"]
    return f"{pod[:40]:40} | {title[:45]:45} | {duration:8.0f} sec"


def format_series_row(name: str, avg_duration: float, count: int) -> str:
    return f"{name[:40]:40} | {avg_duration:8.2f} sec | {count:5d} eps"


def main() -> None:
    args = parse_args()
    csv_path = args.input
    if not csv_path.exists():
        raise FileNotFoundError(f"Input file not found: {csv_path}")

    df = pd.read_csv(
        csv_path, usecols=["duration", "podName", "title", "ID", "date"]
    )
    df["duration"] = pd.to_numeric(df["duration"], errors="coerce")
    df = df.dropna(subset=["duration"])
    durations = df["duration"]
    if durations.empty:
        raise ValueError("No numeric duration values found in the CSV.")

    stats = {
        "sum": durations.sum(),
        "mean": durations.mean(),
        "median": durations.median(),
        "std_dev": durations.std(ddof=1),
        "min": durations.min(),
        "max": durations.max(),
    }

    print(f"Count of episodes included: {len(durations)}")
    print(f"Sum of all durations: {stats['sum']:.0f}")
    print(f"Average duration: {stats['mean']:.2f}")
    print(f"Median duration: {stats['median']:.0f}")
    print(f"Standard deviation: {stats['std_dev']:.2f}")
    print(f"Shortest duration: {stats['min']:.0f}")
    print(f"Longest duration: {stats['max']:.0f}")

    top_episodes = df.nlargest(10, "duration")
    bottom_episodes = df.nsmallest(10, "duration")

    print("\nTop 10 episodes by duration:")
    for _, row in top_episodes.iterrows():
        print("  " + format_episode_row(row))

    print("\nBottom 10 episodes by duration:")
    for _, row in bottom_episodes.iterrows():
        print("  " + format_episode_row(row))

    series_summary = (
        df.groupby("podName")["duration"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "avg_duration", "count": "episode_count"})
    )
    series_avg = series_summary["avg_duration"]

    avg_stats = {
        "mean_of_means": series_avg.mean(),
        "median_of_means": series_avg.median(),
        "shortest_avg": series_avg.min(),
        "longest_avg": series_avg.max(),
    }

    print("\nSeries average duration stats:")
    print(f"  Mean of averages   : {avg_stats['mean_of_means']:.2f}")
    print(f"  Median of averages : {avg_stats['median_of_means']:.2f}")
    print(f"  Shortest average   : {avg_stats['shortest_avg']:.2f}")
    print(f"  Longest average    : {avg_stats['longest_avg']:.2f}")
    top_series = series_summary.sort_values(
        "avg_duration", ascending=False
    ).head(10)
    bottom_series = series_summary.sort_values(
        "avg_duration", ascending=True
    ).head(10)

    print("\nTop 10 series by average episode duration:")
    for name, row in top_series.iterrows():
        print(
            "  "
            + format_series_row(
                name, row["avg_duration"], int(row["episode_count"])
            )
        )

    print("\nBottom 10 series by average episode duration:")
    for name, row in bottom_series.iterrows():
        print(
            "  "
            + format_series_row(
                name, row["avg_duration"], int(row["episode_count"])
            )
        )


if __name__ == "__main__":
    main()
