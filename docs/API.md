# API Reference

> Complete REST API documentation for the BE-Invest broker fee analysis service.

## Base URL

- **Local Development**: `http://localhost:8000`
- **Production**: `https://your-domain.vercel.app`

## Authentication

Currently, the API does not require authentication for most endpoints. LLM extraction endpoints require valid API keys to be configured on the server.

## Content Types

- **Request**: `application/json`
- **Response**: `application/json`

## Core Endpoints

### Health Check

Check API availability and status.

```http
GET /api/health
```

**Response**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-09T18:00:00Z",
  "version": "0.1.0",
  "llm_available": true
}
```

### List Brokers

Get all supported brokers and their basic information.

```http
GET /api/brokers
```

**Response**
```json
{
  "brokers": [
    {
      "name": "Bolero",
      "website": "https://www.bolero.be/",
      "country": "Belgium",
      "instruments": ["Equities", "ETFs", "Bonds", "Funds"],
      "llm_extraction_available": true,
      "last_updated": "2025-12-09T10:00:00Z"
    }
  ],
  "total_count": 5
}
```

### Get Broker Fees

Retrieve fee information for a specific broker.

```http
GET /api/brokers/{broker_name}/fees
```

**Parameters**
- `broker_name` (path): Name of the broker (e.g., "Bolero", "Keytrade Bank")

**Query Parameters**
- `instrument_type` (optional): Filter by instrument type (`Equities`, `ETFs`, `Bonds`, `Options`)
- `order_channel` (optional): Filter by order channel (`Online Platform`, `Phone`, `Branch`)

**Response**
```json
{
  "broker": "Bolero",
  "fees": [
    {
      "instrument_type": "ETFs",
      "order_channel": "Online Platform",
      "base_fee": 15.0,
      "variable_fee": null,
      "currency": "EUR",
      "fee_structure_type": "flat",
      "notes": "Fixed fee for all ETF transactions",
      "last_extracted": "2025-12-09T10:00:00Z"
    }
  ],
  "custody_fee": {
    "has_custody_fee": true,
    "amount": "0.15% annually",
    "details": "Annual portfolio management fee"
  }
}
```

## Analysis Endpoints

### Cost Comparison

Compare transaction costs across brokers for specific trade parameters.

```http
POST /api/compare
```

**Request Body**
```json
{
  "trade_amount": 5000,
  "instrument_type": "ETFs",
  "brokers": ["Bolero", "Keytrade Bank", "Degiro Belgium"],
  "include_custody_fees": true
}
```

**Response**
```json
{
  "trade_amount": 5000,
  "instrument_type": "ETFs",
  "comparison": [
    {
      "broker": "Degiro Belgium",
      "transaction_cost": 1.00,
      "custody_fee_annual": 0.00,
      "total_cost": 1.00,
      "rank": 1
    },
    {
      "broker": "Keytrade Bank", 
      "transaction_cost": 9.50,
      "custody_fee_annual": 0.00,
      "total_cost": 9.50,
      "rank": 2
    },
    {
      "broker": "Bolero",
      "transaction_cost": 15.00,
      "custody_fee_annual": 12.00,
      "total_cost": 15.00,
      "rank": 3
    }
  ],
  "cheapest": {
    "broker": "Degiro Belgium",
    "savings_vs_most_expensive": 14.00
  }
}
```

### Find Cheapest Broker

Find the cheapest broker for a specific trade size and instrument type.

```http
GET /api/cheapest/{amount}
```

**Parameters**
- `amount` (path): Trade amount in EUR

**Query Parameters**
- `instrument_type` (required): `ETFs` or `Equities`
- `include_custody_fees` (optional): `true` or `false` (default: `false`)

**Response**
```json
{
  "trade_amount": 1000,
  "instrument_type": "ETFs",
  "cheapest_broker": {
    "name": "Degiro Belgium",
    "transaction_cost": 1.00,
    "fee_structure": "flat",
    "notes": "Includes €1 handling fee"
  },
  "all_costs": [
    {"broker": "Degiro Belgium", "cost": 1.00},
    {"broker": "Keytrade Bank", "cost": 1.90},
    {"broker": "Bolero", "cost": 15.00}
  ]
}
```

### Investment Scenario Analysis

Analyze total costs for different investment scenarios over time.

```http
POST /api/scenarios
```

**Request Body**
```json
{
  "scenarios": [
    {
      "name": "Monthly Investor",
      "lump_sum": 0,
      "monthly_investment": 169,
      "duration_years": 5,
      "instrument_types": ["ETFs", "Equities"]
    },
    {
      "name": "High Value Investor",
      "lump_sum": 10000,
      "monthly_investment": 500,
      "duration_years": 5,
      "instrument_types": ["ETFs"]
    }
  ],
  "brokers": ["all"]
}
```

**Response**
```json
{
  "scenarios": [
    {
      "name": "Monthly Investor",
      "results": {
        "ETFs": [
          {
            "broker": "Keytrade Bank",
            "total_transaction_cost": 19.20,
            "total_custody_cost": 0.00,
            "total_cost": 19.20,
            "rank": 1
          }
        ],
        "Equities": [
          {
            "broker": "Rebel",
            "total_transaction_cost": 180.00,
            "total_custody_cost": 0.00,
            "total_cost": 180.00,
            "rank": 1
          }
        ]
      }
    }
  ]
}
```

## News and Updates Endpoints

### Scrape Broker News

Automatically scrape news from broker websites, RSS feeds, and APIs.

```http
POST /api/news/scrape
```

**Query Parameters**
- `brokers_to_scrape` (optional): Array of specific broker names to scrape
- `force` (optional): `true` to bypass cache and perform fresh scrape (default: `false`)

**Response**
```json
{
  "status": "success",
  "message": "Successfully scraped 15 news items from 3 brokers",
  "news_by_broker": {
    "Bolero": 5,
    "Keytrade Bank": 7,
    "ING Self Invest": 3
  },
  "news_items": [
    {
      "broker": "Bolero",
      "title": "New ETF Trading Features",
      "summary": "Bolero announces enhanced ETF trading platform with reduced fees...",
      "url": "https://www.bolero.be/news/new-etf-features",
      "date": "2025-12-09",
      "source": "RSS Feed"
    }
  ],
  "total_scraped": 15,
  "brokers_with_news": 3,
  "brokers_processed": 5,
  "duration_seconds": 4.2,
  "from_cache": false
}
```

### Add News Flash

Manually add a news flash for a broker.

```http
POST /api/news
```

**Request Body**
```json
{
  "broker": "Bolero",
  "title": "Fee Structure Update",
  "summary": "Bolero has updated its fee structure for ETF trading, effective January 2026.",
  "url": "https://www.bolero.be/news/fee-update",
  "date": "2025-12-09",
  "source": "Official Website",
  "notes": "Affects all ETF transactions"
}
```

**Response**
```json
{
  "status": "success",
  "message": "News flash added for Bolero",
  "broker": "Bolero",
  "title": "Fee Structure Update"
}
```

### Get All News

Retrieve all news flashes, sorted by creation date (newest first).

```http
GET /api/news
```

**Response**
```json
[
  {
    "broker": "Bolero",
    "title": "Fee Structure Update",
    "summary": "Bolero has updated its fee structure for ETF trading...",
    "url": "https://www.bolero.be/news/fee-update",
    "date": "2025-12-09",
    "source": "Official Website",
    "notes": "Affects all ETF transactions",
    "created_at": "2025-12-09T10:30:00Z"
  }
]
```

### Get Broker-Specific News

Retrieve all news flashes for a specific broker.

```http
GET /api/news/broker/{broker_name}
```

**Parameters**
- `broker_name` (path): Name of the broker (e.g., "Bolero", "Keytrade Bank")

**Response**
```json
[
  {
    "broker": "Bolero",
    "title": "Fee Structure Update", 
    "summary": "Bolero has updated its fee structure...",
    "url": "https://www.bolero.be/news/fee-update",
    "date": "2025-12-09",
    "source": "Official Website",
    "notes": "Affects all ETF transactions",
    "created_at": "2025-12-09T10:30:00Z"
  }
]
```

### Get Recent News

Get the most recent news flashes across all brokers.

```http
GET /api/news/recent
```

**Query Parameters**
- `limit` (optional): Maximum number of news items to return (default: 10)

**Response**
```json
[
  {
    "broker": "Keytrade Bank",
    "title": "Platform Maintenance",
    "summary": "Scheduled maintenance on December 15th...",
    "url": "https://www.keytradebank.be/maintenance",
    "date": "2025-12-08",
    "source": "RSS Feed",
    "notes": null,
    "created_at": "2025-12-08T14:20:00Z"
  }
]
```

### Get News Statistics

Get statistics about the news data.

```http
GET /api/news/statistics
```

**Response**
```json
{
  "total_news": 45,
  "brokers_with_news": 4,
  "news_by_broker": {
    "Bolero": 12,
    "Keytrade Bank": 18,
    "ING Self Invest": 8,
    "Rebel": 7
  },
  "latest_news_date": "2025-12-09T10:30:00Z",
  "oldest_news_date": "2025-11-01T09:15:00Z"
}
```

### Delete News Flash

Delete a specific news flash by broker and title.

```http
DELETE /api/news
```

**Request Body**
```json
{
  "broker": "Bolero",
  "title": "Fee Structure Update"
}
```

**Response**
```json
{
  "status": "success", 
  "message": "News flash deleted for Bolero: Fee Structure Update"
}
```

## Data Management Endpoints

### Trigger LLM Extraction

Manually trigger LLM extraction for specific brokers (requires API keys).

```http
POST /api/extract
```

**Request Body**
```json
{
  "brokers": ["Bolero", "Keytrade Bank"],
  "model": "gpt-4o",
  "force_refresh": false
}
```

**Response**
```json
{
  "extraction_id": "ext_123456",
  "status": "processing",
  "brokers_queued": ["Bolero", "Keytrade Bank"],
  "estimated_completion": "2025-12-09T18:05:00Z"
}
```

### Get Extraction Status

Check the status of an LLM extraction job.

```http
GET /api/extract/{extraction_id}
```

**Response**
```json
{
  "extraction_id": "ext_123456",
  "status": "completed",
  "results": {
    "Bolero": {
      "status": "success",
      "records_extracted": 4,
      "validation_issues": 0
    },
    "Keytrade Bank": {
      "status": "success", 
      "records_extracted": 6,
      "validation_issues": 1
    }
  },
  "completed_at": "2025-12-09T18:04:32Z"
}
```

### Validate Data Quality

Run data quality validation checks against expected values.

```http
POST /api/validate
```

**Request Body**
```json
{
  "brokers": ["all"],
  "validation_type": "comprehensive",
  "include_llm_extraction": true
}
```

**Response**
```json
{
  "validation_id": "val_789012",
  "summary": {
    "brokers_tested": 5,
    "total_issues": 3,
    "critical_issues": 1,
    "warnings": 2
  },
  "issues": [
    {
      "broker": "Degiro Belgium",
      "severity": "critical",
      "issue": "Missing €1 handling fee for ETF transactions",
      "expected": 1.00,
      "actual": 0.00
    }
  ]
}
```

## Report Generation Endpoints

### Generate Analysis Report

Create comprehensive broker fee analysis reports.

```http
POST /api/reports/generate
```

**Request Body**
```json
{
  "report_type": "comprehensive",
  "output_format": ["json", "csv", "markdown"],
  "include_charts": true,
  "brokers": ["all"],
  "trade_sizes": [250, 500, 1000, 5000]
}
```

**Response**
```json
{
  "report_id": "rpt_345678",
  "status": "generating",
  "download_urls": {
    "json": "/api/reports/rpt_345678/download?format=json",
    "csv": "/api/reports/rpt_345678/download?format=csv",
    "markdown": "/api/reports/rpt_345678/download?format=markdown"
  },
  "estimated_completion": "2025-12-09T18:10:00Z"
}
```

### Download Report

Download a generated report in the specified format.

```http
GET /api/reports/{report_id}/download
```

**Query Parameters**
- `format` (required): `json`, `csv`, `markdown`, or `pdf`

**Response**
- Content-Type varies by format
- File download or JSON response

## WebSocket Endpoints

### Real-time Updates

Subscribe to real-time updates for extraction and analysis jobs.

```javascript
const ws = new WebSocket('wss://your-domain.vercel.app/api/ws');

// Subscribe to specific updates
ws.send(JSON.stringify({
  type: 'subscribe',
  topics: ['extractions', 'validations', 'analysis']
}));

// Receive updates
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Update:', update);
};
```

**Update Message Format**
```json
{
  "type": "extraction_completed",
  "extraction_id": "ext_123456",
  "broker": "Bolero",
  "status": "success",
  "records_extracted": 4,
  "timestamp": "2025-12-09T18:04:32Z"
}
```

## Error Handling

### Error Response Format

All API errors follow a consistent format:

```json
{
  "error": {
    "code": "BROKER_NOT_FOUND",
    "message": "The specified broker 'Unknown Bank' was not found",
    "details": {
      "available_brokers": ["Bolero", "Keytrade Bank", "Degiro Belgium"],
      "suggestion": "Check broker name spelling and capitalization"
    },
    "timestamp": "2025-12-09T18:00:00Z",
    "request_id": "req_abc123"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `BROKER_NOT_FOUND` | 404 | Requested broker not supported |
| `INVALID_TRADE_AMOUNT` | 400 | Trade amount must be positive |
| `MISSING_API_KEY` | 401 | LLM API key not configured |
| `EXTRACTION_FAILED` | 500 | LLM extraction service error |
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `SERVICE_UNAVAILABLE` | 503 | External service temporarily unavailable |

## Rate Limiting

- **Standard endpoints**: 100 requests per minute per IP
- **LLM extraction endpoints**: 10 requests per minute per IP
- **WebSocket connections**: 5 concurrent connections per IP

Rate limit headers are included in all responses:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1673024400
```

## Pagination

For endpoints returning large datasets:

```http
GET /api/brokers?page=1&limit=10
```

**Response**
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total_pages": 3,
    "total_count": 25,
    "has_next": true,
    "has_prev": false
  }
}
```

## Caching

- **Broker data**: Cached for 1 hour
- **Analysis results**: Cached for 30 minutes
- **LLM extractions**: Cached for 24 hours

Cache headers indicate freshness:
```http
Cache-Control: public, max-age=3600
ETag: "abc123def456"
Last-Modified: Mon, 09 Dec 2025 17:00:00 GMT
```

## SDK Examples

### Python SDK Usage

```python
import requests

# Initialize client
base_url = "https://your-domain.vercel.app"
headers = {"Content-Type": "application/json"}

# Get broker fees
response = requests.get(f"{base_url}/api/brokers/Bolero/fees", headers=headers)
fees = response.json()

# Compare brokers
comparison_data = {
    "trade_amount": 1000,
    "instrument_type": "ETFs",
    "brokers": ["Bolero", "Keytrade Bank"]
}
response = requests.post(f"{base_url}/api/compare", json=comparison_data, headers=headers)
comparison = response.json()
```

### JavaScript SDK Usage

```javascript
const apiClient = {
  baseUrl: 'https://your-domain.vercel.app',
  
  async getBrokerFees(brokerName) {
    const response = await fetch(`${this.baseUrl}/api/brokers/${brokerName}/fees`);
    return response.json();
  },
  
  async compareBrokers(tradeAmount, instrumentType, brokers) {
    const response = await fetch(`${this.baseUrl}/api/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trade_amount: tradeAmount,
        instrument_type: instrumentType,
        brokers: brokers
      })
    });
    return response.json();
  },

  // News endpoints
  async scrapeNews(brokers = [], force = false) {
    const params = new URLSearchParams();
    if (brokers.length > 0) {
      brokers.forEach(broker => params.append('brokers_to_scrape', broker));
    }
    if (force) params.append('force', 'true');
    
    const response = await fetch(`${this.baseUrl}/api/news/scrape?${params}`, {
      method: 'POST'
    });
    return response.json();
  },

  async getAllNews() {
    const response = await fetch(`${this.baseUrl}/api/news`);
    return response.json();
  },

  async getBrokerNews(brokerName) {
    const response = await fetch(`${this.baseUrl}/api/news/broker/${brokerName}`);
    return response.json();
  },

  async getRecentNews(limit = 10) {
    const response = await fetch(`${this.baseUrl}/api/news/recent?limit=${limit}`);
    return response.json();
  },

  async addNewsFlash(newsData) {
    const response = await fetch(`${this.baseUrl}/api/news`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newsData)
    });
    return response.json();
  }

};

// Usage
const fees = await apiClient.getBrokerFees('Bolero');
const comparison = await apiClient.compareBrokers(1000, 'ETFs', ['Bolero', 'Keytrade Bank']);
```

## Testing

Use the interactive API documentation at `/docs` when running the server locally, or test endpoints with curl:

```bash
# Health check
curl https://your-domain.vercel.app/api/health

# Get broker fees
curl https://your-domain.vercel.app/api/brokers/Bolero/fees

# Compare brokers
curl -X POST https://your-domain.vercel.app/api/compare \
  -H "Content-Type: application/json" \
  -d '{
    "trade_amount": 1000,
    "instrument_type": "ETFs", 
    "brokers": ["Bolero", "Keytrade Bank"]
  }'
```
