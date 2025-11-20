# be-invest Copilot Instructions

Purpose: Enable AI coding agents to quickly contribute to Belgian broker fee aggregation and LLM-assisted extraction with minimal orientation.

## Architecture Overview
- Core package: `src/be_invest/` with dataclasses (`models.py`), YAML loading (`config_loader.py`), fee record pipeline (`pipeline.py`), data ingestion (`sources/manual.py`), and experimental LLM extraction (`sources/llm_extract.py`).
- Data inputs:
  - Broker metadata in one or more YAML files (example: `data/brokers.yaml`).
  - Manual fee entries CSV: `data/fees/manual_fees.csv` (normalized row schema).
  - Optional scraped or PDF-derived text (dumped under `data/output/pdf_text/`).
- Outputs: Aggregated CSV report `data/output/comparison_report.csv` via `scripts/generate_report.py`.

## Data Model Conventions
- `FeeRecord` fields: `broker`, `instrument_type`, `order_channel`, `base_fee (float|None)`, `variable_fee (str|None)`, `currency`, `source`, `notes`.
- `instrument_type` values are free text but practically constrained to a small controlled vocabulary (`Equities`, `ETFs`, `Options`, `Bonds`, `Funds`, `Futures`). Prefer consistent capitalization.
- `order_channel` default should be `Online Platform` if missing.
- `base_fee` numeric only (omit symbols). Keep `variable_fee` verbatim percentage or tier descriptor (`"0.35%"`, `"€1 + 0.35%"`), do NOT parse composite structures prematurely.
- Use `notes` to preserve evidence, page references, footnotes, composite fee explanations.

## YAML Broker Files
- Each broker entry lists `data_sources` with `allowed_to_scrape` flag. Agents MUST respect this flag for automation logic; do not implement scraping bypass unless explicitly requested.
- Extend by appending new broker objects under `brokers:`. Preserve existing schema keys; missing optional keys are fine.

## Manual Fee CSV (`sources/manual.py`)
- Required columns enforced: `broker,instrument_type,order_channel,base_fee,variable_fee,currency,source,notes`.
- Empty numeric -> `""` becomes `None` in model.
- When adding new columns, update `REQUIRED_COLUMNS`, normalization, export writer simultaneously.

## LLM Extraction (`sources/llm_extract.py`)
- Current issues (for improvement tasks):
  - Example JSON uses comments and pipe-delimited placeholders leading to invalid/misaligned outputs.
  - Response format forcing `json_object` while expecting an array may coerce model incorrectly.
  - Lacks chunking; very large PDFs truncated at ~120k chars without semantic segmentation.
  - Evidence & page captured then collapsed into `notes`; consider extending `FeeRecord` or adding an auxiliary structure if higher fidelity needed.
  - Missing `from pathlib import Path` (bug when cache dir is set).
- Preferred direction: Pre-process PDF text into logical fee blocks (tables, bullet sections), run per-block extraction, then merge distinct rows with deduplication keyed by (`broker`,`instrument_type`,`order_channel`,`variable_fee`,`base_fee`).

## Typical Workflows
- Report generation (manual only): `python scripts/generate_report.py --output data/output/comparison_report.csv`.
- Combined extraction (future): integrate chunked LLM passes before manual CSV merge.
- Adding a broker: update `data/brokers.yaml`, commit with message summarizing permission status.

## Patterns & Conventions
- Favor pure functions and dataclasses; avoid side effects beyond logging and file I/O in ingestion modules.
- Keep caching optional and isolated; do not introduce global mutable state.
- Logging: use module-level `logger = logging.getLogger(__name__)`; respect `--log-level` CLI flag (implementation resides presumably in `scripts/generate_report.py`).
- Avoid external scraping libraries unless activated by explicit flags; keep default run compliant & manual-focused.

## Extending Functionality
- Adding structured JSON schema enforcement for LLM: create a small schema dict and validate after `json.loads` before coercion.
- Introducing chunking: helper that splits by section headers / fee keywords (`TARIEF`, `FEES`, `COMMISSIONS`) and size threshold (e.g. 4000 chars per chunk).
- Deduplication: implement a key function in `pipeline.py` or a separate `merge.py`.

## Safety & Compliance
- Never auto-set `allowed_to_scrape=true`; rely exclusively on YAML input.
- Keep proprietary/pricing PDFs out of version control unless explicitly permitted.
- When uncertain about legality, add TODO comment in YAML `notes` rather than coding around restrictions.

## PR / Change Guidance
- Scope changes narrowly (one concept per patch: e.g. add chunking OR JSON schema, not both unless requested).
- Update README only when workflow semantics change (new flags, new required columns).
- Include minimal test harness (if adding logic) using deterministic inputs without external API calls.

## Quick Quality Checklist for Agents
1. Did you maintain required CSV columns? (Manual ingestion)
2. Are new enums documented here & README? (Consistency)
3. Is LLM output validated & non-empty before merging? (Extraction)
4. Did you respect `allowed_to_scrape`? (Compliance)
5. Are large PDFs segmented? (Performance & accuracy)

Request feedback on unclear sections before large refactors.
