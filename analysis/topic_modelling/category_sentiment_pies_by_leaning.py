#!/usr/bin/env python3
"""Calculate average emotion scores for each thesis category and political leaning pair.

Also writes a single PNG containing one pie chart for each category x political
leaning pair. By default this excludes the "Unmapped" category, yielding 24 pies
for 8 mapped categories x 3 leanings.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, Iterator, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SENTENCE_CSV = SCRIPT_DIR / "sentence_topics_remapped_with_emotions_sample.csv"
DEFAULT_META_CSV = SCRIPT_DIR.parent.parent / "podMetadata_Nov5_with_leaning.csv"
DEFAULT_OUT_DIR = SCRIPT_DIR / "category_sentiment_by_leaning"
DEFAULT_OUT_CSV = DEFAULT_OUT_DIR / "category_sentiment_by_leaning.csv"
DEFAULT_OUT_PNG = DEFAULT_OUT_DIR / "category_sentiment_pies_by_leaning.png"

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

PREFERRED_LEANINGS = ["Liberal", "Moderate", "Conservative"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate average emotion scores for each thesis category and political "
            "leaning pair, and write all pies to one PNG."
        )
    )
    parser.add_argument("--sentences", type=Path, default=DEFAULT_SENTENCE_CSV)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--output-png", type=Path, default=DEFAULT_OUT_PNG)
    parser.add_argument(
        "--category-column",
        type=str,
        default="thesis_categories",
        help="Column containing thesis categories.",
    )
    parser.add_argument(
        "--leaning-column",
        type=str,
        default="political_leaning",
        help="Column containing political leaning in the sentence CSV.",
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


def load_metadata_leanings(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"ID", "political_leaning"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Metadata CSV must include ID and political_leaning columns.")
        mapping: Dict[str, str] = {}
        for row in reader:
            episode_id = (row.get("ID") or "").strip()
            leaning = (row.get("political_leaning") or "").strip()
            if episode_id and leaning and episode_id not in mapping:
                mapping[episode_id] = leaning
        return mapping


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
    leaning_column: str,
    emotion_columns: List[str],
    excluded_categories: set[str],
    metadata_leanings: Dict[str, str],
) -> Tuple[
    Counter[Tuple[str, str]],
    DefaultDict[Tuple[str, str], Dict[str, float]],
    Counter[str],
    set[str],
]:
    counts: Counter[Tuple[str, str]] = Counter()
    sums: DefaultDict[Tuple[str, str], Dict[str, float]] = defaultdict(
        lambda: {column: 0.0 for column in emotion_columns}
    )
    skipped: Counter[str] = Counter()
    seen_categories: set[str] = set()

    for row in rows:
        leaning = (row.get(leaning_column) or "").strip()
        if not leaning:
            episode_id = (row.get("ID") or "").strip()
            leaning = metadata_leanings.get(episode_id, "").strip() if episode_id else ""
        if not leaning:
            skipped["missing_leaning"] += 1
            continue

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
            key = (category, leaning)
            counts[key] += 1
            for column, value in values.items():
                sums[key][column] += value

    if not counts:
        raise SystemExit(
            "No category sentiment aggregates produced. Check category, leaning, and emotion score columns."
        )
    return counts, sums, skipped, seen_categories


def ensure_all_pairs(
    counts: Counter[Tuple[str, str]],
    sums: DefaultDict[Tuple[str, str], Dict[str, float]],
    categories: List[str],
    leanings: List[str],
    emotion_columns: List[str],
) -> None:
    for category in categories:
        for leaning in leanings:
            key = (category, leaning)
            if key not in counts:
                counts[key] = 0
                sums[key] = {column: 0.0 for column in emotion_columns}


def write_output(
    path: Path,
    counts: Counter[Tuple[str, str]],
    sums: DefaultDict[Tuple[str, str], Dict[str, float]],
    emotion_columns: List[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["thesis_category", "political_leaning", "sentence_count", *emotion_columns]
    rows: List[Dict[str, str | int | float]] = []

    for (category, leaning), count in counts.items():
        row: Dict[str, str | int | float] = {
            "thesis_category": category,
            "political_leaning": leaning,
            "sentence_count": count,
        }
        for column in emotion_columns:
            row[column] = sums[(category, leaning)][column] / count if count else 0.0
        rows.append(row)

    rows.sort(key=lambda row: (str(row["thesis_category"]), str(row["political_leaning"])))

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def label_for_emotion(column_name: str) -> str:
    return column_name.replace("_Score", "")


def ordered_leanings(counts: Counter[Tuple[str, str]]) -> List[str]:
    found = {leaning for (_, leaning) in counts}
    return [leaning for leaning in PREFERRED_LEANINGS if leaning in found] + sorted(
        found - set(PREFERRED_LEANINGS)
    )


def plot_pies(
    path: Path,
    counts: Counter[Tuple[str, str]],
    sums: DefaultDict[Tuple[str, str], Dict[str, float]],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    categories = sorted({category for (category, _) in counts})
    leanings = ordered_leanings(counts)

    if not categories or not leanings:
        raise SystemExit("No category x leaning pairs available for plotting.")

    fig, axes = plt.subplots(
        nrows=len(categories),
        ncols=len(leanings),
        figsize=(4.8 * len(leanings), 3.4 * len(categories)),
        subplot_kw={"aspect": "equal"},
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
            key = (category, leaning)
            count = counts.get(key, 0)

            if count == 0:
                ax.axis("equal")
                ax.text(0.5, 0.56, "No data", ha="center", va="center", fontsize=10)
                ax.text(0.5, 0.42, f"{category}\n{leaning}", ha="center", va="center", fontsize=8)
                ax.set_xticks([])
                ax.set_yticks([])
                for spine in ax.spines.values():
                    spine.set_visible(False)
                continue

            means = [sums[key][emotion] / count for emotion in PIE_EMOTION_ORDER]
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
                textprops={"fontsize": 7},
            )
            ax.set_title(f"{category}\n{leaning} (n={count})", fontsize=9)

    fig.suptitle("Average Emotion Distribution by Thesis Category and Political Leaning", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    emotion_columns = parse_list_arg(args.emotion_columns)
    if not emotion_columns:
        raise SystemExit("No emotion columns specified.")

    excluded_categories = set(parse_list_arg(args.exclude_categories))
    metadata_leanings = load_metadata_leanings(args.metadata)
    counts, sums, skipped, seen_categories = aggregate_category_sentiment(
        rows=iter_rows(args.sentences),
        category_column=args.category_column,
        category_sep=args.category_sep,
        leaning_column=args.leaning_column,
        emotion_columns=emotion_columns,
        excluded_categories=excluded_categories,
        metadata_leanings=metadata_leanings,
    )

    categories = sorted(seen_categories)
    leanings = PREFERRED_LEANINGS[:]
    ensure_all_pairs(counts, sums, categories, leanings, emotion_columns)

    write_output(args.output_csv, counts, sums, emotion_columns)
    plot_pies(args.output_png, counts, sums)

    if skipped:
        for reason, count in sorted(skipped.items()):
            print(f"Rows skipped due to {reason}: {count}")
    print(f"Wrote {len(counts)} category x leaning rows to {args.output_csv}")
    print(f"Wrote pie chart grid to {args.output_png}")


if __name__ == "__main__":
    main()
