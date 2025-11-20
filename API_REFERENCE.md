# 📖 API Reference (Complete)

Complete documentation for all REST API endpoints.

## Base URL

```
http://localhost:8000
```

---

## 🔍 Health & Info Endpoints

### GET /health
Server health check.

**Response:**
```json
{"status": "ok"}
```

### GET /brokers
List all brokers.

**Response:**
```json
[
  {
    "name": "Bolero",
    "website": "https://www.bolero.be/",
    "country": "Belgium",
    "instruments": ["Equities", "ETFs", "Bonds", "Funds"],
    "data_sources": [...]
  }
]
```

---

## 💰 Cost Analysis Endpoints

### GET /cost-analysis
Get all brokers' cost analysis (JSON).

**Response:**
```json
{
  "Bolero": {
    "broker_name": "Bolero",
    "summary": "...",
    "fee_categories": [...],
    "supported_instruments": [...]
  },
  "Keytrade Bank": {...},
  "ING Self Invest": {...}
}
```

### GET /cost-analysis/{broker_name}
Get specific broker's cost analysis.

**Parameters:**
- `broker_name` (string, required) - Broker name
  - Options: `Bolero`, `Keytrade Bank`, `ING Self Invest`

**Example:**
```bash
curl http://localhost:8000/cost-analysis/Bolero
```

**Response:**
```json
{
  "broker": "Bolero",
  "analysis": {
    "broker_name": "Bolero",
    "summary": "...",
    "fee_categories": [...]
  }
}
```

### GET /summary
Get markdown summary of all broker costs.

**Response:** Markdown text with:
- Executive summary
- Detailed broker analysis
- Fee comparison tables
- Cost scenarios
- Rankings

**Example:**
```bash
curl http://localhost:8000/summary > report.md
```

---

## 🔄 PDF Management Endpoints

### POST /refresh-pdfs
Download and extract PDFs for brokers.

**Query Parameters:**
- `brokers_to_refresh` (optional list) - Specific brokers to refresh
- `force` (optional bool) - Override scraping restrictions
- `save_dir` (optional string) - Custom save directory

**Examples:**
```bash
# Refresh all
curl -X POST http://localhost:8000/refresh-pdfs

# Refresh specific
curl -X POST "http://localhost:8000/refresh-pdfs?brokers_to_refresh=Bolero"

# Force refresh
curl -X POST "http://localhost:8000/refresh-pdfs?force=true"
```

**Response:**
```json
{
  "timestamp": "2025-11-20T02:00:00.123456",
  "brokers_refreshed": [
    {
      "name": "Bolero",
      "pdfs_processed": 1,
      "chars_extracted": 7191
    }
  ],
  "total_pdfs_processed": 3,
  "total_chars_extracted": 41032,
  "total_errors": 0
}
```

### POST /refresh-and-analyze
Comprehensive refresh: download PDFs, extract text, run LLM analysis.

**Query Parameters:**
- `brokers_to_process` (optional list) - Brokers to process
- `force` (optional bool) - Override restrictions
- `model` (optional string) - LLM model (default: `gpt-4o`)
- `temperature` (optional float) - LLM temperature (default: `0.1`)
- `max_tokens` (optional int) - Max output tokens (default: `4000`)

**Requirements:**
- `OPENAI_API_KEY` environment variable must be set

**Example:**
```bash
export OPENAI_API_KEY="sk-..."
curl -X POST http://localhost:8000/refresh-and-analyze
```

**Response:**
```json
{
  "timestamp": "2025-11-20T02:05:00.123456",
  "refresh_results": {...},
  "analysis_results": {...},
  "errors": [],
  "message": "Complete"
}
```

---

## 🛠️ Broker Names

Use exact names (case-sensitive):

| Broker Name | URL Format |
|-------------|-----------|
| Bolero | `Bolero` |
| Keytrade Bank | `Keytrade%20Bank` |
| ING Self Invest | `ING%20Self%20Invest` |

---

## ⚡ Response Times

| Endpoint | Time | Type |
|----------|------|------|
| /health | <1ms | Instant |
| /brokers | <10ms | Instant |
| /cost-analysis | <100ms | Cached |
| /summary | <100ms | Cached |
| /refresh-pdfs | 10-30s | Background |
| /refresh-and-analyze | 1-3 min | Background |

---

## ❌ Error Responses

All errors return JSON with `detail` field:

```json
{
  "detail": "Error description"
}
```

**Status Codes:**
- `200` - Success
- `400` - Bad request
- `404` - Not found
- `500` - Server error

---

## 💡 Common Examples

### Get all broker costs
```bash
curl http://localhost:8000/cost-analysis | jq '.'
```

### Get Bolero fees
```bash
curl http://localhost:8000/cost-analysis/Bolero | jq '.analysis.fee_categories'
```

### Save markdown summary
```bash
curl http://localhost:8000/summary > broker_comparison.md
```

### Refresh data
```bash
curl -X POST http://localhost:8000/refresh-pdfs
```

### Use in Python
```python
import requests
costs = requests.get('http://localhost:8000/cost-analysis').json()
print(costs['Bolero']['summary'])
```

---

**For integration help, see:** `API_INTEGRATION.md`

**For quick start, see:** `API_QUICK_START.md`

