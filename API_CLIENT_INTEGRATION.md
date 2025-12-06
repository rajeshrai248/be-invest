# be-invest API Client Integration Guide

**Version:** 1.0  
**Last Updated:** December 6, 2025  
**Base URL:** `http://localhost:8000` (default)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Authentication](#authentication)
4. [Base URL & Endpoints](#base-url--endpoints)
5. [API Reference](#api-reference)
6. [Code Examples](#code-examples)
7. [Error Handling](#error-handling)
8. [Rate Limits](#rate-limits)
9. [Best Practices](#best-practices)
10. [Support](#support)

---

## Introduction

The **be-invest API** provides programmatic access to Belgian broker fee analysis and cost comparison data. This API allows you to:

- ✅ Retrieve comprehensive broker cost analysis
- ✅ Generate dynamic cost comparison tables for ETFs, Stocks, and Bonds
- ✅ Refresh broker PDF data in real-time
- ✅ Access detailed fee breakdowns by broker and product type
- ✅ Export markdown summaries of all broker costs

**Use Cases:**
- Financial comparison websites
- Investment advisory platforms
- Personal finance applications
- Market research and analysis
- Automated cost monitoring systems

---

## Getting Started

### Prerequisites

- HTTP client library (e.g., `requests`, `axios`, `fetch`)
- JSON parser
- Network access to the API server

### Quick Start

**1. Check server health:**
```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "ok"
}
```

**2. Get all broker cost analysis:**
```bash
curl http://localhost:8000/cost-analysis
```

**3. Get cost comparison tables:**
```bash
curl "http://localhost:8000/cost-comparison-tables?model=claude-sonnet-4-20250514"
```

---

## Authentication

**Current Version:** No authentication required (v0.1.0)

> **Note:** Future versions may implement API key authentication for production deployments. The current version is designed for internal use and trusted networks.

---

## Base URL & Endpoints

### Base URL

```
http://localhost:8000
```

For production deployments, replace with your server's domain:
```
https://api.yourdomain.com
```

### Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/cost-analysis` | Get all broker cost analyses |
| `GET` | `/cost-analysis/{broker_name}` | Get specific broker analysis |
| `GET` | `/cost-comparison-tables` | Generate comparison tables (LLM-powered) |
| `GET` | `/financial-analysis` | Generate comprehensive financial blog post (LLM-powered) |
| `GET` | `/brokers` | List all configured brokers |
| `GET` | `/summary` | Get markdown summary report |
| `POST` | `/refresh-pdfs` | Download and extract broker PDFs |
| `POST` | `/refresh-and-analyze` | Full refresh + LLM analysis |

---

## API Reference

### 1. Health Check

Check if the API server is running and responsive.

**Endpoint:** `GET /health`

**Parameters:** None

**Response:**
```json
{
  "status": "ok"
}
```

**HTTP Status Codes:**
- `200 OK` - Server is healthy

**Example:**
```bash
curl http://localhost:8000/health
```

---

### 2. Get All Cost Analyses

Retrieve comprehensive cost and charges analysis for all brokers.

**Endpoint:** `GET /cost-analysis`

**Parameters:** None

**Response Structure:**
```json
{
  "ING Self Invest": {
    "shares_stock_exchange_traded_funds_trackers": {
      "euronext_brussels_amsterdam_paris": {
        "via_web_and_app": "0.35%",
        "min_via_web_and_app": "€1",
        "max_via_web_and_app": null,
        "via_phone": "0.60%",
        "min_via_phone": "€25"
      }
    },
    "bonds": {
      "fee": "0.50%",
      "minimum": "€50"
    },
    "custody_fees": {
      "belgian_securities": "Free",
      "foreign_securities": "0.12% per year (min €30/year)"
    }
  },
  "Bolero": {
    "stock_markets_online": {
      "brussels_amsterdam_paris": {
        "0_to_€_250": "€ 2.5",
        "€_250_to_€_500": "€ 5",
        "€_500_to_€_1,000": "€ 7.5",
        "€_1,000_to_€_2,500": "€ 10"
      }
    }
  }
}
```

**HTTP Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Analysis file not found (run `generate_exhaustive_summary.py` first)
- `500 Internal Server Error` - Failed to load analysis

**Example:**
```bash
curl http://localhost:8000/cost-analysis
```

---

### 3. Get Broker-Specific Analysis

Retrieve cost analysis for a single broker.

**Endpoint:** `GET /cost-analysis/{broker_name}`

**Path Parameters:**
- `broker_name` (string, required) - Exact broker name (case-sensitive)

**Example broker names:**
- `ING Self Invest`
- `Bolero`
- `Keytrade Bank`
- `Re=Bel`
- `Revolut`

**Response Structure:**
```json
{
  "broker": "ING Self Invest",
  "analysis": {
    "shares_stock_exchange_traded_funds_trackers": {
      "euronext_brussels_amsterdam_paris": {
        "via_web_and_app": "0.35%",
        "min_via_web_and_app": "€1"
      }
    }
  }
}
```

**HTTP Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Broker not found or analysis file missing

**Example:**
```bash
curl "http://localhost:8000/cost-analysis/ING%20Self%20Invest"
```

---

### 4. Generate Cost Comparison Tables

Generate three matrix tables comparing transaction costs across brokers for different order sizes.

**Endpoint:** `GET /cost-comparison-tables`

**Query Parameters:**
- `model` (string, optional) - LLM model to use
  - Default: `gpt-4o` (recommended for accuracy)
  - Options: `claude-sonnet-4-20250514`, `gpt-4o`, `gpt-4-turbo`

**Transaction Sizes:** €250, €500, €1,000, €1,500, €2,000, €2,500, €5,000, €10,000, €50,000

**Response Structure:**
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
    },
    {
      "broker": "Bolero",
      "250": 2.5,
      "500": 5.0,
      "1000": 5.0,
      "1500": 7.5,
      "2000": 7.5,
      "2500": 7.5,
      "5000": 10.0,
      "10000": 15.0,
      "50000": 50.0
    }
  ],
  "stocks": [
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
  "bonds": [
    {
      "broker": "ING Self Invest",
      "250": 50.0,
      "500": 50.0,
      "1000": 50.0,
      "1500": 50.0,
      "2000": 50.0,
      "2500": 62.5,
      "5000": 75.0,
      "10000": 100.0,
      "50000": 250.0
    }
  ],
  "notes": {
    "ING Self Invest": {
      "stocks": "0.35% with €1 minimum via web/app",
      "etfs": "Same as stocks",
      "bonds": "0.50% with €50 minimum"
    },
    "Keytrade Bank": {
      "stocks": "Tiered pricing: €2.45 up to €250, €5.95 up to €2,500, €14.95 up to €10,000, then +€7.50 per €10,000"
    }
  }
}
```

**HTTP Status Codes:**
- `200 OK` - Success
- `404 Not Found` - No valid broker data found
- `500 Internal Server Error` - LLM call failed or JSON parsing error

**Example:**
```bash
# Using GPT-4o (default)
curl "http://localhost:8000/cost-comparison-tables"

# Using Claude
curl "http://localhost:8000/cost-comparison-tables?model=claude-sonnet-4-20250514"
```

---

### 5. Generate Financial Analysis

Generate a comprehensive, structured financial analysis comparing Belgian investment brokers across ETFs, Stocks, and Bonds.

**Endpoint:** `GET /financial-analysis`

**Query Parameters:**
- `model` (string, optional) - LLM model to use
  - Default: `gpt-4o`
  - Options: `gpt-4o`, `claude-sonnet-4-20250514`, `gpt-4-turbo`

**Response:** JSON (Structured data - perfect for React/Vue/Angular apps)

**What It Generates:**

The endpoint produces structured JSON with:

- **Metadata** - Title, subtitle, publication date, reading time
- **Executive Summary** - Array of key findings
- **Sections** - ETF Trading, Stock Trading, Bond Trading (with tables, scenarios, callouts)
- **Broker Comparisons** - Ratings, pros/cons, best-for recommendations
- **Investment Scenarios** - Cost calculations for different investor types
- **Market Insights** - 2025 trends and 2026 outlook
- **Recommendations** - Best broker by category
- **Checklist** - Decision-making questions

**JSON Structure:**
```json
{
  "metadata": {
    "title": "Belgian Broker Battle 2025: The Ultimate Cost Comparison Guide",
    "subtitle": "Which Belgian investment platform will save you the most money?",
    "publishDate": "December 06, 2025",
    "readingTimeMinutes": 12,
    "lastUpdated": "2025-12-06T10:30:00Z"
  },
  "executiveSummary": [
    "ETF Champions: DEGIRO dominates with €0 fees on core ETFs",
    "Active Traders: Keytrade Bank emerges as cost leader at €2.45-14.95",
    "Wealth Builders: Belfius and ING excel for bond portfolios",
    "Hidden Costs Alert: Currency conversion fees can add €100-500 annually"
  ],
  "sections": [
    {
      "id": "etf-trading",
      "title": "ETF Trading Costs",
      "icon": "💰",
      "content": [
        {
          "type": "paragraph",
          "text": "Exchange-traded funds have become the cornerstone..."
        },
        {
          "type": "table",
          "caption": "ETF Cost Comparison",
          "headers": ["Broker", "Core ETFs", "€500", "€2000", "€10000"],
          "rows": [
            {
              "broker": "DEGIRO",
              "coreETFs": "€0.00",
              "cost500": "€0.00",
              "cost2000": "€2.00",
              "cost10000": "€2.00",
              "rating": 5
            }
          ]
        },
        {
          "type": "callout",
          "style": "tip",
          "title": "Pro Tip",
          "text": "DEGIRO's core ETF selection includes over 200 popular funds"
        }
      ]
    }
  ],
  "brokerComparisons": [
    {
      "broker": "DEGIRO",
      "overallRating": 5,
      "ratings": {
        "etfs": 5,
        "euStocks": 5,
        "usStocks": 5,
        "bonds": 4,
        "platform": 3
      },
      "pros": ["Unbeatable costs", "International access"],
      "cons": ["Limited banking integration"],
      "bestFor": ["ETF investors", "Active traders"]
    }
  ],
  "investmentScenarios": [
    {
      "id": "young-professional",
      "title": "The Young Professional",
      "icon": "👨‍💼",
      "profile": "28 years old, €500/month into ETFs",
      "annualCosts": [
        {"broker": "DEGIRO", "cost": 0, "winner": true},
        {"broker": "Bolero", "cost": 30}
      ],
      "recommendation": "DEGIRO for pure cost efficiency"
    }
  ],
  "marketInsights": {
    "trends2025": [
      {
        "title": "Fee Compression",
        "description": "Average ETF costs dropped 40% since 2020"
      }
    ],
    "outlook2026": [
      "Fractional shares across all brokers",
      "Crypto integration by traditional brokers"
    ]
  },
  "recommendations": {
    "categoryWinners": [
      {
        "category": "Best Overall Value",
        "winner": "DEGIRO Belgium",
        "reasoning": "Unmatched cost structure",
        "bestFor": ["ETF investors", "International trading"]
      }
    ]
  },
  "checklist": {
    "investmentStyle": [
      {
        "question": "Do I primarily invest in ETFs?",
        "recommendation": "Consider DEGIRO"
      }
    ]
  }
}
```
- **Best for Active Traders:** Keytrade Bank provides competitive rates...
- **Best for Bonds:** Bolero specializes in fixed income...
- **Hidden Costs:** Watch out for custody fees that can eat 0.12% annually...

[... full analysis continues ...]
```

**HTTP Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Broker data not found
- `500 Internal Server Error` - LLM generation failed

**Example:**
```bash
# Generate with default model (GPT-4o)
curl "http://localhost:8000/financial-analysis" > financial_analysis.md

# Generate with default model
curl "http://localhost:8000/financial-analysis" > financial_analysis.json

# Generate with Claude for higher quality
curl "http://localhost:8000/financial-analysis?model=claude-sonnet-4-20250514" > financial_analysis.json
```

**Python Example:**
```python
import requests
import json

response = requests.get("http://localhost:8000/financial-analysis")
analysis_data = response.json()

# Access structured data
print(f"Title: {analysis_data['metadata']['title']}")
print(f"Executive Summary: {len(analysis_data['executiveSummary'])} points")
print(f"Sections: {len(analysis_data['sections'])}")
print(f"Brokers analyzed: {len(analysis_data['brokerComparisons'])}")

# Save to file
with open("financial_analysis.json", "w", encoding="utf-8") as f:
    json.dump(analysis_data, f, indent=2)

# Use in your React app
# Pass analysis_data to your React components for rendering
```

**React/TypeScript Example:**
```typescript
interface FinancialAnalysis {
  metadata: {
    title: string;
    subtitle: string;
    publishDate: string;
    readingTimeMinutes: number;
  };
  executiveSummary: string[];
  sections: Section[];
  brokerComparisons: BrokerComparison[];
  // ... other fields
}

async function fetchAnalysis(): Promise<FinancialAnalysis> {
  const response = await fetch('http://localhost:8000/financial-analysis');
  return response.json();
}

// In your React component:
function FinancialAnalysisPage() {
  const [analysis, setAnalysis] = useState<FinancialAnalysis | null>(null);
  
  useEffect(() => {
    fetchAnalysis().then(setAnalysis);
  }, []);
  
  if (!analysis) return <Loading />;
  
  return (
    <div>
      <h1>{analysis.metadata.title}</h1>
      <p>{analysis.metadata.subtitle}</p>
      
      {/* Render executive summary */}
      <ExecutiveSummary items={analysis.executiveSummary} />
      
      {/* Render sections with custom styling */}
      {analysis.sections.map(section => (
        <Section key={section.id} data={section} />
      ))}
      
      {/* Render broker comparisons */}
      <BrokerGrid brokers={analysis.brokerComparisons} />
    </div>
  );
}
```

**JavaScript Example:**
```javascript
const response = await fetch("http://localhost:8000/financial-analysis");
const markdown = await response.text();

// Display or save
console.log(markdown);
```

**Use Cases:**
- Generate investment research reports
- Create comparison articles for financial blogs
- Produce client-facing broker recommendations
- Market analysis for investment advisors
- Educational content for retail investors

---

### 6. List All Brokers

Get metadata for all configured brokers.

**Endpoint:** `GET /brokers`

**Parameters:** None

**Response Structure:**
```json
[
  {
    "name": "ING Self Invest",
    "country": "Belgium",
    "website": "https://www.ing.be/en/retail/daily-banking/investing",
    "data_sources": [
      {
        "url": "https://www.ing.be/...",
        "type": "pdf",
        "description": "Tariff guide",
        "allowed_to_scrape": false
      }
    ]
  },
  {
    "name": "Bolero",
    "country": "Belgium",
    "website": "https://www.bolero.be"
  }
]
```

**HTTP Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Brokers configuration file not found

**Example:**
```bash
curl http://localhost:8000/brokers
```

---

### 7. Get Summary Report

Retrieve the comprehensive markdown summary of all broker costs.

**Endpoint:** `GET /summary`

**Parameters:** None

**Response:** Plain text (Markdown format)

**Example Response:**
```markdown
# Belgian Broker Cost & Charges Summary

## ING Self Invest

### Transaction Fees

#### Stocks/ETFs
- Via web/app: 0.35% (min €1)
- Via phone: 0.60% (min €25)

#### Bonds
- 0.50% (min €50)

### Custody Fees
- Belgian securities: Free
- Foreign securities: 0.12% per year (min €30/year)
```

**HTTP Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Summary file not found

**Example:**
```bash
curl http://localhost:8000/summary > broker_summary.md
```

---

### 8. Refresh PDFs

Download broker PDFs and extract text content.

**Endpoint:** `POST /refresh-pdfs`

**Query Parameters:**
- `brokers_to_refresh` (array of strings, optional) - Specific brokers to refresh (if omitted, refreshes all)
- `force` (boolean, optional) - Ignore `allowed_to_scrape` flag (default: `false`)
- `save_dir` (string, optional) - Directory to save extracted text (default: `data/output/pdf_text`)

**Request Body:** None

**Response Structure:**
```json
{
  "status": "completed",
  "message": "Scraping process finished.",
  "records_found_by_broker": {
    "ING Self Invest": 15,
    "Bolero": 12,
    "Keytrade Bank": 18
  },
  "total_records_found": 45
}
```

**HTTP Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Broker not found or configuration file missing
- `500 Internal Server Error` - Scraping failed

**Example:**
```bash
# Refresh all brokers
curl -X POST "http://localhost:8000/refresh-pdfs"

# Refresh specific brokers
curl -X POST "http://localhost:8000/refresh-pdfs?brokers_to_refresh=ING%20Self%20Invest&brokers_to_refresh=Bolero"

# Force refresh (ignore allowed_to_scrape)
curl -X POST "http://localhost:8000/refresh-pdfs?force=true"
```

---

### 9. Refresh and Analyze

Complete workflow: download PDFs, extract text, and generate LLM-powered analysis.

**Endpoint:** `POST /refresh-and-analyze`

**Query Parameters:**
- `brokers_to_process` (array of strings, optional) - Specific brokers to analyze (if omitted, analyzes all)
- `force` (boolean, optional) - Ignore `allowed_to_scrape` flag (default: `false`)
- `model` (string, optional) - LLM model to use (Default: `gpt-4o`)
  - Options: `claude-sonnet-4-20250514`, `gpt-4o`, `gpt-4-turbo`

**Request Body:** None

**Response Structure:**
```json
{
  "status": "completed",
  "refresh_results": {
    "status": "completed",
    "duration_seconds": 45.67,
    "records_found_by_broker": {
      "ING Self Invest": 15,
      "Bolero": 12
    },
    "total_records_found": 27
  },
  "analysis_results": {
    "brokers_analyzed": 2,
    "duration_seconds": 23.45,
    "model_used": "gpt-4o",
    "analyses": {
      "ING Self Invest": {
        "shares_stock_exchange_traded_funds_trackers": {
          "euronext_brussels_amsterdam_paris": {
            "via_web_and_app": "0.35%"
          }
        }
      },
      "Bolero": {
        "stock_markets_online": {
          "brussels_amsterdam_paris": {
            "0_to_€_250": "€ 2.5"
          }
        }
      }
    }
  },
  "output_file": "data/output/broker_cost_analyses.json"
}
```

**HTTP Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Broker not found
- `500 Internal Server Error` - Process failed (PDF download, extraction, or LLM analysis)

**Example:**
```bash
# Full refresh with Claude (recommended)
curl -X POST "http://localhost:8000/refresh-and-analyze?model=claude-sonnet-4-20250514"

# Specific brokers with Claude
curl -X POST "http://localhost:8000/refresh-and-analyze?brokers_to_process=ING%20Self%20Invest&brokers_to_process=Bolero&model=claude-sonnet-4-20250514"
```

---

## Code Examples

### Python

#### Basic Usage

```python
import requests

BASE_URL = "http://localhost:8000"

# Health check
response = requests.get(f"{BASE_URL}/health")
print(response.json())  # {'status': 'ok'}

# Get all cost analyses
response = requests.get(f"{BASE_URL}/cost-analysis")
data = response.json()
print(f"Brokers: {list(data.keys())}")

# Get specific broker
response = requests.get(f"{BASE_URL}/cost-analysis/ING Self Invest")
broker_data = response.json()
print(broker_data['broker'])  # 'ING Self Invest'
```

#### Client Class

```python
import requests
from typing import Optional, List, Dict, Any

class BeInvestClient:
    """Client for be-invest API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def health_check(self) -> Dict[str, str]:
        """Check API health."""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def get_cost_analysis(self, broker_name: Optional[str] = None) -> Dict[str, Any]:
        """Get cost analysis for all brokers or a specific broker."""
        if broker_name:
            url = f"{self.base_url}/cost-analysis/{broker_name}"
        else:
            url = f"{self.base_url}/cost-analysis"
        
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_comparison_tables(self, model: str = "gpt-4o") -> Dict[str, Any]:
        """Generate cost comparison tables."""
        response = self.session.get(
            f"{self.base_url}/cost-comparison-tables",
            params={"model": model}
        )
        response.raise_for_status()
        return response.json()
    
    def get_financial_analysis(self, model: str = "gpt-4o") -> Dict[str, Any]:
        """Generate comprehensive financial analysis (JSON)."""
        response = self.session.get(
            f"{self.base_url}/financial-analysis",
            params={"model": model}
        )
        response.raise_for_status()
        return response.json()
    
    def list_brokers(self) -> List[Dict[str, Any]]:
        """List all configured brokers."""
        response = self.session.get(f"{self.base_url}/brokers")
        response.raise_for_status()
        return response.json()
    
    def get_summary(self) -> str:
        """Get markdown summary report."""
        response = self.session.get(f"{self.base_url}/summary")
        response.raise_for_status()
        return response.text
    
    def refresh_pdfs(
        self,
        brokers: Optional[List[str]] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """Refresh broker PDFs."""
        params = {"force": force}
        if brokers:
            params["brokers_to_refresh"] = brokers
        
        response = self.session.post(
            f"{self.base_url}/refresh-pdfs",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def refresh_and_analyze(
        self,
        brokers: Optional[List[str]] = None,
        model: str = "gpt-4o",
        force: bool = False
    ) -> Dict[str, Any]:
        """Refresh PDFs and run LLM analysis."""
        params = {"model": model, "force": force}
        if brokers:
            params["brokers_to_process"] = brokers
        
        response = self.session.post(
            f"{self.base_url}/refresh-and-analyze",
            params=params
        )
        response.raise_for_status()
        return response.json()

# Usage
client = BeInvestClient()

# Check health
print(client.health_check())

# Get comparison tables with Claude (recommended)
tables = client.get_comparison_tables(model="claude-sonnet-4-20250514")
print(f"ETF brokers: {len(tables['etfs'])}")
print(f"Stock brokers: {len(tables['stocks'])}")
print(f"Bond brokers: {len(tables['bonds'])}")

# Generate financial analysis (JSON structure)
analysis = client.get_financial_analysis(model="gpt-4o")
print(f"Title: {analysis['metadata']['title']}")
print(f"Sections: {len(analysis['sections'])}")
print(f"Brokers: {len(analysis['brokerComparisons'])}")

# Save to JSON file
import json
with open("financial_analysis.json", "w", encoding="utf-8") as f:
    json.dump(analysis, f, indent=2)
    f.write(analysis)
print(f"Generated {len(analysis)} character analysis")

# Get specific broker analysis
ing_data = client.get_cost_analysis("ING Self Invest")
print(ing_data)

# Refresh and analyze
result = client.refresh_and_analyze(
    brokers=["ING Self Invest", "Bolero"],
    model="claude-sonnet-4-20250514"
)
print(f"Analysis completed in {result['analysis_results']['duration_seconds']}s")
```

---

### JavaScript/TypeScript

#### Basic Usage (Node.js with fetch)

```javascript
const BASE_URL = "http://localhost:8000";

// Health check
async function healthCheck() {
  const response = await fetch(`${BASE_URL}/health`);
  const data = await response.json();
  console.log(data); // { status: 'ok' }
}

// Get all cost analyses
async function getAllCostAnalyses() {
  const response = await fetch(`${BASE_URL}/cost-analysis`);
  const data = await response.json();
  console.log("Brokers:", Object.keys(data));
  return data;
}

// Get specific broker
async function getBrokerAnalysis(brokerName) {
  const response = await fetch(
    `${BASE_URL}/cost-analysis/${encodeURIComponent(brokerName)}`
  );
  const data = await response.json();
  return data;
}

// Get comparison tables
async function getComparisonTables(model = "gpt-4o") {
  const response = await fetch(
    `${BASE_URL}/cost-comparison-tables?model=${model}`
  );
  const data = await response.json();
  console.log(`ETFs: ${data.etfs.length} brokers`);
  console.log(`Stocks: ${data.stocks.length} brokers`);
  console.log(`Bonds: ${data.bonds.length} brokers`);
  return data;
}

// Run examples
healthCheck();
getAllCostAnalyses();
getBrokerAnalysis("ING Self Invest");
getComparisonTables("claude-sonnet-4-20250514");
```

#### TypeScript Client Class

```typescript
interface CostAnalysis {
  [brokerName: string]: any;
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

interface ComparisonTables {
  etfs: BrokerRow[];
  stocks: BrokerRow[];
  bonds: BrokerRow[];
  notes: Record<string, Record<string, string>>;
}

interface RefreshResult {
  status: string;
  duration_seconds: number;
  records_found_by_broker: Record<string, number>;
  total_records_found: number;
}

interface AnalyzeResult {
  status: string;
  refresh_results: RefreshResult;
  analysis_results: {
    brokers_analyzed: number;
    duration_seconds: number;
    model_used: string;
    analyses: Record<string, any>;
  };
  output_file: string;
}

class BeInvestClient {
  private baseUrl: string;

  constructor(baseUrl: string = "http://localhost:8000") {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async healthCheck(): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/health`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async getCostAnalysis(brokerName?: string): Promise<CostAnalysis> {
    const url = brokerName
      ? `${this.baseUrl}/cost-analysis/${encodeURIComponent(brokerName)}`
      : `${this.baseUrl}/cost-analysis`;
    
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async getComparisonTables(
    model: string = "gpt-4o"
  ): Promise<ComparisonTables> {
    const response = await fetch(
      `${this.baseUrl}/cost-comparison-tables?model=${model}`
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async getFinancialAnalysis(
    model: string = "gpt-4o"
  ): Promise<FinancialAnalysis> {
    const response = await fetch(
      `${this.baseUrl}/financial-analysis?model=${model}`
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async listBrokers(): Promise<any[]> {
    const response = await fetch(`${this.baseUrl}/brokers`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async getSummary(): Promise<string> {
    const response = await fetch(`${this.baseUrl}/summary`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.text();
  }

  async refreshPdfs(
    brokers?: string[],
    force: boolean = false
  ): Promise<RefreshResult> {
    const params = new URLSearchParams({ force: force.toString() });
    if (brokers) {
      brokers.forEach(b => params.append("brokers_to_refresh", b));
    }

    const response = await fetch(
      `${this.baseUrl}/refresh-pdfs?${params}`,
      { method: "POST" }
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async refreshAndAnalyze(
    brokers?: string[],
    model: string = "gpt-4o",
    force: boolean = false
  ): Promise<AnalyzeResult> {
    const params = new URLSearchParams({
      model,
      force: force.toString()
    });
    if (brokers) {
      brokers.forEach(b => params.append("brokers_to_process", b));
    }

    const response = await fetch(
      `${this.baseUrl}/refresh-and-analyze?${params}`,
      { method: "POST" }
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
}

// Usage
const client = new BeInvestClient();

// Get comparison tables
const tables = await client.getComparisonTables("claude-sonnet-4-20250514");
console.log(`Found ${tables.etfs.length} ETF brokers`);

// Generate financial analysis (JSON structure)
const analysis = await client.getFinancialAnalysis("gpt-4o");
console.log(`Title: ${analysis.metadata.title}`);
console.log(`Sections: ${analysis.sections.length}`);
console.log(`Brokers: ${analysis.brokerComparisons.length}`);

// Save to JSON file (Node.js)
const fs = require('fs');
fs.writeFileSync('financial_analysis.json', JSON.stringify(analysis, null, 2));

// Use in React component
// <FinancialAnalysisPage data={analysis} />

// Refresh and analyze specific brokers
const result = await client.refreshAndAnalyze(
  ["ING Self Invest", "Bolero"],
  "gpt-4o"
);
console.log(`Completed in ${result.analysis_results.duration_seconds}s`);
```

---

### cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# Get all cost analyses
curl http://localhost:8000/cost-analysis

# Get specific broker (URL-encode spaces)
curl "http://localhost:8000/cost-analysis/ING%20Self%20Invest"

# Get comparison tables with Claude
curl "http://localhost:8000/cost-comparison-tables?model=claude-sonnet-4-20250514"

# List all brokers
curl http://localhost:8000/brokers

# Get summary
curl http://localhost:8000/summary > broker_summary.md

# Refresh PDFs for specific brokers
curl -X POST "http://localhost:8000/refresh-pdfs?brokers_to_refresh=ING%20Self%20Invest&brokers_to_refresh=Bolero"

# Full refresh and analyze with Claude
curl -X POST "http://localhost:8000/refresh-and-analyze?brokers_to_process=ING%20Self%20Invest&model=claude-sonnet-4-20250514"
```

---

### PowerShell Examples

```powershell
# Health check
Invoke-RestMethod -Uri "http://localhost:8000/health"

# Get all cost analyses
$analysis = Invoke-RestMethod -Uri "http://localhost:8000/cost-analysis"
$analysis.Keys  # List broker names

# Get specific broker
$ing = Invoke-RestMethod -Uri "http://localhost:8000/cost-analysis/ING Self Invest"
$ing.analysis

# Get comparison tables
$tables = Invoke-RestMethod -Uri "http://localhost:8000/cost-comparison-tables?model=claude-sonnet-4-20250514"
$tables.etfs | Format-Table
$tables.stocks | Format-Table

# Save summary to file
Invoke-WebRequest -Uri "http://localhost:8000/summary" -OutFile "broker_summary.md"

# Refresh PDFs
$result = Invoke-RestMethod -Uri "http://localhost:8000/refresh-pdfs" -Method POST
$result

# Refresh and analyze with parameters
$params = @{
    Uri = "http://localhost:8000/refresh-and-analyze"
    Method = "POST"
    Body = (@{
        brokers_to_process = @("ING Self Invest", "Bolero")
        model = "gpt-4o"
        force = $false
    } | ConvertTo-Json)
    ContentType = "application/json"
}
$result = Invoke-RestMethod @params
Write-Host "Analysis completed in $($result.analysis_results.duration_seconds)s"
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| `200` | OK | Request successful |
| `404` | Not Found | Resource doesn't exist, broker not found, or data not generated yet |
| `500` | Internal Server Error | Server error, LLM failure, file I/O error |

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Errors

#### 1. Cost Analysis Not Found (404)

**Error:**
```json
{
  "detail": "Cost analysis file not found. Run generate_exhaustive_summary.py first."
}
```

**Solution:**
- Run the analysis generation script first:
  ```bash
  python scripts/generate_exhaustive_summary.py
  ```
- Or use the API endpoint:
  ```bash
  curl -X POST "http://localhost:8000/refresh-and-analyze"
  ```

---

#### 2. Broker Not Found (404)

**Error:**
```json
{
  "detail": "Broker not found: Unknown Broker. Available: ING Self Invest, Bolero, Keytrade Bank"
}
```

**Solution:**
- Check available brokers:
  ```bash
  curl http://localhost:8000/brokers
  ```
- Use exact broker name (case-sensitive)

---

#### 3. LLM API Error (500)

**Error:**
```json
{
  "detail": "OpenAI API call failed: Invalid API key"
}
```

**Solution:**
- Ensure API keys are set:
  ```bash
  export OPENAI_API_KEY="sk-..."
  export ANTHROPIC_API_KEY="sk-ant-..."
  ```
- Check API key validity at provider's console
- Verify sufficient API credits/quota

---

#### 4. Rate Limit Error (500)

**Error:**
```json
{
  "detail": "Anthropic API call failed: rate_limit_error"
}
```

**Solution:**
- Wait and retry (implement exponential backoff)
- Monitor rate limits:
  - OpenAI: https://platform.openai.com/usage
  - Anthropic: https://console.anthropic.com/settings/usage
- Consider using a different model

---

### Error Handling Best Practices

#### Python

```python
import requests
from requests.exceptions import HTTPError, Timeout, ConnectionError
import time

def safe_api_call(url, max_retries=3, backoff_factor=2):
    """Make API call with retry logic."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        
        except HTTPError as e:
            if e.response.status_code == 404:
                # Resource not found - don't retry
                raise
            elif e.response.status_code == 500:
                # Server error - retry with backoff
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    print(f"Server error, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
            else:
                raise
        
        except (Timeout, ConnectionError) as e:
            # Network error - retry
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"Network error, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise

# Usage
try:
    data = safe_api_call("http://localhost:8000/cost-analysis")
    print(f"Success: {len(data)} brokers")
except HTTPError as e:
    print(f"HTTP error: {e.response.status_code}")
    print(f"Details: {e.response.json().get('detail')}")
except Exception as e:
    print(f"Error: {e}")
```

#### TypeScript

```typescript
async function apiCallWithRetry<T>(
  url: string,
  maxRetries: number = 3,
  backoffFactor: number = 2
): Promise<T> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const response = await fetch(url);
      
      if (!response.ok) {
        if (response.status === 404) {
          // Resource not found - don't retry
          throw new Error(`Not found: ${url}`);
        }
        
        if (response.status === 500 && attempt < maxRetries - 1) {
          // Server error - retry
          const waitTime = Math.pow(backoffFactor, attempt) * 1000;
          console.log(`Server error, retrying in ${waitTime}ms...`);
          await new Promise(resolve => setTimeout(resolve, waitTime));
          continue;
        }
        
        const error = await response.json();
        throw new Error(error.detail || `HTTP ${response.status}`);
      }
      
      return response.json();
    } catch (error) {
      if (attempt === maxRetries - 1) throw error;
      
      // Network error - retry
      const waitTime = Math.pow(backoffFactor, attempt) * 1000;
      console.log(`Network error, retrying in ${waitTime}ms...`);
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
  }
  
  throw new Error("Max retries exceeded");
}

// Usage
try {
  const data = await apiCallWithRetry("http://localhost:8000/cost-analysis");
  console.log(`Success: ${Object.keys(data).length} brokers`);
} catch (error) {
  console.error("API call failed:", error.message);
}
```

---

## Rate Limits

### Current Limits

**API Server:** No built-in rate limits (v0.1.0)

**LLM Providers:**

| Provider | Model | Requests/min | Tokens/min (Input) | Tokens/min (Output) |
|----------|-------|--------------|-------------------|---------------------|
| OpenAI | gpt-4o | 500 | 30,000 | 10,000 |
| Anthropic | claude-3-5-sonnet | 50 | 40,000 | 8,000 |

> **Note:** Limits shown are for Tier 1 accounts. Check provider console for your actual limits.

### Best Practices

1. **Cache Results** - Store API responses locally and refresh only when needed
2. **Batch Requests** - Use `/refresh-and-analyze` instead of multiple separate calls
3. **Implement Backoff** - Use exponential backoff for retries
4. **Monitor Usage** - Track API calls to avoid hitting limits
5. **Choose Models Wisely** - Use faster models (gpt-4o) for routine queries, Claude for complex analysis

---

## Best Practices

### 1. Initialization

Always check server health before making requests:

```python
client = BeInvestClient()
if client.health_check()['status'] == 'ok':
    # Proceed with API calls
    pass
```

### 2. Caching

Cache API responses to reduce load and improve performance:

```python
import json
from pathlib import Path
from datetime import datetime, timedelta

class CachedClient:
    def __init__(self, client, cache_dir="cache", cache_ttl_hours=24):
        self.client = client
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
    
    def get_cost_analysis(self):
        cache_file = self.cache_dir / "cost_analysis.json"
        
        # Check cache
        if cache_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - mtime < self.cache_ttl:
                return json.loads(cache_file.read_text())
        
        # Fetch fresh data
        data = self.client.get_cost_analysis()
        cache_file.write_text(json.dumps(data, indent=2))
        return data
```

### 3. Error Handling

Always handle errors gracefully:

```python
try:
    data = client.get_cost_analysis("ING Self Invest")
except requests.HTTPError as e:
    if e.response.status_code == 404:
        print("Broker not found or data not generated")
    else:
        print(f"API error: {e}")
except requests.Timeout:
    print("Request timed out")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### 4. Model Selection

Choose the appropriate model for your use case:

```python
# For best accuracy (recommended)
tables = client.get_comparison_tables(model="claude-sonnet-4-20250514")

# For speed when accuracy is less critical
tables = client.get_comparison_tables(model="gpt-4o")
```

### 5. Selective Refresh

Refresh only the brokers you need:

```python
# Instead of refreshing all brokers
result = client.refresh_and_analyze(
    brokers=["ING Self Invest", "Bolero"],  # Only these two
    model="claude-sonnet-4-20250514"  # Use Claude for best accuracy
)
```

### 6. Async Operations

For better performance with multiple requests:

```python
import asyncio
import aiohttp

async def fetch_multiple_brokers(broker_names):
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_broker(session, name) 
            for name in broker_names
        ]
        return await asyncio.gather(*tasks)

async def fetch_broker(session, broker_name):
    url = f"http://localhost:8000/cost-analysis/{broker_name}"
    async with session.get(url) as response:
        return await response.json()

# Usage
brokers = ["ING Self Invest", "Bolero", "Keytrade Bank"]
results = asyncio.run(fetch_multiple_brokers(brokers))
```

---

## Support

### Documentation

- **Main README:** `README.md`
- **API Reference:** `API_REFERENCE.md`
- **Quick Start:** `API_QUICK_START.md`
- **Claude Integration:** `CLAUDE_INTEGRATION.md`

### Server Logs

Enable detailed logging when starting the server:

```bash
python scripts/run_api.py --log-level DEBUG
```

### Interactive API Docs

Visit the auto-generated Swagger UI:

```
http://localhost:8000/docs
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Connection refused | Ensure server is running: `python scripts/run_api.py` |
| 404 errors | Run `python scripts/generate_exhaustive_summary.py` first |
| LLM errors | Check API keys: `echo $OPENAI_API_KEY` |
| Timeout | Increase request timeout or use smaller broker subsets |
| Empty data | Verify PDFs were downloaded: check `data/output/pdf_text/` |

### Reporting Issues

When reporting issues, include:
1. API endpoint and parameters used
2. Full error message or HTTP status code
3. Server logs (if available)
4. Request/response examples
5. Environment details (OS, Python version, etc.)

---

## Changelog

### v0.1.0 (December 6, 2025)

- Initial API release
- Support for OpenAI and Anthropic models
- 8 endpoints covering all major operations
- CORS support for web clients
- Comprehensive error handling
- JSON and Markdown response formats

---

## Legal & Compliance

**Data Usage:** This API provides access to broker fee data extracted from publicly available documents. Users are responsible for:
- Respecting broker terms of service
- Complying with data usage restrictions
- Not using data for unauthorized purposes

**Accuracy:** Fee data is extracted using LLM technology and may contain errors. Always verify critical information with official broker sources.

**Privacy:** No personal data is collected or stored by this API.

---

**Version:** 1.0  
**Last Updated:** December 6, 2025  
**Maintained by:** be-invest project contributors

