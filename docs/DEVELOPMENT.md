# Development Guide

This guide is for developers working on be-invest locally. It explains the safe path for setup, testing, model changes, data refreshes, and modular code changes.

## Local Setup

Use a virtual environment and install the package in editable mode:

```bash
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and set only the keys you need:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
GROQ_API_KEY=...
EMAIL_SCHEDULER_ENABLED=false
```

For local API development, keep `EMAIL_SCHEDULER_ENABLED=false` so the standalone Windows Task Scheduler job remains the only weekly email scheduler.

## Running The App

Start the FastAPI app locally:

```bash
.\.venv\Scripts\python.exe -m uvicorn be_invest.api.server:app --reload --port 8000
```

Useful endpoints:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/brokers
curl http://localhost:8000/cost-analysis
curl "http://localhost:8000/cost-comparison-tables?lang=en"
```

Use `/docs` for interactive API calls:

```text
http://localhost:8000/docs
```

## Core Data Flow

The project is deterministic-first:

1. Broker source definitions live in `data/brokers.yaml`.
2. PDF/web text extraction writes files under `data/output/pdf_text/`.
3. LLM extraction and structuring produce `data/output/broker_cost_analyses.json` and `data/output/fee_rules.json`.
4. `validation/fee_calculator.py` loads `fee_rules.json` and computes all numeric fees.
5. API endpoints serve deterministic tables, persona rankings, narrative analysis, news, chat, and email data.

LLMs should extract, structure, summarize, or answer. They should not be the source of truth for fee arithmetic.

## Model Defaults

Shared default model identifiers live in `src/be_invest/llm_models.py`.

Use `DEFAULT_CLAUDE_SONNET_MODEL` instead of hard-coding Claude model IDs in application code. At the time of this guide, the default is:

```python
DEFAULT_CLAUDE_SONNET_MODEL = "claude-sonnet-4-6"
```

When changing model defaults:

1. Update `src/be_invest/llm_models.py`.
2. Update docs and script help text if needed.
3. Run `tests/test_llm_model_defaults.py`.
4. Search for stale IDs with `rg "claude-|gpt-|gemini-|groq/"`.

## Testing

Fast checks:

```bash
.\.venv\Scripts\python.exe -m compileall -q src\be_invest
.\.venv\Scripts\python.exe -m pytest tests\test_api_core_smoke.py tests\test_llm_model_defaults.py
```

Recommended refactor suite:

```bash
.\.venv\Scripts\python.exe -m pytest ^
  tests\test_api_core_smoke.py ^
  tests\test_api_modular_helpers.py ^
  tests\test_llm_model_defaults.py ^
  tests\test_import_fix.py ^
  tests\test_email_sender_retry.py ^
  tests\test_cache.py ^
  tests\test_output_validation.py ^
  tests\test_data_quality_validation.py ^
  tests\test_llm_extraction_validation.py
```

Notes:

- `tests/test_api_core_smoke.py` uses FastAPI `TestClient` and does not require a separate server.
- `tests/test_cache.py` performs live API cache checks when `localhost:8000` is running; otherwise it skips cleanly.
- LLM extraction tests return mock validation data when API keys are missing.

## Modularization Rules

Keep imports pointed from high-level layers to low-level layers:

```text
api/server.py
  -> api/schemas.py
  -> api/i18n.py
  -> news.py, email_sender.py, config_loader.py
  -> sources/*
  -> validation/*
```

Avoid importing `be_invest.api.server` from non-API modules. That pulls in the FastAPI app, middleware, schedulers, and tracing side effects. If another module needs helper logic from `server.py`, move that helper into a small module first.

Current intended split:

- `api/schemas.py`: Pydantic request and response models.
- `api/i18n.py`: language names, persona translations, structured broker-note localization.
- `llm_models.py`: shared default model IDs.
- `validation/fee_calculator.py`: numeric source of truth for fees.
- `email_sender.py`: email rendering and SMTP delivery, without importing the FastAPI server.

When adding endpoints, prefer extracting pure functions first. Endpoint functions should mostly validate inputs, call services, and shape HTTP responses.

## Refreshing Fee Data

Use cached PDF text when possible:

```bash
.\.venv\Scripts\python.exe scripts\refresh_fee_rules.py
```

Force re-analysis:

```bash
.\.venv\Scripts\python.exe scripts\refresh_fee_rules.py --force-reanalyze
```

Refresh through the API only when you need the full scrape-and-analyze flow:

```bash
curl -X POST "http://localhost:8000/refresh-and-analyze?force=false"
```

After any fee-rule change, run:

```bash
.\.venv\Scripts\python.exe -m pytest tests\test_output_validation.py tests\test_data_quality_validation.py
```

## Adding A Broker

1. Add the broker and sources to `data/brokers.yaml`.
2. Add expected fee checks in `tests/test_data_quality_validation.py`.
3. Add broker-specific prompt guidance if extraction misses recurring fields.
4. Refresh fee rules.
5. Run the API smoke and validation tests.

## Documentation Hygiene

When changing behavior, update docs in the same branch:

- README for user-facing setup and common workflows.
- `docs/DEVELOPMENT.md` for developer process.
- `docs/fee_model.md` for fee rule schema or calculator behavior.
- `docs/business_flow.md` for business-level flow changes.

Avoid adding links to docs that do not exist.
