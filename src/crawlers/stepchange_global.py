from __future__ import annotations

import html as html_lib
import logging
import re
from typing import List

from bs4 import BeautifulSoup
from src.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class StepchangeGlobalCrawler(BaseCrawler):
    """
    Crawls the Stepchange Global Digital and Integrated Operations Glossary.
    URL: https://stepchangeglobal.com/glossary/
    """

    def __init__(self) -> None:
        super().__init__(source_name="Stepchange Global Glossary")
        self.url = "https://stepchangeglobal.com/glossary/"
        # Remove 'br' encoding dependency if the requests lib doesn't have it   
        self.session.headers["Accept-Encoding"] = "gzip, deflate"

    def crawl(self) -> List[dict]:
        logger.info("Fetching main glossary page: %s", self.url)
        resp = self.get(self.url)
        if not resp:
            logger.error("Failed to fetch %s", self.url)
            return []

        soup = self.parse(resp.text)
        entries = []

        items = soup.find_all("div", class_="name_directory_name_box")
        for item in items:
            term_el = item.find("strong", role="term")
            if not term_el:
                continue
            term = term_el.get_text(strip=True)

            d_div = item.find("div", role="definition")
            if not d_div:
                continue

            # Decode any escaped HTML and prepare parsing
            raw_html = d_div.decode_contents()
            raw_html = html_lib.unescape(raw_html)

            # Replace common block elements with newlines to preserve logic blocks
            raw_html = re.sub(r'(?i)<br\s*/?>', '\n', raw_html)
            raw_html = re.sub(r'(?i)</p>', '\n', raw_html)
            raw_html = re.sub(r'(?i)</div>', '\n', raw_html)

            inner_soup = BeautifulSoup(raw_html, "html.parser")
            text = inner_soup.get_text()

            lines = [line.strip() for line in text.split('\n') if line.strip()]
            filtered_lines = []

            for line in lines:
                lower_line = line.lower()
                # Filtering out explicit references to further content
                if any(phrase in lower_line for phrase in [
                    "for more information",
                    "see ",
                    "discussed in",
                    "discussed here",
                    "featured in",
                    "described in",
                    "described here",
                    "youtube video",
                    "further technical details",
                    "see example",
                    "definition provided by",
                    "full article here",
                    "presented in",
                    "presented by",
                    "technical paper",
                    "further details"
                ]):
                    continue
                
                # strip trailing reference texts from single lines
                line = re.sub(r'(?i)[,\-\s]*(?:is |are |their |the )?(?:discussed|describe|described|presented|present and discuss|outlined|featured|detailed|summarized).*?(?:here|video|paper).*', '', line).strip()
                if line:
                    filtered_lines.append(line)

            clean_def = " ".join(filtered_lines)
            clean_def = re.sub(r'\s+', ' ', clean_def).strip()

            if clean_def:
                entries.append(self.make_entry(term, clean_def))

        logger.info("Extracted %d glossary entries.", len(entries))
        return entries