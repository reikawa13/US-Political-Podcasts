#!/usr/bin/env python3
"""Extract top transcript named entities per political leaning.

Mirrors the file-structure expectations of `check_transcripts.py`, scanning
`podMetadata_Nov5_with_leaning.csv` to locate each transcript file under:
    final_Transcripts_beforeNov5/<podName>/trans_<ID>.txt

For every transcript found, spaCy NER is applied and entity counts are grouped
by `political_leaning`. The top 10 entities (with labels and counts) for each
leaning are written to a CSV and echoed to stdout.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

DEFAULT_INPUT = "podMetadata_Nov5_with_leaning.csv"
DEFAULT_BASE = Path("final_Transcripts_beforeNov5")
DEFAULT_OUTPUT = Path("deliverables/transcript_entities.csv")

try:
    import spacy
except ImportError as exc:  # pragma: no cover - environment dependent
    raise SystemExit(
        "spaCy is required for this script. Install it via `pip install spacy` "
        "and download the model with `python -m spacy download en_core_web_lg`."
    ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate top transcript named entities per political leaning."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT),
        help="Metadata CSV with ID, podName, and political_leaning columns.",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE,
        help="Folder containing per-podcast transcript directories.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="CSV file to store summarized entity counts.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of transcripts to process per spaCy batch.",
    )
    return parser.parse_args()


def expected_path(base: Path, pod_name: str, episode_id: str) -> Path:
    return base / pod_name / f"trans_{episode_id}.txt"


def chunk_transcripts(
    csv_path: Path, base_dir: Path, chunk_size: int
) -> Iterable[List[Tuple[str, Path]]]:
    """Yield batches of (leaning, transcript_path) tuples."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Input file not found: {csv_path}")
    batch: List[Tuple[str, Path]] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            episode_id = (row.get("ID") or "").strip()
            pod_name = (row.get("podName") or "").strip()
            leaning = (row.get("political_leaning") or "Unknown").strip() or "Unknown"
            if not episode_id or not pod_name:
                continue
            path = expected_path(base_dir, pod_name, episode_id)
            if not path.exists():
                continue
            batch.append((leaning, path))
            if len(batch) >= chunk_size:
                yield batch
                batch = []
    if batch:
        yield batch


def read_transcript(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def aggregate_entities(
    csv_path: Path, base_dir: Path, batch_size: int, nlp: "spacy.Language"
) -> Dict[str, Counter]:
    counts: Dict[str, Counter] = defaultdict(Counter)
    processed = 0
    for chunk in chunk_transcripts(csv_path, base_dir, batch_size):
        texts = (read_transcript(path) for _, path in chunk)
        for (leaning, _), doc in zip(chunk, nlp.pipe(texts, batch_size=batch_size)):
            for ent in doc.ents:
                text = ent.text.strip()
                if not text:
                    continue
                counts[leaning][(text, ent.label_)] += 1
            processed += 1
    if processed == 0:
        raise ValueError("No transcripts were available for processing.")
    print(f"Processed {processed} transcripts with available files.")
    return counts


def save_summary(counts: Dict[str, Counter], output: Path, top_n: int = 10) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["political_leaning", "entity", "label", "count", "share_within_leaning"]
        )
        for leaning, counter in counts.items():
            total = sum(counter.values())
            if not total:
                continue
            top_items = sorted(
                counter.items(), key=lambda item: (item[1], item[0][0]), reverse=True
            )[:top_n]
            for (entity, label), count in top_items:
                writer.writerow([leaning, entity, label, count, count / total])


def print_summary(counts: Dict[str, Counter], top_n: int = 10) -> None:
    for leaning, counter in counts.items():
        if not counter:
            continue
        total = sum(counter.values())
        print(f"\nTop entities for political leaning: {leaning}")
        print(f"{'Entity':40} {'Label':10} {'Count':>8} {'Share':>8}")
        top_items = sorted(
            counter.items(), key=lambda item: (item[1], item[0][0]), reverse=True
        )[:top_n]
        for (entity, label), count in top_items:
            share = count / total
            print(f"{entity[:38]:40} {label:10} {count:8d} {share:8.3f}")


def main() -> None:
    args = parse_args()
    try:
        nlp = spacy.load("en_core_web_lg", disable=["tagger", "parser", "lemmatizer"])
    except OSError as exc:  # pragma: no cover - env specific
        raise SystemExit(
            "The spaCy model 'en_core_web_lg' is not installed. "
            "Install it with `python -m spacy download en_core_web_lg`."
        ) from exc

    counts = aggregate_entities(args.input, args.base_dir, args.batch_size, nlp)
    save_summary(counts, args.output)
    print(f"Saved transcript entity summary to {args.output}")
    print_summary(counts)


if __name__ == "__main__":
    main()
