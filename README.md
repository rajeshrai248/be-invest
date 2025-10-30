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
  generate_report.py    # CLI to aggregate manual fee data into a report
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
