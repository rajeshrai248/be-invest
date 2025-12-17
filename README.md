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

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+** - [Download Python](https://python.org/downloads/)
- **Git** - [Download Git](https://git-scm.com/downloads) 
- **API Key** - Get one from [OpenAI](https://platform.openai.com/api-keys) or [Anthropic](https://console.anthropic.com/)

### Installation & Setup

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

```bash
# Start the API server
uvicorn be_invest.api.server:app --reload

# Open http://localhost:8000/docs for interactive API documentation
```

### Example API Usage

```bash
# Check API health
curl http://localhost:8000/api/health

# Compare brokers for a 1000€ ETF trade
curl -X POST http://localhost:8000/api/compare \
  -H "Content-Type: application/json" \
  -d '{
    "trade_amount": 1000,
    "instrument_type": "ETFs",
    "brokers": ["Bolero", "Keytrade Bank", "Degiro Belgium"]
  }'
```

### What You Get

After running the analysis, you'll find these reports in `data/output/analysis/`:

- **`summary_report.md`** - Executive summary with key findings
- **`cheapest_by_trade_size.json`** - Best broker for each trade size
- **`cheapest_by_scenario.json`** - Best broker for different investor profiles  
- **`full_broker_analysis.csv`** - Complete data for spreadsheet analysis

**Key Insights Example:**
- €250 trades: Keytrade Bank (€0.47) for ETFs
- €1000 trades: Degiro Belgium (€1.00) for ETFs
- €5000 trades: Degiro Belgium (€1.00) for ETFs

## 📋 Supported Brokers

| Broker | ETFs | Stocks | Bonds | Options | LLM Extraction | Status |
|--------|------|--------|-------|---------|----------------|--------|
| **Bolero** | ✅ | ✅ | ✅ | ❌ | ✅ | Active |
| **Keytrade Bank** | ✅ | ✅ | ❌ | ✅ | ✅ | Active |
| **Degiro Belgium** | ✅ | ✅ | ❌ | ✅ | ✅ | Active |
| **ING Self Invest** | ✅ | ✅ | ✅ | ❌ | ✅ | Active |
| **Rebel** (formerly Belfius) | ✅ | ✅ | ✅ | ❌ | ✅ | Active |
| **Revolut** | ✅ | ✅ | ❌ | ❌ | ⚠️ | Limited |

## 🔧 Architecture

```
be-invest/
├── src/be_invest/           # Core library
│   ├── models.py           # Data models (Broker, FeeRecord)
│   ├── sources/            # Data extraction modules
│   │   ├── llm_extract.py  # LLM-powered extraction
│   │   ├── manual.py       # Manual data import
│   │   └── pdf_extract.py  # PDF text extraction
│   ├── cache.py            # Caching system
│   └── api/                # FastAPI web service
├── data/                   # Configuration and output
│   ├── brokers.yaml        # Broker definitions
│   └── output/             # Generated reports
├── scripts/                # Analysis and utility scripts
├── tests/                  # Test suite and validations
└── api/                    # Vercel deployment entry
```

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

### Supported Models

- **OpenAI**: GPT-4o, GPT-4 Turbo
- **Anthropic**: Claude 3 Opus, Claude 3 Haiku

### Enhanced Extraction Features

- **Broker-specific prompts**: Tailored extraction rules for each broker
- **Handling fee detection**: Captures often-missed processing fees
- **Market-specific pricing**: Distinguishes between different exchange rates
- **Composite fee parsing**: Handles complex fee structures (e.g., "€2 + 0.35%")

### Data Quality Validation

- Automated validation against expected fee ranges
- Detection of common extraction errors (missing handling fees, wrong market data)
- Comprehensive test suite with realistic broker document samples

## 📈 Example Analysis Results

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

### Core Endpoints

```http
GET /api/brokers                    # List all brokers
GET /api/brokers/{name}/fees        # Get fees for specific broker
POST /api/analyze                   # Run cost analysis
GET /api/health                     # Health check
```

### Analysis Endpoints

```http
POST /api/compare                   # Compare multiple brokers
GET /api/cheapest/{amount}          # Find cheapest for trade size
POST /api/scenarios                 # Investment scenario analysis
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

### Local Development

```bash
# Start API server
uvicorn be_invest.api.server:app --reload --port 8000

# Run analysis pipeline
python scripts/analyze_broker_fees.py
```

### Vercel Deployment

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy to Vercel
vercel

# Environment variables required:
# - OPENAI_API_KEY or ANTHROPIC_API_KEY
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8000
CMD ["uvicorn", "be_invest.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 📚 Documentation

For complete documentation, see the **[docs/ folder](docs/)** which contains:

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
