# 💰 Broker Cost & Charges Analysis

Complete cost analysis for Belgian brokers.

## Brokers Analyzed

1. **Bolero** - Competitive trading with no custody fees
2. **Keytrade Bank** - Straightforward fees, no account maintenance
3. **ING Self Invest** - Online discounts and custody charges

---

## Quick Comparison

| Broker | Equities | ETFs | Options | Custody | Best For |
|--------|----------|------|---------|---------|----------|
| Bolero | €2.5-€50 | €2.5-€50 | €3/contract | Free | Low-cost trading |
| Keytrade | €2.45-€14.95 | Variable | N/A | Free | Straightforward fees |
| ING Self Invest | 0.35% min €1 | Variable | N/A | 0.01%-0.02% | Online traders |

---

## Get Full Analysis

### Via API

```bash
# All brokers
curl http://localhost:8000/cost-analysis

# Specific broker
curl http://localhost:8000/cost-analysis/Bolero

# Markdown summary
curl http://localhost:8000/summary > analysis.md
```

### Via Python

```python
import requests

# Get all data
costs = requests.get('http://localhost:8000/cost-analysis').json()

# Print summaries
for broker_name, data in costs.items():
    print(f"\n{broker_name}:")
    print(f"  Summary: {data.get('summary', 'N/A')[:100]}...")
    
# Get specific broker
bolero = requests.get('http://localhost:8000/cost-analysis/Bolero').json()
print(f"\nBolero fee categories: {len(bolero['analysis'].get('fee_categories', []))}")
```

---

## Data Locations

- **JSON Analysis**: `data/output/broker_cost_analyses.json`
- **Markdown Summary**: `data/output/exhaustive_cost_charges_summary.md`
- **PDF Texts**: `data/output/pdf_text/`
- **Broker Config**: `data/brokers.yaml`

---

## Refresh Analysis

Get latest broker data:

```bash
# Refresh PDFs
curl -X POST http://localhost:8000/refresh-pdfs

# Full analysis (requires OPENAI_API_KEY)
curl -X POST http://localhost:8000/refresh-and-analyze
```

---

## What's Included

For each broker:
- ✅ Trading commissions (all instruments)
- ✅ Deposit/withdrawal fees
- ✅ Account fees (opening, closure, inactivity)
- ✅ Custody charges
- ✅ Special fees (FX conversion, etc.)
- ✅ Supported instruments
- ✅ Order channels
- ✅ Minimum requirements

---

## Accessing Broker Data

### Python

```python
import requests
import json

# Get all broker costs
response = requests.get('http://localhost:8000/cost-analysis')
brokers = response.json()

# Access Bolero data
bolero = brokers['Bolero']
print(f"Summary: {bolero['summary']}")
print(f"Supported: {bolero['supported_instruments']}")

# List all fee categories
for category in bolero['fee_categories']:
    print(f"\n{category['category']}")
    for tier in category['tiers']:
        print(f"  {tier['volume_or_condition']}: {tier['fee_structure']}")
```

### JavaScript

```javascript
// Fetch and display
fetch('http://localhost:8000/cost-analysis')
  .then(r => r.json())
  .then(data => {
    Object.entries(data).forEach(([broker, info]) => {
      console.log(`${broker}: ${info.summary}`);
    });
  });
```

---

## Export Options

### Save as JSON
```bash
curl http://localhost:8000/cost-analysis > broker_costs.json
```

### Save as Markdown
```bash
curl http://localhost:8000/summary > broker_analysis.md
```

### Use in Python
```python
import requests
import json

data = requests.get('http://localhost:8000/cost-analysis').json()
with open('costs.json', 'w') as f:
    json.dump(data, f, indent=2)
```

---

## Schedule Regular Updates

### Refresh Daily (Cron)
```bash
0 0 * * * curl -X POST http://localhost:8000/refresh-pdfs
```

### Refresh Weekly with Analysis
```bash
0 3 * * 0 OPENAI_API_KEY=sk-... curl -X POST http://localhost:8000/refresh-and-analyze
```

---

## Data Structure

### JSON Response Example

```json
{
  "Bolero": {
    "broker_name": "Bolero",
    "summary": "Competitive trading commissions...",
    "fee_categories": [
      {
        "category": "Trading Commission - Equities",
        "description": "Fees for trading equities...",
        "tiers": [
          {
            "volume_or_condition": "Up to €250",
            "fee_structure": "€2.5",
            "notes": "..."
          }
        ]
      }
    ],
    "supported_instruments": ["Equities", "ETFs", "Bonds", "Options", "Funds"],
    "fees_by_instrument": [...]
  }
}
```

---

## Recent Updates

- ✅ Fixed ING Self Invest data (was missing, now included)
- ✅ All broker data current as of November 20, 2025
- ✅ LLM-analyzed fee structures
- ✅ Ready for real-time refresh

---

**For API access, see:** `API_REFERENCE.md`

**For quick start, see:** `API_QUICK_START.md`

