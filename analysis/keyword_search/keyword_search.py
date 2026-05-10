#!/usr/bin/env python3
"""Count immigration-related keywords in podcast transcripts.

For each episode, the script expects a transcript at:
    <base-dir>/<podName>/trans_<ID>.txt

Usage examples:
  python keyword_search.py --limit-per-pod 5
  python keyword_search.py --limit-per-pod 5 --with-sentences
  python keyword_search.py --base-dir final_Transcripts_beforeNov5 --output-csv deliverables/keyword_counts_by_episode.csv
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

DEFAULT_CSV = "podMetadata_Nov5_with_leaning.csv"
DEFAULT_BASE = Path("final_Transcripts_beforeNov5")
DEFAULT_OUT = Path("deliverables/keyword_counts_by_episode.csv")
DEFAULT_SENTENCE_DIR = Path("immigration sentences")

KEYWORDS: List[Tuple[str, str]] = [
    ("immigrant", "immigrant"),
    ("immigrants", "immigrants"),
    ("immigration", "immigration"),
    ("migrant", "migrant"),
    ("migrants", "migrants"),
    ("migration", "migration"),
    ("illegals", "illegals"),
    ("undocumented", "undocumented"),
    ("refugee", "refugee"),
    ("refugees", "refugees"),
    ("guest worker", "guest worker"),
    ("guest workers", "guest workers"),
    ("asylum seeker", "asylum seeker"),
    ("asylum seekers", "asylum seekers"),
    ("illegal alien", "illegal alien"),
    ("illegal aliens", "illegal aliens"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count keyword hits in transcripts by episode."
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
        help="Per-episode keyword counts CSV.",
    )
    parser.add_argument(
        "--sentence-dir",
        type=Path,
        default=DEFAULT_SENTENCE_DIR,
        help="Directory for per-podcast sentence-level keyword hits CSVs.",
    )
    parser.add_argument(
        "--with-sentences",
        action="store_true",
        help="Also output sentence-level keyword hits.",
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
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def compile_patterns() -> List[Tuple[str, re.Pattern]]:
    compiled: List[Tuple[str, re.Pattern]] = []
    for label, phrase in KEYWORDS:
        if " " in phrase:
            parts = phrase.split()
            pattern = r"\b" + r"\s+".join(map(re.escape, parts)) + r"\b"
        else:
            pattern = r"\b" + re.escape(phrase) + r"\b"
        compiled.append((label, re.compile(pattern, re.IGNORECASE)))
    return compiled


def normalize_text(text: str) -> str:
    text = text.replace("\u00A0", " ")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2019", "'")
    return re.sub(r"\s+", " ", text)


def split_sentences(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in parts if s.strip()]


def count_keywords_in_transcript(
    path: Path, patterns: List[Tuple[str, re.Pattern]]
) -> Dict[str, int]:
    counts = {label: 0 for label, _ in patterns}
    with path.open() as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 3)
            text = parts[3] if len(parts) >= 4 else line
            if not text:
                continue
            text = normalize_text(text)
            for label, regex in patterns:
                counts[label] += sum(1 for _ in regex.finditer(text))
    return counts


def write_episode_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keyword_labels = [label for label, _ in KEYWORDS]
    keyword_cols = [label.replace(" ", "_") for label in keyword_labels]
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "ID",
                "podName",
                "transcript_found",
                "total_keyword_hits",
                *keyword_cols,
            ]
        )
        for row in rows:
            out = [
                row["ID"],
                row["podName"],
                row["transcript_found"],
                row["total_keyword_hits"],
            ]
            for label in keyword_labels:
                out.append(row[label])
            writer.writerow(out)


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w\- ]+", "", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "unknown_podcast"


def write_sentence_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keyword_labels = [label for label, _ in KEYWORDS]
    keyword_cols = [label.replace(" ", "_") for label in keyword_labels]
    header = [
        "ID",
        "podName",
        "speaker_id",
        "sentence_prev",
        "sentence",
        "sentence_next",
        "matched_keywords",
        *keyword_cols,
    ]

    def format_csv_field(value: object, force_quote: bool = False) -> str:
        text = "" if value is None else str(value)
        needs_quote = force_quote or any(ch in text for ch in [",", '"', "\n", "\r"])
        if needs_quote:
            text = text.replace('"', '""')
            return f'"{text}"'
        return text

    with path.open("w", newline="") as f:
        f.write(",".join(header) + "\n")
        for row in rows:
            out = [
                row["ID"],
                row["podName"],
                row["speaker_id"],
                row["sentence_prev"],
                row["sentence"],
                row["sentence_next"],
                row["matched_keywords"],
            ]
            for label in keyword_labels:
                out.append(row.get(label, 0))

            formatted = []
            for idx, value in enumerate(out):
                force_quote = idx in {3, 4, 5, 6}
                formatted.append(format_csv_field(value, force_quote=force_quote))
            f.write(",".join(formatted) + "\n")


def write_sentence_csvs_by_pod(
    base_dir: Path, rows: List[Dict[str, object]]
) -> None:
    if not rows:
        return
    base_dir.mkdir(parents=True, exist_ok=True)
    rows_by_pod: Dict[str, List[Dict[str, object]]] = {}
    for row in rows:
        pod_name = str(row.get("podName", "")).strip()
        rows_by_pod.setdefault(pod_name, []).append(row)

    for pod_name, pod_rows in rows_by_pod.items():
        safe_name = sanitize_filename(pod_name)
        out_path = base_dir / f"{safe_name}_sentences.csv"
        write_sentence_csv(out_path, pod_rows)


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"CSV not found: {args.input}")
    if not args.base_dir.exists():
        raise FileNotFoundError(f"Transcript base directory not found: {args.base_dir}")

    patterns = compile_patterns()
    rows: List[Dict[str, object]] = []
    sentence_rows: List[Dict[str, object]] = []
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
            counts = count_keywords_in_transcript(path, patterns)
            total_hits = sum(counts.values())
            if args.with_sentences:
                with path.open() as f:
                    for line in f:
                        parts = line.rstrip("\n").split("\t", 3)
                        speaker_id = parts[2] if len(parts) >= 3 else ""
                        text = parts[3] if len(parts) >= 4 else line
                        text = normalize_text(text)
                        sentences = split_sentences(text)
                        for idx, sentence in enumerate(sentences):
                            sentence_counts: Dict[str, int] = {}
                            matched = []
                            for label, regex in patterns:
                                c = sum(1 for _ in regex.finditer(sentence))
                                if c:
                                    sentence_counts[label] = c
                                    matched.append(label)
                            if matched:
                                # Context is only kept when it's from the same speaker line.
                                if speaker_id:
                                    prev_sentence = (
                                        sentences[idx - 1] if idx > 0 else ""
                                    )
                                    next_sentence = (
                                        sentences[idx + 1]
                                        if idx + 1 < len(sentences)
                                        else ""
                                    )
                                else:
                                    prev_sentence = ""
                                    next_sentence = ""
                                sentence_rows.append(
                                    {
                                        "ID": episode_id,
                                        "podName": pod_name,
                                        "speaker_id": speaker_id,
                                        "sentence_prev": prev_sentence,
                                        "sentence": sentence,
                                        "sentence_next": next_sentence,
                                        "matched_keywords": "; ".join(matched),
                                        **sentence_counts,
                                    }
                                )
            processed += 1
        else:
            counts = {label: 0 for label, _ in patterns}
            total_hits = 0
            missing += 1

        rows.append(
            {
                "ID": episode_id,
                "podName": pod_name,
                "transcript_found": transcript_found,
                "total_keyword_hits": total_hits,
                **counts,
            }
        )
        per_pod_counts[pod_name] = per_pod_counts.get(pod_name, 0) + 1

    if not rows:
        raise SystemExit("No episodes found in metadata CSV.")

    write_episode_csv(args.output_csv, rows)
    if args.with_sentences:
        write_sentence_csvs_by_pod(args.sentence_dir, sentence_rows)
    print(f"Episodes processed with transcripts: {processed}")
    print(f"Missing transcripts: {missing}")
    print(f"Per-episode CSV: {args.output_csv}")
    if args.with_sentences:
        print(f"Sentence CSVs directory: {args.sentence_dir}")


if __name__ == "__main__":
    main()
