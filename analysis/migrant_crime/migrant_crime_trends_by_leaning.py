#!/usr/bin/env python3
"""Aggregate migrant crime counts over time by political leaning and plot trends."""
# Usage: python3 analysis/migrant_crime_trends_by_leaning.py --start-date 2023-01-01 --freq W
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import sys


def parse_date(value: str) -> datetime:
    value = (value or "").strip()
    if not value:
        raise ValueError("empty date")
    try:
        dt = parsedate_to_datetime(value)
        if dt is not None:
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
    except Exception:
        pass
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {value}")


def period_key(dt: datetime, freq: str) -> datetime:
    if freq == "D":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if freq == "W":
        monday = dt - timedelta(days=dt.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)
    if freq == "M":
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if freq == "Q":
        month = ((dt.month - 1) // 3) * 3 + 1
        return dt.replace(month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
    if freq == "Y":
        return dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"Unsupported freq: {freq}")


def format_period(dt: datetime, freq: str) -> str:
    if freq == "D":
        return dt.strftime("%Y-%m-%d")
    if freq == "W":
        return dt.strftime("%Y-%m-%d")
    if freq == "M":
        return dt.strftime("%Y-%m")
    if freq == "Q":
        q = ((dt.month - 1) // 3) + 1
        return f"{dt.year}-Q{q}"
    if freq == "Y":
        return dt.strftime("%Y")
    return dt.isoformat()


def load_metadata_dates(path: Path) -> dict[str, str]:
    meta_dates: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = row.get("ID")
            if not rid:
                continue
            meta_dates[rid] = row.get("date", "") or ""
    return meta_dates


def aggregate_counts(
    counts_path: Path,
    meta_dates: dict[str, str],
    freq: str,
    count_column: str,
    year: int | None,
    start_date: datetime | None,
) -> tuple[dict[str, dict[datetime, int]], set[datetime]]:
    totals: dict[str, dict[datetime, int]] = defaultdict(lambda: defaultdict(int))
    periods: set[datetime] = set()

    with counts_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "political_leaning" not in reader.fieldnames:
            raise ValueError("counts file is missing required column: political_leaning")
        if count_column not in reader.fieldnames:
            raise ValueError(f"counts file is missing required column: {count_column}")
        for row in reader:
            leaning = (row.get("political_leaning") or "").strip()
            if not leaning:
                continue
            rid = row.get("ID")
            if not rid:
                continue
            date_str = meta_dates.get(rid, "")
            try:
                dt = parse_date(date_str)
            except ValueError:
                continue
            if year is not None and dt.year != year:
                continue
            if start_date is not None and dt < start_date:
                continue
            try:
                count = int(float(row.get(count_column, 0) or 0))
            except ValueError:
                count = 0
            key = period_key(dt, freq)
            totals[leaning][key] += count
            periods.add(key)

    return totals, periods


def write_timeseries(
    path: Path, totals: dict[str, dict[datetime, int]], periods: list[datetime], freq: str
) -> None:
    columns = ["period"] + ["Liberal", "Moderate", "Conservative"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for p in periods:
            row = {
                "period": format_period(p, freq),
                "Liberal": totals.get("Liberal", {}).get(p, 0),
                "Moderate": totals.get("Moderate", {}).get(p, 0),
                "Conservative": totals.get("Conservative", {}).get(p, 0),
            }
            writer.writerow(row)


def plot_timeseries(
    path: Path, totals: dict[str, dict[datetime, int]], periods: list[datetime], freq: str
) -> None:
    try:
        import matplotlib.pyplot as plt
        from matplotlib.ticker import MaxNLocator, MultipleLocator
    except Exception:
        print(
            "matplotlib is required to render the plot. Install it or use --no-plot.",
            file=sys.stderr,
        )
        raise

    x_labels = [format_period(p, freq) for p in periods]
    x = list(range(len(x_labels)))

    plt.figure(figsize=(12, 6))
    for leaning, color in [
        ("Liberal", "#1f77b4"),
        ("Moderate", "#2ca02c"),
        ("Conservative", "#d62728"),
    ]:
        y = [totals.get(leaning, {}).get(p, 0) for p in periods]
        plt.plot(x, y, label=leaning, color=color, linewidth=2)

    plt.title("Migrant Crime Phrase Counts Over Time by Political Leaning")
    x_label = {
        "D": "Day",
        "W": "Week",
        "M": "Month",
        "Q": "Quarter",
        "Y": "Year",
    }.get(freq, "Period")
    plt.xlabel(x_label)
    plt.ylabel("Total Phrase Hits")
    ax = plt.gca()
    ax.yaxis.set_major_locator(MaxNLocator(nbins=15, integer=True))
    ax.yaxis.set_minor_locator(MultipleLocator(1))
    if x_labels:
        tick_positions = list(range(len(x_labels)))
        tick_labels = [x_labels[i] for i in tick_positions]
        plt.xticks(tick_positions, tick_labels, rotation=60, ha="right", fontsize=7)
    ax.grid(True, which="major", axis="y", linestyle="-", linewidth=0.6, alpha=0.35)
    ax.grid(True, which="minor", axis="y", linestyle="-", linewidth=0.4, alpha=0.25)
    ax.grid(True, which="minor", axis="x", linestyle="-", linewidth=0.4, alpha=0.2)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=200)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate migrant crime counts by political leaning over time."
    )
    parser.add_argument(
        "--counts",
        default="analysis/migrant_crime_counts_by_episode_overall.csv",
        help="Migrant crime counts CSV",
    )
    parser.add_argument(
        "--count-column",
        default="migrant_crime",
        help="Column to aggregate from counts CSV",
    )
    parser.add_argument(
        "--freq",
        default="W",
        choices=["D", "W", "M", "Q", "Y"],
        help="Aggregation frequency",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Filter to a single calendar year (e.g., 2024).",
    )
    parser.add_argument(
        "--start-date",
        default="2023-01-01",
        help="Earliest date to include (YYYY-MM-DD). Use an empty value to disable.",
    )
    parser.add_argument(
        "--metadata",
        default="podMetadata_Nov5_with_leaning.csv",
        help="Episode metadata CSV (for dates)",
    )
    parser.add_argument(
        "--out-csv",
        default="analysis/migrant_crime_counts_by_leaning_timeseries.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--out-plot",
        default="analysis/migrant_crime_counts_by_leaning_trend.png",
        help="Output plot path",
    )
    parser.add_argument("--no-plot", action="store_true", help="Skip plot generation")

    args = parser.parse_args()

    counts_path = Path(args.counts)
    metadata_path = Path(args.metadata)
    if not counts_path.exists():
        print(f"Missing counts file: {counts_path}", file=sys.stderr)
        return 1
    if not metadata_path.exists():
        print(f"Missing metadata file: {metadata_path}", file=sys.stderr)
        return 1

    try:
        meta_dates = load_metadata_dates(metadata_path)
        start_date = None
        if args.start_date and args.start_date.strip():
            start_date = parse_date(args.start_date)
        totals, period_set = aggregate_counts(
            counts_path,
            meta_dates,
            args.freq,
            args.count_column,
            args.year,
            start_date,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    periods = sorted(period_set)

    if not periods:
        print("No data matched between counts and metadata.", file=sys.stderr)
        return 1

    out_csv = Path(args.out_csv)
    write_timeseries(out_csv, totals, periods, args.freq)

    if not args.no_plot:
        out_plot = Path(args.out_plot)
        plot_timeseries(out_plot, totals, periods, args.freq)

    print(f"Wrote {out_csv}")
    if not args.no_plot:
        print(f"Wrote {args.out_plot}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
