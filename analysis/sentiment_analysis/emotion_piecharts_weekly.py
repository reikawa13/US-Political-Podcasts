#!/usr/bin/env python3
"""Create weekly-average emotion pie charts (excluding Neutral).

Inputs:
  - analysis/sentiment_analysis/emotion_scores_weekly.csv
  - analysis/sentiment_analysis/emotion_scores_weekly_by_leaning.csv

Outputs:
  - analysis/sentiment_analysis/emotion_piecharts_excluding_neutral/*.png
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import pandas as pd

DEFAULT_OVERALL_CSV = Path("analysis/sentiment_analysis/emotion_scores_weekly.csv")
DEFAULT_BY_LEANING_CSV = Path(
    "analysis/sentiment_analysis/emotion_scores_weekly_by_leaning.csv"
)
DEFAULT_OUT_DIR = Path("analysis/sentiment_analysis/emotion_piecharts_excluding_neutral")
DEFAULT_COMBINED_PNG = DEFAULT_OUT_DIR / "all_pies_combined.png"

TARGET_LEANINGS = ["Conservative", "Liberal", "Moderate"]
EMOTION_ORDER = [
    "Anger_Score",
    "Disgust_Score",
    "Fear_Score",
    "Joy_Score",
    "Sadness_Score",
    "Surprise_Score",
]
EMOTION_COLORS = {
    "Anger_Score": "#d73027",
    "Disgust_Score": "#1a9850",
    "Fear_Score": "#4575b4",
    "Joy_Score": "#fdae61",
    "Sadness_Score": "#74add1",
    "Surprise_Score": "#f46d43",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create pie charts for overall and each political leaning, "
            "excluding Neutral_Score."
        )
    )
    parser.add_argument("--overall-csv", type=Path, default=DEFAULT_OVERALL_CSV)
    parser.add_argument("--by-leaning-csv", type=Path, default=DEFAULT_BY_LEANING_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--combined-png", type=Path, default=DEFAULT_COMBINED_PNG)
    return parser.parse_args()


def find_score_cols(df: pd.DataFrame) -> list[str]:
    cols = [c for c in df.columns if c.endswith("_Score")]
    if not cols:
        raise SystemExit("No *_Score columns found.")
    return cols


def series_without_neutral(values: pd.Series) -> pd.Series:
    # Enforce a fixed emotion order across every chart for direct comparison.
    cleaned = values.reindex(EMOTION_ORDER)
    cleaned = cleaned.fillna(0)
    if cleaned.empty or float(cleaned.sum()) <= 0:
        raise SystemExit("No non-neutral positive emotion scores found for pie chart.")
    return cleaned


def pie_labels(index: pd.Index) -> list[str]:
    return [name.replace("_Score", "") for name in index]


def write_pie_chart(data: pd.Series, title: str, out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = [EMOTION_COLORS.get(name, "#bdbdbd") for name in data.index]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(
        data.values,
        labels=pie_labels(data.index),
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
        textprops={"fontsize": 15},
    )
    ax.set_title(title, fontsize=18)
    ax.axis("equal")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def write_combined_pie_chart(charts: Dict[str, pd.Series], out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered_keys = ["overall", "liberal", "moderate", "conservative"]
    present_keys = [key for key in ordered_keys if key in charts]
    if not present_keys:
        raise SystemExit("No pie chart data available for combined output.")

    fig, axes = plt.subplots(2, 2, figsize=(14, 14))
    axes_list = list(axes.flat)

    for ax, key in zip(axes_list, present_keys):
        data = charts[key]
        colors = [EMOTION_COLORS.get(name, "#bdbdbd") for name in data.index]
        ax.pie(
            data.values,
            labels=pie_labels(data.index),
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
            counterclock=False,
            textprops={"fontsize": 15},
        )
        ax.set_title(f"{key.title()} - Neutral Excluded", fontsize=18)
        ax.axis("equal")

    for ax in axes_list[len(present_keys) :]:
        ax.axis("off")

    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def overall_means(overall_df: pd.DataFrame, score_cols: list[str]) -> pd.Series:
    return series_without_neutral(overall_df[score_cols].mean(numeric_only=True))


def leaning_means(
    by_df: pd.DataFrame, score_cols: list[str], leaning: str
) -> pd.Series | None:
    subset = by_df[by_df["political_leaning"] == leaning]
    if subset.empty:
        return None
    return series_without_neutral(subset[score_cols].mean(numeric_only=True))


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    overall_df = pd.read_csv(args.overall_csv)
    by_df = pd.read_csv(args.by_leaning_csv)

    score_cols = find_score_cols(overall_df)

    charts: Dict[str, pd.Series] = {
        "overall": overall_means(overall_df, score_cols),
    }

    for leaning in TARGET_LEANINGS:
        mean_series = leaning_means(by_df, score_cols, leaning)
        if mean_series is None:
            continue
        charts[leaning.lower()] = mean_series

    for key, values in charts.items():
        title = f"Average Emotion Distribution ({key.title()}) - Neutral Excluded"
        out_path = args.out_dir / f"{key}_pie.png"
        write_pie_chart(values, title, out_path)
        print(f"Wrote {out_path}")

    write_combined_pie_chart(charts, args.combined_png)
    print(f"Wrote {args.combined_png}")


if __name__ == "__main__":
    main()
