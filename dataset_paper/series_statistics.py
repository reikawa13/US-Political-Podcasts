from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from statistics import mean, stdev
from typing import List


DATA_PATH = Path("podMetadata_Nov5_with_leaning.csv")
BAR_CHART_PATH = Path("episode_counts_top20.svg")


@dataclass
class SeriesRecord:
    oldest_date: datetime
    episode_count: int


def parse_date(raw: str) -> datetime | None:
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    # Ensure timezone-aware values for averaging.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def load_series_records(path: Path) -> dict[str, SeriesRecord]:
    records: dict[str, SeriesRecord] = {}
    with path.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            pod_name = row.get("podName")
            date = parse_date(row.get("date", ""))
            if not pod_name or date is None:
                continue

            if pod_name not in records:
                records[pod_name] = SeriesRecord(oldest_date=date, episode_count=1)
            else:
                record = records[pod_name]
                record.episode_count += 1
                if date < record.oldest_date:
                    record.oldest_date = date
    return records


def average_datetime(dates: List[datetime]) -> datetime:
    timestamps = [dt.timestamp() for dt in dates]
    avg_timestamp = mean(timestamps)
    return datetime.fromtimestamp(avg_timestamp, tz=timezone.utc)


def describe_oldest_dates(records: dict[str, SeriesRecord]) -> dict[str, datetime]:
    dates = [record.oldest_date for record in records.values()]
    return {
        "oldest": min(dates),
        "newest": max(dates),
        "mean": average_datetime(dates),
    }


def describe_episode_counts(records: dict[str, SeriesRecord]) -> dict[str, float]:
    counts = [record.episode_count for record in records.values()]
    std_value = stdev(counts) if len(counts) > 1 else 0.0
    return {
        "max": max(counts),
        "min": min(counts),
        "mean": mean(counts),
        "std": std_value,
    }


def plot_episode_counts(
    records: dict[str, SeriesRecord], output_path: Path, top_n: int = 20
) -> None:
    """Save a lightweight SVG bar chart of the most prolific series."""
    sorted_records = sorted(
        records.items(), key=lambda item: item[1].episode_count, reverse=True
    )[:top_n]
    names = [name for name, _ in sorted_records]
    counts = [record.episode_count for _, record in sorted_records]

    max_count = max(counts) if counts else 1
    width, height = 900, 40 + 30 * len(names)
    chart_width = width - 250
    y_start = 30
    bar_height = 18
    spacing = 30

    lines = [
        f'<svg width="{width}" height="{height}" '
        'xmlns="http://www.w3.org/2000/svg" '
        'font-family="Arial, sans-serif">',
        f'<text x="{width / 2}" y="20" text-anchor="middle" '
        'font-size="18">Top Series by Episode Count</text>',
    ]

    for idx, (name, count) in enumerate(zip(names, counts)):
        y = y_start + idx * spacing
        bar_width = (count / max_count) * chart_width
        lines.append(
            f'<rect x="180" y="{y}" width="{bar_width:.2f}" height="{bar_height}" '
            'fill="#4C72B0" />'
        )
        lines.append(
            f'<text x="10" y="{y + bar_height - 4}" font-size="12">{name}</text>'
        )
        lines.append(
            f'<text x="{180 + bar_width + 10}" y="{y + bar_height - 4}" '
            'font-size="12">{count}</text>'
        )

    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def render_top_twenty(records: dict[str, SeriesRecord], *, ascending: bool) -> str:
    header = f"{'Podcast':40} {'Oldest Episode Date':20} {'Episode Count':14}"
    lines = [header, "-" * len(header)]
    sorted_records = sorted(
        records.items(), key=lambda item: item[1].oldest_date, reverse=not ascending
    )[:20]

    for name, record in sorted_records:
        date_str = record.oldest_date.strftime("%Y-%m-%d")
        lines.append(f"{name[:38]:40} {date_str:20} {record.episode_count:14}")
    return "\n".join(lines)


def main() -> None:
    records = load_series_records(DATA_PATH)
    if not records:
        raise SystemExit("No valid series records found.")

    oldest_stats = describe_oldest_dates(records)
    count_stats = describe_episode_counts(records)

    print("Oldest episode date stats:")
    for label, value in oldest_stats.items():
        print(f"  {label.title():<7}: {value.date()}")

    print("\nEpisode count stats:")
    for label, value in count_stats.items():
        if label in {"max", "min"}:
            formatted = f"{int(value)}"
        else:
            formatted = f"{value:.2f}"
        print(f"  {label.title():<7}: {formatted}")

    print("\nTop 20 series by oldest episode date (latest first):")
    print(render_top_twenty(records, ascending=False))

    print("\nTop 20 series by earliest oldest episode date:")
    print(render_top_twenty(records, ascending=True))

    plot_episode_counts(records, BAR_CHART_PATH)
    print(f"\nSaved bar chart of episode counts to {BAR_CHART_PATH}")


if __name__ == "__main__":
    main()
