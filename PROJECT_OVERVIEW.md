# 🏗️ Project Overview & Architecture

Technical documentation for the be-invest system.

## Project Structure

```
be-invest/
├── src/be_invest/
│   ├── api/
│   │   └── server.py           ← REST API (7 endpoints)
│   ├── models.py               ← Data models
│   ├── config_loader.py        ← Broker config
│   └── sources/
│       ├── llm_extract.py      ← LLM-powered extraction
│       └── scrape.py           ← PDF scraping
│
├── scripts/
│   ├── run_api.py              ← Start REST API
│   ├── generate_summary_demo.py  ← Generate summaries
│   └── test_api_examples.py    ← API examples
│
├── data/
│   ├── brokers.yaml            ← Broker configuration
│   └── output/
│       ├── broker_cost_analyses.json        ← API serves this
│       ├── exhaustive_cost_charges_summary.md
│       └── pdf_text/           ← Extracted PDFs
│
└── docs/                        ← Consolidated documentation
    ├── README.md               ← Start here
    ├── API_QUICK_START.md      ← 5 min setup
    ├── API_REFERENCE.md        ← All endpoints
    └── PROJECT_OVERVIEW.md     ← This file
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  be-invest System                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  USER INTERFACES                                            │
│  ├─ REST API (7 endpoints)          ← http://localhost:8000
│  ├─ Interactive Docs                ← http://localhost:8000/docs
│  └─ Command Line                    ← CLI scripts
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  DATA SOURCES                                               │
│  ├─ Broker PDFs (tariff documents)                         │
│  └─ Broker Config (data/brokers.yaml)                      │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  PROCESSING LAYER                                           │
│  ├─ PDF Extraction (PyMuPDF, pdfminer)                     │
│  ├─ Text Normalization                                     │
│  ├─ LLM Analysis (GPT-4o, Claude 3)                        │
│  └─ Fee Record Pipeline                                    │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  DATA STORAGE                                               │
│  ├─ JSON Analysis (broker_cost_analyses.json)              │
│  ├─ Markdown Reports (exhaustive_summary.md)               │
│  └─ PDF Texts (pdf_text/*.txt)                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## REST API Endpoints

### 7 Total Endpoints

**Query (Fast - Cached):**
- `GET /health` - Server status (<1ms)
- `GET /brokers` - Broker list (<10ms)
- `GET /cost-analysis` - All costs (<100ms)
- `GET /cost-analysis/{broker}` - Single broker (<100ms)
- `GET /summary` - Markdown report (<100ms)

**Actions (Background):**
- `POST /refresh-pdfs` - Download & extract PDFs (10-30s)
- `POST /refresh-and-analyze` - Full pipeline (1-3 min)

---

## Data Flow

### Query Flow (Real-Time)
```
Client Request (GET /cost-analysis)
    ↓
Load JSON from cache
    ↓
Return instantly (<100ms)
```

### Refresh Flow (Background)
```
Client Request (POST /refresh-pdfs)
    ↓
Download PDFs from URLs in brokers.yaml
    ↓
Extract text using PyMuPDF/pdfminer
    ↓
Save to data/output/pdf_text/
    ↓
Return status
```

### Analysis Flow (Full Pipeline)
```
Client Request (POST /refresh-and-analyze)
    ↓
Refresh PDFs (step 1)
    ↓
Extract text (step 2)
    ↓
Send to specified LLM for analysis (step 3)
    ↓
Save broker_cost_analyses.json (step 4)
    ↓
Return results
```

---

## Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **Server**: Uvicorn
- **PDF Processing**: PyMuPDF, pdfminer.six
- **LLM**: OpenAI (e.g., GPT-4o), Anthropic (e.g., Claude 3 Opus)
- **Data**: JSON, YAML, CSV

### Data Models
- **Broker**: Name, website, instruments, data_sources
- **FeeRecord**: broker, instrument_type, order_channel, fees, notes
- **DataSource**: type, url, allowed_to_scrape, description

### Config Files
- **brokers.yaml** - Broker metadata and PDF URLs. Non-PDF sources are ignored by the automated process.
- **.env** - Environment variables (OPENAI_API_KEY, ANTHROPIC_API_KEY)

---

## Key Features

✅ **Real-Time Data Access** - Sub-100ms queries via caching
✅ **PDF Refresh** - Download latest tariff documents on demand
✅ **Multi-LLM Analysis** - Supports GPT-4o and Claude 3 models for fee structure extraction
✅ **Multiple Formats** - JSON for APIs, Markdown for reports
✅ **Error Handling** - Proper HTTP codes and error messages
✅ **Security** - Respects scraping permissions in `brokers.yaml`

---

## Configuration

### Environment Variables
```bash
OPENAI_API_KEY="sk-..."       # Required for OpenAI models
ANTHROPIC_API_KEY="sk-..."    # Required for Anthropic models
LOG_LEVEL="INFO"              # Optional logging level
```

### Broker Configuration (brokers.yaml)
```yaml
brokers:
  - name: Bolero
    website: https://www.bolero.be/
    instruments: [Equities, ETFs, Bonds, Funds]
    data_sources:
      - type: webpage
        url: https://...pdf
        allowed_to_scrape: false
```

---

## Extending the System

### Add New Broker
1. Add entry to `data/brokers.yaml`
2. Provide a direct URL to a PDF fee document.
3. Set `allowed_to_scrape` appropriately.
4. Run: `python scripts/generate_summary_demo.py`

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| API won't start | Check Python 3.8+ and dependencies |
| 404 Cost analysis | Run `generate_summary_demo.py` |
| LLM fails | Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` |
| Broker missing from summary | Ensure the URL in `brokers.yaml` points directly to a PDF. |

---

**Status**: ✅ Production Ready

**Last Updated**: December 5, 2025
