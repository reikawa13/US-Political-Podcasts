#!/usr/bin/env python3
"""Plot monthly average emotion scores across time.

Inputs:
  - sentence_topics_remapped_with_emotions_sample.csv (needs ID + *_Score columns)
  - podMetadata_Nov5_with_leaning.csv (needs ID + date)

Outputs:
  - analysis/emotion_scores_monthly.csv
  - analysis/emotion_scores_monthly.png
  - analysis/emotion_scores_monthly_by_leaning.csv
  - analysis/emotion_plots_by_leaning/<leaning>.png
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

import pandas as pd

DEFAULT_SENTENCE_CSV = Path("sentence_topics_remapped_with_emotions_sample.csv")
DEFAULT_META_CSV = Path("podMetadata_Nov5_with_leaning.csv")
DEFAULT_OUT_CSV = Path("analysis/emotion_scores_monthly.csv")
DEFAULT_OUT_PNG = Path("analysis/emotion_scores_monthly.png")
DEFAULT_BY_LEANING_CSV = Path("analysis/emotion_scores_monthly_by_leaning.csv")
DEFAULT_BY_LEANING_DIR = Path("analysis/emotion_plots_by_leaning")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a line graph of monthly average emotion scores."
    )
    parser.add_argument("--sentences", type=Path, default=DEFAULT_SENTENCE_CSV)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--output-plot", type=Path, default=DEFAULT_OUT_PNG)
    parser.add_argument("--by-leaning-csv", type=Path, default=DEFAULT_BY_LEANING_CSV)
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


def compute_monthly_means(df: pd.DataFrame, emotion_cols: List[str]) -> pd.DataFrame:
    df = df.copy()
    # Normalize to naive UTC timestamps to avoid timezone warnings during period conversion.
    df["date"] = df["date"].dt.tz_convert("UTC").dt.tz_localize(None)
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        df.groupby("month", as_index=False)[emotion_cols]
        .mean(numeric_only=True)
        .sort_values("month")
    )
    if monthly.empty:
        raise SystemExit("No monthly averages produced after grouping.")
    return monthly


def write_monthly_csv(path: Path, monthly: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = monthly.copy()
    out["month"] = out["month"].dt.date.astype(str)
    out.to_csv(path, index=False)


def compute_monthly_means_by_leaning(
    df: pd.DataFrame, emotion_cols: List[str]
) -> pd.DataFrame:
    df = df.copy()
    df["date"] = df["date"].dt.tz_convert("UTC").dt.tz_localize(None)
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        df.groupby(["month", "political_leaning"], as_index=False)[emotion_cols]
        .mean(numeric_only=True)
        .sort_values(["political_leaning", "month"])
    )
    if monthly.empty:
        raise SystemExit("No monthly averages by leaning produced after grouping.")
    return monthly


def preferred_leaning_order(found: Iterable[str]) -> List[str]:
    found_set = {f for f in found if isinstance(f, str) and f.strip()}
    preferred = ["Liberal", "Moderate", "Conservative"]
    ordered = [p for p in preferred if p in found_set]
    remainder = sorted(found_set - set(preferred))
    return ordered + remainder


def leaning_slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def plot_monthly(monthly: pd.DataFrame, emotion_cols: List[str], out_path: Path) -> None:
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
        ax.plot(monthly["month"], monthly[col], label=col.replace("_Score", ""))

    ax.set_title("Monthly Average Emotion Scores")
    ax.set_xlabel("Month")
    ax.set_ylabel("Average Score")
    ax.grid(True, alpha=0.3)
    ax.legend(ncol=3, frameon=False)

    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate()

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_by_leaning(
    monthly_by_leaning: pd.DataFrame,
    emotion_cols: List[str],
    out_dir: Path,
) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for leaning in preferred_leaning_order(monthly_by_leaning["political_leaning"]):
        subset = monthly_by_leaning[monthly_by_leaning["political_leaning"] == leaning]
        if subset.empty:
            continue
        out_path = out_dir / f"{leaning_slug(leaning)}.png"
        plot_monthly(subset, emotion_cols, out_path)
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

    monthly = compute_monthly_means(df, emotion_cols)
    write_monthly_csv(args.output_csv, monthly)
    plot_monthly(monthly, emotion_cols, args.output_plot)

    monthly_by_leaning = compute_monthly_means_by_leaning(df, emotion_cols)
    write_monthly_csv(args.by_leaning_csv, monthly_by_leaning)
    written_plots = plot_by_leaning(monthly_by_leaning, emotion_cols, args.by_leaning_dir)

    print(f"Wrote monthly averages: {args.output_csv}")
    print(f"Wrote plot: {args.output_plot}")
    print(f"Wrote monthly averages by leaning: {args.by_leaning_csv}")
    if written_plots:
        print("Wrote leaning plots:")
        for path in written_plots:
            print(f"  - {path}")


if __name__ == "__main__":
    main()
