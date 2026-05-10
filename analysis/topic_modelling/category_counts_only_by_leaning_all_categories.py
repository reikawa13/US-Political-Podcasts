#!/usr/bin/env python3
"""Plot weekly category counts by leaning with one row per category."""

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
    SCRIPT_DIR / "category_emotion_plots_by_leaning" / "counts_only" / "all_categories.png"
)
REFERENCE_DATES = [
    datetime(2024, 2, 20),
    datetime(2024, 9, 10),
]
PREFERRED_LEANINGS = ["Liberal", "Moderate", "Conservative"]


def load_counts(path: Path) -> Counter[tuple[str, str, str]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = (row.get("date") or "").strip()
            leaning = (row.get("political_leaning") or "").strip()
            category = (row.get("thesis_category") or "").strip()
            raw_count = (row.get("count") or "").strip()
            if not date or not leaning or not category or not raw_count:
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
    found_leanings = {l for (_, l, _) in counts.keys()}
    leanings = [l for l in PREFERRED_LEANINGS if l in found_leanings] + sorted(
        found_leanings - set(PREFERRED_LEANINGS)
    )
    all_date_strs = sorted({d for (d, _, _) in counts.keys()})
    all_dates = [datetime.fromisoformat(d) for d in all_date_strs]

    def style_time_axis(ax) -> None:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.tick_params(axis="x", which="both", labelbottom=True, rotation=45, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)

    fig, axes = plt.subplots(
        nrows=len(categories),
        ncols=len(leanings),
        figsize=(4.2 * len(leanings), max(2.4 * len(categories), 8)),
        sharex=True,
        sharey=False,
    )

    if len(categories) == 1 and len(leanings) == 1:
        axes_grid = [[axes]]
    elif len(categories) == 1:
        axes_grid = [list(axes)]
    elif len(leanings) == 1:
        axes_grid = [[ax] for ax in axes]
    else:
        axes_grid = axes

    for row_index, category in enumerate(categories):
        for col_index, leaning in enumerate(leanings):
            ax = axes_grid[row_index][col_index]
            series = [counts.get((d, leaning, category), 0) for d in all_date_strs]
            category_max = max(
                (
                    counts.get((d, candidate_leaning, category), 0)
                    for d in all_date_strs
                    for candidate_leaning in leanings
                ),
                default=0,
            )
            ymax = category_max * 1.05 if category_max else 1
            ax.plot(all_dates, series, color="#000000", linewidth=1.2)
            for ref_date in REFERENCE_DATES:
                ax.axvline(ref_date, color="#ffd700", linewidth=1.4, alpha=0.95)
            ax.set_ylim(0, ymax)
            style_time_axis(ax)
            if row_index == 0:
                ax.set_title(leaning)
            if col_index == 0:
                ax.set_ylabel(category)

    fig.tight_layout()
    DEFAULT_OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(DEFAULT_OUT_PNG, dpi=150)
    plt.close(fig)
    print(f"Wrote counts-only by-leaning plot to {DEFAULT_OUT_PNG}")


if __name__ == "__main__":
    main()
