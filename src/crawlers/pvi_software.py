"""
Crawler for https://www.pvisoftware.com/drilling-industry-glossary.html

PVI (Pegasus Vertex, Inc.) Drilling Industry Glossary.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from urllib.parse import urljoin
import urllib3

from bs4 import BeautifulSoup
from tqdm import tqdm

from src.base_crawler import BaseCrawler
from src.utils import rate_limit, sanitize_text

logger = logging.getLogger(__name__)

# Suppress InsecureRequestWarning because PVI Software currently has an invalid SSL certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://www.pvisoftware.com/drilling-industry-glossary.html"


class PviSoftwareCrawler(BaseCrawler):
    """Scrape the PVI Software Drilling Industry Glossary."""

    REQUEST_DELAY = 1.0

    def __init__(self) -> None:
        super().__init__("PVI Software Drilling Glossary")

    def crawl(self) -> List[dict]:
        entries: List[dict] = []

        logger.info("[%s] Fetching main index page to discover term links...", self.source_name)
        # PVI software fails strict SSL cert verifications, bypass with verify=False
        resp = self.get(BASE_URL, verify=False)
        if not resp:
            logger.error("[%s] Failed to fetch main index page.", self.source_name)
            return []

        soup = self.parse(resp.text)
        
        # Collecting all term links
        links = set()
        for h3 in soup.find_all('h3'):
            if h3.parent and h3.parent.name == 'li':
                for a in h3.parent.find_all('a'):
                    if 'href' in a.attrs and 'drilling-glossary' in a['href']:
                        links.add(urljoin(BASE_URL, a['href']))

        term_links = sorted(list(links))
        
        if not term_links:
            logger.warning("[%s] No terms found.", self.source_name)
            return []

        logger.info(
            "[%s] Found %d term links.",
            self.source_name,
            len(term_links),
        )

        for url in tqdm(term_links, desc="PVI Software", unit="term"):
            entry = self._scrape_term_page(url)
            if entry:
                entries.append(entry)
            rate_limit(self.REQUEST_DELAY)

        logger.info("[%s] Total entries collected: %d", self.source_name, len(entries))
        return entries

    def _scrape_term_page(self, url: str) -> Optional[dict]:
        """Fetch a single term page and extract its term + definition."""
        resp = self.get(url, verify=False)
        if resp is None:
            return None

        soup = self.parse(resp.text)

        word_define = soup.find("div", id="word_define")
        if not word_define:
            logger.debug("[%s] Could not find #word_define on %s", self.source_name, url)
            return None

        term_tag = word_define.find("h3")
        def_tag = word_define.find("p")
        
        if not term_tag or not def_tag:
            logger.debug("[%s] Missing h3 or p inside #word_define on %s", self.source_name, url)
            return None

        term = sanitize_text(term_tag.get_text())
        definition = sanitize_text(def_tag.get_text())

        if not term or not definition:
            return None

        entry = self.make_entry(term, definition)
        entry["url"] = url
        return entry