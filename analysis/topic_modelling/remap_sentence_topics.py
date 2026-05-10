"""Remap sentence-level topic IDs into broader thesis categories.

Usage example:
  python3 remap_sentence_topics.py --input sentence_topics_sample.csv --output sentence_topics_remapped.csv

Notes:
  Adds political_leaning by podName via Top 100 CSV, with metadata CSV fallback.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List

# 1. SETUP THE TOPIC MAP
# Based on the specific CSV you provided, categorized topic IDs into larger groups.
# You can add more IDs to these lists if needed.
THESIS_MAP: Dict[str, List[int]] = {
    "Crime & Security Narrative": [
        7, 16, 22, 39, 43, 58, 82, 92, 107, 131, 139, 151, 158, 159,
        180, 210, 219, 222, 223, 224, 235, 246, 278, 289, 291, 298,
        311, 324, 338, 339, 371, 389, 402, 413, 440, 445, 478, 479,
    ],
    "Border Enforcement & Policy": [
        10, 11, 14, 20, 21, 25, 34, 60, 64, 70, 90, 97, 100, 133,
        150, 157, 163, 183, 184, 207, 246, 250, 252, 253, 266, 283,
        313, 317, 338, 366, 442, 446, 447, 452, 461, 474, 480, 490,
        494, 495, 498, 502, 504, 526, 543,
    ],
    "Economic & Social Impact": [
        29, 55, 69, 72, 81, 114, 135, 140, 147, 161, 162, 172, 193,
        201, 227, 263, 276, 292, 322, 350, 385, 398, 404, 419, 434,
        448, 449, 450, 529, 541,
    ],
    "Partisan Politics & Elections": [
        0, 1, 2, 4, 5, 8, 15, 35, 41, 42, 51, 61, 67, 83, 84, 108,
        118, 134, 141, 143, 165, 202, 203, 204, 205, 213, 214, 218,
        228, 230, 233, 236, 268, 271, 275, 301, 302, 332, 333, 334,
        345, 351, 374, 378, 380, 392, 411, 423, 427, 439, 453, 456,
        472, 488, 493, 499, 501, 511, 530, 546,
    ],
    "Viral Incidents & Culture War": [
        9, 12, 27, 47, 52, 59, 75, 99, 119, 169, 171, 173, 237, 241,
        259, 304, 306, 326, 352, 367, 417, 421, 422, 424, 432, 436,
        454, 457, 458, 477, 481, 491, 492, 518, 521, 533, 542, 545,
    ],
    "Humanitarian & Asylum System": [
        3, 18, 19, 23, 63, 74, 95, 117, 122, 144, 148, 149, 155, 187,
        188, 197, 208, 211, 212, 231, 239, 316, 343, 362, 363, 387,
        420, 455, 468, 482, 503, 510, 517, 531, 539,
    ],
    "International Refugee Context": [
        6, 33, 37, 39, 46, 80, 98, 113, 115, 121, 124, 125, 127, 129,
        152, 160, 166, 170, 191, 200, 217, 220, 225, 243, 254, 256,
        260, 280, 284, 315, 341, 358, 364, 375, 388, 416, 459, 465,
        469, 476, 515, 537, 544,
    ],
    "Identity & Assimilation": [
        18, 38, 53, 56, 65, 68, 77, 86, 88, 89, 94, 103, 104, 106,
        110, 128, 130, 177, 195, 196, 198, 199, 216, 226, 248, 249,
        267, 274, 279, 288, 294, 303, 307, 319, 320, 328, 335, 342,
        344, 349, 359, 360, 369, 393, 395, 399, 406, 470, 473, 548,
        552,
    ],
}

DEFAULT_TOP100_CSV = Path("../../Top_100_Podcasts_Nov5_with_Political_Leaning.csv")
DEFAULT_METADATA_CSV = Path("../../podMetadata_Nov5_with_leaning.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remap sentence topics into broader thesis categories."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input sentence_topics CSV (from topic_modelling.py).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("sentence_topics_remapped.csv"),
        help="Output CSV with added thesis_category column.",
    )
    parser.add_argument(
        "--topic-column",
        type=str,
        default="topic",
        help="Column name containing the topic ID.",
    )
    parser.add_argument(
        "--top100-csv",
        type=Path,
        default=DEFAULT_TOP100_CSV,
        help="Top-100 CSV used to map podName -> political leaning.",
    )
    parser.add_argument(
        "--top100-name-column",
        type=str,
        default="Podcast",
        help="Column in the top-100 CSV containing the series name.",
    )
    parser.add_argument(
        "--top100-leaning-column",
        type=str,
        default="Political Leaning",
        help="Column in the top-100 CSV containing the political leaning label.",
    )
    parser.add_argument(
        "--metadata-csv",
        type=Path,
        default=DEFAULT_METADATA_CSV,
        help="Metadata CSV used as a fallback podName -> political leaning map.",
    )
    parser.add_argument(
        "--metadata-name-column",
        type=str,
        default="podName",
        help="Column in the metadata CSV containing the series name.",
    )
    parser.add_argument(
        "--metadata-leaning-column",
        type=str,
        default="political_leaning",
        help="Column in the metadata CSV containing the political leaning label.",
    )
    parser.add_argument(
        "--unknown-label",
        type=str,
        default="Unmapped",
        help="Label to use when a topic ID is not in the map.",
    )
    return parser.parse_args()


def invert_map(topic_map: Dict[str, List[int]]) -> Dict[int, List[str]]:
    inverse: Dict[int, List[str]] = {}
    for label, topic_ids in topic_map.items():
        for topic_id in topic_ids:
            inverse.setdefault(topic_id, []).append(label)
    return inverse


def validate_map(topic_map: Dict[str, List[int]]) -> None:
    for label, topic_ids in topic_map.items():
        if not isinstance(label, str) or not label.strip():
            raise ValueError("All category labels must be non-empty strings.")
        if not all(isinstance(t, int) for t in topic_ids):
            raise ValueError(f"All topic IDs must be ints for category: {label}")


def iter_rows(path: Path) -> Iterable[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Input CSV is missing a header row.")
        for row in reader:
            yield row


def load_top100_map(path: Path, name_column: str, leaning_column: str) -> Dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return {}
        if name_column not in reader.fieldnames or leaning_column not in reader.fieldnames:
            raise ValueError(
                f"Top-100 CSV must include '{name_column}' and '{leaning_column}'."
            )
        mapping: Dict[str, str] = {}
        for row in reader:
            name = (row.get(name_column) or "").strip()
            leaning = (row.get(leaning_column) or "").strip()
            if name and leaning:
                mapping[name] = leaning
        return mapping


def load_metadata_map(
    path: Path, name_column: str, leaning_column: str
) -> Dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return {}
        if name_column not in reader.fieldnames or leaning_column not in reader.fieldnames:
            raise ValueError(
                f"Metadata CSV must include '{name_column}' and '{leaning_column}'."
            )
        mapping: Dict[str, str] = {}
        for row in reader:
            name = (row.get(name_column) or "").strip()
            leaning = (row.get(leaning_column) or "").strip()
            if name and leaning and name not in mapping:
                mapping[name] = leaning
        return mapping


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    validate_map(THESIS_MAP)
    inverse_map = invert_map(THESIS_MAP)
    leaning_map = load_top100_map(
        args.top100_csv, args.top100_name_column, args.top100_leaning_column
    )
    metadata_leaning_map = load_metadata_map(
        args.metadata_csv, args.metadata_name_column, args.metadata_leaning_column
    )

    rows = list(iter_rows(args.input))
    if not rows:
        raise SystemExit("No rows found in input CSV.")

    existing_fields = list(rows[0].keys())
    if "political_leaning" not in existing_fields:
        existing_fields.append("political_leaning")
    if "thesis_categories" not in existing_fields:
        existing_fields.append("thesis_categories")
    preferred_order = [
        "ID",
        "podName",
        "political_leaning",
        "speaker_id",
        "thesis_categories",
        "sentence",
        "center_sentence",
        "topic",
        "probability",
    ]
    fieldnames = preferred_order + [
        name for name in existing_fields if name not in preferred_order
    ]

    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            topic_value = row.get(args.topic_column, "").strip()
            categories = [args.unknown_label]
            if topic_value:
                try:
                    topic_id = int(float(topic_value))
                    categories = inverse_map.get(topic_id, [args.unknown_label])
                except ValueError:
                    categories = [args.unknown_label]
            pod_name = (row.get("podName") or "").strip()
            row["political_leaning"] = leaning_map.get(
                pod_name, metadata_leaning_map.get(pod_name, "")
            )
            row["thesis_categories"] = " | ".join(categories)
            writer.writerow(row)

    print(f"Saved remapped CSV to: {args.output}")


if __name__ == "__main__":
    main()
