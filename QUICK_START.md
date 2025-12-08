# be-invest - Quick Reference

## 📁 Directory Structure

```
be-invest/
├── README.md                  ← START HERE (all documentation)
├── src/be_invest/
│   ├── utils/cache.py        ← Cache implementation
│   ├── api/server.py         ← FastAPI + caching
│   └── ... (core modules)
├── scripts/
│   ├── run_api.py            ← START API HERE
│   ├── debug/                ← Debug scripts
│   ├── generate/             ← Report generation
│   ├── test/                 ← API tests
│   ├── scrape/               ← Web scraping
│   ├── demos/                ← Demo apps
│   └── utils/                ← Utilities
├── tests/                    ← Test files
└── data/                     ← Configs & data
```

## 🚀 Quick Commands

### Start API
```bash
python scripts/run_api.py
# Visit: http://localhost:8000/docs
```

### Run Tests
```bash
# Cache tests
python tests/test_cache.py

# All tests in tests/ folder
python -m pytest tests/
```

### Generate Reports
```bash
python scripts/generate/generate_report.py
python scripts/generate/generate_exhaustive_summary.py
```

### Debug Issues
```bash
python scripts/debug/debug_belfius_fetch.py
python scripts/debug/validate_playwright.py
```

### Scrape Brokers
```bash
python scripts/scrape/download_broker_pdfs.py
```

### Run Demos
```bash
python scripts/demos/broker_summary_demo.py
python scripts/demos/news_dashboard_demo.py
```

## 📚 Documentation

**README.md** contains:
- API endpoints reference
- Caching system details (TTL, configuration)
- Client integration examples (Python, JS, Bash)
- AI model support (OpenAI, Anthropic)
- Configuration guide
- Troubleshooting

## 💾 Cache System

- **LLM Cache:** 7-day TTL, 80% cost reduction
- **News Cache:** 24-hour TTL
- Use `?force=true` parameter to refresh

Example:
```bash
# Use cache (default)
curl http://localhost:8000/cost-comparison-tables

# Force refresh
curl "http://localhost:8000/cost-comparison-tables?force=true"
```

## 🔧 Configuration

Edit `data/brokers.yaml` for broker configs
Edit `src/be_invest/api/server.py` for cache TTL

## 📖 Read More

See `README.md` for complete documentation
See `ORGANIZATION_COMPLETE.md` for structure details

