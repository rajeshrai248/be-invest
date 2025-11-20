# 🔗 API Integration Guide

How to integrate the REST API into your application.

## Quick Setup

### 1. Python Integration

```python
import requests

# Initialize
API_URL = "http://localhost:8000"

# Get all costs
response = requests.get(f"{API_URL}/cost-analysis")
all_costs = response.json()

# Get specific broker
response = requests.get(f"{API_URL}/cost-analysis/Bolero")
bolero = response.json()

# Refresh data
response = requests.post(f"{API_URL}/refresh-pdfs")
status = response.json()
```

### 2. JavaScript Integration

```javascript
const API_URL = "http://localhost:8000";

// Get costs
const costs = await fetch(`${API_URL}/cost-analysis`)
  .then(r => r.json());

// Get broker
const broker = await fetch(`${API_URL}/cost-analysis/Bolero`)
  .then(r => r.json());

// Refresh
await fetch(`${API_URL}/refresh-pdfs`, { method: 'POST' });
```

### 3. Bash/Shell Integration

```bash
API_URL="http://localhost:8000"

# Get costs
curl $API_URL/cost-analysis > costs.json

# Get summary
curl $API_URL/summary > report.md

# Refresh
curl -X POST $API_URL/refresh-pdfs
```

---

## Frontend Integration (React/Vue)

### React Example

```jsx
import { useState, useEffect } from 'react';

function BrokerCosts() {
  const [costs, setCosts] = useState(null);
  
  useEffect(() => {
    fetch('http://localhost:8000/cost-analysis')
      .then(r => r.json())
      .then(data => setCosts(data));
  }, []);
  
  if (!costs) return <div>Loading...</div>;
  
  return (
    <div>
      {Object.entries(costs).map(([broker, data]) => (
        <div key={broker}>
          <h2>{broker}</h2>
          <p>{data.summary}</p>
        </div>
      ))}
    </div>
  );
}
```

### Vue Example

```vue
<template>
  <div>
    <div v-for="(data, broker) in costs" :key="broker">
      <h2>{{ broker }}</h2>
      <p>{{ data.summary }}</p>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return { costs: {} };
  },
  mounted() {
    fetch('http://localhost:8000/cost-analysis')
      .then(r => r.json())
      .then(data => this.costs = data);
  }
}
</script>
```

---

## Backend Integration

### Flask/Python

```python
from flask import Flask, jsonify
import requests

app = Flask(__name__)
API_URL = "http://localhost:8000"

@app.route('/api/brokers')
def get_brokers():
    response = requests.get(f"{API_URL}/cost-analysis")
    return jsonify(response.json())

@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    response = requests.post(f"{API_URL}/refresh-pdfs")
    return jsonify(response.json())
```

### Node.js/Express

```javascript
const express = require('express');
const fetch = require('node-fetch');
const app = express();

const API_URL = 'http://localhost:8000';

app.get('/api/brokers', async (req, res) => {
  const response = await fetch(`${API_URL}/cost-analysis`);
  const data = await response.json();
  res.json(data);
});

app.post('/api/refresh', async (req, res) => {
  const response = await fetch(`${API_URL}/refresh-pdfs`, { 
    method: 'POST' 
  });
  const data = await response.json();
  res.json(data);
});
```

---

## Scheduled Refresh

### Linux/Mac Cron Job

```bash
# Refresh PDFs daily at midnight
0 0 * * * curl -X POST http://localhost:8000/refresh-pdfs

# Refresh and analyze daily at 2 AM (requires OPENAI_API_KEY)
0 2 * * * OPENAI_API_KEY=sk-... curl -X POST http://localhost:8000/refresh-and-analyze
```

### Python Scheduler

```python
import schedule
import requests
import time

def refresh_pdfs():
    requests.post('http://localhost:8000/refresh-pdfs')
    print("PDFs refreshed")

def analyze():
    requests.post('http://localhost:8000/refresh-and-analyze')
    print("Analysis complete")

# Schedule tasks
schedule.every().day.at("00:00").do(refresh_pdfs)
schedule.every().day.at("02:00").do(analyze)

# Run scheduler
while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## Error Handling

### Python

```python
import requests

try:
    response = requests.get('http://localhost:8000/cost-analysis/Bolero')
    response.raise_for_status()
    data = response.json()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 404:
        print("Broker not found")
    else:
        print(f"Error: {e}")
except requests.exceptions.ConnectionError:
    print("Cannot connect to API")
```

### JavaScript

```javascript
try {
  const response = await fetch('http://localhost:8000/cost-analysis/Bolero');
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  const data = await response.json();
} catch (error) {
  console.error('Error:', error);
}
```

---

## Configuration

### Environment Variables

```bash
# Required for refresh-and-analyze endpoint
export OPENAI_API_KEY="sk-your-key"

# Optional: Custom API URL
export API_URL="http://localhost:8000"
```

### Docker Integration

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

ENV OPENAI_API_KEY=""
ENV API_URL="http://api:8000"

CMD ["python", "app.py"]
```

---

## Performance Tips

1. **Cache responses** - Cost analysis doesn't change often
2. **Use background jobs** - For refresh operations
3. **Limit refresh frequency** - Don't refresh more than hourly
4. **Handle timeouts** - Set reasonable timeouts for POST requests
5. **Batch requests** - Combine multiple queries if possible

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 404 Not Found | Check broker name spelling |
| Connection refused | Start API: `python scripts/run_api.py` |
| LLM fails | Set `OPENAI_API_KEY` environment variable |
| Slow refresh | Normal - LLM calls take time (1-3 min) |
| CORS issues | Use proxy or enable CORS in production |

---

## Production Deployment

### Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 be_invest.api.server:app
```

### Using Docker

```bash
docker build -t be-invest-api .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... be-invest-api
```

### Using Systemd

```ini
[Unit]
Description=be-invest API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/be-invest
Environment="OPENAI_API_KEY=sk-..."
ExecStart=/usr/bin/python3 scripts/run_api.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---

**For API details, see:** `API_REFERENCE.md`

**For quick start, see:** `API_QUICK_START.md`

