#!/usr/bin/env python3
"""Count immigration-related keywords in podcast transcripts.

For each episode, the script expects a transcript at:
    <base-dir>/<podName>/trans_<ID>.txt

Each transcript line should have tab-separated fields:
    start_time\tend_time\tspeaker_id\ttext

Outputs:
  - Per-episode CSV with total keyword hits and per-keyword counts.
  - Line chart of keyword hits over time by political leaning.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

DEFAULT_CSV = "podMetadata_Nov5_with_leaning.csv"
DEFAULT_BASE = Path("final_Transcripts_beforeNov5")
DEFAULT_OUT = Path("deliverables/keyword_counts_by_episode.csv")
DEFAULT_PLOT = Path("deliverables/keyword_counts_by_leaning.png")
DEFAULT_PLOT_DATA = Path("deliverables/keyword_counts_by_leaning.csv")

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


@dataclass
class EpisodeResult:
    episode_id: str
    pod_name: str
    date_raw: str
    date_obj: Optional[object]
    political_leaning: str
    transcript_found: bool
    total_hits: int
    counts: Dict[str, int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count keyword hits in transcripts and plot over time."
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
        "--plot-output",
        type=Path,
        default=DEFAULT_PLOT,
        help="Line chart of keyword hits by leaning over time.",
    )
    parser.add_argument(
        "--plot-data-csv",
        type=Path,
        default=DEFAULT_PLOT_DATA,
        help="Aggregated data behind the line chart.",
    )
    parser.add_argument(
        "--limit-per-pod",
        type=int,
        default=0,
        help=(
            "Limit processing to N episodes per podName (0 means no limit). "
            "Useful for quick tests."
        ),
    )
    parser.add_argument(
        "--debug-episode",
        type=str,
        default="",
        help=(
            "If set, print the resolved transcript path and the first few lines "
            "read for this episode ID."
        ),
    )
    parser.add_argument(
        "--debug-lines",
        type=int,
        default=3,
        help="Number of transcript lines to print for --debug-episode.",
    )
    parser.add_argument(
        "--debug-hits",
        action="store_true",
        help="When combined with --debug-episode, print lines with keyword hits.",
    )
    return parser.parse_args()


def expected_transcript(base: Path, pod_name: str, episode_id: str) -> Path:
    return base / pod_name / f"trans_{episode_id}.txt"


def iter_metadata(csv_path: Path) -> Iterable[Dict[str, str]]:
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def normalize_leaning(value: str) -> str:
    val = (value or "").strip().lower()
    if val == "liberal":
        return "Liberal"
    if val == "moderate":
        return "Moderate"
    if val == "conservative":
        return "Conservative"
    return "Unknown"


def compile_patterns() -> List[Tuple[str, re.Pattern]]:
    compiled: List[Tuple[str, re.Pattern]] = []
    for label, phrase in KEYWORDS:
        if " " in phrase:
            parts = phrase.split()
            pattern = r"\\b" + r"\\s+".join(map(re.escape, parts)) + r"\\b"
        else:
            pattern = r"\\b" + re.escape(phrase) + r"\\b"
        compiled.append((label, re.compile(pattern, re.IGNORECASE)))
    return compiled


def count_keywords_in_transcript(
    path: Path,
    patterns: List[Tuple[str, re.Pattern]],
    debug_lines: int = 0,
    debug_hits: bool = False,
) -> Dict[str, int]:
    counts = {label: 0 for label, _ in patterns}
    with path.open() as f:
        for line_idx, line in enumerate(f, start=1):
            if debug_lines > 0 and line_idx <= debug_lines:
                print(f"[debug] line {line_idx}: {line.rstrip()}")
            parts = line.rstrip("\n").split("\t", 3)
            text = parts[3] if len(parts) >= 4 else line
            if not text:
                continue
            text = text.replace("\u00A0", " ")
            text = re.sub(r"\s+", " ", text)
            line_hits = []
            for label, regex in patterns:
                hit_count = sum(1 for _ in regex.finditer(text))
                if hit_count:
                    line_hits.append((label, hit_count))
                counts[label] += hit_count
            if debug_hits and line_hits:
                hits_summary = ", ".join(f"{label}={count}" for label, count in line_hits)
                print(f"[debug] hit line {line_idx}: {hits_summary} | {text}")
    return counts


def parse_date(date_str: str) -> Optional[object]:
    raw = (date_str or "").strip()
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).date()
    except Exception:
        return None


def write_episode_csv(path: Path, results: List[EpisodeResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keyword_labels = [label for label, _ in KEYWORDS]
    keyword_cols = [label.replace(" ", "_") for label in keyword_labels]
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "ID",
                "podName",
                "date",
                "political_leaning",
                "transcript_found",
                "total_keyword_hits",
                *keyword_cols,
            ]
        )
        for res in results:
            row = [
                res.episode_id,
                res.pod_name,
                res.date_raw,
                res.political_leaning,
                "yes" if res.transcript_found else "no",
                res.total_hits,
            ]
            for label in keyword_labels:
                row.append(res.counts.get(label, 0))
            writer.writerow(row)


def aggregate_by_date_and_leaning(
    results: List[EpisodeResult],
) -> Tuple[List[object], Dict[str, List[int]], List[Tuple[object, str, int]]]:
    data = defaultdict(lambda: defaultdict(int))
    for res in results:
        if not res.transcript_found:
            continue
        if res.date_obj is None:
            continue
        leaning = res.political_leaning
        if leaning not in {"Liberal", "Moderate", "Conservative"}:
            continue
        data[res.date_obj][leaning] += res.total_hits

    dates = sorted(data.keys())
    series: Dict[str, List[int]] = {
        "Liberal": [],
        "Moderate": [],
        "Conservative": [],
    }
    flat_rows: List[Tuple[object, str, int]] = []
    for date in dates:
        for leaning in series:
            count = data[date].get(leaning, 0)
            series[leaning].append(count)
            flat_rows.append((date, leaning, count))
    return dates, series, flat_rows


def write_plot_data_csv(path: Path, rows: List[Tuple[object, str, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "political_leaning", "total_keyword_hits"])
        for date, leaning, count in rows:
            writer.writerow([date, leaning, count])


def plot_counts_by_leaning(
    path: Path, dates: List[object], series: Dict[str, List[int]]
) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise SystemExit(
            "matplotlib is required to create the plot. "
            f"Install it or run without plotting. Error: {exc}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 5))
    plt.plot(dates, series["Liberal"], label="Liberal", linewidth=2)
    plt.plot(dates, series["Moderate"], label="Moderate", linewidth=2)
    plt.plot(dates, series["Conservative"], label="Conservative", linewidth=2)
    plt.xlabel("Date")
    plt.ylabel("Total keyword hits")
    plt.title("Immigration keyword hits over time by political leaning")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"CSV not found: {args.input}")
    if not args.base_dir.exists():
        raise FileNotFoundError(f"Transcript base directory not found: {args.base_dir}")

    patterns = compile_patterns()
    results: List[EpisodeResult] = []

    missing_files = 0
    processed = 0

    per_pod_counts: Dict[str, int] = defaultdict(int)
    for row in iter_metadata(args.input):
        episode_id = (row.get("ID") or "").strip()
        pod_name = (row.get("podName") or "").strip()
        if not episode_id or not pod_name:
            continue
        if args.limit_per_pod > 0 and per_pod_counts[pod_name] >= args.limit_per_pod:
            continue

        path = expected_transcript(args.base_dir, pod_name, episode_id)
        transcript_found = path.exists()
        if transcript_found:
            if args.debug_episode and episode_id == args.debug_episode:
                print(f"[debug] episode {episode_id} transcript path: {path}")
                counts = count_keywords_in_transcript(
                    path,
                    patterns,
                    debug_lines=args.debug_lines,
                    debug_hits=args.debug_hits,
                )
            else:
                counts = count_keywords_in_transcript(path, patterns)
            total_hits = sum(counts.values())
            processed += 1
        else:
            print(f"Missing transcript: {path}")
            counts = {label: 0 for label, _ in patterns}
            total_hits = 0
            missing_files += 1

        date_raw = (row.get("date") or "").strip()
        date_obj = parse_date(date_raw)
        normalized_leaning = normalize_leaning(row.get("political_leaning") or "")
        if normalized_leaning == "Unknown":
            print(
                f"Unknown political leaning for {pod_name} (ID {episode_id}): "
                f"{row.get('political_leaning')!r}"
            )
        results.append(
            EpisodeResult(
                episode_id=episode_id,
                pod_name=pod_name,
                date_raw=date_raw,
                date_obj=date_obj,
                political_leaning=normalized_leaning,
                transcript_found=transcript_found,
                total_hits=total_hits,
                counts=counts,
            )
        )
        per_pod_counts[pod_name] += 1

    if not results:
        raise SystemExit("No episodes found in metadata CSV.")

    write_episode_csv(args.output_csv, results)

    dates, series, flat_rows = aggregate_by_date_and_leaning(results)
    write_plot_data_csv(args.plot_data_csv, flat_rows)
    if dates:
        plot_counts_by_leaning(args.plot_output, dates, series)

    print(f"Episodes processed with transcripts: {processed}")
    print(f"Missing transcripts: {missing_files}")
    print(f"Per-episode CSV: {args.output_csv}")
    print(f"Plot data CSV: {args.plot_data_csv}")
    if dates:
        print(f"Plot saved: {args.plot_output}")
    else:
        print("No dated transcripts available to plot.")


if __name__ == "__main__":
    main()
