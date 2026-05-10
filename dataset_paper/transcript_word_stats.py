#!/usr/bin/env python3
"""Compute transcript word-count statistics and plot a CDF.

Mimics the structure of `check_transcripts.py` by walking the metadata CSV and
matching each row to a transcript file stored under:
    final_Transcripts_beforeNov5/<podName>/trans_<ID>.txt

For every transcript found, the script counts words (whitespace-delimited) and
reports the mean, median, and standard deviation of those counts. It also
generates a simple SVG CDF chart highlighting the 25th, 50th, 75th, and 95th
percentiles.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Iterable, List, Tuple

DEFAULT_INPUT = "podMetadata_Nov5_with_leaning.csv"
DEFAULT_BASE = Path("final_Transcripts_beforeNov5")
DEFAULT_CDF = Path("transcript_word_counts_cdf.svg")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate transcript word-count statistics and a CDF chart."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT),
        help="Metadata CSV with ID and podName columns (default: %(default)s).",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE,
        help="Directory containing per-podcast transcript folders (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_CDF,
        help="Path for the generated CDF SVG (default: %(default)s).",
    )
    return parser.parse_args()


def expected_path(base: Path, pod_name: str, episode_id: str) -> Path:
    return base / pod_name / f"trans_{episode_id}.txt"


def count_words(path: Path) -> int:
    total = 0
    with path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            total += len(line.split())
    return total


def collect_word_counts(csv_path: Path, base: Path) -> Tuple[List[int], List[Path]]:
    """Return word counts for available transcripts and list missing files."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Input file not found: {csv_path}")

    counts: List[int] = []
    missing: List[Path] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            episode_id = (row.get("ID") or "").strip()
            pod_name = (row.get("podName") or "").strip()
            if not episode_id or not pod_name:
                missing.append(Path(f"[missing fields] row {idx}"))
                continue
            transcript_path = expected_path(base, pod_name, episode_id)
            if not transcript_path.exists():
                missing.append(transcript_path)
                continue
            counts.append(count_words(transcript_path))
    if not counts:
        raise ValueError("No transcripts were found to compute word counts.")
    return counts, missing


def percentile(sorted_counts: List[int], pct: float) -> float:
    """Return percentile using linear interpolation."""
    if not sorted_counts:
        raise ValueError("Cannot compute percentile of empty data.")
    if len(sorted_counts) == 1:
        return float(sorted_counts[0])
    rank = pct * (len(sorted_counts) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_counts) - 1)
    weight = rank - lower
    return sorted_counts[lower] * (1 - weight) + sorted_counts[upper] * weight


def generate_cdf_svg(
    sorted_counts: List[int],
    output_path: Path,
    markers: dict[str, float],
) -> None:
    width, height = 900, 500
    margin = 60
    plot_width = width - 2 * margin
    plot_height = height - 2 * margin

    min_count = sorted_counts[0]
    max_count = sorted_counts[-1]
    span = max(max_count - min_count, 1)

    # Build polyline points for the empirical CDF
    points = []
    for idx, count in enumerate(sorted_counts, start=1):
        x = margin + ((count - min_count) / span) * plot_width
        y = height - margin - (idx / len(sorted_counts)) * plot_height
        points.append(f"{x:.2f},{y:.2f}")

    lines = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        '<style>text { font-family: Arial, sans-serif; font-size: 12px; }</style>',
        # Axes
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" '
        'stroke="#333" stroke-width="2"/>',
        f'<line x1="{margin}" y1="{height - margin}" x2="{width - margin}" '
        f'y2="{height - margin}" stroke="#333" stroke-width="2"/>',
        f'<text x="{width / 2}" y="25" font-size="18" text-anchor="middle">'
        "Transcript Word Count CDF</text>",
        f'<text x="{width / 2}" y="{height - 10}" text-anchor="middle">Word count</text>',
        f'<text x="20" y="{height / 2}" transform="rotate(-90 20,{height / 2})" '
        'text-anchor="middle">Cumulative share</text>',
        f'<polyline points="{" ".join(points)}" fill="none" stroke="#1976D2" stroke-width="2"/>',
    ]

    # Add quantile markers
    for label, value in markers.items():
        x = margin + ((value - min_count) / span) * plot_width
        lines.append(
            f'<line x1="{x:.2f}" y1="{height - margin}" x2="{x:.2f}" y2="{margin}" '
            'stroke="#FF7043" stroke-dasharray="4,4"/>'
        )
        lines.append(
            f'<text x="{x:.2f}" y="{margin - 5}" text-anchor="middle">{label}: {value:.0f}</text>'
        )

    # y-axis ticks for 25/50/75/95%
    for pct in (0.25, 0.5, 0.75, 0.95):
        y = height - margin - pct * plot_height
        lines.append(
            f'<line x1="{margin - 5}" y1="{y:.2f}" x2="{margin}" y2="{y:.2f}" stroke="#333"/>'
        )
        lines.append(
            f'<text x="{margin - 10}" y="{y + 4:.2f}" text-anchor="end">{int(pct * 100)}%</text>'
        )

    # x-axis labels for min/max
    lines.append(
        f'<text x="{margin}" y="{height - margin + 20}" text-anchor="start">{min_count}</text>'
    )
    lines.append(
        f'<text x="{width - margin}" y="{height - margin + 20}" text-anchor="end">{max_count}</text>'
    )

    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    word_counts, missing = collect_word_counts(args.input, args.base_dir)

    print(f"Processed {len(word_counts)} transcripts.")
    if missing:
        print(f"Skipped {len(missing)} entries with missing transcripts.")

    sorted_counts = sorted(word_counts)
    average = mean(sorted_counts)
    med = median(sorted_counts)
    std_dev = pstdev(sorted_counts)
    q25 = percentile(sorted_counts, 0.25)
    q50 = percentile(sorted_counts, 0.5)
    q75 = percentile(sorted_counts, 0.75)
    q95 = percentile(sorted_counts, 0.95)

    print(f"Average word count : {average:.2f}")
    print(f"Median word count  : {med:.2f}")
    print(f"Std dev (population): {std_dev:.2f}")
    print(
        "Percentiles:\n"
        f"  25%: {q25:.2f}\n"
        f"  50%: {q50:.2f}\n"
        f"  75%: {q75:.2f}\n"
        f"  95%: {q95:.2f}"
    )

    markers = {"25%": q25, "50%": q50, "75%": q75, "95%": q95}
    generate_cdf_svg(sorted_counts, args.output, markers)
    print(f"CDF chart written to {args.output}")


if __name__ == "__main__":
    main()
