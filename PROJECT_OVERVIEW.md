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
│   ├── pipeline.py             ← Fee record processing
│   └── sources/
│       ├── manual.py           ← Manual CSV data
│       ├── llm_extract.py      ← LLM-powered extraction
│       └── scrape.py           ← Web scraping
│
├── scripts/
│   ├── run_api.py              ← Start REST API
│   ├── generate_exhaustive_summary.py  ← Generate summaries
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
    ├── API_INTEGRATION.md      ← How to use
    ├── BROKER_ANALYSIS.md      ← Broker data
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
│  ├─ Manual CSV (data/fees/manual_fees.csv)                 │
│  └─ Broker Config (data/brokers.yaml)                      │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  PROCESSING LAYER                                           │
│  ├─ PDF Extraction (PyMuPDF, pdfminer)                     │
│  ├─ Text Normalization                                     │
│  ├─ LLM Analysis (GPT-4o)                                  │
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
- `POST /refresh-pdfs` - Download & extract (10-30s)
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
Download PDFs from URLs
    ↓
Extract text using PyMuPDF/pdfminer
    ↓
Save to pdf_text/
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
Send to GPT-4o for analysis (step 3)
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
- **LLM**: OpenAI GPT-4o
- **Data**: JSON, YAML, CSV

### Data Models
- **Broker**: Name, website, instruments, data_sources
- **FeeRecord**: broker, instrument_type, order_channel, fees, notes
- **DataSource**: type, url, allowed_to_scrape, description

### Config Files
- **brokers.yaml** - Broker metadata and PDF URLs
- **manual_fees.csv** - Manual fee entries
- **.env** - Environment variables (OPENAI_API_KEY)

---

## Key Features

✅ **Real-Time Data Access** - Sub-100ms queries via caching
✅ **PDF Refresh** - Download latest tariff documents on demand
✅ **LLM Analysis** - GPT-4o powered fee structure extraction
✅ **Multiple Formats** - JSON for APIs, Markdown for reports
✅ **Error Handling** - Proper HTTP codes and error messages
✅ **Security** - Respects scraping permissions
✅ **Performance** - Optimized for speed

---

## Security & Compliance

### Scraping Permissions
- Each broker has `allowed_to_scrape` flag in YAML
- API respects this flag by default
- Can override with `?force=true` if authorized

### API Key Management
- OPENAI_API_KEY via environment variables only
- Never hardcoded
- Required for LLM analysis endpoints

### Data Privacy
- PDFs cached locally only
- No external storage
- Safe error messages

---

## Performance Metrics

| Operation | Time | Notes |
|-----------|------|-------|
| GET /cost-analysis | <100ms | Cached JSON |
| GET /summary | <100ms | Cached markdown |
| POST /refresh-pdfs | 10-30s | Network + extraction |
| POST /refresh-and-analyze | 1-3 min | Includes LLM calls |

---

## Configuration

### Environment Variables
```bash
OPENAI_API_KEY="sk-..."       # Required for LLM
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
2. Set `allowed_to_scrape` appropriately
3. Add PDF URL to `data_sources`
4. Run: `python scripts/generate_exhaustive_summary.py`

### Add Manual Fees
1. Edit `data/fees/manual_fees.csv`
2. Use required columns: broker, instrument_type, order_channel, base_fee, variable_fee, currency, source, notes
3. Run pipeline to regenerate analysis

### Customize API
1. Modify `src/be_invest/api/server.py`
2. Add authentication, caching, or other features
3. Restart API server

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| API won't start | Check Python 3.8+ and dependencies |
| 404 Cost analysis | Run `generate_exhaustive_summary.py` |
| LLM fails | Set `OPENAIN_API_KEY` |
| Slow refresh | Normal - LLM calls take time |
| CORS issues | Use proxy or enable in production |

---

## Dependencies

### Core
```
fastapi        - Web framework
uvicorn        - Server
pydantic       - Data validation
pyyaml         - YAML parsing
```

### PDF Processing
```
pymupdf        - PDF text extraction (preferred)
pdfminer.six   - PDF extraction (fallback)
```

### LLM
```
openai         - GPT-4o integration
```

### Optional
```
requests       - HTTP client
schedule       - Job scheduling
gunicorn       - Production server
```

---

## File Sizes & Data

**Broker Data**
- 3 brokers analyzed
- 4 languages supported
- 41,000+ chars of PDF text extracted

**Documentation**
- 5 main guides
- 3500+ lines total
- Examples in 4 languages

**Code**
- 740+ lines of API code
- 350+ lines of examples
- Syntax validated

---

## Deployment Options

### Development
```bash
python scripts/run_api.py
```

### Production (Gunicorn)
```bash
gunicorn -w 4 -b 0.0.0.0:8000 be_invest.api.server:app
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["python", "scripts/run_api.py"]
```

### Cloud Platforms
- AWS Lambda
- Google Cloud Run
- Azure App Service
- Heroku

---

## Support & Documentation

| Need | Resource |
|------|----------|
| Quick start | `API_QUICK_START.md` |
| API details | `API_REFERENCE.md` |
| Integration | `API_INTEGRATION.md` |
| Broker data | `BROKER_ANALYSIS.md` |
| This file | `PROJECT_OVERVIEW.md` |

---

**Status**: ✅ Production Ready

**Last Updated**: November 20, 2025

