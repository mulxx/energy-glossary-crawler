"""
Crawler for https://glossary.slb.com/en/

The SLB (Schlumberger) Oilfield Glossary is the most authoritative
reference for petroleum-industry terminology, containing thousands of
entries across all disciplines.

Page structure (2024-era layout, subject to change):
  - The home page lists 26 letter tabs (A–Z).
  - Each letter page URL follows the pattern:
        https://glossary.slb.com/en/terms/{letter}
    e.g. https://glossary.slb.com/en/terms/a
  - Each letter page contains a list of term links.
  - Each individual term page URL follows the pattern:
        https://glossary.slb.com/en/terms/{letter}/{slug}
    e.g. https://glossary.slb.com/en/terms/a/acidize

The crawler:
  1. Iterates over every letter A–Z.
  2. Collects all term-page links from the letter listing page.
  3. Visits each term page and extracts the definition.

A conservative rate-limit is applied between requests to be a
respectful client.
"""

from __future__ import annotations

import logging
import string
from typing import List, Optional
from urllib.parse import urljoin

import requests
from tqdm import tqdm

from src.base_crawler import BaseCrawler
from src.utils import rate_limit, sanitize_text

logger = logging.getLogger(__name__)

BASE_URL = "https://glossary.slb.com"
LETTER_URL_TEMPLATE = "https://glossary.slb.com/en/terms/{letter}"


class SlbCrawler(BaseCrawler):
    """Scrape the full SLB Oilfield Glossary (A–Z)."""

    # SLB has a large number of pages; be conservative
    REQUEST_DELAY = 2.0

    def __init__(self, letters: Optional[str] = None) -> None:
        """
        Parameters
        ----------
        letters:
            Optional string of letters to crawl, e.g. ``"abc"``.
            Defaults to all 26 letters.
        """
        super().__init__("SLB Oilfield Glossary")
        self.letters = letters or string.ascii_lowercase

    def crawl(self) -> List[dict]:
        entries: List[dict] = []

        for letter in self.letters:
            logger.info("[%s] Processing letter '%s'", self.source_name, letter.upper())
            term_links = self._get_term_links(letter)
            if not term_links:
                logger.warning("[%s] No terms found for letter '%s'", self.source_name, letter)
                continue

            logger.info(
                "[%s] Found %d term links for '%s'",
                self.source_name,
                len(term_links),
                letter.upper(),
            )

            for url in tqdm(term_links, desc=f"SLB [{letter.upper()}]", unit="term"):
                entry = self._scrape_term_page(url)
                if entry:
                    entries.append(entry)
                rate_limit(self.REQUEST_DELAY)

        logger.info("[%s] Total entries collected: %d", self.source_name, len(entries))
        return entries

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_term_links(self, letter: str) -> List[str]:
        """Fetch term URLs for a specific letter using the Coveo API."""
        url = "https://glossary.slb.com/coveo/rest/search/v2"
        links = []
        page_size = 1000
        first_result = 0
        while True:
            payload = {
                "cq": "@syslanguage==English AND @z95xtemplatename==\"Term\"",
                "q": f'@sysuri="*terms/{letter.lower()}/*"',
                "numberOfResults": page_size,
                "firstResult": first_result
            }
            try:
                resp = self.session.post(url, json=payload, timeout=30)
                if resp.status_code != 200:
                    logger.error("[%s] Coveo API returned %s", self.source_name, resp.status_code)
                    break
                data = resp.json()
                results = data.get("results", [])
                for res in results:
                    uri = res.get("clickUri")
                    if uri and "/en/terms/" in uri:
                        links.append(uri)
                if len(results) < page_size:
                    break
                first_result += page_size
                rate_limit(self.REQUEST_DELAY)
            except (requests.RequestException, ValueError, KeyError) as e:
                logger.error("[%s] Exception fetching from Coveo API: %s", self.source_name, e)
                break
        
        # Deduplicate links while preserving order
        return list(dict.fromkeys(links))

    def _scrape_term_page(self, url: str) -> Optional[dict]:
        """Fetch a single term page and extract its term + definition."""
        resp = self.get(url)
        if resp is None:
            return None

        soup = self.parse(resp.text)

        # Derive the term from the URL slug as a reliable fallback
        slug = url.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ")

        # --- Term extraction ---
        h1_tags = soup.find_all("h1")
        # Usually the first h1 is "Explore the Energy Glossary" or similar, 
        # and the second h1 is the actual term.
        term_tag = h1_tags[1] if len(h1_tags) > 1 else None
        
        if not term_tag:
            term_tag = (
                soup.find("h1")
                or soup.find(class_=lambda c: c and "term" in c.lower() and "title" in c.lower())
                or soup.find(class_=lambda c: c and "glossary" in c.lower() and "term" in c.lower())
            )
        
        term = sanitize_text(term_tag.get_text()) if term_tag else slug.title()
        
        # If we somehow still got the global header, fallback to slug
        if term.lower() in ("explore the energy glossary", "energy glossary en español"):
            term = slug.title()

        # --- Definition extraction ---
        # Common class/id names used by glossary sites
        def_selectors = [
            ".content-two-col__text",
            "div[class*='definition']",
            "div[class*='Description']",
            "div[class*='content-main']",
            "div[id*='definition']",
            "article",
            "main"
        ]
        definition = ""
        for selector in def_selectors:
            tag = soup.select_one(selector)
            if tag:
                # Skip if the element contains only the term title
                text = sanitize_text(tag.get_text())
                if text and text.lower() != term.lower() and len(text) > 20:
                    definition = text
                    break

        # Broader fallback: first substantial <p> anywhere after the h1 in the DOM
        if not definition:
            h1 = soup.find("h1")
            if h1:
                # find all <p> tags after the h1 in the whole document
                for p in h1.find_all_next("p"):
                    text = sanitize_text(p.get_text())
                    if len(text) > 20:
                        definition = text
                        break

        if not term or not definition:
            logger.debug("[%s] Could not extract entry from %s", self.source_name, url)
            return None

        entry = self.make_entry(term, definition)
        entry["url"] = url
        return entry