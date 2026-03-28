"""
Base crawler class shared by every site-specific crawler.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from src.utils import sanitize_text

logger = logging.getLogger(__name__)

# Default browser-like headers to avoid simple bot-blocks
DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


class BaseCrawler(ABC):
    """Abstract base class for all glossary crawlers.

    Sub-classes must implement :meth:`crawl` which returns a list of
    ``{"term": ..., "definition": ..., "source": ...}`` dicts.
    """

    # Seconds to wait between consecutive HTTP requests
    REQUEST_DELAY: float = 1.5
    # Maximum retry attempts on transient HTTP errors
    MAX_RETRIES: int = 3

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abstractmethod
    def crawl(self) -> List[dict]:
        """Return a list of glossary entry dicts for this source."""

    # ------------------------------------------------------------------
    # Helpers available to sub-classes
    # ------------------------------------------------------------------

    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Perform an HTTP GET with retry / back-off logic.

        Returns the :class:`requests.Response` on success, ``None`` on
        permanent failure.
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=30, **kwargs)
                if resp.status_code == 200:
                    return resp
                if resp.status_code in (429, 503):
                    wait = 5 * attempt
                    logger.warning(
                        "[%s] HTTP %s for %s – waiting %ss (attempt %d/%d)",
                        self.source_name,
                        resp.status_code,
                        url,
                        wait,
                        attempt,
                        self.MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue
                logger.error(
                    "[%s] HTTP %s for %s – skipping",
                    self.source_name,
                    resp.status_code,
                    url,
                )
                return None
            except requests.RequestException as exc:
                logger.warning(
                    "[%s] Request error for %s (attempt %d/%d): %s",
                    self.source_name,
                    url,
                    attempt,
                    self.MAX_RETRIES,
                    exc,
                )
                if attempt < self.MAX_RETRIES:
                    time.sleep(3 * attempt)
        return None

    def parse(self, html: str) -> BeautifulSoup:
        """Return a :class:`BeautifulSoup` tree for *html*."""
        return BeautifulSoup(html, "lxml")

    def make_entry(self, term: str, definition: str) -> dict:
        """Build a normalised glossary entry dict."""
        return {
            "term": sanitize_text(term),
            "definition": sanitize_text(definition),
            "source": self.source_name,
        }