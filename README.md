# BE-Invest: Belgian Broker Fee Analysis Toolkit

> 🇧🇪 Comprehensive toolkit for aggregating, analyzing, and comparing Belgian investment broker fees using advanced LLM-powered data extraction.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](#license)

## 🎯 Overview

BE-Invest is an automated system that extracts, validates, and analyzes broker fee structures from Belgian investment platforms. It uses Large Language Models (LLMs) for intelligent data extraction from PDFs and web content, providing accurate cost comparisons and investment scenario analysis.

### Key Features

- **🤖 AI-Powered Extraction**: Uses OpenAI GPT-4 or Anthropic Claude for intelligent fee extraction from broker documents
- **🔍 Data Quality Validation**: Automated validation against known fee structures with comprehensive error detection
- **📊 Investment Analysis**: Cost analysis for different investor profiles and transaction sizes
- **🌐 REST API**: FastAPI-based web service for programmatic access
- **📈 Comprehensive Reporting**: Multiple output formats (JSON, CSV, Markdown) for different use cases
- **⚡ Caching System**: Intelligent caching to minimize API costs and improve performance
- **🐳 Docker Ready**: Complete Docker setup with Langfuse for production deployment
- **🔍 LLM Observability**: Integrated Langfuse tracing for monitoring and evaluation

## ⚡ One-Command Quick Start

```bash
# Clone and setup (includes Docker + Langfuse)
git clone https://github.com/your-username/be-invest.git
cd be-invest
cp .env.example .env          # Copy environment template
# Edit .env with your API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)

# Start all services (API + Langfuse + Database)
docker-compose up -d

# Done! Access:
# API:     http://localhost:8000/docs
# Langfuse: http://localhost:3000
```

For alternative setup options and detailed instructions, see [Quick Start](#-quick-start) below.

## 🚀 Quick Start

### Prerequisites

#### Option 1: Docker (Recommended)
- **Docker** 20.10+ - [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Docker Compose** 1.29+ - Usually included with Docker Desktop
- **API Keys** - OpenAI or Anthropic (for LLM services)

#### Option 2: Local Development
- **Python 3.9+** - [Download Python](https://python.org/downloads/)
- **Git** - [Download Git](https://git-scm.com/downloads) 
- **API Key** - Get one from [OpenAI](https://platform.openai.com/api-keys) or [Anthropic](https://console.anthropic.com/)

### Installation & Setup

#### Docker Setup (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/your-username/be-invest.git
cd be-invest

# 2. Create .env file with your API keys
cp .env.example .env
# Edit .env with your OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.

# 3. Run setup (choose one):
# Linux/Mac:
bash docker-deploy.sh setup

# Windows:
docker-deploy.bat setup

# Or use docker-compose directly:
docker-compose up -d
```

This starts:
- **be-invest** API on http://localhost:8000
- **Langfuse** on http://localhost:3000 (for LLM tracing)
- **PostgreSQL** database (persistence)

#### Local Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-username/be-invest.git
cd be-invest

# 2. Install dependencies
pip install -e .

# 3. Configure API key (choose one)
export OPENAI_API_KEY="your-openai-key-here"
# OR
export ANTHROPIC_API_KEY="your-anthropic-key-here"
```

**Windows users:**
```cmd
set OPENAI_API_KEY=your-openai-key-here
```

### Run Your First Analysis

#### With Docker (Recommended)

```bash
# API is already running at http://localhost:8000/docs

# Generate cost analysis
curl http://localhost:8000/cost-analysis

# Generate cost comparison tables
curl "http://localhost:8000/cost-comparison-tables?lang=en"

# View Langfuse tracing at http://localhost:3000
```

#### Local Development

```bash
# Generate a complete broker fee analysis
python scripts/analyze_broker_fees.py
```

You should see output like:
```
Analysis completed!
- 5 brokers analyzed
- 2 data quality issues found
- Reports saved to: data/output/analysis
```

### Start the Web API

#### Docker (Recommended)
```bash
# Already running! Just verify:
docker-compose ps

# Open http://localhost:8000/docs for interactive API documentation
# Open http://localhost:3000 for Langfuse observability dashboard
```

#### Local Development
```bash
# Start the API server
uvicorn be_invest.api.server:app --reload

# Open http://localhost:8000/docs for interactive API documentation
```

### Example API Usage

```bash
# Check API health
curl http://localhost:8000/health

# List all brokers
curl http://localhost:8000/brokers

# Get cost analysis
curl http://localhost:8000/cost-analysis

# Generate comparison tables
curl "http://localhost:8000/cost-comparison-tables?lang=en&model=claude-sonnet-4-20250514"

# Chat about brokers (natural language)
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which broker is cheapest for ETF trading?",
    "model": "groq/llama-3.3-70b-versatile",
    "lang": "en"
  }'

# Scrape and analyze broker fees
curl -X POST "http://localhost:8000/refresh-and-analyze" \
  -H "Content-Type: application/json"

# Get latest broker news
curl http://localhost:8000/news/recent?limit=10
```

### What You Get

#### Docker Output
- **API Documentation**: http://localhost:8000/docs (interactive)
- **Langfuse Dashboard**: http://localhost:3000 (LLM tracing & observability)
- **Data Persistence**: `data/output/` (JSON analysis files)

#### Analysis Reports
After running analysis, find reports in `data/output/`:

- **`broker_cost_analyses.json`** - Complete broker fee structures
- **`cost_comparison_tables.json`** - Side-by-side fee comparison
- **`financial_analysis_*.json`** - Detailed investment scenarios

**Available Data:**
- €250-€50,000 transaction fee estimates
- ETF, Stock, and Bond pricing
- Custody and hidden cost analysis
- Investor persona cost rankings
- Multi-language support (English, French, Dutch)

## 📋 Supported Brokers

| Broker | ETFs | Stocks | Bonds | Options | LLM Extraction | Status |
|--------|------|--------|-------|---------|----------------|--------|
| **Bolero** | ✅ | ✅ | ✅ | ❌ | ✅ | Active |
| **Keytrade Bank** | ✅ | ✅ | ❌ | ✅ | ✅ | Active |
| **Degiro Belgium** | ✅ | ✅ | ❌ | ✅ | ✅ | Active |
| **ING Self Invest** | ✅ | ✅ | ✅ | ❌ | ✅ | Active |
| **Rebel** (formerly Belfius) | ✅ | ✅ | ✅ | ❌ | ✅ | Active |
| **Revolut** | ✅ | ✅ | ❌ | ❌ | ⚠️ | Limited |
| **Trade Republic** | ✅ | ✅ | ✅ | ❌ | ✅ | Active |

## 🔧 Architecture

The platform is organised in layers: a FastAPI service exposes the endpoints,
deterministic Python computes every number, LLMs are used only for narrative /
extraction, and Langfuse traces and auto-evaluates each call. See
[docs/hld_current_architecture.drawio](docs/hld_current_architecture.drawio)
for the current-state diagram and
[docs/hld_future_architecture.drawio](docs/hld_future_architecture.drawio)
for the planned human-feedback / continuous-improvement direction.

```
be-invest/
├── src/be_invest/
│   ├── api/
│   │   └── server.py            # FastAPI app — all endpoints, Langfuse tracing
│   ├── models.py                # Data models (Broker, FeeRecord, ...)
│   ├── config_loader.py         # YAML config loading (brokers.yaml)
│   ├── pipeline.py              # Broker fee data pipeline orchestration
│   ├── fetchers.py             # Source fetchers (Playwright + filesystem cache)
│   ├── cache.py                # Filesystem cache for fetched resources
│   ├── news.py                 # News-flash storage & retrieval
│   ├── email_sender.py         # Weekly broker-fee report email builder/sender
│   ├── sources/                # Data acquisition
│   │   ├── scrape.py           # Web/PDF scraping scaffolding
│   │   ├── llm_extract.py      # LLM PDF → raw FeeRecord extraction
│   │   ├── news_scrape.py      # Broker news scraping
│   │   └── manual.py           # Manual data import
│   ├── validation/             # Deterministic computation & validation
│   │   ├── fee_calculator.py   # Exact per-trade fee computation (FEE_RULES)
│   │   ├── persona_calculator.py # Per-persona total-cost-of-ownership
│   │   ├── fee_extraction.py   # Shared extraction prompt/parse/validate pipeline
│   │   ├── validator.py        # Validates LLM tables vs calculator output
│   │   └── output_validator.py # Validates API responses vs calculator
│   └── evaluation/
│       └── llm_judge.py        # Gemini-as-judge groundedness scoring → Langfuse
├── data/
│   ├── brokers.yaml            # Broker definitions (7 brokers)
│   └── output/
│       ├── fee_rules.json      # Structured FeeRule + HiddenCosts (runtime load)
│       └── *.json              # Generated analysis reports
├── scripts/                    # Scrape, generate, eval, and ops scripts
│   ├── refresh_fee_rules.py    # Re-extract fee rules from PDFs (CLI)
│   ├── send_weekly_email.py    # Standalone weekly email sender (Task Scheduler)
│   └── register_weekly_email_task.ps1
├── tests/                      # Test suite and validations
└── api/index.py                # Vercel deployment entry
```

### Layers

| Layer | Components | Responsibility |
|-------|-----------|----------------|
| **API** | `api/server.py` | Request handling, language routing, Langfuse tracing |
| **Calculation** | `validation/fee_calculator.py`, `persona_calculator.py`, `validator.py`, `output_validator.py` | Deterministic fees, TCO, and validation — the source of truth for every number |
| **Intelligence** | `sources/llm_extract.py`, `validation/fee_extraction.py`, chat/analysis/notes prompts | LLM extraction and narrative generation (never arithmetic) |
| **Data** | `data/brokers.yaml`, `data/output/fee_rules.json`, filesystem + in-memory caches | Broker config, structured fee rules, cached rankings |
| **Observability** | `evaluation/llm_judge.py`, Langfuse | Async tracing, auto groundedness scoring, `/feedback` thumbs-up/down + review queue |

## 📊 Analysis Capabilities

### Fee Structure Analysis

- **Flat Fees**: Fixed cost per transaction
- **Percentage Fees**: Variable cost based on transaction value  
- **Tiered Fees**: Different rates for different transaction sizes
- **Composite Fees**: Combination of flat + percentage components

### Investment Scenarios

**Investor Profile A**: Starting investor
- Initial investment: €0
- Monthly investment: €169
- Duration: 5 years
- Focus: Cost-effective regular investing

**Investor Profile B**: Established investor  
- Initial investment: €10,000
- Monthly investment: €500
- Duration: 5 years
- Focus: High-value portfolio management

### Cost Comparison

- Transaction cost analysis by trade size (€250, €500, €1,000, €5,000)
- Custody fee comparison (annual portfolio management costs)
- Total cost of ownership calculations for different investment strategies

## 🤖 LLM Integration

### Models by task

| Task | Default model | Notes |
|------|---------------|-------|
| PDF → raw fee records (`sources/llm_extract.py`) | `claude-sonnet-4-6` | `gpt-4o` also supported (temp 0.0) |
| Fee-rule structuring & financial-analysis narrative | `claude-sonnet-4-6` | temp 0.0 |
| Cost-comparison table notes | `claude-sonnet-4-6` | LLM used only for notes, not numbers |
| Chat endpoint | `groq/llama-3.3-70b-versatile` | falls back to `gemini-2.0-flash`; temp 0.3 |
| Groundedness judge (`evaluation/llm_judge.py`) | `gemini-2.5-pro` | Google Genai SDK, `GOOGLE_API_KEY` |

### Enhanced Extraction Features

- **Broker-specific prompts**: Tailored extraction rules for each broker
- **Handling fee detection**: Captures often-missed processing fees
- **Market-specific pricing**: Distinguishes between different exchange rates
- **Composite fee parsing**: Handles complex fee structures (e.g., "€2 + 0.35%")

### Data Quality Validation

- Automated validation against expected fee ranges
- Detection of common extraction errors (missing handling fees, wrong market data)
- Comprehensive test suite with realistic broker document samples

## � Docker & Langfuse Integration

### Production-Ready Containerization

Be-Invest now includes complete Docker support for easy deployment and scaling:

**Docker Components:**
- **Multi-stage Dockerfile** - Optimized Python 3.9 image with minimal footprint
- **docker-compose.yml** - Complete stack: be-invest API + Langfuse + PostgreSQL
- **Health checks** - Automatic monitoring and recovery
- **Volume persistence** - Data and database persistence across restarts
- **Network isolation** - Internal Docker network for secure service communication

### Langfuse Integration

**Complete LLM Observability:**
- **Trace Tracking** - Every LLM call is automatically traced
- **Cost Monitoring** - Track tokens used and API costs
- **Quality Scoring** - Automatic evaluation of LLM outputs
- **Performance Metrics** - Monitor latency and throughput
- **Web Dashboard** - Beautiful UI at http://localhost:3000

**Integrated Evaluations:**
- Groundedness scoring for financial data accuracy
- Hallucination detection in fee comparisons
- JSON validity checks on structured outputs
- Data completeness scoring

### Quick Docker Setup

```bash
# One-command setup (includes Langfuse automatically)
bash docker-deploy.sh setup

# Or for Windows
docker-deploy.bat setup

# Access services
# API: http://localhost:8000/docs
# Langfuse: http://localhost:3000
```

See **[DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)** for comprehensive installation, configuration, and troubleshooting guides.

## �📈 Example Analysis Results

```json
{
  "cheapest_by_trade_size": {
    "ETF": {
      "250": {"broker": "Keytrade Bank", "cost": 0.47},
      "1000": {"broker": "Degiro Belgium", "cost": 1.00},
      "5000": {"broker": "Degiro Belgium", "cost": 1.00}
    },
    "Stocks": {
      "250": {"broker": "Rebel", "cost": 3.00},
      "5000": {"broker": "Rebel", "cost": 3.00}
    }
  },
  "investor_scenarios": {
    "Profile_A": {
      "ETF": {"broker": "Keytrade Bank", "total_cost": 19.20},
      "Stocks": {"broker": "Rebel", "total_cost": 180.00}
    }
  }
}
```

## 🌐 API Endpoints

### Health & Status
```http
GET /health                           # Application health check
```

### Broker Information
```http
GET /brokers                          # List all configured brokers
GET /cost-analysis                    # Get comprehensive cost analysis
GET /cost-analysis/{broker_name}      # Get specific broker analysis
GET /summary                          # Get a high-level broker fee summary
```

### Cost Comparison & Analysis
```http
GET /cost-comparison-tables           # Generate cost comparison tables (with language support)
POST /refresh-and-analyze             # Refresh PDFs and analyze broker fees
GET /financial-analysis               # Generate detailed financial analysis
POST /refresh-pdfs                    # Refresh broker fee documents (PDFs)
```

### Feedback & Notifications
```http
POST /feedback                        # Record thumbs-up/down on a chat response (Langfuse score + review queue)
POST /email/send                      # Manually trigger an immediate broker-fee report email
```

### News Management
```http
GET /news                             # Get all news flashes
GET /news/broker/{broker_name}        # Get broker-specific news
GET /news/recent                      # Get recent news (default limit: 10)
GET /news/statistics                  # Get news data statistics
POST /news/scrape                     # Trigger automated news scraping
POST /news                            # Add new news flash (POST body)
DELETE /news                          # Delete specific news flash
```

### Interactive Chat
```http
POST /chat                            # Chat about brokers with natural language
                                      # Supports multiple LLM models and languages
```

### Documentation
```http
GET /docs                             # Swagger UI interactive documentation
GET /redoc                            # ReDoc alternative documentation
GET /openapi.json                     # OpenAPI specification
```

See [API Documentation](docs/API.md) for detailed endpoint specifications.

## 🧪 Testing and Validation

### Test Suite

```bash
# Run all tests
python -m pytest tests/

# Run specific validation tests
python tests/test_llm_extraction_validation.py
python tests/test_data_quality_validation.py

# Run end-to-end verification
python scripts/final_verification.py
```

### Quality Assurance

- **Data Quality Validation**: Automated checks against known broker fee structures
- **LLM Extraction Testing**: Realistic document samples for each broker
- **API Integration Tests**: End-to-end testing of web service endpoints
- **Performance Benchmarks**: Caching effectiveness and response time monitoring

## 🔄 Development Workflow

### Adding New Brokers

1. Update `data/brokers.yaml` with broker configuration
2. Add test data in `tests/test_data_quality_validation.py`
3. Create broker-specific extraction rules in `tests/enhanced_llm_prompts.py`
4. Run validation: `python tests/test_llm_extraction_validation.py`

### Updating Fee Structures

1. Modify expected values in test files
2. Update LLM prompts if needed
3. Re-run analysis pipeline
4. Validate results against real broker data

## 🚀 Deployment

### Docker Deployment (Recommended for Production)

Be-Invest includes complete Docker support with Langfuse integration for LLM tracing and observability.

#### Quick Start with Docker

```bash
# 1. Create environment file
cp .env.example .env
nano .env  # Edit with your API keys

# 2. Build and start all services
docker-compose up -d

# 3. Check services are running
docker-compose ps

# 4. Access the application
# API: http://localhost:8000/docs
# Langfuse: http://localhost:3000
```

#### Deployment Helper Scripts

For easier management, use the provided helper scripts:

**Linux/Mac:**
```bash
bash docker-deploy.sh setup    # Full setup
bash docker-deploy.sh start    # Start services
bash docker-deploy.sh logs     # View logs
bash docker-deploy.sh health   # Check health
bash docker-deploy.sh help     # Show all commands
```

**Windows:**
```cmd
docker-deploy.bat setup       :: Full setup
docker-deploy.bat start       :: Start services
docker-deploy.bat logs        :: View logs
docker-deploy.bat health      :: Check health
docker-deploy.bat help        :: Show all commands
```

#### What's Included

```
docker-compose.yml      # Multi-container orchestration
Dockerfile              # Be-Invest application image
.dockerignore          # Optimize Docker build
.env.example           # Environment variable template
```

Services:
- **be-invest**: FastAPI application (port 8000)
- **langfuse-server**: LLM observability UI (port 3000)
- **langfuse-db**: PostgreSQL database (port 5433)

#### More Information

See **[DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)** for:
- Detailed configuration options
- Production deployment guide
- Troubleshooting common issues
- Backup and maintenance procedures
- Scaling and monitoring setup

### Local Development

```bash
# Start API server
uvicorn be_invest.api.server:app --reload --port 8000

# Run analysis pipeline
python scripts/analyze_broker_fees.py
```

### Weekly Email Scheduling (Windows host)

The weekly broker fee email is delivered by **Windows Task Scheduler** running a standalone Python script — **not** by an in-process timer inside uvicorn. This change was made after an in-process `threading.Timer` drifted by ~9 hours when the laptop slept mid-week (Python timers don't advance while the host is suspended).

**Components:**
- `scripts/send_weekly_email.py` — standalone sender. Imports `build_and_send_report` directly and sends via SMTP. Exit code 0/1 so Task Scheduler's missed-run catch-up works. Logs to `logs/weekly_email.log`.
- `scripts/register_weekly_email_task.ps1` — idempotent registration script.
- `.env` flag `EMAIL_SCHEDULER_ENABLED=false` — disables the legacy in-process timer in `src/be_invest/api/server.py` so the two schedulers don't both fire.

**Install / re-install the task:**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_weekly_email_task.ps1
```

Task name: `BeInvest-WeeklyEmail`. Trigger: Mondays 09:00 local. Key flags: `StartWhenAvailable` (fires on next wake if the slot was missed), `WakeToRun`, `AllowStartIfOnBatteries`. Runs as the interactive user — no stored password needed.

**Dry run (no SMTP):**
```bash
python -c "import sys; sys.path.insert(0, 'src'); \
  from dotenv import load_dotenv; load_dotenv('.env'); \
  from be_invest import email_sender; \
  email_sender.send_email = lambda s, h, r: print(f'[DRY] {s} | {len(r)} recipients | {len(h)} bytes'); \
  print(email_sender.build_and_send_report())"
```

**Force a real send right now:**
```powershell
Start-ScheduledTask -TaskName 'BeInvest-WeeklyEmail'
```

**Uninstall:**
```powershell
Unregister-ScheduledTask -TaskName 'BeInvest-WeeklyEmail' -Confirm:$false
```

On a Linux host, the equivalent is a systemd timer with `Persistent=true` (or an `anacron` entry) targeting the same script.

### Vercel Deployment

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy to Vercel
vercel

# Environment variables required:
# - OPENAI_API_KEY or ANTHROPIC_API_KEY
# - LANGFUSE_PUBLIC_KEY (if tracing enabled)
# - LANGFUSE_SECRET_KEY (if tracing enabled)
```

## 📚 Documentation

### Getting Started
- **[DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)** ⭐ - Complete Docker setup and deployment guide (recommended)
- **[.env.example](.env.example)** - Environment variable configuration template

### Additional Resources
For more detailed documentation, see the **[docs/ folder](docs/)** which contains:

- **[API Reference](docs/API.md)** - Complete API documentation
- **[React Integration](docs/REACT_INTEGRATION.md)** - Frontend integration guide with examples
- **[Development Guide](docs/DEVELOPMENT.md)** - Contributing and development setup
- **[Data Sources](docs/DATA_SOURCES.md)** - Information about broker data sources
- **[LLM Integration](docs/LLM_INTEGRATION.md)** - Advanced LLM configuration
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment instructions

📖 **[Documentation Index](docs/README.md)** - Navigate all available documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone and setup development environment
git clone https://github.com/your-username/be-invest.git
cd be-invest
pip install -e ".[dev]"

# Run pre-commit hooks
pre-commit install

# Run tests
python -m pytest tests/ -v
```

## 🆘 Support

### Common Issues

**Docker Setup Issues**
- Check Docker daemon is running: `docker ps`
- Verify ports are available: `docker-compose ps`
- Check logs: `docker-compose logs be-invest`
- See **[DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md#troubleshooting)** for detailed Docker troubleshooting

**Langfuse Connection**
- Verify Langfuse is running: `curl http://localhost:3000`
- Check environment variables in .env file
- Restart be-invest container after updating .env: `docker-compose restart be-invest`

**API Key Issues**
- Ensure .env file has correct keys (copy from .env.example)
- For Docker: API keys should be in .env file before running `docker-compose up`
- Local development: Set environment variables before running uvicorn

**LLM Extraction Errors**
- Ensure API keys are set correctly
- Check internet connectivity for API access
- Verify broker document formats haven't changed

**Data Quality Issues**
- Run validation tests to identify specific problems
- Check broker websites for fee structure updates
- Update test expectations in validation files

**API Deployment Issues**
- Verify all environment variables are set
- Check Python version compatibility (3.9+)
- Ensure all dependencies are installed

### Getting Help

- 📋 [Issues](https://github.com/your-username/be-invest/issues) - Report bugs or request features
- 💬 [Discussions](https://github.com/your-username/be-invest/discussions) - Community support
- 📧 [Email](mailto:support@be-invest.com) - Direct support

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI** and **Anthropic** for providing LLM APIs
- **Belgian brokers** for maintaining transparent fee structures
- **FastAPI** and **Pydantic** for excellent web framework and data validation
- **pytest** for comprehensive testing capabilities

---

**Disclaimer**: This tool is for informational purposes only. Always verify broker fees directly with the respective institutions before making investment decisions. Fee structures may change, and this tool may not reflect the most current information.
