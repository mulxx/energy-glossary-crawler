# Contributing to Energy Glossary Crawler

Thank you for your interest in contributing! This guide explains how to add a new glossary source or improve existing crawlers.

## Development Setup

```bash
git clone https://github.com/mulxx/energy-glossary-crawler.git
cd energy-glossary-crawler
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Adding a New Crawler

### 1. Create the crawler file

Create `src/crawlers/<source_name>.py`. Your crawler must inherit from `BaseCrawler` and implement the `crawl()` method:

```python
from __future__ import annotations

import logging
from typing import List

from src.base_crawler import BaseCrawler
from src.utils import rate_limit, sanitize_text

logger = logging.getLogger(__name__)

URL = "https://example.com/glossary"


class ExampleCrawler(BaseCrawler):
    """Scrape the Example glossary page."""

    def __init__(self) -> None:
        super().__init__("Example Glossary")

    def crawl(self) -> List[dict]:
        resp = self.get(URL)
        if resp is None:
            return []

        rate_limit(self.REQUEST_DELAY)
        soup = self.parse(resp.text)

        entries = []
        # ... extract terms and definitions from the page ...
        # For each term/definition pair:
        #   entries.append(self.make_entry(term, definition))
        return entries
```

Key points:
- Use `self.get(url)` for HTTP requests (has built-in retry and backoff).
- Use `self.parse(html)` to get a BeautifulSoup tree.
- Use `self.make_entry(term, definition)` to build normalised entry dicts.
- Call `rate_limit(self.REQUEST_DELAY)` between requests to be respectful.

### 2. Register the crawler

Add your crawler to three places:

**`src/crawlers/__init__.py`** — import and add to `__all__`:

```python
from src.crawlers.example import ExampleCrawler

__all__ = [
    ...,
    "ExampleCrawler",
]
```

**`src/__init__.py`** — add to the re-exports:

```python
from src.crawlers import (
    ...,
    ExampleCrawler,
)
```

**`main.py`** — add to `CRAWLER_REGISTRY`:

```python
CRAWLER_REGISTRY = {
    ...,
    "example": ExampleCrawler,
}
```

### 3. Add tests

Add a test class in `tests/test_crawlers.py`. All tests must run **offline** — mock every HTTP call:

```python
EXAMPLE_HTML = """
<html><body>
  <dl>
    <dt>Term A</dt><dd>Definition A.</dd>
  </dl>
</body></html>
"""

class TestExampleCrawler(unittest.TestCase):
    def _crawl_with_html(self, html: str):
        crawler = ExampleCrawler()
        with patch.object(crawler, "get", return_value=make_response(html)):
            return crawler.crawl()

    def test_extracts_entries(self):
        entries = self._crawl_with_html(EXAMPLE_HTML)
        self.assertGreaterEqual(len(entries), 1)

    def test_returns_empty_on_failed_fetch(self):
        crawler = ExampleCrawler()
        with patch.object(crawler, "get", return_value=None):
            self.assertEqual(crawler.crawl(), [])
```

### 4. Verify

```bash
python -m pytest tests/ -v
```

## Code Style

- Use type hints on all public methods.
- Add `from __future__ import annotations` at the top of every module.
- Use `logging` instead of `print`.
- Keep rate limits conservative — be a respectful client.

## Submitting Changes

1. Fork the repo and create a feature branch.
2. Make your changes and ensure all tests pass.
3. Submit a pull request with a clear description of what you added/changed.
