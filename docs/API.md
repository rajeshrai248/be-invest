# API Reference

The API is served by `be_invest.api.server:app`.

Run locally:

```bash
.\.venv\Scripts\python.exe -m uvicorn be_invest.api.server:app --reload --port 8000
```

Interactive docs:

```text
http://localhost:8000/docs
http://localhost:8000/redoc
http://localhost:8000/openapi.json
```

## Health And Metadata

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Basic health check |
| `GET` | `/brokers` | List configured brokers from `data/brokers.yaml` |

## Cost And Analysis

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/cost-analysis` | Load stored broker cost analyses |
| `GET` | `/cost-analysis/{broker_name}` | Load one broker's stored analysis |
| `GET` | `/cost-comparison-tables` | Deterministic fee tables, broker notes, and persona comparison |
| `GET` | `/financial-analysis` | Narrative financial analysis using deterministic numeric sections |
| `GET` | `/summary` | Stored markdown summary, when generated |

Common query parameters:

| Parameter | Used By | Description |
|---|---|---|
| `model` | LLM-backed endpoints | Defaults to `claude-sonnet-4-6` for Claude-backed analysis paths |
| `lang` | Cost tables, analysis, chat | `en`, `fr-be`, or `nl-be` |
| `force` | Refresh/cache-aware endpoints | Bypass cache or reload from current source data |

## Refresh Flows

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/refresh-pdfs` | Scrape broker PDFs/pages and save extracted text |
| `POST` | `/refresh-and-analyze` | Full scrape, extraction, fee-rule save, and cache warm |
| `POST` | `/news/scrape` | Scrape broker news sources |

Use `force=true` carefully. Remote clients have force suppressed by IP checks; local/private clients can force refreshes.

## News

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/news` | List all stored news flashes |
| `GET` | `/news/broker/{broker_name}` | List news for one broker |
| `GET` | `/news/recent` | List recent news |
| `GET` | `/news/statistics` | News counts and date range |
| `POST` | `/news` | Add a manual news flash |
| `DELETE` | `/news` | Delete a news flash by broker and title |

## Chat And Feedback

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/chat` | Ask natural-language questions about Belgian broker fees |
| `POST` | `/feedback` | Submit thumbs-up/down feedback for a Langfuse trace |

## Email

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/email/send` | Trigger the broker fee email report manually |

Production weekly email delivery should use the standalone scheduler script described in `README.md`, not an always-on in-process timer.
