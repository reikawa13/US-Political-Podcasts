#!/usr/bin/env python3
"""Plot weekly total category counts with one panel per category."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_COUNTS_CSV = (
    SCRIPT_DIR / "category_counts_weekly" / "category_counts_by_leaning_timeseries_weekly.csv"
)
DEFAULT_OUT_PNG = (
    SCRIPT_DIR / "category_emotion_plots_totals" / "counts_only" / "all_categories.png"
)
REFERENCE_DATES = [
    datetime(2024, 2, 20),
    datetime(2024, 9, 10),
]


def load_counts(path: Path) -> Counter[tuple[str, str, str]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = (row.get("date") or "").strip()
            leaning = (row.get("political_leaning") or "").strip()
            category = (row.get("thesis_category") or "").strip()
            raw_count = (row.get("count") or "").strip()
            if not date or not category or not raw_count:
                continue
            counts[(date, leaning, category)] += int(raw_count)
    return counts


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    counts = load_counts(DEFAULT_COUNTS_CSV)
    categories = sorted({c for (_, _, c) in counts.keys()})
    categories = [c for c in categories if c.strip().lower() not in {"unknown", "unmapped"}]
    leanings = sorted({l for (_, l, _) in counts.keys()})
    all_date_strs = sorted({d for (d, _, _) in counts.keys()})
    all_dates = [datetime.fromisoformat(d) for d in all_date_strs]

    def total_count(date: str, category: str) -> int:
        return sum(counts.get((date, leaning, category), 0) for leaning in leanings)

    def style_time_axis(ax) -> None:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.tick_params(axis="x", which="both", labelbottom=True, rotation=45, labelsize=7)
        ax.tick_params(axis="y", labelsize=9)

    fig, axes = plt.subplots(
        nrows=len(categories),
        ncols=1,
        figsize=(10, max(2.4 * len(categories), 8)),
        sharex=True,
    )
    axes_list = list(axes.flat) if hasattr(axes, "flat") else [axes]

    for ax, category in zip(axes_list, categories):
        series = [total_count(d, category) for d in all_date_strs]
        ymax = max(series) * 1.05 if series and max(series) else 1
        ax.plot(all_dates, series, color="#000000", linewidth=1.3)
        for ref_date in REFERENCE_DATES:
            ax.axvline(ref_date, color="#ffd700", linewidth=1.5, alpha=0.95)
        ax.set_ylim(0, ymax)
        ax.set_ylabel(category)
        style_time_axis(ax)

    fig.tight_layout()
    DEFAULT_OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(DEFAULT_OUT_PNG, dpi=150)
    plt.close(fig)
    print(f"Wrote counts-only plot to {DEFAULT_OUT_PNG}")


if __name__ == "__main__":
    main()
