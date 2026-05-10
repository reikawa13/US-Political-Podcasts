#!/usr/bin/env python3
"""Create pie charts of topic-category share within each sentiment and political leaning.

Input:
  - analysis/category_sentiment_by_leaning/category_sentiment_by_leaning.csv

Output:
  - analysis/category_sentiment_by_leaning/topic_category_pies_by_sentiment_and_leaning.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DEFAULT_CSV = Path(
    "analysis/category_sentiment_by_leaning/category_sentiment_by_leaning.csv"
)
DEFAULT_PNG = Path(
    "analysis/category_sentiment_by_leaning/"
    "topic_category_pies_by_sentiment_and_leaning.png"
)

TARGET_LEANINGS = ["Conservative", "Moderate", "Liberal"]
SENTIMENT_ORDER = [
    "Anger_Score",
    "Disgust_Score",
    "Fear_Score",
    "Joy_Score",
    "Sadness_Score",
    "Surprise_Score",
    "Neutral_Score",
]
CATEGORY_ORDER = [
    "Partisan Politics & Elections",
    "Border Enforcement & Policy",
    "Humanitarian & Asylum System",
    "Identity & Assimilation",
    "Crime & Security Narrative",
    "International Refugee Context",
    "Economic & Social Impact",
    "Viral Incidents & Culture War",
]
CATEGORY_COLORS = {
    "Partisan Politics & Elections": "#d73027",
    "Border Enforcement & Policy": "#fc8d59",
    "Humanitarian & Asylum System": "#fee08b",
    "Identity & Assimilation": "#d9ef8b",
    "Crime & Security Narrative": "#91cf60",
    "International Refugee Context": "#66c2a5",
    "Economic & Social Impact": "#3288bd",
    "Viral Incidents & Culture War": "#5e4fa2",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create topic-category pie charts for each political leaning and sentiment."
        )
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_PNG)
    parser.add_argument(
        "--exclude-neutral",
        action="store_true",
        help="Omit Neutral_Score and produce a 3x6 figure.",
    )
    return parser.parse_args()


def sentiment_label(column: str) -> str:
    return column.replace("_Score", "")


def prepare_weighted_counts(df: pd.DataFrame, sentiment_cols: list[str]) -> pd.DataFrame:
    weighted = df.copy()
    for col in sentiment_cols:
        weighted[col] = weighted["sentence_count"] * weighted[col]
    return weighted


def category_distribution(
    df: pd.DataFrame, leaning: str, sentiment_col: str
) -> pd.Series | None:
    subset = df[df["political_leaning"] == leaning]
    if subset.empty:
        return None

    grouped = (
        subset.groupby("thesis_category", as_index=True)[sentiment_col]
        .sum()
        .reindex(CATEGORY_ORDER)
        .fillna(0)
    )
    grouped = grouped[grouped > 0]
    if grouped.empty:
        return None
    return grouped / grouped.sum()


def sentence_count_by_leaning(df: pd.DataFrame) -> dict[str, int]:
    counts = df.groupby("political_leaning")["sentence_count"].sum()
    return {leaning: int(counts.get(leaning, 0)) for leaning in TARGET_LEANINGS}


def draw_figure(
    charts: dict[tuple[str, str], pd.Series],
    sentiments: list[str],
    sample_sizes: dict[str, int],
    out: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(
        nrows=len(TARGET_LEANINGS),
        ncols=len(sentiments),
        figsize=(3.8 * len(sentiments), 4.0 * len(TARGET_LEANINGS)),
    )

    if len(TARGET_LEANINGS) == 1 and len(sentiments) == 1:
        axes_grid = [[axes]]
    elif len(TARGET_LEANINGS) == 1:
        axes_grid = [axes]
    elif len(sentiments) == 1:
        axes_grid = [[ax] for ax in axes]
    else:
        axes_grid = axes

    legend_handles = None

    for row_idx, leaning in enumerate(TARGET_LEANINGS):
        for col_idx, sentiment in enumerate(sentiments):
            ax = axes_grid[row_idx][col_idx]
            data = charts.get((leaning, sentiment))
            if data is None:
                ax.axis("off")
                continue

            colors = [CATEGORY_COLORS.get(cat, "#bdbdbd") for cat in data.index]
            wedges, _, _ = ax.pie(
                data.values,
                colors=colors,
                autopct="%1.0f%%",
                startangle=90,
                counterclock=False,
                pctdistance=0.7,
                radius=1.12,
                textprops={"fontsize": 8},
            )
            if legend_handles is None:
                legend_handles = list(wedges)
            ax.set_title(
                f"{leaning}\n{sentiment_label(sentiment)}\n"
                f"n={sample_sizes.get(leaning, 0):,} sentences",
                fontsize=10,
            )
            ax.axis("equal")

    fig.suptitle(
        "Topic Category Share Within Each Sentiment and Political Leaning\n"
        "(weighted by sentence_count x sentiment score)",
        fontsize=16,
        y=0.995,
    )
    if legend_handles is not None:
        fig.legend(
            legend_handles,
            CATEGORY_ORDER,
            loc="lower center",
            ncol=4,
            fontsize=9,
            frameon=False,
            bbox_to_anchor=(0.5, 0.02),
        )
    fig.tight_layout(rect=(0, 0.08, 1, 0.96))
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.csv)

    sentiment_cols = [col for col in SENTIMENT_ORDER if col in df.columns]
    if args.exclude_neutral:
        sentiment_cols = [col for col in sentiment_cols if col != "Neutral_Score"]
    if not sentiment_cols:
        raise SystemExit("No sentiment columns found.")

    weighted = prepare_weighted_counts(df, sentiment_cols)
    sample_sizes = sentence_count_by_leaning(df)

    charts: dict[tuple[str, str], pd.Series] = {}
    for leaning in TARGET_LEANINGS:
        for sentiment_col in sentiment_cols:
            distribution = category_distribution(weighted, leaning, sentiment_col)
            if distribution is not None:
                charts[(leaning, sentiment_col)] = distribution

    args.out.parent.mkdir(parents=True, exist_ok=True)
    draw_figure(charts, sentiment_cols, sample_sizes, args.out)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
