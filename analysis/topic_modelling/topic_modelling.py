"""Run BERTopic on immigration sentence CSVs and write topic outputs.

Usage example:
  python topic_modelling.py --input-dir immigration_sentences

Outputs (default under analysis/bertopic/):
  - topic_info.csv: per-topic summary from BERTopic
  - sentence_topics.csv: per-sentence topic assignments (+ metadata)

GPU:
  Add --use-gpu to run embeddings on CUDA, or --device cuda:0 / mps to override.

Tests:
  No automated tests for this script; run with --limit-files N for a quick smoke check.
"""

# CLI behavior (summary):
# - Inputs: use --input (single CSV/TXT) or --input-dir (directory of *_sentences.csv).
# - Column selection: --column to pick a sentence column; otherwise auto-detect.
# - Context: --combine-context/--no-combine-context and --context-columns to stitch prev/next.
# - Filtering: add --filter-keywords to enable keyword filtering (no filtering by default).
# - Topic settings: --min-topic-size controls BERTopic min cluster size; --top-n controls stdout preview.
# - Hardware: --use-gpu or --device to select embedding device.
# - Outputs: --output-dir for CSVs; --model-dir to save BERTopic model.

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from bertopic import BERTopic
from sentence_transformers import SentenceTransformer

# 1. Your Academic Seed List (The "borrowed" claims)
# Format: A list of lists, where each sub-list contains keywords for one claim.
# Example based on typical immigration literature:
academic_seed_topics = [
    ["diversity", "perspectives", "language", "national identity", "religion"],  # Culture
    ["labor market", "public finance", "healthcare", "housing", "education"],  # Economy
    ["discrimination", "family", "human rights", "racism"],  # Human Rights
    ["political parties", "politics", "the white house", "president"],  # Political
    ["crime", "terrorism"],  # Security
]

DEFAULT_INPUT = Path("analysis/immigration_sentences.csv")
DEFAULT_INPUT_DIR = Path("immigration_sentences")
DEFAULT_OUTPUT_DIR = Path("analysis/bertopic")
DEFAULT_COLUMN_CANDIDATES = ("sentence", "text", "utterance", "line", "transcript")
DEFAULT_CONTEXT_COLUMNS = ("sentence_prev", "sentence", "sentence_next")
DEFAULT_FILTER_KEYWORDS = (
    "immigration",
    "immigrant",
    "migrant",
    "migrants",
    "asylum",
    "refugee",
    "refugees",
    "border",
    "deportation",
    "visa",
    "ice",
    "cbp",
    "daca",
    "undocumented",
    "illegal",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run BERTopic on immigration-related sentences with seed topics."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Input CSV (with a sentence column) or TXT (one sentence per line).",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing <podcast_series>_sentences.csv files.",
    )
    parser.add_argument(
        "--limit-files",
        type=int,
        default=0,
        help="Limit processing to N *_sentences.csv files from the input directory.",
    )
    parser.add_argument(
        "--column",
        type=str,
        default="",
        help="CSV column containing sentences (auto-detect if omitted).",
    )
    parser.add_argument(
        "--combine-context",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Combine sentence_prev + sentence + sentence_next when available.",
    )
    parser.add_argument(
        "--context-columns",
        nargs=3,
        default=list(DEFAULT_CONTEXT_COLUMNS),
        help="Three CSV columns to combine as context when --combine-context is set.",
    )
    parser.add_argument(
        "--filter-keywords",
        nargs="*",
        default=[],
        help="Keywords to keep sentences (case-insensitive). Omit to disable filtering.",
    )
    parser.add_argument(
        "--min-topic-size",
        type=int,
        default=15,
        help="Minimum topic size passed to BERTopic.",
    )
    parser.add_argument(
        "--use-gpu",
        action="store_true",
        help="Use GPU for embeddings (CUDA) if available.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="",
        help="Embedding device override (e.g., 'cuda', 'cuda:0', 'mps').",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write topic outputs.",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path(""),
        help="Optional path to save the BERTopic model (file or directory).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=15,
        help="Number of topics to print to stdout.",
    )
    return parser.parse_args()


def iter_txt_sentences(path: Path) -> Iterable[str]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            sentence = line.strip()
            if sentence:
                yield sentence


def pick_sentence_column(fieldnames: Sequence[str], preferred: str) -> str:
    if preferred:
        if preferred in fieldnames:
            return preferred
        raise ValueError(f"Column '{preferred}' not found in CSV header.")
    for candidate in DEFAULT_COLUMN_CANDIDATES:
        if candidate in fieldnames:
            return candidate
    raise ValueError(
        "No sentence column found. Provide --column with the sentence field name."
    )


def normalize_space(text: str) -> str:
    return " ".join(text.split())


def combine_context(row: Dict[str, str], columns: Sequence[str]) -> str:
    parts: List[str] = []
    for column in columns:
        value = (row.get(column) or "").strip()
        if value:
            parts.append(value)
    return normalize_space(" ".join(parts))


def extract_sentence(
    row: Dict[str, str],
    fieldnames: Sequence[str],
    column: str,
    use_context: bool,
    context_columns: Sequence[str],
) -> Tuple[str, str]:
    center = ""
    if "sentence" in fieldnames:
        center = (row.get("sentence") or "").strip()
    if use_context and all(col in fieldnames for col in context_columns):
        combined = combine_context(row, context_columns)
        return combined, center
    column = pick_sentence_column(fieldnames, column)
    return (row.get(column) or "").strip(), center


def iter_csv_sentences(
    path: Path,
    column: str,
    use_context: bool,
    context_columns: Sequence[str],
) -> Iterable[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV is missing a header row.")
        fieldnames = reader.fieldnames
        for row in reader:
            sentence, center = extract_sentence(
                row, fieldnames, column, use_context, context_columns
            )
            sentence = sentence.strip()
            if not sentence:
                continue
            payload = {
                "sentence": sentence,
                "center_sentence": center,
                "id": (row.get("ID") or "").strip(),
                "podName": (row.get("podName") or "").strip(),
                "speaker_id": (row.get("speaker_id") or "").strip(),
            }
            yield payload


def load_sentences(
    path: Path,
    input_dir: Path,
    column: str,
    use_context: bool,
    context_columns: Sequence[str],
    limit_files: int,
) -> List[Dict[str, str]]:
    if path.exists() and path.is_dir():
        input_dir = path
    if input_dir.exists():
        rows: List[Dict[str, str]] = []
        csv_paths = sorted(input_dir.glob("*_sentences.csv"))
        if not csv_paths:
            raise FileNotFoundError(
                f"No *_sentences.csv files found in directory: {input_dir}"
            )
        if limit_files and limit_files > 0:
            csv_paths = csv_paths[:limit_files]
        for csv_path in csv_paths:
            rows.extend(
                list(iter_csv_sentences(csv_path, column, use_context, context_columns))
            )
        if rows:
            return rows
        raise SystemExit(
            "Found sentence CSV files but no rows were loaded. "
            "Check --column / --combine-context settings and CSV headers."
        )
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if path.suffix.lower() in {".txt", ".text"}:
        return [{"sentence": s} for s in iter_txt_sentences(path)]
    if path.suffix.lower() == ".csv":
        return list(iter_csv_sentences(path, column, use_context, context_columns))
    raise ValueError("Unsupported input format. Use .csv, .txt, or a directory.")


def is_immigration_related(sentence: str, keywords: Sequence[str]) -> bool:
    lowered = sentence.lower()
    return any(keyword in lowered for keyword in keywords)


def write_sentence_topics(
    path: Path, rows: Sequence[Dict[str, str]], topics: Sequence[int], probs
) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "sentence",
                "center_sentence",
                "topic",
                "probability",
                "ID",
                "podName",
                "speaker_id",
            ]
        )
        if probs is None:
            for row, topic in zip(rows, topics):
                writer.writerow(
                    [
                        row.get("sentence", ""),
                        row.get("center_sentence", ""),
                        topic,
                        "",
                        row.get("id", ""),
                        row.get("podName", ""),
                        row.get("speaker_id", ""),
                    ]
                )
            return
        for idx, (row, topic) in enumerate(zip(rows, topics)):
            prob_row = probs[idx] if probs is not None else None
            probability = float(max(prob_row)) if prob_row is not None else ""
            writer.writerow(
                [
                    row.get("sentence", ""),
                    row.get("center_sentence", ""),
                    topic,
                    probability,
                    row.get("id", ""),
                    row.get("podName", ""),
                    row.get("speaker_id", ""),
                ]
            )


def main() -> None:
    args = parse_args()
    rows = load_sentences(
        args.input,
        args.input_dir,
        args.column,
        args.combine_context,
        args.context_columns,
        args.limit_files,
    )
    if not rows:
        raise SystemExit("No sentences found in input.")

    if args.filter_keywords:
        rows = [
            row
            for row in rows
            if is_immigration_related(row.get("sentence", ""), args.filter_keywords)
        ]
        if not rows:
            raise SystemExit(
                "No sentences matched the filter keywords. "
                "Use --no-filter or adjust --filter-keywords."
            )

    # 2. Initialize the Model with Seeds
    # usage of 'seed_topic_list' tells the model: "Look for these patterns first."
    embedding_model = "all-MiniLM-L6-v2"
    if args.device or args.use_gpu:
        device = args.device if args.device else "cuda"
        embedding_model = SentenceTransformer(embedding_model, device=device)

    topic_model = BERTopic(
        seed_topic_list=academic_seed_topics,
        embedding_model=embedding_model,  # Fast and accurate standard model
        min_topic_size=args.min_topic_size,
        calculate_probabilities=True,
    )

    # 3. Fit the model to your "Immigration Only" sentences
    sentences = [row.get("sentence", "") for row in rows]
    topics, probs = topic_model.fit_transform(sentences)

    # ---------------- ADD STEP 3: CLEAN UP (START) ----------------
    # A. Check Outlier Count (Topic -1)
    freq = topic_model.get_topic_info()
    outlier_count = (
        freq.loc[freq["Topic"] == -1, "Count"].values[0]
        if -1 in freq["Topic"].values
        else 0
    )
    print(f"\n[Step 3] Original Outlier Count: {outlier_count} / {len(sentences)}")

    # B. Reduce Outliers (Soft Assignment)
    if outlier_count > 0:
        print("[Step 3] Reducing outliers with c-TF-IDF strategy (threshold=0.1)...")
        new_topics = topic_model.reduce_outliers(
            sentences,
            topics,
            strategy="c-tf-idf",
            threshold=0.1,
        )
        topic_model.update_topics(sentences, topics=new_topics)
        topics = new_topics
    # ---------------- ADD STEP 3: CLEAN UP (END) ----------------

    # Optional manual merging (after inspecting topic_info.csv):
    # Example: merge topics [4, 5] into 4
    # topic_model.merge_topics(sentences, topics, topics_to_merge=[4, 5])

    # 4. Inspect / persist the output
    args.output_dir.mkdir(parents=True, exist_ok=True)
    info = topic_model.get_topic_info()
    info.to_csv(args.output_dir / "topic_info.csv", index=False)
    write_sentence_topics(
        args.output_dir / "sentence_topics.csv", rows, topics, probs
    )

    if args.model_dir:
        model_path = args.model_dir
        if model_path.exists() and model_path.is_dir():
            model_path = model_path / "bertopic_model.pkl"
        elif model_path.suffix == "":
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model_path = model_path / "bertopic_model.pkl"
        else:
            model_path.parent.mkdir(parents=True, exist_ok=True)
        topic_model.save(str(model_path))
        print(f"Saved BERTopic model to: {model_path}")

    print(info.head(args.top_n))
    print(f"Saved topic info to: {args.output_dir / 'topic_info.csv'}")
    print(f"Saved sentence topics to: {args.output_dir / 'sentence_topics.csv'}")


if __name__ == "__main__":
    main()
