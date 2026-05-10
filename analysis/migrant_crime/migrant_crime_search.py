#!/usr/bin/env python3
"""Count occurrences of the phrase "migrant crime" in podcast transcripts.

For each episode, the script expects a transcript at:
    <base-dir>/<podName>/trans_<ID>.txt

Output:
  - Per-episode CSV with total hits and a migrant_crime column.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, Iterable

DEFAULT_CSV = "podMetadata_Nov5_with_leaning.csv"
DEFAULT_BASE = Path("final_Transcripts_beforeNov5")
DEFAULT_OUT = Path("analysis/migrant_crime_counts_by_episode_overall.csv")

PHRASE_LABEL = "migrant_crime"
PHRASE_TEXT = "migrant crime"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count phrase hits in transcripts by episode."
    )
    parser.add_argument("--input", type=Path, default=Path(DEFAULT_CSV))
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE,
        help="Base directory containing per-podcast transcript folders.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUT,
        help="Per-episode phrase counts CSV.",
    )
    parser.add_argument(
        "--phrase",
        type=str,
        default=PHRASE_TEXT,
        help="Phrase to count (case-insensitive, whitespace flexible).",
    )
    parser.add_argument(
        "--limit-per-pod",
        type=int,
        default=0,
        help="Limit processing to N episodes per podName (0 means no limit).",
    )
    return parser.parse_args()


def expected_transcript(base: Path, pod_name: str, episode_id: str) -> Path:
    return base / pod_name / f"trans_{episode_id}.txt"


def iter_metadata(csv_path: Path) -> Iterable[Dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def compile_phrase_pattern(phrase: str) -> re.Pattern:
    parts = [p for p in phrase.strip().split() if p]
    if not parts:
        raise ValueError("Phrase must contain at least one word.")
    pattern = r"\b" + r"\s+".join(map(re.escape, parts)) + r"\b"
    return re.compile(pattern, re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = text.replace("\u00A0", " ")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2019", "'")
    return re.sub(r"\s+", " ", text)


def count_phrase_in_transcript(path: Path, pattern: re.Pattern) -> int:
    total = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 3)
            text = parts[3] if len(parts) >= 4 else line
            if not text:
                continue
            text = normalize_text(text)
            total += sum(1 for _ in pattern.finditer(text))
    return total


def write_episode_csv(path: Path, rows: list[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "ID",
                "podName",
                "date",
                "political_leaning",
                "transcript_found",
                "total_keyword_hits",
                PHRASE_LABEL,
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["ID"],
                    row["podName"],
                    row.get("date", ""),
                    row.get("political_leaning", ""),
                    row["transcript_found"],
                    row["total_keyword_hits"],
                    row[PHRASE_LABEL],
                ]
            )


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"CSV not found: {args.input}")
    if not args.base_dir.exists():
        raise FileNotFoundError(f"Transcript base directory not found: {args.base_dir}")

    pattern = compile_phrase_pattern(args.phrase)
    rows: list[Dict[str, object]] = []
    processed = 0
    missing = 0
    per_pod_counts: Dict[str, int] = {}

    for row in iter_metadata(args.input):
        episode_id = (row.get("ID") or "").strip()
        pod_name = (row.get("podName") or "").strip()
        if not episode_id or not pod_name:
            continue

        if args.limit_per_pod:
            seen = per_pod_counts.get(pod_name, 0)
            if seen >= args.limit_per_pod:
                continue

        path = expected_transcript(args.base_dir, pod_name, episode_id)
        transcript_found = "yes" if path.exists() else "no"
        if transcript_found == "yes":
            hits = count_phrase_in_transcript(path, pattern)
            processed += 1
        else:
            hits = 0
            missing += 1

        rows.append(
            {
                "ID": episode_id,
                "podName": pod_name,
                "date": (row.get("date") or "").strip(),
                "political_leaning": (row.get("political_leaning") or "").strip(),
                "transcript_found": transcript_found,
                "total_keyword_hits": hits,
                PHRASE_LABEL: hits,
            }
        )
        per_pod_counts[pod_name] = per_pod_counts.get(pod_name, 0) + 1

    if not rows:
        raise SystemExit("No episodes found in metadata CSV.")

    write_episode_csv(args.output_csv, rows)
    print(f"Episodes processed with transcripts: {processed}")
    print(f"Missing transcripts: {missing}")
    print(f"Per-episode CSV: {args.output_csv}")


if __name__ == "__main__":
    main()
