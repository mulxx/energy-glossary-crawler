"""
Crawler for https://www.texasinternational.com/blog/oilfield-glossary/

The page is a long blog post that lists terms and definitions.
Common patterns observed on this type of page:
  - <strong> or <b> containing the term, followed by text as the definition
  - <h2>/<h3> as term headings with <p> definitions
  - <dl>/<dt>/<dd> definition-list markup

All three patterns are tried in order; the one that yields the most
entries is kept.
"""

from __future__ import annotations

import logging
from typing import List

from src.base_crawler import BaseCrawler
from src.utils import rate_limit, sanitize_text

logger = logging.getLogger(__name__)

URL = "https://www.texasinternational.com/blog/oilfield-glossary/"


class TexasInternationalCrawler(BaseCrawler):
    """Scrape the Texas International oilfield glossary blog page."""

    def __init__(self) -> None:
        super().__init__("Texas International")

    def crawl(self) -> List[dict]:
        logger.info("[%s] Fetching %s", self.source_name, URL)
        resp = self.get(URL)
        if resp is None:
            logger.error("[%s] Failed to fetch page.", self.source_name)
            return []

        rate_limit(self.REQUEST_DELAY)
        soup = self.parse(resp.text)

        # Remove navigation, header, footer noise
        for tag in soup.select("header, footer, nav, script, style, noscript"):
            tag.decompose()

        entries: List[dict] = []

        # Strategy 1: <dl>/<dt>/<dd> definition list
        entries = self._extract_dl(soup)
        if entries:
            logger.info("[%s] Strategy 1 (dl/dt/dd): %d entries", self.source_name, len(entries))
            return entries

        # Strategy 2: heading (h2/h3) followed by <p>
        entries = self._extract_headings(soup)
        if entries:
            logger.info("[%s] Strategy 2 (headings): %d entries", self.source_name, len(entries))
            return entries

        # Strategy 3: <strong>/<b> inline term + following text
        entries = self._extract_bold(soup)
        logger.info("[%s] Strategy 3 (bold): %d entries", self.source_name, len(entries))
        return entries

    # ------------------------------------------------------------------
    # Extraction strategies
    # ------------------------------------------------------------------

    def _extract_dl(self, soup) -> List[dict]:
        entries = []
        for dl in soup.find_all("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                term = sanitize_text(dt.get_text())
                definition = sanitize_text(dd.get_text())
                if term and definition:
                    entries.append(self.make_entry(term, definition))
        return entries

    def _extract_headings(self, soup) -> List[dict]:
        entries = []
        content = soup.find("article") or soup.find("main") or soup.find("body")
        if content is None:
            return entries
        for heading in content.find_all(["h2", "h3"]):
            term = sanitize_text(heading.get_text())
            # Gather sibling <p> tags as the definition
            definition_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ("h2", "h3"):
                    break
                if sibling.name == "p":
                    text = sanitize_text(sibling.get_text())
                    if text:
                        definition_parts.append(text)
            definition = " ".join(definition_parts)
            if term and definition:
                entries.append(self.make_entry(term, definition))
        return entries

    def _extract_bold(self, soup) -> List[dict]:
        entries = []
        content = soup.find("article") or soup.find("main") or soup.find("body")
        if content is None:
            return entries
        for para in content.find_all("p"):
            bold = para.find(["strong", "b"])
            if bold is None:
                continue
            term = sanitize_text(bold.get_text())
            # Definition is the rest of the paragraph text after the bold tag
            bold.extract()
            definition = sanitize_text(para.get_text().lstrip(":").lstrip(" \u2013-"))
            if term and definition:
                entries.append(self.make_entry(term, definition))
        return entries