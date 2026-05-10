#!/usr/bin/env python3
"""
Scrape top-100 podcast titles from a Chartable Apple Podcasts chart page
archived on the Wayback Machine.

Target example:
https://web.archive.org/web/20230427041144/https://chartable.com/charts/itunes/us-politics-podcasts
"""

from __future__ import annotations

import re
import sys
import csv
from typing import List, Optional
import requests
from bs4 import BeautifulSoup


WAYBACK_URL = "https://web.archive.org/web/20230427041144/https://chartable.com/charts/itunes/us-politics-podcasts"

# Matches either a direct chartable podcast path or a wayback-rewritten one.
PODCAST_HREF_RE = re.compile(r"(?:chartable\.com)?/podcasts/[^\"'\s]+", re.IGNORECASE)


def fetch_html(url: str) -> str:
    headers = {
        # Wayback can be picky; a normal UA helps.
        "User-Agent": "Mozilla/5.0 (compatible; chart-scraper/1.0; +https://example.com/bot)",
        "Accept": "text/html,application/xhtml+xml",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def extract_top_titles(html: str, n: int = 100) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")

    titles: List[str] = []
    seen = set()

    # Iterate anchors in document order; keep only those that link to podcast pages.
    for a in soup.find_all("a", href=True):
        href = a["href"] or ""
        text = a.get_text(strip=True)

        if not text:
            continue

        # Some anchors may be images or empty labels; filter aggressively.
        if len(text) < 2:
            continue

        # Identify podcast links (not publishers).
        if PODCAST_HREF_RE.search(href):
            # Avoid duplicates (sometimes the same title appears in multiple places).
            if text not in seen:
                titles.append(text)
                seen.add(text)

        if len(titles) >= n:
            break

    return titles


def main(argv: List[str]) -> int:
    url = argv[1] if len(argv) > 1 else WAYBACK_URL
    out_csv: Optional[str] = argv[2] if len(argv) > 2 else None

    html = fetch_html(url)
    titles = extract_top_titles(html, n=100)

    if len(titles) < 100:
        print(f"WARNING: Only found {len(titles)} titles (expected 100).", file=sys.stderr)
        print("Wayback/HTML structure may have changed; consider tightening selectors.", file=sys.stderr)

    # Print to stdout
    for i, t in enumerate(titles, start=1):
        print(f"{i:>3}. {t}")

    # Optionally write CSV: rank,title
    if out_csv:
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["rank", "title"])
            for i, t in enumerate(titles, start=1):
                w.writerow([i, t])

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))