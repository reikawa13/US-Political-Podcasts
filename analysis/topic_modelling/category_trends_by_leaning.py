#!/usr/bin/env python3
"""Count thesis categories over time by political leaning.

Inputs:
  - sentence_topics_remapped.csv (needs ID + thesis_categories)
  - podMetadata_Nov5_with_leaning.csv (needs ID + date + political_leaning)

Output:
  - analysis/category_counts_by_leaning_timeseries.csv
    Columns: date, political_leaning, thesis_category, count
  - analysis/category_plots/<category>.png (when --plot is set)
  - analysis/category_plots/all_categories.png (when --plot is set)
  - analysis/category_plots_totals/<category>.png (when --plot is set)
  - analysis/category_plots_totals/all_categories.png (when --plot is set)
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Tuple

DEFAULT_SENTENCE_CSV = Path("sentence_topics_remapped.csv")
DEFAULT_META_CSV = Path("podMetadata_Nov5_with_leaning.csv")
DEFAULT_OUT_CSV = Path("new/category_counts_by_leaning_timeseries.csv")
DEFAULT_PLOT_DIR = Path("new/category_plots")
DEFAULT_TOTAL_PLOT_DIR = Path("new/category_plots_totals")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count thesis categories over time by political leaning."
    )
    parser.add_argument("--sentences", type=Path, default=DEFAULT_SENTENCE_CSV)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUT_CSV)
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
    return parser.parse_args()


def parse_date_to_day(value: str) -> str:
    dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.date().isoformat()


def load_metadata(path: Path) -> Dict[str, Tuple[str, str]]:
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
                date_day = parse_date_to_day(date_raw)
            except (TypeError, ValueError):
                continue
            mapping[episode_id] = (date_day, leaning)
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
) -> Counter[Tuple[str, str, str]]:
    counts: Counter[Tuple[str, str, str]] = Counter()
    missing_meta = 0
    for row in sentence_rows:
        episode_id = (row.get("ID") or "").strip()
        if not episode_id or episode_id not in meta_map:
            missing_meta += 1
            continue
        date_day, leaning = meta_map[episode_id]
        categories = split_categories(row.get(category_column, ""), category_sep)
        if not categories:
            continue
        for category in categories:
            counts[(date_day, leaning, category)] += 1
    if not counts:
        raise SystemExit(
            "No category counts produced. Check category column and metadata join."
        )
    if missing_meta:
        print(f"Rows skipped due to missing metadata: {missing_meta}")
    return counts


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
        "Liberal": "#1f77b4",       # blue
        "Moderate": "#2ca02c",      # green
        "Conservative": "#d62728",  # red
    }

    def style_time_axis(ax) -> None:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        # Force x labels to show on every subplot even with shared x-axes.
        ax.tick_params(axis="x", which="both", labelbottom=True, rotation=45, labelsize=7)
        ax.tick_params(axis="y", labelsize=9)

    def category_leaning_max(category: str) -> int:
        return max(
            (
                counts.get((d, leaning, category), 0)
                for d in all_date_strs
                for leaning in leanings
            ),
            default=0,
        )

    # Combined page: add an "All leanings" column next to each leaning.
    if categories and leanings:
        # One shared y-scale for all panels across categories and leanings.
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
            # Leaning-specific panels.
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

            # Total (all-leanings) panel at the end of the row.
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
        lean_global_max = max(
            (counts.get((d, leaning, c), 0)
             for d in all_date_strs
             for leaning in leanings
             for c in categories),
            default=0,
        )
        total_global_max = max(
            (totals_by_date_category.get((d, c), 0)
             for d in all_date_strs
             for c in categories),
            default=0,
        )
        global_ymax = max(lean_global_max, total_global_max)
        global_ymax = (global_ymax * 1.05) if global_ymax else 1
        for ax, leaning in zip(axes_list, leanings):
            y = [counts.get((d, leaning, category), 0) for d in all_date_strs]
            ax.plot(all_dates, y, color=leaning_colors.get(leaning), label=leaning)
            ax.set_title(leaning)
            ax.legend(loc="upper right")
            style_time_axis(ax)
            ax.set_ylim(0, global_ymax)
        total_ax = axes_list[-1]
        total_y = [totals_by_date_category.get((d, category), 0) for d in all_date_strs]
        total_ax.plot(all_dates, total_y, color="#444444", label="All leanings")
        total_ax.set_title("All leanings")
        total_ax.legend(loc="upper right")
        style_time_axis(total_ax)
        total_ax.set_ylim(0, global_ymax)
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

    def style_time_axis(ax) -> None:
        ax.set_ylim(0, y_max)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
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
            style_time_axis(ax)
        axes_list[-1].set_xlabel("date")
        axes_list[0].set_ylabel("count")
        fig.tight_layout()
        fig.savefig(plot_dir / "all_categories.png", dpi=150)
        plt.close(fig)

    # Per-category totals.
    for category in categories:
        fig, ax = plt.subplots(figsize=(10, 3.2))
        y = [totals.get((d, category), 0) for d in all_date_strs]
        ax.plot(all_dates, y, color="#444444", label="All leanings")
        ax.set_title(f"{category} over time (all leanings)")
        ax.set_xlabel("date")
        ax.set_ylabel("count")
        ax.legend(loc="upper right")
        style_time_axis(ax)
        fig.tight_layout()
        fig.savefig(plot_dir / f"{slugify(category)}.png", dpi=150)
        plt.close(fig)


def main() -> None:
    args = parse_args()
    meta_map = load_metadata(args.metadata)
    sentence_rows = list(iter_sentence_rows(args.sentences))
    counts = count_categories(
        sentence_rows, meta_map, args.category_column, args.category_sep
    )
    write_counts(args.output_csv, counts)
    print(f"Saved category counts to: {args.output_csv}")
    if args.plot:
        plot_counts(counts, args.plot_dir)
        print(f"Saved category plots to: {args.plot_dir}")
        totals = collapse_leanings(counts)
        plot_total_counts(totals, args.total_plot_dir)
        print(f"Saved total category plots to: {args.total_plot_dir}")


if __name__ == "__main__":
    main()
