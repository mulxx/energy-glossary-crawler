#!/usr/bin/env python3
"""
Oilfield Glossary Crawler — main entry point.

Usage
-----
Run all crawlers (outputs saved to ./output/):

    python main.py

Run a subset of crawlers:

    python main.py --sources texas abb slb

Limit SLB to specific letters (useful for testing):

    python main.py --sources slb --slb-letters ab

Override output directory:

    python main.py --output-dir /path/to/output
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from src.crawlers import (
    AbbCrawler,
    PviSoftwareCrawler,
    SlbCrawler,
    StepchangeGlobalCrawler,
    TexasInternationalCrawler,
)
from src.utils import ensure_output_dir, save_json, save_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Map CLI short-names to crawler classes
CRAWLER_REGISTRY: Dict[str, type] = {
    "texas": TexasInternationalCrawler,
    "abb": AbbCrawler,
    "slb": SlbCrawler,
    "pvi": PviSoftwareCrawler,
    "stepchange": StepchangeGlobalCrawler,
}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl oilfield glossary websites and save results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=list(CRAWLER_REGISTRY.keys()),
        default=list(CRAWLER_REGISTRY.keys()),
        help=(
            "Which sources to crawl. "
            "Choices: %(choices)s (default: all)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to write output files (default: ./output)",
    )
    parser.add_argument(
        "--slb-letters",
        default=None,
        help=(
            "Letters to crawl for the SLB glossary, e.g. 'abcd'. "
            "Defaults to all 26 letters."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["json", "text", "both"],
        default="both",
        help="Output format(s) (default: both)",
    )
    return parser.parse_args(argv)


def build_crawler(source: str, slb_letters: Optional[str]):
    """Instantiate the crawler for *source*, passing extra kwargs as needed."""
    cls = CRAWLER_REGISTRY[source]
    if source == "slb" and slb_letters:
        return cls(letters=slb_letters)
    return cls()


def run(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    output_dir = ensure_output_dir(args.output_dir)

    total_entries = 0

    for source in args.sources:
        crawler = build_crawler(source, args.slb_letters)
        logger.info("=" * 60)
        logger.info("Starting crawler: %s", crawler.source_name)
        logger.info("=" * 60)

        try:
            entries = crawler.crawl()
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Crawler %s raised an unexpected error: %s", source, exc, exc_info=True)
            entries = []

        if not entries:
            logger.warning("No entries returned by %s", source)
            continue

        # Per-source output
        stem = source.replace(" ", "_").lower()
        if args.format in ("json", "both"):
            save_json(entries, str(output_dir / f"{stem}.json"))
        if args.format in ("text", "both"):
            save_text(entries, str(output_dir / f"{stem}.txt"))

        total_entries += len(entries)
        logger.info("Crawler %s finished: %d entries", source, len(entries))

    # Combined output
    if total_entries > 0:
        logger.info("=" * 60)
        logger.info("Total entries across all sources: %d", total_entries)
    else:
        logger.warning("No entries collected from any source.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run())