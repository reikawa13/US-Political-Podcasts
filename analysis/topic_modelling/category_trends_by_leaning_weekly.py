#!/usr/bin/env python3
"""Count thesis categories over time by political leaning (weekly).

Inputs:
  - sentence_topics_remapped.csv (needs ID + thesis_categories)
  - podMetadata_Nov5_with_leaning.csv (needs ID + date + political_leaning)

Output:
  - topic_modelling/category_counts_weekly/category_counts_by_leaning_timeseries_weekly.csv
    Columns: date, political_leaning, thesis_category, count
  - topic_modelling/category_counts_weekly/category_plots_by_leaning/<category>.png (when --plot is set)
  - topic_modelling/category_counts_weekly/category_plots_by_leaning/all_categories.png (when --plot is set)
  - topic_modelling/category_counts_weekly/category_plots_totals/<category>.png (when --plot is set)
  - topic_modelling/category_counts_weekly/category_plots_totals/all_categories.png (when --plot is set)
"""
# Usage: python3 category_trends_by_leaning_weekly.py --plot --start-date 2023-01-01 --end-date 2024-11-05
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Tuple

DEFAULT_SENTENCE_CSV = Path("sentence_topics_remapped.csv")
DEFAULT_META_CSV = Path("podMetadata_Nov5_with_leaning.csv")
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = SCRIPT_DIR / "category_counts_weekly"
DEFAULT_OUT_CSV = DEFAULT_OUT_DIR / "category_counts_by_leaning_timeseries_weekly.csv"
DEFAULT_PLOT_DIR = DEFAULT_OUT_DIR / "category_plots_by_leaning"
DEFAULT_TOTAL_PLOT_DIR = DEFAULT_OUT_DIR / "category_plots_totals"
DEFAULT_MISSING_META_CSV = DEFAULT_OUT_DIR / "sentences_missing_metadata.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count thesis categories over time by political leaning (weekly)."
    )
    parser.add_argument("--sentences", type=Path, default=DEFAULT_SENTENCE_CSV)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument(
        "--start-date",
        default="2023-01-01",
        help="Earliest date to include (YYYY-MM-DD). Use empty to disable.",
    )
    parser.add_argument(
        "--end-date",
        default="2024-11-05",
        help="Latest date to include (YYYY-MM-DD). Use empty to disable.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Also write per-category trajectory plots as PNG files.",
    )
    parser.add_argument(
        "--plot-dir",
        type=Path,
        default=DEFAULT_PLOT_DIR,
        help="Directory to write plots when --plot is set.",
    )
    parser.add_argument(
        "--total-plot-dir",
        type=Path,
        default=DEFAULT_TOTAL_PLOT_DIR,
        help="Directory to write total (all-leaning) plots when --plot is set.",
    )
    parser.add_argument(
        "--category-column",
        type=str,
        default="thesis_categories",
        help="Column containing mapped categories (pipe-delimited).",
    )
    parser.add_argument(
        "--category-sep",
        type=str,
        default="|",
        help="Separator used between multiple categories.",
    )
    parser.add_argument(
        "--missing-meta-csv",
        type=Path,
        default=DEFAULT_MISSING_META_CSV,
        help="Write rows with missing metadata to this CSV.",
    )
    return parser.parse_args()


def parse_date_to_week_start(value: str) -> datetime:
    dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    monday = dt.date() - timedelta(days=dt.weekday())
    return datetime.combine(monday, datetime.min.time(), tzinfo=timezone.utc)


def load_metadata(
    path: Path, start_date: datetime | None, end_date: datetime | None
) -> Dict[str, Tuple[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {path}")
    mapping: Dict[str, Tuple[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"ID", "date", "political_leaning"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                "Metadata CSV must include ID, date, and political_leaning columns."
            )
        for row in reader:
            episode_id = (row.get("ID") or "").strip()
            date_raw = (row.get("date") or "").strip()
            leaning = (row.get("political_leaning") or "").strip()
            if not episode_id or not date_raw or not leaning:
                continue
            try:
                week_start = parse_date_to_week_start(date_raw)
            except (TypeError, ValueError):
                continue
            if start_date is not None and week_start < start_date:
                continue
            if end_date is not None and week_start > end_date:
                continue
            mapping[episode_id] = (week_start.date().isoformat(), leaning)
    if not mapping:
        raise SystemExit("No usable rows found in metadata CSV.")
    return mapping


def iter_sentence_rows(path: Path) -> Iterator[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Sentence topics CSV not found: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "ID" not in reader.fieldnames:
            raise ValueError("Sentence topics CSV must include an ID column.")
        for row in reader:
            yield row


def split_categories(value: str, sep: str) -> List[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.split(sep)]
    return [p for p in parts if p]


def count_categories(
    sentence_rows: Iterable[Dict[str, str]],
    meta_map: Dict[str, Tuple[str, str]],
    category_column: str,
    category_sep: str,
) -> Tuple[Counter[Tuple[str, str, str]], List[Dict[str, str]]]:
    counts: Counter[Tuple[str, str, str]] = Counter()
    missing_meta = 0
    missing_rows: List[Dict[str, str]] = []
    for row in sentence_rows:
        episode_id = (row.get("ID") or "").strip()
        if not episode_id or episode_id not in meta_map:
            missing_meta += 1
            missing_rows.append(row)
            continue
        week_start, leaning = meta_map[episode_id]
        categories = split_categories(row.get(category_column, ""), category_sep)
        if not categories:
            continue
        for category in categories:
            counts[(week_start, leaning, category)] += 1
    if not counts:
        raise SystemExit(
            "No category counts produced. Check category column and metadata join."
        )
    if missing_meta:
        print(f"Rows skipped due to missing metadata: {missing_meta}")
    return counts, missing_rows


def write_missing_rows(path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved missing-metadata rows to: {path}")


def write_counts(path: Path, counts: Counter[Tuple[str, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"date": d, "political_leaning": l, "thesis_category": c, "count": n}
        for (d, l, c), n in counts.items()
    ]
    rows.sort(key=lambda r: (r["date"], r["political_leaning"], r["thesis_category"]))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["date", "political_leaning", "thesis_category", "count"]
        )
        writer.writeheader()
        writer.writerows(rows)


def slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def plot_counts(
    counts: Counter[Tuple[str, str, str]],
    plot_dir: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.ticker import MaxNLocator
    except Exception as exc:  # pragma: no cover - best effort plotting
        raise SystemExit(f"Plotting requested but matplotlib is unavailable: {exc}")

    plot_dir.mkdir(parents=True, exist_ok=True)

    categories = sorted({c for (_, _, c) in counts.keys()})
    categories = [
        c for c in categories if c.strip().lower() not in {"unknown", "unmapped"}
    ]
    found_leanings = {l for (_, l, _) in counts.keys()}
    preferred_leanings = ["Liberal", "Moderate", "Conservative"]
    leanings = [l for l in preferred_leanings if l in found_leanings] + sorted(
        found_leanings - set(preferred_leanings)
    )

    # Precompute all dates to align trajectories.
    all_date_strs = sorted({d for (d, _, _) in counts.keys()})
    all_dates = [datetime.fromisoformat(d) for d in all_date_strs]

    totals_by_date_category: Counter[Tuple[str, str]] = Counter()
    for (d, _leaning, category), value in counts.items():
        totals_by_date_category[(d, category)] += value

    # Keep colors consistent so the legend is meaningful across all plots.
    leaning_colors = {
        "Liberal": "#1f77b4",
        "Moderate": "#2ca02c",
        "Conservative": "#d62728",
    }

    def style_time_axis(ax) -> None:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.tick_params(axis="x", which="both", labelbottom=True, rotation=45, labelsize=7)
        ax.tick_params(axis="y", labelsize=9)

    # Combined page: add an "All leanings" column next to each leaning.
    if categories and leanings:
        lean_global_max = max(
            (counts.get((d, leaning, category), 0)
             for d in all_date_strs
             for leaning in leanings
             for category in categories),
            default=0,
        )
        total_global_max = max(
            (totals_by_date_category.get((d, category), 0)
             for d in all_date_strs
             for category in categories),
            default=0,
        )
        global_ymax = max(lean_global_max, total_global_max)
        global_ymax = (global_ymax * 1.05) if global_ymax else 1
        nrows = len(categories)
        ncols = len(leanings) + 1
        fig, axes = plt.subplots(
            nrows=nrows,
            ncols=ncols,
            figsize=(ncols * 3.8, nrows * 2.3),
            sharex=True,
            sharey=False,
        )
        axes_list = list(axes.flat) if hasattr(axes, "flat") else [axes]
        for r, category in enumerate(categories):
            for c, leaning in enumerate(leanings):
                ax = (
                    axes[r][c]
                    if nrows > 1 and ncols > 1
                    else axes_list[r * ncols + c]
                )
                y = [counts.get((d, leaning, category), 0) for d in all_date_strs]
                ax.plot(all_dates, y, color=leaning_colors.get(leaning))
                if r == 0:
                    ax.set_title(leaning)
                if c == 0:
                    ax.set_ylabel(category)
                style_time_axis(ax)
                ax.set_ylim(0, global_ymax)

            total_c = ncols - 1
            total_ax = (
                axes[r][total_c]
                if nrows > 1 and ncols > 1
                else axes_list[r * ncols + total_c]
            )
            total_y = [
                totals_by_date_category.get((d, category), 0) for d in all_date_strs
            ]
            total_ax.plot(all_dates, total_y, color="#444444")
            if r == 0:
                total_ax.set_title("All leanings")
            style_time_axis(total_ax)
            total_ax.set_ylim(0, global_ymax)

        fig.tight_layout()
        fig.savefig(plot_dir / "all_categories.png", dpi=150)
        plt.close(fig)

    # Also save per-category figures for detailed inspection.
    for category in categories:
        ncols = len(leanings) + 1
        fig, axes = plt.subplots(
            nrows=1,
            ncols=ncols,
            figsize=(ncols * 4.0, 3.2),
            sharex=True,
            sharey=False,
        )
        axes_list = list(axes.flat) if hasattr(axes, "flat") else [axes]
        lean_category_max = max(
            (
                counts.get((d, leaning, category), 0)
                for d in all_date_strs
                for leaning in leanings
            ),
            default=0,
        )
        total_category_max = max(
            (totals_by_date_category.get((d, category), 0) for d in all_date_strs),
            default=0,
        )
        category_ymax = max(lean_category_max, total_category_max)
        category_ymax = (category_ymax * 1.05) if category_ymax else 1
        for ax, leaning in zip(axes_list, leanings):
            y = [counts.get((d, leaning, category), 0) for d in all_date_strs]
            ax.plot(all_dates, y, color=leaning_colors.get(leaning), label=leaning)
            ax.set_title(leaning)
            ax.legend(loc="upper right")
            style_time_axis(ax)
            ax.set_ylim(0, category_ymax)
        total_ax = axes_list[-1]
        total_y = [totals_by_date_category.get((d, category), 0) for d in all_date_strs]
        total_ax.plot(all_dates, total_y, color="#444444", label="All leanings")
        total_ax.set_title("All leanings")
        total_ax.legend(loc="upper right")
        style_time_axis(total_ax)
        total_ax.set_ylim(0, category_ymax)
        axes_list[0].set_ylabel("count")
        fig.suptitle(f"{category} over time", y=1.02)
        fig.tight_layout()
        out_path = plot_dir / f"{slugify(category)}.png"
        fig.savefig(out_path, dpi=150)
        plt.close(fig)


def collapse_leanings(
    counts: Counter[Tuple[str, str, str]]
) -> Counter[Tuple[str, str]]:
    totals: Counter[Tuple[str, str]] = Counter()
    for (date_day, _leaning, category), value in counts.items():
        totals[(date_day, category)] += value
    return totals


def plot_total_counts(
    totals: Counter[Tuple[str, str]],
    plot_dir: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.ticker import MaxNLocator
    except Exception as exc:  # pragma: no cover - best effort plotting
        raise SystemExit(f"Plotting requested but matplotlib is unavailable: {exc}")

    plot_dir.mkdir(parents=True, exist_ok=True)

    categories = sorted({c for (_, c) in totals.keys()})
    all_date_strs = sorted({d for (d, _) in totals.keys()})
    all_dates = [datetime.fromisoformat(d) for d in all_date_strs]

    global_max = max(totals.values()) if totals else 0
    y_max = global_max * 1.05 if global_max else 1

    def style_time_axis(ax, ymax: float) -> None:
        ax.set_ylim(0, ymax)
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.tick_params(axis="x", which="both", labelbottom=True, rotation=45, labelsize=7)
        ax.tick_params(axis="y", labelsize=9)

    # Combined totals page.
    if categories:
        nrows = len(categories)
        fig, axes = plt.subplots(
            nrows=nrows,
            ncols=1,
            figsize=(10, 2.4 * nrows),
            sharex=True,
            sharey=True,
        )
        axes_list = list(axes.flat) if hasattr(axes, "flat") else [axes]
        for ax, category in zip(axes_list, categories):
            y = [totals.get((d, category), 0) for d in all_date_strs]
            ax.plot(all_dates, y, color="#444444")
            ax.set_title(category)
            style_time_axis(ax, y_max)
        axes_list[-1].set_xlabel("date")
        axes_list[0].set_ylabel("count")
        fig.tight_layout()
        fig.savefig(plot_dir / "all_categories.png", dpi=150)
        plt.close(fig)

    # Per-category totals.
    for category in categories:
        fig, ax = plt.subplots(figsize=(10, 3.2))
        y = [totals.get((d, category), 0) for d in all_date_strs]
        category_max = max(y) if y else 0
        category_ymax = category_max * 1.05 if category_max else 1
        ax.plot(all_dates, y, color="#444444", label="All leanings")
        ax.set_title(f"{category} over time (all leanings)")
        ax.set_xlabel("date")
        ax.set_ylabel("count")
        ax.legend(loc="upper right")
        style_time_axis(ax, category_ymax)
        fig.tight_layout()
        fig.savefig(plot_dir / f"{slugify(category)}.png", dpi=150)
        plt.close(fig)


def main() -> None:
    args = parse_args()
    start_date = (
        datetime.fromisoformat(args.start_date).replace(tzinfo=timezone.utc)
        if args.start_date
        else None
    )
    end_date = (
        datetime.fromisoformat(args.end_date).replace(tzinfo=timezone.utc)
        if args.end_date
        else None
    )
    meta_map = load_metadata(args.metadata, start_date, end_date)
    sentence_rows = list(iter_sentence_rows(args.sentences))
    counts, missing_rows = count_categories(
        sentence_rows, meta_map, args.category_column, args.category_sep
    )
    write_counts(args.output_csv, counts)
    print(f"Saved category counts to: {args.output_csv}")
    write_missing_rows(args.missing_meta_csv, missing_rows)
    if args.plot:
        plot_counts(counts, args.plot_dir)
        print(f"Saved category plots to: {args.plot_dir}")
        totals = collapse_leanings(counts)
        plot_total_counts(totals, args.total_plot_dir)
        print(f"Saved total category plots to: {args.total_plot_dir}")


if __name__ == "__main__":
    main()
