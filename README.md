# Energy Glossary Crawler

[![CI](https://github.com/mulxx/energy-glossary-crawler/actions/workflows/ci.yml/badge.svg)](https://github.com/mulxx/energy-glossary-crawler/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Python crawler that collects oil & gas industry terminology and definitions from multiple authoritative glossary websites. Output is saved as structured JSON and human-readable text files.

## Supported Sources

| Source | Website | Description |
|--------|---------|-------------|
| **SLB (Schlumberger)** | [glossary.slb.com](https://glossary.slb.com/en/) | The most comprehensive oilfield glossary — thousands of terms across all disciplines |
| **ABB Oil & Gas** | [new.abb.com/oil-and-gas/glossary](https://new.abb.com/oil-and-gas/glossary) | ABB's oil-and-gas terminology reference |
| **Texas International** | [texasinternational.com](https://www.texasinternational.com/blog/oilfield-glossary/) | Oilfield glossary blog page |
| **PVI Software** | [pvisoftware.com](https://www.pvisoftware.com/drilling-industry-glossary.html) | Pegasus Vertex drilling industry glossary |
| **Stepchange Global** | [stepchangeglobal.com/glossary](https://stepchangeglobal.com/glossary/) | Digital and integrated operations glossary |

## Installation

```bash
git clone https://github.com/mulxx/energy-glossary-crawler.git
cd energy-glossary-crawler
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Or install as an editable package (includes CLI entry point):

```bash
pip install -e .
```

## Usage

### Run all crawlers

```bash
python main.py
```

Output files are saved to `./output/` by default.

### Select specific sources

```bash
python main.py --sources texas abb slb
```

Available source names: `texas`, `abb`, `slb`, `pvi`, `stepchange`

### Limit SLB to specific letters (useful for testing)

```bash
python main.py --sources slb --slb-letters ab
```

### Choose output format

```bash
python main.py --format json         # JSON only
python main.py --format text         # Plain text only
python main.py --format both         # Both (default)
```

### Override output directory

```bash
python main.py --output-dir /path/to/output
```

## Output Format

### JSON

Each entry is a dict with three fields:

```json
[
  {
    "term": "Acidize",
    "definition": "To pump acid into the wellbore to dissolve limestone and improve permeability.",
    "source": "SLB Oilfield Glossary"
  }
]
```

Per-source files (`slb.json`, `abb.json`, etc.) are generated.

### Text

```
ACIDIZE
    To pump acid into the wellbore to dissolve limestone and improve permeability.
------------------------------------------------------------
```

## Project Structure

```
energy-glossary-crawler/
├── main.py                  # CLI entry point
├── src/
│   ├── __init__.py
│   ├── base_crawler.py      # Abstract base class with retry/rate-limit logic
│   ├── utils.py             # Shared helpers (sanitize, save, rate limit)
│   └── crawlers/
│       ├── __init__.py
│       ├── abb_glossary.py
│       ├── pvi_software.py
│       ├── slb_glossary.py
│       ├── stepchange_global.py
│       └── texas_international.py
├── tests/
│   └── test_crawlers.py     # Offline unit tests (all HTTP mocked)
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

All tests run offline — no real HTTP requests are made.

## Adding a New Crawler

See [CONTRIBUTING.md](CONTRIBUTING.md) for a step-by-step guide on how to add support for a new glossary website.

## Disclaimer

This project is intended for **educational and research purposes only**. All glossary content and definitions are the intellectual property of their respective website owners. Please respect each website's `robots.txt` and terms of service. The crawlers apply conservative rate-limiting to be respectful clients.

## License

[MIT](LICENSE)
