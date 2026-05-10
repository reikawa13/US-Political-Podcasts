#!/usr/bin/env python3
"""Calculate average emotion scores for each thesis category overall.

Also writes a single PNG containing one pie chart for each category with no
political-leaning split.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, Iterator, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SENTENCE_CSV = SCRIPT_DIR / "sentence_topics_remapped_with_emotions_sample.csv"
DEFAULT_OUT_DIR = SCRIPT_DIR / "category_sentiment_overall"
DEFAULT_OUT_CSV = DEFAULT_OUT_DIR / "category_sentiment_overall.csv"
DEFAULT_OUT_PNG = DEFAULT_OUT_DIR / "category_sentiment_pies_overall.png"

DEFAULT_EMOTION_COLUMNS = [
    "Fear_Score",
    "Anger_Score",
    "Joy_Score",
    "Sadness_Score",
    "Disgust_Score",
    "Surprise_Score",
    "Neutral_Score",
]

PIE_EMOTION_ORDER = [
    "Anger_Score",
    "Disgust_Score",
    "Fear_Score",
    "Joy_Score",
    "Sadness_Score",
    "Surprise_Score",
]

EMOTION_COLORS = {
    "Anger_Score": "#d73027",
    "Disgust_Score": "#1a9850",
    "Fear_Score": "#4575b4",
    "Joy_Score": "#fdae61",
    "Sadness_Score": "#74add1",
    "Surprise_Score": "#f46d43",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate average emotion scores for each thesis category overall, "
            "and write all pies to one PNG."
        )
    )
    parser.add_argument("--sentences", type=Path, default=DEFAULT_SENTENCE_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--output-png", type=Path, default=DEFAULT_OUT_PNG)
    parser.add_argument(
        "--category-column",
        type=str,
        default="thesis_categories",
        help="Column containing thesis categories.",
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
        help="Comma-separated list of emotion score columns to average.",
    )
    parser.add_argument(
        "--exclude-categories",
        type=str,
        default="Unmapped",
        help="Comma-separated category labels to exclude from outputs.",
    )
    return parser.parse_args()


def iter_rows(path: Path) -> Iterator[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Sentence CSV not found: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Sentence CSV is missing a header row.")
        for row in reader:
            yield row


def parse_list_arg(value: str) -> List[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def split_categories(value: str, sep: str) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(sep) if part.strip()]


def aggregate_category_sentiment(
    rows: Iterable[Dict[str, str]],
    category_column: str,
    category_sep: str,
    emotion_columns: List[str],
    excluded_categories: set[str],
) -> Tuple[
    Counter[str],
    DefaultDict[str, Dict[str, float]],
    Counter[str],
    set[str],
]:
    counts: Counter[str] = Counter()
    sums: DefaultDict[str, Dict[str, float]] = defaultdict(
        lambda: {column: 0.0 for column in emotion_columns}
    )
    skipped: Counter[str] = Counter()
    seen_categories: set[str] = set()

    for row in rows:
        categories = [
            category
            for category in split_categories(row.get(category_column, ""), category_sep)
            if category not in excluded_categories
        ]
        if not categories:
            skipped["missing_or_excluded_category"] += 1
            continue
        seen_categories.update(categories)

        values: Dict[str, float] = {}
        invalid = False
        for column in emotion_columns:
            raw = row.get(column)
            if raw is None or raw == "":
                invalid = True
                break
            try:
                values[column] = float(raw)
            except ValueError:
                invalid = True
                break
        if invalid:
            skipped["missing_or_invalid_emotion_scores"] += 1
            continue

        for category in categories:
            counts[category] += 1
            for column, value in values.items():
                sums[category][column] += value

    if not counts:
        raise SystemExit(
            "No category sentiment aggregates produced. Check category and emotion score columns."
        )
    return counts, sums, skipped, seen_categories


def ensure_all_categories(
    counts: Counter[str],
    sums: DefaultDict[str, Dict[str, float]],
    categories: List[str],
    emotion_columns: List[str],
) -> None:
    for category in categories:
        if category not in counts:
            counts[category] = 0
            sums[category] = {column: 0.0 for column in emotion_columns}


def write_output(
    path: Path,
    counts: Counter[str],
    sums: DefaultDict[str, Dict[str, float]],
    emotion_columns: List[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["thesis_category", "sentence_count", *emotion_columns]
    rows: List[Dict[str, str | int | float]] = []

    for category, count in counts.items():
        row: Dict[str, str | int | float] = {
            "thesis_category": category,
            "sentence_count": count,
        }
        for column in emotion_columns:
            row[column] = sums[category][column] / count if count else 0.0
        rows.append(row)

    rows.sort(key=lambda row: str(row["thesis_category"]))

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def label_for_emotion(column_name: str) -> str:
    return column_name.replace("_Score", "")


def plot_pies(
    path: Path,
    counts: Counter[str],
    sums: DefaultDict[str, Dict[str, float]],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    categories = sorted(counts)
    if not categories:
        raise SystemExit("No categories available for plotting.")

    ncols = 3
    nrows = (len(categories) + ncols - 1) // ncols
    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        figsize=(4.8 * ncols, 3.6 * nrows),
        subplot_kw={"aspect": "equal"},
    )

    if nrows == 1 and ncols == 1:
        axes_list = [axes]
    else:
        axes_list = list(axes.flat)

    for ax, category in zip(axes_list, categories):
        count = counts.get(category, 0)

        if count == 0:
            ax.axis("equal")
            ax.text(0.5, 0.56, "No data", ha="center", va="center", fontsize=10)
            ax.text(0.5, 0.42, category, ha="center", va="center", fontsize=8)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            continue

        means = [sums[category][emotion] / count for emotion in PIE_EMOTION_ORDER]
        total = sum(means)
        if total <= 0:
            ax.axis("off")
            ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=9)
            continue

        ax.pie(
            means,
            labels=[label_for_emotion(emotion) for emotion in PIE_EMOTION_ORDER],
            colors=[EMOTION_COLORS[emotion] for emotion in PIE_EMOTION_ORDER],
            autopct="%1.0f%%",
            startangle=90,
            counterclock=False,
            textprops={"fontsize": 10.5},
        )
        ax.set_title(f"{category} (n={count})", fontsize=13.5)

    for ax in axes_list[len(categories) :]:
        ax.axis("off")

    fig.suptitle("Average Emotion Distribution by Thesis Category", fontsize=21)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    emotion_columns = parse_list_arg(args.emotion_columns)
    if not emotion_columns:
        raise SystemExit("No emotion columns specified.")

    excluded_categories = set(parse_list_arg(args.exclude_categories))
    counts, sums, skipped, seen_categories = aggregate_category_sentiment(
        rows=iter_rows(args.sentences),
        category_column=args.category_column,
        category_sep=args.category_sep,
        emotion_columns=emotion_columns,
        excluded_categories=excluded_categories,
    )

    categories = sorted(seen_categories)
    ensure_all_categories(counts, sums, categories, emotion_columns)

    write_output(args.output_csv, counts, sums, emotion_columns)
    plot_pies(args.output_png, counts, sums)

    if skipped:
        for reason, count in sorted(skipped.items()):
            print(f"Rows skipped due to {reason}: {count}")
    print(f"Wrote {len(counts)} category rows to {args.output_csv}")
    print(f"Wrote pie chart grid to {args.output_png}")


if __name__ == "__main__":
    main()
