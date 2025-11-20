# 🚀 API Quick Start (5 minutes)

Get the REST API running in 5 minutes.

## 1️⃣ Start the Server

```bash
python scripts/run_api.py
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

## 2️⃣ Test It

```bash
# Health check
curl http://localhost:8000/health
# → {"status": "ok"}

# Get all broker costs
curl http://localhost:8000/cost-analysis
# → {JSON with all broker data}
```

## 3️⃣ View Interactive Docs

```
http://localhost:8000/docs
```

Click "Try it out" on any endpoint to test it live.

## 4️⃣ Try in Python

```python
import requests

# Get costs
response = requests.get('http://localhost:8000/cost-analysis')
costs = response.json()

# Get specific broker
response = requests.get('http://localhost:8000/cost-analysis/Bolero')
bolero = response.json()

# Refresh PDFs
response = requests.post('http://localhost:8000/refresh-pdfs')
status = response.json()
```

## 5️⃣ Common Commands

```bash
# Get all brokers
curl http://localhost:8000/brokers

# Get Bolero costs
curl http://localhost:8000/cost-analysis/Bolero

# Get summary
curl http://localhost:8000/summary > report.md

# Refresh data
curl -X POST http://localhost:8000/refresh-pdfs
```

---

## 📍 Endpoints Quick Reference

| Method | Endpoint | Purpose | Model |
|--------|----------|---------|-------|
| GET | /health | Server status | N/A |
| GET | /brokers | List all brokers | N/A |
| GET | /cost-analysis | All costs | N/A |
| GET | /cost-analysis/{broker} | Broker costs | N/A |
| GET | /summary | Markdown report | N/A |
| POST | /refresh-pdfs | Refresh data | N/A |
| POST | /refresh-and-analyze | Full analysis | gpt-5 (latest) |

---

## 🎓 Next Steps

1. **Read API Reference** → See all endpoint details
2. **Read Integration Guide** → How to use in your app
3. **Run Examples** → `python scripts/test_api_examples.py --interactive`

---

**Ready to use!** For more details, see `API_REFERENCE.md`

