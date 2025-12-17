# Changelog

All notable changes to the BE-Invest project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2025-12-17 - Documentation Cleanup

### Changed
- **Consolidated Documentation**: Merged GETTING_STARTED.md content into README.md for better user experience
- **Enhanced Quick Start**: Improved installation and setup instructions with clearer examples
- **Streamlined Structure**: Removed redundant documentation files

### Removed
- **DEBUG_LOGGING_GUIDE.md**: Session-specific debugging guide no longer needed
- **QUICKFIX_REFERENCE.md**: Empty reference file
- **GETTING_STARTED.md**: Content consolidated into main README

## [0.2.0] - 2025-12-09 - Rudolf Requirements Implementation

### Added
- **Enhanced LLM Extraction System**: Comprehensive AI-powered fee extraction with broker-specific prompts
- **Data Quality Validation Framework**: Automated validation against expected broker fee structures  
- **Broker-Specific Extraction Rules**: Tailored prompts for each broker to handle unique fee structures
- **Comprehensive Test Suite**: End-to-end validation with realistic broker document samples
- **Investment Scenario Analysis**: Cost calculations for different investor profiles (A & B scenarios)
- **Fee Structure Classification**: Automatic identification of flat, percentage, tiered, and composite fee structures
- **Custody Fee Detection**: Automated detection and analysis of annual portfolio management fees
- **Cost Comparison Engine**: Find cheapest brokers by trade size and investment scenario
- **Multiple Output Formats**: JSON, CSV, and Markdown reports for different use cases

### Enhanced
- **Broker Coverage**: Updated data for Bolero, Keytrade Bank, Degiro Belgium, ING Self Invest, and Rebel (formerly Belfius)
- **Prompt Engineering**: Advanced prompts with specific instructions for problematic extractions
- **Error Detection**: Automated identification of common issues like missing handling fees
- **Market-Specific Pricing**: Proper handling of exchange-specific fees (Brussels vs Paris/Amsterdam)
- **Caching System**: Intelligent caching to minimize LLM API costs
- **API Endpoints**: RESTful API for programmatic access to all analysis features

### Fixed
- **Bolero Fee Correction**: Fixed €15 fee structure (was incorrectly showing €10)
- **Degiro Handling Fees**: Added detection of €1 handling fee that was often missed
- **Rebel Market Confusion**: Corrected Brussels vs Paris/Amsterdam pricing extraction
- **Composite Fee Parsing**: Improved handling of "€X + Y%" fee structures
- **Import Path Issues**: Resolved enhanced prompts import errors

### Changed
- **Belfius → Rebel**: Renamed broker as requested
- **Bonds Analysis**: Removed bonds from analysis due to data quality issues  
- **Manual Data Entry**: Eliminated in favor of automated LLM extraction
- **Validation Approach**: Shifted from manual verification to automated testing

### Technical Improvements
- **LLM Integration**: Support for OpenAI GPT-4o and Anthropic Claude models
- **Text Preprocessing**: Smart document chunking and fee-content focusing
- **Response Validation**: Comprehensive JSON schema validation and post-processing
- **Error Handling**: Robust error handling with fallback strategies
- **Performance Optimization**: Concurrent processing and intelligent caching
- **Documentation**: Complete API documentation and development guides

## [0.1.0] - 2025-11-01 - Initial Release

### Added
- **Core Data Models**: Broker, FeeRecord, and DataSource models
- **Basic API Server**: FastAPI-based REST API with health endpoints
- **PDF Text Extraction**: Basic PDF processing for broker documents
- **Manual Data Import**: CSV-based manual fee data entry
- **Simple Caching**: File-based caching for extracted data
- **Broker Configuration**: YAML-based broker configuration system
- **Basic Analysis**: Simple fee comparison functionality
- **Vercel Deployment**: Serverless deployment configuration

### Supported Brokers
- Bolero (basic fee extraction)
- Keytrade Bank (basic fee extraction)
- Degiro Belgium (basic fee extraction)
- ING Self Invest (basic fee extraction)
- Belfius (basic fee extraction)
- Revolut (limited support)

## [Unreleased] - Future Enhancements

### Planned Features
- **Real-time Monitoring**: Webhook notifications for broker fee changes
- **Advanced Analytics**: Historical trend analysis and fee forecasting
- **Multi-language Support**: French and German language interfaces
- **Mobile API**: Optimized endpoints for mobile applications
- **Broker Notifications**: Alert system for significant fee changes
- **Portfolio Integration**: Connect with portfolio management platforms
- **Advanced Caching**: Redis-based distributed caching
- **ML-based Quality Assurance**: Machine learning for anomaly detection

### Research Areas
- **Document Understanding**: Advanced PDF layout analysis
- **Structured Data Extraction**: Direct table extraction from complex documents  
- **Semantic Change Detection**: Understanding meaningful vs cosmetic changes
- **Multi-modal Processing**: Image and chart analysis in documents
- **European Expansion**: Support for brokers in other EU countries

### Technical Debt
- **Database Migration**: Move from file-based to database storage
- **Async Processing**: Background job queue for long-running extractions
- **Rate Limiting**: Advanced rate limiting with user quotas
- **Security Hardening**: Enhanced authentication and authorization
- **Performance Testing**: Load testing and optimization
- **Monitoring Integration**: Prometheus/Grafana dashboards

## Migration Notes

### From 0.1.0 to 0.2.0

**Breaking Changes:**
- Broker name "Belfius" changed to "Rebel" - update any hardcoded references
- Manual CSV data import deprecated - use LLM extraction instead
- Some API endpoints changed response format for consistency

**Environment Variables:**
```bash
# Required for LLM features
export OPENAI_API_KEY="your-key"  
# OR
export ANTHROPIC_API_KEY="your-key"

# Optional configuration
export CACHE_TTL_HOURS=24
export MAX_CONCURRENT_EXTRACTIONS=3
```

**Configuration Updates:**
```yaml
# data/brokers.yaml - Belfius renamed to Rebel
- name: Rebel  # Previously "Belfius"
  website: https://www.belfius.be/
  # ... rest unchanged
```

**API Changes:**
- `/api/brokers` now includes LLM extraction status
- New endpoints: `/api/compare`, `/api/scenarios`, `/api/cheapest/{amount}`
- Enhanced response format with additional metadata

**File Structure:**
```
# New directories
docs/                    # Comprehensive documentation
tests/enhanced_llm_prompts.py    # Advanced LLM configurations
scripts/analyze_broker_fees.py  # Analysis pipeline
data/output/analysis/            # Generated reports
data/output/validation/          # Validation results
```

### Testing Migration

```bash
# Validate your setup after migration
python scripts/final_verification.py

# Expected output should show all systems working
# ✅ Enhanced prompts working
# ✅ Data quality validation active  
# ✅ Analysis pipeline working
```

### Rollback Instructions

If issues arise after migration:

```bash
# Rollback to manual data approach
git checkout v0.1.0

# Or disable LLM features
unset OPENAI_API_KEY ANTHROPIC_API_KEY

# Use fallback analysis
python scripts/analyze_broker_fees.py --no-llm
```

## Support and Feedback

### Reporting Issues

When reporting issues, include:
- Version number: `python -c "import be_invest; print(be_invest.__version__)"`
- Environment: Development/Production/Staging  
- Python version: `python --version`
- Error logs with stack traces
- Steps to reproduce

### Feature Requests

Submit feature requests with:
- Clear description of the use case
- Expected behavior  
- Alternative solutions considered
- Impact assessment (nice-to-have vs critical)

### Contributing

See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for:
- Development environment setup
- Coding standards and guidelines  
- Testing requirements
- Pull request process

---

For questions about any changes or need help migrating, please:
- 📋 [Create an issue](https://github.com/your-username/be-invest/issues)
- 💬 [Start a discussion](https://github.com/your-username/be-invest/discussions)
- 📧 [Contact support](mailto:support@be-invest.com)
