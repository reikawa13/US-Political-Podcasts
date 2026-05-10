#!/usr/bin/env python3
"""Plot weekly average emotion scores across time.

Inputs:
  - sentence_topics_remapped_with_emotions_sample.csv (needs ID + *_Score columns)
  - podMetadata_Nov5_with_leaning.csv (needs ID + date)

Outputs:
  - analysis/emotion_scores_weekly.csv
  - analysis/emotion_scores_weekly.png
  - analysis/emotion_scores_weekly_by_leaning.csv
  - analysis/emotion_plots_weekly_by_leaning/<leaning>.png
"""
# Usage: python3 analysis/emotion_trends_weekly.py --start-date 2023-01-01 --end-date 2024-11-05
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

import pandas as pd

DEFAULT_SENTENCE_CSV = Path("sentence_topics_remapped_with_emotions_sample.csv")
DEFAULT_META_CSV = Path("podMetadata_Nov5_with_leaning.csv")
DEFAULT_OUT_CSV = Path("analysis/emotion_scores_weekly.csv")
DEFAULT_OUT_PNG = Path("analysis/emotion_scores_weekly.png")
DEFAULT_BY_LEANING_CSV = Path("analysis/emotion_scores_weekly_by_leaning.csv")
DEFAULT_BY_LEANING_DIR = Path("analysis/emotion_plots_weekly_by_leaning")
DEFAULT_AVG_BY_LEANING_CSV = Path("analysis/emotion_scores_average_by_leaning.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a line graph of weekly average emotion scores."
    )
    parser.add_argument("--sentences", type=Path, default=DEFAULT_SENTENCE_CSV)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--output-plot", type=Path, default=DEFAULT_OUT_PNG)
    parser.add_argument("--by-leaning-csv", type=Path, default=DEFAULT_BY_LEANING_CSV)
    parser.add_argument(
        "--average-by-leaning-csv",
        type=Path,
        default=DEFAULT_AVG_BY_LEANING_CSV,
        help="Write overall average emotion scores per political leaning.",
    )
    parser.add_argument(
        "--start-date",
        default="2023-01-01",
        help="Earliest date to include (YYYY-MM-DD). Use empty to disable.",
    )
    parser.add_argument(
        "--end-date",
        default="2024-11-05",
        help="Latest date to include (YYYY-MM-DD). Use empty to disable.",
    )
    parser.add_argument(
        "--by-leaning-dir",
        type=Path,
        default=DEFAULT_BY_LEANING_DIR,
        help="Directory to write one plot per political leaning.",
    )
    return parser.parse_args()


def find_emotion_columns(columns: List[str]) -> List[str]:
    emotion_cols = [c for c in columns if c.endswith("_Score")]
    if not emotion_cols:
        raise SystemExit("No emotion score columns found (expected *_Score columns).")
    return sorted(emotion_cols)


def load_metadata(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {path}")
    meta = pd.read_csv(path, usecols=["ID", "date", "political_leaning"])
    meta["date"] = pd.to_datetime(meta["date"], errors="coerce", utc=True)
    meta = meta.dropna(subset=["ID", "date", "political_leaning"])
    if meta.empty:
        raise SystemExit("No usable metadata rows with ID, date, and political_leaning.")
    return meta


def load_sentences(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Sentence CSV not found: {path}")
    df = pd.read_csv(path)
    if "ID" not in df.columns:
        raise SystemExit("Sentence CSV must include an ID column.")
    return df


def compute_weekly_means(df: pd.DataFrame, emotion_cols: List[str]) -> pd.DataFrame:
    df = df.copy()
    df["week"] = df["date"].dt.to_period("W-MON").dt.start_time
    weekly = (
        df.groupby("week", as_index=False)[emotion_cols]
        .mean(numeric_only=True)
        .sort_values("week")
    )
    if weekly.empty:
        raise SystemExit("No weekly averages produced after grouping.")
    return weekly


def write_weekly_csv(path: Path, weekly: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = weekly.copy()
    out["week"] = out["week"].dt.date.astype(str)
    out.to_csv(path, index=False)


def compute_weekly_means_by_leaning(
    df: pd.DataFrame, emotion_cols: List[str]
) -> pd.DataFrame:
    df = df.copy()
    df["week"] = df["date"].dt.to_period("W-MON").dt.start_time
    weekly = (
        df.groupby(["week", "political_leaning"], as_index=False)[emotion_cols]
        .mean(numeric_only=True)
        .sort_values(["political_leaning", "week"])
    )
    if weekly.empty:
        raise SystemExit("No weekly averages by leaning produced after grouping.")
    return weekly


def compute_overall_means_by_leaning(
    df: pd.DataFrame, emotion_cols: List[str]
) -> pd.DataFrame:
    overall = (
        df.groupby("political_leaning", as_index=False)[emotion_cols]
        .mean(numeric_only=True)
        .sort_values("political_leaning")
    )
    if overall.empty:
        raise SystemExit("No overall averages by leaning produced after grouping.")
    return overall


def apply_date_window(
    df: pd.DataFrame, start_date: pd.Timestamp | None, end_date: pd.Timestamp | None
) -> pd.DataFrame:
    if start_date is not None:
        df = df[df["date"] >= start_date]
    if end_date is not None:
        df = df[df["date"] <= end_date]
    return df


def normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = df["date"].dt.tz_convert("UTC").dt.tz_localize(None)
    return df


def preferred_leaning_order(found: Iterable[str]) -> List[str]:
    found_set = {f for f in found if isinstance(f, str) and f.strip()}
    preferred = ["Liberal", "Moderate", "Conservative"]
    ordered = [p for p in preferred if p in found_set]
    remainder = sorted(found_set - set(preferred))
    return ordered + remainder


def leaning_slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def plot_weekly(weekly: pd.DataFrame, emotion_cols: List[str], out_path: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - plotting is best effort
        raise SystemExit(f"Matplotlib is required for plotting: {exc}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    for col in emotion_cols:
        ax.plot(weekly["week"], weekly[col], label=col.replace("_Score", ""))

    ax.set_title("Weekly Average Emotion Scores")
    ax.set_xlabel("Week")
    ax.set_ylabel("Average Score")
    ax.grid(True, alpha=0.3)
    ax.legend(ncol=3, frameon=False)

    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_by_leaning(
    weekly_by_leaning: pd.DataFrame,
    emotion_cols: List[str],
    out_dir: Path,
) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for leaning in preferred_leaning_order(weekly_by_leaning["political_leaning"]):
        subset = weekly_by_leaning[weekly_by_leaning["political_leaning"] == leaning]
        if subset.empty:
            continue
        out_path = out_dir / f"{leaning_slug(leaning)}.png"
        plot_weekly(subset, emotion_cols, out_path)
        written.append(out_path)
    return written


def main() -> None:
    args = parse_args()

    sentences = load_sentences(args.sentences)
    emotion_cols = find_emotion_columns(sentences.columns.tolist())
    if "political_leaning" in sentences.columns:
        sentences = sentences.drop(columns=["political_leaning"])

    meta = load_metadata(args.metadata)
    df = sentences.merge(meta, on="ID", how="left", validate="many_to_one")

    missing_dates = df["date"].isna().sum()
    if missing_dates:
        print(f"Rows skipped due to missing metadata dates: {missing_dates}")
    df = df.dropna(subset=["date"])

    df = normalize_dates(df)
    start_date = pd.to_datetime(args.start_date) if args.start_date else None
    end_date = pd.to_datetime(args.end_date) if args.end_date else None
    df = apply_date_window(df, start_date, end_date)

    weekly = compute_weekly_means(df, emotion_cols)
    write_weekly_csv(args.output_csv, weekly)
    plot_weekly(weekly, emotion_cols, args.output_plot)

    weekly_by_leaning = compute_weekly_means_by_leaning(df, emotion_cols)
    write_weekly_csv(args.by_leaning_csv, weekly_by_leaning)
    written_plots = plot_by_leaning(weekly_by_leaning, emotion_cols, args.by_leaning_dir)

    overall_by_leaning = compute_overall_means_by_leaning(df, emotion_cols)
    args.average_by_leaning_csv.parent.mkdir(parents=True, exist_ok=True)
    overall_by_leaning.to_csv(args.average_by_leaning_csv, index=False)

    print(f"Wrote weekly averages: {args.output_csv}")
    print(f"Wrote plot: {args.output_plot}")
    print(f"Wrote weekly averages by leaning: {args.by_leaning_csv}")
    print(f"Wrote overall averages by leaning: {args.average_by_leaning_csv}")
    if written_plots:
        print("Wrote leaning plots:")
        for path in written_plots:
            print(f"  - {path}")


if __name__ == "__main__":
    main()
