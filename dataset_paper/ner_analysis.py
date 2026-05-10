#!/usr/bin/env python3
"""Run spaCy named-entity recognition on podcast titles and descriptions.

The script uses the `en_core_web_lg` model to process the CSV file used
throughout the project.  It outputs two CSV files summarizing entity counts:

    - deliverables/title_entities.csv
    - deliverables/description_entities.csv

Each CSV contains three columns:
    entity  |  label  |  count

Usage:
    python ner_analysis.py --input podMetadata_Nov5_with_leaning.csv

Dependencies:
    - pandas
    - spacy (with the en_core_web_lg model, install via
      `python -m spacy download en_core_web_lg`)
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Iterable, List

import pandas as pd

try:
    import spacy
except ImportError as exc:  # pragma: no cover - depends on local install
    raise SystemExit(
        "spaCy is required for this script. Install it via `pip install spacy` "
        "and download the model with `python -m spacy download en_core_web_lg`."
    ) from exc

DEFAULT_INPUT = "podMetadata_Nov5_with_leaning.csv"
TITLE_OUTPUT = Path("deliverables/title_entities.csv")
DESC_OUTPUT = Path("deliverables/description_entities.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate named entities for titles and descriptions."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT),
        help="CSV containing `title` and `description` columns (default: %(default)s).",
    )
    parser.add_argument(
        "--title-output",
        type=Path,
        default=TITLE_OUTPUT,
        help="Where to write title entity counts (default: %(default)s).",
    )
    parser.add_argument(
        "--description-output",
        type=Path,
        default=DESC_OUTPUT,
        help="Where to write description entity counts (default: %(default)s).",
    )
    return parser.parse_args()


def load_texts(csv_path: Path) -> pd.DataFrame:
    """Load cleaned title/description text alongside political leaning."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Input file not found: {csv_path}")
    df = pd.read_csv(csv_path, usecols=["title", "description", "political_leaning"])
    for column in ["title", "description", "political_leaning"]:
        df[column] = df[column].fillna("").astype(str).str.strip()
    if df[["title", "description"]].replace("", pd.NA).dropna(how="all").empty:
        raise ValueError("No valid titles or descriptions to process.")
    df["political_leaning"] = df["political_leaning"].replace("", "Unknown")
    return df


def aggregate_entities(texts: Iterable[str], nlp: "spacy.Language") -> Counter:
    """Count entities (text + label) across a sequence of texts."""
    counts: Counter[Tuple[str, str]] = Counter()
    for doc in nlp.pipe(texts, batch_size=50):
        for ent in doc.ents:
            entity_text = ent.text.strip()
            if not entity_text:
                continue
            counts[(entity_text, ent.label_)] += 1
    return counts


def counts_to_dataframe(counts: Counter, top_n: int | None = None) -> pd.DataFrame:
    """Convert counter to a sorted DataFrame with columns entity/label/count."""
    records = [
        {"entity": entity, "label": label, "count": count}
        for (entity, label), count in counts.items()
    ]
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.sort_values(by=["count", "entity"], ascending=[False, True]).reset_index(drop=True)
    if top_n is not None:
        df = df.head(top_n)
    return df


def save_counts(df: pd.DataFrame, path: Path) -> None:
    """Save counts to CSV, creating directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def top_entities_by_leaning(
    df: pd.DataFrame,
    column: str,
    nlp: "spacy.Language",
    top_n: int = 10,
) -> pd.DataFrame:
    """Return top entities (as percentages) per political leaning."""
    results: List[pd.DataFrame] = []
    for leaning, group in df.groupby("political_leaning"):
        texts = group[column]
        texts = texts[texts != ""]
        if texts.empty:
            continue
        counts = aggregate_entities(texts.tolist(), nlp)
        if not counts:
            continue
        summary = counts_to_dataframe(counts, top_n=None)
        total = summary["count"].sum()
        if total == 0:
            continue
        summary["percentage"] = summary["count"] / total
        summary = summary.sort_values(by=["percentage", "entity"], ascending=[False, True])
        summary = summary.head(top_n).reset_index(drop=True)
        summary.insert(0, "political_leaning", leaning)
        results.append(summary)
    if not results:
        return pd.DataFrame(columns=["political_leaning", "entity", "label", "count", "percentage"])
    return pd.concat(results, ignore_index=True)


def main() -> None:
    args = parse_args()
    df = load_texts(args.input)

    try:
        nlp = spacy.load("en_core_web_lg", disable=["tagger", "parser", "lemmatizer"])
    except OSError as exc:  # pragma: no cover - depends on local install
        raise SystemExit(
            "The spaCy model 'en_core_web_lg' is not installed. "
            "Install it with `python -m spacy download en_core_web_lg`."
        ) from exc

    print("Processing named entities by political leaning...")
    title_df = top_entities_by_leaning(df, "title", nlp)
    desc_df = top_entities_by_leaning(df, "description", nlp)

    save_counts(title_df, args.title_output)
    save_counts(desc_df, args.description_output)

    print(f"Saved title entity counts to {args.title_output}")
    print(f"Saved description entity counts to {args.description_output}")
    def display_summary(label: str, summary: pd.DataFrame) -> None:
        if summary.empty:
            print(f"No entities extracted for {label}.")
            return
        print(f"\nTop entities in {label}:")
        for leaning, subset in summary.groupby("political_leaning"):
            print(f"  Political leaning: {leaning}")
            print(
                subset[["entity", "label", "count", "percentage"]]
                .rename(columns={"percentage": "share"})
                .to_string(index=False)
            )

    display_summary("titles", title_df)
    display_summary("descriptions", desc_df)


if __name__ == "__main__":
    main()
