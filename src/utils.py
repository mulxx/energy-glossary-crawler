"""
Oilfield Glossary Crawler – shared utilities.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def sanitize_text(text: str) -> str:
    """Collapse whitespace and strip leading/trailing space."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def ensure_output_dir(output_dir: str) -> Path:
    """Create the output directory if it does not exist."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(entries: List[dict], filepath: str) -> None:
    """Save a list of glossary entries as a pretty-printed JSON file."""
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=2)
    logger.info("Saved %d entries → %s", len(entries), filepath)


def save_text(entries: List[dict], filepath: str) -> None:
    """Save glossary entries as a human-readable plain-text file.

    Format per entry::

        TERM
            Definition text.
        -------
    """
    with open(filepath, "w", encoding="utf-8") as fh:
        for entry in entries:
            term = entry.get("term", "").upper()
            definition = entry.get("definition", "")
            fh.write(f"{term}\n")
            fh.write(f"    {definition}\n")
            fh.write("-" * 60 + "\n")
    logger.info("Saved %d entries → %s", len(entries), filepath)


def rate_limit(seconds: float = 1.0) -> None:
    """Sleep for *seconds* to avoid hammering a server."""
    time.sleep(seconds)