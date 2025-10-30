# be-invest

Toolkit for aggregating and comparing brokerage fees in the Belgian market.

## Project goals

This repository provides a structured workflow to collect, normalize, and report
fee schedules for Belgian investment brokers. It focuses on:

1. Cataloguing brokers and their publicly available fee sources.
2. Recording whether automation is permitted according to the broker's terms of
   service and robots.txt policies.
3. Capturing fee data manually (respecting legal constraints) and exporting a
   comparison matrix for equities, ETFs, options, and other instruments.

The repository does **not** perform automated scraping. Instead, it offers data
models, ingestion helpers, and reporting utilities that you can pair with manual
research or with automation that you are legally authorized to run.

## Repository layout

```
pyproject.toml          # Project metadata and dependencies (PyYAML)
src/be_invest/          # Python package with data models and helpers
  models.py             # Dataclasses for brokers, data sources, and fees
  config_loader.py      # YAML loaders for broker metadata
  pipeline.py           # High-level helpers to load data and build reports
  sources/manual.py     # CSV ingestion and export utilities
scripts/
  generate_report.py    # CLI to aggregate manual and/or scraped fee data
data/
  brokers.yaml          # Example broker catalogue with ToS/Tariff source notes
  fees/manual_fees.csv  # Template for manually entered fee data
data/output/            # Auto-generated reports (ignored from version control)
```

## Getting started

1. Create and activate a Python 3.9+ environment.
2. Install dependencies:

   ```bash
   pip install -e .
   ```

3. Populate `data/fees/manual_fees.csv` with verified fee entries. The sample
   row is provided only to demonstrate the expected schema.
4. (Optional) Extend `data/brokers.yaml` with additional brokers and data-source
   notes as you continue your research.
5. Generate the comparison report:

   ```bash
   python scripts/generate_report.py --output data/output/comparison_report.csv
   ```

   The command echoes how many rows were written and regenerates the CSV in the
   `data/output/` directory.

### Scrape mode (no manual data)

When you have permission to automate collection from a broker's website, you can
attempt a best-effort scrape for all brokers in your `brokers.yaml`:

```bash
python scripts/generate_report.py --scrape --no-manual --brokers data/brokers.yaml --output data/output/comparison_report.csv
```

- The scraper iterates over all brokers in `data/brokers.yaml` and respects
  `allowed_to_scrape` unless you
  pass `--force-scrape` (not recommended unless you have explicit permission).
- The built-in scraper only handles very simple HTML tables; most brokers will
  require custom, site-specific parsing or PDF parsing. For those, the command
  will still run but may produce zero scraped rows.
- You can also reference local files in `brokers.yaml` by setting a data-source
  `url` to a file path (e.g., `C:\path\to\fees.pdf`) or a `file://` URI. This
  avoids network access and lets you test parsers on downloaded documents.
- If no manual or scraped records are found, the CLI message will suggest
  adding manual entries or enabling `--scrape`.

### Caching and Playwright

Install extras (optional):

```bash
pip install -e .[scrape]
pip install -e .[browser]
python -m playwright install chromium
```

Use cache + Playwright for dynamic pages and to avoid re-fetches:

```bash
python scripts/generate_report.py --scrape --no-manual \
  --use-playwright \
  --cache-dir data/cache --cache-ttl-seconds 21600 \
  --brokers data/brokers.yaml \
  --output data/output/comparison_report.csv
```

### LLM-assisted extraction (OpenAI GPT-4o)

Install the LLM extra and set your API key (example for PowerShell):

```bash
pip install -e .[llm]
$env:OPENAI_API_KEY = "sk-..."  # or set in your shell profile
```

Run with LLM fallback when heuristics find nothing:

```bash
python scripts/generate_report.py --scrape --no-manual --force-scrape \
  --use-llm --llm-model gpt-4o --llm-cache-dir data/llm_cache \
  --dump-pdf-text data/output/pdf_text --log-level DEBUG \
  --brokers data/brokers.yaml --output data/output/comparison_report.csv
```

- The LLM converts extracted text into strict JSON rows and cites short evidence.
- Outputs are cached by (model, content hash) in `data/llm_cache/`.
- Use `--strict-parse` to keep only rows with both base and variable fees.

### Debugging and PDF text dumps

Use verbose logs and dump extracted PDF text to inspect what the parser sees:

```bash
python scripts/generate_report.py --scrape --no-manual --force-scrape \
  --brokers data/brokers.yaml \
  --dump-pdf-text data/output/pdf_text \
  --log-level DEBUG \
  --output data/output/comparison_report.csv
```

This writes one `.txt` file per PDF under `data/output/pdf_text/` and prints
DEBUG logs with fetch sizes, content-type guesses, and parsed row counts.

## Manual data collection workflow

To follow the research plan discussed earlier:

1. **Compile broker list** – Maintain `data/brokers.yaml` as your living source
   of record. Include each broker's website, covered instruments, and the
   primary locations where fee data is published (web pages, PDFs, brochures).
2. **Check permissions** – Record the `allowed_to_scrape` flag and any legal
   notes in the YAML file. This makes it easy to see at a glance which brokers
   allow automation and which require manual extraction or explicit consent.
3. **Capture fee data** – Use `data/fees/manual_fees.csv` to enter fee details
   gathered manually or via permitted APIs. Track per-instrument fees, base vs
   variable components, currency, and citation URL.
4. **Normalize and audit** – Run `python scripts/generate_report.py` to export
   the consolidated view. Review the CSV for completeness and accuracy, and add
   timestamps or additional metadata as needed for auditability.
5. **Report and iterate** – Import the CSV into spreadsheets or BI tools to
   create visualization dashboards. Schedule periodic reviews to update the
   manual fee entries when brokers change their tariffs.

## Disclaimer

Always review each broker's legal notices and robots.txt directives before
collecting data. Many brokers forbid automated scraping; violating those terms
can lead to account restrictions or legal consequences. This project is designed
to keep your workflow compliant by centralizing permission tracking and
encouraging manual verification.
