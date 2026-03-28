"""
Crawler for https://new.abb.com/oil-and-gas/glossary

The ABB glossary page lists oil-and-gas terms.  The page may render
content dynamically, but the static HTML usually contains either:
  - A definition list (<dl>/<dt>/<dd>)
  - Accordion/collapsible panels where the term is in a heading/button
    and the definition is in the expanded panel body
  - A plain HTML table with two columns: term | definition

All three patterns are tried; whichever returns the most entries wins.
"""

from __future__ import annotations

import logging
from typing import List

from src.base_crawler import BaseCrawler
from src.utils import rate_limit, sanitize_text

logger = logging.getLogger(__name__)

URL = "https://new.abb.com/oil-and-gas/glossary"


class AbbCrawler(BaseCrawler):
    """Scrape the ABB Oil & Gas glossary page."""

    def __init__(self) -> None:
        super().__init__("ABB Oil & Gas")

    def crawl(self) -> List[dict]:
        logger.info("[%s] Fetching %s", self.source_name, URL)
        resp = self.get(URL)
        if resp is None:
            logger.error("[%s] Failed to fetch page.", self.source_name)
            return []

        rate_limit(self.REQUEST_DELAY)
        soup = self.parse(resp.text)

        for tag in soup.select("header, footer, nav, script, style, noscript"):
            tag.decompose()

        # Try strategies in order and use the richest result
        candidates = [
            self._extract_dl(soup),
            self._extract_accordion(soup),
            self._extract_table(soup),
            self._extract_headings(soup),
        ]
        entries = max(candidates, key=len)
        logger.info("[%s] Extracted %d entries.", self.source_name, len(entries))
        return entries

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

    def _extract_accordion(self, soup) -> List[dict]:
        """Handle accordion-style layouts where term is in a button/heading
        and definition is in the adjacent panel."""
        entries = []
        # Common accordion patterns: a heading/button followed by a div
        for btn in soup.find_all(["button", "h3", "h4"], class_=lambda c: c and (
            "accordion" in c.lower() or "toggle" in c.lower() or "title" in c.lower()
        )):
            term = sanitize_text(btn.get_text())
            panel = btn.find_next_sibling()
            if panel:
                definition = sanitize_text(panel.get_text())
                if term and definition:
                    entries.append(self.make_entry(term, definition))
        return entries

    def _extract_table(self, soup) -> List[dict]:
        """Two-column tables: first column = term, second = definition."""
        entries = []
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    term = sanitize_text(cells[0].get_text())
                    definition = sanitize_text(cells[1].get_text())
                    if term and definition and term.lower() not in ("term", "word", "entry"):
                        entries.append(self.make_entry(term, definition))
                elif len(cells) == 1:
                    text = cells[0].get_text().strip()
                    parts = text.split(" - ", 1)
                    if len(parts) == 2:
                        term = sanitize_text(parts[0])
                        definition = sanitize_text(parts[1])
                        if term and definition and term.lower() not in ("term", "word", "entry"):
                            entries.append(self.make_entry(term, definition))
        return entries

    def _extract_headings(self, soup) -> List[dict]:
        entries = []
        content = soup.find("main") or soup.find("article") or soup.find("body")
        if content is None:
            return entries
        for heading in content.find_all(["h2", "h3"]):
            term = sanitize_text(heading.get_text())
            definition_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ("h2", "h3"):
                    break
                if sibling.name in ("p", "div"):
                    text = sanitize_text(sibling.get_text())
                    if text:
                        definition_parts.append(text)
            definition = " ".join(definition_parts)
            if term and definition:
                entries.append(self.make_entry(term, definition))
        return entries