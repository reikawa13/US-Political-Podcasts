#!/usr/bin/env python3
"""Analyze transcript files associated with the metadata CSV.

For each episode, the script expects a transcript at:
    final_Transcripts_beforeNov5/<podName>/trans_<ID>.txt

Each transcript line should have tab-separated fields:
    start_time\tend_time\tspeaker_id\ttext

The script reports:
    - Histogram of number of distinct speakers per episode
    - Average words per speaker segment (across all segments)
    - Proportion of "very short" segments (duration < threshold seconds)
    - Percentage of episodes with at least N speakers
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

DEFAULT_CSV = "podMetadata_Nov5_with_leaning.csv"
DEFAULT_BASE = Path("final_Transcripts_beforeNov5")
DEFAULT_SHORT_THRESHOLD = 2.0  # seconds
DEFAULT_MIN_SPEAKERS = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute transcript statistics.")
    parser.add_argument("--input", type=Path, default=Path(DEFAULT_CSV))
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE,
        help="Base directory containing per-podcast transcript folders.",
    )
    parser.add_argument(
        "--short-threshold",
        type=float,
        default=DEFAULT_SHORT_THRESHOLD,
        help="Duration (seconds) below which a segment is considered very short.",
    )
    parser.add_argument(
        "--min-speakers",
        type=int,
        default=DEFAULT_MIN_SPEAKERS,
        help="Threshold for '# of episodes with ≥N speakers'.",
    )
    parser.add_argument(
        "--hist-output",
        type=Path,
        default=Path("deliverables/speaker_histogram.csv"),
        help="File to write histogram of speakers per episode.",
    )
    return parser.parse_args()


def expected_transcript(base: Path, pod_name: str, episode_id: str) -> Path:
    return base / pod_name / f"trans_{episode_id}.txt"


def iter_metadata(csv_path: Path) -> Iterable[Tuple[str, str]]:
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            episode_id = (row.get("ID") or "").strip()
            pod_name = (row.get("podName") or "").strip()
            if episode_id and pod_name:
                yield episode_id, pod_name


def analyze_transcript(path: Path, short_threshold: float) -> Dict[str, float]:
    speakers = set()
    total_segments = 0
    short_segments = 0
    total_words = 0

    with path.open() as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 4:
                continue
            try:
                start = float(parts[0])
                end = float(parts[1])
            except ValueError:
                continue
            speaker = parts[2].strip()
            text = parts[3].strip()

            speakers.add(speaker)
            total_segments += 1

            duration = max(0.0, end - start)
            if duration < short_threshold:
                short_segments += 1

            words = [tok for tok in text.split() if tok]
            total_words += len(words)

    return {
        "speakers": len(speakers),
        "segments": total_segments,
        "short_segments": short_segments,
        "words": total_words,
    }


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"CSV not found: {args.input}")
    if not args.base_dir.exists():
        raise FileNotFoundError(f"Transcript base directory not found: {args.base_dir}")

    hist = Counter()
    episodes_with_transcripts = 0
    missing_files = 0
    total_segments = 0
    total_short_segments = 0
    total_words = 0

    for episode_id, pod_name in iter_metadata(args.input):
        path = expected_transcript(args.base_dir, pod_name, episode_id)
        if not path.exists():
            missing_files += 1
            continue
        stats = analyze_transcript(path, args.short_threshold)
        if stats["segments"] == 0:
            continue
        episodes_with_transcripts += 1
        hist[stats["speakers"]] += 1
        total_segments += stats["segments"]
        total_short_segments += stats["short_segments"]
        total_words += stats["words"]

    if episodes_with_transcripts == 0:
        raise SystemExit("No transcripts processed. Check your paths.")

    avg_words_per_segment = total_words / total_segments if total_segments else 0
    short_segment_ratio = (
        total_short_segments / total_segments if total_segments else 0
    )
    at_least_n = sum(
        count for speakers, count in hist.items() if speakers >= args.min_speakers
    )
    pct_at_least_n = at_least_n / episodes_with_transcripts * 100

    args.hist_output.parent.mkdir(parents=True, exist_ok=True)
    with args.hist_output.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["speakers", "episode_count"])
        for speakers in sorted(hist):
            writer.writerow([speakers, hist[speakers]])

    print(f"Episodes processed: {episodes_with_transcripts}")
    print(f"Missing transcripts: {missing_files}")
    print(f"Average words per segment: {avg_words_per_segment:.2f}")
    print(f"Proportion of segments < {args.short_threshold}s: {short_segment_ratio:.3%}")
    print(
        f"Episodes with ≥{args.min_speakers} speakers: "
        f"{pct_at_least_n:.2f}% ({at_least_n}/{episodes_with_transcripts})"
    )
    print(f"Histogram saved to {args.hist_output}")


if __name__ == "__main__":
    main()
