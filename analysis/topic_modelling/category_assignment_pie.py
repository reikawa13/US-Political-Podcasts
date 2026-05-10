#!/usr/bin/env python3
"""Plot a pie chart of mapped thesis-category assignment counts."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "sentence_topics_remapped_with_emotions.csv"
DEFAULT_OUTPUT = SCRIPT_DIR / "category_assignment_pie.png"
CATEGORY_SEP = " | "

COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
]


def load_category_counts(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = (row.get("thesis_categories") or "").strip()
            if not raw or raw == "Unmapped":
                continue
            categories = [part.strip() for part in raw.split(CATEGORY_SEP) if part.strip()]
            for category in categories:
                counts[category] += 1
    return counts


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    counts = load_category_counts(DEFAULT_INPUT)
    if not counts:
        raise SystemExit("No mapped thesis categories found.")

    labels = []
    values = []
    total = sum(counts.values())
    for category, count in counts.most_common():
        pct = 100 * count / total
        labels.append(f"{category}\n{count:,} ({pct:.1f}%)")
        values.append(count)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.pie(
        values,
        labels=labels,
        colors=COLORS[: len(values)],
        startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": "white", "linewidth": 1},
        textprops={"fontsize": 13.5},
    )
    ax.set_title("Mapped Thesis Category Assignments", fontsize=21)
    fig.tight_layout()
    fig.savefig(DEFAULT_OUTPUT, dpi=200)
    plt.close(fig)

    print(f"Wrote pie chart to {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()
