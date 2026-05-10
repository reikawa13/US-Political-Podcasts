#!/usr/bin/env python3
"""Calculate weekly emotion trends per thesis category and political leaning.

Inputs:
  - sentence_topics_remapped_with_emotions.csv (needs ID + thesis_categories + emotion scores)
  - podMetadata_Nov5_with_leaning.csv (needs ID + date + political_leaning)

Output:
  - topic_modelling/category_emotion_trends_weekly/category_emotion_trends_by_leaning_weekly.csv
    Columns: date, political_leaning, thesis_category, emotion, mean_score, sentence_count
  - topic_modelling/category_emotion_trends_weekly/category_emotion_plots_by_leaning/<category>.png (when --plot is set)
"""
# Usage:
#   python3 category_emotion_trends_by_leaning_weekly.py --plot --start-date 2023-01-01 --end-date 2024-11-05
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Tuple

DEFAULT_SENTENCE_CSV = Path("sentence_topics_remapped_with_emotions_sample.csv")
DEFAULT_META_CSV = Path("../../podMetadata_Nov5_with_leaning.csv")
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = SCRIPT_DIR / "category_emotion_trends_weekly"
DEFAULT_OUT_CSV = DEFAULT_OUT_DIR / "category_emotion_trends_by_leaning_weekly.csv"
DEFAULT_PLOT_DIR = DEFAULT_OUT_DIR / "category_emotion_plots_by_leaning"
DEFAULT_PLOT_DIR_EMOTION_ONLY = DEFAULT_PLOT_DIR / "emotion_only"
DEFAULT_PLOT_DIR_WITH_COUNTS = DEFAULT_PLOT_DIR / "emotion_with_counts"
DEFAULT_TOTAL_PLOT_DIR = DEFAULT_OUT_DIR / "category_emotion_plots_totals"
DEFAULT_TOTAL_PLOT_DIR_EMOTION_ONLY = DEFAULT_TOTAL_PLOT_DIR / "emotion_only"
DEFAULT_TOTAL_PLOT_DIR_WITH_COUNTS = DEFAULT_TOTAL_PLOT_DIR / "emotion_with_counts"
DEFAULT_MISSING_META_CSV = DEFAULT_OUT_DIR / "sentences_missing_metadata.csv"
DEFAULT_META_REPORT = DEFAULT_OUT_DIR / "metadata_debug_report.csv"

DEFAULT_EMOTION_COLUMNS = [
    "Fear_Score",
    "Anger_Score",
    "Joy_Score",
    "Sadness_Score",
    "Disgust_Score",
    "Surprise_Score",
    "Neutral_Score",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate weekly emotion trends per thesis category and political leaning."
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
        help="Also write per-category emotion trend plots as PNG files.",
    )
    parser.add_argument(
        "--plot-dir",
        type=Path,
        default=DEFAULT_PLOT_DIR,
        help="Base directory to write plots when --plot is set.",
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
        "--emotion-columns",
        type=str,
        default=",".join(DEFAULT_EMOTION_COLUMNS),
        help="Comma-separated list of emotion score columns.",
    )
    parser.add_argument(
        "--missing-meta-csv",
        type=Path,
        default=DEFAULT_MISSING_META_CSV,
        help="Write rows with missing metadata to this CSV.",
    )
    parser.add_argument(
        "--metadata-debug-report",
        type=Path,
        default=DEFAULT_META_REPORT,
        help="Write metadata skip breakdown report to this CSV.",
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
    path: Path,
    start_date: datetime | None,
    end_date: datetime | None,
) -> Tuple[Dict[str, Tuple[str, str]], List[Dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {path}")
    mapping: Dict[str, Tuple[str, str]] = {}
    report_rows: List[Dict[str, str]] = []
    sample_limit = 10
    missing_fields = 0
    parse_failed = 0
    out_of_range = 0
    total_rows = 0
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"ID", "date", "political_leaning"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                "Metadata CSV must include ID, date, and political_leaning columns."
            )
        for row in reader:
            total_rows += 1
            episode_id = (row.get("ID") or "").strip()
            date_raw = (row.get("date") or "").strip()
            leaning = (row.get("political_leaning") or "").strip()
            if not episode_id or not date_raw or not leaning:
                missing_fields += 1
                if len(report_rows) < sample_limit:
                    report_rows.append(
                        {
                            "reason": "missing_fields",
                            "ID": episode_id,
                            "date": date_raw,
                            "political_leaning": leaning,
                        }
                    )
                continue
            try:
                week_start = parse_date_to_week_start(date_raw)
            except (TypeError, ValueError):
                parse_failed += 1
                if len(report_rows) < sample_limit:
                    report_rows.append(
                        {
                            "reason": "date_parse_failed",
                            "ID": episode_id,
                            "date": date_raw,
                            "political_leaning": leaning,
                        }
                    )
                continue
            if start_date is not None and week_start < start_date:
                out_of_range += 1
                if len(report_rows) < sample_limit:
                    report_rows.append(
                        {
                            "reason": "before_start_date",
                            "ID": episode_id,
                            "date": date_raw,
                            "political_leaning": leaning,
                        }
                    )
                continue
            if end_date is not None and week_start > end_date:
                out_of_range += 1
                if len(report_rows) < sample_limit:
                    report_rows.append(
                        {
                            "reason": "after_end_date",
                            "ID": episode_id,
                            "date": date_raw,
                            "political_leaning": leaning,
                        }
                    )
                continue
            mapping[episode_id] = (week_start.date().isoformat(), leaning)
    if not mapping:
        raise SystemExit("No usable rows found in metadata CSV.")
    summary = [
        {
            "reason": "summary",
            "total_rows": str(total_rows),
            "missing_fields": str(missing_fields),
            "date_parse_failed": str(parse_failed),
            "out_of_range": str(out_of_range),
            "kept_rows": str(len(mapping)),
        }
    ]
    return mapping, summary + report_rows


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


def emotion_label(column_name: str) -> str:
    label = column_name.strip()
    if label.lower().endswith("_score"):
        label = label[: -len("_score")]
    return label.replace("_", " ").strip().lower()


def count_emotions(
    sentence_rows: Iterable[Dict[str, str]],
    meta_map: Dict[str, Tuple[str, str]],
    category_column: str,
    category_sep: str,
    emotion_columns: List[str],
) -> Tuple[
    Counter[Tuple[str, str, str]],
    Dict[Tuple[str, str, str, str], float],
    List[Dict[str, str]],
]:
    counts: Counter[Tuple[str, str, str]] = Counter()
    sums: Dict[Tuple[str, str, str, str], float] = defaultdict(float)
    missing_meta = 0
    missing_emotion = 0
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

        emotion_values: Dict[str, float] = {}
        for col in emotion_columns:
            raw = row.get(col)
            if raw is None or raw == "":
                emotion_values = {}
                break
            try:
                emotion_values[col] = float(raw)
            except ValueError:
                emotion_values = {}
                break
        if not emotion_values:
            missing_emotion += 1
            continue

        for category in categories:
            counts[(week_start, leaning, category)] += 1
            for col, value in emotion_values.items():
                sums[(week_start, leaning, category, col)] += value
    if not counts:
        raise SystemExit(
            "No emotion aggregates produced. Check category/emotion columns and metadata join."
        )
    if missing_meta:
        print(f"Rows skipped due to missing metadata: {missing_meta}")
    if missing_emotion:
        print(f"Rows skipped due to missing emotion scores: {missing_emotion}")
    return counts, sums, missing_rows


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


def write_metadata_report(path: Path, rows: List[Dict[str, str]]) -> None:
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
    print(f"Saved metadata debug report to: {path}")


def write_emotion_trends(
    path: Path,
    counts: Counter[Tuple[str, str, str]],
    sums: Dict[Tuple[str, str, str, str], float],
    emotion_columns: List[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, str | int | float]] = []
    for (date_day, leaning, category), count in counts.items():
        for col in emotion_columns:
            total = sums.get((date_day, leaning, category, col), 0.0)
            mean_score = total / count if count else 0.0
            rows.append(
                {
                    "date": date_day,
                    "political_leaning": leaning,
                    "thesis_category": category,
                    "emotion": emotion_label(col),
                    "mean_score": mean_score,
                    "sentence_count": count,
                }
            )
    rows.sort(
        key=lambda r: (
            r["date"],
            r["political_leaning"],
            r["thesis_category"],
            r["emotion"],
        )
    )
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "political_leaning",
                "thesis_category",
                "emotion",
                "mean_score",
                "sentence_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def plot_with_gaps(
    ax,
    dates: List[datetime],
    values: List[float | None],
    color: str | None,
    label: str,
) -> None:
    # Solid line for contiguous segments, dotted line bridging gaps.
    segment_dates: List[datetime] = []
    segment_values: List[float] = []
    last_valid_index: int | None = None
    for idx, (dt, val) in enumerate(zip(dates, values)):
        if val is None:
            if segment_dates:
                ax.plot(segment_dates, segment_values, color=color, label=label)
                label = "_nolegend_"
                segment_dates = []
                segment_values = []
            last_valid_index = idx
            continue

        if segment_dates:
            segment_dates.append(dt)
            segment_values.append(val)
        else:
            # Start a new segment. If there was a gap since last valid point, draw dotted bridge.
            if last_valid_index is not None and last_valid_index < idx - 1:
                prev_dt = dates[last_valid_index]
                prev_val = values[last_valid_index]
                if prev_val is not None:
                    ax.plot(
                        [prev_dt, dt],
                        [prev_val, val],
                        color=color,
                        linestyle=":",
                        linewidth=1.0,
                        label="_nolegend_",
                    )
            segment_dates = [dt]
            segment_values = [val]
        last_valid_index = idx

    if segment_dates:
        ax.plot(segment_dates, segment_values, color=color, label=label)


def plot_emotion_trends(
    counts: Counter[Tuple[str, str, str]],
    sums: Dict[Tuple[str, str, str, str], float],
    emotion_columns: List[str],
    plot_dir: Path,
    include_counts: bool,
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

    all_date_strs = sorted({d for (d, _, _) in counts.keys()})
    all_dates = [datetime.fromisoformat(d) for d in all_date_strs]

    # Match matplotlib default cycle used in emotion_trends_weekly.py
    emotion_colors = {
        "anger": "#1f77b4",
        "disgust": "#ff7f0e",
        "fear": "#2ca02c",
        "joy": "#d62728",
        "neutral": "#9467bd",
        "sadness": "#8c564b",
        "surprise": "#e377c2",
    }

    def style_time_axis(ax) -> None:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
        ax.yaxis.set_major_locator(MaxNLocator(integer=False))
        ax.tick_params(axis="x", which="both", labelbottom=True, rotation=45, labelsize=7)
        ax.tick_params(axis="y", labelsize=9)

    emotion_labels = [emotion_label(col) for col in emotion_columns]

    # Combined grid: all categories x leanings.
    if categories and leanings:
        nrows = len(categories)
        ncols = len(leanings)
        fig, axes = plt.subplots(
            nrows=nrows,
            ncols=ncols,
            figsize=(ncols * 4.2, nrows * 2.4),
            sharex=True,
            sharey=True,
        )
        axes_list = list(axes.flat) if hasattr(axes, "flat") else [axes]

        for r, category in enumerate(categories):
            if include_counts:
                category_count_max = max(
                    (
                        counts.get((d, leaning, category), 0)
                        for d in all_date_strs
                        for leaning in leanings
                    ),
                    default=0,
                )
                count_ymax = category_count_max * 1.05 if category_count_max else 1

            for c, leaning in enumerate(leanings):
                ax = axes[r][c] if nrows > 1 and ncols > 1 else axes_list[r * ncols + c]
                for col, label in zip(emotion_columns, emotion_labels):
                    if label == "neutral":
                        continue
                    y_values: List[float | None] = []
                    for d in all_date_strs:
                        count = counts.get((d, leaning, category), 0)
                        if not count:
                            y_values.append(None)
                            continue
                        total = sums.get((d, leaning, category, col), 0.0)
                        y_values.append(total / count)
                    plot_with_gaps(
                        ax,
                        all_dates,
                        y_values,
                        color=emotion_colors.get(label, None),
                        label=label,
                    )
                if include_counts:
                    count_series = [
                        counts.get((d, leaning, category), 0) for d in all_date_strs
                    ]
                    ax2 = ax.twinx()
                    ax2.plot(
                        all_dates,
                        count_series,
                        color="#000000",
                        label="count",
                        linewidth=1.1,
                    )
                    ax2.set_ylim(0, count_ymax)
                    ax2.tick_params(axis="y", labelsize=7, colors="#000000")

                if r == 0:
                    ax.set_title(leaning)
                if c == 0:
                    ax.set_ylabel(category)
                style_time_axis(ax)
                ax.set_ylim(0, 1.0)

        legend_handles = []
        legend_labels = []
        for label in emotion_labels:
            if label == "neutral":
                continue
            legend_labels.append(label)
            legend_handles.append(
                plt.Line2D(
                    [0],
                    [0],
                    color=emotion_colors.get(label, None),
                    linewidth=1.5,
                )
            )
        if include_counts:
            legend_labels.append("count")
            legend_handles.append(plt.Line2D([0], [0], color="#000000", linewidth=1.2))

        fig.legend(
            legend_handles,
            legend_labels,
            loc="lower center",
            ncol=min(len(legend_labels), 4),
            fontsize=8,
            frameon=False,
        )
        fig.tight_layout(rect=[0, 0.05, 1, 1])
        fig.savefig(plot_dir / "all_categories.png", dpi=150)
        plt.close(fig)

    for category in categories:
        ncols = max(len(leanings), 1)
        fig, axes = plt.subplots(
            nrows=1,
            ncols=ncols,
            figsize=(ncols * 4.2, 3.2),
            sharex=True,
            sharey=True,
        )
        axes_list = list(axes.flat) if hasattr(axes, "flat") else [axes]
        if include_counts:
            category_count_max = max(
                (
                    counts.get((d, leaning, category), 0)
                    for d in all_date_strs
                    for leaning in leanings
                ),
                default=0,
            )
            count_ymax = category_count_max * 1.05 if category_count_max else 1

        for ax, leaning in zip(axes_list, leanings):
            for col, label in zip(emotion_columns, emotion_labels):
                if label == "neutral":
                    continue
                y_values: List[float | None] = []
                for d in all_date_strs:
                    count = counts.get((d, leaning, category), 0)
                    if not count:
                        y_values.append(None)
                        continue
                    total = sums.get((d, leaning, category, col), 0.0)
                    y_values.append(total / count)
                plot_with_gaps(
                    ax,
                    all_dates,
                    y_values,
                    color=emotion_colors.get(label, None),
                    label=label,
                )
            if include_counts:
                count_series = [
                    counts.get((d, leaning, category), 0) for d in all_date_strs
                ]
                ax2 = ax.twinx()
                ax2.plot(
                    all_dates,
                    count_series,
                    color="#000000",
                    label="count",
                    linewidth=1.2,
                )
                ax2.set_ylim(0, count_ymax)
                ax2.tick_params(axis="y", labelsize=8, colors="#000000")
            ax.set_title(leaning)
            style_time_axis(ax)
            ax.set_ylim(0, 1.0)
            ax.legend(loc="upper right", fontsize=7)
            if include_counts:
                ax2.legend(loc="upper left", fontsize=7)

        axes_list[0].set_ylabel("mean emotion score")
        fig.suptitle(f"{category} emotion trends", y=1.02)
        fig.tight_layout()
        out_path = plot_dir / f"{slugify(category)}.png"
        fig.savefig(out_path, dpi=150)
        plt.close(fig)


def plot_emotion_trends_totals(
    counts: Counter[Tuple[str, str, str]],
    sums: Dict[Tuple[str, str, str, str], float],
    emotion_columns: List[str],
    plot_dir: Path,
    include_counts: bool,
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
    leanings = sorted({l for (_, l, _) in counts.keys()})
    all_date_strs = sorted({d for (d, _, _) in counts.keys()})
    all_dates = [datetime.fromisoformat(d) for d in all_date_strs]

    # Match matplotlib default cycle used in emotion_trends_weekly.py
    emotion_colors = {
        "anger": "#1f77b4",
        "disgust": "#ff7f0e",
        "fear": "#2ca02c",
        "joy": "#d62728",
        "neutral": "#9467bd",
        "sadness": "#8c564b",
        "surprise": "#e377c2",
    }

    def style_time_axis(ax) -> None:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
        ax.yaxis.set_major_locator(MaxNLocator(integer=False))
        ax.tick_params(axis="x", which="both", labelbottom=True, rotation=45, labelsize=7)
        ax.tick_params(axis="y", labelsize=9)

    emotion_labels = [emotion_label(col) for col in emotion_columns]

    def total_count(d: str, category: str) -> int:
        return sum(counts.get((d, leaning, category), 0) for leaning in leanings)

    def total_sum(d: str, category: str, col: str) -> float:
        return sum(sums.get((d, leaning, category, col), 0.0) for leaning in leanings)

    # Combined grid: all categories (single column).
    if categories:
        nrows = len(categories)
        fig, axes = plt.subplots(
            nrows=nrows,
            ncols=1,
            figsize=(10, nrows * 2.4),
            sharex=True,
            sharey=True,
        )
        axes_list = list(axes.flat) if hasattr(axes, "flat") else [axes]

        for ax, category in zip(axes_list, categories):
            if include_counts:
                category_count_max = max(
                    (total_count(d, category) for d in all_date_strs),
                    default=0,
                )
                count_ymax = category_count_max * 1.05 if category_count_max else 1

            for col, label in zip(emotion_columns, emotion_labels):
                if label == "neutral":
                    continue
                y_values: List[float | None] = []
                for d in all_date_strs:
                    count = total_count(d, category)
                    if not count:
                        y_values.append(None)
                        continue
                    y_values.append(total_sum(d, category, col) / count)
                plot_with_gaps(
                    ax,
                    all_dates,
                    y_values,
                    color=emotion_colors.get(label, None),
                    label=label,
                )
            if include_counts:
                count_series = [total_count(d, category) for d in all_date_strs]
                ax2 = ax.twinx()
                ax2.plot(
                    all_dates,
                    count_series,
                    color="#000000",
                    label="count",
                    linewidth=1.1,
                )
                ax2.set_ylim(0, count_ymax)
                ax2.tick_params(axis="y", labelsize=7, colors="#000000")

            ax.set_ylabel(category)
            style_time_axis(ax)
            ax.set_ylim(0, 1.0)

        legend_handles = []
        legend_labels = []
        for label in emotion_labels:
            if label == "neutral":
                continue
            legend_labels.append(label)
            legend_handles.append(
                plt.Line2D(
                    [0],
                    [0],
                    color=emotion_colors.get(label, None),
                    linewidth=1.5,
                )
            )
        if include_counts:
            legend_labels.append("count")
            legend_handles.append(plt.Line2D([0], [0], color="#000000", linewidth=1.2))

        fig.legend(
            legend_handles,
            legend_labels,
            loc="lower center",
            ncol=min(len(legend_labels), 4),
            fontsize=8,
            frameon=False,
        )
        fig.tight_layout(rect=[0, 0.05, 1, 1])
        fig.savefig(plot_dir / "all_categories.png", dpi=150)
        plt.close(fig)

    # Per-category totals.
    for category in categories:
        fig, ax = plt.subplots(figsize=(10, 3.2))
        if include_counts:
            category_count_max = max(
                (total_count(d, category) for d in all_date_strs),
                default=0,
            )
            count_ymax = category_count_max * 1.05 if category_count_max else 1

        for col, label in zip(emotion_columns, emotion_labels):
            if label == "neutral":
                continue
            y_values: List[float | None] = []
            for d in all_date_strs:
                count = total_count(d, category)
                if not count:
                    y_values.append(None)
                    continue
                y_values.append(total_sum(d, category, col) / count)
            plot_with_gaps(
                ax,
                all_dates,
                y_values,
                color=emotion_colors.get(label, None),
                label=label,
            )

        if include_counts:
            count_series = [total_count(d, category) for d in all_date_strs]
            ax2 = ax.twinx()
            ax2.plot(
                all_dates,
                count_series,
                color="#000000",
                label="count",
                linewidth=1.1,
            )
            ax2.set_ylim(0, count_ymax)
            ax2.tick_params(axis="y", labelsize=8, colors="#000000")

        ax.set_title(f"{category} emotion trends (all leanings)")
        ax.set_ylabel("mean emotion score")
        style_time_axis(ax)
        ax.set_ylim(0, 1.0)
        ax.legend(loc="upper right", fontsize=7)
        if include_counts:
            ax2.legend(loc="upper left", fontsize=7)
        fig.tight_layout()
        out_path = plot_dir / f"{slugify(category)}.png"
        fig.savefig(out_path, dpi=150)
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
    emotion_columns = [c.strip() for c in args.emotion_columns.split(",") if c.strip()]
    if not emotion_columns:
        raise SystemExit("No emotion columns specified.")

    meta_map, meta_report = load_metadata(args.metadata, start_date, end_date)
    sentence_rows = list(iter_sentence_rows(args.sentences))
    counts, sums, missing_rows = count_emotions(
        sentence_rows,
        meta_map,
        args.category_column,
        args.category_sep,
        emotion_columns,
    )
    write_emotion_trends(args.output_csv, counts, sums, emotion_columns)
    print(f"Saved emotion trends to: {args.output_csv}")
    write_metadata_report(args.metadata_debug_report, meta_report)
    write_missing_rows(args.missing_meta_csv, missing_rows)
    if args.plot:
        base_dir = args.plot_dir
        emotion_only_dir = base_dir / "emotion_only"
        with_counts_dir = base_dir / "emotion_with_counts"
        plot_emotion_trends(counts, sums, emotion_columns, emotion_only_dir, include_counts=False)
        plot_emotion_trends(counts, sums, emotion_columns, with_counts_dir, include_counts=True)
        print(f"Saved emotion-only plots to: {emotion_only_dir}")
        print(f"Saved emotion+count plots to: {with_counts_dir}")
        totals_emotion_only_dir = DEFAULT_TOTAL_PLOT_DIR_EMOTION_ONLY
        totals_with_counts_dir = DEFAULT_TOTAL_PLOT_DIR_WITH_COUNTS
        plot_emotion_trends_totals(
            counts, sums, emotion_columns, totals_emotion_only_dir, include_counts=False
        )
        plot_emotion_trends_totals(
            counts, sums, emotion_columns, totals_with_counts_dir, include_counts=True
        )
        print(f"Saved totals emotion-only plots to: {totals_emotion_only_dir}")
        print(f"Saved totals emotion+count plots to: {totals_with_counts_dir}")


if __name__ == "__main__":
    main()
