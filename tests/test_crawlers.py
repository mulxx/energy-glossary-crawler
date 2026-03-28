"""
Unit tests for the oilfield glossary crawler.

Tests run entirely offline — no real HTTP requests are made.
All network calls are patched with unittest.mock.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import sanitize_text, save_json, save_text, ensure_output_dir
from src.base_crawler import BaseCrawler
from src.crawlers.texas_international import TexasInternationalCrawler
from src.crawlers.abb_glossary import AbbCrawler
from src.crawlers.slb_glossary import SlbCrawler
from src.crawlers.pvi_software import PviSoftwareCrawler
from src.crawlers.stepchange_global import StepchangeGlobalCrawler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_response(html: str, status_code: int = 200) -> MagicMock:
    """Create a fake requests.Response-like mock."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    return resp


# ---------------------------------------------------------------------------
# utils.py
# ---------------------------------------------------------------------------

class TestSanitizeText(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(sanitize_text("  hello   world  "), "hello world")

    def test_handles_empty_string(self):
        self.assertEqual(sanitize_text(""), "")

    def test_handles_none(self):
        self.assertEqual(sanitize_text(None), "")

    def test_handles_newlines(self):
        self.assertEqual(sanitize_text("hello\n\nworld"), "hello world")


class TestSaveJson(unittest.TestCase):
    def test_creates_valid_json_file(self):
        import tempfile
        entries = [{"term": "Wellbore", "definition": "The hole drilled.", "source": "test"}]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            path = fh.name
        try:
            save_json(entries, path)
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            self.assertEqual(loaded, entries)
        finally:
            os.unlink(path)


class TestSaveText(unittest.TestCase):
    def test_creates_readable_text_file(self):
        import tempfile
        entries = [{"term": "Acidize", "definition": "To treat with acid.", "source": "test"}]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as fh:
            path = fh.name
        try:
            save_text(entries, path)
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("ACIDIZE", content)
            self.assertIn("To treat with acid.", content)
        finally:
            os.unlink(path)


class TestEnsureOutputDir(unittest.TestCase):
    def test_creates_directory(self):
        import tempfile, shutil
        base = tempfile.mkdtemp()
        target = os.path.join(base, "a", "b", "c")
        try:
            result = ensure_output_dir(target)
            self.assertTrue(result.is_dir())
        finally:
            shutil.rmtree(base)


# ---------------------------------------------------------------------------
# BaseCrawler
# ---------------------------------------------------------------------------

class TestBaseCrawler(unittest.TestCase):
    def setUp(self):
        # Use TexasInternationalCrawler as a concrete instance
        self.crawler = TexasInternationalCrawler()

    def test_make_entry_normalises_whitespace(self):
        entry = self.crawler.make_entry("  Mud  ", "  Drilling fluid.  ")
        self.assertEqual(entry["term"], "Mud")
        self.assertEqual(entry["definition"], "Drilling fluid.")
        self.assertEqual(entry["source"], "Texas International")

    @patch("src.base_crawler.requests.Session.get")
    def test_get_returns_response_on_200(self, mock_get):
        mock_resp = make_response("<html></html>", 200)
        mock_get.return_value = mock_resp
        result = self.crawler.get("http://example.com")
        self.assertIsNotNone(result)

    @patch("src.base_crawler.requests.Session.get")
    def test_get_returns_none_on_404(self, mock_get):
        mock_resp = make_response("", 404)
        mock_get.return_value = mock_resp
        result = self.crawler.get("http://example.com/missing")
        self.assertIsNone(result)

    @patch("src.base_crawler.requests.Session.get")
    def test_get_retries_on_503(self, mock_get):
        """On 503 it should retry up to MAX_RETRIES times."""
        fail_resp = make_response("", 503)
        mock_get.return_value = fail_resp
        with patch("time.sleep"):  # don't actually sleep in tests
            result = self.crawler.get("http://example.com/slow")
        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, self.crawler.MAX_RETRIES)


# ---------------------------------------------------------------------------
# TexasInternationalCrawler
# ---------------------------------------------------------------------------

TEXAS_DL_HTML = """
<html><body>
<article>
  <dl>
    <dt>Acidize</dt>
    <dd>To treat a formation with acid to improve permeability.</dd>
    <dt>Blowout</dt>
    <dd>An uncontrolled flow of reservoir fluids into the wellbore.</dd>
  </dl>
</article>
</body></html>
"""

TEXAS_BOLD_HTML = """
<html><body>
<article>
  <p><strong>Acidize</strong>: To treat a formation with acid.</p>
  <p><strong>Blowout</strong>: Uncontrolled flow of reservoir fluids.</p>
</article>
</body></html>
"""

TEXAS_HEADING_HTML = """
<html><body>
<article>
  <h2>Acidize</h2>
  <p>To treat a formation with acid to improve permeability.</p>
  <h2>Blowout</h2>
  <p>An uncontrolled flow of reservoir fluids into the wellbore.</p>
</article>
</body></html>
"""


class TestTexasInternationalCrawler(unittest.TestCase):
    def _crawl_with_html(self, html: str):
        crawler = TexasInternationalCrawler()
        with patch.object(crawler, "get", return_value=make_response(html)):
            with patch("src.crawlers.texas_international.rate_limit"):
                return crawler.crawl()

    def test_dl_strategy(self):
        entries = self._crawl_with_html(TEXAS_DL_HTML)
        self.assertEqual(len(entries), 2)
        terms = {e["term"] for e in entries}
        self.assertIn("Acidize", terms)
        self.assertIn("Blowout", terms)

    def test_bold_strategy(self):
        entries = self._crawl_with_html(TEXAS_BOLD_HTML)
        self.assertEqual(len(entries), 2)
        terms = {e["term"] for e in entries}
        self.assertIn("Acidize", terms)

    def test_heading_strategy(self):
        entries = self._crawl_with_html(TEXAS_HEADING_HTML)
        self.assertEqual(len(entries), 2)

    def test_returns_empty_on_failed_fetch(self):
        crawler = TexasInternationalCrawler()
        with patch.object(crawler, "get", return_value=None):
            entries = crawler.crawl()
        self.assertEqual(entries, [])

    def test_source_name_set(self):
        entries = self._crawl_with_html(TEXAS_DL_HTML)
        for entry in entries:
            self.assertEqual(entry["source"], "Texas International")


# ---------------------------------------------------------------------------
# AbbCrawler
# ---------------------------------------------------------------------------

ABB_HTML = """
<html><body>
<main>
  <dl>
    <dt>API gravity</dt>
    <dd>Measure of oil density relative to water.</dd>
    <dt>Casing</dt>
    <dd>Steel pipe cemented into the wellbore for structural integrity.</dd>
  </dl>
</main>
</body></html>
"""


class TestAbbCrawler(unittest.TestCase):
    def _crawl_with_html(self, html: str):
        crawler = AbbCrawler()
        with patch.object(crawler, "get", return_value=make_response(html)):
            with patch("src.crawlers.abb_glossary.rate_limit"):
                return crawler.crawl()

    def test_extracts_dl_entries(self):
        entries = self._crawl_with_html(ABB_HTML)
        self.assertGreaterEqual(len(entries), 2)

    def test_returns_empty_on_failed_fetch(self):
        crawler = AbbCrawler()
        with patch.object(crawler, "get", return_value=None):
            entries = crawler.crawl()
        self.assertEqual(entries, [])


# ---------------------------------------------------------------------------
# SlbCrawler
# ---------------------------------------------------------------------------

SLB_LETTER_A_HTML = """
<html><body>
<main>
  <ul>
    <li><a href="/en/terms/a/acidize">acidize</a></li>
    <li><a href="/en/terms/a/annulus">annulus</a></li>
  </ul>
</main>
</body></html>
"""

SLB_TERM_HTML = """
<html><body>
<h1>acidize</h1>
<p class="definition">To treat a well or formation with acid in order to improve production.</p>
</body></html>
"""


class TestSlbCrawler(unittest.TestCase):
    def test_extracts_term_links_from_coveo(self):
        crawler = SlbCrawler(letters="a")
        
        class FakeResponse:
            status_code = 200
            def json(self):
                return {
                    "results": [
                        {"clickUri": "https://glossary.slb.com/en/terms/a/acidize"},
                        {"clickUri": "https://glossary.slb.com/en/terms/a/acid_frac"}
                    ]
                }

        with patch.object(crawler.session, "post", return_value=FakeResponse()):
            with patch("src.crawlers.slb_glossary.rate_limit"):
                links = crawler._get_term_links("a")
        self.assertEqual(len(links), 2)
        from urllib.parse import urlparse
        self.assertTrue(all(urlparse(lnk).netloc == "glossary.slb.com" for lnk in links))

    def test_scrape_term_page(self):
        crawler = SlbCrawler(letters="a")
        with patch.object(crawler, "get", return_value=make_response(SLB_TERM_HTML)):
            entry = crawler._scrape_term_page("https://glossary.slb.com/en/terms/a/acidize")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["term"], "acidize")
        self.assertIn("acid", entry["definition"].lower())

    def test_crawl_returns_entries(self):
        crawler = SlbCrawler(letters="a")

        class FakeResponse:
            status_code = 200
            def json(self):
                return {
                    "results": [
                        {"clickUri": "https://glossary.slb.com/en/terms/a/acidize"},
                        {"clickUri": "https://glossary.slb.com/en/terms/a/acid_frac"}
                    ]
                }

        def fake_get(url, **kwargs):
            return make_response(SLB_TERM_HTML)

        with patch.object(crawler.session, "post", return_value=FakeResponse()):
            with patch.object(crawler, "get", side_effect=fake_get):
                with patch("src.crawlers.slb_glossary.rate_limit"):
                    entries = crawler.crawl()

        self.assertEqual(len(entries), 2)
        for entry in entries:
            self.assertEqual(entry["source"], "SLB Oilfield Glossary")

    def test_returns_empty_when_letter_page_fails(self):
        crawler = SlbCrawler(letters="z")
        class FakeResponse:
            status_code = 500
        with patch.object(crawler.session, "post", return_value=FakeResponse()):
            with patch("src.crawlers.slb_glossary.rate_limit"):
                entries = crawler.crawl()
        self.assertEqual(entries, [])


# ---------------------------------------------------------------------------
# PviSoftwareCrawler
# ---------------------------------------------------------------------------

PVI_INDEX_HTML = """
<html><body>
<ul>
  <li><h3>A</h3>
    <ul>
      <li><h3><a href="/drilling-glossary/acidize">Acidize</a></h3></li>
    </ul>
  </li>
</ul>
</body></html>
"""

PVI_INDEX_WITH_LINKS_HTML = """
<html><body>
<ul>
  <li>
    <h3>A</h3>
    <li>
      <h3>Acidize</h3>
      <a href="/drilling-glossary-acidize.html">Acidize</a>
    </li>
    <li>
      <h3>Blowout</h3>
      <a href="/drilling-glossary-blowout.html">Blowout</a>
    </li>
  </li>
</ul>
</body></html>
"""

PVI_TERM_HTML = """
<html><body>
<div id="word_define">
  <h3>Acidize</h3>
  <p>To pump acid into the wellbore to dissolve limestone and improve permeability.</p>
</div>
</body></html>
"""

PVI_TERM_EMPTY_HTML = """
<html><body>
<div id="other_content">
  <h3>Something</h3>
  <p>Not a glossary term.</p>
</div>
</body></html>
"""


class TestPviSoftwareCrawler(unittest.TestCase):
    def test_scrape_term_page_extracts_entry(self):
        crawler = PviSoftwareCrawler()
        with patch.object(crawler, "get", return_value=make_response(PVI_TERM_HTML)):
            entry = crawler._scrape_term_page("https://www.pvisoftware.com/drilling-glossary-acidize.html")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["term"], "Acidize")
        self.assertIn("acid", entry["definition"].lower())
        self.assertEqual(entry["source"], "PVI Software Drilling Glossary")
        self.assertIn("url", entry)

    def test_scrape_term_page_returns_none_when_no_word_define(self):
        crawler = PviSoftwareCrawler()
        with patch.object(crawler, "get", return_value=make_response(PVI_TERM_EMPTY_HTML)):
            entry = crawler._scrape_term_page("https://www.pvisoftware.com/drilling-glossary-missing.html")
        self.assertIsNone(entry)

    def test_scrape_term_page_returns_none_on_failed_fetch(self):
        crawler = PviSoftwareCrawler()
        with patch.object(crawler, "get", return_value=None):
            entry = crawler._scrape_term_page("https://www.pvisoftware.com/drilling-glossary-fail.html")
        self.assertIsNone(entry)

    def test_crawl_returns_empty_on_failed_index(self):
        crawler = PviSoftwareCrawler()
        with patch.object(crawler, "get", return_value=None):
            entries = crawler.crawl()
        self.assertEqual(entries, [])

    def test_crawl_collects_entries(self):
        """Simulate crawl: index page has links, each term page returns a valid entry."""
        crawler = PviSoftwareCrawler()

        index_html = """
        <html><body>
        <ul>
          <li>
            <h3>Terms</h3>
            <li>
              <h3>Acidize</h3>
              <a href="/drilling-glossary-acidize.html">Acidize</a>
            </li>
          </li>
        </ul>
        </body></html>
        """

        def fake_get(url, **kwargs):
            if "glossary.html" in url:
                return make_response(index_html)
            return make_response(PVI_TERM_HTML)

        with patch.object(crawler, "get", side_effect=fake_get):
            with patch("src.crawlers.pvi_software.rate_limit"):
                entries = crawler.crawl()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["term"], "Acidize")

    def test_source_name(self):
        crawler = PviSoftwareCrawler()
        self.assertEqual(crawler.source_name, "PVI Software Drilling Glossary")


# ---------------------------------------------------------------------------
# StepchangeGlobalCrawler
# ---------------------------------------------------------------------------

STEPCHANGE_HTML = """
<html><body>
<div class="name_directory_name_box">
  <strong role="term">Digital Twin</strong>
  <div role="definition">
    A virtual representation of a physical asset or system.
  </div>
</div>
<div class="name_directory_name_box">
  <strong role="term">IoT</strong>
  <div role="definition">
    Internet of Things – a network of connected devices and sensors.
  </div>
</div>
<div class="name_directory_name_box">
  <strong role="term">Edge Computing</strong>
  <div role="definition">
    Processing data near the source rather than in a centralised data centre.
    For more information, see our technical paper.
  </div>
</div>
</body></html>
"""

STEPCHANGE_EMPTY_HTML = """
<html><body>
<p>No glossary items here.</p>
</body></html>
"""


class TestStepchangeGlobalCrawler(unittest.TestCase):
    def _crawl_with_html(self, html: str):
        crawler = StepchangeGlobalCrawler()
        with patch.object(crawler, "get", return_value=make_response(html)):
            return crawler.crawl()

    def test_extracts_entries(self):
        entries = self._crawl_with_html(STEPCHANGE_HTML)
        self.assertGreaterEqual(len(entries), 2)
        terms = {e["term"] for e in entries}
        self.assertIn("Digital Twin", terms)
        self.assertIn("IoT", terms)

    def test_filters_reference_lines(self):
        """Lines containing 'for more information' should be stripped."""
        entries = self._crawl_with_html(STEPCHANGE_HTML)
        edge_entry = next((e for e in entries if e["term"] == "Edge Computing"), None)
        self.assertIsNotNone(edge_entry)
        self.assertNotIn("for more information", edge_entry["definition"].lower())

    def test_returns_empty_on_failed_fetch(self):
        crawler = StepchangeGlobalCrawler()
        with patch.object(crawler, "get", return_value=None):
            entries = crawler.crawl()
        self.assertEqual(entries, [])

    def test_returns_empty_on_no_glossary_items(self):
        entries = self._crawl_with_html(STEPCHANGE_EMPTY_HTML)
        self.assertEqual(entries, [])

    def test_source_name(self):
        crawler = StepchangeGlobalCrawler()
        self.assertEqual(crawler.source_name, "Stepchange Global Glossary")

    def test_entry_has_required_keys(self):
        entries = self._crawl_with_html(STEPCHANGE_HTML)
        for entry in entries:
            self.assertIn("term", entry)
            self.assertIn("definition", entry)
            self.assertIn("source", entry)


# ---------------------------------------------------------------------------
# main.py integration
# ---------------------------------------------------------------------------

class TestMainRun(unittest.TestCase):
    """Smoke-test the CLI entry point with mocked crawlers."""

    def test_run_all_sources(self):
        import tempfile, shutil
        from main import run

        fake_entries = [{"term": "Mud", "definition": "Drilling fluid.", "source": "test"}]
        mock_crawler = MagicMock()
        mock_crawler.crawl.return_value = fake_entries
        mock_crawler.source_name = "test"

        tmp_dir = tempfile.mkdtemp()
        try:
            with patch("main.build_crawler", return_value=mock_crawler):
                rc = run(["--sources", "texas", "--output-dir", tmp_dir, "--format", "json"])
            self.assertEqual(rc, 0)
            output_files = list(Path(tmp_dir).glob("*.json"))
            self.assertGreater(len(output_files), 0)
        finally:
            shutil.rmtree(tmp_dir)

    def test_run_returns_1_when_no_entries(self):
        import tempfile, shutil
        from main import run

        mock_crawler = MagicMock()
        mock_crawler.crawl.return_value = []
        mock_crawler.source_name = "test"

        tmp_dir = tempfile.mkdtemp()
        try:
            with patch("main.build_crawler", return_value=mock_crawler):
                rc = run(["--sources", "texas", "--output-dir", tmp_dir])
            self.assertEqual(rc, 1)
        finally:
            shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    unittest.main()