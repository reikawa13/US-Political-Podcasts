#!/usr/bin/env python3
"""Calculate average emotion scores for each topic and political leaning pair.

Inputs:
  - sentence_topics_remapped_with_emotions_sample.csv by default
    Requires: topic, emotion score columns, and either political_leaning or ID
  - podMetadata_Nov5_with_leaning.csv when political_leaning must be joined by ID

Output:
  - analysis/topic_modelling/topic_sentiment_by_leaning/topic_sentiment_by_leaning.csv
    Columns: topic, political_leaning, sentence_count, <emotion score means...>

Usage:
  python3 topic_sentiment_by_leaning.py
  python3 topic_sentiment_by_leaning.py --sentences path/to/input.csv --output-csv path/to/output.csv
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
DEFAULT_OUT_DIR = SCRIPT_DIR / "topic_sentiment_by_leaning"
DEFAULT_OUT_CSV = DEFAULT_OUT_DIR / "topic_sentiment_by_leaning.csv"

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
        description="Calculate average emotion scores for each topic and political leaning pair."
    )
    parser.add_argument("--sentences", type=Path, default=DEFAULT_SENTENCE_CSV)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument(
        "--topic-column",
        type=str,
        default="topic",
        help="Column containing the topic identifier.",
    )
    parser.add_argument(
        "--leaning-column",
        type=str,
        default="political_leaning",
        help="Column containing political leaning in the sentence CSV.",
    )
    parser.add_argument(
        "--emotion-columns",
        type=str,
        default=",".join(DEFAULT_EMOTION_COLUMNS),
        help="Comma-separated list of emotion score columns to average.",
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


def parse_emotion_columns(value: str) -> List[str]:
    columns = [part.strip() for part in value.split(",")]
    return [column for column in columns if column]


def aggregate_topic_sentiment(
    rows: Iterable[Dict[str, str]],
    topic_column: str,
    leaning_column: str,
    emotion_columns: List[str],
    metadata_leanings: Dict[str, str],
) -> Tuple[
    Counter[Tuple[str, str]],
    DefaultDict[Tuple[str, str], Dict[str, float]],
    Counter[str],
]:
    counts: Counter[Tuple[str, str]] = Counter()
    sums: DefaultDict[Tuple[str, str], Dict[str, float]] = defaultdict(
        lambda: {column: 0.0 for column in emotion_columns}
    )
    skipped: Counter[str] = Counter()

    for row in rows:
        topic = (row.get(topic_column) or "").strip()
        if not topic:
            skipped["missing_topic"] += 1
            continue

        leaning = (row.get(leaning_column) or "").strip()
        if not leaning:
            episode_id = (row.get("ID") or "").strip()
            leaning = metadata_leanings.get(episode_id, "").strip() if episode_id else ""
        if not leaning:
            skipped["missing_leaning"] += 1
            continue

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

        key = (topic, leaning)
        counts[key] += 1
        for column, value in values.items():
            sums[key][column] += value

    if not counts:
        raise SystemExit(
            "No topic sentiment aggregates produced. Check topic, political leaning, and emotion score columns."
        )
    return counts, sums, skipped


def write_output(
    path: Path,
    counts: Counter[Tuple[str, str]],
    sums: DefaultDict[Tuple[str, str], Dict[str, float]],
    emotion_columns: List[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["topic", "political_leaning", "sentence_count", *emotion_columns]
    rows: List[Dict[str, str | int | float]] = []

    for (topic, leaning), count in counts.items():
        row: Dict[str, str | int | float] = {
            "topic": topic,
            "political_leaning": leaning,
            "sentence_count": count,
        }
        for column in emotion_columns:
            row[column] = sums[(topic, leaning)][column] / count if count else 0.0
        rows.append(row)

    def sort_key(row: Dict[str, str | int | float]) -> Tuple[int, str, str]:
        topic = str(row["topic"])
        try:
            topic_num = int(float(topic))
        except ValueError:
            topic_num = 10**9
        return (topic_num, str(row["topic"]), str(row["political_leaning"]))

    rows.sort(key=sort_key)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    emotion_columns = parse_emotion_columns(args.emotion_columns)
    if not emotion_columns:
        raise SystemExit("No emotion columns specified.")

    metadata_leanings = load_metadata_leanings(args.metadata)
    counts, sums, skipped = aggregate_topic_sentiment(
        rows=iter_rows(args.sentences),
        topic_column=args.topic_column,
        leaning_column=args.leaning_column,
        emotion_columns=emotion_columns,
        metadata_leanings=metadata_leanings,
    )
    write_output(args.output_csv, counts, sums, emotion_columns)

    if skipped:
        for reason, count in sorted(skipped.items()):
            print(f"Rows skipped due to {reason}: {count}")
    print(f"Wrote {len(counts)} topic x leaning rows to {args.output_csv}")


if __name__ == "__main__":
    main()
