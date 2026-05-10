#!/usr/bin/env python3
"""Analyze historical presence of Nov 5, 2024 top 100 podcasts.

Reads `graphs/rankings_overtime_updated.csv`, identifies the shows that placed
in the top 100 on 11-5-24, counts how many also appeared in earlier top-100
lists, and renders a simple SVG heatmap showing each show's trajectory across
the provided dates (similar to the structure implied by check_transcripts.py).
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List
import html

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - depends on environment
    raise SystemExit(
        "Pillow is required to render the PNG heatmap. Install it via "
        "`pip install pillow`."
    ) from exc

DEFAULT_INPUT = Path("graphs/rankings_overtime_updated.csv")
DEFAULT_TARGET_DATE = "11-5-24"
DEFAULT_OUTPUT = Path("graphs/top100_history.png")
DEFAULT_HTML_OUTPUT = Path("graphs/rankings_overtime_colored.html")
DEFAULT_TABLE_PNG = Path("graphs/rankings_overtime_colored.png")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize historical trajectories for Nov 5, 2024 top 100 podcasts."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="CSV file with columns representing snapshot dates (default: %(default)s).",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=DEFAULT_TARGET_DATE,
        help="Target date column label (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the SVG heatmap (default: %(default)s).",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        default=DEFAULT_HTML_OUTPUT,
        help="Path to write the colored rankings table (default: %(default)s).",
    )
    parser.add_argument(
        "--table-png-output",
        type=Path,
        default=DEFAULT_TABLE_PNG,
        help="Path to write the colored rankings table as PNG (default: %(default)s).",
    )
    return parser.parse_args()


def load_rankings(csv_path: Path) -> tuple[list[str], list[list[str]]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Ranking file not found: {csv_path}")
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = []
        for row in reader:
            padded = row + [""] * (len(header) - len(row))
            rows.append([entry.strip() for entry in padded])
    return header, rows


def first_appearance_map(header: list[str], rows: list[list[str]]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for col_idx, _ in enumerate(header):
        for row in rows:
            name = row[col_idx]
            if name and name not in mapping:
                mapping[name] = col_idx
    return mapping


def collect_finalists(
    header: list[str], rows: list[list[str]], target_date: str
) -> list[str]:
    if target_date not in header:
        raise ValueError(f"Target date '{target_date}' not found in header.")
    col_idx = header.index(target_date)
    finalists: List[str] = []
    for row in rows:
        name = row[col_idx]
        if name:
            finalists.append(name)
    # Deduplicate while preserving ranking order.
    seen = set()
    unique_finalists = []
    for name in finalists:
        if name not in seen:
            seen.add(name)
            unique_finalists.append(name)
    return unique_finalists


def build_presence_matrix(
    finalists: list[str], header: list[str], rows: list[list[str]]
) -> Dict[str, list[int]]:
    matrix = {name: [0] * len(header) for name in finalists}
    finalists_set = set(finalists)
    for col_idx, _ in enumerate(header):
        for row in rows:
            name = row[col_idx]
            if name and name in finalists_set:
                matrix[name][col_idx] = 1
    return matrix


def save_heatmap_png(
    finalists: list[str],
    header: list[str],
    matrix: Dict[str, list[int]],
    first_seen: Dict[str, int],
    target_col: int,
    output_path: Path,
) -> None:
    cell_w, cell_h = 14, 12
    left_margin = 220
    top_margin = 60
    width = left_margin + len(header) * cell_w + 220
    height = top_margin + len(finalists) * cell_h + 80

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = ImageFont.load_default()
    small_font = ImageFont.load_default()

    draw.text(
        (width / 2 - 150, 15),
        "Historical Trajectory of Nov 5, 2024 Top 100",
        fill="black",
        font=title_font,
    )
    draw.text(
        (width / 2 - 150, 30),
        "Blue = prior appearance; Orange = Nov 5 snapshot",
        fill="black",
        font=small_font,
    )

    for idx, date in enumerate(header):
        x = left_margin + idx * cell_w
        draw.text((x, top_margin - 15), date, fill="black", font=small_font)

    for row_idx, name in enumerate(finalists):
        y = top_margin + row_idx * cell_h
        draw.text(
            (10, y),
            f"{row_idx + 1:>3}. {name[:35]}",
            fill="black",
            font=small_font,
        )
        presence = matrix[name]
        for col_idx, value in enumerate(presence):
            if not value:
                continue
            color = "#FF7043" if col_idx == target_col else "#1976D2"
            x = left_margin + col_idx * cell_w
            draw.rectangle(
                [x, y, x + cell_w - 1, y + cell_h - 1],
                fill=color,
                outline=None,
            )
        start_idx = first_seen.get(name)
        if start_idx is not None:
            label = (
                f"First top 100: {header[start_idx]}"
                if start_idx <= target_col
                else "First recorded after target"
            )
            draw.text(
                (left_margin + len(header) * cell_w + 10, y),
                label,
                fill="black",
                font=small_font,
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")


def save_colored_table(
    header: list[str],
    rows: list[list[str]],
    highlight_set: set[str],
    output_path: Path,
) -> None:
    """Write an HTML table mirroring the CSV with highlighted cells."""
    lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        '<meta charset="utf-8"/>',
        "<title>Rankings with Nov 5 Highlights</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; }",
        "table { border-collapse: collapse; width: 100%; font-size: 12px; }",
        "th, td { border: 1px solid #ccc; padding: 4px; }",
        ".highlight { background-color: #FFF176; }",
        ".empty { background-color: #f5f5f5; }",
        ".sticky { position: sticky; left: 0; background: #fff; }",
        "</style>",
        "</head>",
        "<body>",
        "<h2>Historical Rankings Highlighted for Nov 5, 2024 Top 100</h2>",
        "<p>Cells in yellow correspond to podcasts that ranked on 11-5-24.</p>",
        "<div style='overflow:auto;'>",
        "<table>",
        "<thead>",
        "<tr><th class='sticky'>Rank</th>",
    ]
    for date in header:
        lines.append(f"<th>{html.escape(date)}</th>")
    lines.append("</tr></thead><tbody>")

    for idx, row in enumerate(rows, start=1):
        lines.append("<tr>")
        lines.append(f"<td class='sticky'>{idx}</td>")
        for value in row:
            if not value:
                lines.append("<td class='empty'>&nbsp;</td>")
                continue
            cls = "highlight" if value in highlight_set else ""
            lines.append(f"<td class='{cls}'>{html.escape(value)}</td>")
        lines.append("</tr>")
    lines.append("</tbody></table></div></body></html>")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_colored_table_png(
    header: list[str],
    rows: list[list[str]],
    highlight_set: set[str],
    output_path: Path,
) -> None:
    """Render the colored rankings table to a PNG image."""
    first_col_w = 80
    cell_w = 220
    cell_h = 24
    margin = 20
    width = first_col_w + len(header) * cell_w + margin * 2
    height = margin * 2 + (len(rows) + 1) * cell_h

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    # Header row
    y = margin
    draw.rectangle(
        [margin, y, width - margin, y + cell_h],
        fill="#e0e0e0",
        outline="black",
    )
    draw.text(
        (margin + 5, y + 6),
        "Rank",
        fill="black",
        font=font,
    )
    for idx, date in enumerate(header):
        x = margin + first_col_w + idx * cell_w
        draw.text((x + 5, y + 6), date, fill="black", font=font)

    # Rows
    for idx, row in enumerate(rows, start=1):
        y = margin + idx * cell_h
        # Rank column
        draw.rectangle(
            [margin, y, margin + first_col_w, y + cell_h],
            outline="#cccccc",
            fill="#f8f8f8",
        )
        draw.text(
            (margin + 5, y + 6),
            str(idx),
            fill="black",
            font=font,
        )
        for col_idx, value in enumerate(row):
            x = margin + first_col_w + col_idx * cell_w
            fill = "#FFF176" if value and value in highlight_set else "white"
            if not value:
                fill = "#f0f0f0"
            draw.rectangle(
                [x, y, x + cell_w, y + cell_h],
                outline="#d0d0d0",
                fill=fill,
            )
            if value:
                draw.text((x + 5, y + 6), value[:32], fill="black", font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")


def main() -> None:
    args = parse_args()
    header, rows = load_rankings(args.input)
    finalists = collect_finalists(header, rows, args.date)
    target_col = header.index(args.date)
    first_seen = first_appearance_map(header, rows)
    matrix = build_presence_matrix(finalists, header, rows)

    historical = sum(
        1 for name in finalists if first_seen.get(name, target_col) < target_col
    )
    newcomers = len(finalists) - historical

    comparison_dates = ["11-04-20", "11-02-21", "09-22-22", "01-03-24"]
    present_counts = {}
    for comp_date in comparison_dates:
        if comp_date in header:
            col_idx = header.index(comp_date)
            names = {row[col_idx] for row in rows if row[col_idx]}
            present_counts[comp_date] = len(set(finalists) & names)
        else:
            present_counts[comp_date] = None

    print(f"Top 100 count for {args.date}: {len(finalists)}")
    print(f"Previously ranked before {args.date}: {historical}")
    print(f"First appearance on {args.date}: {newcomers}")
    for comp_date in comparison_dates:
        count = present_counts.get(comp_date)
        if count is None:
            print(f"No data for comparison date {comp_date}.")
        else:
            print(
                f"Series also appearing on {comp_date}: {count} "
                f"({count / len(finalists) * 100:.1f}%)"
            )

    save_heatmap_png(finalists, header, matrix, first_seen, target_col, args.output)
    print(f"Heatmap saved to {args.output}")

    highlight_set = set(finalists)
    save_colored_table(header, rows, highlight_set, args.html_output)
    print(f"Colored ranking table saved to {args.html_output}")

    save_colored_table_png(header, rows, highlight_set, args.table_png_output)
    print(f"Colored ranking table PNG saved to {args.table_png_output}")


if __name__ == "__main__":
    main()
