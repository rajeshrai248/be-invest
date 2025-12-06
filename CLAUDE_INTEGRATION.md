# Claude (Anthropic) Integration Guide

**Last Updated:** December 6, 2025  
**Purpose:** Enable Claude AI models for broker cost analysis, cost-comparison tables, and summary generation with improved accuracy.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [API Key Setup](#api-key-setup)
4. [Available Endpoints](#available-endpoints)
5. [Usage Examples](#usage-examples)
6. [Model Selection](#model-selection)
7. [Cost Comparison Tables](#cost-comparison-tables)
8. [Summary Generation](#summary-generation)
9. [API Integration](#api-integration)
10. [Troubleshooting](#troubleshooting)
11. [Best Practices](#best-practices)

---

## Overview

The be-invest project supports both **OpenAI (GPT)** and **Anthropic (Claude)** models for:

- **Cost Analysis Generation** – Extract structured fee data from broker PDFs
- **Cost Comparison Tables** – Generate matrix tables comparing transaction costs
- **Summary Reports** – Create comprehensive markdown summaries

Claude models often provide improved accuracy for complex fee structures and tiered pricing.

---

## Prerequisites

### 1. Install Required Packages

```powershell
pip install anthropic jsonschema
```

### 2. Verify Installation

```powershell
python -c "import anthropic; print('Anthropic SDK installed successfully')"
```

### 3. Project Structure

Ensure these directories exist:
- `data/brokers.yaml` – Broker metadata
- `data/output/pdf_text/` – Extracted PDF text files
- `data/output/broker_cost_analyses.json` – Generated cost analysis

---

## API Key Setup

### Windows (PowerShell)

```powershell
# Set for current session
$env:ANTHROPIC_API_KEY = "sk-ant-api03-..."

# Set permanently (User level)
[System.Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', 'sk-ant-api03-...', 'User')

# Verify
echo $env:ANTHROPIC_API_KEY
```

### Windows (CMD)

```cmd
set ANTHROPIC_API_KEY=sk-ant-api03-...
```

### Keep OpenAI Key (Optional)

If you want fallback support or comparison:

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

---

## Available Endpoints

The FastAPI server (`src/be_invest/api/server.py`) provides:

### 1. Health Check
```
GET /health
```

### 2. Get Cost Analysis JSON
```
GET /cost-analysis
```
Returns the complete `broker_cost_analyses.json` file.

### 3. Cost Comparison Tables
```
GET /cost-comparison-tables?model=claude-sonnet-4-20250514
```
Generates three matrix tables (ETFs, Stocks, Bonds) with transaction costs.

**Query Parameters:**
- `model` (optional) – LLM model name
  - Default: `gpt-4o`
  - Claude: `claude-sonnet-4-20250514`

### 4. Refresh PDFs and Analyze
```
POST /refresh-and-analyze
```
Downloads PDFs, extracts text, and generates analysis.

**Query Parameters:**
- `brokers` (optional) – Comma-separated broker names
- `force` (optional) – Override `allowed_to_scrape` flag
- `model` (optional) – LLM model for analysis

---

## Usage Examples

### 1. Generate Cost Analysis with Claude (CLI)

```powershell
# Set API key
$env:ANTHROPIC_API_KEY = "sk-ant-api03-..."

# Generate analysis using Claude
python scripts/generate_exhaustive_summary.py --model claude-sonnet-4-20250514

# Output files:
# - data/output/broker_cost_analyses.json
# - data/output/exhaustive_cost_charges_summary.md
```

### 2. Start API Server

```powershell
# Start server
python scripts/run_api.py

# Server runs at: http://localhost:8000
# API docs at: http://localhost:8000/docs
```

### 3. Get Cost Comparison Tables (Using Claude)

**PowerShell:**

```powershell
# Using Invoke-RestMethod
$response = Invoke-RestMethod -Uri "http://localhost:8000/cost-comparison-tables?model=claude-sonnet-4-20250514" -Method GET
$response | ConvertTo-Json -Depth 10

# Save to file
$response | ConvertTo-Json -Depth 10 | Out-File cost_tables.json
```

**cURL:**

```bash
curl "http://localhost:8000/cost-comparison-tables?model=claude-sonnet-4-20250514"
```

**Python:**

```python
import requests

response = requests.get(
    "http://localhost:8000/cost-comparison-tables",
    params={"model": "claude-sonnet-4-20250514"}
)

data = response.json()

print(f"ETFs: {len(data['etfs'])} brokers")
print(f"Stocks: {len(data['stocks'])} brokers")
print(f"Bonds: {len(data['bonds'])} brokers")
```

### 4. Refresh and Analyze with Claude

**PowerShell:**

```powershell
# Refresh specific brokers
$body = @{
    brokers = @("ING Self Invest", "Bolero", "Keytrade Bank")
    model = "gpt-4o"
    force = $false
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/refresh-and-analyze" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"
```

**cURL:**

```bash
curl -X POST "http://localhost:8000/refresh-and-analyze" \
  -H "Content-Type: application/json" \
  -d '{"brokers":["ING Self Invest","Bolero"],"model":"claude-sonnet-4-20250514"}'
```

---

## Model Selection

### Supported Claude Models

| Model | Description | Context Window | Best For |
|-------|-------------|----------------|----------|
| `claude-sonnet-4-20250514` | Claude Sonnet 4 (Recommended) | 200K tokens | Complex fee structures, tiered pricing, high accuracy |
| `claude-opus-4-20250514` | Claude Opus 4.5 | 200K tokens | Maximum accuracy (slower, more expensive) |
| `claude-haiku-3-5-20250514` | Claude Haiku 3.5 | 200K tokens | Fast, economical |
| `claude-haiku-3-20240307` | Claude Haiku 3 | 200K tokens | Fast, economical (older) |

**Note:** Claude 3.5 models are no longer supported. Use Claude 4 models instead.

### Supported OpenAI Models

| Model | Description | Best For |
|-------|-------------|----------|
| `gpt-4o` | GPT-4 Optimized (default) | General purpose, fast, good accuracy |
| `gpt-4-turbo` | GPT-4 Turbo | Longer context |
| `gpt-4` | GPT-4 Standard | High accuracy |

### Rate Limits (as of Dec 2025)

**Claude 3.5 Sonnet (Tier 1):**
- **Requests:** 50 per minute
- **Tokens:** 40,000 per minute input, 8,000 per minute output

**Monitor Usage:**
- Console: https://console.anthropic.com/settings/usage

### Model Selection Strategy

```python
# Recommended: Use Claude Sonnet 4 for best accuracy, GPT-4o for speed
PRIMARY_MODEL = "claude-sonnet-4-20250514"  # Best accuracy for complex pricing
FALLBACK_MODEL = "gpt-4o"                    # Fast, good for simple structures
```

**Workflow:**
1. Use Claude Sonnet 4 for brokers with complex tiered pricing (Keytrade Bank, Bolero)
2. Use GPT-4o for simpler percentage-based pricing (ING Self Invest)
3. Compare outputs for validation

---

## Cost Comparison Tables

### What It Does

Generates three matrix tables showing transaction costs for different order sizes:

**Transaction Sizes (EUR):** 250, 500, 1000, 1500, 2000, 2500, 5000, 10000, 50000

**Tables:**
1. **ETFs** – Exchange-traded fund transaction costs
2. **Stocks** – Stock/equity transaction costs
3. **Bonds** – Bond transaction costs

### Response Format

```json
{
  "etfs": [
    {
      "broker": "ING Self Invest",
      "250": 1.0,
      "500": 1.75,
      "1000": 3.5,
      "1500": 5.25,
      "2000": 7.0,
      "2500": 8.75,
      "5000": 17.5,
      "10000": 35.0,
      "50000": 175.0
    }
  ],
  "stocks": [...],
  "bonds": [...],
  "notes": {
    "ING Self Invest": {
      "stocks": "0.35% with €1 minimum via web/app",
      "etfs": "Same as stocks",
      "bonds": "0.50% with €50 minimum"
    }
  }
}
```

### Why Claude Performs Better

Claude models excel at:
- **Complex Fee Structures:** Tiered pricing with multiple thresholds
- **Mathematical Calculations:** Percentage + minimum fee logic
- **Context Understanding:** Distinguishing between product types
- **Instruction Following:** Precise JSON output formatting

### Example: Complex Calculation

**Keytrade Bank Tiered Structure:**
```
€0 - €250: €2.45
€250.01 - €2,500: €5.95
€2,500.01 - €10,000: €14.95
Each additional €10,000: +€7.50
```

**Transaction: €50,000**
- Base tier (up to €10,000): €14.95
- Additional: (€50,000 - €10,000) / €10,000 × €7.50 = €30.00
- **Total: €44.95**

Claude consistently calculates this correctly; GPT-4o sometimes applies flat rates.

---

## Summary Generation

### Generate with Claude

```powershell
# Full pipeline: Extract + Analyze + Summarize
python scripts/generate_exhaustive_summary.py `
  --model claude-sonnet-4-20250514 `
  --brokers-yaml data/brokers.yaml `
  --pdf-text-dir data/output/pdf_text `
  --output data/output/exhaustive_cost_charges_summary.md
```

### Output Files

1. **JSON Analysis:**
   ```
   data/output/broker_cost_analyses.json
   ```
   Structured fee data for all brokers.

2. **Markdown Summary:**
   ```
   data/output/exhaustive_cost_charges_summary.md
   ```
   Human-readable comparison report.

### Summary Features

- **Transaction Fees:** By product type (stocks, ETFs, bonds, options, etc.)
- **Custody Fees:** Annual account maintenance charges
- **Currency Fees:** FX conversion costs
- **Market Coverage:** Supported exchanges and geographies
- **Special Notes:** Free selections, tiered pricing details

---

## API Integration

### Client Example (Python)

```python
import requests
import json
import os

class BeInvestClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        
    def get_cost_analysis(self):
        """Get complete broker cost analysis."""
        response = requests.get(f"{self.base_url}/cost-analysis")
        response.raise_for_status()
        return response.json()
    
    def get_comparison_tables(self, model="claude-sonnet-4-20250514"):
        """Get cost comparison tables using specified model."""
        response = requests.get(
            f"{self.base_url}/cost-comparison-tables",
            params={"model": model}
        )
        response.raise_for_status()
        return response.json()
    
    def refresh_and_analyze(self, brokers=None, model="claude-sonnet-4-20250514", force=False):
        """Refresh PDFs and regenerate analysis."""
        payload = {
            "brokers": brokers,
            "model": model,
            "force": force
        }
        response = requests.post(
            f"{self.base_url}/refresh-and-analyze",
            json=payload
        )
        response.raise_for_status()
        return response.json()

# Usage
client = BeInvestClient()

# Get comparison tables with Claude
tables = client.get_comparison_tables(model="claude-sonnet-4-20250514")
print(f"ETF brokers: {[b['broker'] for b in tables['etfs']]}")

# Refresh specific brokers
result = client.refresh_and_analyze(
    brokers=["ING Self Invest", "Bolero"],
    model="claude-sonnet-4-20250514"
)
print(f"Status: {result['status']}")
```

### JavaScript/TypeScript Example

```typescript
interface CostComparisonTables {
  etfs: BrokerRow[];
  stocks: BrokerRow[];
  bonds: BrokerRow[];
  notes: Record<string, Record<string, string>>;
}

interface BrokerRow {
  broker: string;
  250: number | null;
  500: number | null;
  1000: number | null;
  1500: number | null;
  2000: number | null;
  2500: number | null;
  5000: number | null;
  10000: number | null;
  50000: number | null;
}

async function getCostComparisonTables(
  model = "gpt-4o"
): Promise<CostComparisonTables> {
  const response = await fetch(
    `http://localhost:8000/cost-comparison-tables?model=${model}`
  );
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  
  return response.json();
}

// Usage
const tables = await getCostComparisonTables();
console.log(`ETFs: ${tables.etfs.length} brokers`);
console.log(`Stocks: ${tables.stocks.length} brokers`);
console.log(`Bonds: ${tables.bonds.length} brokers`);
```

### REST API Response Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Parse JSON response |
| 400 | Bad Request | Check query parameters |
| 404 | Not Found | Run `generate_exhaustive_summary.py` first |
| 500 | Server Error | Check logs, verify API keys |
| 503 | Rate Limited | Wait and retry with exponential backoff |

---

## Troubleshooting

### Issue: `ANTHROPIC_API_KEY not set`

**Symptom:**
```
ERROR - ❌ ANTHROPIC_API_KEY not set
```

**Solution:**
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-api03-..."

# Verify
echo $env:ANTHROPIC_API_KEY
```

---

### Issue: `HTTP 500 - Anthropic API call failed`

**Symptom:**
```
ERROR - ❌ Anthropic API call failed: rate_limit_error
```

**Solution:**
1. Check rate limits: https://console.anthropic.com/settings/usage
2. Add retry logic with exponential backoff:

```python
import time

def call_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except anthropic.RateLimitError:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            logger.warning(f"Rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)
```

---

### Issue: `HTTP 400 - Unsupported parameter`

**Symptom (GPT-5 models):**
```
ERROR - ❌ Unsupported parameter: 'max_tokens' is not supported with this model.
Use 'max_completion_tokens' instead.
```

**Solution:**
This affects newer OpenAI models (o1 series). Use `gpt-4o` or `claude-sonnet-4-20250514` instead:

```powershell
python scripts/generate_exhaustive_summary.py --model gpt-4o
# or
python scripts/generate_exhaustive_summary.py --model claude-sonnet-4-20250514
```

---

### Issue: Empty or Invalid JSON Response

**Symptom:**
```
ERROR - ❌ JSON parsing failed: Expecting value: line 1 column 1 (char 0)
```

**Solution:**
1. The script automatically cleans markdown code blocks from Claude responses
2. If issue persists, check the raw response in logs
3. Try with lower temperature (already set to 0.1)
4. Increase `max_tokens` to 8096 for complex brokers

---

### Issue: Missing Brokers in Tables

**Symptom:**
```json
{
  "broker": "ING Self Invest",
  "250": null,
  "500": null,
  ...
}
```

**Cause:**
- Missing or incomplete data in `broker_cost_analyses.json`
- LLM couldn't parse the fee structure

**Solution:**
1. Check source PDF text exists:
   ```powershell
   ls data\output\pdf_text\ing_self_invest_*.txt
   ```

2. Regenerate with Claude for better parsing:
   ```powershell
   python scripts/generate_exhaustive_summary.py --model claude-sonnet-4-20250514
   ```

3. Manually inspect `broker_cost_analyses.json` for data quality

---

### Issue: CORS / OPTIONS Error

**Symptom:**
```
127.0.0.1:51502 - "OPTIONS /cost-analysis HTTP/1.1" 405 Method Not Allowed
```

**Solution:**
Already fixed in `server.py` with CORS middleware:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows OPTIONS
    allow_headers=["*"],
)
```

If issue persists, restart the API server:
```powershell
# Stop server (Ctrl+C)
# Restart
python scripts/run_api.py
```

---

### Issue: DEGIRO PDF Download Fails (503 Error)

**Symptom:**
```
ERROR - ❌ Failed to download https://www.degiro.nl/data/pdf/Tarievenoverzicht.pdf: 
503 Server Error: Service Temporarily Unavailable
```

**Cause:**
DEGIRO uses bot protection (Myra Cloud).

**Solution:**
1. Download PDF manually in browser
2. Save to `data/pdfs/degiro_tarievenoverzicht.pdf`
3. Convert to text manually:
   ```powershell
   python scripts/convert_degiro_pdf.py
   ```

4. Or mark as `allowed_to_scrape: false` in `brokers.yaml` and provide PDF offline

---

## Best Practices

### 1. Model Selection Strategy

```python
# Recommended order: Claude first for accuracy, GPT for speed
PRIMARY_MODEL = "claude-sonnet-4-20250514"   # Best accuracy
FALLBACK_MODEL = "gpt-4o"                     # Fast, good accuracy
```

**Workflow:**
1. Use Claude Sonnet 4 for all brokers (highest accuracy)
2. Use GPT-4o for quick iterations during development
3. Compare outputs for validation

### 2. Rate Limit Management

```python
import time
import random

def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0):
    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
    time.sleep(delay)
```

### 3. Caching Strategy

- Cache LLM responses by broker + PDF hash
- Invalidate cache when PDF updates
- Store cache in `data/cache/`

### 4. Validation Checks

```python
def validate_comparison_table(table: list[dict]) -> bool:
    """Validate cost comparison table structure."""
    transaction_sizes = ["250", "500", "1000", "1500", "2000", "2500", "5000", "10000", "50000"]
    
    for row in table:
        # Check broker field
        if "broker" not in row or not row["broker"]:
            return False
        
        # Check all transaction sizes present
        for size in transaction_sizes:
            if size not in row:
                return False
            
            # Validate numeric or null
            if row[size] is not None and not isinstance(row[size], (int, float)):
                return False
    
    return True
```

### 5. Logging Best Practices

```python
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Log LLM calls
logger.info(f"🔄 Calling {model} for {broker_name}")

# Log success with metrics
logger.info(f"✅ Analysis complete in {duration:.2f}s")

# Log errors with context
logger.error(f"❌ Failed to parse {broker_name}: {error}", exc_info=True)
```

### 6. Cost Optimization

**Claude Pricing (as of Dec 2025):**
- Input: $3.00 / million tokens
- Output: $15.00 / million tokens

**Tips:**
- Truncate PDF text to ~15,000 chars (sufficient for most brokers)
- Use Claude only for complex cases
- Cache results aggressively
- Monitor monthly spend: https://console.anthropic.com/settings/billing

### 7. Error Recovery

```python
def analyze_with_fallback(broker_name: str, pdf_text: str):
    models = ["claude-sonnet-4-20250514", "gpt-4o"]
    
    for model in models:
        try:
            result = analyze_broker_costs_with_llm(broker_name, pdf_text, model=model)
            
            # Validate result
            if "error" not in result and len(result.get("fees", [])) > 0:
                logger.info(f"✅ Success with {model}")
                return result
        except Exception as e:
            logger.warning(f"❌ {model} failed: {e}")
            continue
    
    return {"error": "All models failed"}
```

---

## Quick Reference

### Common Commands

```powershell
# Set API keys
$env:ANTHROPIC_API_KEY = "sk-ant-api03-..."
$env:OPENAI_API_KEY = "sk-..."

# Generate analysis with Claude
python scripts/generate_exhaustive_summary.py --model claude-sonnet-4-20250514

# Start API server
python scripts/run_api.py

# Test cost comparison tables
Invoke-RestMethod -Uri "http://localhost:8000/cost-comparison-tables?model=claude-sonnet-4-20250514"

# Compare GPT vs Claude
python scripts/compare_gpt_vs_claude.py
```

### File Locations

- **Broker metadata:** `data/brokers.yaml`
- **PDF text:** `data/output/pdf_text/*.txt`
- **Cost analysis JSON:** `data/output/broker_cost_analyses.json`
- **Summary markdown:** `data/output/exhaustive_cost_charges_summary.md`
- **API server:** `src/be_invest/api/server.py`
- **Summary script:** `scripts/generate_exhaustive_summary.py`

### Key URLs

- **API Server:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Anthropic Console:** https://console.anthropic.com
- **OpenAI Platform:** https://platform.openai.com

---

## Support & Feedback

For issues or questions:
1. Check logs in console output
2. Review troubleshooting section above
3. Validate API keys and rate limits
4. Open issue in project repository

---

**Last Updated:** December 6, 2025  
**Version:** 1.0

